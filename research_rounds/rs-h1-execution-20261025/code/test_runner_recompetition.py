"""End-to-end failed buy must compete at the very next close."""
import unittest
from dataclasses import replace
from test_history_runner import fixture
class Recompetition(unittest.TestCase):
 def test_unfilled_old_leader_loses_next_day_to_fresh_stronger_stock(self):
  r,b,m=fixture(count=3)
  b.lines=tuple(replace(x,sector_id='G0') for x in b.lines);b.sector_series={'G0':'G0'};m.lines={x.security_id:x for x in b.lines}
  ds,col,scores=b._h1_cache
  scores[:,col['S0']]=80;scores[:,col['S1']]=90;scores[:,col['S2']]=100
  scores[0,col['S0']]=100;scores[0,col['S2']]=80
  original=m.window
  def window(sid,when,side,mult):
   w=original(sid,when,side,mult)
   return replace(w,buy_allowed=False) if side=='buy' and when.date()==ds[1].date() else w
  m.window=window
  r.specs=tuple(s for s in r.specs if s.account_id=='T0_base');r.accounts={s.account_id:r.accounts[s.account_id] for s in r.specs};r.memory={'T0_base':()}
  r.run();a=r.accounts['T0_base']
  self.assertEqual({f.security_id for f in a.fills if f.side=='buy'},{'S1','S2'})
  self.assertFalse(a.quantity('S0'))
  self.assertEqual({f.at.date() for f in a.fills if f.side=='buy'},{ds[2].date()})
  expired=[x for x in a.audit_log if x['kind']=='buy_day_expiry'];self.assertEqual({x['sid'] for x in expired},{'S0','S1'})
  decisions=[x for x in r.decisions if x['at'].date()==ds[1].date()]
  self.assertEqual(decisions[0]['ack'].accepted,('S2','S1'))
if __name__=='__main__':unittest.main()
