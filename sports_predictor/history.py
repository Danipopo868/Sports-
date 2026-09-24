from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import (
    Candidate,
    Game,
    is_finished,
    score_for_side,
)


# ============================================================
# CONFIGURACIÓN DE APUESTAS
# ============================================================

DEFAULT_STAKE = 100.0


# ============================================================
# CARGAR HISTORIAL
# ============================================================

def load_history(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        return []

    try:

        data = json.loads(
            path.read_text(
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

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []


# ============================================================
# GUARDAR HISTORIAL
# ============================================================

def save_history(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            rows,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


# ============================================================
# NORMALIZAR NOMBRES
# ============================================================

def _normalize_name(
    value: Any,
) -> str:

    text = str(
        value
        or ""
    )

    plain = (
        unicodedata.normalize(
            "NFKD",
            text,
        )
        .encode(
            "ascii",
            "ignore",
        )
        .decode()
        .lower()
    )

    return re.sub(
        r"[^a-z0-9]+",
        "",
        plain,
    )


# ============================================================
# SACAR VISITANTE + LOCAL DEL MATCHUP
# ============================================================

def _matchup_teams(
    row: dict[str, Any],
) -> tuple[str, str] | None:

    matchup = str(
        row.get("matchup")
        or ""
    ).strip()

    if "@" not in matchup:
        return None

    parts = matchup.split(
        "@",
        1,
    )

    if len(parts) != 2:
        return None

    expected_away = _normalize_name(
        parts[0]
    )

    expected_home = _normalize_name(
        parts[1]
    )

    if (
        not expected_away
        or not expected_home
    ):
        return None

    return (
        expected_away,
        expected_home,
    )


# ============================================================
# CONVERTIR FECHA A TIMESTAMP
# ============================================================

def _timestamp(
    value: Any,
) -> float | None:

    text = str(
        value
        or ""
    ).strip()

    if not text:
        return None

    try:

        return datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        ).timestamp()

    except (
        TypeError,
        ValueError,
    ):
        return None


# ============================================================
# BUSCAR PARTIDO
# ============================================================

def _find_game(
    row: dict[str, Any],
    games: list[Game],
    game_map: dict[str, Game],
) -> Game | None:

    game_id = str(
        row.get("game_id")
        or ""
    )

    if game_id:

        exact = game_map.get(
            game_id
        )

        if exact is not None:
            return exact

    matchup_teams = _matchup_teams(
        row
    )

    if matchup_teams is None:
        return None

    expected_away, expected_home = (
        matchup_teams
    )

    candidates: list[Game] = []

    for game in games:

        actual_away = _normalize_name(
            game.away.name
        )

        actual_home = _normalize_name(
            game.home.name
        )

        if (
            actual_away == expected_away
            and actual_home == expected_home
        ):
            candidates.append(
                game
            )

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    row_start = _timestamp(
        row.get("start")
    )

    if row_start is None:
        return None

    timed: list[
        tuple[float, Game]
    ] = []

    for game in candidates:

        game_start = _timestamp(
            game.start
        )

        if game_start is None:
            continue

        timed.append(
            (
                abs(
                    game_start
                    - row_start
                ),
                game,
            )
        )

    if not timed:
        return None

    timed.sort(
        key=lambda item: item[0]
    )

    return timed[0][1]


# ============================================================
# EXTRAER NÚMERO
# ============================================================

def _number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return float(value)

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    if isinstance(
        value,
        dict,
    ):

        for key in (
            "runs",
            "total",
            "score",
            "points",
            "value",
        ):

            if key not in value:
                continue

            found = _number(
                value.get(key)
            )

            if found is not None:
                return found

        return None

    if isinstance(
        value,
        (list, tuple),
    ):

        if len(value) == 1:
            return _number(
                value[0]
            )

        for item in value:

            found = _number(
                item
            )

            if found is not None:
                return found

        return None

    try:

        return float(
            str(value).strip()
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


# ============================================================
# MARCADOR PRIMERAS 5 ENTRADAS
# ============================================================

def _first_five_score(
    raw: dict[str, Any],
) -> tuple[float, float] | None:

    inning_sources: list[
        list[Any]
    ] = []

    primary_innings = raw.get(
        "innings"
    )

    if isinstance(
        primary_innings,
        list,
    ):
        inning_sources.append(
            primary_innings
        )

    mlb_raw = (
        raw.get("_mlb_raw")
        or {}
    )

    if isinstance(
        mlb_raw,
        dict,
    ):

        linescore = (
            mlb_raw.get(
                "linescore"
            )
            or {}
        )

        if isinstance(
            linescore,
            dict,
        ):

            mlb_innings = (
                linescore.get(
                    "innings"
                )
                or []
            )

            if isinstance(
                mlb_innings,
                list,
            ):
                inning_sources.append(
                    mlb_innings
                )

    if not inning_sources:
        return None

    inning_map: dict[
        int,
        tuple[float, float],
    ] = {}

    for innings in inning_sources:

        for inning in innings:

            if not isinstance(
                inning,
                dict,
            ):
                continue

            num_raw = inning.get(
                "num"
            )

            if num_raw is None:
                num_raw = inning.get(
                    "inning"
                )

            try:

                inning_num = int(
                    num_raw
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                inning_num < 1
                or inning_num > 5
            ):
                continue

            visitor_runs = _number(
                inning.get("away")
            )

            home_runs = _number(
                inning.get("home")
            )

            if (
                visitor_runs is None
                or home_runs is None
            ):
                continue

            inning_map[
                inning_num
            ] = (
                float(visitor_runs),
                float(home_runs),
            )

    if any(
        number not in inning_map
        for number in range(
            1,
            6,
        )
    ):
        return None

    visitor_total = sum(
        inning_map[number][0]
        for number in range(
            1,
            6,
        )
    )

    home_total = sum(
        inning_map[number][1]
        for number in range(
            1,
            6,
        )
    )

    return (
        home_total,
        visitor_total,
    )


# ============================================================
# COMPARAR SELECCIÓN
# ============================================================

def _selection_matches(
    selection: Any,
    winner: str,
) -> bool:

    return (
        _normalize_name(selection)
        ==
        _normalize_name(winner)
    )


# ============================================================
# CALCULAR DINERO DE UNA APUESTA
# ============================================================

def _calculate_money(
    row: dict[str, Any],
    result: str,
) -> None:

    try:
        stake = float(
            row.get(
                "stake",
                DEFAULT_STAKE,
            )
            or DEFAULT_STAKE
        )
    except (
        TypeError,
        ValueError,
    ):
        stake = DEFAULT_STAKE

    try:
        odds = float(
            row.get(
                "odds",
                0,
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        odds = 0.0

    row["stake"] = round(
        stake,
        2,
    )

    if result == "GANADA":

        if odds > 0:

            return_amount = (
                stake * odds
            )

            profit_loss = (
                return_amount
                - stake
            )

        else:

            return_amount = stake
            profit_loss = 0.0

    elif result == "PERDIDA":

        return_amount = 0.0
        profit_loss = -stake

    elif result == "EMPATE":

        return_amount = stake
        profit_loss = 0.0

    else:

        return

    row["return_amount"] = round(
        return_amount,
        2,
    )

    row["profit_loss"] = round(
        profit_loss,
        2,
    )


# ============================================================
# MARCAR FILA RESUELTA
# ============================================================

def _resolve_row(
    row: dict[str, Any],
    *,
    result: str,
    winner: str | None,
    final_score: str,
    generated_at: datetime,
) -> None:

    row["winner"] = winner
    row["final_score"] = final_score
    row["result"] = result
    row["status"] = "RESUELTA"

    row["resolved_at"] = (
        generated_at.isoformat()
    )

    _calculate_money(
        row,
        result,
    )


# ============================================================
# ACTUALIZAR HISTORIAL
# ============================================================

def update_history(
    path: Path,
    sport: str,
    games: list[Game],
    recommendations: list[Candidate],
    generated_at: datetime,
) -> list[dict[str, Any]]:

    rows = load_history(
        path
    )

    game_map = {
        str(game.id): game
        for game in games
    }

    # ========================================================
    # RESOLVER PICKS PENDIENTES
    # ========================================================

    for row in rows:

        if (
            str(
                row.get("sport")
                or ""
            ).upper()
            != sport.upper()
        ):
            continue

        if (
            str(
                row.get("status")
                or ""
            ).upper()
            != "PENDIENTE"
        ):
            continue

        market = str(
            row.get("market")
            or ""
        ).strip()

        if market not in {
            "Ganador del partido",
            "Primeras 5 entradas",
        }:
            continue

        game = _find_game(
            row,
            games,
            game_map,
        )

        if game is None:
            continue

        # ====================================================
        # GANADOR DEL PARTIDO
        # ====================================================

        if market == "Ganador del partido":

            if not is_finished(
                game.status
            ):
                continue

            home_score = _number(
                score_for_side(
                    game.raw,
                    "home",
                )
            )

            visitor_score = _number(
                score_for_side(
                    game.raw,
                    "away",
                )
            )

            if (
                home_score is None
                or visitor_score is None
            ):
                continue

            score_text = (
                f"{game.away.name} "
                f"{visitor_score:g} - "
                f"{game.home.name} "
                f"{home_score:g}"
            )

            if home_score == visitor_score:

                _resolve_row(
                    row,
                    result="EMPATE",
                    winner=None,
                    final_score=score_text,
                    generated_at=generated_at,
                )

                continue

            winner = (
                game.home.name
                if home_score
                > visitor_score
                else game.away.name
            )

            result = (
                "GANADA"
                if _selection_matches(
                    row.get(
                        "selection"
                    ),
                    winner,
                )
                else "PERDIDA"
            )

            _resolve_row(
                row,
                result=result,
                winner=winner,
                final_score=score_text,
                generated_at=generated_at,
            )

            continue

        # ====================================================
        # PRIMERAS 5 ENTRADAS
        # ====================================================

        first_five = _first_five_score(
            game.raw
        )

        if first_five is None:
            continue

        home_f5, visitor_f5 = (
            first_five
        )

        score_text = (
            f"{game.away.name} "
            f"{visitor_f5:g} - "
            f"{game.home.name} "
            f"{home_f5:g} "
            "(F5)"
        )

        if home_f5 == visitor_f5:

            _resolve_row(
                row,
                result="EMPATE",
                winner=None,
                final_score=score_text,
                generated_at=generated_at,
            )

            continue

        winner = (
            game.home.name
            if home_f5 > visitor_f5
            else game.away.name
        )

        result = (
            "GANADA"
            if _selection_matches(
                row.get(
                    "selection"
                ),
                winner,
            )
            else "PERDIDA"
        )

        _resolve_row(
            row,
            result=result,
            winner=winner,
            final_score=score_text,
            generated_at=generated_at,
        )

    # ========================================================
    # GUARDAR NUEVAS RECOMENDACIONES
    # ========================================================

    for (
        pick_number,
        recommendation,
    ) in enumerate(
        recommendations[:2],
        start=1,
    ):

        key = (
            f"{sport}|"
            f"{recommendation.game_id}|"
            f"{recommendation.market}|"
            f"{recommendation.selection}"
        )

        if any(
            row.get("key") == key
            for row in rows
        ):
            continue

        rows.append(
            {
                "key": key,

                "pick_number": (
                    pick_number
                ),

                "created_at": (
                    generated_at.isoformat()
                ),

                "sport": sport,

                "game_id": (
                    recommendation.game_id
                ),

                "matchup": (
                    recommendation.matchup
                ),

                "start": (
                    recommendation.start
                ),

                "market": (
                    recommendation.market
                ),

                "selection": (
                    recommendation.selection
                ),

                # PORCENTAJE CONGELADO
                # AL MOMENTO DE LA APUESTA
                "probability": (
                    recommendation.model_probability
                ),

                # CUOTA CONGELADA
                # AL MOMENTO DE LA APUESTA
                "odds": (
                    recommendation.decimal_odds
                ),

                # APUESTA FIJA
                "stake": DEFAULT_STAKE,

                "edge": (
                    recommendation.edge
                ),

                "expected_value": (
                    recommendation.expected_value
                ),

                "data_quality": (
                    recommendation.data_quality
                ),

                "status": "PENDIENTE",

                "result": None,

                "return_amount": None,

                "profit_loss": None,
            }
        )

    save_history(
        path,
        rows,
    )

    return rows


# ============================================================
# RESUMEN
# ============================================================

def history_summary(
    rows: list[dict[str, Any]],
) -> dict[str, int | float]:

    won = sum(
        row.get("result") == "GANADA"
        for row in rows
    )

    lost = sum(
        row.get("result") == "PERDIDA"
        for row in rows
    )

    tied = sum(
        row.get("result") == "EMPATE"
        for row in rows
    )

    resolved = (
        won
        + lost
        + tied
    )

    pending = sum(
        str(
            row.get("status")
            or ""
        ).upper()
        == "PENDIENTE"
        for row in rows
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

    total_staked = 0.0
    total_profit_loss = 0.0

    for row in rows:

        if (
            row.get("result")
            not in {
                "GANADA",
                "PERDIDA",
                "EMPATE",
            }
        ):
            continue

        try:
            stake = float(
                row.get(
                    "stake",
                    DEFAULT_STAKE,
                )
                or DEFAULT_STAKE
            )
        except (
            TypeError,
            ValueError,
        ):
            stake = DEFAULT_STAKE

        total_staked += stake

        profit_loss = row.get(
            "profit_loss"
        )

        if profit_loss is None:

            temporary = dict(
                row
            )

            _calculate_money(
                temporary,
                str(
                    row.get("result")
                ),
            )

            profit_loss = temporary.get(
                "profit_loss",
                0.0,
            )

        try:
            total_profit_loss += float(
                profit_loss
                or 0
            )
        except (
            TypeError,
            ValueError,
        ):
            pass

    roi = (
        total_profit_loss
        / total_staked
        if total_staked
        else 0.0
    )

    return {
        "total": len(rows),
        "resolved": resolved,
        "won": won,
        "lost": lost,
        "tied": tied,
        "pending": pending,
        "win_rate": win_rate,

        "total_staked": round(
            total_staked,
            2,
        ),

        "profit_loss": round(
            total_profit_loss,
            2,
        ),

        "roi": roi,
    }
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
# FORMATO %
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


# ============================================================
# CONVERTIR PROBABILIDAD A %
# ============================================================

def probability_percent(
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


# ============================================================
# FORMATO DINERO
# ============================================================

def money(
    value: Any,
    signed: bool = False,
) -> str:

    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        number = 0.0

    if signed:
        return f"{number:+,.2f}"

    return f"${number:,.2f}"


# ============================================================
# HORA
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
# CALCULAR P/L DE UNA FILA
# Compatible también con historial viejo.
# ============================================================

def row_profit_loss(
    row: dict[str, Any],
) -> float:

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
        row.get("result")
        or ""
    ).upper()

    try:
        stake = float(
            row.get(
                "stake",
                DEFAULT_STAKE,
            )
            or DEFAULT_STAKE
        )
    except (
        TypeError,
        ValueError,
    ):
        stake = DEFAULT_STAKE

    try:
        odds = float(
            row.get("odds")
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        odds = 0.0

    if result == "GANADA":

        if odds > 0:
            return (
                stake * odds
                - stake
            )

        return 0.0

    if result == "PERDIDA":
        return -stake

    return 0.0


# ============================================================
# ESTADÍSTICAS
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

    resolved_rows = [
        row
        for row in filtered
        if row.get("result")
        in {
            "GANADA",
            "PERDIDA",
            "EMPATE",
        }
    ]

    total_staked = 0.0

    for row in resolved_rows:

        try:

            total_staked += float(
                row.get(
                    "stake",
                    DEFAULT_STAKE,
                )
                or DEFAULT_STAKE
            )

        except (
            TypeError,
            ValueError,
        ):

            total_staked += (
                DEFAULT_STAKE
            )

    profit_loss = sum(
        row_profit_loss(row)
        for row in resolved_rows
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
# ESTADÍSTICAS DEPORTE
# ============================================================

def render_sport_stats(
    history_rows: list[dict[str, Any]],
    sport: str,
) -> None:

    stats = history_stats(
        history_rows,
        sport,
    )

    c1, c2, c3, c4, c5 = (
        st.columns(5)
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
            f"{float(stats['roi']) * 100:+.2f}%"
            if stats["total_staked"]
            else "—"
        ),
    )

    st.caption(
        f"Empates: {int(stats['tied'])} · "
        f"Pendientes: {int(stats['pending'])} · "
        f"Efectividad: "
        f"{float(stats['win_rate']) * 100:.1f}%"
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
            candidate.get("edge")
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

    st.caption(
        "💵 Tamaño registrado por apuesta: $100.00"
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
            st.columns(3)
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
                best.get("edge")
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

        st.write(error)

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

            probability = (
                probability_percent(
                    row.get(
                        "probability"
                    )
                )
            )

            if probability is None:
                continue

            if (
                probability >= low
                and probability <= high
            ):
                selected.append(
                    row
                )

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

        net = sum(
            row_profit_loss(row)
            for row in selected
        )

        staked = 0.0

        for row in selected:

            try:
                staked += float(
                    row.get(
                        "stake",
                        DEFAULT_STAKE,
                    )
                    or DEFAULT_STAKE
                )
            except (
                TypeError,
                ValueError,
            ):
                staked += DEFAULT_STAKE

        roi = (
            net / staked
            if staked
            else 0.0
        )

        output.append(
            {
                "Probabilidad": label,
                "Apuestas": len(
                    selected
                ),
                "Ganadas": won,
                "Perdidas": lost,
                "Empates": tied,
                "Efectividad": (
                    f"{won / decisions * 100:.1f}%"
                    if decisions
                    else "—"
                ),
                "Apostado": (
                    f"${staked:,.2f}"
                ),
                "Neto": (
                    f"${net:+,.2f}"
                ),
                "ROI": (
                    f"{roi * 100:+.2f}%"
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
    "📊 Resultados generales"
)

general = history_stats(
    history_rows
)

g1, g2, g3, g4, g5 = (
    st.columns(5)
)

g1.metric(
    "💵 Apostado",
    money(
        general[
            "total_staked"
        ]
    ),
)

g2.metric(
    "💰 Ganancia/Pérdida",
    money(
        general[
            "profit_loss"
        ],
        signed=True,
    ),
)

g3.metric(
    "📈 ROI",
    (
        f"{float(general['roi']) * 100:+.2f}%"
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
    f"💵 $100 por apuesta · "
    f"Empates: {int(general['tied'])} · "
    f"Pendientes: {int(general['pending'])} · "
    f"Efectividad: "
    f"{float(general['win_rate']) * 100:.1f}%"
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
# RESULTADOS POR PROBABILIDAD
# ============================================================

st.divider()

st.subheader(
    "📊 Rendimiento por porcentaje"
)

st.caption(
    "Compara cuánto dinero producen las apuestas "
    "según la probabilidad que tenía el modelo "
    "cuando fueron registradas."
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
        "Todavía no hay suficientes apuestas "
        "resueltas para analizar por porcentaje."
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

        probability = pct(
            row.get(
                "probability"
            )
        )

        try:

            odds = (
                f"{float(row.get('odds')):.2f}"
                if row.get("odds")
                is not None
                else "—"
            )

        except (
            TypeError,
            ValueError,
        ):
            odds = "—"

        try:

            stake = float(
                row.get(
                    "stake",
                    DEFAULT_STAKE,
                )
                or DEFAULT_STAKE
            )

        except (
            TypeError,
            ValueError,
        ):
            stake = DEFAULT_STAKE

        result = (
            row.get("result")
            or "PENDIENTE"
        )

        if result in {
            "GANADA",
            "PERDIDA",
            "EMPATE",
        }:

            net = (
                f"${row_profit_loss(row):+,.2f}"
            )

        else:

            net = "—"

        table.append(
            {
                "Fecha": display_time(
                    row.get(
                        "created_at",
                        "",
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
                "% a favor": probability,
                "Cuota": odds,
                "Apuesta": (
                    f"${stake:,.2f}"
                ),
                "Resultado": result,
                "Ganancia/Pérdida": net,
                "Marcador": row.get(
                    "final_score"
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
        'Cálculo financiero basado en $100 por apuesta. '
        'Una apuesta ganada calcula la ganancia según la cuota '
        'decimal registrada al momento de la selección; una '
        'perdida resta $100 y un empate devuelve la inversión. '
        'Las probabilidades son estimaciones, no garantías.'
        '</div>'
    ),
    unsafe_allow_html=True,
)
