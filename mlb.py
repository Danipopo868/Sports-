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
    return "".join(
        character.lower()
        for character in value
        if character.isalnum()
    )


class MlbStatsClient:
    """
    Enriquecimiento MLB:
    - abridores probables
    - ERA / WHIP / K9 / BB9 / HR9
    - ofensiva de equipo
    - pitching de equipo como proxy de bullpen
    - bateadores activos vs abridor rival (BvP)
    """

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self._probable_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._pitcher_cache: dict[tuple[int, int], dict[str, Any]] = {}
        self._offense_cache: dict[tuple[int, int], dict[str, float]] = {}
        self._team_pitching_cache: dict[tuple[int, int], dict[str, float]] = {}
        self._roster_cache: dict[tuple[int, int], list[dict[str, Any]]] = {}
        self._bvp_cache: dict[tuple[int, int, int], dict[str, Any]] = {}

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query = urllib.parse.urlencode(params or {})
        url = f"{MLB_STATS_BASE}/{path.lstrip('/')}"

        if query:
            url = f"{url}?{query}"

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
                    request,
                    timeout=self.timeout_seconds,
                ) as response:
                    payload = json.loads(
                        response.read().decode("utf-8")
                    )
                    return payload if isinstance(payload, dict) else {}

            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ):
                if attempt == 2:
                    return {}
                time.sleep(2**attempt)

        return {}

    def probable_pitchers(
        self,
        date_iso: str,
    ) -> dict[str, dict[str, Any]]:
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
                    team_block = (
                        game.get("teams", {})
                        .get(side, {})
                    )

                    team = team_block.get("team", {})
                    pitcher = (
                        team_block.get("probablePitcher")
                        or {}
                    )

                    team_name = str(
                        team.get("name", "")
                    )

                    if team_name:
                        result[
                            normalize_name(team_name)
                        ] = {
                            "team_id": team.get("id"),
                            "pitcher_id": pitcher.get("id"),
                            "pitcher_name": (
                                pitcher.get("fullName")
                                or "No confirmado"
                            ),
                        }

        self._probable_cache[date_iso] = result
        return result

    def pitcher_stats(
        self,
        pitcher_id: int | None,
        season: int,
    ) -> dict[str, Any]:
        if not pitcher_id:
            return {}

        key = (int(pitcher_id), season)

        if key in self._pitcher_cache:
            return self._pitcher_cache[key]

        payload = self._get(
            f"people/{pitcher_id}/stats",
            {
                "stats": "season",
                "group": "pitching",
                "season": season,
            },
        )

        splits = (
            (payload.get("stats") or [{}])[0]
            .get("splits", [])
        )

        stat = (
            splits[0].get("stat", {})
            if splits
            else {}
        )

        games_pitched = _float(
            stat.get("gamesPitched")
            or stat.get("gamesPlayed")
        )

        games_started = _float(
            stat.get("gamesStarted")
        )

        parsed = {
            "era": _float(stat.get("era")),
            "whip": _float(stat.get("whip")),
            "k9": _float(stat.get("strikeoutsPer9Inn")),
            "bb9": _float(stat.get("walksPer9Inn")),
            "hr9": _float(stat.get("homeRunsPer9")),
            "innings": _float(stat.get("inningsPitched")),
            "games_pitched": games_pitched,
            "games_started": games_started,
            "wins": _float(stat.get("wins")),
            "losses": _float(stat.get("losses")),
        }

        self._pitcher_cache[key] = parsed
        return parsed

    def team_offense(
        self,
        team_id: int | None,
        season: int,
    ) -> dict[str, float]:
        if not team_id:
            return {}

        key = (int(team_id), season)

        if key in self._offense_cache:
            return self._offense_cache[key]

        payload = self._get(
            f"teams/{team_id}/stats",
            {
                "stats": "season",
                "group": "hitting",
                "season": season,
            },
        )

        splits = (
            (payload.get("stats") or [{}])[0]
            .get("splits", [])
        )

        stat = (
            splits[0].get("stat", {})
            if splits
            else {}
        )

        games = max(
            1.0,
            _float(stat.get("gamesPlayed")),
        )

        parsed = {
            "avg": _float(stat.get("avg")),
            "obp": _float(stat.get("obp")),
            "slg": _float(stat.get("slg")),
            "ops": _float(stat.get("ops")),
            "runs_per_game": (
                _float(stat.get("runs")) / games
            ),
            "home_runs": _float(
                stat.get("homeRuns")
            ),
        }

        self._offense_cache[key] = parsed
        return parsed

    def team_pitching(
        self,
        team_id: int | None,
        season: int,
    ) -> dict[str, float]:
        """
        Es pitching total de equipo, usado como proxy de bullpen.
        No se presenta como bullpen exacto.
        """
        if not team_id:
            return {}

        key = (int(team_id), season)

        if key in self._team_pitching_cache:
            return self._team_pitching_cache[key]

        payload = self._get(
            f"teams/{team_id}/stats",
            {
                "stats": "season",
                "group": "pitching",
                "season": season,
            },
        )

        splits = (
            (payload.get("stats") or [{}])[0]
            .get("splits", [])
        )

        stat = (
            splits[0].get("stat", {})
            if splits
            else {}
        )

        parsed = {
            "era": _float(stat.get("era")),
            "whip": _float(stat.get("whip")),
            "k9": _float(stat.get("strikeoutsPer9Inn")),
            "bb9": _float(stat.get("walksPer9Inn")),
            "hr9": _float(stat.get("homeRunsPer9")),
        }

        self._team_pitching_cache[key] = parsed
        return parsed

    def active_hitters(
        self,
        team_id: int | None,
        season: int,
    ) -> list[dict[str, Any]]:
        if not team_id:
            return []

        key = (int(team_id), season)

        if key in self._roster_cache:
            return self._roster_cache[key]

        payload = self._get(
            f"teams/{team_id}/roster",
            {
                "rosterType": "active",
                "season": season,
            },
        )

        hitters: list[dict[str, Any]] = []

        for row in payload.get("roster", []):
            person = row.get("person", {})
            position = row.get("position", {})

            position_type = str(
                position.get("type", "")
            ).lower()

            if "pitcher" in position_type:
                continue

            person_id = person.get("id")

            if not person_id:
                continue

            hitters.append(
                {
                    "id": int(person_id),
                    "name": (
                        person.get("fullName")
                        or "Desconocido"
                    ),
                }
            )

        self._roster_cache[key] = hitters
        return hitters

    def batter_vs_pitcher(
        self,
        batter_id: int,
        pitcher_id: int,
        season: int,
    ) -> dict[str, float]:
        key = (
            int(batter_id),
            int(pitcher_id),
            season,
        )

        if key in self._bvp_cache:
            return self._bvp_cache[key]

        payload = self._get(
            f"people/{batter_id}/stats",
            {
                "stats": "vsPlayer",
                "group": "hitting",
                "opposingPlayerId": pitcher_id,
                "season": season,
            },
        )

        splits: list[dict[str, Any]] = []

        for block in payload.get("stats", []):
            splits.extend(
                block.get("splits", [])
            )

        if not splits:
            self._bvp_cache[key] = {}
            return {}

        stat = splits[0].get("stat", {})

        result = {
            "plate_appearances": _float(
                stat.get("plateAppearances")
            ),
            "at_bats": _float(
                stat.get("atBats")
            ),
            "hits": _float(
                stat.get("hits")
            ),
            "avg": _float(
                stat.get("avg")
            ),
            "obp": _float(
                stat.get("obp")
            ),
            "slg": _float(
                stat.get("slg")
            ),
            "ops": _float(
                stat.get("ops")
            ),
            "home_runs": _float(
                stat.get("homeRuns")
            ),
            "strike_outs": _float(
                stat.get("strikeOuts")
            ),
        }

        self._bvp_cache[key] = result
        return result

    def team_vs_pitcher(
        self,
        team_id: int | None,
        pitcher_id: int | None,
        season: int,
    ) -> dict[str, float]:
        if not team_id or not pitcher_id:
            return {}

        hitters = self.active_hitters(
            team_id,
            season,
        )

        total_pa = 0.0
        weighted_avg = 0.0
        weighted_obp = 0.0
        weighted_slg = 0.0
        weighted_ops = 0.0
        home_runs = 0.0
        batters_with_data = 0

        for hitter in hitters:
            stats = self.batter_vs_pitcher(
                hitter["id"],
                int(pitcher_id),
                season,
            )

            pa = stats.get(
                "plate_appearances",
                0.0,
            )

            if pa <= 0:
                continue

            batters_with_data += 1
            total_pa += pa

            weighted_avg += (
                stats.get("avg", 0.0) * pa
            )
            weighted_obp += (
                stats.get("obp", 0.0) * pa
            )
            weighted_slg += (
                stats.get("slg", 0.0) * pa
            )
            weighted_ops += (
                stats.get("ops", 0.0) * pa
            )

            home_runs += stats.get(
                "home_runs",
                0.0,
            )

        if total_pa <= 0:
            return {}

        return {
            "plate_appearances": total_pa,
            "batters_with_data": float(
                batters_with_data
            ),
            "avg": weighted_avg / total_pa,
            "obp": weighted_obp / total_pa,
            "slg": weighted_slg / total_pa,
            "ops": weighted_ops / total_pa,
            "home_runs": home_runs,
        }

    def matchup(
        self,
        home_name: str,
        away_name: str,
        season: int,
        date_iso: str,
    ) -> dict[str, Any]:
        probable = self.probable_pitchers(
            date_iso
        )

        home = probable.get(
            normalize_name(home_name),
            {},
        )

        away = probable.get(
            normalize_name(away_name),
            {},
        )

        home_pitcher = self.pitcher_stats(
            home.get("pitcher_id"),
            season,
        )

        away_pitcher = self.pitcher_stats(
            away.get("pitcher_id"),
            season,
        )

        home_offense = self.team_offense(
            home.get("team_id"),
            season,
        )

        away_offense = self.team_offense(
            away.get("team_id"),
            season,
        )

        home_team_pitching = self.team_pitching(
            home.get("team_id"),
            season,
        )

        away_team_pitching = self.team_pitching(
            away.get("team_id"),
            season,
        )

        home_vs_away_pitcher = self.team_vs_pitcher(
            home.get("team_id"),
            away.get("pitcher_id"),
            season,
        )

        away_vs_home_pitcher = self.team_vs_pitcher(
            away.get("team_id"),
            home.get("pitcher_id"),
            season,
        )

        return {
            "home": {
                **home,
                "pitching": home_pitcher,
                "offense": home_offense,
                "team_pitching": home_team_pitching,
                "vs_opposing_pitcher": (
                    home_vs_away_pitcher
                ),
            },
            "away": {
                **away,
                "pitching": away_pitcher,
                "offense": away_offense,
                "team_pitching": away_team_pitching,
                "vs_opposing_pitcher": (
                    away_vs_home_pitcher
                ),
            },
        }


