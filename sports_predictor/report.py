from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import Candidate


SPORT_LABELS = {
    "MLB": "MLB — Béisbol",
    "NFL": "NFL — Fútbol americano",
    "NBA": "NBA — Baloncesto",
}


def build_snapshot(
    generated_at: datetime,
    date_iso: str,
    scan_number: int,
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at": generated_at.isoformat(),
        "analysis_date": date_iso,
        "scan_number": scan_number,
        "guarantee": False,
        "message": "Las probabilidades son estimaciones; ninguna apuesta garantiza ganancias.",
        "sports": {
            sport: {
                **{
                    key: value
                    for key, value in result.items()
                    if key
                    not in {
                        "recommendations",
                        "recommendation",
                        "best_observed",
                    }
                },
                "recommendations": [
                    _candidate_dict(candidate)
                    for candidate in result.get(
                        "recommendations",
                        [],
                    )
                ],
                # Se conserva recommendation por compatibilidad
                # con versiones anteriores del panel.
                "recommendation": _candidate_dict(
                    result.get("recommendation")
                ),
                "best_observed": _candidate_dict(
                    result.get("best_observed")
                ),
            }
            for sport, result in results.items()
        },
    }


def render_markdown(
    snapshot: dict[str, Any],
) -> str:
    lines = [
        "# Reporte del analizador deportivo",
        "",
        f"Actualizado: **{snapshot['generated_at']}**",
        f"Fecha deportiva analizada: **{snapshot['analysis_date']}**",
        f"Escaneo de la sesión: **#{snapshot['scan_number']}**",
        "",
        "> Las probabilidades son estimaciones. "
        "El sistema puede indicar NO APOSTAR y nunca garantiza ganancias.",
        "",
    ]

    for sport in (
        "MLB",
        "NFL",
        "NBA",
    ):
        result = snapshot[
            "sports"
        ].get(
            sport,
            {},
        )

        lines.extend(
            [
                f"## {SPORT_LABELS[sport]}",
                "",
            ]
        )

        error = result.get(
            "error"
        )

        recommendations = (
            result.get(
                "recommendations"
            )
            or (
                []
                if not result.get(
                    "recommendation"
                )
                else [
                    result.get(
                        "recommendation"
                    )
                ]
            )
        )

        if error:
            lines.extend(
                [
                    "**NO APOSTAR — datos incompletos**",
                    "",
                    f"Motivo: {error}",
                    "",
                ]
            )
            continue

        if recommendations:
            for (
                index,
                recommendation,
            ) in enumerate(
                recommendations[:2],
                start=1,
            ):
                lines.extend(
                    [
                        f"### APUESTA #{index}",
                        "",
                    ]
                )

                lines.extend(
                    _render_candidate(
                        recommendation,
                        approved=True,
                    )
                )

        else:
            lines.extend(
                [
                    "**NO APOSTAR**",
                    "",
                ]
            )

            for note in result.get(
                "notes",
                [],
            ):
                lines.append(
                    f"- {note}"
                )

            best = result.get(
                "best_observed"
            )

            if best:
                lines.extend(
                    [
                        "",
                        "La opción más cercana fue descartada:",
                        f"- {best['selection']} — {best['market']}",
                        f"- Probabilidad estimada: "
                        f"{_percent(best['model_probability'])}",
                        f"- Ventaja: "
                        f"{_percent(best['edge'])}; "
                        f"valor esperado: "
                        f"{_percent(best['expected_value'])}",
                        f"- Calidad de datos: "
                        f"{best['data_quality']}/100",
                    ]
                )

            lines.append("")

        lines.extend(
            [
                f"Partidos revisados: "
                f"{result.get('games', 0)} · "
                f"Cuotas válidas: "
                f"{result.get('quotes', 0)}",
                "",
            ]
        )

    return (
        "\n".join(lines)
        .rstrip()
        + "\n"
    )


def save_reports(
    snapshot: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    history_dir = (
        output_dir
        / "history"
    )

    history_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    markdown = render_markdown(
        snapshot
    )

    latest_md = (
        output_dir
        / "latest.md"
    )

    latest_json = (
        output_dir
        / "latest.json"
    )

    latest_md.write_text(
        markdown,
        encoding="utf-8",
    )

    serialized = json.dumps(
        snapshot,
        ensure_ascii=False,
        indent=2,
    )

    latest_json.write_text(
        serialized + "\n",
        encoding="utf-8",
    )

    stamp = snapshot[
        "generated_at"
    ].replace(
        ":",
        "-",
    )

    (
        history_dir
        / f"scan-{stamp}.json"
    ).write_text(
        serialized + "\n",
        encoding="utf-8",
    )

    return (
        latest_md,
        latest_json,
    )


def _render_candidate(
    candidate: dict[str, Any],
    approved: bool,
) -> list[str]:

    heading = (
        "APUESTA CON VALOR DETECTADA"
        if approved
        else "OPCIÓN OBSERVADA"
    )

    lines = [
        f"**{heading}**",
        "",
        f"- Partido: {candidate['matchup']}",
        f"- Mercado: {candidate['market']}",
        f"- Selección: **{candidate['selection']}**",
        f"- Mejor cuota decimal: "
        f"**{candidate['decimal_odds']:.2f}** "
        f"({candidate['bookmaker']})",
        f"- Probabilidad estimada: "
        f"**{_percent(candidate['model_probability'])}**",
        f"- Punto de equilibrio: "
        f"{_percent(candidate['break_even_probability'])}",
        f"- Ventaja calculada: "
        f"**{_percent(candidate['edge'])}**",
        f"- Valor esperado por unidad: "
        f"**{_percent(candidate['expected_value'])}**",
        f"- Casas comparadas: "
        f"{candidate['bookmakers']}",
        f"- Calidad de datos: "
        f"{candidate['data_quality']}/100",
    ]

    for reason in candidate.get(
        "reasons",
        [],
    ):
        lines.append(
            f"- {reason}"
        )

    lines.append("")

    return lines


def _candidate_dict(
    candidate: Candidate | None,
) -> dict[str, Any] | None:

    return (
        candidate.to_dict()
        if candidate
        else None
    )


def _percent(
    value: float,
) -> str:
    return (
        f"{100 * value:.1f}%"
    )
