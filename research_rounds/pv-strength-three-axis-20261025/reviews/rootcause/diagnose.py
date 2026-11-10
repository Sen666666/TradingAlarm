"""Read-only B1 diagnosis. No candidate, fitted parameter, trade or source mutation.

Output selection and these diagnostics were written after inspecting B1 outputs:
all results are exploratory historical development evidence.
"""
from pathlib import Path
import os, sys, json, hashlib, importlib.util, datetime
sys.dont_write_bytecode = True
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent/'mplconfig'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
OLD = ROOT/'research_rounds/pv-strength-20261025'
spec = importlib.util.spec_from_file_location('frozen_b1', OLD/'code/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
KAPPA = np.sqrt(21.)
WINDOWS = {
 'consolidation_main_202505_08': ('2025-05-01','2025-08-31'),
 'september_separate': ('2025-09-01','2025-09-30'),
 'decline_main_202603_06': ('2026-03-01','2026-06-30'),
 'july_separate': ('2026-07-01','2026-07-31'),
 'consolidation_inclusive_202505_09': ('2025-05-01','2025-09-30'),
 'decline_inclusive_202603_07': ('2026-03-01','2026-07-31'),
 'preceding_shock_20260120_0213': ('2026-01-20','2026-02-13'),
}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def f(mu,sigma): return 100*np.tanh(KAPPA*mu/sigma)

def trace_filter(inp):
 """Instrument the existing equations, keeping all Q/R/rho/prior constants exact."""
 rows=[]
 for segment_id,seg in inp.groupby('segment_id',sort=False):
  g=seg.loc[seg.valid_strength_observation]
  y=np.log(g.close.to_numpy(float)/float(g.close.iloc[0]))
  v=g.volume.to_numpy(float);r=np.r_[np.nan,np.diff(y)];m=P=None
  for t in range(64,len(g)):
   sigma=max(float(np.sqrt(np.mean(r[t-63:t]**2))),1e-8)
   a=float(np.clip(v[t]/np.median(v[t-21:t]),.25,4))
   if m is None:
    m=np.array([y[t],0.,0.]);P=sigma**2*np.diag([1.,1/21**2,1.]);continue
   prev=m.copy();pred=model.F@m;cov=model.F@P@model.F.T
   res=float(y[t]-model.H@pred)
   gains=[];variances=[];means=[];covs=[];ll=[]
   qs=np.array([[.01,1/21**2,.01],[a,a/5**2,.01],[.01,1/21**2,4*a]])*sigma**2
   for q in qs:
    p=cov+np.diag(q);s=float(model.H@p@model.H+sigma**2*.25);k=p@model.H/s
    mean=pred+k*res;A=model.I-np.outer(k,model.H)
    post=A@p@A.T+np.outer(k,k)*(.25*sigma**2)
    gains.append(k);variances.append(s);means.append(mean);covs.append(post)
    ll.append(-.5*(np.log(2*np.pi*s)+res*res/s))
   logw=np.log(model.PRIOR)+np.array(ll);w=np.exp(logw-logw.max());w/=w.sum()
   means=np.array(means);m=w@means
   P=sum(weight*(p+np.outer(x-m,x-m)) for weight,x,p in zip(w,means,covs));P=(P+P.T)/2
   gains=np.array(gains);keff=w@gains
   old_epsilon=float(y[t-1]-prev[0]-prev[2])
   ret_piece=float(r[t]);advance_piece=-prev[1];temporary_piece=(1-model.RHO)*prev[2]
   parts=np.array([ret_piece,advance_piece,temporary_piece,old_epsilon])
   row=dict(date=g.index[t],segment_id=int(segment_id),close=float(g.close.iloc[t]),
    ret_log=ret_piece,ret_pct=float(100*np.expm1(ret_piece)),sigma=sigma,
    activity=a,mu_prev=prev[1],mu=m[1],T_prev=prev[2],T=m[2],
    pred_level=pred[0],pred_temporary=pred[2],residual=res,
    residual_current_return=ret_piece,residual_minus_expected_advance=advance_piece,
    residual_T_relaxation=temporary_piece,residual_old_fit=old_epsilon,
    mu_delta=float(m[1]-prev[1]),mu_gain=keff[1],T_gain=keff[2],L_gain=keff[0],
    T_share_current_level_assimilation=float(keff[2]/(keff[0]+keff[2])),
    gain_mu_vs_normal=float(keff[1]/gains[0,1]),
    one_step_mu_delta_normal=float(gains[0,1]*res),
    one_step_mu_competition_effect=float((keff[1]-gains[0,1])*res),
    mu_from_current_return=float(keff[1]*ret_piece),
    mu_from_expected_advance=float(keff[1]*advance_piece),
    mu_from_T_relaxation=float(keff[1]*temporary_piece),
    mu_from_old_fit=float(keff[1]*old_epsilon),
    normal_weight=w[0],persistent_weight=w[1],transient_weight=w[2],
    strength=f(m[1],sigma),z=KAPPA*m[1]/sigma,
    tanh_slope_fraction=1-np.tanh(KAPPA*m[1]/sigma)**2,
    residual_decomposition_error=float(res-parts.sum()),
    mu_decomposition_error=float(m[1]-prev[1]-keff[1]*parts.sum()))
   for j,name in enumerate(['normal','persistent','transient']):
    row['mu_gain_'+name]=gains[j,1];row['T_gain_'+name]=gains[j,2]
    row['variance_'+name]=variances[j]
   rows.append(row)
 out=pd.DataFrame(rows).set_index('date')
 out['sigma_prev']=out.sigma.shift()
 out['strength_prev']=out.strength.shift()
 out['delta_strength']=out.strength.diff();out['delta_z']=out.z.diff()
 # Two-factor, symmetric-order exact Shapley decomposition of displayed score.
 out['score_change_mu']=.5*((f(out.mu,out.sigma_prev)-f(out.mu_prev,out.sigma_prev))+
                           (f(out.mu,out.sigma)-f(out.mu_prev,out.sigma)))
 out['score_change_direct_sigma']=.5*((f(out.mu_prev,out.sigma)-f(out.mu_prev,out.sigma_prev))+
                                     (f(out.mu,out.sigma)-f(out.mu,out.sigma_prev)))
 out['z_change_mu']=.5*KAPPA*(out.mu-out.mu_prev)*(1/out.sigma_prev+1/out.sigma)
 out['z_change_direct_sigma']=.5*KAPPA*(out.mu+out.mu_prev)*(1/out.sigma-1/out.sigma_prev)
 out['score_decomposition_error']=out.delta_strength-out.score_change_mu-out.score_change_direct_sigma
 out['z_decomposition_error']=out.delta_z-out.z_change_mu-out.z_change_direct_sigma
 out['ret_5_pct']=100*inp.close.pct_change(5).reindex(out.index)
 out['ret_21_pct']=100*inp.close.pct_change(21).reindex(out.index)
 out['sigma_including_today_display_only']=np.sqrt(pd.Series(r,index=g.index).pow(2).rolling(63).mean()).reindex(out.index)
 out['score_if_current_return_in_sigma_display_only']=f(out.mu,out.sigma_including_today_display_only)
 return out

def window_stats(g):
 abs_m=float(g.score_change_mu.abs().sum());abs_s=float(g.score_change_direct_sigma.abs().sum())
 parts=['mu_from_current_return','mu_from_expected_advance','mu_from_T_relaxation','mu_from_old_fit']
 part_abs={x:float(g[x].abs().sum()) for x in parts};psum=sum(part_abs.values())
 return dict(rows=len(g),first=str(g.index[0].date()),last=str(g.index[-1].date()),
  first_close=float(g.close.iloc[0]),last_close=float(g.close.iloc[-1]),
  price_change_first_to_last_pct=float(100*(g.close.iloc[-1]/g.close.iloc[0]-1)),
  S_min=float(g.strength.min()),S_max=float(g.strength.max()),
  S_total_variation=float(g.delta_strength.abs().sum()),
  score_mu_abs_attribution=abs_m,score_direct_sigma_abs_attribution=abs_s,
  score_mu_abs_share=abs_m/(abs_m+abs_s),score_direct_sigma_abs_share=abs_s/(abs_m+abs_s),
  score_mu_signed_attribution=float(g.score_change_mu.sum()),
  score_direct_sigma_signed_attribution=float(g.score_change_direct_sigma.sum()),
  z_mu_abs_attribution=float(g.z_change_mu.abs().sum()),
  z_sigma_abs_attribution=float(g.z_change_direct_sigma.abs().sum()),
  mu_daily_pct_min=float(100*np.expm1(g.mu.min())),mu_daily_pct_max=float(100*np.expm1(g.mu.max())),
  mu_21_log_pct_total_variation=float(2100*g.mu_delta.abs().sum()),
  sigma_min=float(g.sigma.min()),sigma_max=float(g.sigma.max()),
  sign_crosses=int(((g.strength*g.strength.shift())<0).sum()),
  abs_score_over_95_days=int((g.strength.abs()>95).sum()),
  median_tanh_slope_fraction=float(g.tanh_slope_fraction.median()),
  median_mu_gain=float(g.mu_gain.median()),
  median_mu_gain_vs_normal=float(g.gain_mu_vs_normal.median()),
  transient_weight_over_half_days=int((g.transient_weight>.5).sum()),
  median_T_share_current_assimilation=float(g.T_share_current_level_assimilation.median()),
  mu_residual_part_abs=part_abs,mu_residual_part_abs_share={k:v/psum for k,v in part_abs.items()},
  T_sigma_abs_median=float((g['T']/g.sigma).abs().median()),
  T_sigma_abs_max=float((g['T']/g.sigma).abs().max()),
  largest_score_change_date=str(g.delta_strength.abs().idxmax().date()))

def plots(inp,old,trace):
 for name,(a,b) in WINDOWS.items():
  if name not in ['consolidation_main_202505_08','decline_main_202603_06','preceding_shock_20260120_0213']:continue
  raw=inp.loc[a:b];g=trace.loc[a:b]
  fig,ax=plt.subplots(2,1,figsize=(14,6),sharex=True,gridspec_kw={'height_ratios':[3,1]})
  ax[0].plot(raw.index,raw.close,color='black');ax[0].fill_between(raw.index,raw.low,raw.high,color='grey',alpha=.2)
  ax[0].set_ylabel('AU0 close / daily range');ax[1].bar(raw.index,raw.volume,width=.8);ax[1].set_ylabel('Volume')
  ax[0].set_title(name+' | raw frozen OHLCV');fig.autofmt_xdate();fig.tight_layout();fig.savefig(OUT/(name+'_raw.png'),dpi=140);plt.close(fig)
  fig,ax=plt.subplots(6,1,figsize=(15,15),sharex=True)
  ax[0].plot(raw.index,raw.close,color='black');ax[0].set_ylabel('Close')
  ax[1].plot(g.index,g.strength,label='B1 S');ax[1].plot(g.index,old.loc[g.index,'total_21_strength'],label='Including T diagnostic',alpha=.6);ax[1].axhline(0,color='grey');ax[1].set_ylim(-105,105);ax[1].legend()
  ax[2].plot(g.index,2100*g.mu,label='21*mu, log %');ax[2].plot(g.index,100*g.sigma,label='lagged sigma, %');ax[2].axhline(0,color='grey');ax[2].legend()
  ax[3].bar(g.index,g.score_change_mu,label='Delta S: mu',color='tab:blue');ax[3].bar(g.index,g.score_change_direct_sigma,label='Delta S: direct sigma',color='tab:orange',alpha=.8);ax[3].legend()
  ax[4].plot(g.index,g['T']/g.sigma,label='T / sigma');ax[4].plot(g.index,g.residual/g.sigma,label='current residual / sigma',alpha=.7);ax[4].axhline(0,color='grey');ax[4].legend()
  ax[5].plot(g.index,g.transient_weight,label='transient weight');ax[5].plot(g.index,g.gain_mu_vs_normal,label='mu gain / normal branch');ax[5].plot(g.index,g.T_share_current_level_assimilation,label='signed T / fitted-level update');ax[5].legend()
  ax[0].set_title(name+' | B1 equations, no new candidate');fig.autofmt_xdate();fig.tight_layout();fig.savefig(OUT/(name+'_attribution.png'),dpi=140);plt.close(fig)

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 # Verify old evidence is byte-identical after diagnostics, including its scripts.
 old_paths=sorted(p for p in OLD.rglob('*') if p.is_file())
 old_before={str(p.relative_to(ROOT)):sha(p) for p in old_paths}
 inp=pd.read_parquet(OLD/'inputs/AU0.parquet');old=pd.read_parquet(OLD/'results/AU0.parquet')
 trace=trace_filter(inp)
 for a in ['strength','sigma','normal_weight','persistent_weight','transient_weight','activity']:
  np.testing.assert_allclose(trace[a],old.loc[trace.index,a],atol=2e-12,rtol=1e-12)
 np.testing.assert_allclose(trace.mu,old.loc[trace.index,'drift'],atol=1e-15,rtol=1e-12)
 for c in ['mu_decomposition_error','residual_decomposition_error','score_decomposition_error','z_decomposition_error']:
  assert trace[c].abs().max()<1e-10,(c,trace[c].abs().max())
 trace.to_csv(OUT/'AU0_full_trace.csv');trace.to_parquet(OUT/'AU0_full_trace.parquet')
 stats={k:window_stats(trace.loc[a:b]) for k,(a,b) in WINDOWS.items()}
 write_json(OUT/'window_statistics.json',stats)
 for k,(a,b) in WINDOWS.items():trace.loc[a:b].to_csv(OUT/(k+'.csv'))
 selected=['2025-05-12','2025-05-15','2025-05-21','2025-06-30','2025-07-28','2025-08-04','2025-08-25','2025-08-29','2025-09-01','2026-01-29','2026-01-30','2026-02-02','2026-02-03','2026-02-04','2026-02-10','2026-02-11','2026-03-02','2026-03-23','2026-04-01','2026-04-02','2026-06-17','2026-06-22','2026-06-30','2026-07-21','2026-07-23','2026-07-24']
 selected=trace.loc[pd.to_datetime(selected)].join(old[['total_21_strength','drift_21_pct','price_only_strength','e0_target','e0_floor']])
 selected.to_csv(OUT/'selected_daily_attribution.csv')
 prefix=[]
 for cutoff in ['2025-05-15','2025-08-29','2026-02-02','2026-03-23','2026-06-30','2026-07-23']:
  path=OUT/('physical_input_prefix_'+cutoff+'.parquet');inp.loc[:cutoff].to_parquet(path)
  physical=pd.read_parquet(path);calc=model.strength_frame(physical)
  pd.testing.assert_frame_equal(old.loc[calc.index,calc.columns],calc,check_exact=True)
  prefix.append(dict(cutoff=cutoff,rows=len(calc),all_B1_columns_exact=True,input_sha256=sha(path),last_score=float(calc.strength.iloc[-1])))
 write_json(OUT/'physical_prefix_checks.json',prefix)
 synth=[]
 for case,lo,hi in [('fast_start',118,132),('true_weakening',182,200),('bear_rebound',182,200),('lowvol_selloff',182,197),('one_pulse',118,135)]:
  g=pd.read_parquet(OLD/'validation'/(case+'.parquet'));g=g.copy();g['observation']=np.arange(len(g));g['ret_pct']=100*g.close.pct_change();g['ret_21_pct']=100*g.close.pct_change(21)
  g.iloc[lo:hi].to_csv(OUT/('synthetic_'+case+'_transition.csv'))
  start=120 if case in ['fast_start','one_pulse'] else 185
  suffix=g.iloc[start:]
  target_positive=case in ['fast_start','bear_rebound']
  sign=(suffix.strength>0) if target_positive else (suffix.strength<0)
  if case=='one_pulse':sign=suffix.strength.abs()<1
  first=next((int(x) for x in suffix.loc[sign,'observation']),None)
  synth.append(dict(case=case,change_observation_zero_based=start,diagnostic_target=('abs(S)<1 after pulse' if case=='one_pulse' else ('positive S' if target_positive else 'negative S')),first_target_observation=first,observations_from_change_inclusive=(first-start+1 if first is not None else None),transition_start_score=float(g.strength.iloc[start]),transition_start_return_pct=float(g.ret_pct.iloc[start]),transition_start_temporary_sigma=float(g.temporary_sigma.iloc[start])))
 write_json(OUT/'synthetic_transition_statistics.json',synth)
 plots(inp,old,trace)
 old_after={str(p.relative_to(ROOT)):sha(p) for p in old_paths}
 assert old_before==old_after
 registry=json.loads((ROOT/'research_rounds/algorithm-baselines-20261024/registry.json').read_text())
 for path,h in registry['sha256'].items():assert sha(ROOT/path)==h,path
 write_json(OUT/'audit.json',dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  scope='exploratory read-only B1 root-cause diagnosis; no candidate/parameter/strategy/account/new quote',
  diagnostic_script_sha256=sha(Path(__file__)),model_sha256=sha(OLD/'code/model.py'),input_sha256=sha(OLD/'inputs/AU0.parquet'),
  source_rows=len(inp),source_valid_observations=int(inp.valid_strength_observation.sum()),scored_rows=len(trace),frozen_registry_files_unchanged=len(registry['sha256']),
  old_evidence_files_unchanged=len(old_paths),old_files_sha256=old_after,
  max_strength_reproduction_error=float((trace.strength-old.loc[trace.index,'strength']).abs().max()),
  max_mu_reproduction_error=float((trace.mu-old.loc[trace.index,'drift']).abs().max()),
  decomposition_max_errors={c:float(trace[c].abs().max()) for c in ['mu_decomposition_error','residual_decomposition_error','score_decomposition_error','z_decomposition_error']},
  physical_prefixes=len(prefix),accounts=0,source_mutations=0,parameter_changes=0))
 print(json.dumps(stats,indent=2))

if __name__=='__main__': main()
