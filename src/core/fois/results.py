"""Production Results category scoring over observed historical outcomes."""
from __future__ import annotations

from dataclasses import replace
from statistics import mean

from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION
from src.core.fois.cycles import CompetitiveCycleAnalyzer, analysis_payload
from src.core.fois.facts import FOISFacts
from src.core.fois.models import (
    Directionality,
    FrontOfficeCategoryScore,
    FrontOfficeMetricScore,
    FrontOfficeScoringConfiguration,
    MetricStatus,
)
from src.core.fois.registry import registry_by_category
from src.core.fois.scoring import aggregate_metrics, clamp

RESULT_WEIGHTS = {
    "championships": 10,
    "championship_game_appearances": 7,
    "final_four_appearances": 7,
    "playoff_appearances": 8,
    "regular_season_winning_percentage": 9,
    "sustained_winning_seasons": 8,
    "average_finish": 6,
    "best_finish": 4,
    "worst_finish": 4,
    "championship_conversion_rate": 5,
    "playoff_advancement_rate": 5,
    "contention_window_length": 6,
    "reload_efficiency": 7,
    "rebuild_duration": 7,
    "long_term_competitive_consistency": 7,
}


class ResultsScorer:
    def __init__(
        self,
        configuration: FrontOfficeScoringConfiguration = DEFAULT_FOIS_CONFIGURATION,
    ) -> None:
        self.configuration = configuration
        self.definitions = registry_by_category()["results"]
        self.analyzer = CompetitiveCycleAnalyzer()

    def score(self, facts: FOISFacts) -> FrontOfficeCategoryScore:
        all_seasons = tuple(
            sorted(facts.completed_seasons, key=lambda row: row.season)
        )
        seasons = all_seasons[-10:]
        analysis = self.analyzer.analyze(
            all_seasons,
            ownership_changes=facts.ownership_changes,
            expected_seasons=facts.expected_seasons,
        )
        calculated = self._metrics(seasons, analysis, facts)
        metrics = tuple(
            calculated.get(definition.key, self._insufficient(definition))
            for definition in self.definitions
        )
        category = aggregate_metrics(
            "results",
            "Results",
            self.configuration.category_weights["results"],
            metrics,
            self.configuration,
        )
        explanation = self._explanation(category, analysis)
        return replace(
            category,
            explanation=explanation,
            strengths=analysis.strengths,
            weaknesses=analysis.weaknesses,
            details=analysis_payload(analysis),
        )

    def _metrics(
        self,
        seasons,
        analysis,
        facts: FOISFacts,
    ) -> dict[str, FrontOfficeMetricScore]:
        count = len(seasons)
        if not count:
            return {}
        confidence = self._confidence(
            seasons,
            count,
            facts.ownership_changes,
            facts.expected_seasons,
        )
        completeness = self._completeness(
            seasons,
            count,
            facts.expected_seasons,
        )
        titles = sum(row.championship for row in seasons)
        finals = sum(row.championship_game or row.championship for row in seasons)
        final_fours = sum(row.final_four or row.championship_game or row.championship for row in seasons)
        playoffs = sum(row.playoff or row.playoff_finish is not None for row in seasons)
        records = [
            (
                row.matchup_wins if row.matchup_wins is not None else row.wins,
                row.matchup_losses if row.matchup_losses is not None else row.losses,
            )
            for row in seasons
        ]
        wins = sum(row[0] or 0 for row in records)
        losses = sum(row[1] or 0 for row in records)
        games = wins + losses
        winning = [index for index, (won, lost) in enumerate(records) if (won or 0) > (lost or 0)]
        winning_streak = self._longest_streak(tuple(index in winning for index in range(count)))
        playoff_streak = self._longest_streak(
            tuple(row.playoff or row.playoff_finish is not None for row in seasons)
        )
        finish_scores = [
            self._finish_score(row.finish, row.league_size)
            for row in seasons
            if row.finish is not None and row.league_size
        ]
        bottom_finishes = sum(
            row.finish is not None
            and row.league_size is not None
            and row.finish > row.league_size * .75
            for row in seasons
        )
        contention = [
            cycle for cycle in analysis.competitive_cycles
            if cycle.cycle_type == "contention"
        ]
        rebuilds = [
            cycle.duration for cycle in analysis.competitive_cycles
            if cycle.cycle_type == "rebuild"
        ]
        reloads = [
            cycle.reload_time for cycle in contention
            if cycle.reload_time is not None
        ]
        relevant = sum(
            row.state in {"contender", "elite_contender", "ascending", "reload"}
            for row in analysis.timeline
        )
        metrics = {
            "championships": self._metric(
                "championships", titles, clamp(25 + titles * 25 if titles else 35),
                count, confidence, completeness,
                f"{titles} title(s) in {count} season(s); titles are capped at 10% of Results.",
            ),
            "championship_game_appearances": self._metric(
                "championship_game_appearances", finals,
                clamp(finals / count * 100 + min(finals, 3) * 8),
                count, confidence, completeness,
                f"{finals} championship-game appearance(s), converting {titles} into titles.",
            ),
            "final_four_appearances": self._metric(
                "final_four_appearances", final_fours,
                clamp(final_fours / count * 100), count, confidence, completeness,
                f"{final_fours} Final Four appearance(s) in {count} eligible season(s).",
            ),
            "playoff_appearances": self._metric(
                "playoff_appearances", playoffs,
                clamp(playoffs / count * 85 + min(playoff_streak, 5) * 3),
                count, confidence, completeness,
                f"{playoffs} playoff appearance(s); longest streak {playoff_streak}.",
            ),
            "regular_season_winning_percentage": self._metric(
                "regular_season_winning_percentage",
                round(wins / games, 4) if games else None,
                clamp(wins / games * 100) if games else None,
                games, confidence, completeness,
                f"{wins}-{losses} across observed regular-season matchups.",
            ),
            "sustained_winning_seasons": self._metric(
                "sustained_winning_seasons", len(winning),
                clamp(len(winning) / count * 85 + min(winning_streak, 5) * 3),
                count, confidence, completeness,
                f"{len(winning)} winning season(s); longest streak {winning_streak}.",
            ),
            "average_finish": self._metric(
                "average_finish",
                round(mean(row.finish for row in seasons if row.finish is not None), 2)
                if finish_scores else None,
                mean(finish_scores) if finish_scores else None,
                len(finish_scores), confidence, completeness,
                "Average regular-season finish normalized independently for each league size.",
                directionality=Directionality.LOWER_IS_BETTER,
            ),
            "best_finish": self._metric(
                "best_finish",
                min((row.finish for row in seasons if row.finish is not None), default=None),
                max(finish_scores) if finish_scores else None,
                len(finish_scores), confidence, completeness,
                "Best observed league-size-normalized regular-season finish.",
                directionality=Directionality.LOWER_IS_BETTER,
            ),
            "worst_finish": self._metric(
                "worst_finish",
                max((row.finish for row in seasons if row.finish is not None), default=None),
                clamp(90 - bottom_finishes * 15),
                len(finish_scores), confidence, completeness,
                f"{bottom_finishes} bottom-quartile finish(es); one isolated poor season has limited impact.",
                directionality=Directionality.LOWER_IS_BETTER,
            ),
            "championship_conversion_rate": self._metric(
                "championship_conversion_rate",
                round(titles / finals, 4) if finals else None,
                clamp(titles / finals * 100) if finals else None,
                finals, confidence, completeness,
                f"Won {titles} of {finals} championship-game appearance(s).",
            ),
            "playoff_advancement_rate": self._metric(
                "playoff_advancement_rate",
                round(final_fours / playoffs, 4) if playoffs else None,
                clamp(final_fours / playoffs * 100) if playoffs else None,
                playoffs, confidence, completeness,
                f"Advanced to the Final Four in {final_fours} of {playoffs} playoff appearances.",
            ),
            "contention_window_length": self._metric(
                "contention_window_length",
                max((cycle.duration for cycle in contention), default=0),
                clamp(max((cycle.duration for cycle in contention), default=0) / 5 * 100),
                count, confidence, completeness,
                f"Longest detected contention window: {max((cycle.duration for cycle in contention), default=0)} season(s).",
            ),
            "reload_efficiency": self._metric(
                "reload_efficiency",
                round(mean(reloads), 2) if reloads else None,
                clamp(100 - max(0, mean(reloads) - 1) * 20) if reloads else None,
                len(reloads), confidence, completeness,
                (
                    f"Average return to contention: {round(mean(reloads), 2)} season(s)."
                    if reloads else "No completed exit-and-return cycle is available."
                ),
                directionality=Directionality.LOWER_IS_BETTER,
            ),
            "rebuild_duration": self._metric(
                "rebuild_duration",
                round(mean(rebuilds), 2) if rebuilds else 0,
                self._rebuild_score(rebuilds), len(rebuilds) or count,
                confidence, completeness,
                (
                    f"Longest rebuild {max(rebuilds)} season(s); one or two seasons remain within the accepted productive-cycle threshold."
                    if rebuilds else "No rebuild cycle detected."
                ),
                directionality=Directionality.LOWER_IS_BETTER,
            ),
            "long_term_competitive_consistency": self._metric(
                "long_term_competitive_consistency", relevant,
                clamp(relevant / count * 100), count, confidence, completeness,
                f"Competitive or advancing in {relevant} of {count} evaluated season(s).",
            ),
        }
        return metrics

    def _metric(
        self,
        key: str,
        raw: float | int | None,
        score: float | None,
        sample: int,
        confidence: float,
        completeness: float,
        explanation: str,
        *,
        directionality: Directionality = Directionality.HIGHER_IS_BETTER,
    ) -> FrontOfficeMetricScore:
        definition = next(item for item in self.definitions if item.key == key)
        weight = RESULT_WEIGHTS[key]
        status = MetricStatus.ACTIVE if score is not None else MetricStatus.INSUFFICIENT_DATA
        return FrontOfficeMetricScore(
            key, definition.name, definition.description, raw, score, weight,
            round(score * weight / 100, 2) if score is not None else None,
            directionality, sample, confidence, completeness, explanation, (),
            () if score is not None else ("Insufficient observed outcomes.",),
            status,
        )

    def _insufficient(self, definition) -> FrontOfficeMetricScore:
        return FrontOfficeMetricScore(
            definition.key, definition.name, definition.description, None, None,
            RESULT_WEIGHTS[definition.key], None, definition.directionality, 0,
            0, 0, "Insufficient observed historical evidence.", (),
            ("Missing evidence reduces confidence, not score.",),
            MetricStatus.INSUFFICIENT_DATA,
        )

    def _confidence(
        self,
        seasons,
        count: int,
        ownership_changes: int,
        expected_seasons: int | None,
    ) -> float:
        complete = sum(row.complete for row in seasons)
        history_target = min(10, expected_seasons or 10)
        ownership_penalty = min(30, 12 * ownership_changes)
        return clamp(complete / history_target * 100 - ownership_penalty)

    @staticmethod
    def _completeness(
        seasons,
        count: int,
        expected_seasons: int | None,
    ) -> float:
        denominator = min(10, expected_seasons or count)
        return (
            clamp(sum(row.complete for row in seasons) / denominator * 100)
            if denominator else 0
        )

    @staticmethod
    def _finish_score(finish: int | None, size: int | None) -> float:
        if finish is None or not size:
            return 0
        if size <= 1:
            return 100
        return clamp((size - finish) / (size - 1) * 100)

    @staticmethod
    def _longest_streak(flags: tuple[bool, ...]) -> int:
        longest = current = 0
        for flag in flags:
            current = current + 1 if flag else 0
            longest = max(longest, current)
        return longest

    @staticmethod
    def _rebuild_score(rebuilds: list[int]) -> float:
        if not rebuilds:
            return 90
        longest = max(rebuilds)
        return 90 if longest <= 2 else clamp(90 - (longest - 2) * 20)

    @staticmethod
    def _explanation(category, analysis) -> str:
        strengths = " ".join(analysis.strengths) or "No supported strength yet."
        weaknesses = " ".join(analysis.weaknesses) or "No prolonged weakness detected."
        return (
            f"Results grade {category.letter_grade} ({category.normalized_score}/100). "
            f"Strengths: {strengths} Constraints: {weaknesses} "
            f"{analysis.explanation}"
        )
