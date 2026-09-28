from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

import requests


KALSHI_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


MLB_TEAM_ALIASES = {
    "Arizona Diamondbacks": (
        "Arizona",
    ),
    "Athletics": (
        "Athletics",
        "Oakland",
    ),
    "Atlanta Braves": (
        "Atlanta",
    ),
    "Baltimore Orioles": (
        "Baltimore",
    ),
    "Boston Red Sox": (
        "Boston",
    ),
    "Chicago Cubs": (
        "Chicago Cubs",
        "Chicago C",
    ),
    "Chicago White Sox": (
        "Chicago White Sox",
        "Chicago WS",
    ),
    "Cincinnati Reds": (
        "Cincinnati",
    ),
    "Cleveland Guardians": (
        "Cleveland",
    ),
    "Colorado Rockies": (
        "Colorado",
    ),
    "Detroit Tigers": (
        "Detroit",
    ),
    "Houston Astros": (
        "Houston",
    ),
    "Kansas City Royals": (
        "Kansas City",
    ),
    "Los Angeles Angels": (
        "Los Angeles Angels",
        "Los Angeles A",
    ),
    "Los Angeles Dodgers": (
        "Los Angeles Dodgers",
        "Los Angeles D",
    ),
    "Miami Marlins": (
        "Miami",
    ),
    "Milwaukee Brewers": (
        "Milwaukee",
    ),
    "Minnesota Twins": (
        "Minnesota",
    ),
    "New York Mets": (
        "New York Mets",
        "New York M",
    ),
    "New York Yankees": (
        "New York Yankees",
        "New York Y",
    ),
    "Philadelphia Phillies": (
        "Philadelphia",
    ),
    "Pittsburgh Pirates": (
        "Pittsburgh",
    ),
    "San Diego Padres": (
        "San Diego",
    ),
    "San Francisco Giants": (
        "San Francisco",
    ),
    "Seattle Mariners": (
        "Seattle",
    ),
    "St. Louis Cardinals": (
        "St. Louis",
    ),
    "Tampa Bay Rays": (
        "Tampa Bay",
    ),
    "Texas Rangers": (
        "Texas",
    ),
    "Toronto Blue Jays": (
        "Toronto",
    ),
    "Washington Nationals": (
        "Washington",
    ),
}


MLB_TEAM_CODES = {
    "Arizona Diamondbacks": (
        "ARI",
    ),
    "Athletics": (
        "ATH",
        "OAK",
    ),
    "Atlanta Braves": (
        "ATL",
    ),
    "Baltimore Orioles": (
        "BAL",
    ),
    "Boston Red Sox": (
        "BOS",
    ),
    "Chicago Cubs": (
        "CHC",
    ),
    "Chicago White Sox": (
        "CHW",
        "CWS",
    ),
    "Cincinnati Reds": (
        "CIN",
    ),
    "Cleveland Guardians": (
        "CLE",
    ),
    "Colorado Rockies": (
        "COL",
    ),
    "Detroit Tigers": (
        "DET",
    ),
    "Houston Astros": (
        "HOU",
    ),
    "Kansas City Royals": (
        "KC",
        "KCR",
    ),
    "Los Angeles Angels": (
        "LAA",
    ),
    "Los Angeles Dodgers": (
        "LAD",
    ),
    "Miami Marlins": (
        "MIA",
    ),
    "Milwaukee Brewers": (
        "MIL",
    ),
    "Minnesota Twins": (
        "MIN",
    ),
    "New York Mets": (
        "NYM",
    ),
    "New York Yankees": (
        "NYY",
    ),
    "Philadelphia Phillies": (
        "PHI",
    ),
    "Pittsburgh Pirates": (
        "PIT",
    ),
    "San Diego Padres": (
        "SD",
        "SDP",
    ),
    "San Francisco Giants": (
        "SF",
        "SFG",
    ),
    "Seattle Mariners": (
        "SEA",
    ),
    "St. Louis Cardinals": (
        "STL",
    ),
    "Tampa Bay Rays": (
        "TB",
        "TBR",
    ),
    "Texas Rangers": (
        "TEX",
    ),
    "Toronto Blue Jays": (
        "TOR",
    ),
    "Washington Nationals": (
        "WSH",
        "WAS",
    ),
}


