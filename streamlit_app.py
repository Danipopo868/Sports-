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
HISTORY_FILE = ROOT / "dashboard_data" / "prediction_history.json"

DEFAULT_STAKE = 100.0


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


st.markdown(
    """
    <style>

    :root {
        /* ================================================
           CAMBIA SOLO ESTOS NÚMEROS
           ================================================ */

        --sport-width: 72%;
        --sport-height: 250px;
        --sport-font: 3000px;
        --sport-gap: 10px;
        --sport-radius: 22px;
    }


    .stApp {
        background:
          linear-gradient(
            rgba(3, 8, 15, 0.80),
            rgba(3, 8, 15, 0.90)
          ),
          url("https://img.mlbstatic.com/mlb-photos/image/upload/ar_16:9,g_auto,q_auto:good,w_2048,c_fill,f_jpg/v1/people/670541/action/vertical/current");

        background-size: cover;
        background-position: center top;
        background-attachment: fixed;
        background-repeat: no-repeat;
    }


    .block-container {
        max-width: 1180px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }


    [data-testid="stMetric"] {
        background: rgba(15, 24, 36, 0.92);
        border: 1px solid #273547;
        border-radius: 16px;
        padding: 14px 16px;
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
        color: #b3bdca;
        font-size: .9rem;
    }


    .sport-header {
        display: flex;
        align-items: center;
        gap: 18px;
        padding: 18px 20px;
        margin-bottom: 18px;
        background: rgba(8, 16, 26, .88);
        border: 1px solid rgba(80, 110, 145, .50);
        border-radius: 18px;
        backdrop-filter: blur(8px);
    }


    .sport-logo {
        width: 78px;
        height: 78px;
        object-fit: contain;
    }


    .sport-code {
        font-size: 1.65rem;
        font-weight: 800;
        color: white;
    }


    .sport-name {
        color: #b0bac8;
        font-size: .95rem;
    }


    .footer-note {
        margin-top: 2rem;
        color: #b1bcc9;
        border-top: 1px solid #334253;
        padding-top: 1rem;
        font-size: .88rem;
        background: rgba(4, 10, 18, .55);
        padding: 15px;
        border-radius: 12px;
    }


    [data-testid="stDataFrame"] {
        background: rgba(5, 12, 20, .88);
        border-radius: 14px;
    }


    /* ======================================================
       MLB / NFL / BASKETBALL
       PESTAÑAS INTERNAS — NO ABREN OTRA PÁGINA
       ====================================================== */

    div[role="tablist"],
    [data-baseweb="tab-list"] {
        width: var(--sport-width) !important;

        margin-left: auto !important;
        margin-right: auto !important;

        display: flex !important;
        justify-content: center !important;
        align-items: center !important;

        gap: var(--sport-gap) !important;

        margin-top: 24px !important;
        margin-bottom: 30px !important;
    }


    button[role="tab"] {
        flex: 1 1 0 !important;

        height: var(--sport-height) !important;

        min-width: 0 !important;

        display: flex !important;
        justify-content: center !important;
        align-items: center !important;

        padding: 8px 12px !important;

        border-radius:
            var(--sport-radius) !important;

        border:
            3px solid
            rgba(255,255,255,.65) !important;

        overflow: visible !important;
    }


    button[role="tab"] p,
    button[role="tab"] span {
        font-size:
            var(--sport-font) !important;

        font-weight: 900 !important;

        color: white !important;

        text-align: center !important;

        white-space: nowrap !important;

        margin: 0 !important;

        text-shadow:
            0 2px 7px
            rgba(0,0,0,.90) !important;
    }


    /* MLB AZUL */

    button[role="tab"]:nth-of-type(1) {
        background:
            linear-gradient(
                135deg,
                #003cff,
                #008cff,
                #00ddff
            ) !important;

        box-shadow:
            0 0 18px #008cff,
            0 0 38px rgba(0,140,255,.65) !important;
    }


    /* NFL ROJO */

    button[role="tab"]:nth-of-type(2) {
        background:
            linear-gradient(
                135deg,
                #ff0000,
                #ff351f,
                #ff8500
            ) !important;

        box-shadow:
            0 0 18px #ff3b1f,
            0 0 38px rgba(255,59,31,.65) !important;
    }


    /* BASKETBALL NARANJA */

    button[role="tab"]:nth-of-type(3) {
        background:
            linear-gradient(
                135deg,
                #ff6500,
                #ff9a00,
                #ffd800
            ) !important;

        box-shadow:
            0 0 18px #ffae00,
            0 0 38px rgba(255,174,0,.65) !important;
    }


    /* SELECCIONADO */

    button[role="tab"][aria-selected="true"] {
        transform: scale(1.06) !important;

        border:
            4px solid white !important;

        box-shadow:
            0 0 15px white,
            0 0 35px rgba(255,255,255,.70) !important;
    }


    /* SAMSUNG */

    @media (max-width: 800px) {

        :root {
            --sport-width: 98%;
            --sport-height: 82px;
            --sport-font: 18px;
            --sport-gap: 6px;
            --sport-radius: 16px;
        }

        button[role="tab"] {
            padding:
                4px 4px !important;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CARGA
# ============================================================

@st.cache_data(ttl=30)
def load_snapshot(
    path: str,
    modified: float,
) -> dict[str, Any]:

    del modified

    try:
        return json.loads(
            Path(path).read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}


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

        return data if isinstance(data, list) else []

    except Exception:
        return []


# ============================================================
# FORMATOS
# ============================================================

def pct(value: Any) -> str:

    try:
        number = float(value)

        if abs(number) > 1:
            return f"{number:.1f}%"

        return f"{number * 100:.1f}%"

    except (TypeError, ValueError):
        return "—"


def probability_percent(
    value: Any,
) -> float | None:

    try:
        number = float(value)

        if abs(number) <= 1:
            number *= 100

        return number

    except (TypeError, ValueError):
        return None


def money(
    value: Any,
    signed: bool = False,
) -> str:

    if value is None:
        return "—"

    try:
        number = float(value)

    except (TypeError, ValueError):
        return "—"

    if signed:
        return f"${number:+,.2f}"

    return f"${number:,.2f}"


def display_time(value: str) -> str:

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

    except (TypeError, ValueError):
        return value or "Sin fecha"


def valid_odds(
    value: Any,
) -> float | None:

    try:
        odds = float(value)

    except (TypeError, ValueError):
        return None

    return odds if odds > 1.0 else None


def kalshi_quote_text(
    odds: float | None,
) -> str:

    if odds is None:
        return "—"

    cents = 100.0 / odds

    return (
        f"{cents:.0f}¢ "
        f"({odds:.3f}x)"
    )


# ============================================================
# FINANZAS
# ============================================================

def row_has_financial_data(
    row: dict[str, Any],
) -> bool:

    odds = valid_odds(
        row.get("odds")
    )

    try:
        stake_raw = row.get("stake")

        if stake_raw is None:
            return False

        stake = float(stake_raw)

    except (TypeError, ValueError):
        return False

    return (
        odds is not None
        and stake > 0
    )


def row_stake(
    row: dict[str, Any],
) -> float | None:

    if not row_has_financial_data(row):
        return None

    try:
        return float(
            row.get("stake")
        )

    except (TypeError, ValueError):
        return None


def row_profit_loss(
    row: dict[str, Any],
) -> float | None:

    if not row_has_financial_data(row):
        return None

    stored = row.get(
        "profit_loss"
    )

    if stored is not None:

        try:
            return float(stored)

        except (TypeError, ValueError):
            pass

    result = str(
        row.get("result") or ""
    ).upper()

    stake = row_stake(row)

    odds = valid_odds(
        row.get("odds")
    )

    if stake is None or odds is None:
        return None

    if result == "GANADA":
        return stake * odds - stake

    if result == "PERDIDA":
        return -stake

    if result == "EMPATE":
        return 0.0

    return None


def potential_return(
    row: dict[str, Any],
) -> float | None:

    stored = row.get(
        "potential_return"
    )

    if stored is not None:

        try:
            return float(stored)

        except (TypeError, ValueError):
            pass

    stake = row_stake(row)

    odds = valid_odds(
        row.get("odds")
    )

    if stake is None or odds is None:
        return None

    return stake * odds


def potential_profit(
    row: dict[str, Any],
) -> float | None:

    stored = row.get(
        "potential_profit"
    )

    if stored is not None:

        try:
            return float(stored)

        except (TypeError, ValueError):
            pass

    returned = potential_return(row)
    stake = row_stake(row)

    if returned is None or stake is None:
        return None

    return returned - stake


# ============================================================
# ESTADÍSTICAS
# ============================================================

def history_stats(
    rows: list[dict[str, Any]],
    sport: str | None = None,
) -> dict[str, Any]:

    filtered = rows

    if sport:

        filtered = [
            row
            for row in rows
            if str(
                row.get("sport") or ""
            ).upper()
            == sport.upper()
        ]

    won = sum(
        row.get("result") == "GANADA"
        for row in filtered
    )

    lost = sum(
        row.get("result") == "PERDIDA"
        for row in filtered
    )

    tied = sum(
        row.get("result") == "EMPATE"
        for row in filtered
    )

    pending = sum(
        str(
            row.get("status") or ""
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

    financial_rows = [
        row
        for row in filtered
        if (
            row.get("result")
            in {
                "GANADA",
                "PERDIDA",
                "EMPATE",
            }
            and row_has_financial_data(row)
        )
    ]

    total_staked = sum(
        row_stake(row) or 0.0
        for row in financial_rows
    )

    profit_loss = sum(
        row_profit_loss(row) or 0.0
        for row in financial_rows
    )

    roi = (
        profit_loss / total_staked
        if total_staked
        else 0.0
    )

    real_odds = sum(
        str(
            row.get("odds_source") or ""
        ).upper()
        in {
            "REAL",
            "LIVE_AT_RECOMMENDATION",
            "HISTORICAL_F5",
        }
        for row in financial_rows
    )

    estimated_odds = sum(
        str(
            row.get("odds_source") or ""
        ).upper()
        == "ESTIMADA_FULL_GAME"
        for row in financial_rows
    )

    return {
        "won": won,
        "lost": lost,
        "tied": tied,
        "pending": pending,
        "win_rate": win_rate,
        "financial_bets": len(financial_rows),
        "real_odds": real_odds,
        "estimated_odds": estimated_odds,
        "total_staked": total_staked,
        "profit_loss": profit_loss,
        "roi": roi,
    }


# ============================================================
# CABECERA DEPORTE
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
            <img class="sport-logo" src="{logo}">
            <div>
                <div class="sport-code">{sport}</div>
                <div class="sport-name">{name}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sport_stats(
    history_rows: list[dict[str, Any]],
    sport: str,
) -> None:

    stats = history_stats(
        history_rows,
        sport,
    )

    c1, c2, c3, c4 = st.columns(4)

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
        (
            money(
                stats["profit_loss"],
                signed=True,
            )
            if stats["financial_bets"]
            else "—"
        ),
    )

    c4.metric(
        "💵 Apostado",
        (
            money(
                stats["total_staked"]
            )
            if stats["financial_bets"]
            else "—"
        ),
    )

    st.caption(
        f"Empates: {stats['tied']} · "
        f"Pendientes: {stats['pending']} · "
        f"Efectividad: {stats['win_rate'] * 100:.1f}% · "
        f"Con cuota calculable: {stats['financial_bets']}"
    )


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

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Probabilidad estimada",
        pct(
            candidate.get(
                "model_probability"
            )
        ),
    )

    odds = valid_odds(
        candidate.get(
            "decimal_odds"
        )
    )

    c2.metric(
        "Cuota Kalshi",
        kalshi_quote_text(
            odds
        ),
    )

    c3.metric(
        "Ventaja del modelo",
        pct(
            candidate.get(
                "edge"
            )
        ),
    )

    c4.metric(
        "Valor esperado del modelo",
        pct(
            candidate.get(
                "expected_value"
            )
        ),
    )

    st.caption(
        "La cuota de Kalshi se usa solo para calcular "
        "Apuesta, Cobro y Ganancia. No modifica la "
        "probabilidad ni la selección del motor."
    )

    if odds is not None:

        payout = DEFAULT_STAKE * odds
        profit = payout - DEFAULT_STAKE

        f1, f2, f3 = st.columns(3)

        f1.metric(
            "💵 Apuesta",
            "$100.00",
        )

        f2.metric(
            "💳 Cobro si gana",
            money(payout),
        )

        f3.metric(
            "💰 Ganancia neta",
            money(
                profit,
                signed=True,
            ),
        )

    else:

        st.warning(
            "Kalshi no devolvió una cuota válida para este "
            "partido. La predicción se mantiene, pero todavía "
            "no se puede calcular cobro ni ganancia."
        )

    st.write(
        f"**Fuente de pago:** "
        f"{candidate.get('bookmaker', 'No disponible')}"
    )

    st.write(
        "**Calidad de datos:** "
        f"{candidate.get('data_quality', 0)}/100"
    )

    reasons = (
        candidate.get("reasons")
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
        result.get("notes")
        or [
            "Ninguna opción superó todos los filtros matemáticos y de calidad."
        ]
    )

    for note in notes:
        st.write(
            f"• {note}"
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

            for index, candidate in enumerate(
                recommendations[:2],
                start=1,
            ):

                render_candidate(
                    candidate,
                    index,
                )

                if index < len(
                    recommendations[:2]
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
        f"Cuotas Kalshi encontradas: "
        f"{result.get('kalshi_quotes', 0)}"
    )


# ============================================================
# ANÁLISIS POR PROBABILIDAD
# ============================================================

def probability_analysis(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    ranges = [
        (0, 59.999, "<60%"),
        (60, 64.999, "60–64%"),
        (65, 69.999, "65–69%"),
        (70, 74.999, "70–74%"),
        (75, 79.999, "75–79%"),
        (80, 84.999, "80–84%"),
        (85, 89.999, "85–89%"),
        (90, 1000, "90%+"),
    ]

    output = []

    for low, high, label in ranges:

        selected = []

        for row in rows:

            if row.get("result") not in {
                "GANADA",
                "PERDIDA",
                "EMPATE",
            }:
                continue

            probability = probability_percent(
                row.get(
                    "probability"
                )
            )

            if probability is None:
                continue

            if low <= probability <= high:
                selected.append(
                    row
                )

        if not selected:
            continue

        won = sum(
            row.get("result") == "GANADA"
            for row in selected
        )

        lost = sum(
            row.get("result") == "PERDIDA"
            for row in selected
        )

        tied = sum(
            row.get("result") == "EMPATE"
            for row in selected
        )

        decisions = won + lost

        financial = [
            row
            for row in selected
            if row_has_financial_data(
                row
            )
        ]

        staked = sum(
            row_stake(row) or 0
            for row in financial
        )

        net = sum(
            row_profit_loss(row) or 0
            for row in financial
        )

        roi = (
            net / staked
            if staked
            else None
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

                "Con cuota": len(financial),

                "Apostado": (
                    f"${staked:,.2f}"
                    if financial
                    else "—"
                ),

                "Neto": (
                    f"${net:+,.2f}"
                    if financial
                    else "—"
                ),

                "ROI": (
                    f"{roi * 100:+.2f}%"
                    if roi is not None
                    else "—"
                ),
            }
        )

    return output


# ============================================================
# ENCABEZADO
# ============================================================

title, action = st.columns(
    [5, 1]
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
        f' · escaneo #'
        f'{snapshot.get("scan_number", "—")}'
        '</p>'
    ),
    unsafe_allow_html=True,
)


# ============================================================
# RESULTADOS GENERALES
# ============================================================

st.subheader(
    "📊 Resultados generales"
)


general = history_stats(
    history_rows
)


g1, g2, g3, g4 = st.columns(4)


g1.metric(
    "💵 Apostado",
    (
        money(
            general["total_staked"]
        )
        if general["financial_bets"]
        else "—"
    ),
)


g2.metric(
    "💰 Ganancia/Pérdida",
    (
        money(
            general["profit_loss"],
            signed=True,
        )
        if general["financial_bets"]
        else "—"
    ),
)


g3.metric(
    "✅ Ganadas",
    int(
        general["won"]
    ),
)


g4.metric(
    "❌ Perdidas",
    int(
        general["lost"]
    ),
)


st.caption(
    f"Empates: {int(general['tied'])} · "
    f"Pendientes: {int(general['pending'])} · "
    f"Efectividad: "
    f"{general['win_rate'] * 100:.1f}% · "
    f"Apuestas con cuota calculable: "
    f"{general['financial_bets']} · "
    f"Cuotas reales/históricas F5: "
    f"{general['real_odds']} · "
    f"Estimadas con Full Game: "
    f"{general['estimated_odds']}"
)


# ============================================================
# MLB / NFL / BASKETBALL
# MISMA PÁGINA
# ============================================================

tabs = st.tabs(
    [
        "⚾ MLB",
        "🏈 NFL",
        "🏀 Basketball",
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


st.caption(
    "La efectividad usa todas las apuestas resueltas. "
    "P/L y ROI solo usan operaciones que tienen una cuota registrada."
)


probability_table = probability_analysis(
    history_rows
)


if probability_table:

    st.dataframe(
        probability_table,
        use_container_width=True,
        hide_index=True,
    )

else:

    st.caption(
        "Todavía no hay suficientes apuestas resueltas."
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

        odds_value = valid_odds(
            row.get(
                "odds"
            )
        )

        source = str(
            row.get(
                "odds_source"
            )
            or ""
        ).upper()

        bookmaker = str(
            row.get(
                "bookmaker"
            )
            or ""
        ).strip()

        is_kalshi = (
            bookmaker.lower()
            == "kalshi"
        )

        if (
            is_kalshi
            and odds_value
            is not None
        ):

            source_text = "KALSHI REAL"

        elif source in {
            "REAL",
            "LIVE_AT_RECOMMENDATION",
        }:

            source_text = "REAL"

        elif source == "HISTORICAL_F5":

            source_text = "HISTÓRICA F5"

        elif source == "ESTIMADA_FULL_GAME":

            source_text = "ESTIMADA FULL GAME"

        elif odds_value is not None:

            source_text = "CUOTA REGISTRADA"

        else:

            source_text = "SIN CUOTA"

        stake = row_stake(
            row
        )

        result = (
            row.get("result")
            or "PENDIENTE"
        )

        net_value = row_profit_loss(
            row
        )

        table.append(
            {
                "Fecha":
                    display_time(
                        row.get(
                            "created_at",
                            "",
                        )
                    ),

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

                "% modelo":
                    pct(
                        row.get(
                            "probability"
                        )
                    ),

                "Casa/Fuente":
                    (
                        row.get(
                            "bookmaker"
                        )
                        or "—"
                    ),

                "Tipo cuota":
                    source_text,

                "Cuota":
                    (
                        kalshi_quote_text(
                            odds_value
                        )
                        if is_kalshi
                        else (
                            f"{odds_value:.3f}"
                            if odds_value is not None
                            else "—"
                        )
                    ),

                "Apuesta":
                    (
                        money(stake)
                        if stake is not None
                        else "—"
                    ),

                "Cobro si gana":
                    money(
                        potential_return(
                            row
                        )
                    ),

                "Ganancia si gana":
                    (
                        money(
                            potential_profit(
                                row
                            ),
                            signed=True,
                        )
                        if potential_profit(
                            row
                        ) is not None
                        else "—"
                    ),

                "Resultado":
                    result,

                "P/L":
                    (
                        money(
                            net_value,
                            signed=True,
                        )
                        if net_value is not None
                        else "—"
                    ),

                "Marcador":
                    (
                        row.get(
                            "final_score"
                        )
                        or "—"
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
# NOTA FINAL
# ============================================================

st.markdown(
    (
        '<div class="footer-note">'
        'Apuesta fija: $100. '
        'La cuota de Kalshi se usa únicamente para calcular '
        'Cobro, Ganancia y P/L; no modifica la predicción '
        'ni la probabilidad del motor. '
        'Las operaciones sin cuota Kalshi válida no se incluyen '
        'en los cálculos financieros.'
        '</div>'
    ),
    unsafe_allow_html=True,
    )
