from common import *
import model,unittest,io
def fixture(tail=None,n=150):
 r=np.resize(np.array([.011,-.009,.006,-.008]),n)
 close=100*np.exp(np.cumsum(r))
 if tail is not None:close=np.r_[close,tail]
 return pd.DataFrame(dict(close=close,amount=1e8,segment_id=0,e0_valid=True,e0_down=False,i_floor=70.),index=pd.bdate_range('2020-01-01',periods=len(close)))
class Tests(unittest.TestCase):
 def test_empty_prelisting_prefix(self):
  f=fixture();a=model.calculate(f.iloc[:0]);b=model.calculate(f).iloc[:0];pd.testing.assert_frame_equal(a,b,check_exact=True)
 def test_prepare(self):
  z=model.calculate(fixture());self.assertFalse(z.ready.iloc[:64].any());self.assertTrue(z.ready.iloc[64:].all())
 def test_continuous_up_without_pivots(self):
  f=fixture(np.linspace(130,250,80));z=model.calculate(f);q=z.iloc[150:];self.assertGreater(q.receipt.sum(),5);self.assertFalse(f.e0_down.any());self.assertGreater(q.loc[q.receipt,'candidate'].iloc[-1],q.loc[q.receipt,'candidate'].iloc[0])
 def test_flat_does_not_create(self):
  f=fixture(np.repeat(200.,90));z=model.calculate(f);self.assertFalse(z.receipt.iloc[151:].any());self.assertTrue((z.delta_frontier.iloc[151:]==0).all())
 def test_volume_flat_does_not_create(self):
  f=fixture(np.repeat(200.,90));f.loc[f.index[151:],'amount']=1e15;z=model.calculate(f);self.assertFalse(z.receipt.iloc[151:].any())
 def test_same_range_no_repeated_credit(self):
  f=fixture(np.r_[200.,np.resize([185.,195.,200.],90)]);z=model.calculate(f);self.assertFalse(z.receipt.iloc[151:].any())
 def test_low_amount_positive_credit(self):
  f=fixture(np.linspace(130,170,20));f.loc[f.index[150:],'amount']=1e6;z=model.calculate(f);self.assertTrue(z.m.iloc[150:].gt(.5).all());self.assertTrue(z.receipt.iloc[150:].any())
 def test_amount_changes_features(self):
  f=fixture(np.linspace(130,170,20));f.loc[f.index[150:],'amount']=1e10;hi=model.calculate(f);f.loc[f.index[150:],'amount']=1e6;lo=model.calculate(f);self.assertGreater(hi.m.iloc[150],lo.m.iloc[150]);self.assertFalse(hi[['m']].equals(lo[['m']]))
 def test_price_control_features_are_same(self):
  f=fixture();a=model.calculate(f);b=model.calculate(f,True);pd.testing.assert_frame_equal(a[['s','u','v','m']],b[['s','u','v','m']])
 def test_source_reprepare(self):
  f=fixture(n=200);f.loc[f.index[100:],'segment_id']=1;z=model.calculate(f);self.assertFalse(z.ready.iloc[100:164].any());self.assertTrue(z.ready.iloc[164])
 def test_missing_amount_reject(self):
  f=fixture();f.loc[f.index[110],'amount']=np.nan
  with self.assertRaises(ValueError):model.calculate(f)
 def test_e0_invalid_no_receipts(self):
  f=fixture(np.linspace(130,300,40));f.loc[f.index[150:],'e0_valid']=False;z=model.calculate(f);self.assertFalse(z.receipt.iloc[150:].any())
 def test_down_event_is_reset_not_exit(self):
  f=fixture(np.linspace(130,180,40));f.loc[f.index[160],'e0_down']=True;z=model.calculate(f);self.assertEqual(z.iloc[160].reset_reason,'E0_down_reset');self.assertFalse(z.iloc[160].receipt)
 def test_no_threshold_lowered_mid_segment(self):
  f=fixture(np.r_[np.linspace(130,140,4),np.repeat(139.,30)]);z=model.calculate(f)
  for j in range(65,len(z)):
   if z.iloc[j].phase is not None and z.iloc[j].reset_reason is None:self.assertEqual(z.iloc[j].scale,z.iloc[j-1].next_scale)
 def test_receipt_consumes(self):
  z=model.calculate(fixture(np.linspace(130,250,80)));q=z[z.receipt];self.assertTrue(q.next_credit.eq(0).all());self.assertTrue(q.next_phase.eq('UP').all());self.assertTrue(q.delta_frontier.gt(0).all());self.assertTrue(q.candidate.gt(0).all())
 def test_projection_exit_before_raise(self):
  f=fixture();f=f.iloc[-3:].copy();f['close']=[100.,89.,120.];f['i_floor']=90.;z=pd.DataFrame(dict(receipt=[False,True,False],candidate=[np.nan,95.,np.nan]),index=f.index)
  r=model.project(f,z,f.index[0],90.);self.assertEqual(len(r),2);self.assertTrue(r[-1]['exit']);self.assertEqual(r[-1]['P_after'],90.)
 def test_projection_never_lowers(self):
  f=fixture(np.linspace(130,250,80));z=model.calculate(f);r=model.project(f,z,f.index[150],70.,True);self.assertTrue(all(x['P_after']>=x['P_before'] for x in r))
 def test_known_unit_scaling_sample(self):
  f=fixture(np.linspace(130,250,80));a=model.calculate(f);f['close']*=7.3;f['i_floor']*=7.3;f['amount']*=10000;b=model.calculate(f);self.assertEqual(a.receipt.tolist(),b.receipt.tolist());np.testing.assert_allclose(a.m,b.m,equal_nan=True,atol=1e-12)
 def test_floor_is_economic_not_numeric(self):
  z=model.calculate(fixture(np.repeat(100.,90)));self.assertTrue(z.z.iloc[-10:].eq(model.S_MIN).all());self.assertTrue(z.s.iloc[-10:].eq(1e-8).all())
if __name__=='__main__':
 buf=io.StringIO();r=unittest.TextTestRunner(stream=buf,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 save(O/'tests.json',dict(passed=r.wasSuccessful(),tests=r.testsRun,scope='synthetic technical only, no history/account',details=buf.getvalue(),code_sha256={str(p):sha(p) for p in [Path(__file__),Path(model.__file__)]}))
 print(buf.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
