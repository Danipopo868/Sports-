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


# ============================================================
# CARGAR / GUARDAR HISTORIAL
# ============================================================

def load_history(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)

    if not path.exists():
        return []

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
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
# IDENTIFICADOR FIJO DE PREDICCIÓN
# ============================================================

def prediction_id(
    sport: str,
    game_id: Any,
    market: str,
) -> str:
    """
    IMPORTANTE:

    El ID NO incluye la selección.

    Por ejemplo:

    MLB + juego 123 + Ganador del partido

    siempre genera el mismo ID aunque después
    el motor quisiera cambiar Yankees por Red Sox.

    Eso permite bloquear la primera predicción.
    """

    return (
        f"{str(sport).upper()}|"
        f"{str(game_id)}|"
        f"{str(market).lower().strip()}"
    )


# ============================================================
# EXTRAER DATOS DEL PARTIDO
# ============================================================

def _game_id(game: dict[str, Any]) -> Any:
    return (
        game.get("id")
        or game.get("game_id")
        or game.get("fixture_id")
    )


def _team_names(
    game: dict[str, Any],
) -> tuple[str, str]:

    teams = game.get("teams") or {}

    away = (
        game.get("away_name")
        or game.get("away_team")
    )

    home = (
        game.get("home_name")
        or game.get("home_team")
    )

    if isinstance(teams, dict):
        away_data = teams.get("away") or {}
        home_data = teams.get("home") or {}

        if isinstance(away_data, dict):
            away = (
                away
                or away_data.get("name")
            )

        if isinstance(home_data, dict):
            home = (
                home
                or home_data.get("name")
            )

    return (
        str(away or ""),
        str(home or ""),
    )


def _score(
    game: dict[str, Any],
) -> tuple[float | None, float | None]:

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
                or away.get("points")
                or away.get("runs")
            )
        else:
            away_score = away

        if isinstance(home, dict):
            home_score = (
                home.get("total")
                or home.get("points")
                or home.get("runs")
            )
        else:
            home_score = home

    return (
        _safe_float(away_score),
        _safe_float(home_score),
    )


def _first_five_scores(
    game: dict[str, Any],
) -> tuple[float | None, float | None]:

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
    found = False

    for inning_number in range(1, 6):

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

        if not isinstance(inning, dict):
            continue

        away = _safe_float(
            inning.get("away")
        )

        home = _safe_float(
            inning.get("home")
        )

        if away is not None:
            away_total += away
            found = True

        if home is not None:
            home_total += home
            found = True

    if not found:
        return None, None

    return away_total, home_total


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

    status = str(status).upper()

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
# ENCONTRAR PARTIDO
# ============================================================

def _find_game(
    games: list[Any],
    row: dict[str, Any],
) -> dict[str, Any] | None:

    wanted_id = str(
        row.get("game_id") or ""
    )

    for raw_game in games:

        game = _as_dict(raw_game)

        current_id = str(
            _game_id(game) or ""
        )

        if (
            wanted_id
            and current_id
            and wanted_id == current_id
        ):
            return game

    wanted_away = row.get("away_team")
    wanted_home = row.get("home_team")

    for raw_game in games:

        game = _as_dict(raw_game)

        away, home = _team_names(game)

        if (
            _same_team(away, wanted_away)
            and
            _same_team(home, wanted_home)
        ):
            return game

    return None


# ============================================================
# RESOLVER RESULTADO
# ============================================================

