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

ESPN_NFL_BASE = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/football/nfl"
)


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

        self._mlb_games_api_sports_available = True
        self._mlb_odds_api_sports_available = True
        self._mlb_using_stats_api = False

        self._nfl_api_sports_available = True
        self._nfl_odds_api_sports_available = True
        self._nfl_using_espn = False

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
        payload: dict[str, Any] = {}
        remaining: int | None = None

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

                    try:

                        remaining = (
                            int(remaining_raw)
                            if remaining_raw is not None
                            else None
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        remaining = None

                break

            except urllib.error.HTTPError as exc:

                try:

                    body = (
                        exc.read()
                        .decode(
                            "utf-8",
                            errors="replace",
                        )[:1000]
                    )

                except Exception:

                    body = ""

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
    # GET JSON PÚBLICO
    # ========================================================

    def _public_get(
        self,
        url: str,
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

        full_url = (
            f"{url}?{query}"
            if query
            else url
        )

        request = urllib.request.Request(
            full_url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 "
                    "sports-predictor/1.0"
                ),
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
                        "Fuente pública devolvió "
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
                        f"Fuente pública: {exc}"
                    ) from exc

                time.sleep(
                    2 ** attempt
                )

        raise ApiSportsError(
            f"Fuente pública: {last_error}"
        )

    # ========================================================
    # ESPN NFL
    # ========================================================

    def _espn_nfl_get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self._public_get(
            (
                f"{ESPN_NFL_BASE}/"
                f"{endpoint.lstrip('/')}"
            ),
            params,
        )

    # ========================================================
    # ESTADO ESPN -> FORMATO API-SPORTS
    # ========================================================

    @staticmethod
    def _espn_nfl_status(
        event: dict[str, Any],
    ) -> dict[str, Any]:

        status = (
            event.get("status")
            or {}
        )

        status_type = (
            status.get("type")
            or {}
        )

        state = str(
            status_type.get("state")
            or ""
        ).lower()

        completed = bool(
            status_type.get("completed")
        )

        if completed or state == "post":

            short = "FT"

            long = (
                status_type.get("description")
                or "Finished"
            )

        elif state == "in":

            short = "LIVE"

            long = (
                status_type.get("detail")
                or status_type.get("description")
                or "In Progress"
            )

        else:

            short = "NS"

            long = (
                status_type.get("description")
                or "Not Started"
            )

        return {
            "short": short,
            "long": long,
            "timer": status.get(
                "displayClock"
            ),
        }

    # ========================================================
    # ESPN NFL -> FORMATO COMPATIBLE API-SPORTS
    # ========================================================

    def _convert_espn_nfl_game(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any]:

        competitions = (
            event.get("competitions")
            or []
        )

        competition = (
            competitions[0]
            if competitions
            and isinstance(
                competitions[0],
                dict,
            )
            else {}
        )

        competitors = (
            competition.get("competitors")
            or []
        )

        home: dict[str, Any] = {}
        away: dict[str, Any] = {}

        for competitor in competitors:

            if not isinstance(
                competitor,
                dict,
            ):
                continue

            side = competitor.get(
                "homeAway"
            )

            if side == "home":
                home = competitor

            elif side == "away":
                away = competitor

        def team_block(
            competitor: dict[str, Any],
        ) -> dict[str, Any]:

            team = (
                competitor.get("team")
                or {}
            )

            return {
                "id": team.get("id"),
                "name": (
                    team.get("displayName")
                    or team.get("name")
                    or ""
                ),
                "logo": team.get("logo"),
            }

        def score_value(
            competitor: dict[str, Any],
        ) -> int | None:

            raw = competitor.get(
                "score"
            )

            if raw in (
                None,
                "",
            ):
                return None

            try:

                return int(
                    float(raw)
                )

            except (
                TypeError,
                ValueError,
            ):

                return None

        event_date = str(
            event.get("date")
            or ""
        )

        timestamp = None
        date_only = ""
        time_only = ""

        if event_date:

            try:

                parsed_dt = (
                    datetime.fromisoformat(
                        event_date.replace(
                            "Z",
                            "+00:00",
                        )
                    )
                )

                timestamp = int(
                    parsed_dt.timestamp()
                )

                date_only = (
                    parsed_dt.strftime(
                        "%Y-%m-%d"
                    )
                )

                time_only = (
                    parsed_dt.strftime(
                        "%H:%M"
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                pass

        season_data = (
            event.get("season")
            or {}
        )

        season_year = (
            season_data.get("year")
            or datetime.now(
                timezone.utc
            ).year
        )

        week_data = (
            event.get("week")
            or {}
        )

        week_number = (
            week_data.get("number")
        )

        season_type = (
            season_data.get("type")
        )

        if season_type == 1:

            stage = "Pre Season"

        elif season_type == 2:

            stage = "Regular Season"

        elif season_type == 3:

            stage = "Post Season"

        else:

            stage = ""

        venue = (
            competition.get("venue")
            or {}
        )

        return {
            "game": {
                "id": event.get("id"),

                "stage": stage,

                "week": (
                    f"Week {week_number}"
                    if week_number is not None
                    else None
                ),

                "date": {
                    "timezone": "UTC",
                    "date": date_only,
                    "time": time_only,
                    "timestamp": timestamp,
                },

                "venue": {
                    "name": venue.get(
                        "fullName"
                    ),
                    "city": (
                        (
                            venue.get(
                                "address"
                            )
                            or {}
                        ).get(
                            "city"
                        )
                    ),
                },

                "status": (
                    self._espn_nfl_status(
                        event
                    )
                ),
            },

            "league": {
                "id": 1,
                "name": "NFL",
                "season": season_year,
            },

            "teams": {
                "home": team_block(
                    home
                ),
                "away": team_block(
                    away
                ),
            },

            "scores": {
                "home": {
                    "quarter_1": None,
                    "quarter_2": None,
                    "quarter_3": None,
                    "quarter_4": None,
                    "overtime": None,
                    "total": score_value(
                        home
                    ),
                },

                "away": {
                    "quarter_1": None,
                    "quarter_2": None,
                    "quarter_3": None,
                    "quarter_4": None,
                    "overtime": None,
                    "total": score_value(
                        away
                    ),
                },
            },

            "_source": "ESPN_NFL",

            "_espn_raw": event,
        }

    # ========================================================
    # NFL ESPN - PARTIDOS DEL DÍA
    # ========================================================

    def _espn_nfl_games_for_date(
        self,
        date_iso: str,
    ) -> ApiResult:

        payload = self._espn_nfl_get(
            "scoreboard",
            {
                "dates": (
                    date_iso.replace(
                        "-",
                        "",
                    )
                ),
                "limit": 100,
            },
        )

        converted: list[
            dict[str, Any]
        ] = []

        for event in (
            payload.get("events")
            or []
        ):

            if isinstance(
                event,
                dict,
            ):

                converted.append(
                    self._convert_espn_nfl_game(
                        event
                    )
                )

        print(
            "NFL ESPN: "
            f"{len(converted)} "
            "partidos encontrados "
            f"para {date_iso}."
        )

        return ApiResult(
            response=converted,
            remaining_requests=None,
        )

    # ========================================================
    # NFL ESPN - HISTORIAL DE EQUIPO
    # ========================================================

    def _espn_nfl_team_history(
        self,
        team_id: int | str,
        season: int | str,
    ) -> ApiResult:

        payload = self._espn_nfl_get(
            f"teams/{team_id}/schedule",
            {
                "season": season,
            },
        )

        converted: list[
            dict[str, Any]
        ] = []

        for event in (
            payload.get("events")
            or []
        ):

            if isinstance(
                event,
                dict,
            ):

                converted.append(
                    self._convert_espn_nfl_game(
                        event
                    )
                )

        return ApiResult(
            response=converted,
            remaining_requests=None,
        )

    # ========================================================
    # MLB STATS API
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
                "User-Agent": (
                    "sports-predictor-github/1.0"
                ),
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
    # MLB STATS -> FORMATO INTERNO
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

            except (
                ValueError,
                TypeError,
            ):

                timestamp = None

        season_value = (
            season
            or game.get("season")
            or datetime.now(
                timezone.utc
            ).year
        )

        linescore = (
            game.get("linescore")
            or {}
        )

        innings_raw = (
            linescore.get("innings")
            or []
        )

        innings: list[
            dict[str, Any]
        ] = []

        for inning in innings_raw:

            if not isinstance(
                inning,
                dict,
            ):
                continue

            away_inning = (
                inning.get("away")
                or {}
            )

            home_inning = (
                inning.get("home")
                or {}
            )

            innings.append(
                {
                    "num": inning.get(
                        "num"
                    ),
                    "away": (
                        away_inning.get(
                            "runs"
                        )
                    ),
                    "home": (
                        home_inning.get(
                            "runs"
                        )
                    ),
                }
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
                    "id": away_team.get(
                        "id"
                    ),
                    "name": away_team.get(
                        "name"
                    ),
                },
                "home": {
                    "id": home_team.get(
                        "id"
                    ),
                    "name": home_team.get(
                        "name"
                    ),
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

            "innings": innings,

            "_source": "MLB_STATS_API",

            "_mlb_raw": game,
        }

    # ========================================================
    # MLB SCHEDULE
    # ========================================================

    def _mlb_schedule(
        self,
        *,
        date_iso: str | None = None,
        team_id: int | str | None = None,
        season: int | str | None = None,
    ) -> ApiResult:

        params: dict[str, Any] = {
            "sportId": 1,
            "hydrate": "linescore",
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

            if not isinstance(
                date_block,
                dict,
            ):
                continue

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
    # TEMPORADA NFL
    # ========================================================

    @staticmethod
    def _nfl_season_for_date(
        date_iso: str,
    ) -> int:

        try:

            parsed = datetime.strptime(
                date_iso,
                "%Y-%m-%d",
            )

            if parsed.month <= 2:
                return parsed.year - 1

            return parsed.year

        except ValueError:

            now = datetime.now(
                timezone.utc
            )

            if now.month <= 2:
                return now.year - 1

            return now.year

    # ========================================================
    # DETECTAR BLOQUEO DE PLAN/TEMPORADA
    # ========================================================

    @staticmethod
    def _is_plan_or_season_error(
        exc: Exception,
    ) -> bool:

        text = str(
            exc
        ).lower()

        return any(
            marker in text
            for marker in (
                "free plans",
                "do not have access to this season",
                "plan",
                "season",
            )
        )

    # ========================================================
    # PARTIDOS PARA RESOLVER RESULTADOS
    #
    # MLB USA MLB STATS API PRIMERO PARA OBTENER
    # LINESCORE COMPLETO Y RESOLVER F5.
    #
    # ESTO NO CAMBIA LA FUENTE NORMAL DE PREDICCIONES.
    # ========================================================

    def result_games_for_date(
        self,
        sport: str,
        date_iso: str,
    ) -> ApiResult:

        if sport == "MLB":

            try:

                result = self._mlb_schedule(
                    date_iso=date_iso,
                )

                if result.response:

                    print(
                        "MLB RESULTADOS: "
                        "usando MLB Stats API "
                        "con linescore."
                    )

                    return result

            except ApiSportsError as exc:

                print(
                    "MLB RESULTADOS: "
                    "MLB Stats API falló. "
                    "Usando respaldo normal."
                )

                print(
                    f"Motivo: {exc}"
                )

        return self.games_for_date(
            sport,
            date_iso,
        )

    # ========================================================
    # TODOS LOS PARTIDOS DEL DÍA
    # ========================================================

    def games_for_date(
        self,
        sport: str,
        date_iso: str,
    ) -> ApiResult:

        # ====================================================
        # NFL
        # ====================================================

        if sport == "NFL":

            nfl_season = (
                self._nfl_season_for_date(
                    date_iso
                )
            )

            if self._nfl_api_sports_available:

                try:

                    print(
                        "NFL: buscando en API-Sports "
                        f"fecha={date_iso}, "
                        "league=1, "
                        f"season={nfl_season}"
                    )

                    result = self._get(
                        "NFL",
                        "games",
                        {
                            "league": 1,
                            "season": nfl_season,
                            "date": date_iso,
                        },
                    )

                    if result.response:

                        self._nfl_using_espn = False

                        print(
                            "NFL API-Sports: "
                            f"{len(result.response)} "
                            "partidos encontrados."
                        )

                        return result

                except ApiSportsError as exc:

                    if (
                        self._is_plan_or_season_error(
                            exc
                        )
                    ):

                        self._nfl_api_sports_available = False

                        print(
                            "NFL: API-Sports no permite "
                            "esta temporada con el plan actual."
                        )

                    else:

                        print(
                            "NFL: API-Sports falló. "
                            f"Motivo: {exc}"
                        )

            self._nfl_using_espn = True

            print(
                "NFL: activando fallback ESPN."
            )

            return (
                self._espn_nfl_games_for_date(
                    date_iso
                )
            )

        # ====================================================
        # NBA
        # ====================================================

        if sport == "NBA":

            return self._get(
                "NBA",
                "games",
                {
                    "date": date_iso,
                },
            )

        # ====================================================
        # MLB
        # ====================================================

        if sport != "MLB":

            raise ValueError(
                f"Deporte desconocido: {sport}"
            )

        if self._mlb_games_api_sports_available:

            try:

                result = self._get(
                    "MLB",
                    "games",
                    {
                        "date": date_iso,
                    },
                )

                if result.response:

                    self._mlb_using_stats_api = False

                    return result

            except ApiSportsError as exc:

                self._mlb_games_api_sports_available = False

                print(
                    "MLB: API-Sports no disponible. "
                    "Activando MLB Stats API."
                )

                print(
                    f"Motivo: {exc}"
                )

        self._mlb_using_stats_api = True

        return self._mlb_schedule(
            date_iso=date_iso,
        )

    # ========================================================
    # HISTORIAL DE EQUIPO
    # ========================================================

    def team_history(
        self,
        sport: str,
        team_id: int | str,
        season: int | str,
    ) -> ApiResult:

        if sport == "NFL":

            if self._nfl_using_espn:

                return (
                    self._espn_nfl_team_history(
                        team_id=team_id,
                        season=season,
                    )
                )

            try:

                return self._get(
                    "NFL",
                    "games",
                    {
                        "team": team_id,
                        "league": 1,
                        "season": season,
                    },
                )

            except ApiSportsError as exc:

                if (
                    self._is_plan_or_season_error(
                        exc
                    )
                ):

                    self._nfl_api_sports_available = False

                return ApiResult(
                    response=[],
                    remaining_requests=None,
                )

        if sport == "NBA":

            return self._get(
                "NBA",
                "games",
                {
                    "team": team_id,
                    "season": season,
                },
            )

        if sport != "MLB":

            raise ValueError(
                f"Deporte desconocido: {sport}"
            )

        if self._mlb_using_stats_api:

            return self._mlb_schedule(
                team_id=team_id,
                season=season,
            )

        if self._mlb_games_api_sports_available:

            try:

                return self._get(
                    "MLB",
                    "games",
                    {
                        "team": team_id,
                        "season": season,
                    },
                )

            except ApiSportsError:

                self._mlb_games_api_sports_available = False

                return ApiResult(
                    response=[],
                    remaining_requests=None,
                )

        return ApiResult(
            response=[],
            remaining_requests=None,
        )

    # ========================================================
    # CUOTAS
    # ========================================================

    def odds_for_date(
        self,
        sport: str,
        date_iso: str,
        game_ids: list[int | str],
    ) -> ApiResult:

        if (
            sport == "NFL"
            and self._nfl_using_espn
        ):

            print(
                "NFL: juegos obtenidos desde ESPN. "
                "No se consultarán cuotas API-Sports "
                "con IDs de ESPN."
            )

            return ApiResult(
                response=[],
                remaining_requests=None,
            )

        if (
            sport == "NFL"
            and not self._nfl_odds_api_sports_available
        ):

            return ApiResult(
                response=[],
                remaining_requests=None,
            )

        if (
            sport == "MLB"
            and self._mlb_using_stats_api
        ):

            print(
                "MLB: juegos obtenidos desde "
                "MLB Stats API. "
                "No se consultarán cuotas API-Sports "
                "con IDs de MLB Stats."
            )

            return ApiResult(
                response=[],
                remaining_requests=None,
            )

        if (
            sport == "MLB"
            and not self._mlb_odds_api_sports_available
        ):

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

                    self._mlb_odds_api_sports_available = False

                    print(
                        "MLB: cuotas API-Sports "
                        "no disponibles."
                    )

                    print(
                        f"Motivo: {exc}"
                    )

                    return ApiResult(
                        response=[],
                        remaining_requests=None,
                    )

                if sport == "NFL":

                    self._nfl_odds_api_sports_available = False

                    print(
                        "NFL: cuotas API-Sports "
                        "no disponibles."
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

                        self._mlb_odds_api_sports_available = False

                        print(
                            "MLB: límite/error de cuotas."
                        )

                        print(
                            f"Motivo: {exc}"
                        )

                        break

                    if sport == "NFL":

                        self._nfl_odds_api_sports_available = False

                        print(
                            "NFL: límite/error de cuotas."
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