def first_five_home_probability(
    matchup: dict[str, Any],
) -> float | None:
    home = matchup.get("home", {})
    away = matchup.get("away", {})

    home_pitching = home.get(
        "pitching",
        {},
    )

    away_pitching = away.get(
        "pitching",
        {},
    )

    home_offense = home.get(
        "offense",
        {},
    )

    away_offense = away.get(
        "offense",
        {},
    )

    required = [
        home_pitching.get("era"),
        home_pitching.get("whip"),
        away_pitching.get("era"),
        away_pitching.get("whip"),
        home_offense.get("ops"),
        away_offense.get("ops"),
    ]

    if any(
        value in (None, 0, 0.0, "")
        for value in required
    ):
        return None

    pitcher_edge = (
        (
            float(away_pitching["era"])
            - float(home_pitching["era"])
        )
        / 1.4
        +
        (
            float(away_pitching["whip"])
            - float(home_pitching["whip"])
        )
        / 0.30
    ) / 2.0

    offense_edge = (
        float(home_offense["ops"])
        - float(away_offense["ops"])
    ) / 0.11

    home_bvp = home.get(
        "vs_opposing_pitcher",
        {},
    )

    away_bvp = away.get(
        "vs_opposing_pitcher",
        {},
    )

    bvp_edge = 0.0

    home_pa = home_bvp.get(
        "plate_appearances",
        0.0,
    )

    away_pa = away_bvp.get(
        "plate_appearances",
        0.0,
    )

    if home_pa >= 20 and away_pa >= 20:
        bvp_edge = (
            home_bvp.get("ops", 0.0)
            - away_bvp.get("ops", 0.0)
        ) / 0.20

    logit_value = (
        0.10
        + 0.46 * pitcher_edge
        + 0.28 * offense_edge
        + 0.12 * bvp_edge
    )

    return min(
        0.82,
        max(
            0.18,
            1.0
            / (
                1.0
                + math.exp(-logit_value)
            ),
        ),
    )


