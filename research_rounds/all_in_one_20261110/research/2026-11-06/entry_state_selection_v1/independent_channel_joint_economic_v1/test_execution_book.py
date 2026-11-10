"""Synthetic-only execution tests. Importing this module performs no work."""
from dataclasses import replace, FrozenInstanceError
import unittest
from execution_book import Clock, EvidenceDomain, ExecutionBook, ExecutionRejected, OpenPermission, Receipt, Role

ROOT = ("SYNTHETIC.SZ", "SYNTHETIC_SOURCE", "2024-01-01")

def clock(day, sequence=100):
    return Clock(f"2024-01-{day:02d}", sequence)

def receipt(day=1):
    return Receipt(ROOT, clock(day).day, clock(day), clock(day + 1).day)

def permission(day=1, q=100, **kwargs):
    values = dict(receipt=receipt(day), decision_open=clock(day + 1).day,
                  known_at=clock(day + 1, 20), raw_open=10., protection_raw=8.,
                  feasible_qty=q, budget=24000., evidence_version="SYNTHETIC_CHECKS_V1",
                  checks_passed=True)
    values.update(kwargs)
    return OpenPermission(**values)

def book(proxy=False):
    return ExecutionBook(ROOT, EvidenceDomain.PROXY if proxy else EvidenceDomain.SYNTHETIC_TEST)

def fill(b, order, qty, day=2, seq=30, fill_id="fill1", fee=5.):
    return b.synthetic_fill(order.order_id, fill_id=fill_id, quantity=qty, price=10., fee=fee,
                            trade_day=clock(day).day, known_at=clock(day, seq))

def terminal(b, order, qty, day=2, seq=40):
    b.terminal_ack(order.order_id, cumulative_filled=qty, known_at=clock(day, seq))

def full_probe(b):
    o = b.open_target("PROBE", permission())
    fill(b, o, 100)
    terminal(b, o, 100)
    return o

def add_permission(day=2, q=100, **kwargs):
    return permission(day, q, confirmed=True, close_net_positive=True, open_net_positive=True, **kwargs)

