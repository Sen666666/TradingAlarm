"""Read source/cache provenance only. Never imports/calls CP or signal models."""
from pathlib import Path
import hashlib,json
import pandas as pd
import numpy as np
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
R29=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
CP=RR/'continuous-protection-lines-20261028/code/model.py'
MANIFEST=R29/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
FEATURE=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v):(HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
 assert not(HERE/'SEAL.json').exists()
 manifest=json.loads(MANIFEST.read_text());by={r['symbol']:r for r in manifest}
 feature_seal=json.loads((FEATURE.parent/'SEAL.json').read_text())
 assert sha(FEATURE)==feature_seal['files'][FEATURE.name]
 feature=pd.read_parquet(FEATURE).set_index(['sid','day'])
 examples=[];sample=[]
 for sid in ['000620.SZ','300085.SZ','002583.SZ']:
  r=by[sid];qp=Path(r['refs']['CP1_input']);zp=Path(r['refs']['CP1'])
  assert sha(qp)==r['output_sha256'][str(qp)]and sha(zp)==r['output_sha256'][str(zp)]
  q=pd.read_parquet(qp)
  sample.append(dict(sid=sid,refs=r['refs'],source_sha256=r['source_sha256'],
      output_sha256={str(qp):sha(qp),str(zp):sha(zp)},
      first_input_day=str(q.index.min().date()),last_input_day=str(q.index.max().date()),
      input_columns=list(q.columns),output_schema=pq.read_schema(zp).names,
      old_input_C_amount_all_positive_finite=bool(q[['close','amount']].gt(0).all().all()and np.isfinite(q[['close','amount']]).all().all()),
      source_domain='Old prepared-v2 signal/events/states and IX/G1; not canonical adjusted_daily_bars SHA11e'))
  for day in ['2022-01-24','2024-09-24','2026-01-15']:
   old=q.loc[pd.Timestamp(day)];new=feature.loc[(sid,day)]
   examples.append(dict(sid=sid,day=day,old_CP_input_close=float(old.close),canonical_close=float(new.current_close_qfq),
       old_CP_input_amount=float(old.amount),canonical_amount_native=float(new.current_amount_passthrough),
       close_values_identical=float(old.close)==float(new.current_close_qfq),
       amount_values_identical=float(old.amount)==float(new.current_amount_passthrough)))
 pd.DataFrame(examples).to_csv(HERE/'OLD_VS_CANONICAL_INPUT_EXAMPLES.csv',index=False)
 snapshots=[]
 for p in [ENTRY/'full_local_signal_two_dates_v1/2022-01-24/signals/ALL_SIGNALS.parquet',
           ENTRY/'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet',
           ENTRY/'full_local_signal_two_dates_v1/2026-01-15/signals/ALL_SIGNALS.parquet']:
  names=pq.read_schema(p).names
  snapshots.append(dict(path=str(p),sha256=sha(p),CP_columns=[n for n in names if n.lower().startswith('cp')or n in ['receipt','candidate','P_before','P_after']]))
 save('EXISTING_CP_CACHE_PROVENANCE.json',dict(stock_manifest_path=str(MANIFEST),stock_manifest_sha256=sha(MANIFEST),stocks=len(manifest),
     manifest_source_paths_referencing_canonical_adjusted_daily_bars=sum(any('adjusted_daily_bars'in p for p in r['source_sha256'])for r in manifest),
     audited_old_CP_cache_samples=sample,current_canonical_stock_snapshots=snapshots,
     scope='Bounded review of original1709 CP manifest, three exact old input/output artifacts and current three full canonical stock snapshots. Not an exhaustive negative claim about every workspace file.',
     no_same_canonical_historical_CP_output_identified_in_this_scope=True,
     old_prepared_outputs_not_claimed_reproduction_on_canonical=True))
 save('CP_INTERFACE.json',dict(function_path=str(CP),source_sha256=sha(CP),function='calculate(f,price_only=False)',
    inputs_required=['daily unique increasing DatetimeIndex','close positive finite','amount positive finite','segment_id explicit contiguous','e0_valid explicit Boolean','e0_down explicit Boolean'],
    stock_input_binding=dict(e0_valid='original G1_I i_target, not e0_target',e0_down='original numeric event == -1',
       i_floor='original G1_I i_floor; optional to calculate receipts, copied to output e0_floor and used in per-start projection'),
    account_inputs_required=False,public_receipt_and_candidate_same_for_flat_or_held=True,
    actual_position_protection_P_publicly_determined=False,
    constants=dict(A='sqrt(5)',K='sqrt(21)',S_MIN='log1p(.001)',EPS='fixed gamma4 binary64',
       scale='prior63 absolute log-return median *1.4826, minimum1e-8; CP scale floor S_MIN',
       amount_reference='prior21 median excluding today',m='1+.5*abs(tanh(r/s))*tanh(log(amount/B))'),
    candidate='close*exp(-sqrt(21)*used_frozen_scale), only when receipt',
    invalid_input_behavior='Original input builder blocks on nonpositive/nonfinite close/amount; no CP-specific drop/fill/resegmentation',
    cost_scope='Existing35–45min estimate covers stock_signal E0/B5/G1/I only, excludes CP, excludes CP trace and per-position project',
    new_model_calls=0,new_accounts=0))
 specs=[(CP,[(1,72)]),(RR/'continuous-protection-lines-20261028/code/common.py',[(17,24)]),
   (R29/'native-I-cache-interface-20261031/cache.py',[(16,35)]),
   (R29/'case-stock-cp1-warmup-20261031/generate.py',[(23,28),(41,47)]),
   (R29/'universe-cp1-inputs-20261031/prepare.py',[(20,45)]),
   (R29/'cp1-evidence-trace-20261031/trace.py',[(30,58)]),
   (R29/'case-stage-ledger-20261031/v3/joint_v3.py',[(223,240),(243,255)]),
   (ENTRY/'selection_qualification_closeout_v1/eligibility_source/stock_signal.py',[(18,55)])]
 excerpts=[];sources=[]
 for p,ranges in specs:
  text=p.read_text().splitlines();sources.append(dict(path=str(p),sha256=sha(p)));excerpts.append(str(p)+'\nSHA256 '+sha(p))
  for lo,hi in ranges:excerpts.append('\n'.join(f'{i:5d} {text[i-1]}'for i in range(lo,min(hi,len(text))+1)))
 (HERE/'SOURCE_EXCERPTS.txt').write_text('\n\n'.join(excerpts)+'\n');save('SOURCE_IDENTITY.json',sources)
 print(json.dumps(dict(cp_source_sha256=sha(CP),old_manifest_stocks=len(manifest),sample_old_vs_new_close_all_different=all(not r['close_values_identical']for r in examples),new_model_calls=0),ensure_ascii=False))

if __name__=='__main__':main()
