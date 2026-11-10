"""Semantic probes and technical invariants. No trades or return optimization."""
import numpy as np,pandas as pd
from data import HERE,ROOT,read,write,sha,now
from model import strength_frame,run_valid

def synth(returns,volume):
 c=100*np.exp(np.cumsum(returns));f=pd.DataFrame({'close':c,'volume':volume},index=pd.bdate_range('2019-01-01',periods=len(c)))
 f['segment_id']=0;f['valid_strength_observation']=True;return f

def main():
 out=HERE/'validation';out.mkdir(exist_ok=False);rng=np.random.default_rng(177);warm=rng.normal(0,.004,120);basevol=np.full(120,100.)
 paths={
 'fast_start':(np.r_[warm,np.full(5,.02),np.full(55,.003)],np.r_[basevol,np.full(5,400.),np.full(55,150.)]),
 'slow_rise':(np.r_[warm,.001+rng.normal(0,.0003,160)],np.r_[basevol,np.full(160,100.)]),
 'consolidation':(np.r_[warm,np.full(60,.004),rng.normal(0,.0015,40),np.full(50,.003)],np.r_[basevol,np.full(60,150.),np.full(40,70.),np.full(50,130.)]),
 'bear_rebound':(np.r_[warm,np.full(65,-.004),np.full(8,.008),np.full(45,-.004)],np.r_[basevol,np.full(65,130.),np.full(8,250.),np.full(45,130.)]),
 'true_weakening':(np.r_[warm,np.full(65,.004),np.full(45,-.006)],np.r_[basevol,np.full(65,130.),np.full(45,170.)]),
 'one_pulse':(np.r_[warm,.08,-.08,np.zeros(58)],np.r_[basevol,400.,350.,np.full(58,100.)]),
 'lowvol_selloff':(np.r_[warm,np.full(65,.004),np.full(3,-.105),.05,-.105,np.full(20,-.002)],np.r_[basevol,np.full(65,130.),[15.,5.,13.,250.,150.],np.full(20,100.)]),
 'same_end_recovery':(np.r_[warm,.04,-.06,.04],np.r_[basevol,[100.,400.,100.]]),
 'same_end_retracement':(np.r_[warm,.04,.04,-.06],np.r_[basevol,[100.,100.,400.]])}
 metrics=[];technical=0
 for name,(r,v) in paths.items():
  f=synth(r,v);a=strength_frame(f);p=strength_frame(f,False);f.join(a).assign(price_only=p.strength).to_parquet(out/(name+'.parquet'))
  assert np.isfinite(a.strength.dropna()).all() and a.strength.dropna().abs().le(100).all();assert a.cov_min_eigenvalue.dropna().ge(-1e-14).all();technical+=1
  aa=strength_frame(f.assign(close=f.close*37.0,volume=f.volume*123.0));np.testing.assert_allclose(a.strength,aa.strength,atol=1e-8,rtol=1e-10,equal_nan=True);technical+=1
  cut=170 if len(f)>170 else 121;b=strength_frame(f.iloc[:cut]);pd.testing.assert_frame_equal(a.iloc[:cut],b,check_exact=True);technical+=1
  good=a.iloc[120:];metrics.append(dict(case=name,end_strength=float(a.strength.iloc[-1]),min_strength=float(good.strength.min()),max_strength=float(good.strength.max()),max_abs_volume_difference=float((a.strength-p.strength).abs().max())))
 # Same prefix fork: all identical outputs through the fork date, all components.
 f=synth(np.r_[warm,np.full(30,.003),np.full(30,.004)],np.full(180,100.));g=synth(np.r_[warm,np.full(30,.003),np.full(30,-.004)],np.full(180,100.));pd.testing.assert_frame_equal(strength_frame(f).iloc[:150],strength_frame(g).iloc[:150],check_exact=True);technical+=1
 # Segment restart has no inherited model memory.
 f=synth(np.r_[warm,np.full(120,.002)],np.full(240,100.));f.loc[f.index[120:],'segment_id']=1;a=strength_frame(f);b=strength_frame(f.iloc[120:].assign(segment_id=0));pd.testing.assert_frame_equal(a.iloc[120:],b,check_exact=True);technical+=1
 # Missing bar is unknown, not score0.5/50; past outputs unaffected.
 g=f.copy();g.loc[g.index[175],'valid_strength_observation']=False;assert np.isnan(strength_frame(g).strength.iloc[175]);technical+=1
 prefixes=[]
 for x in read(HERE/'inputs/manifest.json')['series']:
  f=pd.read_parquet(x['path']);full=pd.read_parquet(HERE/'results'/(x['asset']+'.parquet'))
  for cutoff in ['2023-12-29','2025-08-29','2026-06-30']:
   truncated=f.loc[:cutoff]
   if not len(truncated):continue
   p=strength_frame(truncated);pd.testing.assert_frame_equal(full.loc[p.index,p.columns],p,check_exact=True)
   prefixes.append(dict(asset=x['asset'],cutoff=cutoff,rows=len(p),all_fields_exact=True))
 registry=read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')
 for p,h in registry['sha256'].items():assert sha(ROOT/p)==h,p
 # Check all actual per-step posterior quantities.
 for x in read(HERE/'inputs/manifest.json')['series']:
  f=pd.read_parquet(HERE/'results'/(x['asset']+'.parquet')).dropna(subset=['strength']);np.testing.assert_allclose(f[['normal_weight','persistent_weight','transient_weight']].sum(axis=1),1,atol=1e-13);assert (f.cov_min_eigenvalue>=-1e-14).all()
 write(out/'synthetic-metrics.json',metrics);write(out/'checks.json',dict(recorded_at=now(),passed=True,technical_invariants=technical,synthetic_paths=len(paths),physical_input_prefixes=prefixes,registry_files_unchanged=len(registry['sha256']),model_sha256=sha(HERE/'code/model.py'),account_runs=0,semantics='Path outcomes are probes, not threshold pass-fail or future prediction accuracy. Checks completed before real-output visual review; real cache generated first, no parameter changes.'))
 print({'passed':True,'technical':technical,'prefixes':len(prefixes)},flush=True)
if __name__=='__main__':main()
