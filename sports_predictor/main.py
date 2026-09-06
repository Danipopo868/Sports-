from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .api import ApiSportsClient, ApiSportsError
from .engine import (
    TeamForm,
    analyze_sport,
    calculate_team_form,
    is_finished,
    normalize_games,
    parse_quotes,
)
from .mlb import MlbStatsClient
from .history import update_history, history_summary
from .report import build_snapshot, save_reports


SPORTS = ("MLB", "NFL", "NBA")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SportsAnalyzer:

    def __init__(
        self,
        api_key: str,
        config: dict[str, Any],
    ) -> None:

        self.config = config

        self.client = ApiSportsClient(
            api_key
        )

        self.mlb = MlbStatsClient()

        self.history_cache: dict[
            tuple[str, str, str],
            list[dict[str, Any]],
        ] = {}


    # ========================================================
    # ESCANEO GENERAL
    # ========================================================

    def scan(
        self,
        date_iso: str,
    ) -> dict[str, dict[str, Any]]:

        results: dict[
            str,
            dict[str, Any],
        ] = {}

        for sport in SPORTS:

            try:

                # ------------------------------------------------
                # BUSCAR TODOS LOS PARTIDOS DEL DÍA
                # ------------------------------------------------

                game_result = (
                    self.client.games_for_date(
                        sport,
                        date_iso,
                    )
                )

                normalized = normalize_games(
                    sport,
                    game_result.response,
                )

                # ------------------------------------------------
                # SOLO PARTIDOS QUE TODAVÍA NO TERMINARON
                # ------------------------------------------------

                games = [
                    game
                    for game in normalized
                    if not is_finished(
                        game.status
                    )
                ]

                game_ids = [
                    game.id
                    for game in games
                ]

                # ------------------------------------------------
                # CUOTAS / PROBABILIDADES DE MERCADO
                # ------------------------------------------------

                odds_result = (
                    self.client.odds_for_date(
                        sport,
                        date_iso,
                        game_ids,
                    )
                )

                quotes = parse_quotes(
                    odds_result.response,
                    games,
                )

                # ------------------------------------------------
                # FORMA RECIENTE
                # ------------------------------------------------

                forms = (
                    self._forms_for_games(
                        sport,
                        games,
                    )
                )

                # ------------------------------------------------
                # MLB: ANÁLISIS COMPLETO
                # ------------------------------------------------

                if sport == "MLB":

                    matchups = (
                        self._mlb_matchups(
                            games,
                            date_iso,
                        )
                    )

                else:

                    matchups = None

                # ------------------------------------------------
                # MOTOR PRINCIPAL
                # ------------------------------------------------

                recommendation, best_observed, notes = (
                    analyze_sport(
                        sport,
                        games,
                        quotes,
                        forms,
                        self.config,
                        matchups,
                    )
                )

                # ------------------------------------------------
                # HISTORIAL
                # ------------------------------------------------

                history_file = (
                    PROJECT_ROOT
                    / "dashboard_data"
                    / "prediction_history.json"
                )

                history_file.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                history_rows = update_history(
                    history_file,
                    sport,
                    normalized,
                    recommendation,
                    datetime.now(),
                )

                # ------------------------------------------------
                # RESULTADO DEL DEPORTE
                # ------------------------------------------------

                results[sport] = {

                    "games":
                        len(games),

                    "quotes":
                        len(quotes),

                    "remaining_requests":
                        odds_result.remaining_requests,

                    "recommendation":
                        recommendation,

                    "best_observed":
                        best_observed,

                    "notes":
                        notes,

                    "history_summary":
                        history_summary(
                            history_rows
                        ),

                    "error":
                        None,
                }

            except (
                ApiSportsError,
                ValueError,
            ) as exc:

                results[sport] = {

                    "games": 0,

                    "quotes": 0,

                    "remaining_requests":
                        None,

                    "recommendation":
                        None,

                    "best_observed":
                        None,

                    "notes": [],

                    "history_summary":
                        {},

                    "error":
                        _safe_error(
                            str(exc)
                        ),
                }

        return results


    # ========================================================
    # FORMA RECIENTE
    # ========================================================

    def _forms_for_games(
        self,
        sport: str,
        games: list[Any],
    ) -> dict[str, TeamForm]:

        forms: dict[
            str,
            TeamForm,
        ] = {}

        history_limit = int(
            self.config[
                "history_games"
            ]
        )

        for game in games:

            for team in (
                game.home,
                game.away,
            ):

                key = (
                    sport,
                    str(team.id),
                    game.season,
                )

                # --------------------------------------------
                # HISTORIAL TEMPORADA ACTUAL
                # --------------------------------------------

                if key not in self.history_cache:

                    try:

                        history = (
                            self.client.team_history(
                                sport,
                                team.id,
                                game.season,
                            )
                        )

                        self.history_cache[
                            key
                        ] = (
                            history.response
                        )

                    except ApiSportsError:

                        self.history_cache[
                            key
                        ] = []

                history_rows = list(
                    self.history_cache[
                        key
                    ]
                )

                current_form = (
                    calculate_team_form(
                        sport,
                        team.id,
                        history_rows,
                        history_limit,
                        game.id,
                    )
                )

                # --------------------------------------------
                # SI FALTAN PARTIDOS USA TEMPORADA ANTERIOR
                # --------------------------------------------

                if (
                    current_form.games
                    <
                    history_limit
                ):

                    previous_season = (
                        _previous_season(
                            game.season
                        )
                    )

                    previous_key = (
                        sport,
                        str(team.id),
                        previous_season,
                    )

                    if (
                        previous_key
                        not in
                        self.history_cache
                    ):

                        try:

                            previous = (
                                self.client
                                .team_history(
                                    sport,
                                    team.id,
                                    previous_season,
                                )
                            )

                            self.history_cache[
                                previous_key
                            ] = (
                                previous.response
                            )

                        except ApiSportsError:

                            self.history_cache[
                                previous_key
                            ] = []

                    history_rows.extend(
                        self.history_cache[
                            previous_key
                        ]
                    )

                # --------------------------------------------
                # FORMA FINAL
                # --------------------------------------------

                forms[
                    str(team.id)
                ] = (
                    calculate_team_form(
                        sport,
                        team.id,
                        history_rows,
                        history_limit,
                        game.id,
                    )
                )

        return forms


    # ========================================================
    # MLB COMPLETO
    # ========================================================

    def _mlb_matchups(
        self,
        games: list[Any],
        date_iso: str,
    ) -> dict[
        str,
        dict[str, Any],
    ]:

        matchups: dict[
            str,
            dict[str, Any],
        ] = {}

        for game in games:

            try:

                matchup = (
                    self.mlb.matchup(
                        game.home.name,
                        game.away.name,
                        game.season_year,
                        date_iso,
                    )
                )

                # --------------------------------------------
                # INFORMACIÓN EXTRA DEL PARTIDO
                # --------------------------------------------

                matchup[
                    "home_name"
                ] = game.home.name

                matchup[
                    "away_name"
                ] = game.away.name

                matchup[
                    "game_id"
                ] = str(game.id)

                matchup[
                    "date"
                ] = date_iso

                matchups[
                    str(game.id)
                ] = matchup

            except Exception as exc:

                # IMPORTANTE:
                # un partido NO desaparece si falla un dato.
                # Se guarda indicando el error.
                matchups[
                    str(game.id)
                ] = {

                    "game_id":
                        str(game.id),

                    "home_name":
                        game.home.name,

                    "away_name":
                        game.away.name,

                    "date":
                        date_iso,

                    "error":
                        str(exc),

                    "completeness": {
                        "score": 0,
                        "checks": {},
                        "missing": [
                            "datos_mlb"
                        ],
                    },
                }

        return matchups


