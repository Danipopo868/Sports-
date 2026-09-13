from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import (
    Candidate,
    Game,
    is_finished,
    score_for_side,
)


# ============================================================
# CARGAR HISTORIAL
# ============================================================

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
            if isinstance(
                data,
                list,
            )
            else []
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []


# ============================================================
# GUARDAR HISTORIAL
# ============================================================

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
        )
        + "\n",
        encoding="utf-8",
    )


# ============================================================
# NORMALIZAR NOMBRES
#
# Se usa para poder emparejar:
#
# API-Sports:
#   game_id = X
#
# MLB Stats:
#   gamePk = Y
#
# aunque sean el mismo partido.
# ============================================================

def _normalize_name(
    value: Any,
) -> str:

    text = str(
        value
        or ""
    )

    plain = (
        unicodedata.normalize(
            "NFKD",
            text,
        )
        .encode(
            "ascii",
            "ignore",
        )
        .decode()
        .lower()
    )

    return re.sub(
        r"[^a-z0-9]+",
        "",
        plain,
    )


# ============================================================
# OBTENER EQUIPOS DEL MATCHUP GUARDADO
#
# El historial guarda:
#
#   "Boston Red Sox @ New York Yankees"
#
# Devuelve:
#
#   away, home
# ============================================================

def _matchup_teams(
    row: dict[str, Any],
) -> tuple[
    str,
    str,
] | None:

    matchup = str(
        row.get(
            "matchup",
            "",
        )
        or ""
    ).strip()

    if "@" not in matchup:
        return None

    away,
    home = matchup.split(
        "@",
        1,
    )

    away = _normalize_name(
        away
    )

    home = _normalize_name(
        home
    )

    if not away or not home:
        return None

    return (
        away,
        home,
    )


# ============================================================
# TIMESTAMP AUXILIAR
#
# Se usa solo si hay doble cartelera:
# mismos dos equipos el mismo día.
# ============================================================

