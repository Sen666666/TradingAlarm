"""Pure saved-output/source audit. No algorithm, feature assembly, Account or Runner import."""
from pathlib import Path
from collections import Counter
import ast,hashlib,json,math
import numpy as np
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');P=O.parent/'risk_constraints/volume_feature_fixtures_v1';V=P/'verification_fix_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def exact(a,b):pd.testing.assert_frame_equal(a,b,check_exact=True,check_dtype=False,check_names=False,check_freq=False)
def same(a,b):pd.testing.assert_series_equal(a,b,check_exact=True,check_dtype=False,check_names=False,check_freq=False)
f=read(P/'EXECUTION_FREEZE.json');v=read(V/'EXECUTION_FREEZE.json');done=read(V/'COMPLETED.json');failure=read(P/'FAILED.json')
assert f['fixtures']==v['fixtures']and f['series']==v['series'];assert done['passed']and done['account_events']==done['economic_outputs']==0
for ff in [f,v]:
 for p,h in ff['sources'].items():assert sha(p)==h,('source',p)
assert done['source_freeze_sha256']==sha(V/'EXECUTION_FREEZE.json')
assert failure['wall_seconds']+v['remaining_compute_budget_seconds']==180
assert failure['wall_seconds']+done['wall_seconds']<180
# Mathematical functions unchanged across the correction; only assertions inside assemble differ.
def ast_body(p,name):
 n=next(z for z in ast.parse(Path(p).read_text()).body if isinstance(z,ast.FunctionDef)and z.name==name)
 class RemoveComparisonAssertions(ast.NodeTransformer):
  def visit_Expr(self,n):
   if isinstance(n.value,ast.Call)and isinstance(n.value.func,ast.Attribute)and n.value.func.attr in ('assert_equal','assert_array_equal'):return None
   return n
 return ast.dump(RemoveComparisonAssertions().visit(n),include_attributes=False)
old=O.parent/'risk_constraints/run_volume_fixture_once.py';new=O.parent/'risk_constraints/run_volume_fixture_verification_fix_v2.py'
for name in ['assemble','score_function']:assert ast_body(old,name)==ast_body(new,name)
records={x['sid']:x for x in read(V/'DIFFERENCES.json')};out=[];examples=[];assets={}
for fixture in f['fixtures']:
 for stock,sid in [(True,fixture['sid']),(False,fixture['sector'])]:
  real={k:pd.read_parquet(P/(sid+'_REAL')/(k+'.parquet'))for k in ['facts','q','CP1','PVR','evidence']}
  neu={k:pd.read_parquet(V/(sid+'_NEUTRAL')/(k+'.parquet'))for k in real}
  for folder in [P/(sid+'_REAL'),V/(sid+'_NEUTRAL')]:
   for z in folder.glob('*.parquet'):assets[str(z)]=sha(z)
  exact(real['facts'][['close','segment_id','factor','raw_close']],neu['facts'][['close','segment_id','factor','raw_close']]);same(real['evidence'].ready,neu['evidence'].ready)
  same(real['q'].amount,neu['q'].amount);same(neu['q'].e0_valid,neu['facts']['i_target'if stock else'e0_target'].astype(bool));same(neu['q'].e0_down,neu['evidence'].event.eq(-1));same(neu['CP1'].e0_valid,neu['q'].e0_valid)
  same(neu['CP1'].e0_floor,neu['facts']['i_floor'if stock else'e0_floor'])
  a=neu['evidence'];same(a.strength_qeff,a.strength_q)
  for c in ['r','scale','u']:same(real['PVR'][c],neu['PVR'][c])
  same(neu['PVR'].e,neu['PVR'].u)
  weights=.9**np.arange(20,-1,-1);weights/=weights.sum();ee=neu['PVR'].u.rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
  expected_score=50+50*np.tanh(2*ee)
  E_error=float((neu['PVR'].E-ee).abs().max());score_error=float((neu['PVR'].score-expected_score).abs().max())
  np.testing.assert_allclose(neu['PVR'].E,ee,rtol=0,atol=8*np.finfo(float).eps,equal_nan=True);np.testing.assert_allclose(neu['PVR'].score,expected_score,rtol=0,atol=800*np.finfo(float).eps,equal_nan=True)
  # Independent price-only credit amount invariant on saved states. Uses saved transitions, not recomputing a state machine.
  previous=0.;credit_rows=0
  for z in neu['CP1'].itertuples():
   reason=z.reset_reason if not pd.isna(z.reset_reason) else None
   expected=0. if reason in ['unprepared','E0_invalid','start','E0_down_reset','lower_anchor']else math.fsum((previous,z.delta_frontier))
   assert z.credit==expected,(sid,z.Index,z.credit,expected)
   if z.receipt:
    assert z.delta_frontier>0 and z.next_credit==0 and z.candidate==float(neu['q'].loc[z.Index,'close'])*math.exp(-math.sqrt(21)*z.scale)
   previous=z.next_credit;credit_rows+=1
  report=dict(sid=sid,role='stock'if stock else'industry',rows=len(neu['facts']),saved_CP1_credit_rows_exact=credit_rows,independent_PVR_formula_maxabs_error=dict(E=E_error,score=score_error),differences={})
  pairs=[('E0target',real['facts'].e0_target,neu['facts'].e0_target),('CP1receipt',real['CP1'].receipt,neu['CP1'].receipt)]
  if stock:pairs += [('Itarget',real['facts'].i_target,neu['facts'].i_target),('Ibuy',real['facts'].i_buy,neu['facts'].i_buy),('G1grade',real['facts'].g_grade,neu['facts'].g_grade)]
  for label,ar,an in pairs:
   mask=ar.notna()&an.notna()&ar.ne(an);days=[str(t.date())for t in ar.index[mask]]
   assert len(days)==records[sid]['differences'][label]['changed_observations']and days==records[sid]['differences'][label]['dates']
   report['differences'][label]=dict(changed_observations=len(days),real_higher=int((ar.gt(an)&mask).sum()),neutral_higher=int((ar.lt(an)&mask).sum()))if label=='G1grade'else dict(changed_observations=len(days),real_only=int((ar.eq(1)&an.eq(0)).sum()),neutral_only=int((ar.eq(0)&an.eq(1)).sum()))
  # First chronological mechanics discrepancy per fixed fixture; no performance selection or forward outcomes.
  if stock:
   for label,ar,an in pairs:
    if label not in ['Ibuy','CP1receipt']:continue
    mask=ar.notna()&an.notna()&ar.ne(an)
    if mask.any():
     dt=ar.index[mask][0];row=dict(sid=sid,first_difference_kind=label,day=str(dt.date()),adjusted_close=float(neu['facts'].loc[dt,'close']))
     for arm,z in [('real',real),('neutral',neu)]:
      row[arm]=dict(event=float(z['evidence'].loc[dt,'event']),E0_target=float(z['facts'].loc[dt,'e0_target']),I_target=float(z['facts'].loc[dt,'i_target']),I_buy=bool(z['facts'].loc[dt,'i_buy']),G1_grade=None if pd.isna(z['facts'].loc[dt,'g_grade'])else float(z['facts'].loc[dt,'g_grade']),qeff=None if pd.isna(z['evidence'].loc[dt,'strength_qeff'])else float(z['evidence'].loc[dt,'strength_qeff']),CP1_receipt=bool(z['CP1'].loc[dt,'receipt']),CP1_credit=float(z['CP1'].loc[dt,'credit']),CP1_delta=float(z['CP1'].loc[dt,'delta_frontier']),CP1_disp=None if pd.isna(z['CP1'].loc[dt,'displacement'])else float(z['CP1'].loc[dt,'displacement']))
     examples.append(row)
  out.append(report)
