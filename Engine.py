from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

from .mlb import (
    first_five_home_probability,
    full_game_home_probability,
)


# ============================================================
# ESTRUCTURAS DE DATOS
# ============================================================

@dataclass(frozen=True)
class Team:
    id: int | str
    name: str


@dataclass(frozen=True)
class Game:
    sport: str
    id: int | str
    home: Team
    away: Team
    start: str
    status: str
    season: str
    season_year: int
    raw: dict[str, Any]


@dataclass(frozen=True)
class TeamForm:
    games: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    average_for: float
    average_against: float
    average_margin: float


@dataclass(frozen=True)
class Quote:
    game_id: str
    market: str
    bookmaker: str
    side: str
    decimal_odds: float


@dataclass(frozen=True)
class Candidate:
    sport: str
    game_id: str
    matchup: str
    start: str
    market: str
    selection: str
    bookmaker: str
    decimal_odds: float
    model_probability: float
    break_even_probability: float
    edge: float
    expected_value: float
    bookmakers: int
    data_quality: int
    passes_filters: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# CONFIGURACION INTERNA
# ============================================================

FINISHED_STATUS_WORDS = {
    "aot",
    "closed",
    "final",
    "finished",
    "ft",
    "game finished",
    "match finished",
}

SPORT_MARGIN_SCALE = {
    "MLB": 3.0,
    "NFL": 13.0,
    "NBA": 17.0,
}

HOME_ADVANTAGE_LOGIT = {
    "MLB": 0.10,
    "NFL": 0.14,
    "NBA": 0.16,
}


# ============================================================
# NORMALIZAR PARTIDOS
# ============================================================

def normalize_games(
    sport: str,
    raw_games: Iterable[dict[str, Any]],
) -> list[Game]:

    games: list[Game] = []

    for raw in raw_games:

        teams = raw.get("teams") or {}

        home_raw = teams.get("home") or {}

        away_raw = (
            teams.get("away")
            or teams.get("visitors")
            or {}
        )

        game_id = raw.get("id")
        home_id = home_raw.get("id")
        away_id = away_raw.get("id")

        if game_id is None or home_id is None or away_id is None:
            continue

        home_name = _team_name(home_raw)
        away_name = _team_name(away_raw)

        if not home_name or not away_name:
            continue

        season_raw = (
            (raw.get("league") or {}).get("season")
            or raw.get("season")
        )

        season = str(
            season_raw
            or datetime.utcnow().year
        )

        season_year = _season_number(season_raw)

        games.append(
            Game(
                sport=sport,
                id=game_id,
                home=Team(
                    id=home_id,
                    name=home_name,
                ),
                away=Team(
                    id=away_id,
                    name=away_name,
                ),
                start=_start_time(raw),
                status=_status_text(raw),
                season=season,
                season_year=season_year,
                raw=raw,
            )
        )

    return games


# ============================================================
# FORMA RECIENTE
# ============================================================

def calculate_team_form(
    sport: str,
    team_id: int | str,
    raw_games: Iterable[dict[str, Any]],
    limit: int,
    exclude_game_id: int | str | None = None,
) -> TeamForm:

    normalized = normalize_games(
        sport,
        raw_games,
    )

    eligible: list[
        tuple[
            float,
            Game,
            float,
            float,
        ]
    ] = []

    for game in normalized:

        if (
            exclude_game_id is not None
            and str(game.id) == str(exclude_game_id)
        ):
            continue

        if not is_finished(game.status):
            continue

        home_score = score_for_side(
            game.raw,
            "home",
        )

        away_score = score_for_side(
            game.raw,
            "away",
        )

        if home_score is None or away_score is None:
            continue

        if str(game.home.id) == str(team_id):

            scored = home_score
            allowed = away_score

        elif str(game.away.id) == str(team_id):

            scored = away_score
            allowed = home_score

        else:
            continue

        eligible.append(
            (
                _sort_timestamp(game.raw),
                game,
                scored,
                allowed,
            )
        )

    eligible.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected = eligible[
        : max(1, limit)
    ]

    wins = sum(
        scored > allowed
        for _, _, scored, allowed in selected
    )

    losses = sum(
        scored < allowed
        for _, _, scored, allowed in selected
    )

    ties = (
        len(selected)
        - wins
        - losses
    )

    total = len(selected)

    if not total:

        return TeamForm(
            games=0,
            wins=0,
            losses=0,
            ties=0,
            win_rate=0.5,
            average_for=0.0,
            average_against=0.0,
            average_margin=0.0,
        )

    average_for = (
        sum(
            item[2]
            for item in selected
        )
        / total
    )

    average_against = (
        sum(
            item[3]
            for item in selected
        )
        / total
    )

    return TeamForm(
        games=total,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=(
            wins
            + 0.5 * ties
        )
        / total,
        average_for=average_for,
        average_against=average_against,
        average_margin=(
            average_for
            - average_against
        ),
    )


