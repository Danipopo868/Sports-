from __future__ import annotations

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .api import ApiSportsClient
from .engine import normalize_games
from .history import (
    history_summary,
    load_history,
    update_history,
)


# ============================================================
# RUTAS
# ============================================================

ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

CONFIG_FILE = (
    ROOT
    / "config.json"
)

HISTORY_FILE = (
    ROOT
    / "dashboard_data"
    / "prediction_history.json"
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

def load_config() -> dict[str, Any]:

    with CONFIG_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# ============================================================
# FECHA DE UNA PREDICCIÓN
# ============================================================

def prediction_date(
    row: dict[str, Any],
) -> str | None:

    date_value = str(
        row.get("date")
        or ""
    ).strip()

    if date_value:
        return date_value[:10]

    created_at = str(
        row.get("created_at")
        or ""
    ).strip()

    if created_at:

        try:
            return datetime.fromisoformat(
                created_at.replace(
                    "Z",
                    "+00:00",
                )
            ).date().isoformat()

        except ValueError:

            if len(created_at) >= 10:
                return created_at[:10]

    return None


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    config = load_config()

    timezone_name = (
        config.get(
            "timezone",
            "America/Chicago",
        )
    )

    timezone = ZoneInfo(
        timezone_name
    )

    now = datetime.now(
        timezone
    )

    # ========================================================
    # API KEY
    # ========================================================

    api_key = os.environ.get(
        "API_SPORTS_KEY",
        "",
    ).strip()

    if not api_key:

        raise RuntimeError(
            "Falta el secret API_SPORTS_KEY."
        )

    client = ApiSportsClient(
        api_key=api_key,
    )

    # ========================================================
    # CARGAR HISTORIAL
    # ========================================================

    history = load_history(
        HISTORY_FILE
    )

    pendientes = [
        row
        for row in history
        if str(
            row.get(
                "status",
                ""
            )
        ).upper()
        == "PENDIENTE"
    ]

    print()
    print("=" * 60)
    print("REVISOR DE RESULTADOS")
    print(
        f"Hora: {now.isoformat()}"
    )
    print(
        (
            "Predicciones pendientes: "
            f"{len(pendientes)}"
        )
    )
    print("=" * 60)

    # ========================================================
    # NO HAY NADA QUE RESOLVER
    # ========================================================

    if not pendientes:

        print(
            "No hay predicciones pendientes."
        )

        return

    # ========================================================
    # AGRUPAR POR DEPORTE + FECHA
    # ========================================================

    consultas: set[
        tuple[str, str]
    ] = set()

    sin_fecha = 0

    for row in pendientes:

        sport = str(
            row.get(
                "sport",
                ""
            )
        ).upper().strip()

        date_iso = prediction_date(
            row
        )

        if (
            sport
            and date_iso
        ):

            consultas.add(
                (
                    sport,
                    date_iso,
                )
            )

        else:

            sin_fecha += 1

    if sin_fecha:

        print(
            (
                "Advertencia: "
                f"{sin_fecha} predicción(es) "
                "pendiente(s) no tienen una "
                "fecha utilizable."
            )
        )

    # ========================================================
    # CONSULTAR RESULTADOS
    # ========================================================

    for sport, date_iso in sorted(
        consultas
    ):

        print()
        print(
            (
                f"Revisando {sport} "
                f"- {date_iso}"
            )
        )

        try:

            games_result = (
                client.result_games_for_date(
                    sport,
                    date_iso,
                )
            )

            games = normalize_games(
                sport,
                games_result.response,
            )

            print(
                (
                    f"{sport}: "
                    f"{len(games)} partido(s) "
                    "normalizado(s)."
                )
            )

            update_history(
                path=HISTORY_FILE,
                sport=sport,
                games=games,
                recommendations=[],
                generated_at=now,
            )

            print(
                (
                    f"{sport}: "
                    "resultados comprobados."
                )
            )

        except Exception as exc:

            print(
                (
                    f"{sport}: error "
                    "consultando resultados: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
            )

            print(
                "TRACEBACK COMPLETO:"
            )

            traceback.print_exc()

    # ========================================================
    # RECARGAR HISTORIAL
    # ========================================================

    history = load_history(
        HISTORY_FILE
    )

    # ========================================================
    # RESUMEN
    # ========================================================

    summary = history_summary(
        history
    )

    won = int(
        summary.get(
            "won",
            0,
        )
    )

    lost = int(
        summary.get(
            "lost",
            0,
        )
    )

    resolved = int(
        summary.get(
            "resolved",
            0,
        )
    )

    pending = int(
        summary.get(
            "pending",
            0,
        )
    )

    win_rate = (
        float(
            summary.get(
                "win_rate",
                0.0,
            )
        )
        * 100.0
    )

    print()
    print("=" * 60)
    print(
        "RESULTADO DE LA REVISIÓN"
    )

    print(
        (
            "GANADAS:    "
            f"{won}"
        )
    )

    print(
        (
            "PERDIDAS:   "
            f"{lost}"
        )
    )

    print(
        (
            "RESUELTAS:  "
            f"{resolved}"
        )
    )

    print(
        (
            "PENDIENTES: "
            f"{pending}"
        )
    )

    print(
        (
            "WIN RATE:   "
            f"{win_rate:.2f}%"
        )
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
