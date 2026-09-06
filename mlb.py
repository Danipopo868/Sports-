from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any

MLB_STATS_BASE = "https://statsapi.mlb.com/api/v1"
MLB_LIVE_BASE = "https://statsapi.mlb.com/api/v1.1"


def normalize_name(value: str) -> str:
    return "".join(c.lower() for c in value if c.isalnum())


def _float(value: Any) -> float:
    try:
        if value in (None, "", "-.--"):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-8.0, min(8.0, x))))


def _clamp(p: float, lo: float = 0.16, hi: float = 0.84) -> float:
    return min(hi, max(lo, p))


class MlbStatsClient:
    """
    Enriquecimiento MLB usando StatsAPI oficial.

    Reúne:
    - abridores
    - ofensiva
    - splits vs L/R
    - bullpen
    - forma reciente
    - descanso
    - uso reciente bullpen
    - alineaciones
    - BvP
    - estadio
    - clima

    Si falta información no inventa datos.
    """

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, dict[str, Any]] = {}

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        live: bool = False,
    ) -> dict[str, Any]:

        base = MLB_LIVE_BASE if live else MLB_STATS_BASE

        query = urllib.parse.urlencode(
            {
                k: v
                for k, v in (params or {}).items()
                if v not in (None, "")
            }
        )

        url = (
            f"{base}/{path.lstrip('/')}"
            + (f"?{query}" if query else "")
        )

        if url in self._cache:
            return self._cache[url]

        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "sports-predictor-github/2.0",
            },
        )

        for attempt in range(3):

            try:

                with urllib.request.urlopen(
                    req,
                    timeout=self.timeout_seconds,
                ) as r:

                    obj = json.loads(
                        r.read().decode("utf-8")
                    )

                    out = (
                        obj
                        if isinstance(obj, dict)
                        else {}
                    )

                    self._cache[url] = out

                    return out

            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                json.JSONDecodeError,
            ):

                if attempt == 2:
                    self._cache[url] = {}
                    return {}

                time.sleep(2 ** attempt)

        return {}

    def schedule(
        self,
        date_iso: str,
    ) -> list[dict[str, Any]]:

        payload = self._get(
            "schedule",
            {
                "sportId": 1,
                "date": date_iso,
                "hydrate": "probablePitcher,team,venue",
            },
        )

        return [
            g
            for d in payload.get("dates", [])
            for g in d.get("games", [])
        ]

    def _find_game(
        self,
        home_name: str,
        away_name: str,
        date_iso: str,
    ) -> dict[str, Any]:

        hn = normalize_name(home_name)
        an = normalize_name(away_name)

        for game in self.schedule(date_iso):

            home = normalize_name(
                str(
                    game
                    .get("teams", {})
                    .get("home", {})
                    .get("team", {})
                    .get("name", "")
                )
            )

            away = normalize_name(
                str(
                    game
                    .get("teams", {})
                    .get("away", {})
                    .get("team", {})
                    .get("name", "")
                )
            )

            if home == hn and away == an:
                return game

        return {}

    def pitcher_stats(
        self,
        pitcher_id: int | None,
        season: int,
    ) -> dict[str, Any]:

        if not pitcher_id:
            return {}

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

        return {
            "era": _float(stat.get("era")),
            "whip": _float(stat.get("whip")),
            "k9": _float(
                stat.get("strikeoutsPer9Inn")
            ),
            "bb9": _float(
                stat.get("walksPer9Inn")
            ),
            "hr9": _float(
                stat.get("homeRunsPer9")
            ),
            "innings": _float(
                stat.get("inningsPitched")
            ),
            "hand": "",
        }

    def person_hand(
        self,
        person_id: int | None,
    ) -> str:

        if not person_id:
            return ""

        p = self._get(
            f"people/{person_id}"
        )

        people = p.get("people") or []

        if not people:
            return ""

        return str(
            (
                people[0]
                .get("pitchHand")
                or {}
            ).get("code")
            or ""
        )

    def team_offense(
        self,
        team_id: int | None,
        season: int,
        sit_code: str | None = None,
    ) -> dict[str, float]:

        if not team_id:
            return {}

        params: dict[str, Any] = {
            "stats": "season",
            "group": "hitting",
            "season": season,
        }

        if sit_code:
            params["sitCodes"] = sit_code

        payload = self._get(
            f"teams/{team_id}/stats",
            params,
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
            _float(
                stat.get("gamesPlayed")
            ),
        )

        return {
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
            "runs_per_game":
                _float(stat.get("runs"))
                / games,
            "pa": _float(
                stat.get("plateAppearances")
            ),
        }

    def team_pitching(
        self,
        team_id: int | None,
        season: int,
    ) -> dict[str, float]:

        if not team_id:
            return {}

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

        return {
            "era": _float(
                stat.get("era")
            ),
            "whip": _float(
                stat.get("whip")
            ),
            "innings": _float(
                stat.get("inningsPitched")
            ),
        }

    def recent_form(
        self,
        team_id: int | None,
        season: int,
        end_date: str,
        games_limit: int = 10,
    ) -> dict[str, float]:

        if not team_id:
            return {}

        start = (
            date.fromisoformat(end_date)
            - timedelta(days=24)
        ).isoformat()

        payload = self._get(
            "schedule",
            {
                "sportId": 1,
                "teamId": team_id,
                "startDate": start,
                "endDate": end_date,
            },
        )

        rows = [
            g
            for d in payload.get("dates", [])
            for g in d.get("games", [])
        ]

        finals = [
            g
            for g in rows
            if str(
                g.get("status", {})
                .get(
                    "abstractGameState",
                    "",
                )
            ).lower()
            == "final"
        ][-games_limit:]

        if not finals:
            return {}

        wins = 0.0
        runs_for = 0.0
        runs_against = 0.0

        for g in finals:

            h = (
                g.get("teams", {})
                .get("home", {})
            )

            a = (
                g.get("teams", {})
                .get("away", {})
            )

            home_id = (
                h.get("team", {})
                .get("id")
            )

            if str(home_id) == str(team_id):

                rf = _float(
                    h.get("score")
                )

                ra = _float(
                    a.get("score")
                )

            else:

                rf = _float(
                    a.get("score")
                )

                ra = _float(
                    h.get("score")
                )

            runs_for += rf
            runs_against += ra

            if rf > ra:
                wins += 1.0

        n = len(finals)

        return {
            "games": n,
            "win_rate":
                wins / n,
            "runs_for":
                runs_for / n,
            "runs_against":
                runs_against / n,
        }

    def rest_days(
        self,
        team_id: int | None,
        game_date: str,
    ) -> int | None:

        if not team_id:
            return None

        d = date.fromisoformat(
            game_date
        )

        payload = self._get(
            "schedule",
            {
                "sportId": 1,
                "teamId": team_id,
                "startDate":
                    (
                        d
                        - timedelta(days=7)
                    ).isoformat(),
                "endDate":
                    (
                        d
                        - timedelta(days=1)
                    ).isoformat(),
            },
        )

        dates = []

        for block in payload.get(
            "dates",
            [],
        ):

            if any(
                str(
                    g.get("status", {})
                    .get(
                        "abstractGameState",
                        "",
                    )
                ).lower()
                == "final"
                for g in block.get(
                    "games",
                    [],
                )
            ):

                dates.append(
                    date.fromisoformat(
                        block.get("date")
                    )
                )

        if not dates:
            return 5

        return max(
            0,
            (
                d
                - max(dates)
            ).days
            - 1,
        )

    def live_context(
        self,
        game_pk: int | None,
    ) -> dict[str, Any]:

        if not game_pk:
            return {}

        feed = self._get(
            f"game/{game_pk}/feed/live",
            live=True,
        )

        game_data = (
            feed.get("gameData", {})
        )

        live_data = (
            feed.get("liveData", {})
        )

        weather = (
            game_data.get("weather")
            or {}
        )

        venue = (
            game_data.get("venue")
            or {}
        )

        box = (
            live_data.get("boxscore")
            or {}
        )

        teams_box = (
            box.get("teams")
            or {}
        )

        return {

            "weather": {
                "condition":
                    weather.get(
                        "condition"
                    ),
                "temp_f":
                    _float(
                        weather.get(
                            "temp"
                        )
                    ),
                "wind":
                    weather.get(
                        "wind"
                    ),
            },

            "venue": {
                "name":
                    venue.get(
                        "name"
                    ),
                "id":
                    venue.get(
                        "id"
                    ),
            },

            "lineups": {

                side:
                    list(
                        (
                            teams_box
                            .get(side)
                            or {}
                        ).get(
                            "battingOrder"
                        )
                        or []
                    )

                for side in (
                    "home",
                    "away",
                )
            },
        }

    def bullpen_load(
        self,
        team_id: int | None,
        game_date: str,
    ) -> dict[str, float]:

        if not team_id:

            return {
                "availability": False,
                "innings_3d": 0.0,
                "games_3d": 0,
            }

        d = date.fromisoformat(
            game_date
        )

        payload = self._get(
            "schedule",
            {
                "sportId": 1,
                "teamId": team_id,
                "startDate":
                    (
                        d
                        - timedelta(days=3)
                    ).isoformat(),
                "endDate":
                    (
                        d
                        - timedelta(days=1)
                    ).isoformat(),
            },
        )

        game_pks = [

            g.get("gamePk")

            for block
            in payload.get(
                "dates",
                [],
            )

            for g
            in block.get(
                "games",
                [],
            )

            if str(
                g.get(
                    "status",
                    {},
                ).get(
                    "abstractGameState",
                    "",
                )
            ).lower()
            == "final"
        ]

        total = 0.0
        used = 0

        for pk in game_pks[-3:]:

            box = self._get(
                f"game/{pk}/boxscore"
            )

            teams = (
                box.get("teams")
                or {}
            )

            side_obj = None

            for side in (
                "home",
                "away",
            ):

                if str(
                    (
                        teams
                        .get(side, {})
                        .get("team")
                        or {}
                    ).get("id")
                ) == str(team_id):

                    side_obj = (
                        teams.get(
                            side,
                            {},
                        )
                    )

                    break

            if not side_obj:
                continue

            pitchers = (
                side_obj.get(
                    "pitchers"
                )
                or []
            )

            players = (
                side_obj.get(
                    "players"
                )
                or {}
            )

            for pid in pitchers[1:]:

                stat = (
                    (
                        players
                        .get(
                            f"ID{pid}"
                        )
                        or {}
                    )
                    .get("stats")
                    or {}
                ).get(
                    "pitching"
                ) or {}

                total += (
                    _innings_to_float(
                        stat.get(
                            "inningsPitched"
                        )
                    )
                )

            used += 1

        return {
            "availability":
                used > 0,
            "innings_3d":
                round(
                    total,
                    2,
                ),
            "games_3d":
                used,
        }

    def batter_vs_pitcher(
        self,
        batter_ids: list[int],
        pitcher_id: int | None,
        season: int,
        min_pa: int = 10,
    ) -> dict[str, float]:

        if (
            not pitcher_id
            or not batter_ids
        ):
            return {}

        pa = 0.0
        hits = 0.0
        at_bats = 0.0
        walks = 0.0
        total_bases = 0.0

        for batter_id in batter_ids[:9]:

            payload = self._get(
                f"people/{batter_id}/stats",
                {
                    "stats": "vsPlayer",
                    "group": "hitting",
                    "opposingPlayerId":
                        pitcher_id,
                    "season":
                        season,
                },
            )

            splits = (
                (payload.get("stats") or [{}])[0]
                .get("splits", [])
            )

            for split in splits:

                st = (
                    split.get("stat")
                    or {}
                )

                pa += _float(
                    st.get(
                        "plateAppearances"
                    )
                )

                hits += _float(
                    st.get("hits")
                )

                at_bats += _float(
                    st.get("atBats")
                )

                walks += _float(
                    st.get(
                        "baseOnBalls"
                    )
                )

                total_bases += _float(
                    st.get(
                        "totalBases"
                    )
                )

        if pa < min_pa:

            return {
                "pa": pa,
                "sample_ok": False,
            }

        avg = (
            hits / at_bats
            if at_bats
            else 0.0
        )

        obp = (
            (hits + walks) / pa
            if pa
            else 0.0
        )

        slg = (
            total_bases / at_bats
            if at_bats
            else 0.0
        )

        return {
            "pa":
                pa,
            "sample_ok":
                True,
            "avg":
                avg,
            "obp":
                obp,
            "slg":
                slg,
            "ops":
                obp + slg,
        }

    def matchup(
        self,
        home_name: str,
        away_name: str,
        season: int,
        date_iso: str,
    ) -> dict[str, Any]:

        game = self._find_game(
            home_name,
            away_name,
            date_iso,
        )

        teams = (
            game.get("teams")
            or {}
        )

        home_raw = (
            teams.get("home", {})
        )

        away_raw = (
            teams.get("away", {})
        )

        home_team = (
            home_raw.get("team")
            or {}
        )

        away_team = (
            away_raw.get("team")
            or {}
        )

        home_pitcher = (
            home_raw.get(
                "probablePitcher"
            )
            or {}
        )

        away_pitcher = (
            away_raw.get(
                "probablePitcher"
            )
            or {}
        )

        home_pid = (
            home_pitcher.get("id")
        )

        away_pid = (
            away_pitcher.get("id")
        )

        home_tid = (
            home_team.get("id")
        )

        away_tid = (
            away_team.get("id")
        )

        home_hand = self.person_hand(
            home_pid
        )

        away_hand = self.person_hand(
            away_pid
        )

        context = self.live_context(
            game.get("gamePk")
        )

        home_lineup = (
            context
            .get("lineups", {})
            .get("home", [])
        )

        away_lineup = (
            context
            .get("lineups", {})
            .get("away", [])
        )

        def side(
            team_id: int | None,
            pitcher_id: int | None,
            pitcher_name: str,
            pitcher_hand: str,
            opponent_pitcher_hand: str,
            lineup: list[int],
            opponent_pitcher_id: int | None,
        ) -> dict[str, Any]:

            split_code = (
                "vl"
                if opponent_pitcher_hand
                == "L"
                else
                "vr"
                if opponent_pitcher_hand
                == "R"
                else
                None
            )

            return {

                "team_id":
                    team_id,

                "pitcher_id":
                    pitcher_id,

                "pitcher_name":
                    pitcher_name
                    or
                    "No confirmado",

                "pitcher_hand":
                    pitcher_hand,

                "pitching":
                    self.pitcher_stats(
                        pitcher_id,
                        season,
                    ),

                "offense":
                    self.team_offense(
                        team_id,
                        season,
                    ),

                "offense_split":
                    self.team_offense(
                        team_id,
                        season,
                        split_code,
                    )
                    if split_code
                    else {},

                "recent":
                    self.recent_form(
                        team_id,
                        season,
                        date_iso,
                    ),

                "rest_days":
                    self.rest_days(
                        team_id,
                        date_iso,
                    ),

                "bullpen":
                    self.team_pitching(
                        team_id,
                        season,
                    ),

                "bullpen_load":
                    self.bullpen_load(
                        team_id,
                        date_iso,
                    ),

                "lineup":
                    lineup,

                "lineup_confirmed":
                    len(lineup) >= 9,

                "bvp":
                    self.batter_vs_pitcher(
                        lineup,
                        opponent_pitcher_id,
                        season,
                    ),
            }

        result = {

            "game_pk":
                game.get("gamePk"),

            "venue":
                context.get(
                    "venue",
                    {},
                ),

            "weather":
                context.get(
                    "weather",
                    {},
                ),

            "home":
                side(
                    home_tid,
                    home_pid,
                    home_pitcher.get(
                        "fullName",
                        "",
                    ),
                    home_hand,
                    away_hand,
                    home_lineup,
                    away_pid,
                ),

            "away":
                side(
                    away_tid,
                    away_pid,
                    away_pitcher.get(
                        "fullName",
                        "",
                    ),
                    away_hand,
                    home_hand,
                    away_lineup,
                    home_pid,
                ),
        }

        result["completeness"] = (
            matchup_completeness(
                result
            )
        )

        return result