# ============================================================
# EJECUCIÓN
# ============================================================

def run(
    args: argparse.Namespace,
) -> int:

    config_path = Path(
        args.config
    ).resolve()

    config = json.loads(
        config_path.read_text(
            encoding="utf-8"
        )
    )

    # ========================================================
    # API KEY
    # ========================================================

    api_key = os.environ.get(
        "API_SPORTS_KEY",
        "",
    ).strip()

    if not api_key:

        print(
            (
                "ERROR: crea el secreto "
                "API_SPORTS_KEY en GitHub "
                "antes de ejecutar."
            ),
            file=sys.stderr,
        )

        return 2

    # ========================================================
    # TIMEZONE
    # ========================================================

    timezone = ZoneInfo(
        str(
            config.get(
                "timezone",
                "America/Chicago",
            )
        )
    )

    analyzer = SportsAnalyzer(
        api_key,
        config,
    )

    output_dir = Path(
        args.output
    ).resolve()

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    stop_event = (
        threading.Event()
    )

    # ========================================================
    # DETENER LIMPIAMENTE
    # ========================================================

    def request_stop(
        _signum: int,
        _frame: Any,
    ) -> None:

        stop_event.set()

    signal.signal(
        signal.SIGTERM,
        request_stop,
    )

    signal.signal(
        signal.SIGINT,
        request_stop,
    )

    # ========================================================
    # TIEMPO DE EJECUCIÓN
    # ========================================================

    duration_seconds = (
        0
        if args.once
        else
        max(
            1,
            args.duration_minutes,
        )
        * 60
    )

    interval_seconds = (
        max(
            1,
            args.interval_minutes,
        )
        * 60
    )

    started = time.monotonic()

    deadline = (
        started
        +
        duration_seconds
    )

    next_scan = started

    scan_number = 0

    last_snapshot: (
        dict[str, Any]
        | None
    ) = None

    # ========================================================
    # LOOP PRINCIPAL
    # ========================================================

    while not stop_event.is_set():

        scan_number += 1

        now = datetime.now(
            timezone
        )

        date_iso = (
            args.date
            or
            now.date().isoformat()
        )

        print(
            (
                f"[{now.isoformat()}] "
                f"Escaneo #{scan_number} "
                f"de {date_iso}"
            ),
            flush=True,
        )

        # ----------------------------------------------------
        # ANALIZAR TODOS LOS DEPORTES
        # ----------------------------------------------------

        results = analyzer.scan(
            date_iso
        )

        # ----------------------------------------------------
        # CREAR SNAPSHOT
        # ----------------------------------------------------

        last_snapshot = (
            build_snapshot(
                now,
                date_iso,
                scan_number,
                results,
            )
        )

        latest_md, _ = (
            save_reports(
                last_snapshot,
                output_dir,
            )
        )

        # ----------------------------------------------------
        # MOSTRAR RESULTADOS
        # ----------------------------------------------------

        for sport in SPORTS:

            sport_data = (
                results.get(
                    sport,
                    {},
                )
            )

            recommendation = (
                sport_data.get(
                    "recommendation"
                )
            )

            if recommendation:

                selection = getattr(
                    recommendation,
                    "selection",
                    None,
                )

                market = getattr(
                    recommendation,
                    "market",
                    None,
                )

                probability = getattr(
                    recommendation,
                    "probability",
                    None,
                )

                if probability is not None:

                    prob_text = (
                        f"{probability * 100:.1f}%"
                        if probability <= 1
                        else
                        f"{probability:.1f}%"
                    )

                else:

                    prob_text = "N/D"

                state = (
                    f"APOSTAR "
                    f"{selection} "
                    f"| {market or 'GANADOR FINAL'} "
                    f"| {prob_text}"
                )

            else:

                state = (
                    "NO APOSTAR"
                )

            print(
                f"{sport}: {state}",
                flush=True,
            )

        print(
            (
                "Reporte actualizado: "
                f"{latest_md}"
            ),
            flush=True,
        )

        # ----------------------------------------------------
        # SOLO UNA EJECUCIÓN
        # ----------------------------------------------------

        if (
            args.once
            or
            duration_seconds == 0
        ):

            break

        # ----------------------------------------------------
        # ESPERAR PRÓXIMO ESCANEO
        # ----------------------------------------------------

        next_scan += (
            interval_seconds
        )

        remaining_session = (
            deadline
            -
            time.monotonic()
        )

        if remaining_session <= 0:
            break

        wait_seconds = min(
            max(
                0.0,
                next_scan
                -
                time.monotonic(),
            ),
            remaining_session,
        )

        if wait_seconds <= 0:
            continue

        stop_event.wait(
            wait_seconds
        )

        if (
            time.monotonic()
            >=
            deadline
        ):
            break

    # ========================================================
    # FINAL
    # ========================================================

    if last_snapshot is None:
        return 1

    all_errors = all(
        last_snapshot[
            "sports"
        ].get(
            sport,
            {},
        ).get(
            "error"
        )
        for sport in SPORTS
    )

    return (
        1
        if all_errors
        else 0
    )


