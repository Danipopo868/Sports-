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
# SACAR VISITANTE + LOCAL DEL MATCHUP
# ============================================================

def _matchup_teams(
    row: dict[str, Any],
) -> tuple[
    str,
    str,
] | None:

    matchup = str(
        row.get(
            "matchup"
        )
        or ""
    ).strip()

    if "@" not in matchup:
        return None

    parts = matchup.split(
        "@",
        1,
    )

    if len(parts) != 2:
        return None

    expected_away = (
        _normalize_name(
            parts[0]
        )
    )

    expected_home = (
        _normalize_name(
            parts[1]
        )
    )

    if (
        not expected_away
        or not expected_home
    ):
        return None

    return (
        expected_away,
        expected_home,
    )


# ============================================================
# CONVERTIR FECHA A TIMESTAMP
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
# 1. ID exacto
# 2. visitante + local
# 3. si hay doble cartelera, horario más cercano
# ============================================================

def _find_game(
    row: dict[str, Any],
    games: list[Game],
    game_map: dict[str, Game],
) -> Game | None:

    game_id = str(
        row.get(
            "game_id"
        )
        or ""
    )

    if game_id:

        exact = game_map.get(
            game_id
        )

        if exact is not None:
            return exact

    matchup_teams = (
        _matchup_teams(
            row
        )
    )

    if matchup_teams is None:
        return None

    (
        expected_away,
        expected_home,
    ) = matchup_teams

    candidates: list[
        Game
    ] = []

    for game in games:

        actual_away = (
            _normalize_name(
                game.away.name
            )
        )

        actual_home = (
            _normalize_name(
                game.home.name
            )
        )

        if (
            actual_away
            == expected_away
            and actual_home
            == expected_home
        ):

            candidates.append(
                game
            )

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    row_start = _timestamp(
        row.get(
            "start"
        )
    )

    if row_start is None:
        return None

    timed: list[
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


# ============================================================
# EXTRAER UN NÚMERO SEGURO
# ============================================================

def _number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return float(
            value
        )

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return float(
            value
        )

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
                value.get(
                    key
                )
            )

            if found is not None:
                return found

        return None

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        if len(value) == 1:

            return _number(
                value[0]
            )

        for item in value:

            found = _number(
                item
            )

            if found is not None:
                return found

        return None

    try:

        return float(
            str(
                value
            ).strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


# ============================================================
# MARCADOR PRIMERAS 5 ENTRADAS
#
# REPARACIÓN:
# Combina la fuente principal con el respaldo MLB.
# ============================================================

def _first_five_score(
    raw: dict[str, Any],
) -> tuple[
    float,
    float,
] | None:

    inning_sources: list[
        list[Any]
    ] = []

    # --------------------------------------------------------
    # FUENTE PRINCIPAL
    # --------------------------------------------------------

    primary_innings = raw.get(
        "innings"
    )

    if isinstance(
        primary_innings,
        list,
    ):

        inning_sources.append(
            primary_innings
        )

    # --------------------------------------------------------
    # RESPALDO MLB
    # --------------------------------------------------------

    mlb_raw = (
        raw.get(
            "_mlb_raw"
        )
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

            mlb_innings = (
                linescore.get(
                    "innings"
                )
                or []
            )

            if isinstance(
                mlb_innings,
                list,
            ):

                inning_sources.append(
                    mlb_innings
                )

    if not inning_sources:
        return None

    inning_map: dict[
        int,
        tuple[
            float,
            float,
        ],
    ] = {}

    for innings in inning_sources:

        for inning in innings:

            if not isinstance(
                inning,
                dict,
            ):
                continue

            num_raw = inning.get(
                "num"
            )

            if num_raw is None:

                num_raw = inning.get(
                    "inning"
                )

            try:

                inning_num = int(
                    num_raw
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                inning_num < 1
                or inning_num > 5
            ):
                continue

            visitor_runs = _number(
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
                visitor_runs is None
                or home_runs is None
            ):
                continue

            inning_map[
                inning_num
            ] = (
                float(
                    visitor_runs
                ),
                float(
                    home_runs
                ),
            )

    # --------------------------------------------------------
    # ENTRE AMBAS FUENTES DEBEN ESTAR LOS INNINGS 1-5
    # --------------------------------------------------------

    if any(
        number not in inning_map
        for number in range(
            1,
            6,
        )
    ):
        return None

    visitor_total = sum(
        inning_map[
            number
        ][0]
        for number in range(
            1,
            6,
        )
    )

    home_total = sum(
        inning_map[
            number
        ][1]
        for number in range(
            1,
            6,
        )
    )

    return (
        home_total,
        visitor_total,
    )


# ============================================================
# COMPARAR SELECCIÓN
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
# MARCAR FILA RESUELTA
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
            != sport.upper()
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

            home_score = (
                score_for_side(
                    game.raw,
                    "home",
                )
            )

            visitor_score = (
                score_for_side(
                    game.raw,
                    "away",
                )
            )

            home_score = _number(
                home_score
            )

            visitor_score = _number(
                visitor_score
            )

            if (
                home_score is None
                or visitor_score is None
            ):
                continue

            score_text = (
                f"{game.away.name} "
                f"{visitor_score:g} - "
                f"{game.home.name} "
                f"{home_score:g}"
            )

            if (
                home_score
                == visitor_score
            ):

                _resolve_row(
                    row,
                    result="EMPATE",
                    winner=None,
                    final_score=(
                        score_text
                    ),
                    generated_at=(
                        generated_at
                    ),
                )

                continue

            winner = (
                game.home.name
                if home_score
                > visitor_score
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
                    score_text
                ),
                generated_at=(
                    generated_at
                ),
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

        (
            home_f5,
            visitor_f5,
        ) = first_five

        score_text = (
            f"{game.away.name} "
            f"{visitor_f5:g} - "
            f"{game.home.name} "
            f"{home_f5:g} "
            "(F5)"
        )

        # ----------------------------------------------------
        # EMPATE F5
        # ----------------------------------------------------

        if (
            home_f5
            == visitor_f5
        ):

            _resolve_row(
                row,
                result="EMPATE",
                winner=None,
                final_score=(
                    score_text
                ),
                generated_at=(
                    generated_at
                ),
            )

            continue

        winner = (
            game.home.name
            if home_f5
            > visitor_f5
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
                score_text
            ),
            generated_at=(
                generated_at
            ),
        )

    # ========================================================
    # GUARDAR NUEVAS RECOMENDACIONES
    #
    # results.py usa recommendations=[]
    # así que NO crea picks nuevos.
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

        if any(
            row.get(
                "key"
            )
            == key
            for row in rows
        ):
            continue

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
