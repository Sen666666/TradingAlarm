"""Report-only schema regression on saved actual native records; no events."""
from pathlib import Path
import copy, json, pickle, unittest
from types import SimpleNamespace
import first_session_recovery as R
F,A,J,Q=R.F,R.A,R.J,R.Q

P=pickle.loads((F.ROOT/'full-input/checkpoint.pkl').read_bytes())
OLD=pickle.loads(F.PARENT.read_bytes())
AUDIT=P['accounts']['B']['audit_log']
FILL=next(x for x in AUDIT if x['kind']=='fill')

class Tests(unittest.TestCase):
    def test_outer_at(self):
        at=J.M.N.iso('2026-04-01T15:10:00+08:00')
        self.assertEqual(R.event_day(dict(kind='exit_request',at=at)),'2026-04-01')
    def test_actual_FillReceipt_at_and_canonical_equivalent(self):
        self.assertNotIn('at',FILL)
        self.assertEqual(type(FILL['receipt']).__name__,'FillReceipt')
        expected=str(FILL['receipt'].at)[:10]
        self.assertEqual(R.event_day(FILL),expected)
        self.assertEqual(R.event_day(J.W.canon(FILL)),expected)
    def test_unsupported_schema_rejected_no_recursive_timestamp_search(self):
        for row in [dict(kind='unknown',payload={'at':'2026-04-01'}),
                    dict(kind='unknown',receipt=J.W.canon(FILL['receipt'])),
                    dict(kind='fill',receipt={'at':'2026-04-01'})]:
            with self.assertRaisesRegex(AssertionError,'unsupported native record timestamp schema'):R.event_day(row)
    def test_all_April1_append_counts_same_saved_gate(self):
        r=SimpleNamespace(**P['runner']);r.accounts={'B':SimpleNamespace(**P['accounts']['B'])}
        proof=R.append_proof(r,OLD)
        self.assertEqual(proof,json.loads((F.ROOT/'FIRST_SESSION_GATE.json').read_text())['history_append_proof'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    F.save(F.ROOT/'EVENT_TIME_SCHEMA_GATE.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,
        original_audited_source=str(R.TIME.SOURCE),original_audited_source_sha256=R.TIME.SOURCE_SHA256,
        shared_helper_sha256=A.sha(R.TIME.__file__),report_adapter_sha256=A.sha(R.__file__),
        classes=['outer at','actual FillReceipt.at','unsupported schema rejects'],
        actual_saved_April1_append_counts_exact=True,new_account_events=0))
    raise SystemExit(not result.wasSuccessful())
