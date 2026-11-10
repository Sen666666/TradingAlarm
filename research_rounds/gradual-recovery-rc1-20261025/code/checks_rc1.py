"""Offline mechanism units plus native synthetic paths, no account engine."""
from common_rc1 import *
from evidence_rc1 import recover
from grade_rc1 import classify_with_recovery
import pandas as pd

def modules():
 sys.path.insert(0,str(B5/'code'))
 return load('_rc1_api',B5/'code/api.py'),load('_rc1_grade',G1/'code/grade.py'),load('_rc1_ix',G1/'code/policies_g1.py'),load('_rc1_m1',M1/'code/model_m1.py')

def unit(close,volume=1000.,down_background=False):
 n=len(close);ix=pd.bdate_range('2000-01-01',periods=n);v=np.broadcast_to(volume,n)
 e=pd.DataFrame(dict(close=close,volume=v,segment_id='a',valid_strength_observation=True,strength_s=.01,strength_volume_reference=1000.,strength_r=np.r_[np.nan,np.diff(np.log(close))],strength_S21=1.,strength_S63=-1. if down_background else 1.,strength_acute_down=False,strength_confirmed_direction_21=0.,strength_confirmed_direction_63=0.,strength_running_extreme_price_21=np.maximum.accumulate(close)),index=ix);e.loc[ix[1],'strength_acute_down']=True
 g=pd.DataFrame(dict(ready=True,proposal=3.,grade=-3.,score=-75.,fresh_up=False,promotion_blocked=True,transition='blocked_upgrade',z5=.2,label='强冷',display='强冷',acute_down=False,up_reasons=''),index=ix);g.loc[ix[0],['grade','score','promotion_blocked','transition']]=[3.,75.,False,'initialize'];g.loc[ix[1],['proposal','promotion_blocked','transition','acute_down']]=[-3.,False,'downgrade',True]
 g.loc[ix[0],['label','display']]=['热','热'];g.loc[ix[1],'display']='freeze·强冷'
 m=pd.DataFrame(dict(mu63=-.001 if down_background else .001,mu126=-.001 if down_background else .001),index=ix)
 return e,m,g