class ExecutionTests(unittest.TestCase):
    def test_proxy_target_before_fill_and_explicit_domain(self):
        b = book(True)
        o = b.open_target("PROBE", permission())
        p = b.parent("PROBE")
        self.assertEqual((p.target_Q, p.filled_F), (100, 0))
        self.assertIsNone(p.complete_known_at)
        with self.assertRaises(FrozenInstanceError):
            p.target.target_Q = 200
        p = b.proxy_full_fill(o.order_id, fill_known_at=clock(2, 30), complete_known_at=clock(2, 40), price=10.005, fee=5)
        self.assertEqual((p.target_Q, p.filled_F, p.complete_known_at), (100, 100, clock(2, 40)))
        self.assertTrue(b.complete("PROBE"))
        names = [e["event"] for e in b.events]
        self.assertLess(names.index("proxy_target_registered"), names.index("proxy_fill"))
        self.assertNotIn("proxy_terminal_ack", names)
        self.assertEqual(b.responsibility()["actual_ack"], "NOT_PROVIDED")
        self.assertEqual(b.responsibility()["historical_tradability"], "UNKNOWN")

    def test_no_submit_q0_no_parent_no_order(self):
        b = book()
        self.assertIsNone(b.open_target("PROBE", permission(q=0)))
        self.assertFalse(b.parents)
        self.assertFalse(b.orders)
        self.assertFalse(b.responsibility()["owner_locked"])
        with self.assertRaises(ExecutionRejected):
            b.open_target("PROBE", permission())

    def test_no_submit_expires_instead_of_consuming(self):
        b = book()
        b.open_target("PROBE", permission(q=0))
        self.assertFalse(b._consumed)
        self.assertEqual(b._expired, {receipt().receipt_id})
        self.assertTrue(any(e["event"] == "synthetic_test_receipt_expired_no_submit" for e in b.events))
        self.assertFalse(any(e["event"] == "synthetic_test_receipt_consumed" for e in b.events))

    def test_cross_root_identifiers_and_latefill_cannot_alias(self):
        old = book()
        old_order = old.open_target("PROBE", permission())
        new_root = (ROOT[0], "DIFFERENT_SOURCE", ROOT[2])
        new = ExecutionBook(new_root, EvidenceDomain.SYNTHETIC_TEST)
        p = permission(receipt=replace(receipt(), root_id=new_root))
        new_order = new.open_target("PROBE", p)
        self.assertNotEqual(old_order.order_id, new_order.order_id)
        self.assertNotEqual(old_order.parent_id, new_order.parent_id)
        self.assertTrue(all(e["root_id"] == new_root for e in new.events))
        with self.assertRaises(ExecutionRejected):
            new.synthetic_fill(old_order.order_id, fill_id="old_fill", quantity=10, price=10, fee=5,
                               trade_day=clock(2).day, known_at=clock(2, 30))
        self.assertEqual(new.held_qty, 0)
        self.assertEqual(new.parent("PROBE").filled_F, 0)
        self.assertTrue(new.unknown)

    def test_open_at_below_S_no_parent(self):
        for op in (8., 7.):
            b = book()
            self.assertIsNone(b.open_target("PROBE", permission(raw_open=op)))
            self.assertFalse(b.parents)
            self.assertFalse(b.orders)

    def test_true_zero_fill_has_responsibility(self):
        b = book()
        o = b.open_target("PROBE", permission())
        terminal(b, o, 0)
        self.assertFalse(b.complete("PROBE"))
        self.assertEqual(b.remaining("PROBE"), 100)
        self.assertTrue(b.responsibility()["owner_locked"])
        self.assertEqual(b.parent("PROBE").unlock_known_at, clock(2, 40))

    def test_partial_immutable_Q_and_same_parent_remainder(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        terminal(b, o, 40)
        self.assertEqual(b.spent("PROBE"), 405.)
        second = b.submit_remaining("PROBE", permission(day=2, q=999))
        self.assertEqual(second.quantity, 60)
        self.assertEqual(second.parent_id, o.parent_id)
        self.assertEqual(b.parent("PROBE").target_Q, 100)
        fill(b, second, 60, day=3, fill_id="fill2")
        terminal(b, second, 60, day=3)
        self.assertTrue(b.complete("PROBE"))
        self.assertEqual(b.parent("PROBE").filled_F, 100)

    def test_cancel_pending_keeps_leaves_and_blocks(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        b.request_cancel(o.order_id, clock(2, 35))
        self.assertEqual(b.live_leaves(), 60)
        self.assertIsNone(b.parent("PROBE").unlock_known_at)
        with self.assertRaises(ExecutionRejected):
            b.submit_remaining("PROBE", permission(2))
        terminal(b, o, 40)
        self.assertEqual(b.live_leaves(), 0)

    def test_cancel_ack_requires_new_strictly_later_receipt(self):
        b = book()
        o = b.open_target("PROBE", permission())
        terminal(b, o, 0)
        stale = replace(receipt(2), known_at=clock(2, 40))
        with self.assertRaises(ExecutionRejected):
            b.submit_remaining("PROBE", permission(2, receipt=stale))
        self.assertEqual(b.submit_remaining("PROBE", permission(2)).quantity, 100)

    def test_duplicate_fill_idempotent_and_conflict_latches(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        fill(b, o, 40, seq=31)
        self.assertEqual(b.parent("PROBE").filled_F, 40)
        with self.assertRaises(ExecutionRejected):
            fill(b, o, 41, seq=32)
        self.assertTrue(b.unknown)
        self.assertEqual(b.parent("PROBE").filled_F, 40)

    def test_duplicate_terminal_ack_idempotent_conflict_unknown(self):
        b = book()
        o = b.open_target("PROBE", permission())
        terminal(b, o, 0)
        terminal(b, o, 0, seq=41)
        with self.assertRaises(ExecutionRejected):
            terminal(b, o, 1, seq=42)
        self.assertTrue(b.unknown)

    def test_terminal_ahead_of_fill_stays_pending_until_aligned(self):
        b = book()
        o = b.open_target("PROBE", permission())
        terminal(b, o, 40)
        self.assertFalse(b.responsibility()["all_orders_reconciled"])
        self.assertIsNone(b.parent("PROBE").unlock_known_at)
        fill(b, o, 40, seq=50)
        self.assertFalse(b.unknown)
        self.assertEqual(b.parent("PROBE").unlock_known_at, clock(2, 50))

    def test_latefill_after_unlock_updates_F_then_locks(self):
        b = book()
        o = b.open_target("PROBE", permission())
        terminal(b, o, 0)
        fill(b, o, 20, seq=50)
        self.assertEqual(b.parent("PROBE").filled_F, 20)
        self.assertEqual(b.held_qty, 20)
        self.assertTrue(b.unknown)
        self.assertIsNone(b.parent("PROBE").unlock_known_at)
        with self.assertRaises(ExecutionRejected):
            b.submit_remaining("PROBE", permission(2))

    def test_latefill_with_replacement_leaves_exceeds_Q(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        terminal(b, o, 40)
        b.submit_remaining("PROBE", permission(2))
        fill(b, o, 20, day=3, fill_id="late", seq=30)
        self.assertEqual(b.parent("PROBE").filled_F, 60)
        self.assertEqual(b.live_leaves(), 60)
        self.assertIn("parent F plus leaves exceeds fixed Q", b.unknown_reasons)

    def test_F_plus_live_leaves_locks_before_actual_overfill(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        b.synthetic_ack(o.order_id, leaves=70, known_at=clock(2, 35))
        self.assertTrue(b.unknown)
        self.assertLess(b.parent("PROBE").filled_F, b.parent("PROBE").target_Q)

    def test_actual_overfill_retained_and_unknown(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 101)
        self.assertEqual(b.parent("PROBE").filled_F, 101)
        self.assertEqual(b.held_qty, 101)
        self.assertTrue(b.unknown)

    def test_unknown_order_latches(self):
        b = book()
        with self.assertRaises(ExecutionRejected):
            b.synthetic_fill("missing", fill_id="a", quantity=1, price=1, fee=0,
                             trade_day=clock(2).day, known_at=clock(2, 30))
        self.assertTrue(b.unknown)

    def test_wrong_root_and_expired_receipt_rejected(self):
        b = book()
        wrong = replace(receipt(), root_id=("OTHER", "SOURCE", "2024-01-01"))
        with self.assertRaises(ExecutionRejected):
            b.open_target("PROBE", permission(receipt=wrong))
        with self.assertRaises(ExecutionRejected):
            b.open_target("PROBE", permission(decision_open=clock(3).day, known_at=clock(3, 20)))
        self.assertFalse(b.parents)

    def test_receipt_payload_conflict_unknown(self):
        b = book()
        b.open_target("PROBE", permission(q=0))
        changed = replace(receipt(), eligible_open=clock(3).day)
        with self.assertRaises(ExecutionRejected):
            b.open_target("PROBE", permission(receipt=changed, decision_open=clock(3).day, known_at=clock(3, 20)))
        self.assertTrue(b.unknown)

    def test_retired_root_and_parent_never_reused(self):
        b = book()
        o = b.open_target("PROBE", permission())
        terminal(b, o, 0)
        b.retire_root(clock(2, 100))
        self.assertFalse(b.responsibility()["owner_locked"])
        with self.assertRaises(ExecutionRejected):
            b.submit_remaining("PROBE", permission(2))
        with self.assertRaises(ExecutionRejected):
            b.open_target("PROBE", permission(2))
        self.assertEqual(b.parent("PROBE").target_Q, 100)

    def test_whole_remainder_cannot_shrink_target(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        terminal(b, o, 40)
        self.assertIsNone(b.submit_remaining("PROBE", permission(2, q=50)))
        self.assertEqual((b.parent("PROBE").target_Q, b.remaining("PROBE")), (100, 60))
        self.assertEqual(len(b.orders), 1)
        self.assertEqual(b.submit_remaining("PROBE", permission(3, q=60)).quantity, 60)

    def test_ADD_requires_complete_probe(self):
        for qty in (0, 40):
            b = book()
            o = b.open_target("PROBE", permission())
            if qty:
                fill(b, o, qty)
            terminal(b, o, qty)
            with self.assertRaises(ExecutionRejected):
                b.open_target("ADD", add_permission())
            self.assertNotIn(Role.ADD, b.parents)

    def test_ADD_same_ticket_or_equal_completion_forbidden(self):
        b = book()
        full_probe(b)
        with self.assertRaises(ExecutionRejected):
            b.open_target("ADD", permission())
        r = replace(receipt(2), known_at=clock(2, 40))
        with self.assertRaises(ExecutionRejected):
            b.open_target("ADD", add_permission(receipt=r))
        self.assertIsNotNone(b.open_target("ADD", add_permission()))

    def test_ADD_zero_fill_reuses_same_parent(self):
        b = book()
        full_probe(b)
        o = b.open_target("ADD", add_permission())
        terminal(b, o, 0, day=3)
        with self.assertRaises(ExecutionRejected):
            b.open_target("ADD", add_permission(3))
        again = b.submit_remaining("ADD", add_permission(3))
        self.assertEqual((again.parent_id, again.quantity), (o.parent_id, 100))
        self.assertEqual(len(b.parents), 2)

    def test_ADD_partial_reuses_Q_and_parent(self):
        b = book()
        full_probe(b)
        o = b.open_target("ADD", add_permission())
        fill(b, o, 30, day=3, fill_id="add1")
        terminal(b, o, 30, day=3)
        again = b.submit_remaining("ADD", add_permission(3, q=200))
        self.assertEqual(again.quantity, 70)
        self.assertEqual(b.parent("ADD").target_Q, 100)
        fill(b, again, 70, day=4, fill_id="add2")
        terminal(b, again, 70, day=4)
        self.assertTrue(b.complete("ADD"))
        self.assertEqual(b.held_qty, 200)

    def test_ADD_precheck_no_submit_does_not_spend_unique_parent(self):
        for update in (dict(feasible_qty=0), dict(raw_open=8), dict(confirmed=False),
                       dict(close_net_positive=False), dict(open_net_positive=False)):
            b = book()
            full_probe(b)
            self.assertIsNone(b.open_target("ADD", replace(add_permission(), **update)))
            self.assertNotIn(Role.ADD, b.parents)
            self.assertIsNotNone(b.open_target("ADD", add_permission(3)))

    def test_root_failure_keeps_cancel_and_exit_liability(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        b.retire_root(clock(2, 100))
        self.assertEqual((b.held_qty, b.live_leaves()), (40, 60))
        self.assertTrue(o.cancel_pending)
        self.assertTrue(b.exit_pending)
        self.assertTrue(b.responsibility()["owner_locked"])
        with self.assertRaises(ExecutionRejected):
            b.submit_exit(decision_open=clock(3).day, known_at=clock(3, 20))
        terminal(b, o, 40, day=3, seq=10)
        self.assertTrue(b.responsibility()["owner_locked"])
        sell = b.submit_exit(decision_open=clock(3).day, known_at=clock(3, 20))
        fill(b, sell, 40, day=3, fill_id="sell")
        self.assertTrue(b.responsibility()["owner_locked"])
        terminal(b, sell, 40, day=3)
        self.assertFalse(b.responsibility()["owner_locked"])
        self.assertEqual(b.parent("PROBE").filled_F, 40)
        self.assertEqual(b.held_qty, 0)

    def test_per_lot_T_plus_1_for_later_partial(self):
        b = book()
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        terminal(b, o, 40)
        again = b.submit_remaining("PROBE", permission(2))
        fill(b, again, 60, day=3, fill_id="later")
        terminal(b, again, 60, day=3)
        b.retire_root(clock(3, 50))
        self.assertEqual(b.sellable_qty(clock(3).day), 40)
        with self.assertRaises(ExecutionRejected):
            b.submit_exit(decision_open=clock(3).day, known_at=clock(3, 60))
        sell = b.submit_exit(decision_open=clock(3).day, known_at=clock(3, 60), quantity=40)
        fill(b, sell, 40, day=3, seq=70, fill_id="sell1")
        terminal(b, sell, 40, day=3, seq=80)
        self.assertEqual(b.held_qty, 60)
        self.assertTrue(b.exit_pending)
        next_sell = b.submit_exit(decision_open=clock(4).day, known_at=clock(4, 20))
        self.assertEqual(next_sell.quantity, 60)
        fill(b, next_sell, 60, day=4, fill_id="sell2")
        terminal(b, next_sell, 60, day=4)
        self.assertFalse(b.responsibility()["owner_locked"])

    def test_unknown_source_does_not_sell_release_or_restore(self):
        b = book()
        full_probe(b)
        b.freeze_unknown("source boundary 2026-05-18", clock(2, 50))
        b.retire_root(clock(2, 100))
        self.assertEqual(b.held_qty, 100)
        self.assertTrue(b.responsibility()["owner_locked"])
        with self.assertRaises(ExecutionRejected):
            b.submit_exit(decision_open=clock(3).day, known_at=clock(3, 20))
        self.assertTrue(b.unknown)

    def test_proxy_sell_reconciles_and_never_claims_actual_ACK(self):
        b = book(True)
        o = b.open_target("PROBE", permission())
        b.proxy_full_fill(o.order_id, fill_known_at=clock(2, 30), complete_known_at=clock(2, 40), price=10, fee=5)
        b.retire_root(clock(2, 100))
        sell = b.submit_exit(decision_open=clock(3).day, known_at=clock(3, 20))
        b.proxy_full_fill(sell.order_id, fill_known_at=clock(3, 30), complete_known_at=clock(3, 40), price=9, fee=5)
        self.assertEqual(b.held_qty, 0)
        self.assertFalse(b.responsibility()["owner_locked"])
        self.assertEqual(b.responsibility()["actual_fill"], "NOT_PROVIDED")

    def test_proxy_exit_all_convenience_and_inventory_alias(self):
        b = book(True)
        o = b.open_target("PROBE", permission())
        b.proxy_full_fill(o.order_id, fill_known_at=clock(2, 30), complete_known_at=clock(2, 40), price=10, fee=5)
        self.assertEqual(b.inventory, 100)
        self.assertEqual(b.parents["PROBE"].target_Q, 100)
        b.retire_root(clock(2, 100))
        qty = b.proxy_exit_all(trade_day=clock(3).day, submission_known_at=clock(3, 20),
                               fill_known_at=clock(3, 30), completion_known_at=clock(3, 40),
                               price=9, fee=5, reason="PRICE_FAILED")
        self.assertEqual((qty, b.inventory), (100, 0))
        self.assertFalse(b.responsibility()["owner_locked"])

    def test_import_is_inert_no_history_dependencies(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(__file__).with_name("execution_book.py").read_text())
        imports = {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
        imports.update(alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names)
        self.assertEqual(imports, {"__future__", "dataclasses", "datetime", "enum", "math", "typing"})
        self.assertTrue(all(isinstance(node, (ast.Expr, ast.Import, ast.ImportFrom, ast.Assign, ast.ClassDef)) for node in tree.body))
        for node in tree.body:
            if isinstance(node, ast.Expr):
                self.assertIsInstance(node.value, ast.Constant)
            if isinstance(node, ast.Assign):
                self.assertFalse(any(isinstance(child, ast.Call) for child in ast.walk(node)))

    def test_evidence_domain_cannot_be_real_or_mixed(self):
        with self.assertRaises(ValueError):
            ExecutionBook(ROOT, "REAL")
        b = book(True)
        o = b.open_target("PROBE", permission())
        with self.assertRaises(ExecutionRejected):
            fill(b, o, 100)
        b2 = book()
        o2 = b2.open_target("PROBE", permission())
        with self.assertRaises(ExecutionRejected):
            b2.proxy_full_fill(o2.order_id, fill_known_at=clock(2, 30), complete_known_at=clock(2, 40), price=10, fee=5)

    def test_proxy_completion_clock_strict(self):
        b = book(True)
        o = b.open_target("PROBE", permission())
        with self.assertRaises(ExecutionRejected):
            b.proxy_full_fill(o.order_id, fill_known_at=clock(2, 20), complete_known_at=clock(2, 40), price=10, fee=5)
        self.assertFalse(b.fills)

    def test_future_receipt_and_clock_reversal_rejected(self):
        b = book()
        r = replace(receipt(), known_at=clock(2, 20))
        with self.assertRaises(ExecutionRejected):
            b.open_target("PROBE", permission(receipt=r))
        o = b.open_target("PROBE", permission())
        fill(b, o, 40)
        with self.assertRaises(ExecutionRejected):
            b.synthetic_ack(o.order_id, leaves=60, known_at=clock(2, 25))

    def test_open_interface_ignores_daily_future_and_market_phase(self):
        outcomes = []
        for future in ({"high": 10, "low": 10, "close": 10, "amount": 0, "volume": 0,
                        "phase": "FAILED", "root_id": "NEW", "confirmed": False},
                       {"high": 99, "low": 1, "close": 80, "amount": 1e10, "volume": 1e9,
                        "phase": "CONFIRMED", "root_id": "OLD", "confirmed": True}):
            b = book(True)
            # No daily-future argument exists on the execution interface.
            self.assertNotEqual(future["high"], future["low"]) if future["high"] == 99 else None
            o = b.open_target("PROBE", permission())
            b.proxy_full_fill(o.order_id, fill_known_at=clock(2, 30), complete_known_at=clock(2, 40), price=10.005, fee=5)
            outcomes.append((b.parent("PROBE").target_Q, b.spent("PROBE"), b.events))
        self.assertEqual(outcomes[0], outcomes[1])

    def test_pending_parent_prevents_second_probe(self):
        b = book()
        b.open_target("PROBE", permission())
        with self.assertRaises(ExecutionRejected):
            b.open_target("PROBE", permission(2))
        self.assertTrue(b.responsibility()["owner_locked"])

    def test_retirement_zero_unacked_not_flat(self):
        b = book()
        o = b.open_target("PROBE", permission())
        b.retire_root(clock(2, 100))
        self.assertTrue(b.responsibility()["owner_locked"])
        terminal(b, o, 0, day=3, seq=10)
        self.assertFalse(b.responsibility()["owner_locked"])


def main():
    import argparse
    import hashlib
    import json
    from pathlib import Path
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa-dir", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    expected = "94965590a1d5ba5fd28e88a6cf6c09188f747663590d2ffa0e3f7858e2265687"
    protocol_hash = hashlib.sha256((root / "PROTOCOL_DRAFT.md").read_bytes()).hexdigest()
    if protocol_hash != expected:
        raise RuntimeError("protocol hash mismatch")
    output = Path(args.qa_dir).resolve()
    if output.parent != root:
        raise ValueError("QA must be a fresh direct child directory of implementation root")
    output.mkdir(exist_ok=False)
    class Result(unittest.TextTestResult):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.passed_names = []
        def addSuccess(self, test):
            super().addSuccess(test)
            self.passed_names.append(test.id())
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExecutionTests))
    qa = dict(result="PASS_SYNTHETIC_EXECUTION_ONLY" if result.wasSuccessful() else "FAIL",
              protocol_sha256=protocol_hash, tests_run=result.testsRun, passed=result.passed_names,
              failures=[(str(t), s) for t, s in result.failures], errors=[(str(t), s) for t, s in result.errors],
              source_sha256={name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                             for name in ("execution_book.py", "test_execution_book.py")},
              economic_runs=0, history_lifecycle_runs=0, broker_calls=0, real_ACKs=0,
              evidence_domains=["PROXY", "SYNTHETIC_TEST"],
              exclusions=["Caller market/sector/dated sizing/budget/risk/rights qualification not tested here",
                          "No historical returns or baseline regression",
                          "OPEN invariance here tests only pure execution interface; consumer integration needs its own perturbation tests"],
              interpreter=sys.executable)
    (output / "QA.json").write_text(json.dumps(qa, indent=2, ensure_ascii=False) + "\n")
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    raise SystemExit(main())