# ============================================================
# LEER CUOTAS
# ============================================================

def parse_quotes(
    raw_odds: Iterable[dict[str, Any]],
    games: Iterable[Game],
) -> list[Quote]:

    game_map = {
        str(game.id): game
        for game in games
    }

    quotes: list[Quote] = []

    for item in raw_odds:

        game_id = _odds_game_id(item)

        game = game_map.get(
            str(game_id)
        )

        if not game:
            continue

        bookmakers = (
            item.get("bookmakers")
            or item.get("bookmaker")
            or []
        )

        if isinstance(
            bookmakers,
            dict,
        ):
            bookmakers = [bookmakers]

        for bookmaker in bookmakers:

            bookmaker_name = str(
                bookmaker.get("name")
                or "Casa desconocida"
            )

            bets = (
                bookmaker.get("bets")
                or bookmaker.get("markets")
                or []
            )

            for bet in bets:

                market_name = str(
                    bet.get("name")
                    or bet.get("key")
                    or ""
                )

                market = classify_market(
                    game.sport,
                    market_name,
                )

                if not market:
                    continue

                values = (
                    bet.get("values")
                    or bet.get("outcomes")
                    or []
                )

                for value in values:

                    label = str(
                        value.get("value")
                        or value.get("name")
                        or value.get("label")
                        or ""
                    )

                    side = selection_side(
                        label,
                        game,
                    )

                    decimal_odds = (
                        to_decimal_odds(
                            value.get("odd")
                            or value.get("odds")
                            or value.get("price")
                        )
                    )

                    if (
                        side
                        and decimal_odds
                        and 1.01
                        <= decimal_odds
                        <= 50
                    ):

                        quotes.append(
                            Quote(
                                game_id=str(
                                    game.id
                                ),
                                market=market,
                                bookmaker=bookmaker_name,
                                side=side,
                                decimal_odds=decimal_odds,
                            )
                        )

    return quotes


# ============================================================
# MOTOR PRINCIPAL
# ============================================================

