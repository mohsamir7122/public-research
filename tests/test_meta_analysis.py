import math
from datetime import date
import unittest

from medical_research.meta_analysis import (
    EffectEstimate,
    PoolingApproval,
    combine_effects,
    estimate_tau_squared_paule_mandel,
)


TODAY = date.today().isoformat()


APPROVAL = PoolingApproval(
    artifact="analysis/pooling-decision.json",
    sha256="a" * 64,
    approved_by=("Dr Nora Hassan", "Prof Omar Khalil"),
    approved_on=TODAY,
    rationale="The population, comparison, outcome, time point, and estimand were reviewed as compatible.",
)


class MetaAnalysisTests(unittest.TestCase):
    def combine(self, estimates, **kwargs):
        options = {
            "effect_measure": "Mean difference",
            "analysis_scale": "identity",
            "pooling_approval": APPROVAL,
        }
        options.update(kwargs)
        return combine_effects(estimates, **options)

    def test_fixed_effect_calculation_is_reproducible(self):
        estimates = [
            EffectEstimate("A", 0.1, 0.1),
            EffectEstimate("B", 0.2, 0.1),
            EffectEstimate("C", 0.3, 0.1),
        ]
        result = self.combine(estimates, model="fixed")
        self.assertAlmostEqual(result.pooled_effect, 0.2)
        self.assertAlmostEqual(result.standard_error, math.sqrt(1 / 300))
        self.assertAlmostEqual(result.q, 2.0)
        self.assertEqual(result.tau_squared, 0.0)
        self.assertIsNone(result.prediction_interval)
        self.assertEqual(result.analysis_status, "calculation_check_not_release_analysis")

    def test_paule_mandel_detects_between_study_variance(self):
        estimates = [
            EffectEstimate("A", 0.0, 0.1),
            EffectEstimate("B", 1.0, 0.1),
            EffectEstimate("C", 2.0, 0.1),
        ]
        tau_squared = estimate_tau_squared_paule_mandel(estimates)
        self.assertGreater(tau_squared, 0)
        result = self.combine(estimates, model="random")
        self.assertAlmostEqual(result.pooled_effect, 1.0)
        self.assertIsNotNone(result.prediction_interval)
        self.assertGreater(result.i_squared_percent, 90)

    def test_paule_mandel_matches_independent_root_solver_reference(self):
        estimates = [
            EffectEstimate("S1", -0.42, 0.18),
            EffectEstimate("S2", 0.11, 0.22),
            EffectEstimate("S3", -0.05, 0.14),
            EffectEstimate("S4", 0.36, 0.25),
            EffectEstimate("S5", -0.20, 0.16),
        ]
        # Reference value independently solved with a bracketed root finder for Q(tau²)=k-1.
        self.assertAlmostEqual(
            estimate_tau_squared_paule_mandel(estimates),
            0.04265158086102777,
            places=12,
        )

    def test_boolean_or_missing_approval_is_never_sufficient(self):
        estimates = [EffectEstimate("A", 0.1, 0.1), EffectEstimate("B", 0.2, 0.1)]
        with self.assertRaisesRegex(ValueError, "traceable PoolingApproval"):
            combine_effects(
                estimates,
                effect_measure="Mean difference",
                analysis_scale="identity",
                pooling_approval=None,
            )

    def test_rejects_case_colliding_study_ids_and_invalid_standard_errors(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            self.combine(
                [EffectEstimate("Study-A", 0.1, 0.1), EffectEstimate("study-a", 0.2, 0.1)]
            )
        with self.assertRaisesRegex(ValueError, "positive"):
            self.combine(
                [EffectEstimate("A", 0.1, 0.0), EffectEstimate("B", 0.2, 0.1)]
            )

    def test_ratio_measures_require_log_scale_and_are_back_transformed(self):
        estimates = [
            EffectEstimate("A", math.log(0.8), 0.1),
            EffectEstimate("B", math.log(1.0), 0.1),
        ]
        with self.assertRaisesRegex(ValueError, "log scale"):
            self.combine(
                estimates,
                effect_measure="Risk ratio for graft failure",
                analysis_scale="identity",
            )
        with self.assertRaisesRegex(ValueError, "log scale"):
            self.combine(estimates, effect_measure="RR", analysis_scale="identity")
        result = self.combine(
            estimates,
            effect_measure="Risk ratio for graft failure",
            analysis_scale="log",
            model="fixed",
        )
        self.assertAlmostEqual(result.display_pooled_effect, math.sqrt(0.8))
        self.assertEqual(result.analysis_scale, "log")

    def test_ratio_scale_guard_normalizes_punctuation_and_common_aliases(self):
        estimates = [
            EffectEstimate("A", math.log(0.8), 0.1),
            EffectEstimate("B", math.log(1.0), 0.1),
        ]
        identity_scale_aliases = (
            "risk-ratio",
            "odds_ratio",
            "hazard–ratio",
            "relative-risk",
            "incidence-rate-ratio",
            "RR for graft failure",
            "adjusted OR",
            "HR—time to revision",
            "IRR/per person-year",
            "PR (prevalence ratio)",
        )
        for effect_measure in identity_scale_aliases:
            with self.subTest(effect_measure=effect_measure):
                with self.assertRaisesRegex(ValueError, "log scale"):
                    self.combine(
                        estimates,
                        effect_measure=effect_measure,
                        analysis_scale="identity",
                    )

    def test_approval_rejects_machine_or_future_approvers(self):
        estimates = [EffectEstimate("A", 0.1, 0.1), EffectEstimate("B", 0.2, 0.1)]
        machine = PoolingApproval(
            artifact="analysis/pooling-decision.json",
            sha256="a" * 64,
            approved_by=("Dr Nora Hassan", "ChatGPT AI bot"),
            approved_on=TODAY,
            rationale=APPROVAL.rationale,
        )
        with self.assertRaisesRegex(ValueError, "AI/tool"):
            self.combine(estimates, pooling_approval=machine)
        future = PoolingApproval(
            artifact="analysis/pooling-decision.json",
            sha256="a" * 64,
            approved_by=("Dr Nora Hassan", "Prof Omar Khalil"),
            approved_on="2999-01-01",
            rationale=APPROVAL.rationale,
        )
        with self.assertRaisesRegex(ValueError, "future"):
            self.combine(estimates, pooling_approval=future)

    def test_approval_fingerprint_is_deterministic(self):
        estimates = [EffectEstimate("A", 0.1, 0.1), EffectEstimate("B", 0.2, 0.1)]
        first = self.combine(estimates)
        second = self.combine(estimates)
        self.assertEqual(
            first.pooling_approval_fingerprint_sha256,
            second.pooling_approval_fingerprint_sha256,
        )
        self.assertEqual(len(first.pooling_approval_fingerprint_sha256), 64)

    def test_rejects_single_study(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            estimate_tau_squared_paule_mandel([EffectEstimate("A", 0.1, 0.1)])


if __name__ == "__main__":
    unittest.main()
