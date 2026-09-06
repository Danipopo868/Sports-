from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "dashboard_data" / "latest.json"
HISTORY_FILE = ROOT / "dashboard_data" / "prediction_history.json"
SPORT_NAMES = {
    "MLB": "MLB · Béisbol",
    "NFL": "NFL · Fútbol americano",
    "NBA": "NBA · Baloncesto",
}


st.set_page_config(
    page_title="Sports Edge",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .stApp {
        background:
          radial-gradient(circle at 50% -20%, #18304b 0%, #090f18 42%, #060910 72%);
      }
      .block-container { max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem; }
      h1, h2, h3 { letter-spacing: -0.025em; }
      [data-testid="stMetric"] {
        background: rgba(15, 24, 36, 0.88);
        border: 1px solid #273547;
        border-radius: 14px;
        padding: 14px 16px;
      }
      [data-testid="stMetricValue"] { color: #f7fafc; }
      .edge-badge {
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        padding: .35rem .7rem;
        border: 1px solid rgba(200,255,61,.35);
        border-radius: 999px;
        color: #dfff8d;
        background: rgba(200,255,61,.08);
        font-size: .82rem;
        font-weight: 700;
      }
      .muted { color: #95a4b7; font-size: .9rem; }
      .footer-note {
        margin-top: 2rem;
        color: #93a0b2;
        border-top: 1px solid #263242;
        padding-top: 1rem;
        font-size: .88rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=30)
def load_snapshot(path: str, modified: float) -> dict[str, Any]:
    del modified
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pct(value: Any) -> str:
    try:
        return f"{100 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def display_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d/%m/%Y · %I:%M %p")
    except (TypeError, ValueError):
        return value or "Sin fecha"


def render_candidate(candidate: dict[str, Any], pick_number: int | None = None) -> None:
    label = f"APUESTA #{pick_number}" if pick_number is not None else "APUESTA"
    st.success(f"{label} · CON VALOR DETECTADA")
    st.subheader(candidate.get("selection", "Selección no disponible"))
    st.caption(
        f"{candidate.get('matchup', 'Partido sin identificar')} · "
        f"{candidate.get('market', 'Mercado sin identificar')}"
    )
    probability, odds, edge, expected_value = st.columns(4)
    probability.metric("Probabilidad estimada", pct(candidate.get("model_probability")))
    odds.metric("Mejor cuota", f"{float(candidate.get('decimal_odds', 0)):.2f}")
    edge.metric("Ventaja", pct(candidate.get("edge")))
    expected_value.metric("Valor esperado", pct(candidate.get("expected_value")))

    detail_left, detail_right = st.columns(2)
    with detail_left:
        st.write(f"**Casa:** {candidate.get('bookmaker', 'No disponible')}")
        st.write(
            f"**Punto de equilibrio:** {pct(candidate.get('break_even_probability'))}"
        )
    with detail_right:
        st.write(f"**Casas comparadas:** {candidate.get('bookmakers', 0)}")
        st.write(f"**Calidad de datos:** {candidate.get('data_quality', 0)}/100")

    reasons = candidate.get("reasons") or []
    if reasons:
        st.markdown("**Por qué pasó los filtros**")
        for reason in reasons:
            st.write(f"• {reason}")


def render_no_bet(result: dict[str, Any]) -> None:
    st.warning("NO APOSTAR")
    notes = result.get("notes") or [
        "Ninguna opción superó todos los filtros matemáticos y de calidad."
    ]
    for note in notes:
        st.write(f"• {note}")

    best = result.get("best_observed")
    if not best:
        return
    with st.expander("Ver la opción más cercana que fue descartada"):
        st.write(f"**{best.get('selection', 'Sin selección')}**")
        st.caption(f"{best.get('matchup', '')} · {best.get('market', '')}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Probabilidad", pct(best.get("model_probability")))
        col2.metric("Ventaja", pct(best.get("edge")))
        col3.metric("Calidad", f"{best.get('data_quality', 0)}/100")


def render_sport(sport: str, result: dict[str, Any]) -> None:
    error = result.get("error")
    if error:
        st.error("NO APOSTAR — DATOS INCOMPLETOS")
        st.write(error)
    else:
        recommendations = result.get("recommendations") or []
        if not recommendations and result.get("recommendation"):
            recommendations = [result["recommendation"]]
        if recommendations:
            for index, candidate in enumerate(recommendations[:2], start=1):
                render_candidate(candidate, index)
                if index < len(recommendations[:2]):
                    st.divider()
            if len(recommendations) == 1:
                st.info("Solo 1 partido distinto pasó todos los filtros. El motor no fuerza una segunda apuesta.")
        else:
            render_no_bet(result)
    st.caption(
        f"Partidos revisados: {result.get('games', 0)} · "
        f"Cuotas válidas: {result.get('quotes', 0)}"
    )


title, action = st.columns([5, 1])
with title:
    st.title("Sports Edge")
    st.caption(
        "Hasta 2 selecciones por deporte, de partidos distintos, "
        "respaldadas por probabilidades y valor esperado."
    )
with action:
    if st.button("Actualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if not DATA_FILE.exists():
    st.info(
        "El panel está listo. Ejecuta primero el workflow de GitHub durante 15 o 180 minutos; "
        "cuando termine, aquí aparecerá el reporte."
    )
    st.stop()

snapshot = load_snapshot(str(DATA_FILE), DATA_FILE.stat().st_mtime)

st.markdown(
    '<span class="edge-badge">● Datos reales · último reporte</span>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<p class="muted">Actualizado {display_time(snapshot.get("generated_at", ""))} · '
    f'escaneo #{snapshot.get("scan_number", "—")}</p>',
    unsafe_allow_html=True,
)

tabs = st.tabs(
    [
        SPORT_NAMES[sport]
        for sport in ("MLB", "NFL", "NBA")
    ]
)

for tab, sport in zip(
    tabs,
    ("MLB", "NFL", "NBA"),
):
    with tab:
        render_sport(
            sport,
            snapshot.get(
                "sports",
                {},
            ).get(
                sport,
                {},
            ),
        )

st.markdown(
    '<div class="footer-note">Las probabilidades son estimaciones, no garantías. '
    'Si faltan cuotas, abridores o historial suficiente, el sistema bloquea la apuesta.</div>',
    unsafe_allow_html=True,
)


# Historial automático de selecciones
st.divider()
st.subheader("Historial de predicciones")

if HISTORY_FILE.exists():
    try:
        history_rows = json.loads(
            HISTORY_FILE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        history_rows = []

    resolved = [
        r
        for r in history_rows
        if r.get("result")
        in ("GANADA", "PERDIDA")
    ]

    won = sum(
        r.get("result") == "GANADA"
        for r in resolved
    )

    lost = sum(
        r.get("result") == "PERDIDA"
        for r in resolved
    )

    pending = sum(
        r.get("status") == "PENDIENTE"
        for r in history_rows
    )

    h1, h2, h3, h4 = st.columns(4)

    h1.metric(
        "Ganadas",
        won,
    )

    h2.metric(
        "Perdidas",
        lost,
    )

    h3.metric(
        "Pendientes",
        pending,
    )

    h4.metric(
        "Efectividad",
        (
            f"{(100 * won / len(resolved)):.1f}%"
            if resolved
            else "—"
        ),
    )

    if history_rows:
        columns = [
            "created_at",
            "sport",
            "pick_number",
            "matchup",
            "market",
            "selection",
            "probability",
            "data_quality",
            "result",
            "final_score",
        ]

        table = [
            {
                k: r.get(k)
                for k in columns
            }
            for r in reversed(
                history_rows[-100:]
            )
        ]

        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
        )

else:
    st.caption(
        "El historial comenzará a llenarse cuando el motor haga su primera selección."
    )
