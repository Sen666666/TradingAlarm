"""Four failure-day original-input substitutions plus two seed old-sigma checks; no FSM replay."""
from pathlib import Path
from statistics import median
import json,math,hashlib
import pandas as pd
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;S=R/'cp_formula_redesign_v1/shadow/protection_v3'
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CASES={'000620.SZ':['2022-01-18','2022-01-27'],'002583.SZ':['2024-11-01'],'300085.SZ':['2024-10-10']}
SEEDS={'000620.SZ':'2022-01-20','002583.SZ':'2024-11-20'}
checks=[];bound={};saved={}
def bind(p):
 p=Path(p);bound[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def check(sid,date,field,a,b):
 if a is None or b is None:passed=a is b;err=None
 else:err=abs(float(a)-float(b));passed=err<=1e-10*max(1.,abs(float(b)))
 checks.append(dict(sid=sid,date=date,field=field,saved=a,independent=b,absolute_error=err,passed=passed));assert passed,(sid,date,field,a,b)
m={x['symbol']:x for x in json.loads(bind(MANIFEST).read_text())}
for sid,dates in CASES.items():
 f=pd.read_parquet(bind(m[sid]['refs']['CP1_input']));facts=pd.read_parquet(bind(m[sid]['refs']['facts']));rows=json.loads(bind(S/(sid+'_combined.json')).read_text());saved[sid]=rows
 for day in dates:
  x=next(z for z in rows if z['date']==day);prev=rows[rows.index(x)-1];i=f.index.get_loc(pd.Timestamp(day));g=f.iloc[:i+1];g=g[g.segment_id.eq(f.iloc[i].segment_id)];C=[float(z)for z in g.close];rr=[math.log(C[k])-math.log(C[k-1])for k in range(1,len(C))];lag=rr[-22:-1];assert len(lag)==21
  d21=math.sqrt(sum(min(z,0.)**2 for z in lag)/21);z63=max(math.log1p(.001),1e-8,1.4826*median(abs(z)for z in rr[-64:-1]));C=float(f.iloc[i].close);H=prev['market_line_after'];init=prev['protection_initial_frozen_scale'];sigH=max(init,d21)
  check(sid,day,'source_close',x['close'],C);check(sid,day,'source_I_domain',x['valid'],bool(facts.loc[day,'i_target']));check(sid,day,'downside21_lag_squared',x['downside21'],d21);check(sid,day,'source_z63_lag',x['z63'],z63);check(sid,day,'H_before_from_previous_output',x['market_line_before'],H);check(sid,day,'decision_sigmaH',x['protection_scale'],sigH);check(sid,day,'H_before_raw',x['market_line_before_raw'],H/float(facts.loc[day,'factor']));check(sid,day,'old_line_broken',x['market_line_failed'],C<=H);check(sid,day,'no_same_bar_receipt',x['receipt'],False);check(sid,day,'line_after_clear',x['market_line_after'],None);check(sid,day,'init_after_clear',x['protection_initial_frozen_scale'],None);check(sid,day,'REPAIR_anchor',x['proof_anchor_after'],math.log(C));check(sid,day,'REPAIR_sigma',x['proof_scale_after'],z63);check(sid,day,'amount_clear',x['next_amount_sum'],0);check(sid,day,'baseline_clear',x['next_baseline_sum'],0)
 if sid in SEEDS:
  day=SEEDS[sid];x=next(z for z in rows if z['date']==day);prev=rows[rows.index(x)-1];init=x['proof_scale_before'];sigH=max(init,x['downside21']);H=x['close']*math.exp(-math.sqrt(21)*sigH)
  check(sid,day,'receipt_init_is_old_proof_sigma',x['protection_initial_frozen_scale'],init);check(sid,day,'old_sigma_prior_state',init,prev['proof_scale_after']);check(sid,day,'seed_protection_scale',x['protection_scale'],sigH);check(sid,day,'seed_line',x['market_line_after'],H);check(sid,day,'next_proof_sigma',x['proof_scale_after'],x['z63']);assert init!=x['proof_scale_after'],'Selected seed must distinguish pre- vs post-reset sigma'
# finite saved-output invariants only, not another formula/state-machine run
for sid,day in [('000620.SZ','2022-01-17'),('002583.SZ','2024-09-27')]:
 rows=saved[sid];x=next(z for z in rows if z['date']==day);prev=rows[rows.index(x)-1];assert x['down']and not x['market_line_failed']
 check(sid,day,'down_preserves_init',x['protection_initial_frozen_scale'],prev['protection_initial_frozen_scale']);check(sid,day,'down_preserves_parent',x['parent_trend_episode']==prev['parent_trend_episode'],True)
out=dict(scope='Four predetermined failure-day original-input substitutions;two distinct-old/new-sigma seed rows;two saved-output down invariants;no full FSM replay',failure_days=4,seed_old_sigma_rows=2,saved_down_invariant_rows=2,checks=len(checks),passed=all(x['passed']for x in checks),maximum_absolute_error=max(x['absolute_error']or 0 for x in checks),new_accounts=0,new_backtests=0,full_formula_runs=0,source_sha256=bound,checks_detail=checks)
(O/'FINITE_V3_PROTECTION_SUBSTITUTIONS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print({k:out[k]for k in ['failure_days','seed_old_sigma_rows','checks','passed','maximum_absolute_error']})