def _resolve_prediction(
    row: dict[str, Any],
    game: dict[str, Any],
) -> None:

    market = str(
        row.get("market") or ""
    ).lower()

    selection = row.get("selection")

    away_team, home_team = _team_names(
        game
    )

    # --------------------------------------------------------
    # F5
    # --------------------------------------------------------

    if (
        "primeras 5" in market
        or "f5" in market
    ):

        away_score, home_score = (
            _first_five_scores(game)
        )

        if (
            away_score is None
            or home_score is None
        ):
            return

        row["away_f5"] = away_score
        row["home_f5"] = home_score

    # --------------------------------------------------------
    # GANADOR FINAL
    # --------------------------------------------------------

    else:

        if not _is_finished_game(game):
            return

        away_score, home_score = _score(
            game
        )

        if (
            away_score is None
            or home_score is None
        ):
            return

        row["away_score"] = away_score
        row["home_score"] = home_score

    # --------------------------------------------------------
    # EMPATE
    # --------------------------------------------------------

    if away_score == home_score:
        row["status"] = "EMPATE"
        row["resolved_at"] = (
            datetime.now().astimezone().isoformat()
        )
        return

    winning_team = (
        away_team
        if away_score > home_score
        else home_team
    )

    if _same_team(
        selection,
        winning_team,
    ):
        row["status"] = "GANADA"
    else:
        row["status"] = "PERDIDA"

    row["resolved_at"] = (
        datetime.now().astimezone().isoformat()
    )


# ============================================================
# BLOQUEO: ¿YA EXISTE PREDICCIÓN?
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
        row.get("prediction_id") == pid
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
    # 1. PRIMERO ACTUALIZAR RESULTADOS EXISTENTES
    # ========================================================

    for row in rows:

        if (
            str(
                row.get("sport")
            ).upper()
            != str(sport).upper()
        ):
            continue

        if row.get("status") != "PENDIENTE":
            continue

        game = _find_game(
            games,
            row,
        )

        if game:
            _resolve_prediction(
                row,
                game,
            )

    # ========================================================
    # 2. SI NO HAY NUEVA RECOMENDACIÓN, SOLO GUARDAR
    # ========================================================

    recommendation_data = (
        _as_dict(
            recommendation
        )
    )

    if not recommendation_data:

        save_history(
            path,
            rows,
        )

        return history_summary(
            rows
        )

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

    selection = (
        recommendation_data.get(
            "selection"
        )
    )

    matchup = (
        recommendation_data.get(
            "matchup"
        )
        or ""
    )

    # ========================================================
    # 3. BLOQUEO ABSOLUTO
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
            if row.get(
                "prediction_id"
            ) == pid
        ),
        None,
    )

    if existing is not None:

        # ====================================================
        # MUY IMPORTANTE:
        #
        # YA EXISTE PREDICCIÓN PARA ESTE PARTIDO + MERCADO.
        #
        # NO CAMBIAMOS:
        # - selección
        # - probabilidad original
        # - mercado
        # - hora
        #
        # Aunque el motor ahora diga otro ganador.
        # ====================================================

        existing[
            "locked"
        ] = True

        save_history(
            path,
            rows,
        )

        return history_summary(
            rows
        )

    # ========================================================
    # 4. CREAR LA PRIMERA Y ÚNICA PREDICCIÓN
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

    # Intentar obtener nombres desde matchup
    if (
        (not away_team or not home_team)
        and " vs " in matchup.lower()
    ):
        parts = re.split(
            r"\s+vs\.?\s+",
            matchup,
            maxsplit=1,
            flags=re.IGNORECASE,
        )

        if len(parts) == 2:
            away_team = (
                away_team
                or parts[0].strip()
            )

            home_team = (
                home_team
                or parts[1].strip()
            )

    probability = (
        recommendation_data.get(
            "model_probability"
        )
    )

    probability_number = (
        _safe_float(
            probability
        )
    )

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

        "selection":
            selection,

        "model_probability":
            probability_number,

        "model_probability_pct":
            (
                round(
                    probability_number * 100,
                    2,
                )
                if (
                    probability_number
                    is not None
                    and probability_number <= 1
                )
                else probability_number
            ),

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
# RESUMEN
# ============================================================

def history_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:

    ganadas = sum(
        row.get("status") == "GANADA"
        for row in rows
    )

    perdidas = sum(
        row.get("status") == "PERDIDA"
        for row in rows
    )

    empates = sum(
        row.get("status") == "EMPATE"
        for row in rows
    )

    pendientes = sum(
        row.get("status") == "PENDIENTE"
        for row in rows
    )

    resolved = (
        ganadas
        + perdidas
    )

    win_rate = (
        round(
            100.0 * ganadas / resolved,
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
) -> dict[str, dict[str, Any]]:

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
