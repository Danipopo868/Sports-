from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Sports Predictor",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROOT = Path(__file__).resolve().parent

REPORT_FILE = (
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
# CSS
# ============================================================

st.markdown(
    """
<style>

.block-container {
    max-width: 1500px;
    padding-top: 1.4rem;
    padding-bottom: 4rem;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(
            circle at top left,
            #13213d 0%,
            #07101d 35%,
            #02050a 100%
        );
}

[data-testid="stHeader"] {
    background: transparent;
}

h1, h2, h3 {
    letter-spacing: -0.02em;
}

.main-title {
    font-size: 2.1rem;
    font-weight: 800;
    margin-bottom: 0;
}

.subtitle {
    opacity: .75;
    margin-top: .2rem;
    margin-bottom: 1.5rem;
}

.pick-card {
    border: 1px solid rgba(148,163,184,.22);
    border-radius: 18px;
    padding: 20px;
    margin: 10px 0 18px 0;
    background: rgba(15,23,42,.88);
}

.pick-title {
    font-size: 1.45rem;
    font-weight: 800;
    margin-bottom: 8px;
}

.pick-team {
    font-size: 1.9rem;
    font-weight: 900;
    margin: 6px 0;
}

.pick-market {
    font-size: 1rem;
    opacity: .82;
}

.good {
    font-weight: 800;
}

.small-text {
    font-size: .9rem;
    opacity: .72;
}

.history-win {
    font-weight: 800;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def load_json(
    path: Path,
    default,
):

    if not path.exists():
        return default

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return default


def pct(
    value,
) -> str:

    try:

        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return "—"

    if abs(number) <= 1.0:

        number *= 100.0

    return f"{number:.1f}%"


def decimal(
    value,
) -> str:

    try:

        return f"{float(value):.2f}"

    except (
        TypeError,
        ValueError,
    ):

        return "—"


def candidate_dict(
    candidate,
) -> dict:

    if candidate is None:
        return {}

    if isinstance(
        candidate,
        dict,
    ):
        return candidate

    return {}


def sport_title(
    sport: str,
) -> str:

    icons = {
        "MLB": "⚾",
        "NFL": "🏈",
        "NBA": "🏀",
    }

    return (
        f"{icons.get(sport, '🏆')} "
        f"{sport}"
    )


def market_icon(
    market: str,
) -> str:

    market_lower = str(
        market
    ).lower()

    if (
        "5"
        in market_lower
        or "f5"
        in market_lower
    ):
        return "5️⃣"

    return "🏆"


def result_icon(
    result: str | None,
) -> str:

    if result == "GANADA":
        return "✅"

    if result == "PERDIDA":
        return "❌"

    if result == "EMPATE":
        return "➖"

    return "⏳"


# ============================================================
# CARGAR DATOS
# ============================================================

snapshot = load_json(
    REPORT_FILE,
    {},
)

history_rows = load_json(
    HISTORY_FILE,
    [],
)

if not isinstance(
    history_rows,
    list,
):

    history_rows = []


# ============================================================
# CABECERA
# ============================================================

st.markdown(
    """
<div class="main-title">
🏆 SPORTS PREDICTOR
</div>

<div class="subtitle">
Motor de análisis deportivo — MLB · NFL · NBA
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# INFORMACIÓN DEL ÚLTIMO ESCANEO
# ============================================================

if snapshot:

    generated_at = (
        snapshot.get(
            "generated_at"
        )
        or snapshot.get(
            "timestamp"
        )
        or "—"
    )

    date_analyzed = (
        snapshot.get(
            "date"
        )
        or snapshot.get(
            "date_iso"
        )
        or "—"
    )

    scan_number = (
        snapshot.get(
            "scan_number",
            "—",
        )
    )

    a, b, c = st.columns(
        3
    )

    a.metric(
        "Fecha analizada",
        date_analyzed,
    )

    b.metric(
        "Escaneo",
        scan_number,
    )

    c.metric(
        "Última actualización",
        str(
            generated_at
        )[:19],
    )


# ============================================================
# DEPORTES
# ============================================================

sports_data = (
    snapshot.get(
        "sports",
        {}
    )
    if snapshot
    else {}
)

st.divider()

st.header(
    "🎯 Selecciones del motor"
)


# ============================================================
# MOSTRAR CADA DEPORTE
# ============================================================

for sport in (
    "MLB",
    "NFL",
    "NBA",
):

    data = (
        sports_data.get(
            sport,
            {}
        )
        or {}
    )

    st.subheader(
        sport_title(
            sport
        )
    )

    error = data.get(
        "error"
    )

    if error:

        st.error(
            f"{sport}: {error}"
        )

        continue

    games = data.get(
        "games",
        0,
    )

    quotes = data.get(
        "quotes",
        0,
    )

    recommendation = (
        candidate_dict(
            data.get(
                "recommendation"
            )
        )
    )

    best_observed = (
        candidate_dict(
            data.get(
                "best_observed"
            )
        )
    )

    # --------------------------------------------------------
    # CONTADORES
    # --------------------------------------------------------

    x1, x2 = st.columns(
        2
    )

    x1.metric(
        "Partidos analizados",
        games,
    )

    x2.metric(
        "Precios/mercados leídos",
        quotes,
    )

    # ========================================================
    # APUESTA RECOMENDADA
    # ========================================================

    if recommendation:

        market = (
            recommendation.get(
                "market"
            )
            or "Ganador del partido"
        )

        selection = (
            recommendation.get(
                "selection"
            )
            or "—"
        )

        matchup = (
            recommendation.get(
                "matchup"
            )
            or "—"
        )

        probability = (
            recommendation.get(
                "model_probability"
            )
        )

        quality = (
            recommendation.get(
                "data_quality"
            )
        )

        edge = (
            recommendation.get(
                "edge"
            )
        )

        ev = (
            recommendation.get(
                "expected_value"
            )
        )

        odds = (
            recommendation.get(
                "decimal_odds"
            )
        )

        st.markdown(
            f"""
<div class="pick-card">

<div class="pick-title">
{market_icon(market)} APUESTA SELECCIONADA
</div>

<div class="pick-team">
{selection}
</div>

<div class="pick-market">
{matchup}
<br>
{market}
</div>

</div>
""",
            unsafe_allow_html=True,
        )

        p1, p2, p3, p4 = (
            st.columns(
                4
            )
        )

        p1.metric(
            "Probabilidad",
            pct(
                probability
            ),
        )

        p2.metric(
            "Calidad de datos",
            (
                f"{quality}%"
                if quality
                is not None
                else "—"
            ),
        )

        p3.metric(
            "Edge",
            pct(
                edge
            ),
        )

        p4.metric(
            "Valor esperado",
            pct(
                ev
            ),
        )

        st.caption(
            "Cuota decimal disponible: "
            + decimal(
                odds
            )
        )

        reasons = (
            recommendation.get(
                "reasons"
            )
            or []
        )

        if reasons:

            with st.expander(
                "🔎 Ver análisis utilizado"
            ):

                for reason in reasons:

                    st.write(
                        f"• {reason}"
                    )

    # ========================================================
    # NO APOSTAR
    # ========================================================

    else:

        st.warning(
            "NO APOSTAR — ningún partido "
            "superó todos los filtros."
        )

        if best_observed:

            with st.expander(
                "Ver la opción que más se acercó"
            ):

                st.write(
                    "**Partido:**",
                    best_observed.get(
                        "matchup",
                        "—",
                    ),
                )

                st.write(
                    "**Selección:**",
                    best_observed.get(
                        "selection",
                        "—",
                    ),
                )

                st.write(
                    "**Mercado:**",
                    best_observed.get(
                        "market",
                        "—",
                    ),
                )

                st.write(
                    "**Probabilidad:**",
                    pct(
                        best_observed.get(
                            "model_probability"
                        )
                    ),
                )

                st.write(
                    "**Calidad:**",
                    best_observed.get(
                        "data_quality",
                        "—",
                    ),
                )

    # ========================================================
    # NOTAS
    # ========================================================

    notes = (
        data.get(
            "notes"
        )
        or []
    )

    if notes:

        with st.expander(
            f"Notas de {sport}"
        ):

            for note in notes:

                st.write(
                    f"• {note}"
                )

    st.divider()


# ============================================================
# MLB: GANADOR FINAL Y F5
# ============================================================

st.header(
    "⚾ MLB — mercados"
)

mlb_history = [
    row
    for row in history_rows
    if str(
        row.get(
            "sport",
            ""
        )
    ).upper()
    == "MLB"
]

final_rows = [
    row
    for row in mlb_history
    if str(
        row.get(
            "market",
            ""
        )
    ).lower()
    == "ganador del partido"
]

f5_rows = [
    row
    for row in mlb_history
    if (
        "5"
        in str(
            row.get(
                "market",
                ""
            )
        )
        or
        "f5"
        in str(
            row.get(
                "market",
                ""
            )
        ).lower()
    )
]

m1, m2 = st.columns(
    2
)

with m1:

    st.subheader(
        "🏆 Ganador final"
    )

    if final_rows:

        latest_final = (
            final_rows[-1]
        )

        st.metric(
            "Última selección",
            latest_final.get(
                "selection",
                "—",
            ),
        )

        st.write(
            "Probabilidad:",
            pct(
                latest_final.get(
                    "model_probability"
                )
            ),
        )

        st.write(
            "Resultado:",
            (
                result_icon(
                    latest_final.get(
                        "status"
                    )
                )
                + " "
                + str(
                    latest_final.get(
                        "status",
                        "PENDIENTE",
                    )
                )
            ),
        )

    else:

        st.caption(
            "Todavía no hay selección "
            "de ganador final."
        )


with m2:

    st.subheader(
        "5️⃣ Primeras 5 entradas"
    )

    if f5_rows:

        latest_f5 = (
            f5_rows[-1]
        )

        st.metric(
            "Última selección",
            latest_f5.get(
                "selection",
                "—",
            ),
        )

        st.write(
            "Probabilidad:",
            pct(
                latest_f5.get(
                    "model_probability"
                )
            ),
        )

        st.write(
            "Resultado:",
            (
                result_icon(
                    latest_f5.get(
                        "status"
                    )
                )
                + " "
                + str(
                    latest_f5.get(
                        "status",
                        "PENDIENTE",
                    )
                )
            ),
        )

    else:

        st.caption(
            "Todavía no hay selección F5."
        )


# ============================================================
# HISTORIAL
# ============================================================

st.divider()

st.header(
    "📚 Historial de predicciones"
)

won = sum(
    row.get(
        "status"
    )
    == "GANADA"
    for row in history_rows
)

lost = sum(
    row.get(
        "status"
    )
    == "PERDIDA"
    for row in history_rows
)

ties = sum(
    row.get(
        "status"
    )
    == "EMPATE"
    for row in history_rows
)

pending = sum(
    row.get(
        "status"
    )
    == "PENDIENTE"
    for row in history_rows
)

resolved = (
    won
    + lost
)

accuracy = (
    100.0
    * won
    / resolved
    if resolved
    else 0.0
)

h1, h2, h3, h4, h5 = (
    st.columns(
        5
    )
)

h1.metric(
    "Ganadas",
    won,
)

h2.metric(
    "Perdidas",
    lost,
)

h3.metric(
    "Empates",
    ties,
)

h4.metric(
    "Pendientes",
    pending,
)

h5.metric(
    "Efectividad",
    (
        f"{accuracy:.1f}%"
        if resolved
        else "—"
    ),
)


# ============================================================
# EFECTIVIDAD GANADOR FINAL / F5
# ============================================================

st.subheader(
    "Resultados MLB por mercado"
)


def market_stats(
    rows,
):

    w = sum(
        row.get(
            "status"
        )
        == "GANADA"
        for row in rows
    )

    l = sum(
        row.get(
            "status"
        )
        == "PERDIDA"
        for row in rows
    )

    p = sum(
        row.get(
            "status"
        )
        == "PENDIENTE"
        for row in rows
    )

    resolved_market = (
        w
        + l
    )

    rate = (
        100.0
        * w
        / resolved_market
        if resolved_market
        else 0.0
    )

    return (
        w,
        l,
        p,
        rate,
    )


fw, fl, fp, fr = market_stats(
    final_rows
)

f5w, f5l, f5p, f5r = market_stats(
    f5_rows
)

r1, r2 = st.columns(
    2
)

with r1:

    st.markdown(
        "### 🏆 GANADOR FINAL"
    )

    a, b, c = st.columns(
        3
    )

    a.metric(
        "Ganadas",
        fw,
    )

    b.metric(
        "Perdidas",
        fl,
    )

    c.metric(
        "Pendientes",
        fp,
    )

    st.metric(
        "Efectividad",
        (
            f"{fr:.1f}%"
            if fw + fl
            else "—"
        ),
    )


with r2:

    st.markdown(
        "### 5️⃣ F5"
    )

    a, b, c = st.columns(
        3
    )

    a.metric(
        "Ganadas",
        f5w,
    )

    b.metric(
        "Perdidas",
        f5l,
    )

    c.metric(
        "Pendientes",
        f5p,
    )

    st.metric(
        "Efectividad",
        (
            f"{f5r:.1f}%"
            if f5w + f5l
            else "—"
        ),
    )


# ============================================================
# TABLA DE HISTORIAL
# ============================================================

if history_rows:

    st.subheader(
        "Últimas predicciones"
    )

    table = []

    for row in reversed(
        history_rows[-100:]
    ):

        table.append(
            {
                "Fecha":
                    str(
                        row.get(
                            "created_at",
                            ""
                        )
                    )[:19],

                "Deporte":
                    row.get(
                        "sport"
                    ),

                "Partido":
                    row.get(
                        "matchup"
                    ),

                "Mercado":
                    row.get(
                        "market"
                    ),

                "Selección":
                    row.get(
                        "selection"
                    ),

                "Probabilidad":
                    pct(
                        row.get(
                            "model_probability"
                        )
                    ),

                "Calidad":
                    (
                        f"{row.get('data_quality')}%"
                        if row.get(
                            "data_quality"
                        )
                        is not None
                        else "—"
                    ),

                "Resultado":
                    (
                        result_icon(
                            row.get(
                                "status"
                            )
                        )
                        + " "
                        + str(
                            row.get(
                                "status",
                                "PENDIENTE",
                            )
                        )
                    ),

                "Marcador final":
                    (
                        (
                            f"{row.get('away_score')} - "
                            f"{row.get('home_score')}"
                        )
                        if (
                            row.get(
                                "away_score"
                            )
                            is not None
                            and
                            row.get(
                                "home_score"
                            )
                            is not None
                        )
                        else "—"
                    ),
            }
        )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "El historial comenzará a llenarse "
        "cuando el motor haga su primera selección."
    )


# ============================================================
# PIE
# ============================================================

st.divider()

st.caption(
    "El motor analiza los partidos antes de seleccionar "
    "una apuesta. Una probabilidad alta no garantiza "
    "el resultado de un evento deportivo."
)
