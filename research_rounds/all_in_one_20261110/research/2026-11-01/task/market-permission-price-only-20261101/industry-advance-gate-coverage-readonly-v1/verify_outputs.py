"""Read-only verification of complete saved joins and original label values."""
from pathlib import Path
import gzip,hashlib,json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;B=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def main():
 tests=[]
 def check(n,b,detail=None):
  tests.append(dict(check=n,passed=bool(b),detail=detail));assert b,(n,detail)
 e=pd.read_parquet(O/'STOCK_CANONICAL_EVENTS.parquet');i=pd.read_parquet(O/'INDUSTRY_DAILY_CONTEXTS.parquet');d=pd.read_parquet(O/'DAILY_COVERAGE.parquet');w=pd.read_parquet(O/'STOCK_CONTEXT_WAIT.parquet');l=pd.read_parquet(O/'EXISTING_LABEL_JOIN.parquet')
 coverage=read(O/'SOURCE_COVERAGE.json');summary=read(O/'COVERAGE_SUMMARY.json');src=read(O/'SOURCE_SHA256.json');freeze=read(O/'FREEZE.json')
 check('all source hashes unchanged',all(sha(p)==v for p,v in src.items()),len(src))
 check('protocol and calculation source remain frozen',sha(O/'PROTOCOL.txt')==freeze['protocol_sha256'] and sha(O/'analyze_coverage.py')==freeze['script_sha256'])
 check('all 524 closes x all 90 sectors retained',len(i)==47160 and not i.duplicated(['case','day','sector']).any() and i.groupby(['case','day']).size().eq(90).all())
 check('all canonical event keys and stock-close keys unique',not e.duplicated(['case','sid','day','receipt']).any() and not e.duplicated(['case','sid','day']).any())
 check('original 2022 and 2023 canonical counts',coverage['canonical_events_by_case']['2022']==16932 and coverage['canonical_events_by_case']['2023']==18781,coverage['canonical_events_by_case'])
 check('original 2022 old mother exact count',int(e[e.case=='2022'].OLD_Q.sum())==10580)
 j=e.merge(i,on=['case','day','sector'],how='left',validate='many_to_one',suffixes=('_stock','_industry'))
 check('all stock fresh join exact original confirmation close',len(j)==len(e) and j.industry_industry.notna().all())
 check('same-day advance copied without prior-event accumulation',(j.F1_advance==j.advance).all())
 check('permit and maturity copied independently',(j.F1_permit==j.permit).all() and (j.F1_mature==j.mature).all())
 check('complete F1 replacement domain stock qualification intersections',(e.F1_PERMIT==(e.STOCK&e.F1_permit)).all() and (e.F1_MATURE==(e.STOCK&e.F1_permit&e.F1_mature)).all())
 check('no F1 stock permission from unknown/false Q',e[e.F1_PERMIT].stock_Q.eq(True).all() and e[e.F1_PERMIT].quote_above_CP1_and_I.all())
 check('no grant from waiting ended or pending contexts',not e[e.F1_PERMIT].F1_context.isna().any() and e[e.F1_PERMIT].F1_mode.eq('ACTIVE').all())
 for s in summary:
  x=e[(e.case==s['case'])&e[s['cohort']]];dd=d[(d.case==s['case'])&(d.cohort==s['cohort'])]
  check('denominator conservation '+s['case']+'/'+s['cohort'],len(x)==s['fresh']==int(dd.fresh.sum()) and int(x.F1_advance.sum())==s['kept']==int(dd.kept.sum()) and s['fresh']==s['kept']+s['excluded'])
  ww=w[(w.case==s['case'])&(w.cohort==s['cohort'])]
  check('stock-context waiting denominator '+s['case']+'/'+s['cohort'],len(ww)==len(x[x.F1_context.notna()][['sid','F1_context']].drop_duplicates())==sum(s['waiting_outcomes'].values()))
 # First hits are verified by group lookups, with no need to replay market/financial kernels.
 look={}
 for co in freeze['cohorts']:
  for key,g in e[e[co]&e.F1_context.notna()].groupby(['case','sid','F1_context']):look[(co,*key)]=g
 correct=True
 for r in w.itertuples(index=False):
  g=look[r.cohort,r.case,r.sid,r.F1_context];hit=g[g.F1_advance]
  expected=None if hit.empty else hit.day.iloc[0]
  match_ok=pd.isna(r.first_fresh_and_advance) if expected is None else r.first_fresh_and_advance==expected
  correct &= r.first_fresh==g.day.iloc[0] and match_ok
  if r.outcome=='same_close':correct &= r.wait_if_continuously_valid==0
  if r.outcome=='later_hit':correct &= r.wait_if_continuously_valid>0
 check('all stock-context first opportunities and raw first advance matches exact',correct,len(w))
 # Original frozen label payload; labels with invalid reasons remain present.
 old=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/opportunity-quality-ranking-20261031');keys={}
 for c,win in [('2022','2022'),('2026','2025_26')]:
  with gzip.open(old/win/'PRICE_LABELS.jsonl.gz','rt') as f:
   for line in f:
    z=json.loads(line)
    for h in [21,63]:keys[c,z['sid'],z['day'],z['receipt'],h]=z['labels'][str(h)]
 eq=True
 for r in l[l.horizon.notna()].itertuples(index=False):
  z=keys[r.case,r.sid,r.day,r.receipt,int(r.horizon)]
  eq &= r.valid==z['valid']
  for col in ['return_pct','MAE_pct','MFE_pct','right_tail_MFE30','end_day','reason']:
   value=getattr(r,col,None);target=z.get(col)
   eq &= (value==target) if target is not None else (value is None or (not isinstance(value,(str,list)) and pd.isna(value)))
 check('every joined original 21/63 label exact, including original censor reasons',eq,len(l[l.horizon.notna()]))
 check('unlabelled F1-only opportunities and 2023 remain unlabelled',not l[(l.case=='2023')|~l.OLD_Q].horizon.notna().any())
 m=e[(e.day=='2026-05-07')&e.F1_MATURE]
 reconcile=read(O/'MAY7_CHECKPOINT_RECONCILIATION.json')
 check('May7 complete domain and exact old snapshot discrepancy reconciled',len(m)==62 and int(m.F1_advance.sum())==55 and reconcile['old_snapshot_fresh']==61 and reconcile['old_snapshot_same_day_advance']==54 and reconcile['new_only']==['300184.SZ'],reconcile)
 aw=pd.read_parquet(O/'STOCK_CONTEXT_WAIT_ASOF.parquet');end=aw.case.map({'2022':'2022-12-30','2023':'2023-12-29','2026':'2026-06-30'})
 check('published waiting metadata contains no context failure after fixed window',not (aw.context_failure_day.notna()&aw.context_failure_day.gt(end)).any())
 check('as-of clipping changes no wait outcomes or hit dates',aw[w.columns.difference(['context_failure_day','context_failure_reason'])].equals(w[w.columns.difference(['context_failure_day','context_failure_reason'])]))
 check('all qualified waiting firsts pass retained stock conditions',aw[aw.cohort.ne('RAW')].first_stock_qualified.all())
 addsrc=read(O/'ADDITIONAL_SOURCE_SHA256.json');check('additional checkpoint sources unchanged',all(sha(p)==v for p,v in addsrc.items()))
 for cut in ['2022-06-28','2023-03-14','2026-05-07']:
  past=e[e.day<=cut];prefix_i=i[i.day<=cut].set_index(['day','sector']);same=True
  for r in past.itertuples(index=False):
   row=prefix_i.loc[r.day,r.sector];same &= r.F1_advance==row.advance and r.F1_permit==row.permit and r.F1_mature==row.mature
  check('past-only saved-table join '+cut,same,len(past))
 complete=read(O/'COMPLETION.json');check('authorized scope counters zero',all(complete[k]==0 for k in ['new_indicators','F1_runs','account_creates','account_restores','financial_events','orders','downloads','source_mutations']))
 result=dict(passed=all(t['passed'] for t in tests),checks=len(tests),tests=tests,scope='saved input/event/label verification; no financial or strategy execution')
 (O/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('VERIFIED',len(tests),'checks')
if __name__=='__main__':main()
