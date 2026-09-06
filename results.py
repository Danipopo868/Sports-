import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .api import ApiSportsClient
from .engine import normalize_games
from .history import load_history, save_history, update_history


ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"
HISTORY_FILE = ROOT / "dashboard_data" / "prediction_history.json"

TZ = ZoneInfo("America/Chicago")


def load_config():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config()
    client = ApiSportsClient()

    history = load_history(HISTORY_FILE)

    pendientes = [
        row
        for row in history
        if str(row.get("status", "")).upper() == "PENDIENTE"
    ]

    print("=" * 60)
    print("REVISOR DE RESULTADOS")
    print(f"Hora: {datetime.now(TZ).isoformat()}")
    print(f"Predicciones pendientes: {len(pendientes)}")
    print("=" * 60)

    if not pendientes:
        print("No hay predicciones pendientes.")
        return

    # Agrupar únicamente las fechas/deportes que tienen
    # predicciones pendientes.
    consultas = set()

    for row in pendientes:
        sport = str(row.get("sport", "")).upper().strip()
        date_iso = str(row.get("date", "")).strip()

        if sport and date_iso:
            consultas.add((sport, date_iso))

    for sport, date_iso in sorted(consultas):
        print()
        print(f"Revisando {sport} - {date_iso}")

        try:
            raw_games = client.games_for_date(
                sport=sport,
                date_iso=date_iso,
            )

            games = normalize_games(
                sport=sport,
                raw_games=raw_games,
            )

            # IMPORTANTE:
            # recommendation=None significa que este proceso
            # NO crea una predicción nueva.
            #
            # Solo permite que history.py encuentre partidos
            # terminados y resuelva predicciones existentes.
            update_history(
                history_path=HISTORY_FILE,
                sport=sport,
                recommendation=None,
                games=games,
                raw_games=raw_games,
            )

            print(f"{sport}: resultados comprobados.")

        except Exception as exc:
            print(f"{sport}: error consultando resultados: {exc}")

    # Leer nuevamente el historial después de las actualizaciones.
    history = load_history(HISTORY_FILE)

    pendientes = sum(
        1
        for row in history
        if str(row.get("status", "")).upper() == "PENDIENTE"
    )

    ganadas = sum(
        1
        for row in history
        if str(row.get("status", "")).upper() == "GANADA"
    )

    perdidas = sum(
        1
        for row in history
        if str(row.get("status", "")).upper() == "PERDIDA"
    )

    print()
    print("=" * 60)
    print("RESULTADO DE LA REVISION")
    print(f"GANADAS:    {ganadas}")
    print(f"PERDIDAS:   {perdidas}")
    print(f"PENDIENTES: {pendientes}")
    print("=" * 60)


if __name__ == "__main__":
    main()
