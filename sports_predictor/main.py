from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone as dt_timezone
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
from .history import history_summary, update_history
from .kalshi import find_kalshi_quote
from .mlb import MlbStatsClient
from .report import build_snapshot, save_reports


SPORTS = ("MLB", "NFL", "NCAAF", "NBA")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SportsAnalyzer:
    def __init__(
        self,
        api_key: str,
        config: dict[str, Any],
    ) -> None:
        self.config = config
        self.client = ApiSportsClient(api_key)
        self.mlb = MlbStatsClient()

        self.history_cache: dict[
            tuple[str, str, str],
            list[dict[str, Any]],
        ] = {}

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

                forms = (
                    self._forms_for_games(
                        sport,
                        games,
                    )
                )

                matchups = (
                    self._mlb_matchups(
                        games,
                        date_iso,
                    )
                    if sport == "MLB"
                    else None
                )

                (
                    recommendations,
                    best_observed,
                    notes,
                ) = analyze_sport(
                    sport,
                    games,
                    quotes,
                    forms,
                    self.config,
                    matchups,
                )

                # ==========================================
                # NO CREAR F5 SI EL PARTIDO YA EMPEZO
                # ==========================================

                if sport == "MLB":

                    now_utc = datetime.now(
                        dt_timezone.utc
                    )

                    valid_recommendations = []

                    for recommendation in recommendations:

                        if (
                            recommendation.market
                            == "Primeras 5 entradas"
                            and _game_has_started(
                                recommendation.start,
                                now_utc,
                            )
                        ):

                            print(
                                (
                                    "F5 OMITIDA | "
                                    "PARTIDO YA EMPEZO | "
                                    f"{recommendation.matchup} | "
                                    f"inicio={recommendation.start}"
                                ),
                                flush=True,
                            )

                            continue

                        valid_recommendations.append(
                            recommendation
                        )

                    recommendations = (
                        valid_recommendations
                    )

                # ==========================================
                # CUOTA KALSHI SOLO PARA CALCULAR PAGO
                # NO CAMBIA LA PREDICCION DEL MOTOR
                # ==========================================

                recommendations_with_kalshi = []
                kalshi_quotes_found = 0
                kalshi_financial: dict[
                    str,
                    dict[str, Any],
                ] = {}

                for recommendation in recommendations:

                    try:

                        kalshi_quote = find_kalshi_quote(
                            selection=(
                                recommendation.selection
                            ),
                            matchup=(
                                recommendation.matchup
                            ),
                            market=(
                                recommendation.market
                            ),
                            sport=sport,
                            game_start=(
                                recommendation.start
                            ),
                        )

                    except Exception as exc:

                        print(
                            (
                                "KALSHI ERROR | "
                                f"{recommendation.selection} | "
                                f"{exc}"
                            ),
                            flush=True,
                        )

                        kalshi_quote = None

                    if not kalshi_quote:

                        # La prediccion queda intacta. Solo marcamos
                        # que no hubo precio Kalshi para calcular pago.
                        recommendation = replace(
                            recommendation,
                            bookmaker="Kalshi",
                            decimal_odds=0.0,
                        )

                        recommendations_with_kalshi.append(
                            recommendation
                        )

                        continue

                    try:

                        kalshi_price = float(
                            kalshi_quote.get(
                                "price"
                            )
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        kalshi_price = 0.0

                    if not (
                        0.0
                        < kalshi_price
                        < 1.0
                    ):

                        recommendation = replace(
                            recommendation,
                            bookmaker="Kalshi",
                            decimal_odds=0.0,
                        )

                        recommendations_with_kalshi.append(
                            recommendation
                        )

                        continue

                    # Esta cuota decimal se usa UNICAMENTE
                    # para calcular cobro/ganancia con $100.
                    # No se recalculan probabilidad, edge ni EV.
                    decimal_odds = (
                        1.0
                        / kalshi_price
                    )

                    recommendation = replace(
                        recommendation,
                        bookmaker="Kalshi",
                        decimal_odds=(
                            decimal_odds
                        ),
                    )

                    kalshi_quotes_found += 1

                    financial_key = (
                        f"{sport}|"
                        f"{recommendation.game_id}|"
                        f"{recommendation.market}|"
                        f"{recommendation.selection}"
                    )

                    kalshi_financial[
                        financial_key
                    ] = {
                        "bookmaker": "Kalshi",
                        "odds": decimal_odds,
                        "odds_source": (
                            "LIVE_AT_RECOMMENDATION"
                        ),
                        "stake": 100.0,
                        "potential_return": (
                            100.0
                            * decimal_odds
                        ),
                        "potential_profit": (
                            100.0
                            * decimal_odds
                            - 100.0
                        ),
                        "kalshi_price": (
                            kalshi_price
                        ),
                        "kalshi_cents": (
                            kalshi_price
                            * 100.0
                        ),
                        "kalshi_ticker": (
                            kalshi_quote.get(
                                "ticker"
                            )
                        ),
                        "kalshi_side": (
                            kalshi_quote.get(
                                "side"
                            )
                        ),
                    }

                    print(
                        (
                            "KALSHI PAGO | "
                            f"{recommendation.selection} | "
                            f"{kalshi_quote.get('side')} | "
                            f"{kalshi_price * 100:.2f}c | "
                            f"cuota={decimal_odds:.4f} | "
                            f"cobro100=${100.0 * decimal_odds:.2f} | "
                            f"ganancia=${100.0 * decimal_odds - 100.0:.2f} | "
                            f"{kalshi_quote.get('ticker')}"
                        ),
                        flush=True,
                    )

                    recommendations_with_kalshi.append(
                        recommendation
                    )

                recommendations = (
                    recommendations_with_kalshi
                )

                # ==========================================
                # HISTORIAL
                # ==========================================

                history_file = (
                    PROJECT_ROOT
                    / "dashboard_data"
                    / "prediction_history.json"
                )

                # ==========================================
                # RECUPERAR PARTIDOS HISTORICOS PENDIENTES
                # SOLO PARA RESOLVER HISTORIAL.
                # NO ENTRAN EN EL MODELO NI EN LA PREDICCION.
                # ==========================================

                history_games = list(normalized)
                known_history_ids = {
                    str(game.id)
                    for game in history_games
                }

                try:
                    existing_history = json.loads(
                        history_file.read_text(encoding="utf-8")
                    ) if history_file.exists() else []
                except (OSError, json.JSONDecodeError):
                    existing_history = []

                pending_dates: set[str] = set()

                for old_row in existing_history:
                    if (
                        not isinstance(old_row, dict)
                        or str(old_row.get("sport") or "").upper() != sport
                        or old_row.get("status") != "PENDIENTE"
                    ):
                        continue

                    old_start = _parse_game_start(
                        old_row.get("start")
                    )

                    if old_start is None:
                        continue

                    old_date = old_start.date().isoformat()

                    if old_date != date_iso:
                        pending_dates.add(old_date)

                for pending_date in sorted(pending_dates):
                    try:
                        old_game_result = self.client.games_for_date(
                            sport,
                            pending_date,
                        )
                        old_normalized = normalize_games(
                            sport,
                            old_game_result.response,
                        )
                    except (ApiSportsError, ValueError) as exc:
                        print(
                            (
                                "HISTORIAL JUEGOS ERROR | "
                                f"{sport} | {pending_date} | {exc}"
                            ),
                            flush=True,
                        )
                        continue

                    for old_game in old_normalized:
                        old_game_id = str(old_game.id)

                        if old_game_id in known_history_ids:
                            continue

                        history_games.append(old_game)
                        known_history_ids.add(old_game_id)

                    print(
                        (
                            "HISTORIAL JUEGOS | "
                            f"{sport} | {pending_date} | "
                            f"recuperados={len(old_normalized)}"
                        ),
                        flush=True,
                    )

                history_rows = update_history(
                    history_file,
                    sport,
                    history_games,
                    recommendations,
                    datetime.now(),
                )

                # Si la seleccion ya existia en el historial SIN CUOTA,
                # completar ahora sus datos financieros de Kalshi.
                history_changed = False

                for row in history_rows:

                    row_key = str(
                        row.get("key")
                        or (
                            f"{row.get('sport')}|"
                            f"{row.get('game_id')}|"
                            f"{row.get('market')}|"
                            f"{row.get('selection')}"
                        )
                    )

                    financial = (
                        kalshi_financial.get(
                            row_key
                        )
                    )

                    if not financial:
                        continue

                    row.update(
                        financial
                    )

                    history_changed = True

                if history_changed:

                    history_file.write_text(
                        json.dumps(
                            history_rows,
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )

                results[sport] = {
                    "games": len(games),
                    "quotes": len(quotes),
                    "kalshi_quotes": (
                        kalshi_quotes_found
                    ),
                    "remaining_requests": (
                        odds_result.remaining_requests
                    ),
                    "recommendations": (
                        recommendations
                    ),
                    "recommendation": (
                        recommendations[0]
                        if recommendations
                        else None
                    ),
                    "best_observed": (
                        best_observed
                    ),
                    "notes": notes,
                    "history_summary": (
                        history_summary(
                            history_rows
                        )
                    ),
                    "error": None,
                }

            except (
                ApiSportsError,
                ValueError,
            ) as exc:

                results[sport] = {
                    "games": 0,
                    "quotes": 0,
                    "kalshi_quotes": 0,
                    "remaining_requests": None,
                    "recommendations": [],
                    "recommendation": None,
                    "best_observed": None,
                    "notes": [],
                    "error": _safe_error(
                        str(exc)
                    ),
                }

        return results

    def _forms_for_games(
        self,
        sport: str,
        games: list[Any],
    ) -> dict[str, TeamForm]:

        forms: dict[str, TeamForm] = {}

        history_limit = int(
            self.config["history_games"]
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

                if key not in self.history_cache:

                    try:

                        history = (
                            self.client.team_history(
                                sport,
                                team.id,
                                game.season,
                            )
                        )

                        self.history_cache[key] = (
                            history.response
                        )

                    except ApiSportsError:

                        self.history_cache[key] = []

                history_rows = list(
                    self.history_cache[key]
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

                if (
                    current_form.games
                    < history_limit
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
                        not in self.history_cache
                    ):

                        try:

                            previous = (
                                self.client.team_history(
                                    sport,
                                    team.id,
                                    previous_season,
                                )
                            )

                            self.history_cache[
                                previous_key
                            ] = previous.response

                        except ApiSportsError:

                            self.history_cache[
                                previous_key
                            ] = []

                    history_rows.extend(
                        self.history_cache[
                            previous_key
                        ]
                    )

                forms[
                    str(team.id)
                ] = calculate_team_form(
                    sport,
                    team.id,
                    history_rows,
                    history_limit,
                    game.id,
                )

        return forms

    def _mlb_matchups(
        self,
        games: list[Any],
        date_iso: str,
    ) -> dict[str, dict[str, Any]]:

        matchups: dict[
            str,
            dict[str, Any],
        ] = {}

        for game in games:

            matchups[
                str(game.id)
            ] = self.mlb.matchup(
                game.home.name,
                game.away.name,
                game.season_year,
                date_iso,
            )

        return matchups
def _parse_game_start(
    value: Any,
) -> datetime | None:

    if isinstance(
        value,
        datetime,
    ):
        dt = value

    elif isinstance(
        value,
        (int, float),
    ):

        timestamp = float(
            value
        )

        if timestamp > 10_000_000_000:
            timestamp /= 1000.0

        try:

            return datetime.fromtimestamp(
                timestamp,
                tz=dt_timezone.utc,
            )

        except (
            OSError,
            OverflowError,
            ValueError,
        ):
            return None

    else:

        text = str(
            value or ""
        ).strip()

        if not text:
            return None

        if re.fullmatch(
            r"\d+(?:\.\d+)?",
            text,
        ):

            timestamp = float(
                text
            )

            if timestamp > 10_000_000_000:
                timestamp /= 1000.0

            try:

                return datetime.fromtimestamp(
                    timestamp,
                    tz=dt_timezone.utc,
                )

            except (
                OSError,
                OverflowError,
                ValueError,
            ):
                return None

        try:

            dt = datetime.fromisoformat(
                text.replace(
                    "Z",
                    "+00:00",
                )
            )

        except ValueError:
            return None

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=dt_timezone.utc
        )

    return dt.astimezone(
        dt_timezone.utc
    )


def _game_has_started(
    start: Any,
    now_utc: datetime,
) -> bool:

    start_time = _parse_game_start(
        start
    )

    if start_time is None:
        return False

    return (
        start_time
        <= now_utc
    )


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

    timezone = ZoneInfo(
        str(
            config.get(
                "timezone",
                "America/New_York",
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

    stop_event = threading.Event()

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

    duration_seconds = (
        0
        if args.once
        else max(
            1,
            args.duration_minutes,
        ) * 60
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
        + duration_seconds
    )

    next_scan = started

    scan_number = 0

    last_snapshot: (
        dict[str, Any]
        | None
    ) = None

    while not stop_event.is_set():

        scan_number += 1

        now = datetime.now(
            timezone
        )

        date_iso = (
            args.date
            or now.date().isoformat()
        )

        print(
            (
                f"[{now.isoformat()}] "
                f"Escaneo #{scan_number} "
                f"de {date_iso}"
            ),
            flush=True,
        )

        results = analyzer.scan(
            date_iso
        )

        last_snapshot = (
            build_snapshot(
                now,
                date_iso,
                scan_number,
                results,
            )
        )

        latest_md, _ = save_reports(
            last_snapshot,
            output_dir,
        )

        for sport in SPORTS:

            recommendation = (
                results[sport].get(
                    "recommendation"
                )
            )

            state = (
                (
                    "APOSTAR "
                    f"{recommendation.selection}"
                )
                if recommendation
                else "NO APOSTAR"
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

        if (
            args.once
            or duration_seconds == 0
        ):
            break

        next_scan += (
            interval_seconds
        )

        remaining_session = (
            deadline
            - time.monotonic()
        )

        if remaining_session <= 0:
            break

        wait_seconds = min(
            max(
                0.0,
                next_scan
                - time.monotonic(),
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
            >= deadline
        ):
            break

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


def build_parser(
) -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        description=(
            "Analiza MLB, NFL, NCAAF y NBA "
            "sin conectar con ninguna "
            "plataforma de apuestas."
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
            / "config.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            PROJECT_ROOT
            / "reports"
        ),
    )

    return parser


def _safe_error(
    message: str,
) -> str:

    return message.replace(
        os.environ.get(
            "API_SPORTS_KEY",
            "",
        ),
        "[OCULTA]",
    )[:700]


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
            int(season) - 1
        )

    except ValueError:

        return season


if __name__ == "__main__":

    raise SystemExit(
        run(
            build_parser().parse_args()
        )
)