NFL_TEAM_ALIASES = {
    "Arizona Cardinals": ("Arizona", "ARI Cardinals", "Cardinals"),
    "Atlanta Falcons": ("Atlanta", "ATL Falcons", "Falcons"),
    "Baltimore Ravens": ("Baltimore", "BAL Ravens", "Ravens"),
    "Buffalo Bills": ("Buffalo", "BUF Bills", "Bills"),
    "Carolina Panthers": ("Carolina", "CAR Panthers", "Panthers"),
    "Chicago Bears": ("Chicago", "CHI Bears", "Bears"),
    "Cincinnati Bengals": ("Cincinnati", "CIN Bengals", "Bengals"),
    "Cleveland Browns": ("Cleveland", "CLE Browns", "Browns"),
    "Dallas Cowboys": ("Dallas", "DAL Cowboys", "Cowboys"),
    "Denver Broncos": ("Denver", "DEN Broncos", "Broncos"),
    "Detroit Lions": ("Detroit", "DET Lions", "Lions"),
    "Green Bay Packers": ("Green Bay", "GB Packers", "Packers"),
    "Houston Texans": ("Houston", "HOU Texans", "Texans"),
    "Indianapolis Colts": ("Indianapolis", "IND Colts", "Colts"),
    "Jacksonville Jaguars": ("Jacksonville", "JAX Jaguars", "Jaguars"),
    "Kansas City Chiefs": ("Kansas City", "KC Chiefs", "Chiefs"),
    "Las Vegas Raiders": ("Las Vegas", "LV Raiders", "Raiders"),
    "Los Angeles Chargers": ("Los Angeles C", "LA Chargers", "LAC Chargers", "Chargers"),
    "Los Angeles Rams": ("Los Angeles R", "LA Rams", "LAR Rams", "Rams"),
    "Miami Dolphins": ("Miami", "MIA Dolphins", "Dolphins"),
    "Minnesota Vikings": ("Minnesota", "MIN Vikings", "Vikings"),
    "New England Patriots": ("New England", "NE Patriots", "Patriots"),
    "New Orleans Saints": ("New Orleans", "NO Saints", "Saints"),
    "New York Giants": ("New York G", "NY Giants", "NYG Giants", "Giants"),
    "New York Jets": ("New York J", "NY Jets", "NYJ Jets", "Jets"),
    "Philadelphia Eagles": ("Philadelphia", "PHI Eagles", "Eagles"),
    "Pittsburgh Steelers": ("Pittsburgh", "PIT Steelers", "Steelers"),
    "San Francisco 49ers": ("San Francisco", "SF 49ers", "49ers"),
    "Seattle Seahawks": ("Seattle", "SEA Seahawks", "Seahawks"),
    "Tampa Bay Buccaneers": ("Tampa Bay", "TB Buccaneers", "Buccaneers", "Bucs"),
    "Tennessee Titans": ("Tennessee", "TEN Titans", "Titans"),
    "Washington Commanders": ("Washington", "WAS Commanders", "WSH Commanders", "Commanders"),
}


NFL_TEAM_CODES = {
    "Arizona Cardinals": ("ARI",),
    "Atlanta Falcons": ("ATL",),
    "Baltimore Ravens": ("BAL",),
    "Buffalo Bills": ("BUF",),
    "Carolina Panthers": ("CAR",),
    "Chicago Bears": ("CHI",),
    "Cincinnati Bengals": ("CIN",),
    "Cleveland Browns": ("CLE",),
    "Dallas Cowboys": ("DAL",),
    "Denver Broncos": ("DEN",),
    "Detroit Lions": ("DET",),
    "Green Bay Packers": ("GB",),
    "Houston Texans": ("HOU",),
    "Indianapolis Colts": ("IND",),
    "Jacksonville Jaguars": ("JAX",),
    "Kansas City Chiefs": ("KC",),
    "Las Vegas Raiders": ("LV",),
    "Los Angeles Chargers": ("LAC",),
    "Los Angeles Rams": ("LAR",),
    "Miami Dolphins": ("MIA",),
    "Minnesota Vikings": ("MIN",),
    "New England Patriots": ("NE",),
    "New Orleans Saints": ("NO",),
    "New York Giants": ("NYG",),
    "New York Jets": ("NYJ",),
    "Philadelphia Eagles": ("PHI",),
    "Pittsburgh Steelers": ("PIT",),
    "San Francisco 49ers": ("SF",),
    "Seattle Seahawks": ("SEA",),
    "Tampa Bay Buccaneers": ("TB",),
    "Tennessee Titans": ("TEN",),
    "Washington Commanders": ("WAS", "WSH"),
}


