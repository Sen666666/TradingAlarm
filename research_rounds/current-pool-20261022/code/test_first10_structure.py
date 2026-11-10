"""Synthetic structural boundaries only: no history, signals, or accounts."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import run_first10 as entry


class FirstTenStructureTests(unittest.TestCase):
    def test_exact_matrix_and_common_initial_capital(self):
        specs = entry.first10_specs()
        expected = {f"{v}_{s}" for v in ("T0", "T1", "S0")
                    for s in ("base", "cost2", "delay1")} | {"B0_base"}
        self.assertEqual({s.account_id for s in specs}, expected)
        self.assertEqual(len(specs), 10)
        self.assertTrue(all(s.initial_capital_cny == 1_000_000 and s.currency == "CNY"
                            and not s.financing and not s.shorting for s in specs))

    def test_strategy_and_passive_allocators_are_distinct(self):
        specs = entry.first10_specs()
        for spec in specs[:-1]:
            self.assertIs(type(spec.allocation), entry.StrategyAllocation)
            self.assertEqual((spec.allocation.gross_fraction,
                              spec.allocation.initial_budget_divisor,
                              spec.allocation.max_issuers, spec.allocation.max_sectors,
                              spec.allocation.max_issuers_per_sector), (.9, 6, 6, 3, 2))
        self.assertIs(type(specs[-1].allocation), entry.PassiveAllocation)
        self.assertFalse(hasattr(specs[-1].allocation, "max_issuers"))

    def test_cost2_does_not_invent_fees_or_double_delay(self):
        stressed = [s for s in entry.first10_specs() if s.stress.name == "cost2"]
        self.assertEqual(len(stressed), 3)
        for spec in stressed:
            self.assertEqual(spec.stress.variable_components_multiplier, 2)
            self.assertEqual(spec.stress.extra_executable_events, 0)
            self.assertIn("variable_components_only", spec.stress.cost_scope)
            self.assertNotIn("cost_bps", asdict(spec.stress))

    def test_delay_counts_executable_events(self):
        for spec in entry.first10_specs():
            if spec.stress.name == "delay1":
                self.assertEqual(spec.stress.extra_executable_events, 1)
                self.assertEqual(spec.stress.variable_components_multiplier, 1)
                self.assertEqual(spec.stress.delay_clock,
                                 "eligible_executable_events_not_calendar_days")

    def test_b0_more_than_six_companies_no_strategy_capacity(self):
        lines = [entry.PassiveLine(f"S{i:02}", f"I{i:02}") for i in range(12)]
        plan = entry.annual_target_caps(1_000_000, lines)
        self.assertEqual(len(plan.targets), 12)
        self.assertTrue(all(t.budget_cap_cny == 75_000 for t in plan.targets))
        self.assertEqual(plan.target_total_cny, 900_000)
        self.assertEqual(plan.residual_cash_before_costs_cny, 100_000)
        self.assertFalse(any(hasattr(t, "shares") for t in plan.targets))

    def test_b0_issuer_dedup_is_stable_not_input_order(self):
        lines = [entry.PassiveLine("H0001", "AH"), entry.PassiveLine("A0001", "AH"),
                 entry.PassiveLine("B0002", "B")]
        plan = entry.annual_target_caps(1_000_000, lines)
        self.assertEqual(plan, entry.annual_target_caps(1_000_000, tuple(reversed(lines))))
        self.assertEqual([t.security_id for t in plan.targets], ["A0001", "B0002"])
        self.assertEqual(plan.duplicate_issuer_lines, ("H0001",))
        self.assertEqual([t.budget_cap_cny for t in plan.targets], [450_000, 450_000])

    def test_b0_empty_eligible_pool_retains_cash(self):
        plan = entry.annual_target_caps(1_000_000, [])
        self.assertEqual(plan.targets, ())
        self.assertEqual(plan.target_total_cny, 0)
        self.assertEqual(plan.residual_cash_before_costs_cny, 1_000_000)

    def test_b0_unknown_identity_and_duplicate_line_are_not_silently_removed(self):
        with self.assertRaises(ValueError):
            entry.PassiveLine("A", None)
        with self.assertRaises(ValueError):
            entry.annual_target_caps(1_000_000, [entry.PassiveLine("A", "I"),
                                               entry.PassiveLine("A", "I")])
        for nav in (True, 0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                entry.annual_target_caps(nav, [])

    def evidence_fixture(self, root):
        scope = root / "scope.json"
        scope.write_text(json.dumps({"algorithm_changes_allowed": 0,
                                     "account_runs_before_data_closeout": 0,
                                     "live_trading": False}))
        artifact = root / "synthetic-evidence.txt"
        artifact.write_text("synthetic-only; not economic authorization")
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        paths = []
        for kind, status in (("data_closeout", "closed"),
                             ("economic_protocol_frozen", "frozen")):
            path = root / f"{kind}.json"
            path.write_text(json.dumps(dict(kind=kind, status=status, round_id=entry.ROUND_ID,
                                             scope_sha256=sha(scope),
                                             recorded_at="2026-10-23T00:00:00+08:00",
                                             artifacts={artifact.name: sha(artifact)})))
            paths.append(path)
        return scope, artifact, paths

    def test_missing_closeout_or_protocol_cannot_validate(self):
        with tempfile.TemporaryDirectory() as d:
            scope, _, paths = self.evidence_fixture(Path(d))
            with self.assertRaisesRegex(ValueError, "data_closeout"):
                entry.validate(scope=scope)
            with self.assertRaisesRegex(ValueError, "economic_protocol_frozen"):
                entry.validate(scope=scope, data_closeout=paths[0])

    def test_explicit_evidence_still_never_executes_accounts(self):
        with tempfile.TemporaryDirectory() as d:
            scope, _, paths = self.evidence_fixture(Path(d))
            result = entry.validate(scope=scope, data_closeout=paths[0],
                                    economic_protocol_frozen=paths[1])
            self.assertTrue(result["account_execution_available"])
            self.assertEqual(result["economic_account_runs"], 0)
            self.assertEqual(len(result["evidence_checks"]), 2)
            self.assertTrue(callable(entry.run))

    def test_changed_or_missing_artifacts_fail_closed(self):
        for action in ("change", "remove"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as d:
                scope, artifact, paths = self.evidence_fixture(Path(d))
                artifact.write_text("changed") if action == "change" else artifact.unlink()
                with self.assertRaisesRegex(ValueError, "Missing or changed"):
                    entry.validate(scope=scope, data_closeout=paths[0],
                                   economic_protocol_frozen=paths[1])

    def test_changed_scope_cannot_reuse_old_declarations(self):
        with tempfile.TemporaryDirectory() as d:
            scope, _, paths = self.evidence_fixture(Path(d))
            scope.write_text(scope.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "current scope"):
                entry.validate(scope=scope, data_closeout=paths[0],
                               economic_protocol_frozen=paths[1])

    def test_describe_does_not_execute_and_run_requires_a_frozen_package(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(entry.main(["describe"]), 0)
        self.assertEqual(len(json.loads(output.getvalue())["accounts"]), 10)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            entry.main(["run"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
