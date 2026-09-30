from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import Candidate, Game, is_finished, score_for_side
from .kalshi import find_kalshi_quote
from .mlb import MlbStatsClient


DEFAULT_STAKE = 100.0

_MLB = MlbStatsClient()


def load_history(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        return []

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return (
            data
            if isinstance(data, list)
            else []
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []


def save_history(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            rows,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def _float(
    value: Any,
) -> float | None:

    try:
        if value is None:
            return None

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _game_date(
    game: Game,
) -> str | None:

    text = str(
        game.start
        or ""
    ).strip()

    if not text:
        return None

    try:
        normalized = text.replace(
            "Z",
            "+00:00",
        )

        dt = datetime.fromisoformat(
            normalized
        )

        return dt.date().isoformat()

    except ValueError:
        pass

    if len(text) >= 10:
        candidate = text[:10]

        try:
            datetime.strptime(
                candidate,
                "%Y-%m-%d",
            )

            return candidate

        except ValueError:
            return None

    return None


def _apply_financials(
    row: dict[str, Any],
) -> None:

    price = _float(
        row.get("kalshi_price")
    )

    if (
        price is None
        or price <= 0
        or price >= 1
    ):

        row["financial_tracking"] = False
        row["stake"] = None
        row["contracts"] = None
        row["potential_return"] = None
        row["potential_profit"] = None

        if row.get("result") in {
            "GANADA",
            "PERDIDA",
            "EMPATE",
        }:
            row["return_amount"] = None
            row["profit_loss"] = None

        return

    stake = DEFAULT_STAKE

    contracts = (
        stake / price
    )

    potential_return = contracts

    potential_profit = (
        potential_return
        - stake
    )

    row["financial_tracking"] = True

    row["stake"] = round(
        stake,
        2,
    )

    row["contracts"] = round(
        contracts,
        4,
    )

    row["potential_return"] = round(
        potential_return,
        2,
    )

    row["potential_profit"] = round(
        potential_profit,
        2,
    )

    result = row.get("result")

    if result == "GANADA":

        row["return_amount"] = round(
            potential_return,
            2,
        )

        row["profit_loss"] = round(
            potential_profit,
            2,
        )

    elif result == "PERDIDA":

        row["return_amount"] = 0.0
        row["profit_loss"] = -100.0

    elif result == "EMPATE":

        row["return_amount"] = 100.0
        row["profit_loss"] = 0.0


def _apply_kalshi_quote(
    row: dict[str, Any],
    *,
    historical: bool,
) -> bool:

    existing = _float(
        row.get("kalshi_price")
    )

    if (
        existing is not None
        and 0 < existing < 1
    ):

        _apply_financials(
            row
        )

        return True

    created_at = (
        row.get("created_at")
        if historical
        else None
    )

    quote = find_kalshi_quote(
        selection=str(
            row.get("selection")
            or ""
        ),
        matchup=str(
            row.get("matchup")
            or ""
        ),
        market=str(
            row.get("market")
            or ""
        ),
        sport=str(
            row.get("sport")
            or ""
        ),
        game_start=row.get(
            "start"
        ),
        at_time=created_at,
    )

    if not quote:

        _apply_financials(
            row
        )

        return False

    price = _float(
        quote.get("price")
    )

    if (
        price is None
        or price <= 0
        or price >= 1
    ):
        return False

    row["kalshi_ticker"] = (
        quote.get("ticker")
    )

    row["kalshi_event_ticker"] = (
        quote.get("event_ticker")
    )

    row["kalshi_side"] = (
        quote.get("side")
    )

    row["kalshi_price"] = round(
        price,
        6,
    )

    row["kalshi_percent"] = round(
        price * 100.0,
        4,
    )

    row["kalshi_price_source"] = (
        quote.get("price_source")
    )

    row["kalshi_price_time"] = (
        quote.get("price_time")
    )

    row["kalshi_market_status"] = (
        quote.get("market_status")
    )

    row["bookmaker"] = "Kalshi"

    row["odds_source"] = (
        "KALSHI_HISTORICAL"
        if historical
        else "KALSHI_LIVE"
    )

    row["odds"] = round(
        1.0 / price,
        4,
    )

    row["decimal_odds"] = round(
        1.0 / price,
        4,
    )

    _apply_financials(
        row
    )

    return True


def _resolve_full_game(
    row: dict[str, Any],
    game: Game,
    generated_at: datetime,
) -> None:

    if not is_finished(
        game.status
    ):
        return

    home_score = score_for_side(
        game.raw,
        "home",
    )

    away_score = score_for_side(
        game.raw,
        "away",
    )

    if (
        home_score is None
        or away_score is None
    ):
        return

    row["final_score"] = (
        f"{game.away.name} "
        f"{away_score:g} - "
        f"{game.home.name} "
        f"{home_score:g}"
    )

    if home_score == away_score:

        row["winner"] = None
        row["result"] = "EMPATE"

    else:

        winner = (
            game.home.name
            if home_score > away_score
            else game.away.name
        )

        row["winner"] = winner

        row["result"] = (
            "GANADA"
            if winner
            == row.get("selection")
            else "PERDIDA"
        )

    row["status"] = "RESUELTA"

    if not row.get("resolved_at"):
        row["resolved_at"] = (
            generated_at.isoformat()
        )

    _apply_financials(
        row
    )


def _resolve_first_five(
    row: dict[str, Any],
    game: Game,
    generated_at: datetime,
) -> None:

    if not is_finished(
        game.status
    ):
        return

    date_iso = _game_date(
        game
    )

    if not date_iso:
        return

    mlb_game = _MLB._find_game(
        game.home.name,
        game.away.name,
        date_iso,
    )

    if not mlb_game:
        return

    game_pk = mlb_game.get(
        "gamePk"
    )

    if not game_pk:
        return

    feed = _MLB._get(
        f"game/{game_pk}/feed/live",
        live=True,
    )

    innings = (
        feed.get(
            "liveData",
            {},
        )
        .get(
            "linescore",
            {},
        )
        .get(
            "innings",
            [],
        )
    )

    if len(innings) < 5:
        return

    home_score = 0.0
    away_score = 0.0

    for inning in innings[:5]:

        home_runs = _float(
            (
                inning.get("home")
                or {}
            ).get("runs")
        )

        away_runs = _float(
            (
                inning.get("away")
                or {}
            ).get("runs")
        )

        home_score += (
            home_runs
            if home_runs is not None
            else 0.0
        )

        away_score += (
            away_runs
            if away_runs is not None
            else 0.0
        )

    row["final_score"] = (
        f"F5: "
        f"{game.away.name} "
        f"{away_score:g} - "
        f"{game.home.name} "
        f"{home_score:g}"
    )

    if home_score == away_score:

        row["winner"] = None
        row["result"] = "EMPATE"

    else:

        winner = (
            game.home.name
            if home_score > away_score
            else game.away.name
        )

        row["winner"] = winner

        row["result"] = (
            "GANADA"
            if winner
            == row.get("selection")
            else "PERDIDA"
        )

    row["status"] = "RESUELTA"

    if not row.get("resolved_at"):
        row["resolved_at"] = (
            generated_at.isoformat()
        )

    _apply_financials(
        row
    )


def _new_row(
    candidate: Candidate,
    pick_number: int,
    generated_at: datetime,
) -> dict[str, Any]:

    row: dict[str, Any] = {

        "key": (
            f"{candidate.sport}|"
            f"{candidate.game_id}|"
            f"{candidate.market}|"
            f"{candidate.selection}"
        ),

        "pick_number": pick_number,

        "created_at": (
            generated_at.isoformat()
        ),

        "sport": candidate.sport,
        "game_id": candidate.game_id,
        "matchup": candidate.matchup,
        "start": candidate.start,
        "market": candidate.market,
        "selection": candidate.selection,

        "probability": (
            candidate.model_probability
        ),

        "edge": candidate.edge,

        "expected_value": (
            candidate.expected_value
        ),

        "data_quality": (
            candidate.data_quality
        ),

        "bookmaker": "Kalshi",

        "odds_source": "KALSHI_PENDING",

        "kalshi_ticker": None,
        "kalshi_event_ticker": None,
        "kalshi_side": None,
        "kalshi_price": None,
        "kalshi_percent": None,
        "kalshi_price_source": None,
        "kalshi_price_time": None,
        "kalshi_market_status": None,

        "odds": None,
        "decimal_odds": None,

        "financial_tracking": False,

        "stake": None,
        "contracts": None,
        "potential_return": None,
        "potential_profit": None,

        "status": "PENDIENTE",
        "result": None,
        "winner": None,
        "final_score": None,

        "return_amount": None,
        "profit_loss": None,
    }

    _apply_kalshi_quote(
        row,
        historical=False,
    )

    return row


def _normalise_old_row(
    row: dict[str, Any],
) -> None:

    if row.get(
        "kalshi_price"
    ) is not None:

        _apply_financials(
            row
        )

        return

    if row.get(
        "bookmaker"
    ) != "Kalshi":

        row["kalshi_ticker"] = (
            row.get("kalshi_ticker")
        )

        row["kalshi_side"] = (
            row.get("kalshi_side")
        )

        row["kalshi_price"] = (
            row.get("kalshi_price")
        )

        row["kalshi_percent"] = (
            row.get("kalshi_percent")
        )

    _apply_financials(
        row
    )


def _find_game_for_row(
    row: dict[str, Any],
    games: list[Game],
    game_map: dict[str, Game],
) -> Game | None:
    """
    Primero intenta por game_id.
    Si el ID no coincide, intenta recuperar
    el partido usando ambos equipos del matchup.
    """

    game = game_map.get(
        str(
            row.get("game_id")
        )
    )

    if game is not None:
        return game

    matchup = str(
        row.get("matchup")
        or ""
    ).lower().strip()

    if not matchup:
        return None

    for candidate_game in games:

        home = str(
            candidate_game.home.name
            or ""
        ).lower().strip()

        away = str(
            candidate_game.away.name
            or ""
        ).lower().strip()

        if (
            home
            and away
            and home in matchup
            and away in matchup
        ):

            print(
                "MATCH FALLBACK | "
                f"{row.get('matchup')} | "
                f"game_id historial={row.get('game_id')} | "
                f"game_id API={candidate_game.id}"
            )

            return candidate_game

    return None


def update_history(
    path: Path,
    sport: str,
    games: list[Game],
    recommendations:
        list[Candidate]
        | Candidate
        | None,
    generated_at: datetime,
) -> list[dict[str, Any]]:

    rows = load_history(
        path
    )

    # ====================================
    # 1. NORMALIZAR TODO EL HISTORIAL
    # ====================================

    for row in rows:
        _normalise_old_row(
            row
        )

    # ====================================
    # 2. RECUPERAR KALSHI EN FILAS VIEJAS
    # ====================================

    for row in rows:

        if row.get(
            "sport"
        ) != sport:
            continue

        existing_price = _float(
            row.get("kalshi_price")
        )

        if (
            existing_price is not None
            and 0 < existing_price < 1
        ):
            continue

        _apply_kalshi_quote(
            row,
            historical=True,
        )

    # ====================================
    # 3. RESOLVER PARTIDOS
    # ====================================

    game_map = {
        str(game.id): game
        for game in games
    }

    for row in rows:

        if row.get(
            "sport"
        ) != sport:
            continue

        # No volver a resolver operaciones
        # que ya tienen resultado.
        if row.get("result") in {
            "GANADA",
            "PERDIDA",
            "EMPATE",
        }:
            continue

        game = _find_game_for_row(
            row,
            games,
            game_map,
        )

        if game is None:

            print(
                "SIN MATCH | "
                f"{row.get('sport')} | "
                f"{row.get('matchup')} | "
                f"game_id={row.get('game_id')}"
            )

            continue

        market = row.get(
            "market"
        )

        if market == (
            "Ganador del partido"
        ):

            _resolve_full_game(
                row,
                game,
                generated_at,
            )

        elif market == (
            "Primeras 5 entradas"
        ):

            _resolve_first_five(
                row,
                game,
                generated_at,
            )

        else:

            print(
                "MERCADO NO RECONOCIDO | "
                f"{market}"
            )

    # ====================================
    # 4. CONVERTIR RECOMENDACIONES A LISTA
    # ====================================

    if recommendations is None:

        recommendation_list: list[
            Candidate
        ] = []

    elif isinstance(
        recommendations,
        Candidate,
    ):

        recommendation_list = [
            recommendations
        ]

    else:

        recommendation_list = list(
            recommendations
        )

    # ====================================
    # 5. GUARDAR APUESTA #1 Y #2
    # ====================================

    existing_by_key = {
        str(row.get("key")): row
        for row in rows
        if row.get("key")
    }

    for (
        pick_number,
        candidate,
    ) in enumerate(
        recommendation_list[:2],
        start=1,
    ):

        key = (
            f"{sport}|"
            f"{candidate.game_id}|"
            f"{candidate.market}|"
            f"{candidate.selection}"
        )

        existing = (
            existing_by_key.get(
                key
            )
        )

        if existing is None:

            row = _new_row(
                candidate,
                pick_number,
                generated_at,
            )

            rows.append(
                row
            )

            existing_by_key[
                key
            ] = row

        else:

            existing[
                "pick_number"
            ] = (
                existing.get(
                    "pick_number"
                )
                or pick_number
            )

            existing_price = _float(
                existing.get(
                    "kalshi_price"
                )
            )

            if not (
                existing_price is not None
                and 0 < existing_price < 1
            ):

                _apply_kalshi_quote(
                    existing,
                    historical=False,
                )

    # ====================================
    # 6. RECALCULAR TODO
    # ====================================

    for row in rows:
        _apply_financials(
            row
        )

    save_history(
        path,
        rows,
    )

    return rows


def history_summary(
    rows: list[dict[str, Any]],
) -> dict[str, int | float]:

    won = sum(
        row.get("result")
        == "GANADA"
        for row in rows
    )

    lost = sum(
        row.get("result")
        == "PERDIDA"
        for row in rows
    )

    tied = sum(
        row.get("result")
        == "EMPATE"
        for row in rows
    )

    pending = sum(
        str(
            row.get("status")
            or ""
        ).upper()
        in {
            "PENDIENTE",
            "PENDING",
        }
        for row in rows
    )

    decisions = (
        won + lost
    )

    tracked = [
        row
        for row in rows
        if (
            row.get(
                "financial_tracking"
            )
            and row.get(
                "profit_loss"
            ) is not None
        )
    ]

    total_staked = sum(
        100.0
        for row in tracked
        if row.get("result")
        in {
            "GANADA",
            "PERDIDA",
        }
    )

    total_profit_loss = sum(
        float(
            row.get(
                "profit_loss"
            )
            or 0.0
        )
        for row in tracked
    )

    roi = (
        total_profit_loss
        / total_staked
        if total_staked > 0
        else 0.0
    )

    return {

        "total": len(rows),

        "resolved": (
            won
            + lost
            + tied
        ),

        "won": won,

        "lost": lost,

        "ties": tied,

        "pending": pending,

        "win_rate": (
            won / decisions
            if decisions
            else 0.0
        ),

        "financial_operations": (
            len(tracked)
        ),

        "total_staked": round(
            total_staked,
            2,
        ),

        "profit_loss": round(
            total_profit_loss,
            2,
        ),

        "roi": round(
            roi,
            6,
        ),
          }
