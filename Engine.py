from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from mlb import (
    first_five_home_probability,
    full_game_home_probability,
    matchup_completeness,
    matchup_reason_lines,
)


# ============================================================
# UTILIDADES
# ============================================================

def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-.--"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def american_to_probability(odds: float | int | None) -> float | None:
    """
    Convierte cuota americana a probabilidad implícita.
    Ej:
        -150 -> 60%
        +150 -> 40%
    """

    if odds is None:
        return None

    odds = _float(odds)

    if odds == 0:
        return None

    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)

    return 100.0 / (odds + 100.0)


def decimal_to_probability(odds: float | None) -> float | None:
    if not odds or odds <= 1:
        return None

    return 1.0 / odds


def normalize_market_probabilities(
    home_probability: float | None,
    away_probability: float | None,
) -> tuple[float | None, float | None]:
    """
    Elimina aproximadamente el vig cuando tenemos ambos lados.
    """

    if home_probability is None or away_probability is None:
        return home_probability, away_probability

    total = home_probability + away_probability

    if total <= 0:
        return home_probability, away_probability

    return (
        home_probability / total,
        away_probability / total,
    )


def probability_to_percent(value: float | None) -> float | None:
    if value is None:
        return None

    return round(value * 100.0, 2)


def edge_percent(
    model_probability: float | None,
    market_probability: float | None,
) -> float | None:
    if model_probability is None or market_probability is None:
        return None

    return round(
        (model_probability - market_probability) * 100.0,
        2,
    )


# ============================================================
# RESULTADO DE UNA SELECCIÓN
# ============================================================

@dataclass
class PickCandidate:
    sport: str
    game_id: str
    market: str
    team: str
    opponent: str
    side: str

    model_probability: float
    market_probability: float | None

    edge_pct: float | None
    confidence: float

    score: float
    completeness: int

    reasons: tuple[str, ...]

    status: str = "CANDIDATA"

    def as_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "game_id": self.game_id,
            "market": self.market,
            "team": self.team,
            "opponent": self.opponent,
            "side": self.side,
            "model_probability": round(
                self.model_probability,
                6,
            ),
            "model_probability_pct": round(
                self.model_probability * 100.0,
                2,
            ),
            "market_probability": (
                round(self.market_probability, 6)
                if self.market_probability is not None
                else None
            ),
            "market_probability_pct": (
                round(self.market_probability * 100.0, 2)
                if self.market_probability is not None
                else None
            ),
            "edge_pct": self.edge_pct,
            "confidence": round(self.confidence, 2),
            "score": round(self.score, 2),
            "completeness": self.completeness,
            "reasons": list(self.reasons),
            "status": self.status,
        }


# ============================================================
# CALIDAD DE DATOS MLB
# ============================================================

def mlb_data_quality(
    matchup: dict[str, Any],
) -> dict[str, Any]:

    completeness = matchup_completeness(matchup)

    checks = completeness.get("checks", {})

    required = {
        "abridores",
        "ofensiva",
        "bullpen",
        "forma_reciente",
        "descanso",
    }

    missing_required = [
        key
        for key in required
        if not checks.get(key)
    ]

    optional_good = sum(
        1
        for key in (
            "splits_lr",
            "bullpen_reciente",
            "alineaciones",
            "bvp",
            "estadio",
            "clima",
        )
        if checks.get(key)
    )

    return {
        "score": int(
            completeness.get("score", 0)
        ),
        "checks": checks,
        "missing": completeness.get(
            "missing",
            [],
        ),
        "missing_required": missing_required,
        "required_ok": len(missing_required) == 0,
        "optional_good": optional_good,
    }


# ============================================================
# PROBABILIDAD DE MERCADO
# ============================================================

def get_market_probabilities(
    market: dict[str, Any] | None,
) -> tuple[float | None, float | None]:

    if not market:
        return None, None

    home_prob = None
    away_prob = None

    # --------------------------------------------------------
    # Ya vienen como probabilidades
    # --------------------------------------------------------

    if market.get("home_probability") is not None:
        home_prob = _float(
            market.get("home_probability")
        )

    if market.get("away_probability") is not None:
        away_prob = _float(
            market.get("away_probability")
        )

    # Permitir porcentaje 0-100
    if home_prob is not None and home_prob > 1:
        home_prob /= 100.0

    if away_prob is not None and away_prob > 1:
        away_prob /= 100.0

    # --------------------------------------------------------
    # Cuotas americanas
    # --------------------------------------------------------

    if home_prob is None:
        for key in (
            "home_odds",
            "home_moneyline",
            "home_ml",
        ):
            if market.get(key) is not None:
                home_prob = american_to_probability(
                    market.get(key)
                )
                break

    if away_prob is None:
        for key in (
            "away_odds",
            "away_moneyline",
            "away_ml",
        ):
            if market.get(key) is not None:
                away_prob = american_to_probability(
                    market.get(key)
                )
                break

    # --------------------------------------------------------
    # Cuotas decimales
    # --------------------------------------------------------

    if home_prob is None and market.get(
        "home_decimal"
    ):
        home_prob = decimal_to_probability(
            _float(
                market.get("home_decimal")
            )
        )

    if away_prob is None and market.get(
        "away_decimal"
    ):
        away_prob = decimal_to_probability(
            _float(
                market.get("away_decimal")
            )
        )

    return normalize_market_probabilities(
        home_prob,
        away_prob,
    )