def main():
 out=HERE/'technical';out.mkdir(exist_ok=False);tests=[]
 def passed(name):tests.append(name)
 close=np.r_[120.,100.,100*np.exp(.005*np.arange(1,21))]
 timings={}
 for name,v in [('low',250.),('ordinary',1000.),('high',4000.)]:
  vols=np.r_[1000.,1000.,np.repeat(v,len(close)-2)];e,m,g=unit(close,vols);rc,j=recover(e,m,g);timings[name]=int(np.flatnonzero(rc.receipt)[0]);rc.to_parquet(out/f'unit-{name}.parquet')
  assert rc.loc[rc.receipt,'increment'].gt(0).all() and rc.loc[rc.receipt,'below_pre_high'].any();passed(name+'_new_volume_price_receipt_below_high')
  h=classify_with_recovery(e,g,rc);assert h.loc[h.rc_promoted_to_warm,'rc_fresh'].all()
 assert timings['low']>timings['ordinary']>=timings['high'];passed('volume_changes_confirmation_time')
 e,m,g=unit(np.r_[120.,100.,np.repeat(100.,180)],np.r_[1000.,1000.,np.repeat(1e6,180)]);rc,j=recover(e,m,g);assert not rc.receipt.any() and rc.credit.fillna(0).eq(0).all();passed('huge_volume_without_price_no_recovery')
 # Price returns to the same frontier repeatedly: no duplicate price credit.
 e,m,g=unit(np.r_[120.,100.,103.,np.tile([102.,103.],30)]);rc,j=recover(e,m,g);assert rc.receipt.sum()==1 and abs(rc.credit.iloc[-1]-math.log(1.03))<1e-14;passed('same_range_cannot_farm_credit')
 e,m,g=unit(close,down_background=True);rc,j=recover(e,m,g);h=classify_with_recovery(e,g,rc);assert h.grade.iloc[2:].le(1).all() and not h.rc_only_fresh.any();passed('down_background_local_rebound_not_new_warm')
 e,m,g=unit(close);rc,j=recover(e,m,g);h=classify_with_recovery(e,g,rc);pd.testing.assert_frame_equal(classify_with_recovery(e,g,rc,enabled=False)[g.columns],g,check_dtype=False);passed('disable_extra_grade_exact')
 # Trigger another actual risk: old accumulated recovery credit is discarded.
 e.loc[e.index[-2],'strength_acute_down']=True;rc,j=recover(e,m,g);assert rc.credit.iloc[-2]==0 and not rc.receipt.iloc[-2];passed('new_shock_clears_credit_and_no_same_bar_recovery')
 e,m,g=unit(close);e.loc[e.index[4],'valid_strength_observation']=False;rc,j=recover(e,m,g);assert not rc.ready.iloc[4] and not rc.receipt.iloc[4];passed('missing_volume_observation_no_new_receipt')
 e,m,g=unit(close);rc,j=recover(e,m,g)
 for n in [1,6,12,18]:
  q,jj=recover(e.iloc[:n],m.iloc[:n],g.iloc[:n]);pd.testing.assert_frame_equal(q,rc.iloc[:n]);assert jj==[x for x in j if x['date']<=str(e.index[n-1].date())]
 passed('unit_prefix_and_journal_exact')
 e2=e.copy();e2.close*=137.;e2.strength_running_extreme_price_21*=137.;e2.volume*=19.;e2.strength_volume_reference*=19.
 q,jj=recover(e2,m,g);assert q.receipt.equals(rc.receipt);np.testing.assert_allclose(q[['x','frontier','credit','delta5','delta21']],rc[['x','frontier','credit','delta5','delta21']],rtol=1e-12,atol=1e-12,equal_nan=True);passed('price_and_volume_unit_invariance')
 api,grade,policy,m1=modules();n=360;t=np.arange(n);noise=.004*np.sin(t*1.77)+.002*np.cos(t*.57)
 paths={
 'flat':np.zeros(n),'slow_up':noise+.0008,'slow_down':noise-.001,
 'fast_launch':np.r_[noise[:180],noise[180:]+.012],
 'decline_then_rebound':np.r_[noise[:220]-.003,noise[220:]+.004],
 'decline_then_new_bull':np.r_[noise[:200]-.003,noise[200:]+.012],
 'up_crash_then_flat':np.r_[noise[:200]+.002,-.12,np.zeros(n-201)],
 'up_crash_then_slow':np.r_[noise[:200]+.002,-.12,noise[201:]+.0008],
 'rebound_then_new_low':np.r_[noise[:180]-.002,noise[180:215]+.004,noise[215:]-.003],
 'slow_up_then_crash':np.r_[noise[:280]+.001,-.15,noise[281:]-.001]
 }
 special=.0006+.0002*np.sin(t*1.77)
 special[240]=.025;special[241]=-.025;special[260]=.025;special[261]=-.025;special[300]=-.003;special[301:]=.00025+.0001*np.sin(t[301:]*1.77)
 paths['mature_slow_partial_repair']=special
 stats=[]
 for name,r in paths.items():
  c=100*np.exp(np.cumsum(r));ix=pd.bdate_range('2000-01-01',periods=n);f=pd.DataFrame(dict(open=c,high=c*1.001,low=c*.999,close=c,volume=1000*(1+.2*np.sin(t*.3)),segment_id='a',valid_price_observation=True,valid_strength_observation=True),index=ix)
  a=api.run_b5(f);e=a['evidence'];g,_=grade.classify(e);mm=m1.describe(f.assign(acute_down=g.acute_down));rc,j=recover(e,mm,g);new=classify_with_recovery(e,g,rc);oldix=policy.project(e,a['state'],g,'G1_IX');newix=policy.project(e,a['state'],new,'G1_IX')
  assert new.grade.dropna().ge(g.grade.dropna()).all();assert not (oldix.target.eq(1)&~newix.target.eq(1)).any();assert (new.loc[new.transition.eq('upgrade'),'fresh_up']).all();assert new.loc[g.acute_down,'grade'].le(-3).all()
  if name in ['flat','up_crash_then_flat']:
   start=201 if name!='flat' else 65;assert not rc.iloc[start:].receipt.any()
  for cut in [127,220,300]:pd.testing.assert_frame_equal(recover(e.iloc[:cut],mm.iloc[:cut],g.iloc[:cut])[0],rc.iloc[:cut])
  result=f.join(rc.add_prefix('rc_')).join(g[['grade','score']].add_prefix('old_')).join(new[['grade','score']].add_prefix('new_'));result.to_parquet(out/f'native-{name}.parquet')
  stats.append(dict(path=name,receipts=int(rc.receipt.sum()),new_warm_promotions=int(new.rc_promoted_to_warm.sum()),original_ix_entries=int(oldix.entered.sum()),rc1_ix_entries=int(newix.entered.sum())))
 pd.DataFrame(stats).to_csv(out/'native-summary.csv',index=False)
 write(out/'checks.json',dict(recorded_at=now(),passed=True,mechanism_tests=tests,volume_receipt_positions=timings,native_paths=len(paths),native_prefixes=3*len(paths),new_accounts=0,unit_receipts_are_injected_evidence_not_native_strategy_results=True))
 print(dict(passed=True,mechanism_tests=len(tests),native_paths=len(paths)),flush=True)
if __name__=='__main__':main()
