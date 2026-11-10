"""Limited implementation probes, not official synthetic performance evaluation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import numpy as np
import pandas as pd
from reference import reference_frame

HERE = Path(__file__).resolve().parent
ROUND = HERE.parents[1]
spec = importlib.util.spec_from_file_location('b2_under_audit', ROUND/'code/model.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
checks = []

def check(name, condition, evidence=None):
    checks.append(dict(name=name, passed=bool(condition), evidence=evidence))

def frame(seed=8723, n=700):
    rng = np.random.default_rng(seed)
    ret = rng.normal(.0002,.012,n)
    ret[[92,201,399,587]] = [-.09,.07,-.12,.09]
    v = np.exp(rng.normal(7,.7,n))
    return pd.DataFrame(dict(close=100*np.exp(np.cumsum(ret)), volume=v,
                             segment_id='one', valid_strength_observation=True),
                        index=pd.date_range('2000-01-01', periods=n))

f = frame()
a,journal = m.three_axis_frame(f)
b = reference_frame(f).reindex(columns=a.columns)
diff = np.abs(a.to_numpy()-b.to_numpy())
check('independent_700_observation_all_fields',
      np.array_equal(np.isnan(a),np.isnan(b)) and np.allclose(a,b,rtol=2e-11,atol=2e-11,equal_nan=True),
      dict(rows=len(a), columns=len(a.columns), max_abs_error=float(np.nanmax(diff))))
check('first_64_unknown_first_computable_t64', a.iloc[:64].isna().all().all() and
      a.iloc[64]['init']==1 and math.isfinite(a.iloc[64]['shock']))
_,jno = m.three_axis_frame(f,joint=False)
ano,_ = m.three_axis_frame(f,joint=False)
prcols=[c for c in a if not any(s in c for s in ('down_','up_','impulse_created','oldest_'))]
check('volume_ablation_P_R_and_shock_exact', a[prcols].equals(ano[prcols]))

# Direct state-machine boundaries deliberately use binary-exact geometry.
def structure():
    events=[]
    return m.Structure(0.,0,.125,lambda t,k,z:events.append((t,k,z))),events
s,e = structure()
s.update(.25,1,.125,.25)
z=s.update(.5,2,.125,.25)
s.update(.25,3,.125,-.25) # checkpoint at .5, pivot .25
z=s.update(.625,4,.125,.375) # same day recover and true new extreme
check('checkpoint_confirm_before_new_E_origin_fixed', z['pivot_confirmed']==1 and s.S==.25 and
      s.A==0 and s.E==.625 and s.advances==1 and s.episode==1,
      {k:z[k] for k in ['episode','origin','support','extreme','pivot_confirmed']})
z=s.update(.25,5,.125,-.375)
check('support_equality_break_old_today_R_and_new_identity', z['structure_broken']==1 and
      z['old_retention_at_t']==.4 and z['old_support']==.25 and z['pre_direction']==1 and
      z['direction']==-1 and z['episode']==2 and z['retention']==1)

s,e=structure()
s.begin(1,0.,0,.25,1,1.) # threshold 2; support failure need not establish reverse
z=s.update(0.,2,.01,-.25)
check('broken_without_reverse_unknown_candidates_frozen', z['direction']==0 and
      z['structure_broken']==1 and z['structure_created']==0 and s.high==.25 and
      s.high_delta==2 and s.low==0 and s.low_delta==.02)
z=s.update(.03125,3,.01,.03125)
check('same_direction_restart_after_unknown_uses_new_ID', z['direction']==1 and
      z['episode']==2 and z['origin']==0 and z['structure_created']==1)

s,e=structure()
s.update(.25,1,.125,.25)
s.update(.5,2,.125,.25)
s.update(.375,3,.001,-.125) # less than old .25, although new sigma tiny
z=s.update(.375,4,.0001,0.)
check('no_sigma_only_checkpoint_or_reanchor', math.isnan(s.K) and s.delta==.25 and s.E_t==2 and
      z['progress_age']==2 and z['retention']==.75)

# Episode transitions do not enter the ledger's recovery rule.
e=[];l=m.Ledger(lambda t,k,z:e.append((t,k,z)))
z=l.update(0.,.125,0,.01,3,1)
z=l.update(.0625,0.,1,.01,1,2)
z=l.update(-.0625,.0625,2,.01,1,3)
check('partial_recovery_monotone_no_resurrection_cross_episode', len(l.live)==1 and
      l.live[0]['lo']==.0625 and l.live[0]['hi']==.125 and
      l.live[0]['birth_episode']==1 and z['down_zone_log_pct']==6.25)
z=l.update(.125,-.0625,3,.01,1,4)
z=l.update(0.,.125,4,.01,1,5)
check('fully_recovered_old_ID_never_revives', not l.live and z['down_zone_log_pct']==0)
z=l.update(-.0625,0.,5,.01,3,6)
check('new_qualified_fall_creates_new_identity', len(l.live)==1 and l.live[0]['event']==2 and
      l.live[0]['birth_episode']==6)
z=l.update(-.25,-.0625,6,.01,1,7)
z=l.update(-.24,-.25,7,.01,1,8)
check('remote_small_bounce_does_not_clear_old_region', z['down_zone_log_pct']==6.25)
check('defensive_union_overlap_and_touch', m.union_length([(0,.5),(.25,.75),(.75,1)])==(1.,1))

# Both directions coexist, rather than netting to endpoint displacement.
l=m.Ledger(lambda *args:None)
l.update(.125,0.,0,.01,3,1)
z=l.update(.0625,.125,1,.01,3,1)
check('up_down_regions_coexist_without_netting', z['up_zone_log_pct']==6.25 and
      z['down_zone_log_pct']==6.25 and z['up_events']==z['down_events']==1)

# Segment state must restart, but old unresolved evidence must be archived, not healed.
f2=frame(n=700)
f2.loc[f2.index[350:],'segment_id']='two'
f2.loc[f2.index[[70,71,490]],'valid_strength_observation']=False
a2,j2=m.three_axis_frame(f2)
b2=reference_frame(f2).reindex(columns=a2.columns)
check('invalid_and_segment_independent_recalculation', np.array_equal(np.isnan(a2),np.isnan(b2)) and
      np.allclose(a2,b2,rtol=2e-11,atol=2e-11,equal_nan=True))
check('segment_rewarms_64_unknown_observations', a2.loc[f2.index[350:414]].isna().all().all() and
      a2.loc[f2.index[414],'init']==1)
archives=[e for e in j2 if e['kind']=='source_segment_start_unresolved_archive']
check('source_discontinuity_archives_not_price_heal', len(archives)==1 and
      archives[0]['date']==str(f2.index[350].date()) and
      'live_impulses' in archives[0]['prior_terminal'] and archives[0]['previous_segment']=='one')

# A physical truncated file is supplied to the model, not only an in-memory view.
cut=412
prefix_path=HERE/'prefreeze_random_physical_prefix.parquet'
f.iloc[:cut].to_parquet(prefix_path)
prefix=pd.read_parquet(prefix_path)
ap,jp=m.three_axis_frame(prefix)
check('physical_prefix_rows_and_journal_exact', ap.equals(a.iloc[:cut]) and
      jp==[e for e in journal if e['date']<=str(prefix.index[-1].date())])

payload=dict(scope='Pre-freeze implementation probes only; not official semantic results; no real B2 outputs viewed.',
             model_sha256=hashlib.sha256((ROUND/'code/model.py').read_bytes()).hexdigest(),
             protocol_sha256=hashlib.sha256((ROUND/'PROTOCOL.md').read_bytes()).hexdigest(),
             passed=sum(c['passed'] for c in checks),total=len(checks),checks=checks)
(HERE/'prefreeze_probe_results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(payload,ensure_ascii=False,indent=2))
assert payload['passed']==payload['total']