def analyze_sport(
    sport: str,
    games: list[Game],
    quotes: list[Quote],
    forms: dict[str, TeamForm],
    config: dict[str, Any],
    mlb_matchups: dict[str, dict[str, Any]] | None = None,
) -> tuple[
    Candidate | None,
    Candidate | None,
    list[str],
]:

    filters = config["filters"]
    model = config["model"]

    all_candidates: list[Candidate] = []

    notes: list[str] = []


    # ========================================================
    # ANALISIS DE APUESTAS
    # ========================================================

    for game in games:

        game_quotes = [
            quote
            for quote in quotes
            if quote.game_id == str(game.id)
        ]

        if not game_quotes:
            continue

        home_form = forms.get(
            str(game.home.id),
            _empty_form(),
        )

        away_form = forms.get(
            str(game.away.id),
            _empty_form(),
        )

        markets = sorted(
            {
                quote.market
                for quote in game_quotes
            }
        )

        for market_name in markets:

            market_quotes = [
                quote
                for quote in game_quotes
                if quote.market
                == market_name
            ]

            book_pairs = (
                _bookmaker_pairs(
                    market_quotes
                )
            )

            if not book_pairs:
                continue

            market_home_probability = (
                sum(
                    devig_two_way(
                        pair[
                            "home"
                        ].decimal_odds,
                        pair[
                            "away"
                        ].decimal_odds,
                    )[0]
                    for pair
                    in book_pairs.values()
                )
                / len(book_pairs)
            )


            # =================================================
            # F5 MLB
            # =================================================

            if (
                sport == "MLB"
                and market_name
                == "Primeras 5 entradas"
            ):

                matchup = (
                    mlb_matchups
                    or {}
                ).get(
                    str(game.id),
                    {},
                )

                form_home_probability = (
                    first_five_home_probability(
                        matchup
                    )
                )

                if (
                    form_home_probability
                    is None
                ):

                    notes.append(
                        f"{game.away.name} @ "
                        f"{game.home.name}: "
                        "F5 omitido porque faltan "
                        "datos suficientes de los "
                        "abridores."
                    )

                    continue

                pitcher_complete = True


            # =================================================
            # GANADOR JUEGO NORMAL
            # =================================================

            else:

                form_home_probability = (
                    form_home_probability_for_game(
                        sport,
                        home_form,
                        away_form,
                    )
                )

                pitcher_complete = False


            sample_factor = (
                min(
                    home_form.games,
                    away_form.games,
                )
                / max(
                    1,
                    int(
                        config[
                            "history_games"
                        ]
                    ),
                )
            )

            combined_home_probability = (
                combine_probabilities(
                    market_home_probability,
                    form_home_probability,
                    float(
                        model[
                            "market_weight"
                        ]
                    ),
                    float(
                        model[
                            "form_weight"
                        ]
                    ),
                    sample_factor,
                    float(
                        model[
                            "maximum_probability"
                        ]
                    ),
                )
            )

            quality = data_quality(
                home_form,
                away_form,
                len(book_pairs),
                int(
                    config[
                        "history_games"
                    ]
                ),
                pitcher_complete,
            )


            # =================================================
            # HOME / AWAY
            # =================================================

            for side in (
                "home",
                "away",
            ):

                best = max(
                    (
                        quote
                        for quote
                        in market_quotes
                        if quote.side
                        == side
                    ),
                    key=lambda quote:
                        quote.decimal_odds,
                    default=None,
                )

                if not best:
                    continue

                if side == "home":

                    probability = (
                        combined_home_probability
                    )

                    selection = (
                        game.home.name
                    )

                else:

                    probability = (
                        1.0
                        - combined_home_probability
                    )

                    selection = (
                        game.away.name
                    )


                break_even = (
                    1.0
                    / best.decimal_odds
                )

                edge = (
                    probability
                    - break_even
                )

                expected_value = (
                    probability
                    * best.decimal_odds
                    - 1.0
                )


                history_ok = (
                    min(
                        home_form.games,
                        away_form.games,
                    )
                    >= int(
                        filters[
                            "minimum_history_games"
                        ]
                    )
                )


                # =================================================
                # FILTROS
                # =================================================

                failures: list[str] = []

                if probability < float(
                    filters[
                        "minimum_probability"
                    ]
                ):

                    failures.append(
                        "FALLA probabilidad: "
                        f"{probability * 100:.1f}% "
                        "< "
                        f"{float(filters['minimum_probability']) * 100:.1f}%"
                    )

                if edge < float(
                    filters[
                        "minimum_edge"
                    ]
                ):

                    failures.append(
                        "FALLA edge: "
                        f"{edge * 100:.1f}% "
                        "< "
                        f"{float(filters['minimum_edge']) * 100:.1f}%"
                    )

                if expected_value < float(
                    filters[
                        "minimum_expected_value"
                    ]
                ):

                    failures.append(
                        "FALLA EV: "
                        f"{expected_value * 100:.1f}% "
                        "< "
                        f"{float(filters['minimum_expected_value']) * 100:.1f}%"
                    )

                if len(book_pairs) < int(
                    filters[
                        "minimum_bookmakers"
                    ]
                ):

                    failures.append(
                        "FALLA casas: "
                        f"{len(book_pairs)} "
                        "< "
                        f"{int(filters['minimum_bookmakers'])}"
                    )

                if quality < int(
                    filters[
                        "minimum_data_quality"
                    ]
                ):

                    failures.append(
                        "FALLA calidad: "
                        f"{quality}/100 "
                        "< "
                        f"{int(filters['minimum_data_quality'])}/100"
                    )

                if not history_ok:

                    failures.append(
                        "FALLA historial: "
                        f"{min(home_form.games, away_form.games)} "
                        "< "
                        f"{int(filters['minimum_history_games'])}"
                    )


                passes = (
                    len(failures)
                    == 0
                )


                reasons = [
                    (
                        f"Forma {game.home.name}: "
                        f"{home_form.wins}-"
                        f"{home_form.losses}; "
                        f"{game.away.name}: "
                        f"{away_form.wins}-"
                        f"{away_form.losses}"
                    ),
                    (
                        "Consenso sin margen de "
                        f"{len(book_pairs)} "
                        "casa(s)"
                    ),
                ]

                reasons.extend(
                    failures
                )


                all_candidates.append(
                    Candidate(
                        sport=sport,
                        game_id=str(
                            game.id
                        ),
                        matchup=(
                            f"{game.away.name} "
                            "@ "
                            f"{game.home.name}"
                        ),
                        start=game.start,
                        market=market_name,
                        selection=selection,
                        bookmaker=best.bookmaker,
                        decimal_odds=(
                            best.decimal_odds
                        ),
                        model_probability=(
                            probability
                        ),
                        break_even_probability=(
                            break_even
                        ),
                        edge=edge,
                        expected_value=(
                            expected_value
                        ),
                        bookmakers=len(
                            book_pairs
                        ),
                        data_quality=quality,
                        passes_filters=(
                            passes
                        ),
                        reasons=tuple(
                            reasons
                        ),
                    )
                )


    # ========================================================
    # MEJOR OPCION OBSERVADA
    # ========================================================

    best_observed = max(
        all_candidates,
        key=lambda candidate: (
            candidate.expected_value,
            candidate.edge,
        ),
        default=None,
    )


    # ========================================================
    # OPCIONES QUE PASARON FILTROS
    # ========================================================

    eligible = [
        candidate
        for candidate
        in all_candidates
        if candidate.passes_filters
    ]


    recommendation = max(
        eligible,
        key=lambda candidate: (
            candidate.expected_value,
            candidate.edge,
        ),
        default=None,
    )


    # ========================================================
    # MLB TOP 3 GANADORES
    # NO DEPENDE DE QUE SEA BUENA APUESTA
    # ========================================================

    if (
        sport == "MLB"
        and mlb_matchups
    ):

        predictions: list[
            tuple[
                float,
                Game,
                str,
                dict[str, Any],
            ]
        ] = []


        for game in games:

            matchup = (
                mlb_matchups.get(
                    str(game.id),
                    {},
                )
            )

            if not matchup:
                continue


            home_probability = (
                full_game_home_probability(
                    matchup
                )
            )

            if home_probability is None:
                continue


            if home_probability >= 0.50:

                predicted_winner = (
                    game.home.name
                )

                winner_probability = (
                    home_probability
                )

            else:

                predicted_winner = (
                    game.away.name
                )

                winner_probability = (
                    1.0
                    - home_probability
                )


            predictions.append(
                (
                    winner_probability,
                    game,
                    predicted_winner,
                    matchup,
                )
            )


        predictions.sort(
            key=lambda item:
                item[0],
            reverse=True,
        )


        if predictions:

            notes.append(
                ""
            )

            notes.append(
                "========================================"
            )

            notes.append(
                "⚾ MLB TOP 3 GANADORES DEL JUEGO"
            )

            notes.append(
                "========================================"
            )


            for rank, (
                winner_probability,
                game,
                predicted_winner,
                matchup,
            ) in enumerate(
                predictions[:3],
                start=1,
            ):

                notes.append(
                    ""
                )

                notes.append(
                    f"#{rank} "
                    f"{game.away.name} "
                    "@ "
                    f"{game.home.name}"
                )

                notes.append(
                    "GANADOR PREDICHO: "
                    f"{predicted_winner}"
                )

                notes.append(
                    "Probabilidad estimada: "
                    f"{winner_probability * 100:.1f}%"
                )


                # =============================================
                # F5 SEPARADO
                # =============================================

                f5_home_probability = (
                    first_five_home_probability(
                        matchup
                    )
                )

                if (
                    f5_home_probability
                    is not None
                ):

                    if (
                        f5_home_probability
                        >= 0.50
                    ):

                        f5_winner = (
                            game.home.name
                        )

                        f5_probability = (
                            f5_home_probability
                        )

                    else:

                        f5_winner = (
                            game.away.name
                        )

                        f5_probability = (
                            1.0
                            - f5_home_probability
                        )


                    notes.append(
                        "F5 PREDICHO: "
                        f"{f5_winner}"
                    )

                    notes.append(
                        "Probabilidad F5: "
                        f"{f5_probability * 100:.1f}%"
                    )

                else:

                    notes.append(
                        "F5: datos insuficientes"
                    )


                # =============================================
                # ABRIDORES SI ESTAN DISPONIBLES
                # =============================================

                home_block = (
                    _matchup_side(
                        matchup,
                        "home",
                    )
                )

                away_block = (
                    _matchup_side(
                        matchup,
                        "away",
                    )
                )


                home_starter = (
                    _starter_text(
                        home_block
                    )
                )

                away_starter = (
                    _starter_text(
                        away_block
                    )
                )


                if away_starter:

                    notes.append(
                        "Abridor visitante: "
                        f"{away_starter}"
                    )


                if home_starter:

                    notes.append(
                        "Abridor local: "
                        f"{home_starter}"
                    )


                # =============================================
                # BATEO VS ABRIDOR CONTRARIO
                # =============================================

                away_bvp = (
                    _bvp_text(
                        away_block
                    )
                )

                home_bvp = (
                    _bvp_text(
                        home_block
                    )
                )


                if away_bvp:

                    notes.append(
                        "Bateo visitante vs abridor: "
                        f"{away_bvp}"
                    )


                if home_bvp:

                    notes.append(
                        "Bateo local vs abridor: "
                        f"{home_bvp}"
                    )


    # ========================================================
    # NOTAS GENERALES
    # ========================================================

    if not games:

        notes.append(
            "No hay partidos disponibles "
            "para la fecha analizada."
        )

    elif not quotes:

        notes.append(
            "No llegaron cuotas comparables; "
            "sin precio no se puede calcular "
            "rentabilidad."
        )

    elif not recommendation:

        notes.append(
            "Ninguna opción superó "
            "simultáneamente todos los "
            "filtros de valor y calidad."
        )

        if best_observed:

            notes.append(
                ""
            )

            notes.append(
                "MEJOR OPCION OBSERVADA:"
            )

            notes.append(
                f"{best_observed.matchup}"
            )

            notes.append(
                f"Mercado: "
                f"{best_observed.market}"
            )

            notes.append(
                f"Selección: "
                f"{best_observed.selection}"
            )

            notes.append(
                "Probabilidad modelo: "
                f"{best_observed.model_probability * 100:.1f}%"
            )

            notes.append(
                "Punto equilibrio: "
                f"{best_observed.break_even_probability * 100:.1f}%"
            )

            notes.append(
                "Edge: "
                f"{best_observed.edge * 100:.1f}%"
            )

            notes.append(
                "EV: "
                f"{best_observed.expected_value * 100:.1f}%"
            )

            notes.append(
                "Calidad: "
                f"{best_observed.data_quality}/100"
            )

            for reason in (
                best_observed.reasons
            ):

                notes.append(
                    reason
                )


    return (
        recommendation,
        best_observed,
        notes,
    )


