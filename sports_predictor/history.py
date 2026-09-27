from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import Candidate, Game, is_finished, score_for_side


DEFAULT_STAKE = 100.0


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
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


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _financial_update(row: dict[str, Any]) -> None:
    """
    Recalcula SIEMPRE los datos financieros cuando existe
    una cuota decimal real.
    """

    odds = _as_float(
        row.get("decimal_odds")
        if row.get("decimal_odds") is not None
        else row.get("odds")
    )

    if odds is None or odds <= 1.0:
        row["odds"] = None
        row["decimal_odds"] = None
        row["financial_tracking"] = False

        row["stake"] = None
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

    odds = round(odds, 4)

    row["odds"] = odds
    row["decimal_odds"] = odds
    row["financial_tracking"] = True

    stake = _as_float(row.get("stake"))

    if stake is None or stake <= 0:
        stake = DEFAULT_STAKE

    row["stake"] = round(stake, 2)

    potential_return = stake * odds
    potential_profit = potential_return - stake

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
        row["profit_loss"] = round(
            -stake,
            2,
        )

    elif result == "EMPATE":
        row["return_amount"] = round(
            stake,
            2,
        )

        row["profit_loss"] = 0.0


def _normalise_old_row(row: dict[str, Any]) -> None:
    """
    Normaliza TODAS las filas antiguas del historial.
    """

    if (
        row.get("decimal_odds") is None
        and row.get("odds") is not None
    ):
        row["decimal_odds"] = row.get("odds")

    if (
        row.get("odds") is None
        and row.get("decimal_odds") is not None
    ):
        row["odds"] = row.get("decimal_odds")

    if not row.get("bookmaker"):
        if row.get("odds") is None:
            row["bookmaker"] = (
                "SIN CUOTAS — MODELO MLB"
            )
        else:
            row["bookmaker"] = "Historical"

    if not row.get("odds_source"):
        if row.get("odds") is None:
            row["odds_source"] = "SIN_CUOTA"
        elif row.get("market") == (
            "Primeras 5 entradas"
        ):
            row["odds_source"] = "HISTORICAL_F5"
        else:
            row["odds_source"] = (
                "HISTORICAL_FULL_GAME"
            )

    _financial_update(row)


def _resolve_full_game(
    row: dict[str, Any],
    game: Game,
    generated_at: datetime,
) -> None:

    if not is_finished(game.status):
        return

    home_score = score_for_side(
        game.raw,
        "home",
    )

    away_score = score_for_side(
        game.raw,
        "away",
    )

    if home_score is None or away_score is None:
        return

    row["final_score"] = (
        f"{game.away.name} {away_score:g} - "
        f"{game.home.name} {home_score:g}"
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
            if winner == row.get("selection")
            else "PERDIDA"
        )

    row["status"] = "RESUELTA"

    if not row.get("resolved_at"):
        row["resolved_at"] = (
            generated_at.isoformat()
        )

    _financial_update(row)


def _candidate_to_row(
    candidate: Candidate,
    pick_number: int,
    generated_at: datetime,
) -> dict[str, Any]:

    odds = _as_float(
        candidate.decimal_odds
    )

    row: dict[str, Any] = {
        "key": (
            f"{candidate.sport}|"
            f"{candidate.game_id}|"
            f"{candidate.market}|"
            f"{candidate.selection}"
        ),
        "pick_number": pick_number,
        "created_at": generated_at.isoformat(),
        "sport": candidate.sport,
        "game_id": candidate.game_id,
        "matchup": candidate.matchup,
        "start": candidate.start,
        "market": candidate.market,
        "selection": candidate.selection,
        "probability": (
            candidate.model_probability
        ),
        "odds": odds,
        "decimal_odds": odds,
        "bookmaker": (
            candidate.bookmaker
            if odds is not None
            else "SIN CUOTAS — MODELO MLB"
        ),
        "odds_source": (
            "LIVE_F5"
            if (
                odds is not None
                and candidate.market
                == "Primeras 5 entradas"
            )
            else (
                "LIVE_FULL_GAME"
                if odds is not None
                else "SIN_CUOTA"
            )
        ),
        "financial_tracking": (
            odds is not None
        ),
        "stake": (
            DEFAULT_STAKE
            if odds is not None
            else None
        ),
        "potential_return": None,
        "potential_profit": None,
        "edge": candidate.edge,
        "expected_value": (
            candidate.expected_value
        ),
        "data_quality": (
            candidate.data_quality
        ),
        "status": "PENDIENTE",
        "result": None,
        "winner": None,
        "final_score": None,
        "return_amount": None,
        "profit_loss": None,
    }

    _financial_update(row)

    return row