def _innings_to_float(
    value: Any,
) -> float:

    text = str(
        value or "0"
    )

    if "." not in text:
        return _float(text)

    whole, frac = (
        text.split(
            ".",
            1,
        )
    )

    return (
        _float(whole)
        +
        {
            "1": 1 / 3,
            "2": 2 / 3,
        }.get(
            frac[:1],
            _float(
                "0." + frac
            ),
        )
    )


def matchup_completeness(
    matchup: dict[str, Any],
) -> dict[str, Any]:

    home = matchup.get(
        "home",
        {},
    )

    away = matchup.get(
        "away",
        {},
    )

    checks = {

        "abridores":
            bool(
                home.get("pitcher_id")
                and
                away.get("pitcher_id")
            ),

        "ofensiva":
            bool(
                home
                .get("offense", {})
                .get("ops")
                and
                away
                .get("offense", {})
                .get("ops")
            ),

        "splits_lr":
            bool(
                home
                .get(
                    "offense_split",
                    {},
                )
                .get("ops")
                and
                away
                .get(
                    "offense_split",
                    {},
                )
                .get("ops")
            ),

        "bullpen":
            bool(
                home
                .get("bullpen", {})
                .get("era")
                and
                away
                .get("bullpen", {})
                .get("era")
            ),

        "forma_reciente":
            bool(
                home
                .get("recent", {})
                .get("games")
                and
                away
                .get("recent", {})
                .get("games")
            ),

        "descanso":
            (
                home.get("rest_days")
                is not None
                and
                away.get("rest_days")
                is not None
            ),

        "bullpen_reciente":
            bool(
                home
                .get(
                    "bullpen_load",
                    {},
                )
                .get("availability")
                and
                away
                .get(
                    "bullpen_load",
                    {},
                )
                .get("availability")
            ),

        "alineaciones":
            bool(
                home.get(
                    "lineup_confirmed"
                )
                and
                away.get(
                    "lineup_confirmed"
                )
            ),

        "bvp":
            bool(
                home
                .get("bvp", {})
                .get("sample_ok")
                and
                away
                .get("bvp", {})
                .get("sample_ok")
            ),

        "estadio":
            bool(
                matchup
                .get("venue", {})
                .get("name")
            ),

        "clima":
            bool(
                matchup
                .get("weather", {})
                .get("condition")
                or
                matchup
                .get("weather", {})
                .get("temp_f")
            ),
    }

    score = round(
        100
        *
        sum(
            checks.values()
        )
        /
        len(checks)
    )

    return {
        "score":
            score,
        "checks":
            checks,
        "missing":
            [
                k
                for k, v
                in checks.items()
                if not v
            ],
    }