# ============================================================
# AJUSTES POR CALIDAD DE DATOS
# ============================================================

def confidence_from_probability(
    probability: float,
    completeness: int,
    market_available: bool,
) -> float:

    distance = abs(probability - 0.50)

    probability_strength = _clamp(
        distance / 0.22,
        0.0,
        1.0,
    )

    completeness_strength = _clamp(
        completeness / 100.0,
        0.0,
        1.0,
    )

    market_bonus = 0.08 if market_available else 0.0

    confidence = (
        probability_strength * 52.0
        +
        completeness_strength * 40.0
        +
        market_bonus * 100.0
    )

    return _clamp(
        confidence,
        0.0,
        100.0,
    )


def candidate_score(
    model_probability: float,
    market_probability: float | None,
    completeness: int,
    market_type: str,
) -> float:
    """
    Puntaje utilizado para comparar TODAS las candidatas.

    No es probabilidad.
    Es ranking interno.
    """

    model_strength = (
        abs(
            model_probability - 0.50
        )
        * 200.0
    )

    if market_probability is not None:
        edge = (
            model_probability
            -
            market_probability
        ) * 100.0
    else:
        edge = 0.0

    quality = completeness * 0.32

    market_bonus = 0.0

    if market_type == "GANADOR_FINAL":
        market_bonus = 1.5

    return (
        model_strength * 0.50
        +
        max(-15.0, min(25.0, edge)) * 1.15
        +
        quality
        +
        market_bonus
    )


# ============================================================
# CREACIÓN DE CANDIDATAS MLB
# ============================================================

def build_mlb_candidates(
    game: dict[str, Any],
    matchup: dict[str, Any],
    market_full_game: dict[str, Any] | None = None,
    market_f5: dict[str, Any] | None = None,
) -> list[PickCandidate]:

    candidates: list[PickCandidate] = []

    home_name = str(
        game.get("home_team")
        or game.get("home")
        or matchup.get("home_name")
        or "Local"
    )

    away_name = str(
        game.get("away_team")
        or game.get("away")
        or matchup.get("away_name")
        or "Visitante"
    )

    game_id = str(
        game.get("game_id")
        or game.get("id")
        or matchup.get("game_pk")
        or f"{away_name}@{home_name}"
    )

    quality = mlb_data_quality(
        matchup
    )

    completeness = int(
        quality.get("score", 0)
    )

    base_reasons = matchup_reason_lines(
        matchup
    )

    # --------------------------------------------------------
    # GANADOR FINAL
    # --------------------------------------------------------

    full_home = full_game_home_probability(
        matchup
    )

    if full_home is not None:

        full_away = 1.0 - full_home

        market_home, market_away = (
            get_market_probabilities(
                market_full_game
            )
        )

        home_edge = edge_percent(
            full_home,
            market_home,
        )

        away_edge = edge_percent(
            full_away,
            market_away,
        )

        candidates.append(
            PickCandidate(
                sport="MLB",
                game_id=game_id,
                market="GANADOR_FINAL",
                team=home_name,
                opponent=away_name,
                side="HOME",
                model_probability=full_home,
                market_probability=market_home,
                edge_pct=home_edge,
                confidence=confidence_from_probability(
                    full_home,
                    completeness,
                    market_home is not None,
                ),
                score=candidate_score(
                    full_home,
                    market_home,
                    completeness,
                    "GANADOR_FINAL",
                ),
                completeness=completeness,
                reasons=base_reasons
                + (
                    f"Probabilidad modelo ganador final local: {full_home*100:.1f}%",
                ),
            )
        )

        candidates.append(
            PickCandidate(
                sport="MLB",
                game_id=game_id,
                market="GANADOR_FINAL",
                team=away_name,
                opponent=home_name,
                side="AWAY",
                model_probability=full_away,
                market_probability=market_away,
                edge_pct=away_edge,
                confidence=confidence_from_probability(
                    full_away,
                    completeness,
                    market_away is not None,
                ),
                score=candidate_score(
                    full_away,
                    market_away,
                    completeness,
                    "GANADOR_FINAL",
                ),
                completeness=completeness,
                reasons=base_reasons
                + (
                    f"Probabilidad modelo ganador final visitante: {full_away*100:.1f}%",
                ),
            )
        )

    # --------------------------------------------------------
    # F5
    # --------------------------------------------------------

    f5_home = first_five_home_probability(
        matchup
    )

    if f5_home is not None:

        f5_away = 1.0 - f5_home

        market_home, market_away = (
            get_market_probabilities(
                market_f5
            )
        )

        candidates.append(
            PickCandidate(
                sport="MLB",
                game_id=game_id,
                market="F5",
                team=home_name,
                opponent=away_name,
                side="HOME",
                model_probability=f5_home,
                market_probability=market_home,
                edge_pct=edge_percent(
                    f5_home,
                    market_home,
                ),
                confidence=confidence_from_probability(
                    f5_home,
                    completeness,
                    market_home is not None,
                ),
                score=candidate_score(
                    f5_home,
                    market_home,
                    completeness,
                    "F5",
                ),
                completeness=completeness,
                reasons=base_reasons
                + (
                    f"Probabilidad modelo F5 local: {f5_home*100:.1f}%",
                ),
            )
        )

        candidates.append(
            PickCandidate(
                sport="MLB",
                game_id=game_id,
                market="F5",
                team=away_name,
                opponent=home_name,
                side="AWAY",
                model_probability=f5_away,
                market_probability=market_away,
                edge_pct=edge_percent(
                    f5_away,
                    market_away,
                ),
                confidence=confidence_from_probability(
                    f5_away,
                    completeness,
                    market_away is not None,
                ),
                score=candidate_score(
                    f5_away,
                    market_away,
                    completeness,
                    "F5",
                ),
                completeness=completeness,
                reasons=base_reasons
                + (
                    f"Probabilidad modelo F5 visitante: {f5_away*100:.1f}%",
                ),
            )
        )

    return candidates


