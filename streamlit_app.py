from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st


# ============================================================
# CONFIGURACIÓN
# ============================================================

ROOT = Path(__file__).resolve().parent

DATA_FILE = ROOT / "reports" / "latest.json"

HISTORY_FILE = (
    ROOT
    / "dashboard_data"
    / "prediction_history.json"
)

DEFAULT_STAKE = 100.0


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

    .money-box {
        margin-top: 14px;
        margin-bottom: 14px;
        padding: 16px;
        border-radius: 16px;
        border: 1px solid #2e435b;
        background: rgba(11, 20, 31, 0.95);
    }

    .money-title {
        color: #9eabbc;
        font-size: .82rem;
        font-weight: 700;
        margin-bottom: 4px;
    }

    .money-value {
        color: #ffffff;
        font-size: 1.35rem;
        font-weight: 800;
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
            if isinstance(data, list)
            else []
        )

    except Exception:
        return []


# ============================================================
# FORMATOS
# ============================================================

def pct(
    value: Any,
) -> str:

    try:

        number = float(value)

        if abs(number) > 1:
            return f"{number:.1f}%"

        return f"{number * 100:.1f}%"

    except (
        TypeError,
        ValueError,
    ):
        return "—"


def probability_number(
    value: Any,
) -> float | None:

    try:

        number = float(value)

        if abs(number) <= 1:
            number *= 100

        return number

    except (
        TypeError,
        ValueError,
    ):
        return None


def money(
    value: Any,
    signed: bool = False,
) -> str:

    try:

        number = float(value)

        if signed:
            return f"{number:+,.2f}"

        return f"${number:,.2f}"

    except (
        TypeError,
        ValueError,
    ):
        return "—"


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
# DINERO DE UNA FILA DEL HISTORIAL
# ============================================================

