from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"


def normalize_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


class MlbStatsClient:
    """Enriquecimiento gratuito: abridores y estadísticas oficiales de MLB."""

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self._probable_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._pitcher_cache: dict[tuple[int, int], dict[str, float | str]] = {}
        self._offense_cache: dict[tuple[int, int], dict[str, float]] = {}

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        url = f"{MLB_STATS_BASE}/{path.lstrip('/')}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "sports-predictor-github/1.0",
            },
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    return payload if isinstance(payload, dict) else {}
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                if attempt == 2:
                    return {}
                time.sleep(2**attempt)
        return {}

    def probable_pitchers(self, date_iso: str) -> dict[str, dict[str, Any]]:
        if date_iso in self._probable_cache:
            return self._probable_cache[date_iso]
        payload = self._get(
            "schedule",
            {
                "sportId": 1,
                "date": date_iso,
                "hydrate": "probablePitcher,team",
            },
        )
        result: dict[str, dict[str, Any]] = {}
        for date_block in payload.get("dates", []):
            for game in date_block.get("games", []):
                for side in ("home", "away"):
                    team_block = game.get("teams", {}).get(side, {})
                    team = team_block.get("team", {})
                    pitcher = team_block.get("probablePitcher") or {}
                    team_name = str(team.get("name", ""))
                    if team_name:
                        result[normalize_name(team_name)] = {
                            "team_id": team.get("id"),
                            "pitcher_id": pitcher.get("id"),
                            "pitcher_name": pitcher.get("fullName") or "No confirmado",
                        }
        self._probable_cache[date_iso] = result
        return result

    def pitcher_stats(self, pitcher_id: int | None, season: int) -> dict[str, float | str]:
        if not pitcher_id:
            return {}
        key = (int(pitcher_id), season)
        if key in self._pitcher_cache:
            return self._pitcher_cache[key]
        payload = self._get(
            f"people/{pitcher_id}/stats",
            {"stats": "season", "group": "pitching", "season": season},
        )
        splits = (payload.get("stats") or [{}])[0].get("splits", [])
        stat = splits[0].get("stat", {}) if splits else {}
        parsed: dict[str, float | str] = {
            "era": _float(stat.get("era")),
            "whip": _float(stat.get("whip")),
            "k9": _float(stat.get("strikeoutsPer9Inn")),
            "bb9": _float(stat.get("walksPer9Inn")),
            "innings": _float(stat.get("inningsPitched")),
        }
        self._pitcher_cache[key] = parsed
        return parsed

    def team_offense(self, team_id: int | None, season: int) -> dict[str, float]:
        if not team_id:
            return {}
        key = (int(team_id), season)
        if key in self._offense_cache:
            return self._offense_cache[key]
        payload = self._get(
            f"teams/{team_id}/stats",
            {"stats": "season", "group": "hitting", "season": season},
        )
        splits = (payload.get("stats") or [{}])[0].get("splits", [])
        stat = splits[0].get("stat", {}) if splits else {}
        games = max(1.0, _float(stat.get("gamesPlayed")))
        parsed = {
            "avg": _float(stat.get("avg")),
            "obp": _float(stat.get("obp")),
            "slg": _float(stat.get("slg")),
            "ops": _float(stat.get("ops")),
            "runs_per_game": _float(stat.get("runs")) / games,
        }
        self._offense_cache[key] = parsed
        return parsed

    def matchup(self, home_name: str, away_name: str, season: int, date_iso: str) -> dict[str, Any]:
        probable = self.probable_pitchers(date_iso)
        home = probable.get(normalize_name(home_name), {})
        away = probable.get(normalize_name(away_name), {})
        home_pitcher = self.pitcher_stats(home.get("pitcher_id"), season)
        away_pitcher = self.pitcher_stats(away.get("pitcher_id"), season)
        home_offense = self.team_offense(home.get("team_id"), season)
        away_offense = self.team_offense(away.get("team_id"), season)
        return {
            "home": {**home, "pitching": home_pitcher, "offense": home_offense},
            "away": {**away, "pitching": away_pitcher, "offense": away_offense},
        }


def first_five_home_probability(matchup: dict[str, Any]) -> float | None:
    home = matchup.get("home", {})
    away = matchup.get("away", {})
    home_pitching = home.get("pitching", {})
    away_pitching = away.get("pitching", {})
    home_offense = home.get("offense", {})
    away_offense = away.get("offense", {})
    required = [
        home_pitching.get("era"),
        home_pitching.get("whip"),
        away_pitching.get("era"),
        away_pitching.get("whip"),
        home_offense.get("ops"),
        away_offense.get("ops"),
    ]
    if any(value in (None, 0, 0.0, "") for value in required):
        return None

    # Un valor positivo favorece al equipo local. Se usan escalas de liga,
    # evitando convertir pequeñas diferencias en certezas artificiales.
    pitcher_edge = (
        (float(away_pitching["era"]) - float(home_pitching["era"])) / 1.4
        + (float(away_pitching["whip"]) - float(home_pitching["whip"])) / 0.30
    ) / 2.0
    offense_edge = (float(home_offense["ops"]) - float(away_offense["ops"])) / 0.11
    logit_value = 0.10 + 0.48 * pitcher_edge + 0.30 * offense_edge
    return min(0.82, max(0.18, 1.0 / (1.0 + math.exp(-logit_value))))


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