# ============================================================
# PARÁMETROS
# ============================================================

def build_parser(
) -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        description=(
            "Analiza MLB, NFL y NBA "
            "independientemente y selecciona "
            "la mejor oportunidad."
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
    )

    parser.add_argument(
        "--date",
        help=(
            "Fecha YYYY-MM-DD; "
            "útil para pruebas"
        ),
    )

    parser.add_argument(
        "--config",
        default=str(
            PROJECT_ROOT
            /
            "config.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            PROJECT_ROOT
            /
            "reports"
        ),
    )

    return parser


# ============================================================
# OCULTAR API KEY DE ERRORES
# ============================================================

def _safe_error(
    message: str,
) -> str:

    api_key = os.environ.get(
        "API_SPORTS_KEY",
        "",
    )

    if api_key:

        message = message.replace(
            api_key,
            "[OCULTA]",
        )

    return message[:700]


# ============================================================
# TEMPORADA ANTERIOR
# ============================================================

def _previous_season(
    season: str,
) -> str:

    if "-" in season:

        parts = season.split(
            "-",
            1,
        )

        try:

            return (
                f"{int(parts[0]) - 1}-"
                f"{int(parts[1]) - 1}"
            )

        except ValueError:

            return season

    try:

        return str(
            int(season)
            -
            1
        )

    except ValueError:

        return season


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    raise SystemExit(
        run(
            build_parser()
            .parse_args()
        )
      )