prefix=read(V/'PHYSICAL_PREFIXES.json');expected={(s,c)for s in f['series']for c in ['2021-12-31','2024-09-23','2026-06-30']};assert {(x['sid'],x['cut'])for x in prefix}==expected and len(prefix)==18 and all(x['all_outputs_exact']for x in prefix)
act=read(V/'ACT_BOUNDARY.json');assert not act['ACT_features_computed']and act['no_three_stock_toy_breadth']
x=dict(status='PASS_WITH_SCOPE_THREE_FIXED_PURE_FEATURE_MECHANICAL_CONTROL_ONLY',sources_checked_original=len(f['sources']),sources_checked_continuation=len(v['sources']),total_wall_seconds=failure['wall_seconds']+done['wall_seconds'],series=out,first_chronological_mechanics_examples=examples,
 verdict='Thin existing pure-function assembly works in these three fixed stocks and their three industries. Neutral changes E0/I/CP1 qualification, not just display; sign or count of changes does not establish better entries, stock returns, or volume financial increment.',
 observed_scope={'true_cold':'6 fullwarm facts/CP1/cache exact independently read in VOLUME_FIXTURE_FIRST_PASS_AUDIT; PVR only55 existing8field dates and2904 score dates, no invented fullwarm reference.', 'neutral_effective_hooks':'Independent saved qeff=q, e=u, weightedE/score and everyCP1 credit increment=frontier increment checked; inputCP1 validity/down bound to rebuiltneutral I/E0/event. Originalamount/masks/prices common.', 'physical_prefix':'Producer executed NEUTRAL6x3 all5output tables exact; reviewer checked frozen comparator/source and complete receipt, did not repeat algorithm calculation or independently recreate discardedphysical tables. REAL was not physicallyrerun in thisattempt.', 'ACT':'Not computed. No full1709signal-chain neutral control or economic claim.'},
 remains_unverified=['Full1709/90 neutral ACT and cross-sectional opportunity/rank/eligibility interactions.', 'Whether changed signals improve wrong chase/reentry versus hurt durable early trends across complete domains and frozenwinnercontrols.', 'Causal strategy-account PnL, fees/capital/resources/portfolio feedback and out-of-sample benefit.'],
 attempt_scope={'v1':'Preserved17.143s failure after6REAL verified; firstneutral was computed but not saved. Series comparator typeerror, not numerical mismatch.', 'v2':'Only comparison/controller fix and6REAL reuse;6neutral+18physicalprefix,51.877s. No retries beyond explicitrootgrant, no financial events.'},
 reviewer_arithmetic_scope='Independent E/score weightedwindow recomputation differs by machine rounding from original rolling-dot memory layout; checked explicit8eps E/800eps score absolute bounds and reports actual maxerrors. First reviewer strictbit E assertion corrected without any producer mutation or feature rerun. All shared price/u/e/qeff and CP1 credit tests remain exact.',
 reviewer_account_events=0,inputs={str(p):sha(p)for p in [P/'EXECUTION_FREEZE.json',V/'EXECUTION_FREEZE.json',P/'FAILED.json',V/'COMPLETED.json',V/'PHYSICAL_PREFIXES.json',V/'DIFFERENCES.json',V/'ACT_BOUNDARY.json',old,new,Path(__file__)]},feature_artifact_SHA256=assets)
(O/'VOLUME_THREE_FIXTURE_COMPLETED_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],seconds=x['total_wall_seconds'],series=x['series']),ensure_ascii=False))
