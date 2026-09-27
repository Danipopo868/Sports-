from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import Candidate, Game, is_finished, score_for_side


DEFAULT_STAKE = 100.0


def _starting_balance() -> float:
    try:
        return float(os.environ.get("SPORTS_STARTING_BALANCE", "0"))
    except (TypeError, ValueError):
        return 0.0


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
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


def _normalize_name(value: Any) -> str:
    plain = (
        unicodedata.normalize(
            "NFKD",
            str(value or ""),
        )
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )

    return re.sub(
        r"[^a-z0-9]+",
        "",
        plain,
    )


def _matchup_teams(
    row: dict[str, Any],
) -> tuple[str, str] | None:
    matchup = str(
        row.get("matchup") or ""
    ).strip()

    if "@" not in matchup:
        return None

    away_raw, home_raw = matchup.split(
        "@",
        1,
    )

    away = _normalize_name(
        away_raw
    )

    home = _normalize_name(
        home_raw
    )

    if not away or not home:
        return None

    return away, home


def _timestamp(
    value: Any,
) -> float | None:
    text = str(
        value or ""
    ).strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        ).timestamp()

    except (
        TypeError,
        ValueError,
    ):
        return None


def _number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return float(value)

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    if isinstance(
        value,
        dict,
    ):
        for key in (
            "runs",
            "total",
            "score",
            "points",
            "value",
        ):
            if key not in value:
                continue

            found = _number(
                value.get(key)
            )

            if found is not None:
                return found

        return None

    if isinstance(
        value,
        (list, tuple),
    ):
        for item in value:

            found = _number(
                item
            )

            if found is not None:
                return found

        return None

    try:
        return float(
            str(value).strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _valid_kalshi_percent(
    value: Any,
) -> float | None:

    if value is None:
        return None

    text = (
        str(value)
        .strip()
        .replace("%", "")
    )

    try:
        percent = float(text)

    except (
        TypeError,
        ValueError,
    ):
        return None

    # Permite que el workflow entregue:
    # 61
    # o
    # 0.61
    if 0 < percent < 1:
        percent *= 100.0

    if not (
        0 < percent < 100
    ):
        return None

    return percent


def _find_game(
    row: dict[str, Any],
    games: list[Game],
    game_map: dict[str, Game],
) -> Game | None:

    game_id = str(
        row.get("game_id") or ""
    )

    if (
        game_id
        and game_id in game_map
    ):
        return game_map[game_id]

    matchup = _matchup_teams(
        row
    )

    if matchup is None:
        return None

    expected_away, expected_home = matchup

    candidates = [
        game
        for game in games
        if (
            _normalize_name(
                game.away.name
            )
            == expected_away
            and
            _normalize_name(
                game.home.name
            )
            == expected_home
        )
    ]

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    row_start = _timestamp(
        row.get("start")
    )

    if row_start is None:
        return None

    timed: list[
        tuple[float, Game]
    ] = []

    for game in candidates:

        game_start = _timestamp(
            game.start
        )

        if game_start is None:
            continue

        timed.append(
            (
                abs(
                    game_start
                    - row_start
                ),
                game,
            )
        )

    if not timed:
        return None

    timed.sort(
        key=lambda item: item[0]
    )

    return timed[0][1]


def _first_five_score(
    raw: dict[str, Any],
) -> tuple[float, float] | None:

    inning_sources: list[
        list[Any]
    ] = []

    primary = raw.get(
        "innings"
    )

    if isinstance(
        primary,
        list,
    ):
        inning_sources.append(
            primary
        )

    mlb_raw = (
        raw.get("_mlb_raw")
        or {}
    )

    if isinstance(
        mlb_raw,
        dict,
    ):

        linescore = (
            mlb_raw.get(
                "linescore"
            )
            or {}
        )

        if isinstance(
            linescore,
            dict,
        ):

            innings = (
                linescore.get(
                    "innings"
                )
                or []
            )

            if isinstance(
                innings,
                list,
            ):
                inning_sources.append(
                    innings
                )

    if not inning_sources:
        return None

    inning_map: dict[
        int,
        tuple[float, float],
    ] = {}

    for innings in inning_sources:

        for inning in innings:

            if not isinstance(
                inning,
                dict,
            ):
                continue

            num_raw = inning.get(
                "num",
                inning.get(
                    "inning"
                ),
            )

            try:
                number = int(
                    num_raw
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                number < 1
                or number > 5
            ):
                continue

            away_runs = _number(
                inning.get(
                    "away"
                )
            )

            home_runs = _number(
                inning.get(
                    "home"
                )
            )

            if (
                away_runs is None
                or home_runs is None
            ):
                continue

            inning_map[number] = (
                float(away_runs),
                float(home_runs),
            )

    if any(
        number not in inning_map
        for number in range(
            1,
            6,
        )
    ):
        return None

    away_total = sum(
        inning_map[n][0]
        for n in range(
            1,
            6,
        )
    )

    home_total = sum(
        inning_map[n][1]
        for n in range(
            1,
            6,
        )
    )

    return (
        home_total,
        away_total,
    )


def _selection_matches(
    selection: Any,
    winner: str,
) -> bool:

    return (
        _normalize_name(
            selection
        )
        ==
        _normalize_name(
            winner
        )
    )
    # ============================================================
# FINANZAS KALSHI
# ============================================================

def _set_potential_money(
    row: dict[str, Any],
) -> None:

    percent = _valid_kalshi_percent(
        row.get(
            "kalshi_percent"
        )
    )

    try:
        stake = float(
            row.get(
                "stake"
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        stake = 0.0

    if (
        percent is None
        or stake <= 0
    ):
        row[
            "potential_return"
        ] = None

        row[
            "potential_profit"
        ] = None

        return

    price_decimal = (
        percent / 100.0
    )

    total_return = (
        stake
        / price_decimal
    )

    row[
        "potential_return"
    ] = round(
        total_return,
        2,
    )

    row[
        "potential_profit"
    ] = round(
        total_return
        - stake,
        2,
    )


def _calculate_money(
    row: dict[str, Any],
    result: str,
) -> None:

    percent = _valid_kalshi_percent(
        row.get(
            "kalshi_percent"
        )
    )

    try:
        stake = float(
            row.get(
                "stake"
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        stake = 0.0

    if (
        percent is None
        or stake <= 0
    ):

        row[
            "return_amount"
        ] = None

        row[
            "profit_loss"
        ] = None

        return

    row["stake"] = round(
        stake,
        2,
    )

    row[
        "kalshi_percent"
    ] = round(
        percent,
        6,
    )

    _set_potential_money(
        row
    )

    if result == "GANADA":

        price_decimal = (
            percent
            / 100.0
        )

        return_amount = (
            stake
            / price_decimal
        )

        profit_loss = (
            return_amount
            - stake
        )

    elif result == "PERDIDA":

        return_amount = 0.0

        profit_loss = (
            -stake
        )

    elif result == "EMPATE":

        return_amount = stake

        profit_loss = 0.0

    else:
        return

    row[
        "return_amount"
    ] = round(
        return_amount,
        2,
    )

    row[
        "profit_loss"
    ] = round(
        profit_loss,
        2,
    )


def _resolve_row(
    row: dict[str, Any],
    *,
    result: str,
    winner: str | None,
    final_score: str,
    generated_at: datetime,
) -> None:

    row[
        "winner"
    ] = winner

    row[
        "final_score"
    ] = final_score

    row[
        "result"
    ] = result

    row[
        "status"
    ] = "RESUELTA"

    row[
        "resolved_at"
    ] = generated_at.isoformat()

    _calculate_money(
        row,
        result,
    )


# ============================================================
# ACTUALIZAR HISTORIAL
# ============================================================

def update_history(
    path: Path,
    sport: str,
    games: list[Game],
    recommendations: list[Candidate],
    generated_at: datetime,
) -> list[dict[str, Any]]:

    rows = load_history(
        path
    )

    game_map = {
        str(game.id): game
        for game in games
    }

    # ========================================================
    # RESOLVER PICKS PENDIENTES
    # ========================================================

    for row in rows:

        if (
            str(
                row.get(
                    "sport"
                )
                or ""
            ).upper()
            !=
            sport.upper()
        ):
            continue

        if (
            str(
                row.get(
                    "status"
                )
                or ""
            ).upper()
            != "PENDIENTE"
        ):
            continue

        market = str(
            row.get(
                "market"
            )
            or ""
        ).strip()

        if market not in {
            "Ganador del partido",
            "Primeras 5 entradas",
        }:
            continue

        game = _find_game(
            row,
            games,
            game_map,
        )

        if game is None:
            continue

        # ====================================================
        # GANADOR DEL PARTIDO
        # ====================================================

        if (
            market
            == "Ganador del partido"
        ):

            if not is_finished(
                game.status
            ):
                continue

            home_score = _number(
                score_for_side(
                    game.raw,
                    "home",
                )
            )

            away_score = _number(
                score_for_side(
                    game.raw,
                    "away",
                )
            )

            if (
                home_score is None
                or away_score is None
            ):
                continue

            score_text = (
                f"{game.away.name} "
                f"{away_score:g} - "
                f"{game.home.name} "
                f"{home_score:g}"
            )

            if (
                home_score
                == away_score
            ):

                _resolve_row(
                    row,
                    result="EMPATE",
                    winner=None,
                    final_score=score_text,
                    generated_at=generated_at,
                )

                continue

            winner = (
                game.home.name
                if (
                    home_score
                    > away_score
                )
                else
                game.away.name
            )

            result = (
                "GANADA"
                if _selection_matches(
                    row.get(
                        "selection"
                    ),
                    winner,
                )
                else
                "PERDIDA"
            )

            _resolve_row(
                row,
                result=result,
                winner=winner,
                final_score=score_text,
                generated_at=generated_at,
            )

            continue

        # ====================================================
        # PRIMERAS 5 ENTRADAS
        # ====================================================

        first_five = (
            _first_five_score(
                game.raw
            )
        )

        if first_five is None:
            continue

        home_f5, away_f5 = (
            first_five
        )

        score_text = (
            f"{game.away.name} "
            f"{away_f5:g} - "
            f"{game.home.name} "
            f"{home_f5:g} "
            "(F5)"
        )

        if (
            home_f5
            == away_f5
        ):

            _resolve_row(
                row,
                result="EMPATE",
                winner=None,
                final_score=score_text,
                generated_at=generated_at,
            )

            continue

        winner = (
            game.home.name
            if (
                home_f5
                > away_f5
            )
            else
            game.away.name
        )

        result = (
            "GANADA"
            if _selection_matches(
                row.get(
                    "selection"
                ),
                winner,
            )
            else
            "PERDIDA"
        )

        _resolve_row(
            row,
            result=result,
            winner=winner,
            final_score=score_text,
            generated_at=generated_at,
        )

    # ========================================================
    # GUARDAR NUEVAS RECOMENDACIONES
    # ========================================================

    for (
        pick_number,
        recommendation,
    ) in enumerate(
        recommendations[:2],
        start=1,
    ):

        key = (
            f"{sport}|"
            f"{recommendation.game_id}|"
            f"{recommendation.market}|"
            f"{recommendation.selection}"
        )

        if any(
            row.get("key")
            == key
            for row in rows
        ):
            continue

        kalshi_percent = (
            _valid_kalshi_percent(
                getattr(
                    recommendation,
                    "kalshi_percent",
                    None,
                )
            )
        )

        financial_tracking = (
            kalshi_percent
            is not None
        )

        stake = (
            DEFAULT_STAKE
            if financial_tracking
            else None
        )

        if financial_tracking:

            price_decimal = (
                kalshi_percent
                / 100.0
            )

            potential_return = round(
                DEFAULT_STAKE
                / price_decimal,
                2,
            )

            potential_profit = round(
                potential_return
                - DEFAULT_STAKE,
                2,
            )

        else:

            potential_return = None
            potential_profit = None

        rows.append(
            {
                "key": key,

                "pick_number": (
                    pick_number
                ),

                "created_at": (
                    generated_at.isoformat()
                ),

                "sport": sport,

                "game_id": (
                    recommendation.game_id
                ),

                "matchup": (
                    recommendation.matchup
                ),

                "start": (
                    recommendation.start
                ),

                "market": (
                    recommendation.market
                ),

                "selection": (
                    recommendation.selection
                ),

                # MODELO
                "probability": (
                    recommendation.model_probability
                ),

                "edge": (
                    recommendation.edge
                ),

                "expected_value": (
                    recommendation.expected_value
                ),

                "data_quality": (
                    recommendation.data_quality
                ),

                # COMPATIBILIDAD CON TU APP ACTUAL
                "odds": getattr(
                    recommendation,
                    "decimal_odds",
                    None,
                ),

                "bookmaker": getattr(
                    recommendation,
                    "bookmaker",
                    None,
                ),

                # KALSHI
                "kalshi_percent": (
                    kalshi_percent
                ),

                "kalshi_source": (
                    "REAL"
                    if financial_tracking
                    else "SIN_KALSHI"
                ),

                "financial_tracking": (
                    financial_tracking
                ),

                # STAKE FIJO
                "stake": (
                    stake
                ),

                "potential_return": (
                    potential_return
                ),

                "potential_profit": (
                    potential_profit
                ),

                # RESULTADO
                "status": "PENDIENTE",

                "result": None,

                "winner": None,

                "final_score": None,

                "return_amount": None,

                "profit_loss": None,
            }
        )

    save_history(
        path,
        rows,
    )

    return rows
    # ============================================================
# COMPROBAR SI UNA FILA TIENE DINERO CALCULABLE
# ============================================================

def has_financial_data(
    row: dict[str, Any],
) -> bool:

    percent = _valid_kalshi_percent(
        row.get(
            "kalshi_percent"
        )
    )

    try:
        stake = float(
            row.get(
                "stake"
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return False

    return (
        percent is not None
        and stake > 0
    )


# ============================================================
# RESUMEN
# ============================================================

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

    resolved = (
        won
        + lost
        + tied
    )

    pending = sum(
        str(
            row.get(
                "status"
            )
            or ""
        ).upper()
        == "PENDIENTE"
        for row in rows
    )

    decisions = (
        won
        + lost
    )

    win_rate = (
        won / decisions
        if decisions
        else 0.0
    )

    # SOLO filas que tienen:
    # resultado + porcentaje Kalshi + stake
    financial_rows = [
        row
        for row in rows
        if (
            row.get("result")
            in {
                "GANADA",
                "PERDIDA",
                "EMPATE",
            }
            and has_financial_data(
                row
            )
        )
    ]

    total_staked = 0.0

    total_profit_loss = 0.0

    for row in financial_rows:

        try:
            stake = float(
                row.get(
                    "stake"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        total_staked += stake

        profit_loss = row.get(
            "profit_loss"
        )

        if profit_loss is None:

            temporary = dict(
                row
            )

            _calculate_money(
                temporary,
                str(
                    row.get(
                        "result"
                    )
                ),
            )

            profit_loss = (
                temporary.get(
                    "profit_loss"
                )
            )

        try:
            if profit_loss is not None:

                total_profit_loss += float(
                    profit_loss
                )

        except (
            TypeError,
            ValueError,
        ):
            pass

    roi = (
        total_profit_loss
        / total_staked
        if total_staked
        else 0.0
    )

    starting_balance = (
        _starting_balance()
    )

    current_balance = (
        starting_balance
        + total_profit_loss
    )

    exact_kalshi = sum(
        str(
            row.get(
                "kalshi_source"
            )
            or ""
        ).upper()
        == "REAL"
        for row in financial_rows
    )

    return {
        "total": len(
            rows
        ),

        "resolved": (
            resolved
        ),

        "won": (
            won
        ),

        "lost": (
            lost
        ),

        "tied": (
            tied
        ),

        "pending": (
            pending
        ),

        "win_rate": (
            win_rate
        ),

        "financial_bets": len(
            financial_rows
        ),

        "exact_kalshi": (
            exact_kalshi
        ),

        "total_staked": round(
            total_staked,
            2,
        ),

        "profit_loss": round(
            total_profit_loss,
            2,
        ),

        "roi": (
            roi
        ),

        "starting_balance": round(
            starting_balance,
            2,
        ),

        "current_balance": round(
            current_balance,
            2,
        ),
    }
