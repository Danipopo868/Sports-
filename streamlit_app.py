from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st


# ============================================================
# CONFIGURACION
# ============================================================

ROOT = Path(__file__).resolve().parent

STATE_FILE = ROOT / "dashboard_data" / "state.json"
LATEST_FILE = ROOT / "dashboard_data" / "latest.json"

SPORT_NAMES = {
    "MLB": "⚾ MLB",
    "NFL": "🏈 NFL",
    "NBA": "🏀 NBA",
}


st.set_page_config(
    page_title="Sports Edge",
    page_icon="⚾",
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
        radial-gradient(circle at 50% -20%, #172d46 0%, #090f18 42%, #05080d 75%);
}

.block-container {
    max-width: 1180px;
    padding-top: 1rem;
    padding-bottom: 3rem;
}

h1, h2, h3 {
    letter-spacing: -0.03em;
}

[data-testid="stMetric"] {
    background: rgba(15, 24, 36, 0.92);
    border: 1px solid #29384b;
    border-radius: 15px;
    padding: 14px;
}

.pred-card {
    background: rgba(12, 20, 31, 0.94);
    border: 1px solid #2b394a;
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 16px;
}

.rank {
    font-size: 1.15rem;
    font-weight: 800;
}

.winner {
    font-size: 1.45rem;
    font-weight: 900;
    margin-top: 8px;
}

.muted {
    color: #95a4b7;
}

.good {
    font-weight: 800;
}

.section-title {
    font-size: 1.35rem;
    font-weight: 850;
    margin-top: 1.3rem;
    margin-bottom: .7rem;
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
# LEER ARCHIVO
# ============================================================

def get_data_file() -> Path | None:

    if STATE_FILE.exists():
        return STATE_FILE

    if LATEST_FILE.exists():
        return LATEST_FILE

    return None


@st.cache_data(ttl=5)
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
# FORMATO
# ============================================================

def pct(value: Any) -> str:

    try:
        number = float(value)

        if number <= 1:
            number *= 100

        return f"{number:.1f}%"

    except (TypeError, ValueError):
        return "—"


def display_time(value: str) -> str:

    try:

        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return parsed.strftime(
            "%d/%m/%Y · %I:%M %p"
        )

    except Exception:
        return value or "Sin fecha"


# ============================================================
# EXTRAER TOP 3 DESDE NOTES
# ============================================================

def parse_mlb_top3(
    notes: list[str],
) -> list[dict[str, Any]]:

    predictions: list[dict[str, Any]] = []

    current: dict[str, Any] | None = None

    for raw in notes:

        line = str(raw).strip()

        if not line:
            continue


        rank_match = re.match(
            r"#([123])\s+(.+?)\s+@\s+(.+)",
            line,
        )

        if rank_match:

            if current:
                predictions.append(current)

            current = {
                "rank": int(
                    rank_match.group(1)
                ),
                "away": rank_match.group(2),
                "home": rank_match.group(3),
            }

            continue


        if current is None:
            continue


        if line.startswith(
            "GANADOR PREDICHO:"
        ):

            current["winner"] = line.split(
                ":",
                1,
            )[1].strip()

            continue


        if line.startswith(
            "Probabilidad estimada:"
        ):

            current["probability"] = (
                line.split(
                    ":",
                    1,
                )[1].strip()
            )

            continue


        if line.startswith(
            "F5 PREDICHO:"
        ):

            current["f5_winner"] = line.split(
                ":",
                1,
            )[1].strip()

            continue


        if line.startswith(
            "Probabilidad F5:"
        ):

            current["f5_probability"] = (
                line.split(
                    ":",
                    1,
                )[1].strip()
            )

            continue


        if line.startswith(
            "Abridor visitante:"
        ):

            current["away_starter"] = (
                line.split(
                    ":",
                    1,
                )[1].strip()
            )

            continue


        if line.startswith(
            "Abridor local:"
        ):

            current["home_starter"] = (
                line.split(
                    ":",
                    1,
                )[1].strip()
            )

            continue


        if line.startswith(
            "Bateo visitante vs abridor:"
        ):

            current["away_bvp"] = (
                line.split(
                    ":",
                    1,
                )[1].strip()
            )

            continue


        if line.startswith(
            "Bateo local vs abridor:"
        ):

            current["home_bvp"] = (
                line.split(
                    ":",
                    1,
                )[1].strip()
            )

            continue


    if current:
        predictions.append(current)


    predictions.sort(
        key=lambda item:
            item.get("rank", 99)
    )

    return predictions[:3]


# ============================================================
# TARJETAS TOP 3 MLB
# ============================================================

def render_mlb_top3(
    result: dict[str, Any],
) -> None:

    notes = result.get("notes") or []

    predictions = parse_mlb_top3(
        notes
    )

    st.markdown(
        '<div class="section-title">🏆 TOP 3 GANADORES MLB</div>',
        unsafe_allow_html=True,
    )


    if not predictions:

        st.info(
            "Todavía no hay predicciones Top 3 MLB disponibles."
        )

        return


    for prediction in predictions:

        rank = prediction.get(
            "rank",
            "—",
        )

        away = prediction.get(
            "away",
            "Visitante",
        )

        home = prediction.get(
            "home",
            "Local",
        )

        winner = prediction.get(
            "winner",
            "Sin predicción",
        )

        probability = prediction.get(
            "probability",
            "—",
        )

        f5_winner = prediction.get(
            "f5_winner",
            "Sin datos",
        )

        f5_probability = prediction.get(
            "f5_probability",
            "—",
        )


        st.markdown(
            f"""
<div class="pred-card">

<div class="rank">
#{rank} · {away} @ {home}
</div>

<div class="winner">
🏆 GANADOR: {winner}
</div>

<div class="muted">
Probabilidad estimada: <b>{probability}</b>
</div>

</div>
""",
            unsafe_allow_html=True,
        )


        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "Ganador juego completo",
                winner,
            )

            st.metric(
                "Probabilidad",
                probability,
            )


        with col2:

            st.metric(
                "F5 predicho",
                f5_winner,
            )

            st.metric(
                "Probabilidad F5",
                f5_probability,
            )


        away_starter = prediction.get(
            "away_starter"
        )

        home_starter = prediction.get(
            "home_starter"
        )

        away_bvp = prediction.get(
            "away_bvp"
        )

        home_bvp = prediction.get(
            "home_bvp"
        )


        with st.expander(
            "Ver análisis del partido"
        ):

            if away_starter:
                st.write(
                    f"**Abridor visitante:** {away_starter}"
                )

            if home_starter:
                st.write(
                    f"**Abridor local:** {home_starter}"
                )

            if away_bvp:
                st.write(
                    f"**Bateo visitante vs abridor:** {away_bvp}"
                )

            if home_bvp:
                st.write(
                    f"**Bateo local vs abridor:** {home_bvp}"
                )


        st.divider()


# ============================================================
# APUESTA CON VALOR
# ============================================================

def render_candidate(
    candidate: dict[str, Any],
) -> None:

    st.success(
        "✅ APOSTAR — VALOR DETECTADO"
    )

    st.subheader(
        candidate.get(
            "selection",
            "Selección no disponible",
        )
    )

    st.caption(
        f"{candidate.get('matchup', '')} · "
        f"{candidate.get('market', '')}"
    )


    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Probabilidad",
        pct(
            candidate.get(
                "model_probability"
            )
        ),
    )

    try:
        odds = (
            f"{float(candidate.get('decimal_odds', 0)):.2f}"
        )
    except Exception:
        odds = "—"

    c2.metric(
        "Mejor cuota",
        odds,
    )

    c3.metric(
        "Edge",
        pct(
            candidate.get(
                "edge"
            )
        ),
    )

    c4.metric(
        "EV",
        pct(
            candidate.get(
                "expected_value"
            )
        ),
    )


