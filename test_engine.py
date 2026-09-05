from __future__ import annotations

import unittest

from sports_predictor.engine import (
    TeamForm,
    analyze_sport,
    calculate_team_form,
    classify_market,
    devig_two_way,
    normalize_games,
    parse_quotes,
    to_decimal_odds,
)


CONFIG = {
    "history_games": 12,
    "filters": {
        "minimum_probability": 0.55,
        "minimum_edge": 0.03,
        "minimum_expected_value": 0.03,
        "minimum_bookmakers": 2,
        "minimum_history_games": 5,
        "minimum_data_quality": 60,
    },
    "model": {
        "market_weight": 0.58,
        "form_weight": 0.42,
        "maximum_probability": 0.85,
    },
}


def upcoming_game() -> dict:
    return {
        "id": 10,
        "date": "2026-09-05T19:10:00+00:00",
        "status": {"short": "NS", "long": "Not Started"},
        "league": {"season": 2026},
        "teams": {
            "home": {"id": 1, "name": "Home Club"},
            "away": {"id": 2, "name": "Away Club"},
        },
        "scores": {"home": {"total": None}, "away": {"total": None}},
    }


def odds_payload(bookmaker: str, home: str, away: str) -> dict:
    return {
        "game": {"id": 10},
        "bookmakers": [
            {
                "name": bookmaker,
                "bets": [
                    {
                        "name": "Moneyline - Match Winner",
                        "values": [
                            {"value": "Home", "odd": home},
                            {"value": "Away", "odd": away},
                        ],
                    }
                ],
            }
        ],
    }


class EngineTests(unittest.TestCase):
    def test_devig_two_way_sums_to_one(self) -> None:
        home, away = devig_two_way(1.80, 2.10)
        self.assertAlmostEqual(home + away, 1.0)
        self.assertGreater(home, away)

    def test_american_and_decimal_odds(self) -> None:
        self.assertAlmostEqual(to_decimal_odds(-150) or 0, 1.666666, places=5)
        self.assertAlmostEqual(to_decimal_odds(150) or 0, 2.5)
        self.assertAlmostEqual(to_decimal_odds("1.91") or 0, 1.91)

    def test_first_five_market_detection(self) -> None:
        self.assertEqual(
            classify_market("MLB", "First 5 Innings - Winner"),
            "Primeras 5 entradas",
        )
        self.assertIsNone(classify_market("MLB", "First 5 Innings Total"))

    def test_team_form_uses_completed_games(self) -> None:
        history = []
        for index, (home_score, away_score) in enumerate(((5, 2), (3, 4), (6, 1))):
            history.append(
                {
                    "id": 100 + index,
                    "date": f"2026-08-{20 + index:02d}T19:00:00+00:00",
                    "status": {"short": "FT", "long": "Finished"},
                    "league": {"season": 2026},
                    "teams": {
                        "home": {"id": 1, "name": "Home Club"},
                        "away": {"id": 9 + index, "name": "Opponent"},
                    },
                    "scores": {
                        "home": {"total": home_score},
                        "away": {"total": away_score},
                    },
                }
            )
        form = calculate_team_form("MLB", 1, history, 12)
        self.assertEqual(form.games, 3)
        self.assertEqual(form.wins, 2)
        self.assertEqual(form.losses, 1)
        self.assertAlmostEqual(form.average_margin, 7 / 3)

    def test_best_pick_requires_all_filters(self) -> None:
        games = normalize_games("MLB", [upcoming_game()])
        quotes = parse_quotes(
            [
                odds_payload("Book A", "2.10", "1.80"),
                odds_payload("Book B", "2.05", "1.85"),
            ],
            games,
        )
        forms = {
            "1": TeamForm(12, 10, 2, 0, 10 / 12, 5.2, 2.2, 3.0),
            "2": TeamForm(12, 4, 8, 0, 4 / 12, 2.8, 4.8, -2.0),
        }
        recommendation, best, notes = analyze_sport(
            "MLB", games, quotes, forms, CONFIG
        )
        self.assertIsNotNone(recommendation)
        self.assertIsNotNone(best)
        self.assertEqual(recommendation.selection, "Home Club")
        self.assertTrue(recommendation.passes_filters)
        self.assertGreater(recommendation.expected_value, 0.03)
        self.assertEqual(notes, [])

    def test_one_bookmaker_produces_no_bet(self) -> None:
        games = normalize_games("NFL", [upcoming_game()])
        quotes = parse_quotes([odds_payload("Only Book", "2.10", "1.80")], games)
        forms = {
            "1": TeamForm(12, 10, 2, 0, 10 / 12, 28, 18, 10),
            "2": TeamForm(12, 3, 9, 0, 3 / 12, 17, 27, -10),
        }
        recommendation, best, notes = analyze_sport(
            "NFL", games, quotes, forms, CONFIG
        )
        self.assertIsNone(recommendation)
        self.assertIsNotNone(best)
        self.assertIn("Ninguna opción", " ".join(notes))


if __name__ == "__main__":
    unittest.main()