NBA_TEAM_ALIASES = {
    "Atlanta Hawks": ("Atlanta", "ATL Hawks", "Hawks"),
    "Boston Celtics": ("Boston", "BOS Celtics", "Celtics"),
    "Brooklyn Nets": ("Brooklyn", "BKN Nets", "Nets"),
    "Charlotte Hornets": ("Charlotte", "CHA Hornets", "Hornets"),
    "Chicago Bulls": ("Chicago", "CHI Bulls", "Bulls"),
    "Cleveland Cavaliers": ("Cleveland", "CLE Cavaliers", "Cavaliers", "Cavs"),
    "Dallas Mavericks": ("Dallas", "DAL Mavericks", "Mavericks", "Mavs"),
    "Denver Nuggets": ("Denver", "DEN Nuggets", "Nuggets"),
    "Detroit Pistons": ("Detroit", "DET Pistons", "Pistons"),
    "Golden State Warriors": ("Golden State", "GSW Warriors", "Warriors"),
    "Houston Rockets": ("Houston", "HOU Rockets", "Rockets"),
    "Indiana Pacers": ("Indiana", "IND Pacers", "Pacers"),
    "Los Angeles Clippers": ("Los Angeles C", "LA Clippers", "LAC Clippers", "Clippers"),
    "LA Clippers": ("Los Angeles C", "LA Clippers", "LAC Clippers", "Clippers"),
    "Los Angeles Lakers": ("Los Angeles L", "LA Lakers", "LAL Lakers", "Lakers"),
    "Memphis Grizzlies": ("Memphis", "MEM Grizzlies", "Grizzlies"),
    "Miami Heat": ("Miami", "MIA Heat", "Heat"),
    "Milwaukee Bucks": ("Milwaukee", "MIL Bucks", "Bucks"),
    "Minnesota Timberwolves": ("Minnesota", "MIN Timberwolves", "Timberwolves", "Wolves"),
    "New Orleans Pelicans": ("New Orleans", "NOP Pelicans", "Pelicans"),
    "New York Knicks": ("New York", "New York K", "NY Knicks", "NYK Knicks", "Knicks"),
    "Oklahoma City Thunder": ("Oklahoma City", "OKC Thunder", "Thunder"),
    "Orlando Magic": ("Orlando", "ORL Magic", "Magic"),
    "Philadelphia 76ers": ("Philadelphia", "PHI 76ers", "76ers", "Sixers"),
    "Phoenix Suns": ("Phoenix", "PHX Suns", "Suns"),
    "Portland Trail Blazers": ("Portland", "POR Trail Blazers", "Trail Blazers", "Blazers"),
    "Sacramento Kings": ("Sacramento", "SAC Kings", "Kings"),
    "San Antonio Spurs": ("San Antonio", "SAS Spurs", "Spurs"),
    "Toronto Raptors": ("Toronto", "TOR Raptors", "Raptors"),
    "Utah Jazz": ("Utah", "UTA Jazz", "Jazz"),
    "Washington Wizards": ("Washington", "WAS Wizards", "WSH Wizards", "Wizards"),
}


NBA_TEAM_CODES = {
    "Atlanta Hawks": ("ATL",),
    "Boston Celtics": ("BOS",),
    "Brooklyn Nets": ("BKN",),
    "Charlotte Hornets": ("CHA",),
    "Chicago Bulls": ("CHI",),
    "Cleveland Cavaliers": ("CLE",),
    "Dallas Mavericks": ("DAL",),
    "Denver Nuggets": ("DEN",),
    "Detroit Pistons": ("DET",),
    "Golden State Warriors": ("GSW",),
    "Houston Rockets": ("HOU",),
    "Indiana Pacers": ("IND",),
    "Los Angeles Clippers": ("LAC",),
    "LA Clippers": ("LAC",),
    "Los Angeles Lakers": ("LAL",),
    "Memphis Grizzlies": ("MEM",),
    "Miami Heat": ("MIA",),
    "Milwaukee Bucks": ("MIL",),
    "Minnesota Timberwolves": ("MIN",),
    "New Orleans Pelicans": ("NOP",),
    "New York Knicks": ("NYK",),
    "Oklahoma City Thunder": ("OKC",),
    "Orlando Magic": ("ORL",),
    "Philadelphia 76ers": ("PHI",),
    "Phoenix Suns": ("PHX",),
    "Portland Trail Blazers": ("POR",),
    "Sacramento Kings": ("SAC",),
    "San Antonio Spurs": ("SAS",),
    "Toronto Raptors": ("TOR",),
    "Utah Jazz": ("UTA",),
    "Washington Wizards": ("WAS", "WSH"),
}


