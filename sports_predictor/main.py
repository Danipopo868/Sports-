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
    def __init__(self, api_key: str, config: dict[str, Any]) -> None:
        self.config = config
        self.client = ApiSportsClient(api_key)
        self.mlb = MlbStatsClient()
        self.history_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    def scan(self, date_iso: str) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for sport in SPORTS:
            try:
                game_result = self.client.games_for_date(sport, date_iso)
                normalized = normalize_games(sport, game_result.response)
                games = [game for game in normalized if not is_finished(game.status)]
                game_ids = [game.id for game in games]
                odds_result = self.client.odds_for_date(sport, date_iso, game_ids)
                quotes = parse_quotes(odds_result.response, games)
                forms = self._forms_for_games(sport, games)
                matchups = self._mlb_matchups(games, date_iso) if sport == "MLB" else None
                recommendations, best_observed, notes = analyze_sport(
                    sport,
                    games,
                    quotes,
                    forms,
                    self.config,
                    matchups,
                )
                history_file = PROJECT_ROOT / "dashboard_data" / "prediction_history.json"
                history_rows = update_history(
                    history_file, sport, normalized, recommendations, datetime.now()
                )
                results[sport] = {
                    "games": len(games),
                    "quotes": len(quotes),
                    "remaining_requests": odds_result.remaining_requests,
                    "recommendations": recommendations,
                    "recommendation": recommendations[0] if recommendations else None,
                    "best_observed": best_observed,
                    "notes": notes,
                    "history_summary": history_summary(history_rows),
                    "error": None,
                }
            except (ApiSportsError, ValueError) as exc:
                results[sport] = {
                    "games": 0,
                    "quotes": 0,
                    "remaining_requests": None,
                    "recommendations": [],
                    "recommendation": None,
                    "best_observed": None,
                    "notes": [],
                    "error": _safe_error(str(exc)),
                }
        return results

    def _forms_for_games(self, sport: str, games: list[Any]) -> dict[str, TeamForm]:
        forms: dict[str, TeamForm] = {}
        history_limit = int(self.config["history_games"])
        for game in games:
            for team in (game.home, game.away):
                key = (sport, str(team.id), game.season)
                if key not in self.history_cache:
                    try:
                        history = self.client.team_history(sport, team.id, game.season)
                        self.history_cache[key] = history.response
                    except ApiSportsError:
                        self.history_cache[key] = []
                history_rows = list(self.history_cache[key])
                current_form = calculate_team_form(
                    sport,
                    team.id,
                    history_rows,
                    history_limit,
                    game.id,
                )
                if current_form.games < history_limit:
                    previous_season = _previous_season(game.season)
                    previous_key = (sport, str(team.id), previous_season)
                    if previous_key not in self.history_cache:
                        try:
                            previous = self.client.team_history(
                                sport, team.id, previous_season
                            )
                            self.history_cache[previous_key] = previous.response
                        except ApiSportsError:
                            self.history_cache[previous_key] = []
                    history_rows.extend(self.history_cache[previous_key])
                forms[str(team.id)] = calculate_team_form(
                    sport,
                    team.id,
                    history_rows,
                    history_limit,
                    game.id,
                )
        return forms

    def _mlb_matchups(self, games: list[Any], date_iso: str) -> dict[str, dict[str, Any]]:
        matchups: dict[str, dict[str, Any]] = {}
        for game in games:
            matchups[str(game.id)] = self.mlb.matchup(
                game.home.name,
                game.away.name,
                game.season_year,
                date_iso,
            )
        return matchups


def run(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    api_key = os.environ.get("API_SPORTS_KEY", "").strip()
    if not api_key:
        print(
            "ERROR: crea el secreto API_SPORTS_KEY en GitHub antes de ejecutar.",
            file=sys.stderr,
        )
        return 2

    timezone = ZoneInfo(str(config.get("timezone", "America/New_York")))
    analyzer = SportsAnalyzer(api_key, config)
    output_dir = Path(args.output).resolve()
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    duration_seconds = 0 if args.once else max(1, args.duration_minutes) * 60
    interval_seconds = max(1, args.interval_minutes) * 60
    started = time.monotonic()
    deadline = started + duration_seconds
    next_scan = started
    scan_number = 0
    last_snapshot: dict[str, Any] | None = None

    while not stop_event.is_set():
        scan_number += 1
        now = datetime.now(timezone)
        date_iso = args.date or now.date().isoformat()
        print(f"[{now.isoformat()}] Escaneo #{scan_number} de {date_iso}", flush=True)
        results = analyzer.scan(date_iso)
        last_snapshot = build_snapshot(now, date_iso, scan_number, results)
        latest_md, _ = save_reports(last_snapshot, output_dir)
        for sport in SPORTS:
            recommendation = results[sport].get("recommendation")
            state = (
                f"APOSTAR {recommendation.selection}"
                if recommendation
                else "NO APOSTAR"
            )
            print(f"{sport}: {state}", flush=True)
        print(f"Reporte actualizado: {latest_md}", flush=True)

        if args.once or duration_seconds == 0:
            break
        next_scan += interval_seconds
        remaining_session = deadline - time.monotonic()
        if remaining_session <= 0:
            break
        wait_seconds = min(max(0.0, next_scan - time.monotonic()), remaining_session)
        if wait_seconds <= 0:
            continue
        stop_event.wait(wait_seconds)
        if time.monotonic() >= deadline:
            break

    if last_snapshot is None:
        return 1
    all_errors = all(
        last_snapshot["sports"].get(sport, {}).get("error") for sport in SPORTS
    )
    return 1 if all_errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analiza MLB, NFL y NBA sin conectar con ninguna plataforma de apuestas."
    )
    parser.add_argument("--duration-minutes", type=int, default=180)
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--date", help="Fecha YYYY-MM-DD; útil para pruebas")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "reports"))
    return parser


def _safe_error(message: str) -> str:
    # Evita que una API incluya accidentalmente la clave dentro de un error visible.
    return message.replace(os.environ.get("API_SPORTS_KEY", ""), "[OCULTA]")[:700]


def _previous_season(season: str) -> str:
    if "-" in season:
        parts = season.split("-", 1)
        try:
            return f"{int(parts[0]) - 1}-{int(parts[1]) - 1}"
        except ValueError:
            return season
    try:
        return str(int(season) - 1)
    except ValueError:
        return season


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
