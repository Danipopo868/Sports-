from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


HISTORY_FILE = "sports_history.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_load(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def _safe_save(
    rows: list[dict[str, Any]],
    path: str,
) -> None:

    temp_path = f"{path}.tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(
            rows,
            f,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(
        temp_path,
        path,
    )


def load_history(
    path: str = HISTORY_FILE,
) -> list[dict[str, Any]]:

    return _safe_load(path)


def save_history(
    rows: list[dict[str, Any]],
    path: str = HISTORY_FILE,
) -> None:

    _safe_save(
        rows,
        path,
    )


def build_history_id(
    sport: str,
    game_id: str,
    market: str,
    team: str,
) -> str:

    return (
        f"{sport}|"
        f"{game_id}|"
        f"{market}|"
        f"{team}"
    )


def add_prediction(
    prediction: dict[str, Any],
    path: str = HISTORY_FILE,
) -> dict[str, Any]:

    rows = load_history(path)

    sport = str(
        prediction.get("sport")
        or ""
    )

    game_id = str(
        prediction.get("game_id")
        or ""
    )

    market = str(
        prediction.get("market")
        or "GANADOR_FINAL"
    )

    team = str(
        prediction.get("team")
        or ""
    )

    history_id = build_history_id(
        sport=sport,
        game_id=game_id,
        market=market,
        team=team,
    )

    for row in rows:
        if row.get("history_id") == history_id:
            return row

    item = {
        "history_id": history_id,
        "created_at": _now_iso(),

        "sport": sport,
        "game_id": game_id,
        "market": market,

        "team": team,
        "opponent": prediction.get(
            "opponent"
        ),

        "side": prediction.get(
            "side"
        ),

        "decision": prediction.get(
            "decision"
        ),

        "model_probability": prediction.get(
            "model_probability"
        ),

        "model_probability_pct": prediction.get(
            "model_probability_pct"
        ),

        "market_probability": prediction.get(
            "market_probability"
        ),

        "market_probability_pct": prediction.get(
            "market_probability_pct"
        ),

        "edge_pct": prediction.get(
            "edge_pct"
        ),

        "confidence": prediction.get(
            "confidence"
        ),

        "score": prediction.get(
            "score"
        ),

        "data_quality": prediction.get(
            "data_quality"
        ),

        "reasons": prediction.get(
            "reasons"
        ),

        "status": "PENDIENTE",

        "winner": None,

        "home_score": None,
        "away_score": None,

        "f5_home_score": None,
        "f5_away_score": None,

        "resolved_at": None,
    }

    rows.append(item)

    save_history(
        rows,
        path,
    )

    return item


def _team_matches(
    selected_team: str,
    winner_team: str,
) -> bool:

    a = (
        selected_team
        .strip()
        .lower()
    )

    b = (
        winner_team
        .strip()
        .lower()
    )

    return (
        a == b
        or
        a in b
        or
        b in a
    )


def resolve_final_winner(
    game_id: str,
    winner_team: str,
    home_score: int | float | None = None,
    away_score: int | float | None = None,
    sport: str = "MLB",
    path: str = HISTORY_FILE,
) -> int:

    rows = load_history(path)

    changed = 0

    for row in rows:

        if str(
            row.get("game_id")
        ) != str(game_id):
            continue

        if str(
            row.get("sport")
        ).upper() != sport.upper():
            continue

        if (
            str(
                row.get("market")
            ).upper()
            !=
            "GANADOR_FINAL"
        ):
            continue

        if row.get("status") not in (
            "PENDIENTE",
            None,
            "",
        ):
            continue

        selected_team = str(
            row.get("team")
            or ""
        )

        if _team_matches(
            selected_team,
            winner_team,
        ):
            result = "GANADA"
        else:
            result = "PERDIDA"

        row["status"] = result
        row["winner"] = winner_team

        row["home_score"] = home_score
        row["away_score"] = away_score

        row["resolved_at"] = _now_iso()

        changed += 1

    if changed:
        save_history(
            rows,
            path,
        )

    return changed


def resolve_f5_result(
    game_id: str,
    home_team: str,
    away_team: str,
    home_score_f5: int | float,
    away_score_f5: int | float,
    sport: str = "MLB",
    path: str = HISTORY_FILE,
) -> int:

    rows = load_history(path)

    changed = 0

    if home_score_f5 > away_score_f5:
        winner = home_team

    elif away_score_f5 > home_score_f5:
        winner = away_team

    else:
        winner = None

    for row in rows:

        if str(
            row.get("game_id")
        ) != str(game_id):
            continue

        if str(
            row.get("sport")
        ).upper() != sport.upper():
            continue

        if str(
            row.get("market")
        ).upper() != "F5":
            continue

        if row.get("status") not in (
            "PENDIENTE",
            None,
            "",
        ):
            continue

        row["f5_home_score"] = home_score_f5
        row["f5_away_score"] = away_score_f5

        if winner is None:
            row["status"] = "EMPATE"
            row["winner"] = None

        else:

            selected_team = str(
                row.get("team")
                or ""
            )

            if _team_matches(
                selected_team,
                winner,
            ):
                row["status"] = "GANADA"
            else:
                row["status"] = "PERDIDA"

            row["winner"] = winner

        row["resolved_at"] = _now_iso()

        changed += 1

    if changed:
        save_history(
            rows,
            path,
        )

    return changed


def history_summary(
    sport: str | None = None,
    market: str | None = None,
    path: str = HISTORY_FILE,
) -> dict[str, Any]:

    rows = load_history(path)

    filtered = []

    for row in rows:

        if sport:

            if str(
                row.get("sport")
            ).upper() != sport.upper():
                continue

        if market:

            if str(
                row.get("market")
            ).upper() != market.upper():
                continue

        filtered.append(row)

    won = sum(
        1
        for row in filtered
        if row.get("status") == "GANADA"
    )

    lost = sum(
        1
        for row in filtered
        if row.get("status") == "PERDIDA"
    )

    ties = sum(
        1
        for row in filtered
        if row.get("status") == "EMPATE"
    )

    pending = sum(
        1
        for row in filtered
        if row.get("status") == "PENDIENTE"
    )

    resolved = won + lost

    accuracy = (
        won / resolved * 100.0
        if resolved
        else 0.0
    )

    return {
        "total": len(filtered),
        "ganadas": won,
        "perdidas": lost,
        "empates": ties,
        "pendientes": pending,
        "resueltas": resolved,
        "accuracy_pct": round(
            accuracy,
            2,
        ),
    }


def recent_history(
    limit: int = 50,
    sport: str | None = None,
    market: str | None = None,
    path: str = HISTORY_FILE,
) -> list[dict[str, Any]]:

    rows = load_history(path)

    filtered = []

    for row in rows:

        if sport:

            if str(
                row.get("sport")
            ).upper() != sport.upper():
                continue

        if market:

            if str(
                row.get("market")
            ).upper() != market.upper():
                continue

        filtered.append(row)

    filtered.sort(
        key=lambda row: str(
            row.get("created_at")
            or ""
        ),
        reverse=True,
    )

    return filtered[:limit]


def clear_history(
    path: str = HISTORY_FILE,
) -> None:

    save_history(
        [],
        path,
    )


def pending_predictions(
    sport: str | None = None,
    path: str = HISTORY_FILE,
) -> list[dict[str, Any]]:

    rows = load_history(path)

    pending = []

    for row in rows:

        if row.get("status") != "PENDIENTE":
            continue

        if sport:

            if str(
                row.get("sport")
            ).upper() != sport.upper():
                continue

        pending.append(row)

    return pending
