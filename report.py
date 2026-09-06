from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# CONVERTIR OBJETOS A JSON
# ============================================================

def _serialize(
    value: Any,
) -> Any:

    if value is None:
        return None

    if is_dataclass(value):
        return {
            key: _serialize(val)
            for key, val
            in asdict(value).items()
        }

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key):
                _serialize(val)
            for key, val
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _serialize(item)
            for item in value
        ]

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    return value


# ============================================================
# CREAR SNAPSHOT
# ============================================================

def build_snapshot(
    generated_at: datetime,
    date_iso: str,
    scan_number: int,
    results: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, Any]:

    sports: dict[
        str,
        dict[str, Any],
    ] = {}

    for sport, data in results.items():

        sports[
            sport
        ] = {
            "games":
                data.get(
                    "games",
                    0,
                ),

            "quotes":
                data.get(
                    "quotes",
                    0,
                ),

            "remaining_requests":
                data.get(
                    "remaining_requests"
                ),

            "recommendation":
                _serialize(
                    data.get(
                        "recommendation"
                    )
                ),

            "best_observed":
                _serialize(
                    data.get(
                        "best_observed"
                    )
                ),

            "notes":
                _serialize(
                    data.get(
                        "notes",
                        [],
                    )
                ),

            "history_summary":
                _serialize(
                    data.get(
                        "history_summary",
                        {},
                    )
                ),

            "error":
                data.get(
                    "error"
                ),
        }

    return {
        "generated_at":
            generated_at.isoformat(),

        "date":
            date_iso,

        "scan_number":
            scan_number,

        "sports":
            sports,
    }


# ============================================================
# GUARDAR REPORTES
# ============================================================

def save_reports(
    snapshot: dict[str, Any],
    output_dir: str | Path,
) -> tuple[
    Path,
    Path,
]:

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    latest_json = (
        output_dir
        / "latest.json"
    )

    latest_md = (
        output_dir
        / "latest.md"
    )

    timestamp = str(
        snapshot.get(
            "generated_at",
            "",
        )
    )

    safe_timestamp = (
        timestamp
        .replace(
            ":",
            "-"
        )
        .replace(
            "+",
            "_"
        )
    )

    historical_json = (
        output_dir
        /
        f"snapshot_{safe_timestamp}.json"
    )

    # ========================================================
    # JSON
    # ========================================================

    json_text = json.dumps(
        snapshot,
        ensure_ascii=False,
        indent=2,
    )

    latest_json.write_text(
        json_text,
        encoding="utf-8",
    )

    historical_json.write_text(
        json_text,
        encoding="utf-8",
    )

    # ========================================================
    # MARKDOWN
    # ========================================================

    markdown = (
        _snapshot_to_markdown(
            snapshot
        )
    )

    latest_md.write_text(
        markdown,
        encoding="utf-8",
    )

    return (
        latest_md,
        latest_json,
    )


# ============================================================
# REPORTE LEGIBLE
# ============================================================

