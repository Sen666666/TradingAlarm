from e0_amount import *
import unittest,json
from decimal import Decimal

def bars():
 n=160;dates=pd.bdate_range('2024-01-01',periods=n);close=100*np.exp(.035*np.sin(np.arange(n)/4))
 return pd.DataFrame(dict(open=close,high=close+1,low=close-1,close=close,volume=1e6*(1+.3*np.cos(np.arange(n)/3)),amount=1e8*(1+.4*np.sin(np.arange(n)/5))),index=dates)

class Contract(unittest.TestCase):
 def test_share_control_reuses_exact_original(self):
  b=bars();z=run(b,'shares');x=activity_input(b,'shares');e=event_frame_numeric(x.close,x.volume);s,_=participation_frame(x,e);pd.testing.assert_series_equal(z['state'].target,s.target)
 def test_amount_ignores_share_column(self):
  b=bars();a=run(b);b['volume']*=100;z=run(b);pd.testing.assert_frame_equal(a['state'],z['state'])
 def test_amount_unit_scaling_cancels(self):
  b=bars();a=run(b);b.amount*=1000;z=run(b);pd.testing.assert_series_equal(a['state'].target,z['state'].target);np.testing.assert_allclose(a['state'].activity_ratio,z['state'].activity_ratio,equal_nan=True)
 def test_missing_amount_cannot_fall_back(self):
  b=bars();b.loc[b.index[-1],'amount']=np.nan
  with self.assertRaises(ValueError):run(b)
 def test_reclaim_memory_is_not_down_day_entry(self):
  dates=pd.bdate_range('2024-01-01',periods=25);b=pd.DataFrame(dict(open=10.,high=10.2,low=9.8,close=10.,volume=100.,amount=1000.),index=dates)
  b.loc[dates[22],['close','low','amount']]=[9.5,9.2,2500];b.loc[dates[23],['close','low']]=[9.8,9.7];b.loc[dates[24],['close','high','low']]=[10.1,10.2,10.0]
  # Isolate this policy branch from the ordinary swing-confirmation channel.
  x=activity_input(b);e=pd.DataFrame(dict(event=0.,leg_direction=-1.,confirmed_pivot_price=np.nan),index=dates);s,m=participation_frame(x,e)
  self.assertEqual(s.loc[dates[22],'created'],1);self.assertEqual(s.loc[dates[22],'target'],0);self.assertEqual(s.loc[dates[23],'target'],0);self.assertEqual(s.loc[dates[24],'independent_entry'],1);self.assertEqual(s.loc[dates[24],'floor'],9.2);self.assertLess(s.loc[dates[24],'volume_ratio'],2)

if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contract))
 if not r.wasSuccessful():sys.exit(1)
 p=Path(__file__).resolve().parents[1]/'technical.json';assert not p.exists();p.write_text(json.dumps(dict(passed=True,tests=r.testsRun,real_history_replays=0,financial_accounts=0,prototype_not_promoted=True),indent=2)+'\n')