# ============================================================
# FILTROS DE APUESTA
# ============================================================

def candidate_is_eligible(
    candidate: PickCandidate,
    min_probability: float = 0.54,
    min_edge_pct: float = 1.5,
    min_completeness: int = 60,
    min_confidence: float = 55.0,
) -> tuple[bool, tuple[str, ...]]:

    reasons: list[str] = []

    if candidate.model_probability < min_probability:
        reasons.append(
            f"Probabilidad {candidate.model_probability*100:.1f}% "
            f"< mínimo {min_probability*100:.1f}%"
        )

    if candidate.completeness < min_completeness:
        reasons.append(
            f"Cobertura {candidate.completeness}% "
            f"< mínimo {min_completeness}%"
        )

    if candidate.confidence < min_confidence:
        reasons.append(
            f"Confianza {candidate.confidence:.1f}% "
            f"< mínimo {min_confidence:.1f}%"
        )

    if candidate.market_probability is not None:

        if (
            candidate.edge_pct is None
            or candidate.edge_pct < min_edge_pct
        ):
            reasons.append(
                f"Edge {candidate.edge_pct or 0:.2f}% "
                f"< mínimo {min_edge_pct:.2f}%"
            )

    return (
        len(reasons) == 0,
        tuple(reasons),
    )


# ============================================================
# ELEGIR MEJOR APUESTA MLB
# ============================================================