def full_game_home_probability(
    matchup: dict[str, Any],
) -> float | None:
    home = matchup.get("home", {})
    away = matchup.get("away", {})

    home_pitching = home.get(
        "pitching",
        {},
    )

    away_pitching = away.get(
        "pitching",
        {},
    )

    home_offense = home.get(
        "offense",
        {},
    )

    away_offense = away.get(
        "offense",
        {},
    )

    home_team_pitching = home.get(
        "team_pitching",
        {},
    )

    away_team_pitching = away.get(
        "team_pitching",
        {},
    )

    required = [
        home_pitching.get("era"),
        home_pitching.get("whip"),
        away_pitching.get("era"),
        away_pitching.get("whip"),
        home_offense.get("ops"),
        away_offense.get("ops"),
    ]

    if any(
        value in (None, 0, 0.0, "")
        for value in required
    ):
        return None

    starter_edge = (
        (
            float(away_pitching["era"])
            - float(home_pitching["era"])
        )
        / 1.4
        +
        (
            float(away_pitching["whip"])
            - float(home_pitching["whip"])
        )
        / 0.30
        +
        (
            float(home_pitching.get("k9", 0.0))
            - float(away_pitching.get("k9", 0.0))
        )
        / 3.0
        +
        (
            float(away_pitching.get("bb9", 0.0))
            - float(home_pitching.get("bb9", 0.0))
        )
        / 2.0
    ) / 4.0

    offense_edge = (
        float(home_offense["ops"])
        - float(away_offense["ops"])
    ) / 0.11

    runs_edge = (
        float(
            home_offense.get(
                "runs_per_game",
                0.0,
            )
        )
        -
        float(
            away_offense.get(
                "runs_per_game",
                0.0,
            )
        )
    ) / 1.2

    team_pitching_edge = 0.0

    if (
        home_team_pitching.get("era")
        and away_team_pitching.get("era")
    ):
        team_pitching_edge = (
            float(
                away_team_pitching["era"]
            )
            -
            float(
                home_team_pitching["era"]
            )
        ) / 1.3

    home_bvp = home.get(
        "vs_opposing_pitcher",
        {},
    )

    away_bvp = away.get(
        "vs_opposing_pitcher",
        {},
    )

    bvp_edge = 0.0

    home_pa = home_bvp.get(
        "plate_appearances",
        0.0,
    )

    away_pa = away_bvp.get(
        "plate_appearances",
        0.0,
    )

    if home_pa >= 20 and away_pa >= 20:
        bvp_edge = (
            home_bvp.get("ops", 0.0)
            - away_bvp.get("ops", 0.0)
        ) / 0.20

    logit_value = (
        0.12
        + 0.34 * starter_edge
        + 0.26 * offense_edge
        + 0.12 * runs_edge
        + 0.10 * team_pitching_edge
        + 0.10 * bvp_edge
    )

    probability = (
        1.0
        / (
            1.0
            + math.exp(-logit_value)
        )
    )

    return min(
        0.80,
        max(
            0.20,
            probability,
        ),
    )


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
