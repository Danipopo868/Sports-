def analyze_sport(
    sport: str,
    games: list[Game],
    quotes: list[Quote],
    forms: dict[str, TeamForm],
    config: dict[str, Any],
    mlb_matchups: dict[str, dict[str, Any]] | None = None,
) -> tuple[Candidate | None, Candidate | None, list[str]]:
    filters = config["filters"]
    model = config["model"]
    all_candidates: list[Candidate] = []
    notes: list[str] = []

    # ============================================================
    # ANALISIS NORMAL DE MERCADOS
    # ============================================================

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

        for market_name in sorted(
            {quote.market for quote in game_quotes}
        ):
            market_quotes = [
                quote
                for quote in game_quotes
                if quote.market == market_name
            ]

            book_pairs = _bookmaker_pairs(
                market_quotes
            )

            if not book_pairs:
                continue

            market_home_probability = sum(
                devig_two_way(
                    pair["home"].decimal_odds,
                    pair["away"].decimal_odds,
                )[0]
                for pair in book_pairs.values()
            ) / len(book_pairs)

            # ====================================================
            # PRIMERAS 5 ENTRADAS
            # ====================================================

            if market_name == "Primeras 5 entradas":
                matchup = (
                    mlb_matchups or {}
                ).get(
                    str(game.id),
                    {},
                )

                form_home_probability = (
                    first_five_home_probability(
                        matchup
                    )
                )

                if form_home_probability is None:
                    notes.append(
                        f"{game.away.name} @ {game.home.name}: "
                        "F5 omitido porque no están confirmados "
                        "ambos abridores o faltan estadísticas."
                    )
                    continue

                pitcher_complete = True

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
                    int(config["history_games"]),
                )
            )

            combined_home_probability = (
                combine_probabilities(
                    market_home_probability,
                    form_home_probability,
                    float(model["market_weight"]),
                    float(model["form_weight"]),
                    sample_factor,
                    float(model["maximum_probability"]),
                )
            )

            quality = data_quality(
                home_form,
                away_form,
                len(book_pairs),
                int(config["history_games"]),
                pitcher_complete,
            )

            base_reason_lines = (
                f"Forma {game.home.name}: "
                f"{home_form.wins}-{home_form.losses}; "
                f"{game.away.name}: "
                f"{away_form.wins}-{away_form.losses}",

                f"Consenso sin margen de "
                f"{len(book_pairs)} casa(s)",
            )

            for side in ("home", "away"):
                best = max(
                    (
                        quote
                        for quote in market_quotes
                        if quote.side == side
                    ),
                    key=lambda quote: quote.decimal_odds,
                    default=None,
                )

                if not best:
                    continue

                probability = (
                    combined_home_probability
                    if side == "home"
                    else 1.0 - combined_home_probability
                )

                break_even = (
                    1.0 / best.decimal_odds
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

                minimum_history = int(
                    filters[
                        "minimum_history_games"
                    ]
                )

                history_games = min(
                    home_form.games,
                    away_form.games,
                )

                history_ok = (
                    history_games
                    >= minimum_history
                )

                probability_ok = (
                    probability
                    >= float(
                        filters[
                            "minimum_probability"
                        ]
                    )
                )

                edge_ok = (
                    edge
                    >= float(
                        filters[
                            "minimum_edge"
                        ]
                    )
                )

                expected_value_ok = (
                    expected_value
                    >= float(
                        filters[
                            "minimum_expected_value"
                        ]
                    )
                )

                bookmakers_ok = (
                    len(book_pairs)
                    >= int(
                        filters[
                            "minimum_bookmakers"
                        ]
                    )
                )

                quality_ok = (
                    quality
                    >= int(
                        filters[
                            "minimum_data_quality"
                        ]
                    )
                )

                passes = all(
                    (
                        probability_ok,
                        edge_ok,
                        expected_value_ok,
                        bookmakers_ok,
                        quality_ok,
                        history_ok,
                    )
                )

                selection = (
                    game.home.name
                    if side == "home"
                    else game.away.name
                )

                filter_reasons: list[str] = []

                if not probability_ok:
                    filter_reasons.append(
                        "FALLA probabilidad: "
                        f"{probability * 100:.1f}% "
                        f"< mínimo "
                        f"{float(filters['minimum_probability']) * 100:.1f}%"
                    )

                if not edge_ok:
                    filter_reasons.append(
                        "FALLA edge: "
                        f"{edge * 100:.1f}% "
                        f"< mínimo "
                        f"{float(filters['minimum_edge']) * 100:.1f}%"
                    )

                if not expected_value_ok:
                    filter_reasons.append(
                        "FALLA valor esperado: "
                        f"{expected_value * 100:.1f}% "
                        f"< mínimo "
                        f"{float(filters['minimum_expected_value']) * 100:.1f}%"
                    )

                if not bookmakers_ok:
                    filter_reasons.append(
                        "FALLA casas: "
                        f"{len(book_pairs)} "
                        f"< mínimo "
                        f"{int(filters['minimum_bookmakers'])}"
                    )

                if not quality_ok:
                    filter_reasons.append(
                        "FALLA calidad de datos: "
                        f"{quality} "
                        f"< mínimo "
                        f"{int(filters['minimum_data_quality'])}"
                    )

                if not history_ok:
                    filter_reasons.append(
                        "FALLA historial: "
                        f"{history_games} partidos "
                        f"< mínimo "
                        f"{minimum_history}"
                    )

                if passes:
                    filter_reasons.append(
                        "PASÓ TODOS LOS FILTROS"
                    )

                reason_lines = (
                    base_reason_lines
                    + tuple(filter_reasons)
                )

                all_candidates.append(
                    Candidate(
                        sport=sport,
                        game_id=str(game.id),
                        matchup=(
                            f"{game.away.name} "
                            f"@ {game.home.name}"
                        ),
                        start=game.start,
                        market=market_name,
                        selection=selection,
                        bookmaker=best.bookmaker,
                        decimal_odds=best.decimal_odds,
                        model_probability=probability,
                        break_even_probability=break_even,
                        edge=edge,
                        expected_value=expected_value,
                        bookmakers=len(book_pairs),
                        data_quality=quality,
                        passes_filters=passes,
                        reasons=reason_lines,
                    )
                )

    # ============================================================
    # MLB - TOP 3 GANADORES DEL JUEGO COMPLETO
    # ============================================================

    if sport == "MLB" and mlb_matchups:
        mlb_predictions: list[
            tuple[
                float,
                Game,
                str,
                dict[str, Any],
            ]
        ] = []

        for game in games:
            matchup = (
                mlb_matchups
                .get(
                    str(game.id),
                    {},
                )
            )

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

            mlb_predictions.append(
                (
                    winner_probability,
                    game,
                    predicted_winner,
                    matchup,
                )
            )

        mlb_predictions.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        if mlb_predictions:
            notes.append(
                "========== MLB TOP 3 GANADORES =========="
            )

            for rank, (
                winner_probability,
                game,
                predicted_winner,
                matchup,
            ) in enumerate(
                mlb_predictions[:3],
                start=1,
            ):
                notes.append(
                    f"#{rank} "
                    f"{game.away.name} @ "
                    f"{game.home.name}"
                )

                notes.append(
                    f"GANADOR PREDICHO: "
                    f"{predicted_winner}"
                )

                notes.append(
                    f"Probabilidad estimada: "
                    f"{winner_probability * 100:.1f}%"
                )

                home_pitcher = (
                    matchup
                    .get("home", {})
                    .get("pitcher", {})
                )

                away_pitcher = (
                    matchup
                    .get("away", {})
                    .get("pitcher", {})
                )

                if home_pitcher:
                    notes.append(
                        f"Abridor {game.home.name}: "
                        f"{home_pitcher.get('name', 'N/D')} | "
                        f"ERA "
                        f"{home_pitcher.get('era', 'N/D')} | "
                        f"WHIP "
                        f"{home_pitcher.get('whip', 'N/D')}"
                    )

                if away_pitcher:
                    notes.append(
                        f"Abridor {game.away.name}: "
                        f"{away_pitcher.get('name', 'N/D')} | "
                        f"ERA "
                        f"{away_pitcher.get('era', 'N/D')} | "
                        f"WHIP "
                        f"{away_pitcher.get('whip', 'N/D')}"
                    )

                home_bvp = (
                    matchup
                    .get("home", {})
                    .get(
                        "vs_opposing_pitcher",
                        {},
                    )
                )

                away_bvp = (
                    matchup
                    .get("away", {})
                    .get(
                        "vs_opposing_pitcher",
                        {},
                    )
                )

                if home_bvp:
                    notes.append(
                        f"{game.home.name} vs abridor rival: "
                        f"OPS "
                        f"{home_bvp.get('ops', 'N/D')} | "
                        f"PA "
                        f"{home_bvp.get('plate_appearances', 'N/D')}"
                    )

                if away_bvp:
                    notes.append(
                        f"{game.away.name} vs abridor rival: "
                        f"OPS "
                        f"{away_bvp.get('ops', 'N/D')} | "
                        f"PA "
                        f"{away_bvp.get('plate_appearances', 'N/D')}"
                    )

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
                        f"F5 PREDICHO: "
                        f"{f5_winner} | "
                        f"{f5_probability * 100:.1f}%"
                    )

                notes.append(
                    "----------------------------------------"
                )

        else:
            notes.append(
                "MLB: no se pudo calcular el Top 3 "
                "porque faltan datos de los enfrentamientos."
            )

    # ============================================================
    # MEJOR OPCION OBSERVADA
    # ============================================================

    best_observed = max(
        all_candidates,
        key=lambda candidate: (
            candidate.expected_value,
            candidate.edge,
        ),
        default=None,
    )

    eligible = [
        candidate
        for candidate in all_candidates
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

    # ============================================================
    # NOTAS FINALES
    # ============================================================

    if not games:
        notes.append(
            "No hay partidos disponibles para la fecha analizada."
        )

    elif not quotes:
        notes.append(
            "No llegaron cuotas comparables; "
            "sin precio no se puede calcular rentabilidad."
        )

    elif not all_candidates:
        notes.append(
            "Llegaron cuotas, pero no se pudieron formar "
            "mercados comparables con ambos lados."
        )

    elif not recommendation:
        notes.append(
            "Ninguna opción superó simultáneamente "
            "todos los filtros de valor y calidad."
        )

        if best_observed:
            notes.append(
                f"MEJOR OPCIÓN: "
                f"{best_observed.selection} | "
                f"{best_observed.matchup} | "
                f"{best_observed.market}"
            )

            notes.append(
                f"Probabilidad: "
                f"{best_observed.model_probability * 100:.1f}%"
            )

            notes.append(
                f"Cuota decimal: "
                f"{best_observed.decimal_odds:.2f}"
            )

            notes.append(
                f"Edge: "
                f"{best_observed.edge * 100:.1f}%"
            )

            notes.append(
                f"Valor esperado: "
                f"{best_observed.expected_value * 100:.1f}%"
            )

            notes.append(
                f"Bookmakers comparables: "
                f"{best_observed.bookmakers}"
            )

            notes.append(
                f"Calidad de datos: "
                f"{best_observed.data_quality}/100"
            )

            for reason in best_observed.reasons:
                if reason.startswith("FALLA"):
                    notes.append(reason)

    return recommendation, best_observed, notes
