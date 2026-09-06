from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


SPORT_ENDPOINTS = {
    "MLB": "https://v1.baseball.api-sports.io",
    "NFL": "https://v1.american-football.api-sports.io",
    "NBA": "https://v1.basketball.api-sports.io",
}

MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"


class ApiSportsError(RuntimeError):
    """Error de proveedor. Nunca se sustituyen datos con datos inventados."""


@dataclass(frozen=True)
class ApiResult:
    response: list[dict[str, Any]]
    remaining_requests: int | None = None


class ApiSportsClient:

    def __init__(
        self,
        api_key: str,
        timeout_seconds: int = 25,
    ) -> None:

        self.api_key = str(api_key or "").strip()
        self.timeout_seconds = timeout_seconds

        self._fallback_odds_cache: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

        self._batch_odds_supported: dict[str, bool] = {}

        # Si API-Sports nos dice que se acabó el límite MLB,
        # dejamos de insistir durante esta ejecución.
        self._mlb_api_sports_available = True

    # ========================================================
    # API-SPORTS
    # ========================================================

    def _get(
        self,
        sport: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> ApiResult:

        if sport not in SPORT_ENDPOINTS:
            raise ValueError(
                f"Deporte desconocido: {sport}"
            )

        if not self.api_key:
            raise ApiSportsError(
                "API_SPORTS_KEY está vacía."
            )

        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value is not None
            and value != ""
        }

        query = urllib.parse.urlencode(
            clean_params
        )

        url = (
            f"{SPORT_ENDPOINTS[sport]}/"
            f"{endpoint.lstrip('/')}"
        )

        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "x-apisports-key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "sports-predictor-github/1.0",
            },
        )

        last_error: Exception | None = None

        for attempt in range(3):

            try:

                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:

                    payload = json.loads(
                        response.read().decode(
                            "utf-8"
                        )
                    )

                    remaining_raw = (
                        response.headers.get(
                            "x-ratelimit-requests-remaining"
                        )
                    )

                    remaining = (
                        int(remaining_raw)
                        if remaining_raw
                        else None
                    )

                    break

            except urllib.error.HTTPError as exc:

                body = (
                    exc.read()
                    .decode(
                        "utf-8",
                        errors="replace",
                    )[:1000]
                )

                last_error = ApiSportsError(
                    f"{sport} {endpoint}: "
                    f"HTTP {exc.code}. {body}"
                )

                if (
                    exc.code not in {
                        429,
                        500,
                        502,
                        503,
                        504,
                    }
                    or attempt == 2
                ):
                    raise last_error from exc

                time.sleep(
                    2 ** attempt
                )

            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as exc:

                last_error = exc

                if attempt == 2:
                    raise ApiSportsError(
                        f"{sport} {endpoint}: "
                        f"no se pudo leer la respuesta ({exc})"
                    ) from exc

                time.sleep(
                    2 ** attempt
                )

        else:
            raise ApiSportsError(
                str(last_error)
            )

        provider_errors = (
            payload.get("errors")
            if isinstance(payload, dict)
            else None
        )

        if provider_errors:

            text = str(
                provider_errors
            ).lower()

            if (
                sport == "MLB"
                and (
                    "request limit" in text
                    or "limit for the day" in text
                    or "rate limit" in text
                )
            ):
                self._mlb_api_sports_available = False

            raise ApiSportsError(
                f"{sport} {endpoint}: "
                f"{provider_errors}"
            )

        raw_response = (
            payload.get(
                "response",
                [],
            )
            if isinstance(payload, dict)
            else []
        )

        if not isinstance(
            raw_response,
            list,
        ):
            raise ApiSportsError(
                f"{sport} {endpoint}: "
                "formato inesperado"
            )

        return ApiResult(
            response=raw_response,
            remaining_requests=remaining,
        )

    # ========================================================
    # MLB STATS API PÚBLICA
    # ========================================================

    def _mlb_get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value is not None
            and value != ""
        }

        query = urllib.parse.urlencode(
            clean_params
        )

        url = (
            f"{MLB_STATS_BASE}/"
            f"{endpoint.lstrip('/')}"
        )

        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "sports-predictor-github/1.0",
            },
        )

        last_error: Exception | None = None

        for attempt in range(3):

            try:

                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:

                    payload = json.loads(
                        response.read().decode(
                            "utf-8"
                        )
                    )

                if not isinstance(
                    payload,
                    dict,
                ):
                    raise ApiSportsError(
                        "MLB Stats API devolvió "
                        "un formato inesperado."
                    )

                return payload

            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as exc:

                last_error = exc

                if attempt == 2:
                    raise ApiSportsError(
                        "MLB Stats API: "
                        f"{exc}"
                    ) from exc

                time.sleep(
                    2 ** attempt
                )

        raise ApiSportsError(
            f"MLB Stats API: {last_error}"
        )

    # ========================================================
    # CONVERTIR MLB STATS -> FORMATO INTERNO
    # ========================================================

    def _convert_mlb_game(
        self,
        game: dict[str, Any],
        season: int | str | None = None,
    ) -> dict[str, Any]:

        teams = (
            game.get("teams")
            or {}
        )

        away_block = (
            teams.get("away")
            or {}
        )

        home_block = (
            teams.get("home")
            or {}
        )

        away_team = (
            away_block.get("team")
            or {}
        )

        home_team = (
            home_block.get("team")
            or {}
        )

        status_block = (
            game.get("status")
            or {}
        )

        away_score = (
            away_block.get("score")
        )

        home_score = (
            home_block.get("score")
        )

        game_date = str(
            game.get("gameDate")
            or ""
        )

        timestamp = None

        if game_date:
            try:
                timestamp = int(
                    datetime.fromisoformat(
                        game_date.replace(
                            "Z",
                            "+00:00",
                        )
                    ).timestamp()
                )
            except ValueError:
                timestamp = None

        season_value = (
            season
            or game.get("season")
            or datetime.now(
                timezone.utc
            ).year
        )

        return {
            "id": game.get("gamePk"),

            "date": game_date,

            "timestamp": timestamp,

            "league": {
                "season": season_value,
            },

            "season": season_value,

            "status": {
                "short": (
                    status_block.get(
                        "statusCode"
                    )
                    or ""
                ),
                "long": (
                    status_block.get(
                        "detailedState"
                    )
                    or status_block.get(
                        "abstractGameState"
                    )
                    or ""
                ),
            },

            "teams": {
                "away": {
                    "id": away_team.get("id"),
                    "name": away_team.get("name"),
                },
                "home": {
                    "id": home_team.get("id"),
                    "name": home_team.get("name"),
                },
            },

            "scores": {
                "away": {
                    "total": away_score,
                    "runs": away_score,
                },
                "home": {
                    "total": home_score,
                    "runs": home_score,
                },
            },

            "_source": "MLB_STATS_API",

            "_mlb_raw": game,
        }

    def _mlb_schedule(
        self,
        *,
        date_iso: str | None = None,
        team_id: int | str | None = None,
        season: int | str | None = None,
    ) -> ApiResult:

        params: dict[str, Any] = {
            "sportId": 1,
        }

        if date_iso:
            params["date"] = date_iso

        if team_id is not None:
            params["teamId"] = team_id

        if season is not None:
            params["season"] = season

        payload = self._mlb_get(
            "schedule",
            params,
        )

        converted: list[
            dict[str, Any]
        ] = []

        for date_block in (
            payload.get("dates")
            or []
        ):

            for game in (
                date_block.get("games")
                or []
            ):

                if isinstance(
                    game,
                    dict,
                ):
                    converted.append(
                        self._convert_mlb_game(
                            game,
                            season=season,
                        )
                    )

        return ApiResult(
            response=converted,
            remaining_requests=None,
        )

    # ========================================================
    # TODOS LOS PARTIDOS DEL DÍA
    #
    # MLB:
    # API-Sports -> si falla -> MLB Stats API
    # ========================================================

    def games_for_date(
        self,
        sport: str,
        date_iso: str,
    ) -> ApiResult:

        if sport != "MLB":

            return self._get(
                sport,
                "games",
                {
                    "date": date_iso,
                },
            )

        if self._mlb_api_sports_available:

            try:

                result = self._get(
                    "MLB",
                    "games",
                    {
                        "date": date_iso,
                    },
                )

                if result.response:
                    return result

            except ApiSportsError as exc:

                self._mlb_api_sports_available = False

                print(
                    "MLB: API-Sports no disponible. "
                    "Activando MLB Stats API."
                )

                print(
                    f"Motivo: {exc}"
                )

        result = self._mlb_schedule(
            date_iso=date_iso,
        )

        print(
            "MLB: partidos obtenidos desde "
            "MLB Stats API."
        )

        return result

    # ========================================================
    # HISTORIAL DE EQUIPO
    #
    # MLB también tiene fallback.
    # ========================================================

    def team_history(
        self,
        sport: str,
        team_id: int | str,
        season: int | str,
    ) -> ApiResult:

        if sport != "MLB":

            return self._get(
                sport,
                "games",
                {
                    "team": team_id,
                    "season": season,
                },
            )

        # Si los IDs provienen de MLB Stats,
        # consultar directamente MLB Stats.
        if not self._mlb_api_sports_available:

            return self._mlb_schedule(
                team_id=team_id,
                season=season,
            )

        try:

            result = self._get(
                "MLB",
                "games",
                {
                    "team": team_id,
                    "season": season,
                },
            )

            if result.response:
                return result

        except ApiSportsError:

            self._mlb_api_sports_available = False

        return self._mlb_schedule(
            team_id=team_id,
            season=season,
        )

    # ========================================================
    # CUOTAS
    #
    # MLB Stats NO TIENE CUOTAS.
    #
    # Si API-Sports no está disponible:
    # devolver [].
    #
    # engine.py decidirá usando el modelo MLB,
    # SIN INVENTAR precios.
    # ========================================================

    def odds_for_date(
        self,
        sport: str,
        date_iso: str,
        game_ids: list[int | str],
    ) -> ApiResult:

        if (
            sport == "MLB"
            and not self._mlb_api_sports_available
        ):

            print(
                "MLB: cuotas API-Sports no disponibles. "
                "El modelo continuará SIN cuotas."
            )

            return ApiResult(
                response=[],
                remaining_requests=None,
            )

        batch = ApiResult(
            response=[],
            remaining_requests=None,
        )

        if self._batch_odds_supported.get(
            sport,
            True,
        ):

            try:

                batch = self._get(
                    sport,
                    "odds",
                    {
                        "date": date_iso,
                    },
                )

                if batch.response:

                    self._batch_odds_supported[
                        sport
                    ] = True

                    return batch

                self._batch_odds_supported[
                    sport
                ] = False

            except ApiSportsError as exc:

                self._batch_odds_supported[
                    sport
                ] = False

                if sport == "MLB":

                    self._mlb_api_sports_available = False

                    print(
                        "MLB: cuotas no disponibles. "
                        "Continuando con modelo deportivo."
                    )

                    print(
                        f"Motivo: {exc}"
                    )

                    return ApiResult(
                        response=[],
                        remaining_requests=None,
                    )

        combined: list[
            dict[str, Any]
        ] = []

        remaining: int | None = (
            batch.remaining_requests
        )

        for game_id in game_ids:

            cache_key = (
                sport,
                str(game_id),
            )

            if (
                cache_key
                not in self._fallback_odds_cache
            ):

                try:

                    result = self._get(
                        sport,
                        "odds",
                        {
                            "game": game_id,
                        },
                    )

                    self._fallback_odds_cache[
                        cache_key
                    ] = result.response

                    remaining = (
                        result.remaining_requests
                    )

                except ApiSportsError as exc:

                    self._fallback_odds_cache[
                        cache_key
                    ] = []

                    if sport == "MLB":

                        self._mlb_api_sports_available = False

                        print(
                            "MLB: límite/error de cuotas. "
                            "Se detienen más consultas "
                            "API-Sports para MLB."
                        )

                        print(
                            f"Motivo: {exc}"
                        )

                        break

            combined.extend(
                self._fallback_odds_cache[
                    cache_key
                ]
            )

        return ApiResult(
            response=combined,
            remaining_requests=remaining,
                )
