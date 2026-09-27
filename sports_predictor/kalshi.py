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
        MLB_TEAM_ALIASES.get(
            team,
            (),
        )
    )

    return (
        team,
        *aliases,
    )


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

    f5_tokens = (
        "first 5",
        "first five",
        "1st 5",
        "first 5 innings",
        "first five innings",
        "5 innings",
        "through 5 innings",
        "through five innings",
        "f5",
    )

    is_f5_market = any(
        token in text
        for token in f5_tokens
    )

    if requested == _plain(
        "Primeras 5 entradas"
    ):
        return is_f5_market

    if requested == _plain(
        "Ganador del partido"
    ):
        return not is_f5_market

    return False


def _selection_side(
    *,
    selection: str,
    market: dict[str, Any],
) -> str | None:

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

    requested_market = (
        _plain(
            market
        )
    )

    if (
        requested_market
        == _plain(
            "Primeras 5 entradas"
        )
    ):

        series_ticker = (
            "KXMLBF5"
        )

    elif (
        requested_market
        == _plain(
            "Ganador del partido"
        )
    ):

        series_ticker = (
            "KXMLBGAME"
        )

    else:

        series_ticker = None

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
) -> float | None:

    quote = find_kalshi_quote(
        selection=selection,
        matchup=matchup,
        market=market,
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
