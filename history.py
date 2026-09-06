from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# CARGAR HISTORIAL
# ============================================================

def load_history(
    path: str | Path,
) -> list[dict[str, Any]]:

    path = Path(path)

    if not path.exists():
        return []

    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


# ============================================================
# GUARDAR HISTORIAL
# ============================================================

def save_history(
    path: str | Path,
    rows: list[dict[str, Any]],
) -> None:

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = path.with_suffix(
        path.suffix + ".tmp"
    )

    temp.write_text(
        json.dumps(
            rows,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    os.replace(
        temp,
        path,
    )


# ============================================================
# ID ÚNICO DE PREDICCIÓN
# ============================================================

def prediction_id(
    sport: str,
    game_id: str,
    market: str,
    selection: str,
) -> str:

    return (
        f"{sport}|"
        f"{game_id}|"
        f"{market}|"
        f"{selection}"
    )


# ============================================================
# ACTUALIZAR HISTORIAL
# ============================================================

def update_history(
    path: str | Path,
    sport: str,
    games: list[Any],
    recommendation: Any | None,
    now: datetime,
) -> list[dict[str, Any]]:

    rows = load_history(
        path
    )

    # ========================================================
    # 1. GUARDAR NUEVA PREDICCIÓN
    # ========================================================

    if recommendation is not None:

        game_id = str(
            getattr(
                recommendation,
                "game_id",
                "",
            )
        )

        market = str(
            getattr(
                recommendation,
                "market",
                "Ganador del partido",
            )
        )

        selection = str(
            getattr(
                recommendation,
                "selection",
                "",
            )
        )

        unique_id = prediction_id(
            sport,
            game_id,
            market,
            selection,
        )

        exists = any(
            row.get(
                "prediction_id"
            )
            == unique_id
            for row in rows
        )

        if not exists:

            row = {
                "prediction_id":
                    unique_id,

                "created_at":
                    now.isoformat(),

                "sport":
                    sport,

                "game_id":
                    game_id,

                "matchup":
                    getattr(
                        recommendation,
                        "matchup",
                        "",
                    ),

                "start":
                    getattr(
                        recommendation,
                        "start",
                        "",
                    ),

                "market":
                    market,

                "selection":
                    selection,

                "bookmaker":
                    getattr(
                        recommendation,
                        "bookmaker",
                        "",
                    ),

                "decimal_odds":
                    _safe_float(
                        getattr(
                            recommendation,
                            "decimal_odds",
                            None,
                        )
                    ),

                "model_probability":
                    _safe_float(
                        getattr(
                            recommendation,
                            "model_probability",
                            None,
                        )
                    ),

                "model_probability_pct":
                    _pct(
                        getattr(
                            recommendation,
                            "model_probability",
                            None,
                        )
                    ),

                "break_even_probability":
                    _safe_float(
                        getattr(
                            recommendation,
                            "break_even_probability",
                            None,
                        )
                    ),

                "edge":
                    _safe_float(
                        getattr(
                            recommendation,
                            "edge",
                            None,
                        )
                    ),

                "edge_pct":
                    _pct(
                        getattr(
                            recommendation,
                            "edge",
                            None,
                        )
                    ),

                "expected_value":
                    _safe_float(
                        getattr(
                            recommendation,
                            "expected_value",
                            None,
                        )
                    ),

                "expected_value_pct":
                    _pct(
                        getattr(
                            recommendation,
                            "expected_value",
                            None,
                        )
                    ),

                "bookmakers":
                    getattr(
                        recommendation,
                        "bookmakers",
                        None,
                    ),

                "data_quality":
                    getattr(
                        recommendation,
                        "data_quality",
                        None,
                    ),

                "reasons":
                    list(
                        getattr(
                            recommendation,
                            "reasons",
                            (),
                        )
                    ),

                "status":
                    "PENDIENTE",

                "winner":
                    None,

                "home_team":
                    None,

                "away_team":
                    None,

                "home_score":
                    None,

                "away_score":
                    None,

                "f5_home_score":
                    None,

                "f5_away_score":
                    None,

                "resolved_at":
                    None,
            }

            rows.append(
                row
            )

    # ========================================================
    # 2. RESOLVER PARTIDOS TERMINADOS
    # ========================================================

    for game in games:

        game_id = str(
            getattr(
                game,
                "id",
                "",
            )
        )

        if not game_id:
            continue

        if not _is_finished_game(
            game
        ):
            continue

        home_team = str(
            getattr(
                getattr(
                    game,
                    "home",
                    None,
                ),
                "name",
                "",
            )
        )

        away_team = str(
            getattr(
                getattr(
                    game,
                    "away",
                    None,
                ),
                "name",
                "",
            )
        )

        raw = getattr(
            game,
            "raw",
            {},
        )

        home_score = _score(
            raw,
            "home",
        )

        away_score = _score(
            raw,
            "away",
        )

        # ----------------------------------------------------
        # F5
        # ----------------------------------------------------

        f5_home, f5_away = (
            _first_five_scores(
                raw
            )
        )

        for row in rows:

            if (
                str(
                    row.get(
                        "game_id"
                    )
                )
                != game_id
            ):
                continue

            if str(
                row.get(
                    "sport"
                )
            ).upper() != sport.upper():
                continue

            if (
                row.get("status")
                != "PENDIENTE"
            ):
                continue

            row["home_team"] = (
                home_team
            )

            row["away_team"] = (
                away_team
            )

            row["home_score"] = (
                home_score
            )

            row["away_score"] = (
                away_score
            )

            market = str(
                row.get(
                    "market",
                    "",
                )
            ).lower()

            # =================================================
            # RESOLVER F5
            # =================================================

            if (
                "5"
                in market
                and (
                    "entrada"
                    in market
                    or
                    "inning"
                    in market
                    or
                    "f5"
                    in market
                )
            ):

                if (
                    f5_home is None
                    or
                    f5_away is None
                ):
                    continue

                row[
                    "f5_home_score"
                ] = f5_home

                row[
                    "f5_away_score"
                ] = f5_away

                if (
                    f5_home
                    ==
                    f5_away
                ):

                    row["status"] = (
                        "EMPATE"
                    )

                    row["winner"] = (
                        None
                    )

                else:

                    winner = (
                        home_team
                        if f5_home
                        > f5_away
                        else away_team
                    )

                    row["winner"] = (
                        winner
                    )

                    if _same_team(
                        row.get(
                            "selection",
                            "",
                        ),
                        winner,
                    ):

                        row["status"] = (
                            "GANADA"
                        )

                    else:

                        row["status"] = (
                            "PERDIDA"
                        )

                row[
                    "resolved_at"
                ] = now.isoformat()

            # =================================================
            # RESOLVER GANADOR FINAL
            # =================================================

            else:

                if (
                    home_score is None
                    or
                    away_score is None
                ):
                    continue

                if (
                    home_score
                    ==
                    away_score
                ):

                    row["status"] = (
                        "EMPATE"
                    )

                    row["winner"] = (
                        None
                    )

                else:

                    winner = (
                        home_team
                        if home_score
                        > away_score
                        else away_team
                    )

                    row["winner"] = (
                        winner
                    )

                    if _same_team(
                        row.get(
                            "selection",
                            "",
                        ),
                        winner,
                    ):

                        row["status"] = (
                            "GANADA"
                        )

                    else:

                        row["status"] = (
                            "PERDIDA"
                        )

                row[
                    "resolved_at"
                ] = now.isoformat()

    save_history(
        path,
        rows,
    )

    return rows


# ============================================================
# RESUMEN
# ============================================================

def history_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:

    total = len(
        rows
    )

    won = sum(
        1
        for row in rows
        if row.get(
            "status"
        )
        == "GANADA"
    )

    lost = sum(
        1
        for row in rows
        if row.get(
            "status"
        )
        == "PERDIDA"
    )

    ties = sum(
        1
        for row in rows
        if row.get(
            "status"
        )
        == "EMPATE"
    )

    pending = sum(
        1
        for row in rows
        if row.get(
            "status"
        )
        == "PENDIENTE"
    )

    resolved = (
        won
        + lost
    )

    win_rate = (
        won
        / resolved
        * 100.0
        if resolved
        else 0.0
    )

    return {
        "total":
            total,

        "ganadas":
            won,

        "perdidas":
            lost,

        "empates":
            ties,

        "pendientes":
            pending,

        "resueltas":
            resolved,

        "win_rate":
            round(
                win_rate,
                2,
            ),
    }


# ============================================================
# RESUMEN POR MERCADO
# ============================================================

def history_summary_by_market(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:

    output: dict[
        str,
        dict[str, Any],
    ] = {}

    markets = sorted(
        {
            str(
                row.get(
                    "market",
                    "N/D",
                )
            )
            for row in rows
        }
    )

    for market in markets:

        market_rows = [
            row
            for row in rows
            if str(
                row.get(
                    "market",
                    ""
                )
            )
            == market
        ]

        output[
            market
        ] = history_summary(
            market_rows
        )

    return output


# ============================================================
# ÚLTIMAS PREDICCIONES
# ============================================================

def recent_history(
    rows: list[dict[str, Any]],
    limit: int = 100,
) -> list[dict[str, Any]]:

    ordered = sorted(
        rows,
        key=lambda row: str(
            row.get(
                "created_at",
                "",
            )
        ),
        reverse=True,
    )

    return ordered[
        :limit
    ]


# ============================================================
# BORRAR HISTORIAL
# ============================================================

def clear_history(
    path: str | Path,
) -> None:

    save_history(
        path,
        [],
    )


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
) -> float | None:

    try:

        if value is None:
            return None

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


def _pct(
    value: Any,
) -> float | None:

    number = _safe_float(
        value
    )

    if number is None:
        return None

    return round(
        number
        * 100.0,
        2,
    )


def _same_team(
    a: Any,
    b: Any,
) -> bool:

    a = _normalize_team(
        str(
            a
            or ""
        )
    )

    b = _normalize_team(
        str(
            b
            or ""
        )
    )

    if not a or not b:
        return False

    return (
        a == b
        or a in b
        or b in a
    )


def _normalize_team(
    value: str,
) -> str:

    return "".join(
        char.lower()
        for char in value
        if char.isalnum()
    )


def _is_finished_game(
    game: Any,
) -> bool:

    status = str(
        getattr(
            game,
            "status",
            "",
        )
    ).lower()

    return any(
        word in status
        for word in (
            "final",
            "finished",
            "closed",
            "game finished",
            "ft",
        )
    )


def _score(
    raw: dict[str, Any],
    side: str,
) -> float | None:

    scores = (
        raw.get("scores")
        or {}
    )

    block = scores.get(
        side
    )

    if (
        side == "away"
        and block is None
    ):

        block = scores.get(
            "visitors"
        )

    if block is None:
        return None

    if isinstance(
        block,
        (
            int,
            float,
            str,
        ),
    ):

        return _safe_float(
            block
        )

    if isinstance(
        block,
        dict,
    ):

        for key in (
            "total",
            "points",
            "runs",
            "score",
        ):

            value = block.get(
                key
            )

            if value is not None:

                number = (
                    _safe_float(
                        value
                    )
                )

                if number is not None:
                    return number

    return None


# ============================================================
# PRIMERAS 5 ENTRADAS
# ============================================================

def _first_five_scores(
    raw: dict[str, Any],
) -> tuple[
    float | None,
    float | None,
]:

    scores = (
        raw.get("scores")
        or {}
    )

    # --------------------------------------------------------
    # FORMATO POSIBLE:
    # scores.home.innings
    # scores.away.innings
    # --------------------------------------------------------

    home_block = (
        scores.get("home")
        or {}
    )

    away_block = (
        scores.get("away")
        or scores.get("visitors")
        or {}
    )

    if isinstance(
        home_block,
        dict,
    ) and isinstance(
        away_block,
        dict,
    ):

        home_innings = (
            home_block.get(
                "innings"
            )
        )

        away_innings = (
            away_block.get(
                "innings"
            )
        )

        if isinstance(
            home_innings,
            list,
        ) and isinstance(
            away_innings,
            list,
        ):

            home_f5 = sum(
                _safe_float(
                    value
                )
                or 0.0
                for value
                in home_innings[:5]
            )

            away_f5 = sum(
                _safe_float(
                    value
                )
                or 0.0
                for value
                in away_innings[:5]
            )

            return (
                home_f5,
                away_f5,
            )

    # --------------------------------------------------------
    # FORMATO POSIBLE:
    # innings: [{home: x, away: y}, ...]
    # --------------------------------------------------------

    innings = raw.get(
        "innings"
    )

    if isinstance(
        innings,
        list,
    ):

        home_f5 = 0.0
        away_f5 = 0.0
        found = 0

        for inning in innings[:5]:

            if not isinstance(
                inning,
                dict,
            ):
                continue

            home = (
                _safe_float(
                    inning.get(
                        "home"
                    )
                )
            )

            away = (
                _safe_float(
                    inning.get(
                        "away"
                    )
                )
            )

            if away is None:

                away = (
                    _safe_float(
                        inning.get(
                            "visitors"
                        )
                    )
                )

            if (
                home is None
                or away is None
            ):
                continue

            home_f5 += home
            away_f5 += away
            found += 1

        if found >= 5:

            return (
                home_f5,
                away_f5,
            )

    return (
        None,
        None,
        )