# ============================================================
# PROBABILIDAD POR FORMA
# ============================================================

def form_home_probability_for_game(
    sport: str,
    home: TeamForm,
    away: TeamForm,
) -> float:

    scale = SPORT_MARGIN_SCALE.get(
        sport,
        12.0,
    )

    win_edge = (
        2.0
        * (
            home.win_rate
            - away.win_rate
        )
    )

    margin_edge = math.tanh(
        (
            home.average_margin
            - away.average_margin
        )
        / scale
    )

    logit_value = (
        HOME_ADVANTAGE_LOGIT.get(
            sport,
            0.12,
        )
        + 0.58 * win_edge
        + 0.42 * margin_edge
    )

    return min(
        0.82,
        max(
            0.18,
            sigmoid(
                logit_value
            ),
        ),
    )


# ============================================================
# COMBINAR MERCADO + MODELO
# ============================================================

def combine_probabilities(
    market_probability: float,
    form_probability: float,
    market_weight: float,
    form_weight: float,
    sample_factor: float,
    maximum_probability: float,
) -> float:

    total_weight = max(
        0.0001,
        market_weight
        + form_weight,
    )

    blended_logit = (
        market_weight
        * logit(
            market_probability
        )
        + form_weight
        * logit(
            form_probability
        )
    ) / total_weight

    raw = sigmoid(
        blended_logit
    )

    reliability = min(
        1.0,
        max(
            0.25,
            sample_factor,
        ),
    )

    shrunk = (
        0.5
        + (
            raw
            - 0.5
        )
        * reliability
    )

    return min(
        maximum_probability,
        max(
            1.0
            - maximum_probability,
            shrunk,
        ),
    )


