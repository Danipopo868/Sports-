from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# UTILIDADES
# ============================================================

def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if is_dataclass(value):
        return asdict(value)

    if hasattr(value, "__dict__"):
        return dict(value.__dict__)

    return {}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_team(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _same_team(a: Any, b: Any) -> bool:
    a_norm = _normalize_team(a)
    b_norm = _normalize_team(b)

    if not a_norm or not b_norm:
        return False

    return (
        a_norm == b_norm
        or a_norm in b_norm
        or b_norm in a_norm
    )


def _normalize_market(value: Any) -> str:
    text = str(value or "").lower().strip()

    if (
        "primeras 5" in text
        or "primeros 5" in text
        or "first 5" in text
        or "first five" in text
        or "f5" in text
    ):
        return "f5"

    if (
        "ganador" in text
        or "moneyline" in text
        or "winner" in text
        or "final" in text
        or "full game" in text
    ):
        return "final"

    return text


# ============================================================
# CARGAR / GUARDAR HISTORIAL
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


def save_history(
    path: str | Path,
    rows: list[dict[str, Any]],
) -> None:

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            rows,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# IDENTIFICADOR FIJO
# ============================================================

def prediction_id(
    sport: str,
    game_id: Any,
    market: str,
) -> str:

    return (
        f"{str(sport).upper()}|"
        f"{str(game_id)}|"
        f"{_normalize_market(market)}"
    )


# ============================================================
# DATOS DEL PARTIDO
# ============================================================

def _game_id(
    game: dict[str, Any],
) -> Any:

    return (
        game.get("id")
        or game.get("game_id")
        or game.get("fixture_id")
    )


def _team_names(
    game: dict[str, Any],
) -> tuple[str, str]:

    teams = (
        game.get("teams")
        or {}
    )

    away = (
        game.get("away_name")
        or game.get("away_team")
    )

    home = (
        game.get("home_name")
        or game.get("home_team")
    )

    if isinstance(teams, dict):

        away_data = (
            teams.get("away")
            or {}
        )

        home_data = (
            teams.get("home")
            or {}
        )

        if isinstance(away_data, dict):
            away = (
                away
                or away_data.get("name")
            )
        elif away_data:
            away = (
                away
                or away_data
            )

        if isinstance(home_data, dict):
            home = (
                home
                or home_data.get("name")
            )
        elif home_data:
            home = (
                home
                or home_data
            )

    return (
        str(away or ""),
        str(home or ""),
    )


# ============================================================
# SACAR EQUIPOS DEL MATCHUP
# ============================================================

def _teams_from_matchup(
    matchup: Any,
) -> tuple[str | None, str | None]:

    text = str(
        matchup or ""
    ).strip()

    if not text:
        return None, None

    # Formato principal del engine:
    # Away @ Home
    if "@" in text:

        parts = text.split(
            "@",
            1,
        )

        if len(parts) == 2:
            return (
                parts[0].strip() or None,
                parts[1].strip() or None,
            )

    # Compatibilidad con:
    # Away vs Home
    parts = re.split(
        r"\s+vs\.?\s+",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )

    if len(parts) == 2:
        return (
            parts[0].strip() or None,
            parts[1].strip() or None,
        )

    return None, None


# ============================================================
# MARCADOR FINAL
# ============================================================

def _score(
    game: dict[str, Any],
) -> tuple[
    float | None,
    float | None,
]:

    scores = (
        game.get("scores")
        or game.get("score")
        or {}
    )

    away_score = None
    home_score = None

    if isinstance(scores, dict):

        away = scores.get("away")
        home = scores.get("home")

        if isinstance(away, dict):
            away_score = (
                away.get("total")
                if away.get("total") is not None
                else away.get("points")
            )

            if away_score is None:
                away_score = (
                    away.get("runs")
                )

        else:
            away_score = away

        if isinstance(home, dict):
            home_score = (
                home.get("total")
                if home.get("total") is not None
                else home.get("points")
            )

            if home_score is None:
                home_score = (
                    home.get("runs")
                )

        else:
            home_score = home

    return (
        _safe_float(away_score),
        _safe_float(home_score),
    )


# ============================================================
# MARCADOR F5
# ============================================================

def _first_five_scores(
    game: dict[str, Any],
) -> tuple[
    float | None,
    float | None,
]:

    scores = (
        game.get("scores")
        or game.get("score")
        or {}
    )

    if not isinstance(scores, dict):
        return None, None

    innings = (
        scores.get("innings")
        or game.get("innings")
    )

    if not isinstance(innings, dict):
        return None, None

    away_total = 0.0
    home_total = 0.0

    innings_found = 0

    for inning_number in range(
        1,
        6,
    ):

        key_options = [
            str(inning_number),
            inning_number,
            f"inning_{inning_number}",
        ]

        inning = None

        for key in key_options:

            if key in innings:
                inning = innings[key]
                break

        if not isinstance(
            inning,
            dict,
        ):
            continue

        away = _safe_float(
            inning.get("away")
        )

        home = _safe_float(
            inning.get("home")
        )

        if (
            away is None
            and home is None
        ):
            continue

        innings_found += 1

        if away is not None:
            away_total += away

        if home is not None:
            home_total += home

    # Para resolver F5 exigimos que existan
    # datos de las cinco primeras entradas.
    if innings_found < 5:
        return None, None

    return (
        away_total,
        home_total,
    )


# ============================================================
# ¿PARTIDO TERMINADO?
# ============================================================

def _is_finished_game(
    game: dict[str, Any],
) -> bool:

    status = (
        game.get("status")
        or game.get("game_status")
        or ""
    )

    if isinstance(status, dict):
        status = (
            status.get("short")
            or status.get("long")
            or status.get("name")
            or ""
        )

    status = str(
        status
    ).upper().strip()

    finished_words = (
        "FT",
        "FINAL",
        "FINISHED",
        "COMPLETED",
        "ENDED",
        "AOT",
        "AP",
    )

    return any(
        word in status
        for word in finished_words
    )


# ============================================================
# BUSCAR PARTIDO EN RESPUESTA DE API
# ============================================================

def _find_game(
    games: list[Any],
    row: dict[str, Any],
) -> dict[str, Any] | None:

    wanted_id = str(
        row.get("game_id")
        or ""
    )

    # ========================================================
    # 1. BUSCAR POR ID
    # ========================================================

    for raw_game in games:

        game = _as_dict(
            raw_game
        )

        current_id = str(
            _game_id(game)
            or ""
        )

        if (
            wanted_id
            and current_id
            and wanted_id == current_id
        ):
            return game

    # ========================================================
    # 2. FALLBACK POR EQUIPOS
    # ========================================================

    wanted_away = (
        row.get("away_team")
    )

    wanted_home = (
        row.get("home_team")
    )

    if (
        not wanted_away
        or not wanted_home
    ):

        matchup_away, matchup_home = (
            _teams_from_matchup(
                row.get("matchup")
            )
        )

        wanted_away = (
            wanted_away
            or matchup_away
        )

        wanted_home = (
            wanted_home
            or matchup_home
        )

    if (
        not wanted_away
        or not wanted_home
    ):
        return None

    for raw_game in games:

        game = _as_dict(
            raw_game
        )

        away, home = (
            _team_names(game)
        )

        if (
            _same_team(
                away,
                wanted_away,
            )
            and
            _same_team(
                home,
                wanted_home,
            )
        ):
            return game

    return None


# ============================================================
# RESOLVER PREDICCIÓN
# ============================================================

def _resolve_prediction(
    row: dict[str, Any],
    game: dict[str, Any],
) -> None:

    market_type = (
        _normalize_market(
            row.get("market")
        )
    )

    selection = (
        row.get("selection")
    )

    away_team, home_team = (
        _team_names(game)
    )

    # ========================================================
    # F5
    # ========================================================

    if market_type == "f5":

        away_score, home_score = (
            _first_five_scores(
                game
            )
        )

        if (
            away_score is None
            or home_score is None
        ):
            return

        row["away_f5"] = (
            away_score
        )

        row["home_f5"] = (
            home_score
        )

    # ========================================================
    # GANADOR FINAL
    # ========================================================

    else:

        if not _is_finished_game(
            game
        ):
            return

        away_score, home_score = (
            _score(
                game
            )
        )

        if (
            away_score is None
            or home_score is None
        ):
            return

        row["away_score"] = (
            away_score
        )

        row["home_score"] = (
            home_score
        )

    # ========================================================
    # EMPATE
    # ========================================================

    if away_score == home_score:

        row["status"] = (
            "EMPATE"
        )

        row["locked"] = False

        row["resolved_at"] = (
            datetime
            .now()
            .astimezone()
            .isoformat()
        )

        return

    # ========================================================
    # GANADOR REAL
    # ========================================================

    winning_team = (
        away_team
        if away_score > home_score
        else home_team
    )

    if _same_team(
        selection,
        winning_team,
    ):

        row["status"] = (
            "GANADA"
        )

    else:

        row["status"] = (
            "PERDIDA"
        )

    row["locked"] = False

    row["resolved_at"] = (
        datetime
        .now()
        .astimezone()
        .isoformat()
    )


# ============================================================
# BUSCAR PREDICCIÓN ACTIVA BLOQUEADA
# ============================================================

def get_active_prediction(
    rows: list[dict[str, Any]],
    sport: str,
    market: str,
) -> dict[str, Any] | None:

    wanted_sport = str(
        sport
    ).upper()

    wanted_market = (
        _normalize_market(
            market
        )
    )

    for row in reversed(
        rows
    ):

        if (
            str(
                row.get(
                    "sport",
                    ""
                )
            ).upper()
            != wanted_sport
        ):
            continue

        if (
            _normalize_market(
                row.get("market")
            )
            != wanted_market
        ):
            continue

        if (
            str(
                row.get(
                    "status",
                    ""
                )
            ).upper()
            != "PENDIENTE"
        ):
            continue

        return row

    return None


# ============================================================
# ¿ESTÁ BLOQUEADO ESE PARTIDO?
# ============================================================

def prediction_locked(
    rows: list[dict[str, Any]],
    sport: str,
    game_id: Any,
    market: str,
) -> bool:

    pid = prediction_id(
        sport,
        game_id,
        market,
    )

    return any(
        (
            row.get(
                "prediction_id"
            )
            == pid
            and str(
                row.get(
                    "status",
                    ""
                )
            ).upper()
            == "PENDIENTE"
        )
        for row in rows
    )


# ============================================================
# ACTUALIZAR HISTORIAL
# ============================================================

def update_history(
    path: str | Path,
    sport: str,
    games: list[Any],
    recommendation: Any,
    now: datetime,
) -> dict[str, Any]:

    rows = load_history(
        path
    )

    # ========================================================
    # 1. RESOLVER PREDICCIONES PENDIENTES
    # ========================================================

    for row in rows:

        if (
            str(
                row.get(
                    "sport",
                    ""
                )
            ).upper()
            != str(
                sport
            ).upper()
        ):
            continue

        if (
            str(
                row.get(
                    "status",
                    ""
                )
            ).upper()
            != "PENDIENTE"
        ):
            continue

        game = _find_game(
            games,
            row,
        )

        if game is not None:

            _resolve_prediction(
                row,
                game,
            )

    save_history(
        path,
        rows,
    )

    # ========================================================
    # 2. SI NO HAY RECOMENDACIÓN NUEVA, TERMINAR
    # ========================================================

    recommendation_data = (
        _as_dict(
            recommendation
        )
    )

    if not recommendation_data:

        return history_summary(
            rows
        )

    # ========================================================
    # 3. DATOS DE LA NUEVA PREDICCIÓN
    # ========================================================

    game_id = (
        recommendation_data.get(
            "game_id"
        )
        or recommendation_data.get(
            "fixture_id"
        )
    )

    market = (
        recommendation_data.get(
            "market"
        )
        or "Ganador del partido"
    )

    market_type = (
        _normalize_market(
            market
        )
    )

    selection = (
        recommendation_data.get(
            "selection"
        )
    )

    matchup = str(
        recommendation_data.get(
            "matchup"
        )
        or ""
    ).strip()

    # ========================================================
    # VALIDACIÓN BÁSICA
    # ========================================================

    if game_id is None:
        return history_summary(
            rows
        )

    if not selection:
        return history_summary(
            rows
        )

    # ========================================================
    # 4. BLOQUEO GLOBAL POR DEPORTE + MERCADO
    #
    # FINAL y F5 SON INDEPENDIENTES.
    # ========================================================

    active_prediction = (
        get_active_prediction(
            rows,
            sport,
            market,
        )
    )

    if active_prediction is not None:

        active_prediction[
            "locked"
        ] = True

        active_prediction[
            "market_type"
        ] = market_type

        save_history(
            path,
            rows,
        )

        return history_summary(
            rows
        )

    # ========================================================
    # 5. NO DUPLICAR MISMO PARTIDO + MERCADO
    # ========================================================

    pid = prediction_id(
        sport,
        game_id,
        market,
    )

    existing = next(
        (
            row
            for row in rows
            if (
                row.get(
                    "prediction_id"
                )
                == pid
            )
        ),
        None,
    )

    if existing is not None:

        # Una predicción ya resuelta NO debe
        # volver a convertirse en pendiente.
        save_history(
            path,
            rows,
        )

        return history_summary(
            rows
        )

    # ========================================================
    # 6. EQUIPOS
    # ========================================================

    away_team = (
        recommendation_data.get(
            "away_team"
        )
    )

    home_team = (
        recommendation_data.get(
            "home_team"
        )
    )

    # Si engine no los envió separados,
    # recuperarlos del matchup.
    if (
        not away_team
        or not home_team
    ):

        matchup_away, matchup_home = (
            _teams_from_matchup(
                matchup
            )
        )

        away_team = (
            away_team
            or matchup_away
        )

        home_team = (
            home_team
            or matchup_home
        )

    # ========================================================
    # 7. PROBABILIDAD
    # ========================================================

    probability_number = (
        _safe_float(
            recommendation_data.get(
                "model_probability"
            )
        )
    )

    if probability_number is None:

        probability_pct = None

    elif probability_number <= 1:

        probability_pct = round(
            probability_number * 100,
            2,
        )

    else:

        probability_pct = round(
            probability_number,
            2,
        )

    # ========================================================
    # 8. CREAR PREDICCIÓN
    # ========================================================

    row = {
        "prediction_id":
            pid,

        "created_at":
            now.isoformat(),

        "sport":
            str(sport).upper(),

        "game_id":
            game_id,

        "matchup":
            matchup,

        "away_team":
            away_team,

        "home_team":
            home_team,

        "market":
            market,

        "market_type":
            market_type,

        "selection":
            selection,

        "model_probability":
            probability_number,

        "model_probability_pct":
            probability_pct,

        "data_quality":
            recommendation_data.get(
                "data_quality"
            ),

        "decimal_odds":
            recommendation_data.get(
                "decimal_odds"
            ),

        "edge":
            recommendation_data.get(
                "edge"
            ),

        "expected_value":
            recommendation_data.get(
                "expected_value"
            ),

        "bookmaker":
            recommendation_data.get(
                "bookmaker"
            ),

        "bookmakers":
            recommendation_data.get(
                "bookmakers"
            ),

        "reasons":
            recommendation_data.get(
                "reasons"
            )
            or [],

        "status":
            "PENDIENTE",

        "locked":
            True,

        "resolved_at":
            None,

        "away_score":
            None,

        "home_score":
            None,

        "away_f5":
            None,

        "home_f5":
            None,
    }

    rows.append(
        row
    )

    save_history(
        path,
        rows,
    )

    return history_summary(
        rows
    )


# ============================================================
# RESUMEN GENERAL
# ============================================================

def history_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:

    ganadas = sum(
        str(
            row.get(
                "status",
                ""
            )
        ).upper()
        == "GANADA"
        for row in rows
    )

    perdidas = sum(
        str(
            row.get(
                "status",
                ""
            )
        ).upper()
        == "PERDIDA"
        for row in rows
    )

    empates = sum(
        str(
            row.get(
                "status",
                ""
            )
        ).upper()
        == "EMPATE"
        for row in rows
    )

    pendientes = sum(
        str(
            row.get(
                "status",
                ""
            )
        ).upper()
        == "PENDIENTE"
        for row in rows
    )

    resolved = (
        ganadas
        + perdidas
    )

    win_rate = (
        round(
            100.0
            * ganadas
            / resolved,
            2,
        )
        if resolved
        else 0.0
    )

    return {
        "total":
            len(rows),

        "ganadas":
            ganadas,

        "perdidas":
            perdidas,

        "empates":
            empates,

        "pendientes":
            pendientes,

        "win_rate":
            win_rate,
    }


# ============================================================
# RESUMEN POR MERCADO
# ============================================================

def history_summary_by_market(
    rows: list[dict[str, Any]],
) -> dict[
    str,
    dict[str, Any],
]:

    markets: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in rows:

        market = str(
            row.get("market")
            or "Desconocido"
        )

        markets.setdefault(
            market,
            [],
        ).append(
            row
        )

    return {
        market:
            history_summary(
                market_rows
            )
        for market, market_rows
        in markets.items()
    }


# ============================================================
# ÚLTIMAS PREDICCIONES
# ============================================================

def recent_history(
    rows: list[dict[str, Any]],
    limit: int = 100,
) -> list[dict[str, Any]]:

    return rows[
        -max(
            1,
            int(limit),
        ):
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