def _team_attack_score(
    side: dict[str, Any],
) -> float:

    off = side.get(
        "offense",
        {},
    )

    split = side.get(
        "offense_split",
        {},
    )

    recent = side.get(
        "recent",
        {},
    )

    bvp = side.get(
        "bvp",
        {},
    )

    score = 0.0
    weight = 0.0

    if off.get("ops"):

        score += (
            (
                _float(
                    off["ops"]
                )
                - 0.720
            )
            / 0.10
        ) * 0.35

        weight += 0.35

    if split.get("ops"):

        score += (
            (
                _float(
                    split["ops"]
                )
                - 0.720
            )
            / 0.11
        ) * 0.30

        weight += 0.30

    if recent.get("games"):

        score += (
            (
                _float(
                    recent.get(
                        "runs_for"
                    )
                )
                - 4.35
            )
            / 1.25
        ) * 0.20

        weight += 0.20

    if bvp.get("sample_ok"):

        score += (
            (
                _float(
                    bvp.get("ops")
                )
                - 0.720
            )
            / 0.16
        ) * 0.15

        weight += 0.15

    return (
        score / weight
        if weight
        else 0.0
    )


def _starter_strength(
    side: dict[str, Any],
) -> float:

    p = side.get(
        "pitching",
        {},
    )

    if (
        not p.get("era")
        or
        not p.get("whip")
    ):
        return 0.0

    return (
        (
            (
                4.20
                -
                _float(
                    p["era"]
                )
            )
            / 1.35
        )
        +
        (
            (
                1.30
                -
                _float(
                    p["whip"]
                )
            )
            / 0.24
        )
        +
        (
            (
                _float(
                    p.get("k9")
                )
                -
                8.5
            )
            / 3.0
        )
        -
        (
            max(
                0.0,
                _float(
                    p.get("bb9")
                )
                -
                3.2,
            )
            / 2.5
        )
    ) / 3.2