# ============================================================
# CALIDAD DE DATOS
# ============================================================

def data_quality(
    home: TeamForm,
    away: TeamForm,
    bookmaker_count: int,
    desired_history: int,
    pitcher_complete: bool,
) -> int:

    history_score = (
        min(
            home.games,
            away.games,
        )
        / max(
            1,
            desired_history,
        )
        * 45
    )

    bookmaker_score = (
        min(
            bookmaker_count,
            5,
        )
        / 5
        * 35
    )

    pitcher_score = (
        15
        if pitcher_complete
        else 5
    )

    return min(
        100,
        round(
            5
            + history_score
            + bookmaker_score
            + pitcher_score
        ),
    )


# ============================================================
# CLASIFICAR MERCADOS
# ============================================================

def classify_market(
    sport: str,
    market_name: str,
) -> str | None:

    name = _normalized_text(
        market_name
    )

    if sport == "MLB":

        if any(
            token in name
            for token in (
                "first 5",
                "first five",
                "1st 5",
                "5 innings",
                "innings 1 5",
                "f5",
            )
        ):

            if not any(
                token in name
                for token in (
                    "total",
                    "over",
                    "under",
                    "spread",
                    "handicap",
                )
            ):

                return (
                    "Primeras 5 entradas"
                )


    moneyline_tokens = (
        "moneyline",
        "match winner",
        "game winner",
        "winner",
        "home away",
        "to win",
        "1x2",
    )

    excluded = (
        "quarter",
        "half",
        "inning",
        "period",
        "total",
        "over",
        "under",
        "spread",
        "handicap",
    )

    if (
        any(
            token in name
            for token
            in moneyline_tokens
        )
        and not any(
            token in name
            for token
            in excluded
        )
    ):

        return (
            "Ganador del partido"
        )

    return None