# ============================================================
# NO APOSTAR
# ============================================================

def render_no_bet(
    result: dict[str, Any],
) -> None:

    st.warning(
        "⚠️ NO APOSTAR"
    )

    best = result.get(
        "best_observed"
    )

    if best:

        with st.expander(
            "Ver mejor opción descartada"
        ):

            st.write(
                f"**{best.get('selection', 'Sin selección')}**"
            )

            st.caption(
                f"{best.get('matchup', '')} · "
                f"{best.get('market', '')}"
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Probabilidad",
                pct(
                    best.get(
                        "model_probability"
                    )
                ),
            )

            c2.metric(
                "Edge",
                pct(
                    best.get(
                        "edge"
                    )
                ),
            )

            c3.metric(
                "Calidad",
                f"{best.get('data_quality', 0)}/100",
            )


# ============================================================
# RESULTADO POR DEPORTE
# ============================================================

def render_sport(
    sport: str,
    result: dict[str, Any],
) -> None:

    error = result.get(
        "error"
    )

    if error:

        st.error(
            "DATOS INCOMPLETOS"
        )

        st.write(
            error
        )

        return


    if sport == "MLB":

        render_mlb_top3(
            result
        )

        st.markdown(
            '<div class="section-title">💰 DECISIÓN DE APUESTA</div>',
            unsafe_allow_html=True,
        )


    if result.get(
        "recommendation"
    ):

        render_candidate(
            result[
                "recommendation"
            ]
        )

    else:

        render_no_bet(
            result
        )


    st.caption(
        f"Partidos revisados: "
        f"{result.get('games', 0)} · "
        f"Cuotas válidas: "
        f"{result.get('quotes', 0)}"
    )


# ============================================================
# TITULO
# ============================================================

title, action = st.columns(
    [5, 1]
)

with title:

    st.title(
        "Sports Edge"
    )

    st.caption(
        "Predicciones deportivas · "
        "ganador del juego · F5 · "
        "valor esperado"
    )


with action:

    if st.button(
        "🔄 Actualizar",
        use_container_width=True,
    ):

        st.cache_data.clear()

        st.rerun()


# ============================================================
# CARGAR DATA
# ============================================================

DATA_FILE = get_data_file()


if DATA_FILE is None:

    st.info(
        "Aún no existe "
        "`dashboard_data/state.json` "
        "ni `dashboard_data/latest.json`.\n\n"
        "Cuando el motor escriba su primer "
        "reporte, aparecerán aquí las "
        "predicciones."
    )

    st.stop()


snapshot = load_snapshot(
    str(DATA_FILE),
    DATA_FILE.stat().st_mtime,
)


st.success(
    "● Datos reales · motor conectado"
)


st.caption(
    "Actualizado: "
    f"{display_time(snapshot.get('generated_at', ''))} "
    f"· Escaneo #{snapshot.get('scan_number', '—')}"
)


# ============================================================
# TABS
# ============================================================

tabs = st.tabs(
    [
        SPORT_NAMES["MLB"],
        SPORT_NAMES["NFL"],
        SPORT_NAMES["NBA"],
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

        result = (
            snapshot
            .get(
                "sports",
                {},
            )
            .get(
                sport,
                {},
            )
        )

        render_sport(
            sport,
            result,
        )


# ============================================================
# PIE
# ============================================================

st.markdown(
    """
<div class="footer-note">
Las probabilidades son estimaciones matemáticas,
no garantías. El ganador del juego y el F5 se
muestran separados de la decisión APOSTAR / NO APOSTAR.
</div>
""",
    unsafe_allow_html=True,
)