def _update_existing_from_candidate(
    row: dict[str, Any],
    candidate: Candidate,
    pick_number: int,
) -> None:
    """
    Si una fila ya existe pero antes quedó sin cuota,
    aprovecha la información actual del Candidate para
    completar los datos faltantes.
    """

    row["pick_number"] = (
        row.get("pick_number")
        or pick_number
    )

    if row.get("start") is None:
        row["start"] = candidate.start

    if row.get("probability") is None:
        row["probability"] = (
            candidate.model_probability
        )

    odds = _as_float(
        candidate.decimal_odds
    )

    if (
        row.get("odds") is None
        and odds is not None
    ):
        row["odds"] = odds
        row["decimal_odds"] = odds
        row["bookmaker"] = (
            candidate.bookmaker
        )

        if candidate.market == (
            "Primeras 5 entradas"
        ):
            row["odds_source"] = "LIVE_F5"
        else:
            row["odds_source"] = (
                "LIVE_FULL_GAME"
            )

    row["edge"] = (
        row.get("edge")
        if row.get("edge") is not None
        else candidate.edge
    )

    row["expected_value"] = (
        row.get("expected_value")
        if row.get("expected_value")
        is not None
        else candidate.expected_value
    )

    row["data_quality"] = (
        row.get("data_quality")
        if row.get("data_quality")
        is not None
        else candidate.data_quality
    )

    _financial_update(row)


def update_history(
    path: Path,
    sport: str,
    games: list[Game],
    recommendations: list[Candidate]
    | Candidate
    | None,
    generated_at: datetime,
) -> list[dict[str, Any]]:

    rows = load_history(path)

    # -------------------------------------
    # 1. NORMALIZAR TODO EL HISTORIAL VIEJO
    # -------------------------------------

    for row in rows:
        _normalise_old_row(row)

    # -------------------------------------
    # 2. MAPA DE PARTIDOS DISPONIBLES
    # -------------------------------------

    game_map = {
        str(game.id): game
        for game in games
    }

    # -------------------------------------
    # 3. ACTUALIZAR RESULTADOS
    # -------------------------------------

    for row in rows:

        if row.get("sport") != sport:
            continue

        game = game_map.get(
            str(row.get("game_id"))
        )

        if game is None:
            continue

        market = row.get("market")

        if market == "Ganador del partido":
            _resolve_full_game(
                row,
                game,
                generated_at,
            )

        # Los resultados F5 que ya fueron
        # resueltos previamente se conservan.
        #
        # No se reemplaza un F5 con el marcador
        # FINAL del partido porque eso sería
        # incorrecto.
        elif market == "Primeras 5 entradas":
            if row.get("result") in {
                "GANADA",
                "PERDIDA",
                "EMPATE",
            }:
                row["status"] = "RESUELTA"
                _financial_update(row)

    # -------------------------------------
    # 4. CONVERTIR recommendation -> lista
    # -------------------------------------

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

    # -------------------------------------
    # 5. GUARDAR / ACTUALIZAR PICKS #1 Y #2
    # -------------------------------------

    row_by_key = {
        str(row.get("key")): row
        for row in rows
        if row.get("key")
    }

    for pick_number, candidate in enumerate(
        recommendation_list[:2],
        start=1,
    ):

        key = (
            f"{sport}|"
            f"{candidate.game_id}|"
            f"{candidate.market}|"
            f"{candidate.selection}"
        )

        existing = row_by_key.get(key)

        if existing is not None:
            _update_existing_from_candidate(
                existing,
                candidate,
                pick_number,
            )

        else:
            new_row = _candidate_to_row(
                candidate,
                pick_number,
                generated_at,
            )

            rows.append(new_row)
            row_by_key[key] = new_row

    # -------------------------------------
    # 6. ÚLTIMO RECÁLCULO FINANCIERO GLOBAL
    # -------------------------------------

    for row in rows:
        _financial_update(row)

    save_history(
        path,
        rows,
    )

    return rows


def history_summary(
    rows: list[dict[str, Any]],
) -> dict[str, int | float]:

    won = sum(
        row.get("result") == "GANADA"
        for row in rows
    )

    lost = sum(
        row.get("result") == "PERDIDA"
        for row in rows
    )

    tied = sum(
        row.get("result") == "EMPATE"
        for row in rows
    )

    pending = sum(
        row.get("status") == "PENDIENTE"
        for row in rows
    )

    resolved_decisions = won + lost

    tracked = [
        row
        for row in rows
        if (
            row.get("financial_tracking")
            and row.get("profit_loss")
            is not None
        )
    ]

    total_staked = sum(
        float(row.get("stake") or 0.0)
        for row in tracked
        if row.get("result")
        in {"GANADA", "PERDIDA"}
    )

    total_profit_loss = sum(
        float(
            row.get("profit_loss")
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
            won + lost + tied
        ),
        "won": won,
        "lost": lost,
        "ties": tied,
        "pending": pending,
        "win_rate": (
            won / resolved_decisions
            if resolved_decisions
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
