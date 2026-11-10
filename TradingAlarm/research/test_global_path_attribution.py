import unittest
from global_dual_path_attribution import compare


def row(quantity,unit_pnl,entry='2020-01-01',exit='2020-02-01',symbol='X'):
    return dict(symbol=symbol,status='closed',entry=entry,exit=exit,quantity=quantity,
        unit_pnl=unit_pnl,pnl=quantity*unit_pnl,R=unit_pnl,holding_closes=10,max_close_R=0.,
        above_MA200=True,entry_exit_already_active=False,volume_vs_previous20=1.)


class AttributionTests(unittest.TestCase):
    def test_shifted_entry_still_matched_by_exit(self):
        r,new,old=compare([row(10,2)],[row(20,3,entry='2020-01-02')])
        self.assertEqual(r['total_delta'],40)
        self.assertEqual(r['matched_quantity_effect'],25)
        self.assertEqual(r['matched_per_unit_effect'],15)
        self.assertEqual(r['matched_entry_shifted'],1)
        self.assertFalse(new or old)

    def test_removed_loss_sign_is_positive_contribution(self):
        r,_,_=compare([row(10,-2,symbol='old')],[row(20,-1,symbol='new')])
        self.assertEqual(r['total_delta'],0)
        self.assertEqual(r['new_only']['pnl'],-20)
        self.assertEqual(r['base_only']['pnl'],-20)
        self.assertEqual(r['matched_episodes'],0)


if __name__=='__main__':unittest.main()