def choose_best_mlb_pick(
    game: dict[str, Any],
    matchup: dict[str, Any],
    market_full_game: dict[str, Any] | None = None,
    market_f5: dict[str, Any] | None = None,
    min_probability: float = 0.54,
    min_edge_pct: float = 1.5,
    min_completeness: int = 60,
    min_confidence: float = 55.0,
) -> dict[str, Any]:

    quality = mlb_data_quality(
        matchup
    )

    candidates = build_mlb_candidates(
        game=game,
        matchup=matchup,
        market_full_game=market_full_game,
        market_f5=market_f5,
    )

    evaluated: list[
        tuple[
            PickCandidate,
            bool,
            tuple[str, ...],
        ]
    ] = []

    for candidate in candidates:

        eligible, blocks = (
            candidate_is_eligible(
                candidate,
                min_probability=min_probability,
                min_edge_pct=min_edge_pct,
                min_completeness=min_completeness,
                min_confidence=min_confidence,
            )
        )

        evaluated.append(
            (
                candidate,
                eligible,
                blocks,
            )
        )

    eligible_candidates = [
        row[0]
        for row in evaluated
        if row[1]
    ]

    eligible_candidates.sort(
        key=lambda item: (
            item.score,
            item.model_probability,
            item.confidence,
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # NO APOSTAR
    # --------------------------------------------------------

    if not eligible_candidates:

        all_candidates = sorted(
            candidates,
            key=lambda item: item.score,
            reverse=True,
        )

        best_rejected = (
            all_candidates[0]
            if all_candidates
            else None
        )

        rejection_reasons: list[str] = []

        if best_rejected:

            for candidate, ok, blocks in evaluated:

                if candidate is best_rejected:

                    rejection_reasons.extend(
                        blocks
                    )

                    break

        if quality.get(
            "missing_required"
        ):

            rejection_reasons.append(
                "Faltan datos esenciales: "
                +
                ", ".join(
                    quality[
                        "missing_required"
                    ]
                )
            )

        return {
            "decision": "NO_APOSTAR",
            "sport": "MLB",
            "game_id": (
                str(
                    game.get("game_id")
                    or game.get("id")
                    or matchup.get("game_pk")
                    or ""
                )
            ),
            "reason": (
                "; ".join(
                    rejection_reasons
                )
                if rejection_reasons
                else
                "Ninguna candidata superó los filtros."
            ),
            "data_quality": quality,
            "best_rejected": (
                best_rejected.as_dict()
                if best_rejected
                else None
            ),
            "candidates": [
                c.as_dict()
                for c in candidates
            ],
        }

    # --------------------------------------------------------
    # MEJOR APUESTA
    # --------------------------------------------------------

    best = eligible_candidates[0]

    best.status = "MEJOR_APUESTA"

    return {
        "decision": "APOSTAR",
        "sport": "MLB",
        "game_id": best.game_id,
        "market": best.market,
        "team": best.team,
        "opponent": best.opponent,
        "side": best.side,
        "model_probability": best.model_probability,
        "model_probability_pct": round(
            best.model_probability * 100.0,
            2,
        ),
        "market_probability": best.market_probability,
        "market_probability_pct": (
            round(
                best.market_probability
                * 100.0,
                2,
            )
            if best.market_probability
            is not None
            else None
        ),
        "edge_pct": best.edge_pct,
        "confidence": round(
            best.confidence,
            2,
        ),
        "score": round(
            best.score,
            2,
        ),
        "data_quality": quality,
        "reasons": list(
            best.reasons
        ),
        "candidates": [
            c.as_dict()
            for c in sorted(
                candidates,
                key=lambda x: x.score,
                reverse=True,
            )
        ],
    }


# ============================================================
# COMPARAR TODOS LOS PARTIDOS MLB
# ============================================================

def choose_best_pick_from_all_games(
    game_results: list[dict[str, Any]],
) -> dict[str, Any]:

    valid = [
        result
        for result in game_results
        if result.get("decision")
        == "APOSTAR"
    ]

    if not valid:

        return {
            "decision": "NO_APOSTAR",
            "sport": "MLB",
            "reason": (
                "Ningún partido MLB superó todos los filtros."
            ),
            "games_analyzed": len(
                game_results
            ),
        }

    valid.sort(
        key=lambda result: (
            _float(
                result.get(
                    "score"
                )
            ),
            _float(
                result.get(
                    "model_probability"
                )
            ),
            _float(
                result.get(
                    "confidence"
                )
            ),
        ),
        reverse=True,
    )

    best = dict(
        valid[0]
    )

    best["decision"] = (
        "MEJOR_APUESTA_MLB"
    )

    best["games_analyzed"] = (
        len(game_results)
    )

    return best


# ============================================================
# COMPATIBILIDAD CON OTROS DEPORTES
# ============================================================

def generic_probability_pick(
    sport: str,
    game_id: str,
    home_team: str,
    away_team: str,
    home_probability: float,
    market_home_probability: float | None = None,
) -> dict[str, Any]:

    home_probability = _clamp(
        home_probability,
        0.01,
        0.99,
    )

    away_probability = (
        1.0
        -
        home_probability
    )

    if market_home_probability is not None:

        market_away_probability = (
            1.0
            -
            market_home_probability
        )

    else:

        market_away_probability = None

    if (
        home_probability
        >=
        away_probability
    ):

        team = home_team

        model_probability = (
            home_probability
        )

        market_probability = (
            market_home_probability
        )

        side = "HOME"

    else:

        team = away_team

        model_probability = (
            away_probability
        )

        market_probability = (
            market_away_probability
        )

        side = "AWAY"

    return {
        "decision": "APOSTAR",
        "sport": sport,
        "game_id": game_id,
        "market": "GANADOR_FINAL",
        "team": team,
        "side": side,
        "model_probability": model_probability,
        "model_probability_pct": round(
            model_probability
            * 100.0,
            2,
        ),
        "market_probability": market_probability,
        "edge_pct": edge_percent(
            model_probability,
            market_probability,
        ),
        }