def _bullpen_strength(
    side: dict[str, Any],
) -> float:

    p = side.get(
        "bullpen",
        {},
    )

    load = side.get(
        "bullpen_load",
        {},
    )

    base = 0.0

    if (
        p.get("era")
        and
        p.get("whip")
    ):

        base = (
            (
                (
                    4.25
                    -
                    _float(
                        p["era"]
                    )
                )
                / 1.25
            )
            +
            (
                (
                    1.30
                    -
                    _float(
                        p["whip"]
                    )
                )
                / 0.22
            )
        ) / 2.0

    fatigue = 0.0

    if load.get(
        "availability"
    ):

        fatigue = (
            max(
                0.0,
                _float(
                    load.get(
                        "innings_3d"
                    )
                )
                -
                8.0,
            )
            / 8.0
        )

    return (
        base
        -
        0.55
        *
        fatigue
    )


def _context_home_edge(
    matchup: dict[str, Any],
) -> float:

    home = matchup.get(
        "home",
        {},
    )

    away = matchup.get(
        "away",
        {},
    )

    edge = 0.10

    hr = home.get(
        "rest_days"
    )

    ar = away.get(
        "rest_days"
    )

    if (
        hr is not None
        and
        ar is not None
    ):

        edge += (
            0.08
            *
            max(
                -2,
                min(
                    2,
                    int(hr)
                    -
                    int(ar),
                ),
            )
        )

    weather = matchup.get(
        "weather",
        {},
    )

    if _float(
        weather.get(
            "temp_f"
        )
    ) >= 90:

        edge *= 0.95

    return edge