def _plain(value: Any) -> str:
    text = str(
        value or ""
    ).lower()

    text = (
        unicodedata.normalize(
            "NFKD",
            text,
        )
        .encode(
            "ascii",
            "ignore",
        )
        .decode()
    )

    text = re.sub(
        r"\bst[.]?\b",
        "state",
        text,
    )

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    ).strip()


def _compact(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        _plain(value),
    )


def _team_aliases(
    team: str,
) -> tuple[str, ...]:

    aliases = (
        MLB_TEAM_ALIASES.get(team)
        or NFL_TEAM_ALIASES.get(team)
        or NBA_TEAM_ALIASES.get(team)
        or ()
    )

    return (
        team,
        *aliases,
    )


def _team_codes(
    team: str,
) -> tuple[str, ...]:

    return (
        MLB_TEAM_CODES.get(team)
        or NFL_TEAM_CODES.get(team)
        or NBA_TEAM_CODES.get(team)
        or ()
    )


def _infer_sport(
    selection: str,
    matchup: str,
) -> str | None:

    names = {
        selection,
    }

    if "@" in matchup:
        away, home = (
            part.strip()
            for part in matchup.split(
                "@",
                1,
            )
        )
        names.update((away, home))

    if any(
        name in MLB_TEAM_CODES
        for name in names
    ):
        return "MLB"

    if any(
        name in NFL_TEAM_CODES
        for name in names
    ):
        return "NFL"

    if any(
        name in NBA_TEAM_CODES
        for name in names
    ):
        return "NBA"

    return None


def _series_ticker_for(
    *,
    sport: str | None,
    market: str,
) -> str | None:

    sport_code = str(
        sport or ""
    ).upper().strip()

    requested_market = _plain(
        market
    )

    if (
        requested_market
        == _plain(
            "Primeras 5 entradas"
        )
    ):
        return (
            "KXMLBF5"
            if sport_code == "MLB"
            else None
        )

    if (
        requested_market
        != _plain(
            "Ganador del partido"
        )
    ):
        return None

    return {
        "MLB": "KXMLBGAME",
        "NFL": "KXNFLGAME",
        "NCAAF": "KXNCAAFGAME",
        "NBA": "KXNBAGAME",
    }.get(
        sport_code
    )


def _market_game_date(
    market: dict[str, Any],
) -> datetime | None:

    for field in (
        "event_ticker",
        "ticker",
    ):

        text = str(
            market.get(field)
            or ""
        ).upper()

        match = re.search(
            r"-(\d{2}[A-Z]{3}\d{2})",
            text,
        )

        if not match:
            continue

        try:
            parsed = datetime.strptime(
                match.group(1),
                "%y%b%d",
            )
        except ValueError:
            continue

        return parsed.replace(
            tzinfo=timezone.utc
        )

    return None


def _game_date_matches(
    *,
    game_start: str | datetime | None,
    market: dict[str, Any],
) -> bool:

    requested = _parse_time(
        game_start
    )

    market_date = _market_game_date(
        market
    )

    if (
        requested is None
        or market_date is None
    ):
        return True

    return abs(
        (
            market_date.date()
            - requested.date()
        ).days
    ) <= 1


def _market_text(
    market: dict[str, Any],
) -> str:

    return _plain(
        " ".join(
            str(
                market.get(field)
                or ""
            )
            for field in (
                "title",
                "subtitle",
                "yes_sub_title",
                "no_sub_title",
                "ticker",
                "event_ticker",
            )
        )
    )


