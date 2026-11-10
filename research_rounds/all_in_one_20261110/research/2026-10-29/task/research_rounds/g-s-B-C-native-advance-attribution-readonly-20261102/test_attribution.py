"""Small timing/context counterexamples for attribution, not policy tests."""
import unittest,math
from analyze import scope_facts,clean
from datetime import date

class Tests(unittest.TestCase):
    def state(self,known,confirmed,context='now',source='same'):
        return dict(scopes={'S':dict(source='same',context='now',support=True,permit=True,mature=True)},
            proof_history=[dict(scope='S',source=source,context=context,kind='price_advance',known=known,confirmed=confirmed,seq=1,event_id='e')])
    def test_other_context_today_not_current_proof(self):
        t=date(2025,7,3).toordinal();r=scope_facts(self.state(t,t,context='old'),'S','2025-07-03')
        self.assertFalse(r['has_current_context_advance_today']);self.assertIsNotNone(r['last_historical_advance'])
    def test_future_known_and_other_source_excluded(self):
        t=date(2025,7,3).toordinal()
        self.assertFalse(scope_facts(self.state(t+1,t),'S','2025-07-03')['has_current_context_advance_today'])
        self.assertFalse(scope_facts(self.state(t,t,source='other'),'S','2025-07-03')['has_current_context_advance_today'])
    def test_old_event_arriving_today_not_new_native_progress(self):
        t=date(2025,7,3).toordinal();r=scope_facts(self.state(t,t-1),'S','2025-07-03')
        self.assertFalse(r['has_current_context_advance_today']);self.assertEqual(r['last_current_context_advance']['confirmed_date'],'2025-07-02')
    def test_unknown_export_is_not_zero_or_guessed_date(self):
        self.assertEqual(clean(dict(last=float('nan'))),dict(last=None))

if __name__=='__main__':unittest.main(verbosity=2)
