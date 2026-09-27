from __future__ import annotations

import re
import unicodedata
from typing import Any

import requests


KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


def _normalize(value: Any) -> str:
    text = str(value or "")

    plain = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )

    return re.sub(
        r"[^a-z0-9]+",
        "",
        plain,
    )


def _market_percent(market: dict[str, Any]) -> float | None:
    candidates = (
        market.get("yes_ask"),
        market.get("yes_ask_dollars"),
        market.get("last_price"),
        market.get("last_price_dollars"),
    )

    for value in candidates:
        if value is None:
            continue

        try:
            number = float(value)
        except (TypeError, ValueError):
            continue

        if 0 < number <= 1:
            return number * 100.0

        if 1 < number < 100:
            return number

    return None


def find_kalshi_percent(
    *,
    selection: str,
    matchup: str,
) -> float | None:

    selection_key = _normalize(
        selection
    )

    matchup_key = _normalize(
        matchup
    )

    if not selection_key:
        return None

    try:
        response = requests.get(
            f"{KALSHI_BASE_URL}/markets",
            params={
                "limit": 1000,
                "status": "open",
            },
            timeout=15,
        )

        response.raise_for_status()

        payload = response.json()

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

    for market in markets:

        if not isinstance(
            market,
            dict,
        ):
            continue

        title = str(
            market.get("title")
            or ""
        )

        subtitle = str(
            market.get("subtitle")
            or ""
        )

        yes_sub_title = str(
            market.get("yes_sub_title")
            or ""
        )

        combined = _normalize(
            f"{title} "
            f"{subtitle} "
            f"{yes_sub_title}"
        )

        if selection_key not in combined:
            continue

        # El matchup sirve como filtro extra,
        # pero no bloquea si Kalshi usa nombres distintos.
        if matchup_key:
            matchup_tokens = [
                token
                for token in re.split(
                    r"[^a-z0-9]+",
                    matchup.lower(),
                )
                if len(token) >= 4
            ]

            hits = sum(
                _normalize(token)
                in combined
                for token
                in matchup_tokens
            )

            if hits == 0:
                continue

        percent = _market_percent(
            market
        )

        if percent is not None:
            return round(
                percent,
                6,
            )

    return None
