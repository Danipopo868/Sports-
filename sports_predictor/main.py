from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .api import (
    ApiSportsClient,
    ApiSportsError,
)
from .engine import (
    analyze_sport,
    calculate_team_form,
    is_finished,
    normalize_games,
    parse_quotes,
)
from .history import (
    get_active_prediction,
    history_summary,
    load_history,
    update_history,
)
from .mlb import MlbStatsClient
from .report import (
    build_snapshot,
    save_reports,
)


# ============================================================
# RUTAS
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

CONFIG_FILE = (
    PROJECT_ROOT
    / "config.json"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
)

DASHBOARD_DIR = (
    PROJECT_ROOT
    / "dashboard_data"
)

HISTORY_FILE = (
    DASHBOARD_DIR
    / "prediction_history.json"
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

def load_config() -> dict[str, Any]:

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"No existe {CONFIG_FILE}"
        )

    return json.loads(
        CONFIG_FILE.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# APUESTA BLOQUEADA -> DASHBOARD
# ============================================================

def locked_prediction_to_candidate(
    row: dict[str, Any] | None,
) -> dict[str, Any] | None:

    if not row:
        return None

    reasons = list(
        row.get("reasons")
        or []
    )

    reasons.extend(
        [
            "🔒 Predicción bloqueada.",
            (
                "Esta selección ya fue publicada "
                "y no se cambiará mientras siga pendiente."
            ),
        ]
    )

    return {
        "sport":
            row.get("sport"),

        "game_id":
            row.get("game_id"),

        "matchup":
            row.get("matchup"),

        "start":
            row.get("start"),

        "market":
            row.get("market"),

        "selection":
            row.get("selection"),

        "away_team":
            row.get("away_team"),

        "home_team":
            row.get("home_team"),

        "bookmaker":
            row.get("bookmaker"),

        "model_probability":
            row.get("model_probability"),

        "break_even_probability":
            row.get("break_even_probability"),

        "data_quality":
            row.get("data_quality"),

        "decimal_odds":
            row.get("decimal_odds"),

        "edge":
            row.get("edge"),

        "expected_value":
            row.get("expected_value"),

        "bookmakers":
            row.get("bookmakers"),

        "passes_filters":
            True,

        "locked":
            True,

        "status":
            row.get(
                "status",
                "PENDIENTE",
            ),

        "reasons":
            reasons,
    }


# ============================================================
# TEMPORADA
# ============================================================

def current_season(
    sport: str,
    now: datetime,
) -> int:

    year = now.year

    if (
        sport == "NFL"
        and now.month <= 2
    ):
        return year - 1

    return year


# ============================================================
# FORMAS RECIENTES
# ============================================================

def build_forms(
    client: ApiSportsClient,
    sport: str,
    games,
    history_games: int,
    season: int,
) -> dict[str, Any]:

    team_ids: set[Any] = set()

    for game in games:

        team_ids.add(
            game.away.id
        )

        team_ids.add(
            game.home.id
        )

    forms: dict[str, Any] = {}

    total_teams = len(
        team_ids
    )

    print(
        (
            "Equipos para forma reciente: "
            f"{total_teams}"
        )
    )

    for index, team_id in enumerate(
        sorted(
            team_ids,
            key=lambda value: str(value),
        ),
        start=1,
    ):

        print(
            (
                f"  Forma reciente "
                f"{index}/{total_teams} "
                f"- equipo {team_id}"
            )
        )

        try:

            history_result = (
                client.team_history(
                    sport,
                    team_id,
                    season,
                )
            )

            forms[
                str(team_id)
            ] = calculate_team_form(
                sport=sport,
                team_id=team_id,
                raw_games=history_result.response,
                limit=history_games,
            )

        except Exception as exc:

            print(
                (
                    "  No se pudo obtener "
                    f"forma del equipo {team_id}: "
                    f"{exc}"
                )
            )

    return forms


# ============================================================
# MLB MATCHUPS PROFUNDOS
# ============================================================

def build_mlb_matchups(
    mlb_client: MlbStatsClient,
    games,
    date_iso: str,
) -> dict[str, dict[str, Any]]:

    matchups: dict[
        str,
        dict[str, Any],
    ] = {}

    total_games = len(
        games
    )

    print(
        (
            "MLB: comenzando análisis "
            f"profundo de {total_games} "
            "partido(s)."
        )
    )

    for index, game in enumerate(
        games,
        start=1,
    ):

        print(
            (
                f"  MLB {index}/{total_games}: "
                f"{game.away.name} @ "
                f"{game.home.name}"
            )
        )

        try:

            # =================================================
            # CORRECCIÓN
            #
            # MlbStatsClient.matchup() recibe:
            # home_name
            # away_name
            # season
            # date_iso
            #
            # NO game_id / team ids.
            # =================================================

            matchup = (
                mlb_client.matchup(
                    home_name=game.home.name,
                    away_name=game.away.name,
                    season=game.season_year,
                    date_iso=date_iso,
                )
            )

            if matchup:

                matchups[
                    str(game.id)
                ] = matchup

                completeness = (
                    matchup.get(
                        "completeness"
                    )
                    or {}
                )

                score = (
                    completeness.get(
                        "score"
                    )
                )

                if score is not None:

                    print(
                        (
                            "    Calidad MLB: "
                            f"{score}/100"
                        )
                    )

                missing = (
                    completeness.get(
                        "missing"
                    )
                    or []
                )

                if missing:

                    print(
                        (
                            "    Factores faltantes: "
                            + ", ".join(
                                str(value)
                                for value in missing
                            )
                        )
                    )

            else:

                print(
                    (
                        "    DATOS INSUFICIENTES: "
                        "matchup MLB vacío."
                    )
                )

        except Exception as exc:

            print(
                (
                    "    DATOS INSUFICIENTES: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
            )

    print(
        (
            "MLB: análisis profundo terminado. "
            f"{len(matchups)}/{total_games} "
            "matchup(s) obtenidos."
        )
    )

    return matchups


# ============================================================
# RESOLVER PREDICCIONES EXISTENTES
#
# IMPORTANTE:
# NO CREA APUESTAS NUEVAS.
# ============================================================

def resolve_existing_predictions(
    sport: str,
    raw_games,
    now: datetime,
) -> None:

    update_history(
        path=HISTORY_FILE,
        sport=sport,
        games=raw_games,
        recommendation=None,
        now=now,
    )


# ============================================================
# ANALIZAR UN DEPORTE COMPLETO
# ============================================================

def analyze_one_sport(
    sport: str,
    now: datetime,
    config: dict[str, Any],
    api_client: ApiSportsClient,
    mlb_client: MlbStatsClient | None,
) -> dict[str, Any]:

    date_iso = (
        now.date().isoformat()
    )

    print()
    print("=" * 60)
    print(
        f"ANALIZANDO {sport}"
    )
    print("=" * 60)

    # ========================================================
    # 1. TODOS LOS PARTIDOS DEL DÍA
    # ========================================================

    games_result = (
        api_client.games_for_date(
            sport,
            date_iso,
        )
    )

    raw_games = (
        games_result.response
    )

    games = normalize_games(
        sport,
        raw_games,
    )

    unfinished_games = [
        game
        for game in games
        if not is_finished(
            game.status
        )
    ]

    print(
        (
            f"{sport}: "
            f"{len(games)} partido(s) "
            "encontrados."
        )
    )

    print(
        (
            f"{sport}: "
            f"{len(unfinished_games)} partido(s) "
            "disponibles para analizar."
        )
    )

    # ========================================================
    # 2. RESOLVER APUESTAS ANTERIORES
    # ========================================================

    resolve_existing_predictions(
        sport=sport,
        raw_games=raw_games,
        now=now,
    )

    # ========================================================
    # 3. NO HAY PARTIDOS DISPONIBLES
    # ========================================================

    if not unfinished_games:

        rows = load_history(
            HISTORY_FILE
        )

        return {
            "games":
                len(games),

            "quotes":
                0,

            "remaining_requests":
                games_result.remaining_requests,

            "recommendation":
                None,

            "best_observed":
                None,

            "notes": [
                (
                    "SIN DECISIÓN: "
                    "no hay partidos disponibles "
                    "para una nueva predicción."
                )
            ],

            "history_summary":
                history_summary(
                    rows
                ),

            "error":
                None,
        }

    # ========================================================
    # 4. CUOTAS
    # ========================================================

    game_ids = [
        game.id
        for game in unfinished_games
    ]

    print(
        (
            f"{sport}: descargando mercados "
            f"para {len(game_ids)} "
            "partido(s)..."
        )
    )

    odds_result = (
        api_client.odds_for_date(
            sport,
            date_iso,
            game_ids,
        )
    )

    quotes = parse_quotes(
        odds_result.response,
        unfinished_games,
    )

    print(
        (
            f"{sport}: "
            f"{len(quotes)} cuota(s) "
            "utilizables encontradas."
        )
    )

    # ========================================================
    # 5. FORMA RECIENTE
    # ========================================================

    history_games = int(
        config.get(
            "history_games",
            12,
        )
    )

    season = current_season(
        sport,
        now,
    )

    forms = build_forms(
        client=api_client,
        sport=sport,
        games=unfinished_games,
        history_games=history_games,
        season=season,
    )

    print(
        (
            f"{sport}: forma reciente "
            f"obtenida para "
            f"{len(forms)} equipo(s)."
        )
    )

    # ========================================================
    # 6. MLB PROFUNDO
    # ========================================================

    mlb_matchups: (
        dict[str, dict[str, Any]]
        | None
    ) = None

    if (
        sport == "MLB"
        and mlb_client is not None
    ):

        mlb_matchups = (
            build_mlb_matchups(
                mlb_client=mlb_client,
                games=unfinished_games,
                date_iso=date_iso,
            )
        )

    # ========================================================
    # 7. CALCULAR TODOS LOS CANDIDATOS
    # ========================================================

    print(
        (
            f"{sport}: calculando TODOS "
            "los candidatos..."
        )
    )

    (
        recommendation,
        best_observed,
        notes,
    ) = analyze_sport(
        sport=sport,
        games=unfinished_games,
        quotes=quotes,
        forms=forms,
        config=config,
        mlb_matchups=mlb_matchups,
    )

    recommendation_dict = (
        recommendation.to_dict()
        if recommendation is not None
        else None
    )

    best_observed_dict = (
        best_observed.to_dict()
        if best_observed is not None
        else None
    )

    # ========================================================
    # 8. GUARDAR SOLO DESPUÉS DE TERMINAR TODO
    # ========================================================

    if recommendation_dict:

        print(
            (
                f"{sport}: análisis completo. "
                "Existe una selección que "
                "superó todos los filtros."
            )
        )

        update_history(
            path=HISTORY_FILE,
            sport=sport,
            games=raw_games,
            recommendation=recommendation_dict,
            now=now,
        )

    else:

        print(
            (
                f"{sport}: análisis completo "
                "sin nueva apuesta elegible."
            )
        )

    # ========================================================
    # 9. HISTORIAL
    # ========================================================

    rows = load_history(
        HISTORY_FILE
    )

    # ========================================================
    # 10. BLOQUEOS INDEPENDIENTES
    # ========================================================

    active_final = (
        get_active_prediction(
            rows,
            sport,
            "Ganador del partido",
        )
    )

    active_f5 = (
        get_active_prediction(
            rows,
            sport,
            "Primeras 5 entradas",
        )
    )

    locked_final = (
        locked_prediction_to_candidate(
            active_final
        )
    )

    locked_f5 = (
        locked_prediction_to_candidate(
            active_f5
        )
    )

    # ========================================================
    # 11. RECOMENDACIÓN PARA STREAMLIT
    # ========================================================

    dashboard_recommendation = (
        locked_final
        or locked_f5
        or recommendation_dict
    )

    # ========================================================
    # 12. NOTAS DE BLOQUEO
    # ========================================================

    if locked_final:

        notes.append(
            (
                "🔒 GANADOR FINAL bloqueado: "
                f"{locked_final.get('selection')}. "
                "No puede cambiarse mientras "
                "siga PENDIENTE."
            )
        )

    if locked_f5:

        notes.append(
            (
                "🔒 F5 bloqueado: "
                f"{locked_f5.get('selection')}. "
                "No puede cambiarse mientras "
                "siga PENDIENTE."
            )
        )

    # ========================================================
    # 13. DECISIÓN FINAL
    # ========================================================

    print()
    print(
        f"DECISIÓN FINAL {sport}"
    )
    print("-" * 60)

    if dashboard_recommendation:

        print(
            (
                "SELECCIÓN: "
                f"{dashboard_recommendation.get('selection')}"
            )
        )

        print(
            (
                "PARTIDO: "
                f"{dashboard_recommendation.get('matchup')}"
            )
        )

        print(
            (
                "MERCADO: "
                f"{dashboard_recommendation.get('market')}"
            )
        )

        probability = (
            dashboard_recommendation.get(
                "model_probability"
            )
        )

        if probability is not None:

            try:

                probability_number = float(
                    probability
                )

                if probability_number <= 1:
                    probability_number *= 100

                print(
                    (
                        "PROBABILIDAD: "
                        f"{probability_number:.1f}%"
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                pass

        quality = (
            dashboard_recommendation.get(
                "data_quality"
            )
        )

        if quality is not None:

            print(
                (
                    "CALIDAD DE DATOS: "
                    f"{quality}/100"
                )
            )

        if dashboard_recommendation.get(
            "locked"
        ):

            print(
                "ESTADO: 🔒 BLOQUEADA"
            )

    else:

        no_apostar_real = any(
            (
                "NO APOSTAR REAL"
                in str(note)
            )
            for note in notes
        )

        datos_insuficientes = any(
            (
                "DATOS INSUFICIENTES"
                in str(note)
            )
            for note in notes
        )

        if no_apostar_real:

            print(
                "NO APOSTAR REAL"
            )

        elif datos_insuficientes:

            print(
                "DATOS INSUFICIENTES"
            )

        else:

            print(
                "SIN DECISIÓN"
            )

    # ========================================================
    # MOSTRAR RESUMEN
    # ========================================================

    for note in notes:

        text = str(
            note
        )

        if (
            "ESCANEO COMPLETO"
            in text
            or "NO APOSTAR REAL"
            in text
            or "DATOS INSUFICIENTES"
            in text
            or "APUESTA SELECCIONADA"
            in text
        ):

            print(
                f"• {text}"
            )

    # ========================================================
    # 14. DATOS PARA REPORT / STREAMLIT
    # ========================================================

    return {
        "games":
            len(unfinished_games),

        "quotes":
            len(quotes),

        "remaining_requests":
            odds_result.remaining_requests,

        "recommendation":
            dashboard_recommendation,

        "best_observed":
            best_observed_dict,

        "notes":
            notes,

        "history_summary":
            history_summary(
                rows
            ),

        "error":
            None,
    }


# ============================================================
# ANÁLISIS COMPLETO DEL DÍA
# ============================================================

def run_scan(
    scan_number: int,
    config: dict[str, Any],
    api_client: ApiSportsClient,
    mlb_client: MlbStatsClient | None,
    timezone: ZoneInfo,
) -> dict[str, Any]:

    now = datetime.now(
        timezone
    )

    print()
    print("=" * 60)
    print(
        (
            "ANÁLISIS COMPLETO DEL DÍA "
            f"{now.date().isoformat()}"
        )
    )
    print("=" * 60)

    results: dict[
        str,
        dict[str, Any],
    ] = {}

    for sport in (
        "MLB",
        "NFL",
        "NBA",
    ):

        try:

            results[
                sport
            ] = analyze_one_sport(
                sport=sport,
                now=now,
                config=config,
                api_client=api_client,
                mlb_client=mlb_client,
            )

        except ApiSportsError as exc:

            print(
                (
                    f"{sport} API ERROR: "
                    f"{exc}"
                )
            )

            rows = load_history(
                HISTORY_FILE
            )

            results[sport] = {
                "games": 0,
                "quotes": 0,
                "remaining_requests": None,
                "recommendation": None,
                "best_observed": None,
                "notes": [
                    (
                        "DATOS INSUFICIENTES: "
                        "error de API. "
                        "No se considera "
                        "NO APOSTAR."
                    )
                ],
                "history_summary":
                    history_summary(
                        rows
                    ),
                "error":
                    str(exc),
            }

        except Exception as exc:

            print(
                (
                    f"{sport} ERROR: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )
            )

            rows = load_history(
                HISTORY_FILE
            )

            results[sport] = {
                "games": 0,
                "quotes": 0,
                "remaining_requests": None,
                "recommendation": None,
                "best_observed": None,
                "notes": [
                    (
                        "DATOS INSUFICIENTES: "
                        "el análisis tuvo un error. "
                        "No se considera "
                        "NO APOSTAR."
                    )
                ],
                "history_summary":
                    history_summary(
                        rows
                    ),
                "error":
                    (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
            }

    # ========================================================
    # GUARDAR REPORTE
    # ========================================================

    snapshot = build_snapshot(
        generated_at=now,
        date_iso=now.date().isoformat(),
        scan_number=scan_number,
        results=results,
    )

    save_reports(
        snapshot,
        REPORT_DIR,
    )

    print()
    print("=" * 60)
    print(
        "ANÁLISIS DEL DÍA TERMINADO"
    )
    print(
        "Reporte actualizado."
    )
    print("=" * 60)

    return snapshot


# ============================================================
# ARGUMENTOS
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Sports Predictor "
            "MLB / NFL / NBA"
        )
    )

    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=180,
    )

    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=15,
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Analizar todos los partidos "
            "del día una sola vez."
        ),
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    args = parse_args()

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

    api_key = os.environ.get(
        "API_SPORTS_KEY",
        "",
    ).strip()

    if not api_key:

        raise RuntimeError(
            (
                "Falta el secret "
                "API_SPORTS_KEY."
            )
        )

    api_client = (
        ApiSportsClient(
            api_key=api_key,
        )
    )

    mlb_client = (
        MlbStatsClient()
    )

    DASHBOARD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # UNA SOLA PASADA
    # ========================================================

    run_scan(
        scan_number=1,
        config=config,
        api_client=api_client,
        mlb_client=mlb_client,
        timezone=timezone,
    )


if __name__ == "__main__":
    main()
