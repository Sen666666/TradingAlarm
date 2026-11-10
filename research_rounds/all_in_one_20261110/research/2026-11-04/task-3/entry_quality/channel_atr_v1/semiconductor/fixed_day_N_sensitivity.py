"""Only fixed-day arithmetic, not a trailing-stop or account replay."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
rows=json.loads((O/'TEN_FIXED_FEATURE_ROWS.json').read_text());launch={r['sid']:r['launch'] for r in json.loads((O/'E0_LAUNCH_SOURCE_ROWS.json').read_text())};prices={}
out=[]
for r in rows:
 sid=r['sid'];p=prices.setdefault(sid,pd.read_parquet(O/(sid.replace('.','_')+'_ORIGINAL_OHLC_FULL_PREFIX.parquet')))
 t=pd.Timestamp(r['day']);prior=p.loc[(p.index>=pd.Timestamp(launch[sid]))&(p.index<t)];M=float(prior.high.max());atr=r['ATR14_prior']
 for N in [2,3,4]:
  q=M-N*atr
  out.append(dict(sid=sid,day=r['day'],launch=launch[sid],N=N,C=r['C'],M_prior=M,ATR_prior=atr,raw_ATR_proposal=q,C_minus_raw_proposal=r['C']-q,raw_proposal_already_violated=q>=r['C'],interpretation='Conditional on protection already active and this observation peak applying to that layer: proposal already violated; not a fill-price or proof of actual prior holding.' if q>=r['C'] else 'Not proof of survival: old ratcheted P or hard I may already have caused an earlier exit.',not_inferred=['old_P','hard_I_floor_when_absent','actual_position','execution','first_exit_date','reentry'],new_N_path=False,M_prior_kind='E0_LAUNCH_OBSERVATION_WINDOW_NOT_ACTUAL_LAYER_HOLDING_PEAK',real_layer_peak_requirement='Start at real fill-known time; do not backfill pre-entry highs.'))
(O/'TEN_DAY_N_SENSITIVITY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');pd.DataFrame(out).to_csv(O/'TEN_DAY_N_SENSITIVITY.csv',index=False)
(O/'FIXED_DAY_ARITHMETIC_RECEIPT.json').write_text(json.dumps(dict(status='FIXED_DAY_DIAGNOSTICS_ONLY',rows=len(out),fixed_N=[2,3,4],source_sha256={str((O/'TEN_FIXED_FEATURE_ROWS.json').resolve()):hashlib.sha256((O/'TEN_FIXED_FEATURE_ROWS.json').read_bytes()).hexdigest()},old_line_or_N_path_replay=False,new_accounts=0,new_quantities=0,new_returns=0,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
for r in out:
 if r['day'] in ['2026-02-02','2026-02-03','2026-02-05','2026-02-12']:print(json.dumps({k:r[k] for k in ['sid','day','N','C','M_prior','ATR_prior','raw_ATR_proposal','C_minus_raw_proposal','raw_proposal_already_violated']}))