# ============================================================
# IDENTIFICAR EQUIPO
# ============================================================

def selection_side(
    label: str,
    game: Game,
) -> str | None:

    normalized = (
        _normalized_text(
            label
        )
    )

    home_name = (
        _normalized_text(
            game.home.name
        )
    )

    away_name = (
        _normalized_text(
            game.away.name
        )
    )

    if (
        normalized
        in {
            "home",
            "1",
            "team 1",
            "local",
        }
        or (
            home_name
            and (
                home_name
                in normalized
                or normalized
                in home_name
            )
        )
    ):

        return "home"

    if (
        normalized
        in {
            "away",
            "2",
            "team 2",
            "visitor",
            "visitors",
            "visitante",
        }
        or (
            away_name
            and (
                away_name
                in normalized
                or normalized
                in away_name
            )
        )
    ):

        return "away"

    return None


# ============================================================
# QUITAR MARGEN DE CASA
# ============================================================

def devig_two_way(
    home_odds: float,
    away_odds: float,
) -> tuple[
    float,
    float,
]:

    home_implied = (
        1.0
        / home_odds
    )

    away_implied = (
        1.0
        / away_odds
    )

    total = (
        home_implied
        + away_implied
    )

    return (
        home_implied
        / total,
        away_implied
        / total,
    )


# ============================================================
# CONVERTIR CUOTAS
# ============================================================

def to_decimal_odds(
    value: Any,
) -> float | None:

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if number <= -100:

        return (
            1.0
            + 100.0
            / abs(number)
        )

    if number >= 100:

        return (
            1.0
            + number
            / 100.0
        )

    return (
        number
        if number > 1.0
        else None
    )