def _correct_market_type(
    *,
    market_name: str,
    kalshi_text: str,
) -> bool:

    requested = _plain(
        market_name
    )

    text = _plain(
        kalshi_text
    )

    # La serie ya limita la busqueda al producto correcto:
    # KXMLBF5 = primeras 5 entradas.
    # No exigir que el titulo de cada contrato repita "first 5"/"f5",
    # porque Kalshi puede omitir ese texto en title/subtitle.
    if requested == _plain(
        "Primeras 5 entradas"
    ):
        return True

    # KXMLBGAME/KXNFLGAME/KXNCAAFGAME/KXNBAGAME ya son mercados
    # de ganador del partido. Tampoco hace falta inferirlo del titulo.
    if requested == _plain(
        "Ganador del partido"
    ):
        return True

    return False


def _selection_side(
    *,
    selection: str,
    market: dict[str, Any],
) -> str | None:

    # Primero usamos el sufijo del ticker del mercado.
    # Ejemplo: ...CHCBOS-CHC significa YES = Chicago Cubs.
    ticker = str(
        market.get(
            "ticker"
        )
        or ""
    ).upper()

    ticker_side = (
        ticker.rsplit(
            "-",
            1,
        )[-1]
        if "-" in ticker
        else ""
    )

    selection_codes = {
        re.sub(
            r"[^A-Z0-9]+",
            "",
            code.upper(),
        )
        for code in _team_codes(
            selection
        )
    }

    if (
        ticker_side
        and ticker_side
        in selection_codes
    ):
        return "YES"

    aliases = tuple(
        _compact(alias)
        for alias in _team_aliases(
            selection
        )
        if _compact(alias)
    )

    if not aliases:
        return None

    yes_sub = _compact(
        market.get(
            "yes_sub_title"
        )
    )

    no_sub = _compact(
        market.get(
            "no_sub_title"
        )
    )

    for alias in aliases:

        if (
            yes_sub
            and alias in yes_sub
        ):
            return "YES"

        if (
            no_sub
            and alias in no_sub
        ):
            return "NO"

    yes_text = _compact(
        " ".join(
            str(
                market.get(field)
                or ""
            )
            for field in (
                "yes_sub_title",
                "title",
                "subtitle",
            )
        )
    )

    no_text = _compact(
        " ".join(
            str(
                market.get(field)
                or ""
            )
            for field in (
                "no_sub_title",
                "title",
                "subtitle",
            )
        )
    )

    for alias in aliases:

        yes_match = (
            alias in yes_text
        )

        no_match = (
            alias in no_text
        )

        if (
            yes_match
            and not no_match
        ):
            return "YES"

        if (
            no_match
            and not yes_match
        ):
            return "NO"

    return None

def _matchup_matches(
    *,
    matchup: str,
    market: dict[str, Any],
) -> bool:

    if "@" not in matchup:
        return True

    away, home = (
        part.strip()
        for part in matchup.split(
            "@",
            1,
        )
    )

    event_text = _compact(
        " ".join(
            (
                str(
                    market.get(
                        "event_ticker"
                    )
                    or ""
                ),
                str(
                    market.get(
                        "ticker"
                    )
                    or ""
                ),
            )
        )
    )

    away_codes = _team_codes(
        away
    )

    home_codes = _team_codes(
        home
    )

    for away_code in away_codes:
        for home_code in home_codes:

            pair = _compact(
                away_code
                + home_code
            )

            reverse_pair = _compact(
                home_code
                + away_code
            )

            if (
                pair in event_text
                or reverse_pair in event_text
            ):
                return True

    away_aliases = tuple(
        _compact(alias)
        for alias in _team_aliases(
            away
        )
        if _compact(alias)
    )

    home_aliases = tuple(
        _compact(alias)
        for alias in _team_aliases(
            home
        )
        if _compact(alias)
    )

    combined = _compact(
        _market_text(
            market
        )
    )

    away_match = any(
        alias in combined
        for alias in away_aliases
    )

    home_match = any(
        alias in combined
        for alias in home_aliases
    )

    return (
        away_match
        and home_match
    )


def _price_to_dollars(
    value: Any,
) -> float | None:

    if value is None:
        return None

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if (
        0
        < number
        <= 1
    ):
        return number

    if (
        1
        < number
        < 100
    ):
        return (
            number
            / 100.0
        )

    return None