def _timestamp(
    value: Any,
) -> float | None:

    text = str(
        value
        or ""
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


# ============================================================
# BUSCAR PARTIDO
#
# PRIORIDAD:
#
# 1. game_id exacto
# 2. visitante + local
# 3. si hay doble cartelera, elegir el más cercano
#    por hora de inicio
# ============================================================

def _find_game(
    row: dict[str, Any],
    games: list[Game],
    game_map: dict[str, Game],
) -> Game | None:

    # --------------------------------------------------------
    # 1. ID exacto
    # --------------------------------------------------------

    game_id = str(
        row.get(
            "game_id",
            "",
        )
    )

    if game_id:

        exact = game_map.get(
            game_id
        )

        if exact is not None:
            return exact

    # --------------------------------------------------------
    # 2. Matchup visitante @ local
    # --------------------------------------------------------

    teams = _matchup_teams(
        row
    )

    if teams is None:
        return None

    away_expected,
    home_expected = teams

    candidates: list[
        Game
    ] = []

    for game in games:

        away_actual = (
            _normalize_name(
                game.away.name
            )
        )

        home_actual = (
            _normalize_name(
                game.home.name
            )
        )

        if (
            away_actual
            == away_expected
            and home_actual
            == home_expected
        ):

            candidates.append(
                game
            )

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # --------------------------------------------------------
    # 3. Doble cartelera:
    # elegir el horario más cercano.
    # --------------------------------------------------------

    row_start = _timestamp(
        row.get(
            "start"
        )
    )

    if row_start is None:
        return None

    scored: list[
        tuple[
            float,
            Game,
        ]
    ] = []

    for game in candidates:

        game_start = _timestamp(
            game.start
        )

        if game_start is None:
            continue

        scored.append(
            (
                abs(
                    game_start
                    - row_start
                ),
                game,
            )
        )

    if not scored:
        return None

    scored.sort(
        key=lambda item: item[0]
    )

    return scored[0][1]


# ============================================================
# CONVERTIR VALOR A FLOAT
# ============================================================

def _float_or_none(
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


# ============================================================
# EXTRAER MARCADOR F5
#
# Usa los innings que api.py guarda:
#
# "innings": [
#   {
#       "num": 1,
#       "away": 0,
#       "home": 1
#   },
#   ...
# ]
#
# También tiene respaldo leyendo _mlb_raw.linescore.innings
# si existiera directamente.
# ============================================================

def _first_five_score(
    raw: dict[str, Any],
) -> tuple[
    float,
    float,
] | None:

    innings = (
        raw.get(
            "innings"
        )
        or []
    )

    # --------------------------------------------------------
    # RESPALDO:
    # MLB RAW original
    # --------------------------------------------------------

    if not innings:

        mlb_raw = (
            raw.get(
                "_mlb_raw"
            )
            or {}
        )

        linescore = (
            mlb_raw.get(
                "linescore"
            )
            or {}
        )

        innings = (
            linescore.get(
                "innings"
            )
            or []
        )

    if not isinstance(
        innings,
        list,
    ):
        return None

    inning_map: dict[
        int,
        tuple[
            float | None,
            float | None,
        ],
    ] = {}

    for inning in innings:

        if not isinstance(
            inning,
            dict,
        ):
            continue

        num_raw = (
            inning.get(
                "num"
            )
            or inning.get(
                "inning"
            )
        )

        try:
            num = int(
                num_raw
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            num < 1
            or num > 5
        ):
            continue

        # ----------------------------------------------------
        # FORMATO NORMALIZADO
        #
        # away: 1
        # home: 0
        # ----------------------------------------------------

        away_raw = inning.get(
            "away"
        )

        home_raw = inning.get(
            "home"
        )

        # ----------------------------------------------------
        # FORMATO MLB ORIGINAL
        #
        # away: {"runs": 1}
        # home: {"runs": 0}
        # ----------------------------------------------------

        if isinstance(
            away_raw,
            dict,
        ):

            away_raw = away_raw.get(
                "runs"
            )

        if isinstance(
            home_raw,
            dict,
        ):

            home_raw = home_raw.get(
                "runs"
            )

        away_runs = _float_or_none(
            away_raw
        )

        home_runs = _float_or_none(
            home_raw
        )

        inning_map[
            num
        ] = (
            away_runs,
            home_runs,
        )

    # --------------------------------------------------------
    # Necesitamos innings 1,2,3,4,5.
    #
    # No inventamos resultados si falta alguno.
    # --------------------------------------------------------

    if not all(
        number in inning_map
        for number in range(
            1,
            6,
        )
    ):
        return None

    away_total = 0.0
    home_total = 0.0

    for number in range(
        1,
        6,
    ):

        away_runs,
        home_runs = inning_map[
            number
        ]

        if (
            away_runs is None
            or home_runs is None
        ):
            return None

        away_total += away_runs
        home_total += home_runs

    return (
        home_total,
        away_total,
    )


# ============================================================
# COMPARAR SELECCIÓN CON GANADOR
# ============================================================

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
# MARCAR UNA FILA COMO RESUELTA
# ============================================================

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
        str(
            game.id
        ): game
        for game in games
    }

    # ========================================================
    # RESOLVER SELECCIONES ANTERIORES
    # ========================================================

    for row in rows:

        if (
            str(
                row.get(
                    "sport",
                    ""
                )
            ).upper()
            != sport.upper()
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

        market = str(
            row.get(
                "market",
                ""
            )
            or ""
        ).strip()

        if market not in {
            "Ganador del partido",
            "Primeras 5 entradas",
        }:
            continue

        # ----------------------------------------------------
        # Buscar juego.
        #
        # Primero ID.
        # Luego visitante + local.
        # ----------------------------------------------------

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
                continue

            # ------------------------------------------------
            # Empate.
            #
            # MLB normalmente no termina empatado,
            # pero para otros deportes puede ocurrir.
            # ------------------------------------------------

            if (
                home_score
                == away_score
            ):

                _resolve_row(
                    row,
                    result="EMPATE",
                    winner=None,
                    final_score=(
                        f"{game.away.name} "
                        f"{away_score:g} - "
                        f"{game.home.name} "
                        f"{home_score:g}"
                    ),
                    generated_at=(
                        generated_at
                    ),
                )

                continue

            winner = (
                game.home.name
                if home_score
                > away_score
                else game.away.name
            )

            result = (
                "GANADA"
                if _selection_matches(
                    row.get(
                        "selection"
                    ),
                    winner,
                )
                else "PERDIDA"
            )

            _resolve_row(
                row,
                result=result,
                winner=winner,
                final_score=(
                    f"{game.away.name} "
                    f"{away_score:g} - "
                    f"{game.home.name} "
                    f"{home_score:g}"
                ),
                generated_at=(
                    generated_at
                ),
            )

            continue

        # ====================================================
        # PRIMERAS 5 ENTRADAS
        # ====================================================

        if (
            market
            == "Primeras 5 entradas"
        ):

            # No necesitamos esperar al final del juego.
            #
            # En cuanto existan completos los innings 1-5
            # podemos determinar el resultado F5.

            first_five = _first_five_score(
                game.raw
            )

            if first_five is None:
                continue

            home_f5,
            away_f5 = first_five

            f5_score_text = (
                f"{game.away.name} "
                f"{away_f5:g} - "
                f"{game.home.name} "
                f"{home_f5:g} "
                "(F5)"
            )

            # ------------------------------------------------
            # EMPATE F5
            # ------------------------------------------------

            if (
                home_f5
                == away_f5
            ):

                _resolve_row(
                    row,
                    result="EMPATE",
                    winner=None,
                    final_score=(
                        f5_score_text
                    ),
                    generated_at=(
                        generated_at
                    ),
                )

                continue

            winner = (
                game.home.name
                if home_f5
                > away_f5
                else game.away.name
            )

            result = (
                "GANADA"
                if _selection_matches(
                    row.get(
                        "selection"
                    ),
                    winner,
                )
                else "PERDIDA"
            )

            _resolve_row(
                row,
                result=result,
                winner=winner,
                final_score=(
                    f5_score_text
                ),
                generated_at=(
                    generated_at
                ),
            )

    # ========================================================
    # GUARDAR NUEVAS SELECCIONES
    #
    # results.py pasa recommendations=[].
    #
    # Por tanto el revisor de resultados NO crea picks.
    #
    # El escáner normal sí puede seguir usando esta función
    # para guardar hasta dos selecciones.
    # ========================================================

    for (
        pick_number,
        recommendation,
    ) in enumerate(
        recommendations[
            :2
        ],
        start=1,
    ):

        key = (
            f"{sport}|"
            f"{recommendation.game_id}|"
            f"{recommendation.market}|"
            f"{recommendation.selection}"
        )

        if not any(
            row.get(
                "key"
            )
            == key
            for row in rows
        ):

            rows.append(
                {
                    "key": key,

                    "pick_number": (
                        pick_number
                    ),

                    "created_at": (
                        generated_at
                        .isoformat()
                    ),

                    "sport": sport,

                    "game_id": (
                        recommendation
                        .game_id
                    ),

                    "matchup": (
                        recommendation
                        .matchup
                    ),

                    "start": (
                        recommendation
                        .start
                    ),

                    "market": (
                        recommendation
                        .market
                    ),

                    "selection": (
                        recommendation
                        .selection
                    ),

                    "probability": (
                        recommendation
                        .model_probability
                    ),

                    "odds": (
                        recommendation
                        .decimal_odds
                    ),

                    "edge": (
                        recommendation
                        .edge
                    ),

                    "expected_value": (
                        recommendation
                        .expected_value
                    ),

                    "data_quality": (
                        recommendation
                        .data_quality
                    ),

                    "status": (
                        "PENDIENTE"
                    ),

                    "result": None,
                }
            )

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
) -> dict[
    str,
    int | float,
]:

    won = sum(
        row.get(
            "result"
        )
        == "GANADA"
        for row in rows
    )

    lost = sum(
        row.get(
            "result"
        )
        == "PERDIDA"
        for row in rows
    )

    tied = sum(
        row.get(
            "result"
        )
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
                "status",
                ""
            )
        ).upper()
        == "PENDIENTE"
        for row in rows
    )

    # Win rate excluye empates.
    #
    # Ejemplo:
    #
    # 5 GANADAS
    # 3 PERDIDAS
    # 2 EMPATES
    #
    # win_rate = 5 / 8
    #
    # Los pushes no cuentan como victoria ni derrota.
    decisions = (
        won
        + lost
    )

    win_rate = (
        won
        / decisions
        if decisions
        else 0.0
    )

    return {
        "total": len(
            rows
        ),

        "resolved": (
            resolved
        ),

        "won": won,

        "lost": lost,

        "tied": tied,

        "pending": (
            pending
        ),

        "win_rate": (
            win_rate
        ),
    }
