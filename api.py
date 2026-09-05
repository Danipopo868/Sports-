from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


SPORT_ENDPOINTS = {
    "MLB": "https://v1.baseball.api-sports.io",
    "NFL": "https://v1.american-football.api-sports.io",
    # API-BASKETBALL incluye NBA y, a diferencia del producto API-NBA,
    # publica en la misma cobertura partidos, estadísticas y cuotas.
    "NBA": "https://v1.basketball.api-sports.io",
}


class ApiSportsError(RuntimeError):
    """Error explícito del proveedor; nunca se sustituye con datos inventados."""


@dataclass(frozen=True)
class ApiResult:
    response: list[dict[str, Any]]
    remaining_requests: int | None = None


class ApiSportsClient:
    def __init__(self, api_key: str, timeout_seconds: int = 25) -> None:
        if not api_key.strip():
            raise ValueError("API_SPORTS_KEY está vacía")
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self._fallback_odds_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._batch_odds_supported: dict[str, bool] = {}

    def _get(
        self,
        sport: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> ApiResult:
        if sport not in SPORT_ENDPOINTS:
            raise ValueError(f"Deporte desconocido: {sport}")

        clean_params = {
            key: value
            for key, value in (params or {}).items()
            if value is not None and value != ""
        }
        query = urllib.parse.urlencode(clean_params)
        url = f"{SPORT_ENDPOINTS[sport]}/{endpoint.lstrip('/')}"
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
                    request, timeout=self.timeout_seconds
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    remaining_raw = response.headers.get("x-ratelimit-requests-remaining")
                    remaining = int(remaining_raw) if remaining_raw else None
                    break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:500]
                last_error = ApiSportsError(
                    f"{sport} {endpoint}: HTTP {exc.code}. {body}"
                )
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise last_error from exc
                time.sleep(2**attempt)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 2:
                    raise ApiSportsError(
                        f"{sport} {endpoint}: no se pudo leer la respuesta ({exc})"
                    ) from exc
                time.sleep(2**attempt)
        else:
            raise ApiSportsError(str(last_error))

        provider_errors = payload.get("errors") if isinstance(payload, dict) else None
        if provider_errors:
            raise ApiSportsError(f"{sport} {endpoint}: {provider_errors}")

        raw_response = payload.get("response", []) if isinstance(payload, dict) else []
        if not isinstance(raw_response, list):
            raise ApiSportsError(f"{sport} {endpoint}: formato inesperado")
        return ApiResult(response=raw_response, remaining_requests=remaining)

    def games_for_date(self, sport: str, date_iso: str) -> ApiResult:
        return self._get(sport, "games", {"date": date_iso})

    def team_history(self, sport: str, team_id: int | str, season: int | str) -> ApiResult:
        return self._get(
            sport,
            "games",
            {"team": team_id, "season": season},
        )

    def odds_for_date(
        self,
        sport: str,
        date_iso: str,
        game_ids: list[int | str],
    ) -> ApiResult:
        """Intenta una consulta por fecha; usa por-partido solo una vez si hace falta.

        El caché evita agotar el plan gratuito durante el ciclo de tres horas.
        """
        batch = ApiResult([])
        if self._batch_odds_supported.get(sport, True):
            try:
                batch = self._get(sport, "odds", {"date": date_iso})
                if batch.response:
                    self._batch_odds_supported[sport] = True
                    return batch
                self._batch_odds_supported[sport] = False
            except ApiSportsError:
                self._batch_odds_supported[sport] = False

        combined: list[dict[str, Any]] = []
        remaining: int | None = batch.remaining_requests
        for game_id in game_ids:
            cache_key = (sport, str(game_id))
            if cache_key not in self._fallback_odds_cache:
                try:
                    result = self._get(sport, "odds", {"game": game_id})
                    self._fallback_odds_cache[cache_key] = result.response
                    remaining = result.remaining_requests
                except ApiSportsError:
                    self._fallback_odds_cache[cache_key] = []
            combined.extend(self._fallback_odds_cache[cache_key])
        return ApiResult(combined, remaining)
