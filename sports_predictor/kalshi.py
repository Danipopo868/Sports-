from __future__ import annotations

import re
import unicodedata
from typing import Any

import requests


KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


def _plain(value: Any) -> str:
    text = str(value or "").lower()

    text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode()
    )

    # Ayuda con nombres como "Mississippi St." vs "Mississippi State".
    text = re.sub(r"\bst[.]?\b", "state", text)

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


def _market_text(
    market: dict[str, Any],
) -> str:
    return _plain(
        " ".join(
            str(market.get(field) or "")
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
        # Para ganador final rechazamos cualquier mercado F5.
        return not is_f5_market

    return False


def _selection_matches_yes(
    *,
    selection: str,
    market: dict[str, Any],
) -> bool:

    selection_key = _compact(
        selection
    )

    if not selection_key:
        return False

    yes_text = _compact(
        " ".join(
            str(market.get(field) or "")
            for field in (
                "yes_sub_title",
                "title",
                "subtitle",
            )
        )
    )

    return (
        selection_key in yes_text
    )


def _matchup_matches(
    *,
    matchup: str,
    market: dict[str, Any],
) -> bool:

    if "@" not in matchup:
        return True

    away, home = matchup.split(
        "@",
        1,
    )

    away_key = _compact(
        away
    )

    home_key = _compact(
        home
    )

    combined = _compact(
        _market_text(
            market
        )
    )

    # Ideal: aparecen los dos equipos.
    if (
        away_key
        and home_key
        and away_key in combined
        and home_key in combined
    ):
        return True

    # Respaldo: al menos uno aparece.
    return bool(
        (
            away_key
            and away_key in combined
        )
        or
        (
            home_key
            and home_key in combined
        )
    )


def _market_percent(
    market: dict[str, Any],
) -> float | None:

    # Para comprar YES, preferimos el ask.
    candidates = (
        market.get(
            "yes_ask_dollars"
        ),
        market.get(
            "yes_ask"
        ),
        market.get(
            "last_price_dollars"
        ),
        market.get(
            "last_price"
        ),
    )

    for value in candidates:

        if value is None:
            continue

        try:
            number = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        # Ejemplo 0.61
        if 0 < number <= 1:
            return (
                number * 100.0
            )

        # Ejemplo 61
        if 1 < number < 100:
            return number

    return None


def find_kalshi_percent(
    *,
    selection: str,
    matchup: str,
    market: str,
) -> float | None:

    if not selection:
        return None

    cursor: str | None = None

    # Evita loops infinitos.
    for _page in range(20):

        params: dict[str, Any] = {
            "limit": 200,
            "status": "open",
        }

        if cursor:
            params[
                "cursor"
            ] = cursor

        try:

            response = requests.get(
                f"{KALSHI_BASE_URL}/markets",
                params=params,
                timeout=15,
            )

            response.raise_for_status()

            payload = (
                response.json()
            )

        except (
            requests.RequestException,
            ValueError,
        ):
            return None

        markets = payload.get(
            "markets",
            []
        )

        if not isinstance(
            markets,
            list,
        ):
            return None

        for kalshi_market in markets:

            if not isinstance(
                kalshi_market,
                dict,
            ):
                continue

            text = _market_text(
                kalshi_market
            )

            # 1. Tiene que ser Ganador o F5
            # exactamente como eligió el motor.
            if not _correct_market_type(
                market_name=market,
                kalshi_text=text,
            ):
                continue

            # 2. Tiene que corresponder
            # al mismo partido.
            if not _matchup_matches(
                matchup=matchup,
                market=kalshi_market,
            ):
                continue

            # 3. El lado YES debe representar
            # al equipo que eligió el motor.
            if not _selection_matches_yes(
                selection=selection,
                market=kalshi_market,
            ):
                continue

            percent = _market_percent(
                kalshi_market
            )

            if percent is not None:

                print(
                    (
                        "KALSHI ENCONTRADO | "
                        f"{selection} | "
                        f"{market} | "
                        f"{percent:.2f}%"
                    ),
                    flush=True,
                )

                return round(
                    percent,
                    6,
                )

        cursor_value = payload.get(
            "cursor"
        )

        if not cursor_value:
            break

        cursor = str(
            cursor_value
        )

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
