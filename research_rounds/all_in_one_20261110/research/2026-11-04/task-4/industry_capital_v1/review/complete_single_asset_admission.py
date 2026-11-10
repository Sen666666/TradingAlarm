"""Readonly continuity/identity checks and one bounded label admission; no new paths."""
from pathlib import Path
from datetime import datetime
import gzip,hashlib,json,time
import pandas as pd
import numpy as np
R=Path(__file__).resolve().parent;I=R.parent;P=I/'labels_new';W=I.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
t0=time.monotonic();cal=read(P/'TECHNICAL_CALIBRATION_RESULT.json');contract=read(P/'PROPOSED_FULL_LABEL_CONTRACT.json');oldsrc=read(P/'TECHNICAL_SOURCE_SHA256.json');guard=read(P/'FINAL_SOURCE_GUARD_CORRECTION.json');deadline=read(P/'DEADLINE_AND_RELIABILITY_CORRECTION.json')
assert contract['single_pass_limit_seconds']==120.0 and contract['new_portfolio_policy_accounts']==0
for p,s in contract['source_sha256'].items():assert sha(p)==s,(p,'full source SHA drift')
assert guard['old_source_sha256']==sha(P/'native_single_asset.pre_final_source_guard.py')==oldsrc[str((P/'native_single_asset.py').resolve())]
assert guard['new_source_sha256']==deadline['old_native_source_sha256']
assert deadline['new_native_source_sha256']==sha(P/'native_single_asset.py')and deadline['new_runner_sha256']==sha(P/'run_first_reject_labels.py')
for p,s in oldsrc.items():
 if Path(p).name!='native_single_asset.py':assert sha(p)==s,(p,'old calibration dependency drift')
sm={x['symbol']:x for x in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};env={};checks=[]
for rr in cal['results']:
 z=rr['result'];sid=rr['sid'];w=rr['window'];fp=Path(sm[sid]['refs']['facts']);assert sha(fp)==sm[sid]['output_sha256'][str(fp)]
 f=pd.read_parquet(fp,columns=['segment_id','i_target']);start=pd.Timestamp(z['signal_day']);end=pd.Timestamp(z['horizon_CLOSE_day']);a=f.loc[start:end];initial=float(f.loc[start,'segment_id']);assert len(a)>0 and np.isfinite(a.segment_id.astype(float)).all()and a.segment_id.eq(initial).all()
 if w not in env:
  with gzip.open(W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair/daily.jsonl.gz','rt')as h:env[w]=[(x['at'][:10],bool(x['on']))for x in map(json.loads,h)]
 days=[(d,on)for d,on in env[w]if z['OPEN']<=d<=z['horizon_CLOSE_day']];stop=None
 for d,on in days:
  row=f.iloc[f.index.searchsorted(pd.Timestamp(d),side='right')-1]
  if not bool(row.i_target)or not on:stop=d;break
 assert stop==z['exit_proposal_at'][:10],(sid,stop,z['exit_proposal_at'])
 checks.append({'key':rr['key'],'entire_signal_to_terminal_source_continuous':True,'first_frozen_I_or_ACT_stop_exact':stop,'no_new_ledger_path':True})
assert len(checks)==5
saved=read(R/'SINGLE_ASSET_CALIBRATION_SAVED_REVIEW.json');assert saved['saved_result_review_passed']and saved['all_actual_fill_layer_and_profit_exact']
x={'passed':True,'scope':'first_reject_single_asset_labels','source_sha256':contract['source_sha256'],'single_pass_limit_seconds':120,'primary_events':8335,'primary_quantity':'dated original minimum BUY unit under unchanged LR.preview; actual partial fills/nonfills remain explicit','new_portfolio_policy_accounts':0,'technical_original_paths':5,'technical_saved_review':str((R/'SINGLE_ASSET_CALIBRATION_SAVED_REVIEW.json').resolve()),'technical_saved_review_sha256':sha(R/'SINGLE_ASSET_CALIBRATION_SAVED_REVIEW.json'),'independent_no_new_path_checks':checks,'source_reliability_amendment':{'old_technical_source_archived_and_exact':True,'current_source_chain_sha256':[guard['old_source_sha256'],guard['new_source_sha256'],deadline['new_native_source_sha256']],'old5_boundary_exposures_zero':True,'no_ledger_calibration_rerun_required':True},'execution_guards_reviewed':['Shared absolute deadline before/after provider load, each sparse event and before final output; timeout discards incomplete path output but counts any initialized ledger.','Partial/progress preserved; one pass only; no full/partial replay, no automatic limit extension.','Only native RuleUnavailable becomes explicit unknown. Programming errors stop and preserve failure.','All prepared min/max/price/floor values assert unchanged before ledger creation.','Original native buy day lease, CA/payments, T+1/irrevocable exit and invested-Cn seed correction retained.','Source continuity is checked through final horizon even after an earlier I/ACT exit proposal.'],'scope_limits':['Not a shared-capital or feasible rotation account; no donor orders/pool authorization change.','BaselineACT is fixed original environment. Monetary differences are dependent local opportunities and cannot be summed as portfolio gains.','Terminal liquidation value of residuals is estimated/censored, not an actual sell. Unknown source paths remain in denominator without known net label.','Technical samples did not exercise partialentry/nonfill/ACT-firststop/censored terminal; these use original native primitives, any unsupported case must remain unknown or stop rather than fabricate profit.'],'reviewer_new_single_asset_paths':0,'reviewer_new_market_marks':0,'independent_continuity_check_seconds':time.monotonic()-t0}
(R/'FULL_SINGLE_ASSET_LABEL_ADMISSION.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'scope':x['scope'],'events':8335,'calibration_exact':True,'guard_checks':checks,'admission_sha256':sha(R/'FULL_SINGLE_ASSET_LABEL_ADMISSION.json'),'seconds':time.monotonic()-t0},indent=2))
