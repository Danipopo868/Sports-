from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st


# ============================================================
# RUTAS
# ============================================================

ROOT = Path(__file__).resolve().parent

DATA_FILE = (
    ROOT
    / "reports"
    / "latest.json"
)

HISTORY_FILE = (
    ROOT
    / "dashboard_data"
    / "prediction_history.json"
)


# ============================================================
# DEPORTES
# ============================================================

SPORT_NAMES = {
    "MLB": "Major League Baseball",
    "NFL": "National Football League",
    "NBA": "National Basketball Association",
}

SPORT_LOGOS = {
    "MLB": "https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png",
    "NFL": "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png",
    "NBA": "https://a.espncdn.com/i/teamlogos/leagues/500/nba.png",
}


# ============================================================
# STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Sports Edge",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background:
          radial-gradient(
            circle at 50% -20%,
            #18304b 0%,
            #090f18 42%,
            #060910 72%
          );
    }

    .block-container {
        max-width: 1180px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        letter-spacing: -0.025em;
    }

    [data-testid="stMetric"] {
        background: rgba(15, 24, 36, 0.92);
        border: 1px solid #273547;
        border-radius: 16px;
        padding: 14px 16px;
    }

    [data-testid="stMetricLabel"] {
        color: #9eabbc;
    }

    [data-testid="stMetricValue"] {
        color: #f7fafc;
    }

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

    .muted {
        color: #95a4b7;
        font-size: .9rem;
    }

    .sport-header {
        display: flex;
        align-items: center;
        gap: 18px;
        padding: 18px 20px;
        margin-bottom: 18px;
        background: rgba(14, 22, 34, 0.94);
        border: 1px solid #29384b;
        border-radius: 18px;
    }

    .sport-logo {
        width: 78px;
        height: 78px;
        object-fit: contain;
    }

    .sport-code {
        font-size: 1.65rem;
        font-weight: 800;
        color: #ffffff;
        line-height: 1.1;
    }

    .sport-name {
        margin-top: 5px;
        color: #9aa8bb;
        font-size: .95rem;
    }

    .history-title {
        margin-top: 1rem;
        margin-bottom: .5rem;
    }

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


# ============================================================
# CARGAR REPORTE
# ============================================================

@st.cache_data(ttl=30)
def load_snapshot(
    path: str,
    modified: float,
) -> dict[str, Any]:

    del modified

    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# CARGAR HISTORIAL
# ============================================================

