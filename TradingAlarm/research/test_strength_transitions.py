import unittest
import pandas as pd
from strength_transition_audit import label_transitions

class TransitionTests(unittest.TestCase):
    def test_groups_do_not_leak_and_jumps_are_not_stepwise(self):
        t=pd.DataFrame(dict(model=['joint']*4,symbol=['A','A','B','B'],date=pd.to_datetime(['2026-01-01','2026-01-02']*2),strength=[1.,5.,9.,3.]))
        r=label_transitions(t)
        self.assertEqual(r.direction.tolist(),['unavailable','rising','unavailable','falling'])
        self.assertEqual(r.jump_two_points.tolist(),[False,True,False,True])
        self.assertEqual(r.previous_bin.iloc[-1],'8-10')
    def test_future_outcomes_do_not_change_labels(self):
        t=pd.DataFrame(dict(model=['joint']*3,symbol=['A']*3,date=pd.date_range('2026-01-01',periods=3),strength=[4.,8.,3.],forward5=[.1,-.1,.9]))
        a=label_transitions(t);t.forward5=-99
        b=label_transitions(t)
        pd.testing.assert_series_equal(a.direction,b.direction)
        pd.testing.assert_frame_equal(a.iloc[:2].drop(columns='forward5'),label_transitions(t.iloc[:2]).drop(columns='forward5'))

if __name__=='__main__':unittest.main()
