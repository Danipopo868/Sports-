from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .api import ApiSportsClient
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

    # Si en alguna versión del historial
    # existe "date", lo aceptamos.
    date_value = str(
        row.get("date")
        or ""
    ).strip()

    if date_value:
        return date_value[:10]

    # Historial actual:
    # created_at = 2026-09-06T10:30:00-05:00
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
    print(
        "REVISOR DE RESULTADOS"
    )
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
    #
    # Solo consultamos lo necesario.
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
                client.games_for_date(
                    sport,
                    date_iso,
                )
            )

            # IMPORTANTE:
            #
            # history.py trabaja con la respuesta
            # RAW de API-Sports para encontrar:
            # - game_id
            # - equipos
            # - status
            # - marcador
            #
            # recommendation=None garantiza que
            # este proceso NO crea una apuesta.
            update_history(
                path=HISTORY_FILE,
                sport=sport,
                games=games_result.response,
                recommendation=None,
                now=now,
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

    # ========================================================
    # RESUMEN ACTUALIZADO
    # ========================================================

    history = load_history(
        HISTORY_FILE
    )

    summary = history_summary(
        history
    )

    print()
    print("=" * 60)
    print(
        "RESULTADO DE LA REVISIÓN"
    )

    print(
        (
            "GANADAS:    "
            f"{summary.get('ganadas', 0)}"
        )
    )

    print(
        (
            "PERDIDAS:   "
            f"{summary.get('perdidas', 0)}"
        )
    )

    print(
        (
            "EMPATES:    "
            f"{summary.get('empates', 0)}"
        )
    )

    print(
        (
            "PENDIENTES: "
            f"{summary.get('pendientes', 0)}"
        )
    )

    print(
        (
            "WIN RATE:   "
            f"{summary.get('win_rate', 0.0):.2f}%"
        )
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
