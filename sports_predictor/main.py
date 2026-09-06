from __future__ import annotations

import argparse
import json
import os
import time
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
# CONVERTIR APUESTA BLOQUEADA A FORMATO DEL DASHBOARD
# ============================================================

def locked_prediction_to_candidate(
    row: dict[str, Any] | None,
) -> dict[str, Any] | None:

    if not row:
        return None

    return {
        "game_id":
            row.get("game_id"),

        "matchup":
            row.get("matchup"),

        "market":
            row.get("market"),

        "selection":
            row.get("selection"),

        "away_team":
            row.get("away_team"),

        "home_team":
            row.get("home_team"),

        "model_probability":
            row.get(
                "model_probability"
            ),

        "data_quality":
            row.get(
                "data_quality"
            ),

        "decimal_odds":
            row.get(
                "decimal_odds"
            ),

        "edge":
            row.get(
                "edge"
            ),

        "expected_value":
            row.get(
                "expected_value"
            ),

        "locked":
            True,

        "status":
            row.get(
                "status",
                "PENDIENTE",
            ),

        "reasons": [
            "🔒 Predicción bloqueada.",
            (
                "Esta selección ya fue publicada "
                "y no se cambiará mientras siga pendiente."
            ),
        ],
    }


# ============================================================
# BUSCAR APUESTA ACTIVA
# ============================================================

def active_locked_pick(
    sport: str,
    market: str,
) -> dict[str, Any] | None:

    rows = load_history(
        HISTORY_FILE
    )

    row = get_active_prediction(
        rows,
        sport,
        market,
    )

    return locked_prediction_to_candidate(
        row
    )


# ============================================================
# OBTENER TEMPORADA
# ============================================================

def current_season(
    sport: str,
    now: datetime,
) -> int:

    year = now.year

    if sport == "NFL":

        # Enero y febrero pertenecen
        # normalmente a la temporada
        # iniciada el año anterior.
        if now.month <= 2:
            return year - 1

    return year


# ============================================================
# FORMAS DE EQUIPOS
# ============================================================

def build_forms(
    client: ApiSportsClient,
    sport: str,
    games,
    history_games: int,
    season: int,
) -> dict[Any, Any]:

    team_ids: set[Any] = set()

    for game in games:

        try:
            team_ids.add(
                game.away.id
            )
            team_ids.add(
                game.home.id
            )
        except Exception:
            continue

    forms: dict[Any, Any] = {}

    for team_id in team_ids:

        try:

            history_result = (
                client.team_history(
                    sport,
                    team_id,
                    season,
                )
            )

            history_games_raw = (
                normalize_games(
                    sport,
                    history_result.response,
                )
            )

            finished_games = [
                game
                for game
                in history_games_raw
                if is_finished(game)
            ]

            finished_games = (
                finished_games[
                    -history_games:
                ]
            )

            forms[team_id] = (
                calculate_team_form(
                    team_id,
                    finished_games,
                )
            )

        except Exception:

            continue

    return forms


# ============================================================
# MLB MATCHUPS PROFUNDOS
# ============================================================

def build_mlb_matchups(
    mlb_client: MlbStatsClient,
    games,
    date_iso: str,
) -> dict[Any, dict[str, Any]]:

    matchups: dict[
        Any,
        dict[str, Any],
    ] = {}

    for game in games:

        try:

            matchup = (
                mlb_client.matchup(
                    game_id=game.id,
                    date_iso=date_iso,
                    away_team_id=game.away.id,
                    home_team_id=game.home.id,
                )
            )

            if matchup:
                matchups[
                    game.id
                ] = matchup

        except Exception as exc:

            print(
                (
                    f"MLB matchup "
                    f"{game.id}: "
                    f"{exc}"
                )
            )

    return matchups


