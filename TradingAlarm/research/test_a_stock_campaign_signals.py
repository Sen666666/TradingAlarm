import unittest
import pandas as pd
from a_stock_campaign_signals import campaigns,volume_confirmation


class SignalCampaignTests(unittest.TestCase):
 def test_volume_confirmation_is_lagged_and_does_not_gate_exits(self):
  dates,f,o=self.data();confirm=pd.Series(False,index=dates);confirm.iloc[0]=True
  r=campaigns(f,o,'test',dates[-1],entry_confirmation=confirm)
  self.assertEqual(r[0]['entry_date'],str(dates[1].date()))
  self.assertEqual(r[0]['exit_date'],str(dates[3].date()))
  confirm[:]=False;confirm.iloc[1]=True
  r=campaigns(f,o,'test',dates[-1],entry_confirmation=confirm)
  self.assertEqual(r[0]['entry_date'],str(dates[2].date()))
 def test_volume_mean_requires20_prior_valid_observations(self):
  v=pd.Series([10.]*20+[11.,0.,10.,100.])
  c=volume_confirmation(v);self.assertFalse(c.iloc[:20].any());self.assertTrue(c.iloc[20]);self.assertFalse(c.iloc[21]);self.assertFalse(c.iloc[22]);self.assertTrue(c.iloc[23])
  vv=v.copy();vv.iloc[23]=1.;pd.testing.assert_series_equal(c.iloc[:23],volume_confirmation(vv).iloc[:23])
 def test_trailing_uses_held_prior_close_and_next_eligible_open(self):
  dates,f,o=self.data();f['signal_close']=[101.,110.,105.,104.,104.,104.];f['breakout55']=[100.,999.,999.,999.,999.,999.];o[:]=103.
  baseline=campaigns(f,o,'test',dates[-1]);self.assertEqual(baseline[0]['status'],'open_at_cutoff')
  r=campaigns(f,o,'test',dates[-1],trail_initial_risk=True)
  self.assertEqual(r[0]['exit_date'],str(dates[3].date()))
  mask=pd.Series(True,index=dates);mask.iloc[3]=False
  delayed=campaigns(f,o,'test',dates[-1],execution_mask=mask,trail_initial_risk=True)
  self.assertEqual(delayed[0]['exit_date'],str(dates[4].date()))
  g=f.copy();g.loc[3:,'signal_close']=1000.
  self.assertEqual(r[0],campaigns(g,o,'test',dates[-1],trail_initial_risk=True)[0])
 def test_blocked_exit_persists_but_observed_mark_is_not_removed(self):
  dates,f,o=self.data();mask=pd.Series(True,index=dates);mask.iloc[3]=False
  r=campaigns(f,o,'test',dates[-1],execution_mask=mask)
  self.assertEqual(r[0]['exit_date'],str(dates[4].date()))
  mask.iloc[3:]=False;r=campaigns(f,o,'test',dates[-1],execution_mask=mask)
  self.assertEqual(r[0]['status'],'open_at_cutoff');self.assertEqual(r[0]['exit_price'],100.)
 def test_blocked_entry_does_not_fill_after_signal_disappears(self):
  dates,f,o=self.data();mask=pd.Series(True,index=dates);mask.iloc[1:3]=False
  self.assertEqual(campaigns(f,o,'test',dates[-1],execution_mask=mask),[])
 def test_confirmation_uses_prior_close_and_can_enter_later(self):
  dates,f,o=self.data();f['sma200']=101.5
  a=campaigns(f,o,'test',dates[-1],confirm_ma=True)
  self.assertEqual(a[0]['entry_date'],str(dates[2].date()))
  self.assertEqual(a[0]['signal_date'],str(dates[1].date()))
  self.assertEqual(a[0]['entry_price'],102.)
 def data(self):
  dates=pd.bdate_range('2022-01-03',periods=6)
  f=pd.DataFrame(dict(date=dates,signal_close=[101.,102.,95.,100.,100.,100.],observed_bar=True,positive_volume=True,atr20=1.,breakout55=100.,sma200=90.,exit_signal=False))
  opens=pd.Series([100.,103.,102.,98.,99.,100.],index=dates)
  return dates,f,opens
 def test_next_open_and_pending_exit_during_missing_session(self):
  dates,f,o=self.data();f.loc[3,['observed_bar','positive_volume']]=False;o.iloc[3]=float('nan')
  r=campaigns(f,o,'test',dates[-1]);self.assertEqual(len(r),1)
  self.assertEqual(r[0]['entry_price'],103.);self.assertEqual(r[0]['entry_date'],str(dates[1].date()))
  self.assertEqual(r[0]['exit_date'],str(dates[4].date()));self.assertEqual(r[0]['exit_price'],99.)
 def test_terminal_mark_is_not_a_closed_trade(self):
  dates,f,o=self.data();f['signal_close']=102.;o[:]=102.
  r=campaigns(f,o,'test',dates[-1]+pd.Timedelta(days=10));self.assertEqual(r[0]['status'],'terminal_unknown');self.assertIsNone(r[0]['exit_date'])
 def test_future_prices_do_not_change_completed_trade(self):
  dates,f,o=self.data();a=campaigns(f,o,'test',dates[-1]);g=f.copy();g.loc[4:,'signal_close']=300.;oo=o.copy();oo.iloc[4:]=300.
  b=campaigns(g,oo,'test',dates[-1]);self.assertEqual(a[0],b[0])


if __name__=='__main__':unittest.main()
