from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import Candidate, Game, is_finished, score_for_side


def load_history(path: Path) -> list[dict[str, Any]]:
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


def update_history(
    path: Path,
    sport: str,
    games: list[Game],
    recommendations: list[Candidate],
    generated_at: datetime,
) -> list[dict[str, Any]]:

    rows = load_history(path)

    game_map = {
        str(g.id): g
        for g in games
    }

    # Resolver selecciones anteriores
    # de ganador final.
    for row in rows:

        if (
            row.get("sport") != sport
            or row.get("status") != "PENDIENTE"
        ):
            continue

        if (
            row.get("market")
            != "Ganador del partido"
        ):
            continue

        game = game_map.get(
            str(
                row.get("game_id")
            )
        )

        if (
            not game
            or not is_finished(
                game.status
            )
        ):
            continue

        hs = score_for_side(
            game.raw,
            "home",
        )

        aws = score_for_side(
            game.raw,
            "away",
        )

        if (
            hs is None
            or aws is None
            or hs == aws
        ):
            continue

        winner = (
            game.home.name
            if hs > aws
            else game.away.name
        )

        row["winner"] = winner

        row["final_score"] = (
            f"{game.away.name} "
            f"{aws:g} - "
            f"{game.home.name} "
            f"{hs:g}"
        )

        row["result"] = (
            "GANADA"
            if winner
            == row.get("selection")
            else "PERDIDA"
        )

        row["status"] = "RESUELTA"

        row["resolved_at"] = (
            generated_at.isoformat()
        )

    # Guardar las nuevas selecciones
    # (#1 y #2).
    #
    # F5 también se registra, pero queda
    # pendiente hasta que exista un
    # resolutor por innings.
    #
    # Ganador final sí se resuelve arriba.

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

        if not any(
            row.get("key") == key
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


def history_summary(
    rows: list[dict[str, Any]],
) -> dict[str, int | float]:

    resolved = [
        r
        for r in rows
        if r.get("result")
        in {
            "GANADA",
            "PERDIDA",
        }
    ]

    won = sum(
        r.get("result") == "GANADA"
        for r in resolved
    )

    lost = sum(
        r.get("result") == "PERDIDA"
        for r in resolved
    )

    return {
        "total": len(rows),
        "resolved": len(resolved),
        "won": won,
        "lost": lost,
        "pending": sum(
            r.get("status")
            == "PENDIENTE"
            for r in rows
        ),
        "win_rate": (
            won / len(resolved)
            if resolved
            else 0.0
        ),
    }