def _current_side_price(
    *,
    market: dict[str, Any],
    side: str,
) -> tuple[
    float | None,
    str | None,
]:

    if side == "YES":

        candidates = (
            (
                market.get(
                    "yes_ask_dollars"
                ),
                "YES_ASK",
            ),
            (
                market.get(
                    "yes_ask"
                ),
                "YES_ASK",
            ),
            (
                market.get(
                    "last_price_dollars"
                ),
                "LAST_PRICE",
            ),
            (
                market.get(
                    "last_price"
                ),
                "LAST_PRICE",
            ),
        )

        for (
            value,
            source,
        ) in candidates:

            price = (
                _price_to_dollars(
                    value
                )
            )

            if price is not None:
                return (
                    price,
                    source,
                )

        return (
            None,
            None,
        )

    if side == "NO":

        candidates = (
            (
                market.get(
                    "no_ask_dollars"
                ),
                "NO_ASK",
            ),
            (
                market.get(
                    "no_ask"
                ),
                "NO_ASK",
            ),
        )

        for (
            value,
            source,
        ) in candidates:

            price = (
                _price_to_dollars(
                    value
                )
            )

            if price is not None:
                return (
                    price,
                    source,
                )

        yes_last = (
            _price_to_dollars(
                market.get(
                    "last_price_dollars"
                )
            )
        )

        if yes_last is None:

            yes_last = (
                _price_to_dollars(
                    market.get(
                        "last_price"
                    )
                )
            )

        if yes_last is not None:

            no_price = (
                1.0
                - yes_last
            )

            if (
                0
                < no_price
                < 1
            ):
                return (
                    no_price,
                    "LAST_PRICE_COMPLEMENT",
                )

    return (
        None,
        None,
    )