def row_stake(
    row: dict[str, Any],
) -> float:

    try:
        return float(
            row.get(
                "stake",
                DEFAULT_STAKE,
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return DEFAULT_STAKE


def row_odds(
    row: dict[str, Any],
) -> float:

    try:
        return float(
            row.get(
                "odds",
                0.0,
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def row_profit_loss(
    row: dict[str, Any],
) -> float | None:

    stored = row.get(
        "profit_loss"
    )

    if stored is not None:

        try:
            return float(stored)

        except (
            TypeError,
            ValueError,
        ):
            pass

    result = str(
        row.get(
            "result",
            ""
        )
    ).upper()

    stake = row_stake(row)
    odds = row_odds(row)

    if result == "GANADA":

        if odds > 1.0:
            return (
                stake
                * odds
                - stake
            )

        return None

    if result == "PERDIDA":
        return -stake

    if result == "EMPATE":
        return 0.0

    return None


# ============================================================
# RESUMEN DEL HISTORIAL
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
        row.get("result")
        == "GANADA"
        for row in filtered
    )

    lost = sum(
        row.get("result")
        == "PERDIDA"
        for row in filtered
    )

    tied = sum(
        row.get("result")
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

    decisions = won + lost

    win_rate = (
        won / decisions
        if decisions
        else 0.0
    )

    settled_rows = [
        row
        for row in filtered
        if str(
            row.get(
                "result",
                ""
            )
        ).upper()
        in {
            "GANADA",
            "PERDIDA",
            "EMPATE",
        }
    ]

    total_staked = sum(
        row_stake(row)
        for row in settled_rows
    )

    profit_loss = sum(
        value
        for row in settled_rows
        if (
            value
            := row_profit_loss(row)
        )
        is not None
    )

    roi = (
        profit_loss
        / total_staked
        if total_staked
        else 0.0
    )

    return {
        "won": won,
        "lost": lost,
        "tied": tied,
        "pending": pending,
        "win_rate": win_rate,
        "total_staked": total_staked,
        "profit_loss": profit_loss,
        "roi": roi,
    }


# ============================================================
# CABECERA DEL DEPORTE
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
# MÉTRICAS DEL DEPORTE
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
        int(stats["won"]),
    )

    c2.metric(
        "❌ Perdidas",
        int(stats["lost"]),
    )

    c3.metric(
        "💰 Neto",
        money(
            stats["profit_loss"],
            signed=True,
        ),
    )

    c4.metric(
        "💵 Apostado",
        money(
            stats["total_staked"]
        ),
    )

    c5.metric(
        "📈 ROI",
        (
            f"{float(stats['roi']) * 100:+.1f}%"
            if stats["total_staked"]
            else "—"
        ),
    )

    st.caption(
        f"Empates: {int(stats['tied'])} · "
        f"Pendientes: {int(stats['pending'])} · "
        f"Efectividad: "
        f"{float(stats['win_rate']) * 100:.1f}%"
        if (
            int(stats["won"])
            + int(stats["lost"])
        )
        else (
            f"Empates: {int(stats['tied'])} · "
            f"Pendientes: {int(stats['pending'])} · "
            "Efectividad: —"
        )
    )

    st.write("")


# ============================================================
# CANDIDATO / APUESTA RECOMENDADA
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
        st.columns(4)
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

        decimal_odds = float(
            candidate.get(
                "decimal_odds",
                0.0,
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):

        decimal_odds = 0.0

    odds.metric(
        "Mejor cuota",
        (
            f"{decimal_odds:.2f}"
            if decimal_odds > 1.0
            else "SIN CUOTA"
        ),
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

    # ========================================================
    # CUÁNTO PAGARÍA UNA APUESTA DE $100
    # ========================================================

    if decimal_odds > 1.0:

        potential_return = (
            DEFAULT_STAKE
            * decimal_odds
        )

        potential_profit = (
            potential_return
            - DEFAULT_STAKE
        )

        p1, p2, p3 = st.columns(
            3
        )

        p1.metric(
            "💵 APUESTAS",
            money(
                DEFAULT_STAKE
            ),
        )

        p2.metric(
            "🏦 SI GANA RECIBES",
            money(
                potential_return
            ),
        )

        p3.metric(
            "💰 GANANCIA NETA",
            f"${potential_profit:+,.2f}",
        )

    else:

        st.warning(
            "💵 PAGO NO DISPONIBLE — "
            "esta recomendación no tiene una cuota válida "
            "del mercado. No se inventará una ganancia."
        )

    detail_left, detail_right = (
        st.columns(2)
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

        col1, col2, col3 = st.columns(
            3
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
                recommendations[:2],
                start=1,
            ):

                render_candidate(
                    candidate,
                    index,
                )

                if (
                    index
                    < len(
                        recommendations[:2]
                    )
                ):
                    st.divider()

            if len(
                recommendations
            ) == 1:

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
# ANÁLISIS POR PROBABILIDAD
# ============================================================

def probability_analysis(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    bands = [
        ("<60%", 0, 60),
        ("60–64%", 60, 65),
        ("65–69%", 65, 70),
        ("70–74%", 70, 75),
        ("75–79%", 75, 80),
        ("80–84%", 80, 85),
        ("85–89%", 85, 90),
        ("90%+", 90, 101),
    ]

    output: list[
        dict[str, Any]
    ] = []

    for (
        label,
        low,
        high,
    ) in bands:

        selected = []

        for row in rows:

            result = str(
                row.get(
                    "result",
                    ""
                )
            ).upper()

            if result not in {
                "GANADA",
                "PERDIDA",
                "EMPATE",
            }:
                continue

            probability = (
                probability_number(
                    row.get(
                        "probability"
                    )
                )
            )

            if probability is None:
                continue

            if low <= probability < high:
                selected.append(row)

        if not selected:
            continue

        won = sum(
            row.get("result")
            == "GANADA"
            for row in selected
        )

        lost = sum(
            row.get("result")
            == "PERDIDA"
            for row in selected
        )

        tied = sum(
            row.get("result")
            == "EMPATE"
            for row in selected
        )

        decisions = won + lost

        total_staked = sum(
            row_stake(row)
            for row in selected
        )

        profit_loss = sum(
            value
            for row in selected
            if (
                value
                := row_profit_loss(row)
            )
            is not None
        )

        roi = (
            profit_loss
            / total_staked
            if total_staked
            else 0.0
        )

        output.append(
            {
                "Probabilidad": label,
                "Apuestas": len(selected),
                "Ganadas": won,
                "Perdidas": lost,
                "Empates": tied,
                "Efectividad": (
                    f"{won / decisions * 100:.1f}%"
                    if decisions
                    else "—"
                ),
                "Apostado": money(
                    total_staked
                ),
                "Neto": f"${profit_loss:+,.2f}",
                "ROI": (
                    f"{roi * 100:+.1f}%"
                    if total_staked
                    else "—"
                ),
            }
        )

    return output


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
    str(DATA_FILE),
    DATA_FILE.stat().st_mtime,
)


# ============================================================
# HISTORIAL
# ============================================================

if HISTORY_FILE.exists():

    history_rows = load_history(
        str(HISTORY_FILE),
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
# RESULTADOS GENERALES
# ============================================================

st.subheader(
    "💰 Rendimiento del sistema"
)

general = history_stats(
    history_rows
)

g1, g2, g3, g4, g5 = st.columns(
    5
)

g1.metric(
    "💵 Total apostado",
    money(
        general[
            "total_staked"
        ]
    ),
)

g2.metric(
    "💰 Ganancia/Pérdida",
    f"${float(general['profit_loss']):+,.2f}",
)

g3.metric(
    "📈 ROI",
    (
        f"{float(general['roi']) * 100:+.1f}%"
        if general[
            "total_staked"
        ]
        else "—"
    ),
)

g4.metric(
    "✅ Ganadas",
    int(
        general["won"]
    ),
)

g5.metric(
    "❌ Perdidas",
    int(
        general["lost"]
    ),
)

st.caption(
    f"Stake fijo: ${DEFAULT_STAKE:.2f} por apuesta · "
    f"Empates: {int(general['tied'])} · "
    f"Pendientes: {int(general['pending'])} · "
    f"Efectividad: "
    f"{float(general['win_rate']) * 100:.1f}%"
    if (
        int(general["won"])
        + int(general["lost"])
    )
    else (
        f"Stake fijo: ${DEFAULT_STAKE:.2f} por apuesta · "
        f"Empates: {int(general['tied'])} · "
        f"Pendientes: {int(general['pending'])} · "
        "Efectividad: —"
    )
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
# RENDIMIENTO POR PROBABILIDAD
# ============================================================

st.divider()

st.subheader(
    "📊 Rendimiento por porcentaje"
)

probability_table = (
    probability_analysis(
        history_rows
    )
)

if probability_table:

    st.dataframe(
        probability_table,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.caption(
        "Cuando haya apuestas terminadas aparecerá aquí "
        "cuánto dinero producen los diferentes rangos "
        "de probabilidad."
    )


# ============================================================
# HISTORIAL
# ============================================================

st.divider()

st.subheader(
    "📋 Historial de apuestas"
)

if history_rows:

    table = []

    for row in reversed(
        history_rows[-100:]
    ):

        stake = row_stake(row)
        odds = row_odds(row)

        potential_return = (
            stake * odds
            if odds > 1.0
            else None
        )

        potential_profit = (
            potential_return - stake
            if potential_return
            is not None
            else None
        )

        actual_pl = (
            row_profit_loss(row)
        )

        table.append(
            {
                "Fecha": display_time(
                    str(
                        row.get(
                            "created_at",
                            ""
                        )
                    )
                ),
                "Deporte": row.get(
                    "sport"
                ),
                "Partido": row.get(
                    "matchup"
                ),
                "Mercado": row.get(
                    "market"
                ),
                "Selección": row.get(
                    "selection"
                ),
                "% a favor": pct(
                    row.get(
                        "probability"
                    )
                ),
                "Casa": row.get(
                    "bookmaker",
                    "—",
                ),
                "Cuota": (
                    f"{odds:.2f}"
                    if odds > 1.0
                    else "SIN CUOTA"
                ),
                "Apuesta": money(
                    stake
                ),
                "Cobro si gana": (
                    money(
                        potential_return
                    )
                    if potential_return
                    is not None
                    else "—"
                ),
                "Ganancia si gana": (
                    f"${potential_profit:+,.2f}"
                    if potential_profit
                    is not None
                    else "—"
                ),
                "Resultado": (
                    row.get(
                        "result"
                    )
                    or "PENDIENTE"
                ),
                "Ganancia/Pérdida": (
                    f"${actual_pl:+,.2f}"
                    if actual_pl
                    is not None
                    else "—"
                ),
                "Marcador": row.get(
                    "final_score",
                    "—",
                ),
            }
        )

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
        f'Cada recomendación usa una apuesta fija de '
        f'${DEFAULT_STAKE:.2f}. '
        'Cuando existe una cuota válida, el panel calcula '
        'automáticamente cuánto cobrarías y la ganancia neta. '
        'Una GANADA suma la ganancia correspondiente a la cuota; '
        'una PERDIDA resta $100; un EMPATE tiene resultado neto $0. '
        'Las probabilidades son estimaciones, no garantías.'
        '</div>'
    ),
    unsafe_allow_html=True,
)