# ============================================================
# RESULTADOS
# ============================================================

def score_for_side(
    raw: dict[str, Any],
    side: str,
) -> float | None:

    scores = (
        raw.get("scores")
        or {}
    )

    key = side

    if (
        side == "away"
        and "away"
        not in scores
    ):

        key = "visitors"

    block = scores.get(
        key
    )

    if block is None:
        return None

    if isinstance(
        block,
        (
            int,
            float,
            str,
        ),
    ):

        return _optional_float(
            block
        )

    if isinstance(
        block,
        dict,
    ):

        for field in (
            "total",
            "points",
            "score",
            "runs",
        ):

            if (
                field in block
                and block[field]
                is not None
            ):

                return (
                    _optional_float(
                        block[field]
                    )
                )

    return None


# ============================================================
# ESTADO FINAL
# ============================================================

def is_finished(
    status: str,
) -> bool:

    normalized = (
        _normalized_text(
            status
        )
    )

    return (
        normalized
        in FINISHED_STATUS_WORDS
        or any(
            token
            in normalized
            for token in (
                "finished",
                "final",
                "game over",
            )
        )
    )


# ============================================================
# MATEMATICAS
# ============================================================

def sigmoid(
    value: float,
) -> float:

    return (
        1.0
        / (
            1.0
            + math.exp(
                -value
            )
        )
    )


def logit(
    probability: float,
) -> float:

    clipped = min(
        0.999,
        max(
            0.001,
            probability,
        ),
    )

    return math.log(
        clipped
        / (
            1.0
            - clipped
        )
    )


# ============================================================
# AGRUPAR CASAS
# ============================================================

def _bookmaker_pairs(
    quotes: list[Quote],
) -> dict[
    str,
    dict[
        str,
        Quote,
    ],
]:

    grouped: dict[
        str,
        dict[
            str,
            Quote,
        ],
    ] = {}

    for quote in quotes:

        current = grouped.setdefault(
            quote.bookmaker,
            {},
        )

        existing = current.get(
            quote.side
        )

        if (
            not existing
            or quote.decimal_odds
            > existing.decimal_odds
        ):

            current[
                quote.side
            ] = quote

    return {
        bookmaker: sides
        for bookmaker, sides
        in grouped.items()
        if (
            "home" in sides
            and "away" in sides
        )
    }


# ============================================================
# ID DE JUEGO
# ============================================================

def _odds_game_id(
    item: dict[str, Any],
) -> Any:

    game = item.get(
        "game"
    )

    if isinstance(
        game,
        dict,
    ):

        return game.get(
            "id"
        )

    if game is not None:
        return game

    fixture = item.get(
        "fixture"
    )

    if isinstance(
        fixture,
        dict,
    ):

        return fixture.get(
            "id"
        )

    return (
        item.get("game_id")
        or item.get("fixture_id")
        or item.get("id")
    )


# ============================================================
# NOMBRE DEL EQUIPO
# ============================================================

def _team_name(
    team: dict[str, Any],
) -> str:

    name = str(
        team.get("name")
        or ""
    ).strip()

    nickname = str(
        team.get("nickname")
        or ""
    ).strip()

    if (
        nickname
        and nickname.lower()
        not in name.lower()
    ):

        return (
            f"{name} "
            f"{nickname}"
        ).strip()

    return name


# ============================================================
# TEMPORADA
# ============================================================

def _season_number(
    value: Any,
) -> int:

    match = re.search(
        r"(20\d{2})",
        str(
            value
            or ""
        ),
    )

    if match:

        return int(
            match.group(1)
        )

    return (
        datetime.utcnow().year
    )


# ============================================================
# HORA
# ============================================================

def _start_time(
    raw: dict[str, Any],
) -> str:

    date = raw.get(
        "date"
    )

    if isinstance(
        date,
        dict,
    ):

        return str(
            date.get("start")
            or date.get("date")
            or ""
        )

    return str(
        date
        or raw.get("time")
        or raw.get("timestamp")
        or ""
    )


# ============================================================
# STATUS
# ============================================================