def _snapshot_to_markdown(
    snapshot: dict[str, Any],
) -> str:

    lines: list[str] = []

    lines.append(
        "# Sports Predictor"
    )

    lines.append(
        ""
    )

    lines.append(
        f"Fecha analizada: "
        f"{snapshot.get('date', '—')}"
    )

    lines.append(
        ""
    )

    lines.append(
        f"Generado: "
        f"{snapshot.get('generated_at', '—')}"
    )

    lines.append(
        ""
    )

    lines.append(
        f"Escaneo: "
        f"{snapshot.get('scan_number', '—')}"
    )

    lines.append(
        ""
    )

    sports = (
        snapshot.get(
            "sports",
            {}
        )
        or {}
    )

    for sport in (
        "MLB",
        "NFL",
        "NBA",
    ):

        data = (
            sports.get(
                sport,
                {}
            )
            or {}
        )

        lines.append(
            f"## {sport}"
        )

        lines.append(
            ""
        )

        error = data.get(
            "error"
        )

        if error:

            lines.append(
                f"Error: {error}"
            )

            lines.append(
                ""
            )

            continue

        lines.append(
            f"Partidos analizados: "
            f"{data.get('games', 0)}"
        )

        lines.append(
            ""
        )

        lines.append(
            f"Mercados/cuotas: "
            f"{data.get('quotes', 0)}"
        )

        lines.append(
            ""
        )

        recommendation = (
            data.get(
                "recommendation"
            )
        )

        if recommendation:

            lines.append(
                "### APUESTA SELECCIONADA"
            )

            lines.append(
                ""
            )

            lines.append(
                f"Partido: "
                f"{recommendation.get('matchup', '—')}"
            )

            lines.append(
                ""
            )

            lines.append(
                f"Mercado: "
                f"{recommendation.get('market', '—')}"
            )

            lines.append(
                ""
            )

            lines.append(
                f"Selección: "
                f"{recommendation.get('selection', '—')}"
            )

            lines.append(
                ""
            )

            probability = (
                recommendation.get(
                    "model_probability"
                )
            )

            if probability is not None:

                try:

                    probability_text = (
                        f"{float(probability) * 100:.1f}%"
                    )

                except Exception:

                    probability_text = (
                        str(
                            probability
                        )
                    )

            else:

                probability_text = "—"

            lines.append(
                f"Probabilidad del modelo: "
                f"{probability_text}"
            )

            lines.append(
                ""
            )

            lines.append(
                f"Calidad de datos: "
                f"{recommendation.get('data_quality', '—')}%"
            )

            lines.append(
                ""
            )

            lines.append(
                f"Edge: "
                f"{_percentage_text(recommendation.get('edge'))}"
            )

            lines.append(
                ""
            )

            lines.append(
                f"Valor esperado: "
                f"{_percentage_text(recommendation.get('expected_value'))}"
            )

            lines.append(
                ""
            )

            reasons = (
                recommendation.get(
                    "reasons"
                )
                or []
            )

            if reasons:

                lines.append(
                    "Factores:"
                )

                lines.append(
                    ""
                )

                for reason in reasons:

                    lines.append(
                        f"- {reason}"
                    )

                lines.append(
                    ""
                )

        else:

            lines.append(
                "### NO APOSTAR"
            )

            lines.append(
                ""
            )

            lines.append(
                "Ninguna opción superó todos los filtros."
            )

            lines.append(
                ""
            )

            best = data.get(
                "best_observed"
            )

            if best:

                lines.append(
                    "Mejor opción observada:"
                )

                lines.append(
                    ""
                )

                lines.append(
                    f"- Partido: "
                    f"{best.get('matchup', '—')}"
                )

                lines.append(
                    f"- Mercado: "
                    f"{best.get('market', '—')}"
                )

                lines.append(
                    f"- Selección: "
                    f"{best.get('selection', '—')}"
                )

                lines.append(
                    f"- Probabilidad: "
                    f"{_percentage_text(best.get('model_probability'))}"
                )

                lines.append(
                    ""
                )

        history = (
            data.get(
                "history_summary"
            )
            or {}
        )

        if history:

            lines.append(
                "### Historial"
            )

            lines.append(
                ""
            )

            lines.append(
                f"- Ganadas: "
                f"{history.get('ganadas', 0)}"
            )

            lines.append(
                f"- Perdidas: "
                f"{history.get('perdidas', 0)}"
            )

            lines.append(
                f"- Empates: "
                f"{history.get('empates', 0)}"
            )

            lines.append(
                f"- Pendientes: "
                f"{history.get('pendientes', 0)}"
            )

            lines.append(
                f"- Efectividad: "
                f"{history.get('win_rate', 0)}%"
            )

            lines.append(
                ""
            )

        notes = (
            data.get(
                "notes"
            )
            or []
        )

        if notes:

            lines.append(
                "### Notas"
            )

            lines.append(
                ""
            )

            for note in notes:

                lines.append(
                    f"- {note}"
                )

            lines.append(
                ""
            )

    return "\n".join(
        lines
    )


# ============================================================
# FORMATO DE PORCENTAJE
# ============================================================

def _percentage_text(
    value: Any,
) -> str:

    if value is None:
        return "—"

    try:

        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return str(
            value
        )

    if abs(number) <= 1:

        number *= 100

    return f"{number:.1f}%"