def first_five_home_probability(
    matchup: dict[str, Any],
) -> float | None:

    home = matchup.get(
        "home",
        {},
    )

    away = matchup.get(
        "away",
        {},
    )

    if (
        not home.get("pitcher_id")
        or
        not away.get("pitcher_id")
    ):
        return None

    if (
        not home
        .get("offense", {})
        .get("ops")
        or
        not away
        .get("offense", {})
        .get("ops")
    ):
        return None

    starter_edge = (
        _starter_strength(home)
        -
        _starter_strength(away)
    )

    offense_edge = (
        _team_attack_score(home)
        -
        _team_attack_score(away)
    )

    logit_value = (
        _context_home_edge(
            matchup
        )
        +
        0.62
        *
        starter_edge
        +
        0.38
        *
        offense_edge
    )

    return _clamp(
        _sigmoid(
            logit_value
        ),
        0.18,
        0.82,
    )


def full_game_home_probability(
    matchup: dict[str, Any],
) -> float | None:

    home = matchup.get(
        "home",
        {},
    )

    away = matchup.get(
        "away",
        {},
    )

    if (
        not home.get("pitcher_id")
        or
        not away.get("pitcher_id")
    ):
        return None

    if (
        not home
        .get("offense", {})
        .get("ops")
        or
        not away
        .get("offense", {})
        .get("ops")
    ):
        return None

    starter_edge = (
        _starter_strength(home)
        -
        _starter_strength(away)
    )

    offense_edge = (
        _team_attack_score(home)
        -
        _team_attack_score(away)
    )

    bullpen_edge = (
        _bullpen_strength(home)
        -
        _bullpen_strength(away)
    )

    logit_value = (
        _context_home_edge(
            matchup
        )
        +
        0.38
        *
        starter_edge
        +
        0.34
        *
        offense_edge
        +
        0.28
        *
        bullpen_edge
    )

    return _clamp(
        _sigmoid(
            logit_value
        ),
        0.17,
        0.83,
    )