def _parse_time(
    value: Any,
) -> datetime | None:

    if isinstance(
        value,
        datetime,
    ):

        dt = value

    else:

        text = str(
            value or ""
        ).strip()

        if not text:
            return None

        try:

            dt = (
                datetime.fromisoformat(
                    text.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

        except ValueError:
            return None

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(
        timezone.utc
    )


def _trade_time(
    trade: dict[str, Any],
) -> datetime | None:

    for field in (
        "created_time",
        "created_at",
        "ts",
        "timestamp",
    ):

        value = trade.get(
            field
        )

        if value is None:
            continue

        if isinstance(
            value,
            (int, float),
        ):

            try:

                return (
                    datetime.fromtimestamp(
                        float(value),
                        tz=timezone.utc,
                    )
                )

            except (
                OSError,
                OverflowError,
                ValueError,
            ):
                continue

        parsed = _parse_time(
            value
        )

        if parsed is not None:
            return parsed

    return None


def _trade_side_price(
    *,
    trade: dict[str, Any],
    side: str,
) -> float | None:

    if side == "YES":

        for field in (
            "yes_price_dollars",
            "yes_price",
        ):

            price = (
                _price_to_dollars(
                    trade.get(
                        field
                    )
                )
            )

            if price is not None:
                return price

        return None

    if side == "NO":

        for field in (
            "no_price_dollars",
            "no_price",
        ):

            price = (
                _price_to_dollars(
                    trade.get(
                        field
                    )
                )
            )

            if price is not None:
                return price

        yes_price = None

        for field in (
            "yes_price_dollars",
            "yes_price",
        ):

            yes_price = (
                _price_to_dollars(
                    trade.get(
                        field
                    )
                )
            )

            if yes_price is not None:
                break

        if yes_price is not None:

            no_price = (
                1.0
                - yes_price
            )

            if (
                0
                < no_price
                < 1
            ):
                return no_price

    return None


def _historical_trade_price(
    *,
    ticker: str,
    side: str,
    at_time: datetime,
) -> tuple[
    float | None,
    datetime | None,
    str | None,
]:

    windows = (
        120,
        600,
    )

    for seconds in windows:

        min_ts = (
            int(
                at_time.timestamp()
            )
            - seconds
        )

        max_ts = (
            int(
                at_time.timestamp()
            )
            + seconds
        )

        params = {
            "ticker": ticker,
            "min_ts": min_ts,
            "max_ts": max_ts,
            "limit": 1000,
            "is_block_trade": "false",
        }

        urls = (
            (
                f"{KALSHI_BASE_URL}"
                "/markets/trades"
            ),
            (
                f"{KALSHI_BASE_URL}"
                "/historical/trades"
            ),
        )

        for url in urls:

            try:

                response = requests.get(
                    url,
                    params=params,
                    timeout=15,
                )

                if (
                    response.status_code
                    >= 400
                ):
                    continue

                payload = (
                    response.json()
                )

            except (
                requests.RequestException,
                ValueError,
            ):
                continue

            trades = payload.get(
                "trades",
                [],
            )

            if not isinstance(
                trades,
                list,
            ):
                continue

            valid: list[
                tuple[
                    float,
                    datetime,
                    float,
                ]
            ] = []

            for trade in trades:

                if not isinstance(
                    trade,
                    dict,
                ):
                    continue

                moment = (
                    _trade_time(
                        trade
                    )
                )

                if moment is None:
                    continue

                price = (
                    _trade_side_price(
                        trade=trade,
                        side=side,
                    )
                )

                if price is None:
                    continue

                distance = abs(
                    (
                        moment
                        - at_time
                    ).total_seconds()
                )

                valid.append(
                    (
                        distance,
                        moment,
                        price,
                    )
                )

            if valid:

                valid.sort(
                    key=lambda item: (
                        item[0],
                        item[1],
                    )
                )

                (
                    _distance,
                    moment,
                    price,
                ) = valid[0]

                return (
                    price,
                    moment,
                    "HISTORICAL_TRADE",
                )

    return (
        None,
        None,
        None,
    )


def _fetch_markets(
    *,
    status: str | None,
    series_ticker: str | None = None,
) -> list[
    dict[str, Any]
]:

    found: list[
        dict[str, Any]
    ] = []

    cursor: str | None = None

    for _page in range(
        20
    ):

        params: dict[
            str,
            Any,
        ] = {
            "limit": 200,
        }

        if status:

            params[
                "status"
            ] = status

        if series_ticker:

            params[
                "series_ticker"
            ] = series_ticker

        if cursor:

            params[
                "cursor"
            ] = cursor

        try:

            response = requests.get(
                (
                    f"{KALSHI_BASE_URL}"
                    "/markets"
                ),
                params=params,
                timeout=15,
            )

            if (
                response.status_code
                >= 400
            ):
                return found

            payload = (
                response.json()
            )

        except (
            requests.RequestException,
            ValueError,
        ):
            return found

        markets = payload.get(
            "markets",
            [],
        )

        if not isinstance(
            markets,
            list,
        ):
            return found

        for market in markets:

            if isinstance(
                market,
                dict,
            ):

                found.append(
                    market
                )

        cursor_value = (
            payload.get(
                "cursor"
            )
        )

        if not cursor_value:
            break

        cursor = str(
            cursor_value
        )

    return found


def find_kalshi_quote(
    *,
    selection: str,
    matchup: str,
    market: str,
    sport: str | None = None,
    game_start: str
    | datetime
    | None = None,
    at_time: str
    | datetime
    | None = None,
) -> dict[str, Any] | None:

    if not selection:
        return None

    requested_time = (
        _parse_time(
            at_time
        )
    )

    effective_sport = (
        str(
            sport or ""
        ).upper().strip()
        or _infer_sport(
            selection,
            matchup,
        )
    )

    series_ticker = (
        _series_ticker_for(
            sport=effective_sport,
            market=market,
        )
    )

    statuses: tuple[
        str | None,
        ...
    ] = (
        "open",
        "closed",
        "settled",
        None,
    )

    checked_tickers: set[
        str
    ] = set()

    for status in statuses:

        markets = (
            _fetch_markets(
                status=status,
                series_ticker=(
                    series_ticker
                ),
            )
        )

        print(
            (
                "KALSHI DEBUG | "
                f"seleccion={selection} | "
                f"deporte={effective_sport} | "
                f"mercado={market} | "
                f"status={status} | "
                f"serie={series_ticker} | "
                f"cantidad={len(markets)}"
            ),
            flush=True,
        )

        for debug_market in markets[:10]:

            print(
                (
                    "KALSHI MARKET | "
                    f"{debug_market.get('ticker')} | "
                    f"title={debug_market.get('title')} | "
                    f"subtitle={debug_market.get('subtitle')} | "
                    f"YES={debug_market.get('yes_sub_title')} | "
                    f"NO={debug_market.get('no_sub_title')}"
                ),
                flush=True,
            )

        for kalshi_market in markets:

            text = (
                _market_text(
                    kalshi_market
                )
            )

            if not _correct_market_type(
                market_name=market,
                kalshi_text=text,
            ):
                continue

            if not _game_date_matches(
                game_start=game_start,
                market=kalshi_market,
            ):
                continue

            if not _matchup_matches(
                matchup=matchup,
                market=kalshi_market,
            ):
                continue

            side = (
                _selection_side(
                    selection=selection,
                    market=kalshi_market,
                )
            )

            if side is None:
                continue

            ticker = str(
                kalshi_market.get(
                    "ticker"
                )
                or ""
            ).strip()

            if not ticker:
                continue

            if (
                ticker
                in checked_tickers
            ):
                continue

            checked_tickers.add(
                ticker
            )

            if (
                requested_time
                is not None
            ):

                (
                    historical_price,
                    historical_time,
                    historical_source,
                ) = (
                    _historical_trade_price(
                        ticker=ticker,
                        side=side,
                        at_time=(
                            requested_time
                        ),
                    )
                )

                if (
                    historical_price
                    is not None
                ):

                    percent = (
                        historical_price
                        * 100.0
                    )

                    result = {
                        "ticker": ticker,
                        "event_ticker": (
                            kalshi_market.get(
                                "event_ticker"
                            )
                        ),
                        "side": side,
                        "price": round(
                            historical_price,
                            6,
                        ),
                        "percent": round(
                            percent,
                            6,
                        ),
                        "price_source": (
                            historical_source
                        ),
                        "price_time": (
                            historical_time.isoformat()
                            if historical_time
                            else None
                        ),
                        "market_status": (
                            kalshi_market.get(
                                "status"
                            )
                        ),
                        "title": (
                            kalshi_market.get(
                                "title"
                            )
                        ),
                    }

                    print(
                        (
                            "KALSHI HISTORICO | "
                            f"{selection} | "
                            f"{market} | "
                            f"{side} | "
                            f"{percent:.2f}% | "
                            f"{ticker}"
                        ),
                        flush=True,
                    )

                    return result

                # Si se pidio una cuota historica, NO usar como sustituto
                # el precio actual/cerrado/liquidado. Probar el siguiente
                # mercado coincidente; si ninguno tiene trade historico,
                # la funcion terminara devolviendo None.
                continue

            (
                current_price,
                source,
            ) = (
                _current_side_price(
                    market=kalshi_market,
                    side=side,
                )
            )

            if (
                current_price
                is not None
            ):

                percent = (
                    current_price
                    * 100.0
                )

                result = {
                    "ticker": ticker,
                    "event_ticker": (
                        kalshi_market.get(
                            "event_ticker"
                        )
                    ),
                    "side": side,
                    "price": round(
                        current_price,
                        6,
                    ),
                    "percent": round(
                        percent,
                        6,
                    ),
                    "price_source": (
                        source
                    ),
                    "price_time": None,
                    "market_status": (
                        kalshi_market.get(
                            "status"
                        )
                    ),
                    "title": (
                        kalshi_market.get(
                            "title"
                        )
                    ),
                }

                print(
                    (
                        "KALSHI ENCONTRADO | "
                        f"{selection} | "
                        f"{market} | "
                        f"{side} | "
                        f"{percent:.2f}% | "
                        f"{ticker}"
                    ),
                    flush=True,
                )

                return result

    print(
        (
            "KALSHI SIN MERCADO | "
            f"{selection} | "
            f"{market} | "
            f"{matchup}"
        ),
        flush=True,
    )

    return None


def find_kalshi_percent(
    *,
    selection: str,
    matchup: str,
    market: str,
    sport: str | None = None,
    game_start: str
    | datetime
    | None = None,
) -> float | None:

    quote = find_kalshi_quote(
        selection=selection,
        matchup=matchup,
        market=market,
        sport=sport,
        game_start=game_start,
    )

    if quote is None:
        return None

    try:

        return float(
            quote[
                "percent"
            ]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return None