def _status_text(
    raw: dict[str, Any],
) -> str:

    status = raw.get(
        "status"
    )

    if isinstance(
        status,
        dict,
    ):

        values = [
            status.get("short"),
            status.get("long"),
        ]

        return " ".join(
            str(value)
            for value
            in values
            if value not in (
                None,
                "",
            )
        )

    return str(
        status
        or ""
    )


# ============================================================
# ORDENAR POR FECHA
# ============================================================

def _sort_timestamp(
    raw: dict[str, Any],
) -> float:

    timestamp = raw.get(
        "timestamp"
    )

    if isinstance(
        timestamp,
        (
            int,
            float,
        ),
    ):

        return float(
            timestamp
        )

    text = _start_time(
        raw
    )

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

        return 0.0


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def _normalized_text(
    value: str,
) -> str:

    plain = (
        unicodedata.normalize(
            "NFKD",
            value,
        )
        .encode(
            "ascii",
            "ignore",
        )
        .decode()
    )

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        plain.lower(),
    ).strip()


# ============================================================
# FLOAT SEGURO
# ============================================================

def _optional_float(
    value: Any,
) -> float | None:

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# FORMA VACIA
# ============================================================

def _empty_form() -> TeamForm:

    return TeamForm(
        games=0,
        wins=0,
        losses=0,
        ties=0,
        win_rate=0.5,
        average_for=0.0,
        average_against=0.0,
        average_margin=0.0,
    )


# ============================================================
# BLOQUE MLB HOME / AWAY
# ============================================================

def _matchup_side(
    matchup: dict[str, Any],
    side: str,
) -> dict[str, Any]:

    block = matchup.get(
        side
    )

    if isinstance(
        block,
        dict,
    ):

        return block

    return {}


# ============================================================
# TEXTO DEL ABRIDOR
# ============================================================

def _starter_text(
    block: dict[str, Any],
) -> str | None:

    pitcher = (
        block.get("pitcher")
        or block.get("starter")
        or block.get("probable_pitcher")
        or {}
    )

    if isinstance(
        pitcher,
        str,
    ):

        pitcher_name = pitcher

    elif isinstance(
        pitcher,
        dict,
    ):

        pitcher_name = str(
            pitcher.get("name")
            or pitcher.get("fullName")
            or pitcher.get("full_name")
            or ""
        ).strip()

    else:

        pitcher_name = ""


    stats = (
        block.get("pitcher_stats")
        or block.get("starter_stats")
        or {}
    )

    if not isinstance(
        stats,
        dict,
    ):

        stats = {}


    era = _optional_float(
        stats.get("era")
    )

    whip = _optional_float(
        stats.get("whip")
    )


    pieces: list[str] = []

    if pitcher_name:
        pieces.append(
            pitcher_name
        )

    if era is not None:

        pieces.append(
            f"ERA {era:.2f}"
        )

    if whip is not None:

        pieces.append(
            f"WHIP {whip:.2f}"
        )


    if not pieces:
        return None

    return " | ".join(
        pieces
    )


# ============================================================
# TEXTO BATEO VS PITCHER
# ============================================================

def _bvp_text(
    block: dict[str, Any],
) -> str | None:

    bvp = (
        block.get(
            "vs_opposing_pitcher"
        )
        or block.get(
            "bvp"
        )
        or {}
    )

    if not isinstance(
        bvp,
        dict,
    ):

        return None


    plate_appearances = (
        _optional_float(
            bvp.get("plate_appearances")
        )
        or _optional_float(
            bvp.get("pa")
        )
    )

    avg = _optional_float(
        bvp.get("avg")
    )

    obp = _optional_float(
        bvp.get("obp")
    )

    slg = _optional_float(
        bvp.get("slg")
    )

    ops = _optional_float(
        bvp.get("ops")
    )


    parts: list[str] = []


    if plate_appearances is not None:

        parts.append(
            f"PA {plate_appearances:.0f}"
        )

    if avg is not None:

        parts.append(
            f"AVG {avg:.3f}"
        )

    if obp is not None:

        parts.append(
            f"OBP {obp:.3f}"
        )

    if slg is not None:

        parts.append(
            f"SLG {slg:.3f}"
        )

    if ops is not None:

        parts.append(
            f"OPS {ops:.3f}"
        )


    if not parts:
        return None

    return " | ".join(
        parts
    )