def matchup_reason_lines(
    matchup: dict[str, Any],
) -> tuple[str, ...]:

    home = matchup.get(
        "home",
        {},
    )

    away = matchup.get(
        "away",
        {},
    )

    comp = matchup.get(
        "completeness",
        {},
    )

    lines = [

        (
            f"Abridores: "
            f"{away.get('pitcher_name', 'N/D')} "
            f"vs "
            f"{home.get('pitcher_name', 'N/D')}"
        ),

        (
            f"OPS temporada: "
            f"visitante "
            f"{away.get('offense', {}).get('ops', 0):.3f} "
            f"| local "
            f"{home.get('offense', {}).get('ops', 0):.3f}"
        ),

        (
            f"OPS split L/R: "
            f"visitante "
            f"{away.get('offense_split', {}).get('ops', 0):.3f} "
            f"| local "
            f"{home.get('offense_split', {}).get('ops', 0):.3f}"
        ),

        (
            f"Bullpen/Staff ERA: "
            f"visitante "
            f"{away.get('bullpen', {}).get('era', 0):.2f} "
            f"| local "
            f"{home.get('bullpen', {}).get('era', 0):.2f}"
        ),

        (
            f"Descanso: "
            f"visitante "
            f"{away.get('rest_days', 'N/D')} día(s) "
            f"| local "
            f"{home.get('rest_days', 'N/D')} día(s)"
        ),

        (
            f"Carga bullpen 3d: "
            f"visitante "
            f"{away.get('bullpen_load', {}).get('innings_3d', 0):.1f} IP "
            f"| local "
            f"{home.get('bullpen_load', {}).get('innings_3d', 0):.1f} IP"
        ),

        (
            f"Alineaciones confirmadas: "
            f"visitante "
            f"{'Sí' if away.get('lineup_confirmed') else 'No'} "
            f"| local "
            f"{'Sí' if home.get('lineup_confirmed') else 'No'}"
        ),

        (
            f"BvP suficiente: "
            f"visitante "
            f"{'Sí' if away.get('bvp', {}).get('sample_ok') else 'No'} "
            f"| local "
            f"{'Sí' if home.get('bvp', {}).get('sample_ok') else 'No'}"
        ),

        (
            f"Estadio/clima: "
            f"{matchup.get('venue', {}).get('name') or 'N/D'} "
            f"| "
            f"{matchup.get('weather', {}).get('condition') or 'N/D'} "
            f"{matchup.get('weather', {}).get('temp_f') or ''}"
        ),

        (
            f"Cobertura de factores MLB: "
            f"{comp.get('score', 0)}/100"
        ),
    ]

    return tuple(lines)