@st.cache_data(ttl=20)
def load_history(
    path: str,
    modified: float,
) -> list[dict[str, Any]]:

    del modified

    try:

        data = json.loads(
            Path(path).read_text(
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

    except Exception:
        return []


# ============================================================
# FORMATO %
# ============================================================

def pct(
    value: Any,
) -> str:

    try:

        number = float(
            value
        )

        # Si ya viene 71.2,
        # no volver a multiplicar por 100.
        if abs(number) > 1:
            return f"{number:.1f}%"

        return f"{number * 100:.1f}%"

    except (
        TypeError,
        ValueError,
    ):
        return "—"


# ============================================================
# FORMATO HORA
# ============================================================

def display_time(
    value: str,
) -> str:

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        return parsed.strftime(
            "%d/%m/%Y · %I:%M %p"
        )

    except (
        TypeError,
        ValueError,
    ):
        return value or "Sin fecha"


# ============================================================
# RESUMEN DE HISTORIAL
# ============================================================

def history_stats(
    rows: list[dict[str, Any]],
    sport: str | None = None,
) -> dict[str, int | float]:

    filtered = rows

    if sport:

        filtered = [
            row
            for row in rows
            if str(
                row.get(
                    "sport",
                    ""
                )
            ).upper()
            == sport.upper()
        ]

    won = sum(
        row.get(
            "result"
        )
        == "GANADA"
        for row in filtered
    )

    lost = sum(
        row.get(
            "result"
        )
        == "PERDIDA"
        for row in filtered
    )

    tied = sum(
        row.get(
            "result"
        )
        == "EMPATE"
        for row in filtered
    )

    pending = sum(
        str(
            row.get(
                "status",
                ""
            )
        ).upper()
        == "PENDIENTE"
        for row in filtered
    )

    decisions = (
        won
        + lost
    )

    win_rate = (
        won / decisions
        if decisions
        else 0.0
    )

    return {
        "won": won,
        "lost": lost,
        "tied": tied,
        "pending": pending,
        "win_rate": win_rate,
    }


# ============================================================
# LOGO + CABECERA DE DEPORTE
# ============================================================

def render_sport_header(
    sport: str,
) -> None:

    logo = SPORT_LOGOS.get(
        sport,
        "",
    )

    name = SPORT_NAMES.get(
        sport,
        sport,
    )

    st.markdown(
        f"""
        <div class="sport-header">
            <img
                class="sport-logo"
                src="{logo}"
            >
            <div>
                <div class="sport-code">
                    {sport}
                </div>
                <div class="sport-name">
                    {name}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# MÉTRICAS DE UN DEPORTE
# ============================================================

def render_sport_stats(
    history_rows: list[dict[str, Any]],
    sport: str,
) -> None:

    stats = history_stats(
        history_rows,
        sport,
    )

    c1, c2, c3, c4, c5 = st.columns(
        5
    )

    c1.metric(
        "✅ Ganadas",
        int(
            stats["won"]
        ),
    )

    c2.metric(
        "❌ Perdidas",
        int(
            stats["lost"]
        ),
    )

    c3.metric(
        "➖ Empates",
        int(
            stats["tied"]
        ),
    )

    c4.metric(
        "⏳ Pendientes",
        int(
            stats["pending"]
        ),
    )

    c5.metric(
        "🎯 Efectividad",
        (
            f"{float(stats['win_rate']) * 100:.1f}%"
            if (
                int(stats["won"])
                + int(stats["lost"])
            )
            else "—"
        ),
    )

    st.write("")


# ============================================================
# CANDIDATO
# ============================================================

def render_candidate(
    candidate: dict[str, Any],
    pick_number: int | None = None,
) -> None:

    label = (
        f"APUESTA #{pick_number}"
        if pick_number is not None
        else "APUESTA"
    )

    st.success(
        f"{label} · CON VALOR DETECTADA"
    )

    st.subheader(
        candidate.get(
            "selection",
            "Selección no disponible",
        )
    )

    st.caption(
        f"{candidate.get('matchup', 'Partido sin identificar')} · "
        f"{candidate.get('market', 'Mercado sin identificar')}"
    )

    probability, odds, edge, expected_value = (
        st.columns(
            4
        )
    )

    probability.metric(
        "Probabilidad estimada",
        pct(
            candidate.get(
                "model_probability"
            )
        ),
    )

    try:
        odds_value = (
            f"{float(candidate.get('decimal_odds')):.2f}"
            if candidate.get(
                "decimal_odds"
            )
            is not None
            else "—"
        )
    except (
        TypeError,
        ValueError,
    ):
        odds_value = "—"

    odds.metric(
        "Mejor cuota",
        odds_value,
    )

    edge.metric(
        "Ventaja",
        pct(
            candidate.get(
                "edge"
            )
        ),
    )

    expected_value.metric(
        "Valor esperado",
        pct(
            candidate.get(
                "expected_value"
            )
        ),
    )

    detail_left, detail_right = (
        st.columns(
            2
        )
    )

    with detail_left:

        st.write(
            f"**Casa:** "
            f"{candidate.get('bookmaker', 'No disponible')}"
        )

        st.write(
            "**Punto de equilibrio:** "
            f"{pct(candidate.get('break_even_probability'))}"
        )

    with detail_right:

        st.write(
            "**Casas comparadas:** "
            f"{candidate.get('bookmakers', 0)}"
        )

        st.write(
            "**Calidad de datos:** "
            f"{candidate.get('data_quality', 0)}/100"
        )

    reasons = (
        candidate.get(
            "reasons"
        )
        or []
    )

    if reasons:

        st.markdown(
            "**Por qué pasó los filtros**"
        )

        for reason in reasons:
            st.write(
                f"• {reason}"
            )


# ============================================================
# NO APOSTAR
# ============================================================

def render_no_bet(
    result: dict[str, Any],
) -> None:

    st.warning(
        "NO APOSTAR"
    )

    notes = (
        result.get(
            "notes"
        )
        or [
            "Ninguna opción superó todos los filtros matemáticos y de calidad."
        ]
    )

    for note in notes:
        st.write(
            f"• {note}"
        )

    best = result.get(
        "best_observed"
    )

    if not best:
        return

    with st.expander(
        "Ver la opción más cercana que fue descartada"
    ):

        st.write(
            f"**{best.get('selection', 'Sin selección')}**"
        )

        st.caption(
            f"{best.get('matchup', '')} · "
            f"{best.get('market', '')}"
        )

        col1, col2, col3 = (
            st.columns(
                3
            )
        )

        col1.metric(
            "Probabilidad",
            pct(
                best.get(
                    "model_probability"
                )
            ),
        )

        col2.metric(
            "Ventaja",
            pct(
                best.get(
                    "edge"
                )
            ),
        )

        col3.metric(
            "Calidad",
            f"{best.get('data_quality', 0)}/100",
        )


# ============================================================
# DEPORTE
# ============================================================

def render_sport(
    sport: str,
    result: dict[str, Any],
    history_rows: list[dict[str, Any]],
) -> None:

    render_sport_header(
        sport
    )

    render_sport_stats(
        history_rows,
        sport,
    )

    error = result.get(
        "error"
    )

    if error:

        st.error(
            "NO APOSTAR — DATOS INCOMPLETOS"
        )

        st.write(
            error
        )

    else:

        recommendations = (
            result.get(
                "recommendations"
            )
            or []
        )

        if (
            not recommendations
            and result.get(
                "recommendation"
            )
        ):

            recommendations = [
                result[
                    "recommendation"
                ]
            ]

        if recommendations:

            for (
                index,
                candidate,
            ) in enumerate(
                recommendations[
                    :2
                ],
                start=1,
            ):

                render_candidate(
                    candidate,
                    index,
                )

                if (
                    index
                    < len(
                        recommendations[
                            :2
                        ]
                    )
                ):
                    st.divider()

            if (
                len(
                    recommendations
                )
                == 1
            ):

                st.info(
                    "Solo 1 partido distinto pasó todos los filtros. "
                    "El motor no fuerza una segunda apuesta."
                )

        else:

            render_no_bet(
                result
            )

    st.caption(
        f"Partidos revisados: {result.get('games', 0)} · "
        f"Cuotas válidas: {result.get('quotes', 0)}"
    )


# ============================================================
# ENCABEZADO
# ============================================================

title, action = st.columns(
    [
        5,
        1,
    ]
)

with title:

    st.title(
        "🏆 Sports Edge"
    )

    st.caption(
        "Hasta 2 selecciones por deporte, "
        "de partidos distintos, respaldadas "
        "por probabilidades y valor esperado."
    )

with action:

    if st.button(
        "🔄 Actualizar",
        use_container_width=True,
    ):

        st.cache_data.clear()
        st.rerun()


# ============================================================
# COMPROBAR REPORTE
# ============================================================

if not DATA_FILE.exists():

    st.info(
        "El panel está listo. "
        "Ejecuta primero el workflow de GitHub; "
        "cuando termine aparecerá el reporte."
    )

    st.stop()


# ============================================================
# SNAPSHOT
# ============================================================

snapshot = load_snapshot(
    str(
        DATA_FILE
    ),
    DATA_FILE.stat().st_mtime,
)


# ============================================================
# HISTORIAL
# ============================================================

if HISTORY_FILE.exists():

    history_rows = load_history(
        str(
            HISTORY_FILE
        ),
        HISTORY_FILE.stat().st_mtime,
    )

else:

    history_rows = []


# ============================================================
# ESTADO
# ============================================================

st.markdown(
    '<span class="edge-badge">'
    '● Datos reales · último reporte'
    '</span>',
    unsafe_allow_html=True,
)

st.markdown(
    (
        '<p class="muted">'
        f'Actualizado '
        f'{display_time(snapshot.get("generated_at", ""))}'
        f' · escaneo #{snapshot.get("scan_number", "—")}'
        '</p>'
    ),
    unsafe_allow_html=True,
)


# ============================================================
# RESUMEN GENERAL
# ============================================================

st.subheader(
    "📊 Resultados generales"
)

general = history_stats(
    history_rows
)

g1, g2, g3, g4, g5 = (
    st.columns(
        5
    )
)

g1.metric(
    "✅ Ganadas",
    int(
        general["won"]
    ),
)

g2.metric(
    "❌ Perdidas",
    int(
        general["lost"]
    ),
)

g3.metric(
    "➖ Empates",
    int(
        general["tied"]
    ),
)

g4.metric(
    "⏳ Pendientes",
    int(
        general["pending"]
    ),
)

g5.metric(
    "🎯 Efectividad",
    (
        f"{float(general['win_rate']) * 100:.1f}%"
        if (
            int(
                general["won"]
            )
            + int(
                general["lost"]
            )
        )
        else "—"
    ),
)

st.write("")


# ============================================================
# TABS
# ============================================================

tabs = st.tabs(
    [
        "⚾ MLB",
        "🏈 NFL",
        "🏀 NBA",
    ]
)

for tab, sport in zip(
    tabs,
    (
        "MLB",
        "NFL",
        "NBA",
    ),
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
            history_rows,
        )


# ============================================================
# HISTORIAL
# ============================================================

st.divider()

st.subheader(
    "📋 Historial de predicciones"
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
            key: row.get(
                key
            )
            for key in columns
        }
        for row in reversed(
            history_rows[
                -100:
            ]
        )
    ]

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.caption(
        "El historial comenzará a llenarse "
        "cuando el motor haga su primera selección."
    )


# ============================================================
# NOTA
# ============================================================

st.markdown(
    (
        '<div class="footer-note">'
        'Las probabilidades son estimaciones, no garantías. '
        'La efectividad se calcula solamente con GANADAS y '
        'PERDIDAS; los EMPATES no cuentan como victoria ni derrota.'
        '</div>'
    ),
    unsafe_allow_html=True,
)