# ============================================================
# ANALIZAR UN DEPORTE
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

    print(
        f"\n=== {sport} ==="
    )

    # ========================================================
    # PARTIDOS DEL DÍA
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
        if not is_finished(game)
    ]

    print(
        f"Partidos encontrados: "
        f"{len(games)}"
    )

    print(
        f"Partidos disponibles: "
        f"{len(unfinished_games)}"
    )

    # ========================================================
    # ACTUALIZAR RESULTADOS DEL HISTORIAL
    #
    # Incluso si hoy no hay una nueva apuesta,
    # debemos revisar si alguna pendiente ya terminó.
    # ========================================================

    update_history(
        path=HISTORY_FILE,
        sport=sport,
        games=raw_games,
        recommendation=None,
        now=now,
    )

    # ========================================================
    # SI NO HAY PARTIDOS ABIERTOS
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
                games_result
                .remaining_requests,

            "recommendation":
                None,

            "best_observed":
                None,

            "notes": [
                (
                    "No hay partidos disponibles "
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
    # CUOTAS
    # ========================================================

    game_ids = [
        game.id
        for game
        in unfinished_games
    ]

    odds_result = (
        api_client.odds_for_date(
            sport,
            date_iso,
            game_ids,
        )
    )

    quotes = parse_quotes(
        sport,
        odds_result.response,
    )

    # ========================================================
    # FORMAS RECIENTES
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
        api_client,
        sport,
        unfinished_games,
        history_games,
        season,
    )

    # ========================================================
    # MLB: ABRIDORES, BULLPEN, BATEO, SPLITS, BVP,
    # ALINEACIÓN, CLIMA, DESCANSO, F5, ETC.
    # ========================================================

    mlb_matchups: dict[
        Any,
        dict[str, Any],
    ] = {}

    if (
        sport == "MLB"
        and mlb_client is not None
    ):

        mlb_matchups = (
            build_mlb_matchups(
                mlb_client,
                unfinished_games,
                date_iso,
            )
        )

    # ========================================================
    # MOTOR
    # ========================================================

    analysis = analyze_sport(
        sport=sport,
        games=unfinished_games,
        forms=forms,
        quotes=quotes,
        config=config,
        mlb_matchups=mlb_matchups,
    )

    recommendation = (
        analysis.get(
            "recommendation"
        )
    )

    best_observed = (
        analysis.get(
            "best_observed"
        )
    )

    notes = list(
        analysis.get(
            "notes"
        )
        or []
    )

    # ========================================================
    # GUARDAR NUEVA PREDICCIÓN
    #
    # history.py decide si puede guardarse.
    # Si ya existe una apuesta pendiente del
    # mismo mercado, NO crea otra.
    # ========================================================

    if recommendation:

        update_history(
            path=HISTORY_FILE,
            sport=sport,
            games=raw_games,
            recommendation=recommendation,
            now=now,
        )

    # ========================================================
    # CARGAR HISTORIAL ACTUALIZADO
    # ========================================================

    rows = load_history(
        HISTORY_FILE
    )

    # ========================================================
    # BLOQUEO VISUAL
    #
    # Si existe una apuesta pendiente bloqueada,
    # el dashboard debe enseñar ESA apuesta,
    # no la nueva recomendación calculada.
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
    # ELEGIR QUÉ MOSTRAR COMO RECOMENDACIÓN PRINCIPAL
    #
    # Prioridad:
    # 1. Ganador final bloqueado
    # 2. F5 bloqueado
    # 3. Recomendación recién calculada
    # ========================================================

    dashboard_recommendation = (
        locked_final
        or locked_f5
        or recommendation
    )

    # ========================================================
    # NOTAS DE BLOQUEO
    # ========================================================

    if locked_final:

        notes.append(
            (
                "🔒 GANADOR FINAL bloqueado: "
                f"{locked_final.get('selection')}. "
                "No se cambiará por otro equipo "
                "ni por otro partido mientras "
                "siga pendiente."
            )
        )

    if locked_f5:

        notes.append(
            (
                "🔒 F5 bloqueado: "
                f"{locked_f5.get('selection')}. "
                "No se cambiará mientras "
                "siga pendiente."
            )
        )

    # ========================================================
    # CONSOLA
    # ========================================================

    if dashboard_recommendation:

        print(
            (
                "SELECCIÓN: "
                f"{dashboard_recommendation.get('selection')}"
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

            except Exception:
                pass

    else:

        print(
            "NO APOSTAR"
        )

    # ========================================================
    # RESULTADO
    # ========================================================

    return {
        "games":
            len(unfinished_games),

        "quotes":
            len(quotes),

        "remaining_requests":
            odds_result
            .remaining_requests,

        "recommendation":
            dashboard_recommendation,

        "best_observed":
            best_observed,

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
# UN ESCANEO COMPLETO
# ============================================================

def run_scan(
    scan_number: int,
    config: dict[str, Any],
    api_client: ApiSportsClient,
    mlb_client: MlbStatsClient | None,
    timezone: ZoneInfo,
) -> dict[str, Any]:

    now = (
        datetime
        .now(timezone)
    )

    print(
        "\n"
        + "=" * 60
    )

    print(
        (
            f"ESCANEO #{scan_number} "
            f"{now.isoformat()}"
        )
    )

    print(
        "=" * 60
    )

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

            results[sport] = (
                analyze_one_sport(
                    sport=sport,
                    now=now,
                    config=config,
                    api_client=api_client,
                    mlb_client=mlb_client,
                )
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
                "games":
                    0,

                "quotes":
                    0,

                "remaining_requests":
                    None,

                "recommendation":
                    None,

                "best_observed":
                    None,

                "notes":
                    [],

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
                "games":
                    0,

                "quotes":
                    0,

                "remaining_requests":
                    None,

                "recommendation":
                    None,

                "best_observed":
                    None,

                "notes":
                    [],

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
    # SNAPSHOT
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

    print(
        "\nReporte actualizado."
    )

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
        help=(
            "Tiempo total que permanecerá "
            "analizando."
        ),
    )

    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=15,
        help=(
            "Minutos entre escaneos."
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Ejecutar solamente un escaneo."
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

    # ========================================================
    # CLIENTE API-SPORTS
    # ========================================================

    api_client = ApiSportsClient(
        api_key=api_key,
    )

    # ========================================================
    # MLB STATS API
    #
    # No necesita la API key de API-Sports.
    # ========================================================

    mlb_client = MlbStatsClient()

    DASHBOARD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # SOLO UNA VEZ
    # ========================================================

    if args.once:

        run_scan(
            scan_number=1,
            config=config,
            api_client=api_client,
            mlb_client=mlb_client,
            timezone=timezone,
        )

        return

    # ========================================================
    # CICLO
    # ========================================================

    duration_seconds = max(
        1,
        args.duration_minutes,
    ) * 60

    interval_seconds = max(
        1,
        args.interval_minutes,
    ) * 60

    started = time.time()

    scan_number = 0

    while True:

        elapsed = (
            time.time()
            - started
        )

        if (
            scan_number > 0
            and elapsed
            >= duration_seconds
        ):
            break

        scan_number += 1

        scan_started = (
            time.time()
        )

        run_scan(
            scan_number=scan_number,
            config=config,
            api_client=api_client,
            mlb_client=mlb_client,
            timezone=timezone,
        )

        if (
            time.time()
            - started
            >= duration_seconds
        ):
            break

        scan_elapsed = (
            time.time()
            - scan_started
        )

        sleep_seconds = max(
            0,
            interval_seconds
            - scan_elapsed,
        )

        if sleep_seconds > 0:

            print(
                (
                    "\nPróximo escaneo en "
                    f"{sleep_seconds / 60:.1f} "
                    "minutos..."
                )
            )

            time.sleep(
                sleep_seconds
            )


if __name__ == "__main__":
    main()
