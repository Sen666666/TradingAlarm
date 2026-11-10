"""Publish explicit denominators, clipped as-of waiting metadata and fixed focus views."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;B=O.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 e=pd.read_parquet(O/'STOCK_CANONICAL_EVENTS.parquet');i=pd.read_parquet(O/'INDUSTRY_DAILY_CONTEXTS.parquet');w=pd.read_parquet(O/'STOCK_CONTEXT_WAIT.parquet');l=pd.read_parquet(O/'EXISTING_LABEL_JOIN.parquet')
 sources={};cat=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json');sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
 s=read(O/'COVERAGE_SUMMARY.json');ls=read(O/'EXISTING_LABEL_SUMMARY.json');smap={(x['case'],x['cohort']):x for x in s};lm={(x['case'],x['cohort'],x['horizon']):x for x in ls}
 # Raw historical-source metadata retains the full source end date, but the published waiting view must be as-of the fixed case end.
 ends=w.case.map({'2022':'2022-12-30','2023':'2023-12-29','2026':'2026-06-30'});outside=w.context_failure_day.notna() & w.context_failure_day.gt(ends)
 asof=w.copy();asof.loc[outside,['context_failure_day','context_failure_reason']]=None
 stock={(r.case,r.sid,r.day):r.STOCK for r in e.itertuples(index=False)}
 asof['first_stock_qualified']=[stock[r.case,r.sid,r.first_fresh] for r in asof.itertuples(index=False)]
 assert asof[asof.cohort.ne('RAW')].first_stock_qualified.all()
 asof.to_parquet(O/'STOCK_CONTEXT_WAIT_ASOF.parquet',index=False)
 save('WAIT_METADATA_ASOF_AUDIT.json',dict(raw_wait_sha256=sha(O/'STOCK_CONTEXT_WAIT.parquet'),asof_wait_sha256=sha(O/'STOCK_CONTEXT_WAIT_ASOF.parquet'),
  full_source_failure_dates_after_case_end_redacted=int(outside.sum()),outcome_and_wait_values_unchanged=True,
  RAW_not_stock_qualified_firsts=int((asof.cohort.eq('RAW')&~asof.first_stock_qualified).sum()),
  note='Use ASOF file. RAW is receipt coverage only; waiting from an unqualified RAW first is descriptive, not a valid risk opportunity. All STOCK/OLD_Q/F1 firsts are stock-qualified.'))
 # Full node and roster coverage includes nodes/stocks with zero opportunities.
 node=[]
 for n in cat:
  if n['domain']!='NATIVE1709':continue
  for case in ['2022','2023','2026']:
   x=e[e.case.eq(case)&e.sector.eq(n['sector'])];ic=i[i.case.eq(case)&i.sector.eq(n['sector'])]
   node.append(dict(case=case,sector=n['sector'],industry=n['name'],fixed_identities=n['fixed_identities'],source_roster=n['source_roster'],
    market_observations=len(ic),advance_industry_days=int(ic.advance.sum()),permit_industry_days=int(ic.permit.sum()),mature_permit_days=int((ic.mature&ic.permit).sum()),
    unknown_breadth_days=int(ic.breadth.isna().sum()),unknown_F1_days=int(ic.unknown.map(len).gt(0).sum()),
    ready_m_min=ic.ready_m.min(),ready_m_max=ic.ready_m.max(),daily_input=n['input_file'],frozen_daily_result=n['daily_result_path'],
    cohorts={co:dict(fresh=int(x[co].sum()),kept=int((x[co]&x.F1_advance).sum())) for co in ['RAW','STOCK','OLD_Q','F1_PERMIT','F1_MATURE']}))
 save('ALL_NODES_COVERAGE.json',node)
 meta=read(W/'g-s-historical-native-nextsession-20261101/inputs/2025_26/metadata.json')
 roster=[]
 for rec in sm:
  sid=rec['symbol'];x=e[e.sid.eq(sid)]
  roster.append(dict(sid=sid,name=meta[sid]['name'],sector=meta[sid]['sector'],source_status=rec['status'],source_facts=rec['refs']['facts'],
    canonical_by_case=x.groupby('case').size().to_dict(),qualified_by_case=x[x.STOCK].groupby('case').size().to_dict()))
 save('ALL_1709_ROSTER_COVERAGE.json',roster)
 # Exact old snapshot reconciliation; do not edit that old package or repeat the NaN identity test.
 oldp=B/'g-s-static-capital-competition-v1/2026-05-07-ALL1709_DISPOSITIONS.json';old=read(oldp);sources[str(oldp)]=sha(oldp)
 prevp=B/'industry-evidence-ranking-readonly-v1/LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet';prev=pd.read_parquet(prevp);sources[str(prevp)]=sha(prevp)
 oldids={x['sid'] for x in old if x.get('fresh_use')};now=e[e.day.eq('2026-05-07')&e.F1_MATURE];newids=set(now.sid)
 assert oldids<=newids and newids-oldids=={'300184.SZ'} and int(prev[prev.day.eq('2026-05-07')].local_expansion_stock_opportunities.sum())==62
 save('MAY7_CHECKPOINT_RECONCILIATION.json',dict(old_snapshot_fresh=len(oldids),old_snapshot_same_day_advance=int(now[now.sid.isin(oldids)].F1_advance.sum()),
  full_domain_fresh=len(now),full_domain_same_day_advance=int(now.F1_advance.sum()),old_only=sorted(oldids-newids),new_only=sorted(newids-oldids),
  row=now[now.sid.isin(newids-oldids)].to_dict('records'),
  cause='Old static sector_states used pending_failure_at is None. URFI881123 column has NaN for absent pending failure. The existing later full-industry cached view already uses pd.isna and counts this valid ACTIVE/mature/permit stock.',
  frozen_F1_and_old_outputs_unchanged=True))
 conclusion=[]
 for case in ['2022','2023','2026']:
  for co in ['OLD_Q','F1_PERMIT','F1_MATURE']:
   z=smap[case,co];zz=[lm[case,co,h] for h in [21,63]]
   conclusion.append(dict(case=case,cohort=co,fresh=z['fresh'],kept=z['kept'],excluded=z['excluded'],kept_fraction=z['kept_fraction'],
    stocks=z['stocks'],sectors=z['sectors'],stock_contexts=z['stock_contexts'],no_live_F1_context_events=z['contextless_events'],
    waiting=z['waiting_outcomes'],left_inherited_contexts=z['left_inherited_contexts'],wait_distribution=z['continuously_valid_wait'],
    tail=[dict(horizon=a['horizon'],labelled=a['labels_available'],mother=a['all_fresh'],tail_kept=a['kept_existing_tail_events'],tail_total=a['total_existing_tail_events'],
      tail_stocks_kept=a['kept_tail_stocks'],tail_stocks_total=a['tail_stocks']) for a in zz]))
 save('CONCLUSION_TABLE.json',conclusion)
 focus=[]
 for name,kind,code in [('新易盛','stock','300502.SZ'),('中际旭创','stock','300308.SZ'),('严格半导体','sector','URFI881121'),('电子化学品','sector','URFI881172')]:
  for case in ['2022','2023','2026']:
   mask=e.sid.eq(code) if kind=='stock' else e.sector.eq(code);x=e[e.case.eq(case)&mask]
   for co in ['OLD_Q','F1_PERMIT','F1_MATURE']:
    a=x[x[co]];ww=asof[asof.case.eq(case)&asof.cohort.eq(co)&(asof.sid.eq(code) if kind=='stock' else asof.sector.eq(code))]
    focus.append(dict(case=case,focus=name,kind=kind,code=code,cohort=co,fresh=len(a),kept=int(a.F1_advance.sum()),stocks=a.sid.nunique(),
      waits=ww.to_dict('records') if kind=='stock' else None,waiting_outcomes=ww.outcome.value_counts().to_dict(),contexts=len(ww),
      label_coverage={str(h):dict(available=len(l[l.case.eq(case)&l[co]&l.horizon.eq(h)&(l.sid.eq(code) if kind=='stock' else l.sector.eq(code))])) for h in [21,63]}))
 save('FIXED_FOCUS_COVERAGE.json',focus)
 # These are additional views of the existing labels, not new indicators or selected best cases.
 lab=[]
 for case in ['2022','2026']:
  for co in ['OLD_Q','F1_PERMIT','F1_MATURE']:
   for sec in ['ALL','URFI881121','URFI881172']:
    for h in [21,63]:
     x=l[l.case.eq(case)&l[co]&l.horizon.eq(h)&l.valid.eq(True)];x=x if sec=='ALL' else x[x.sector.eq(sec)]
     for keep in [True,False]:
      a=x[x.F1_advance.eq(keep)];tail=a[a.right_tail_MFE30.eq(True)]
      lab.append(dict(case=case,cohort=co,sector=sec,horizon=h,kept=keep,valid_label_events=len(a),stocks=a.sid.nunique(),
       MFE30=len(tail),MFE30_negative_endpoint=int(tail.return_pct.lt(0).sum()),negative_endpoints=int(a.return_pct.lt(0).sum()),
       endpoint_mean=a.return_pct.mean(),endpoint_median=a.return_pct.median(),endpoint_p10=a.return_pct.quantile(.1),endpoint_p90=a.return_pct.quantile(.9)))
 save('EXISTING_LABEL_SECTOR_VIEWS.json',lab)
 save('ADDITIONAL_SOURCE_SHA256.json',sources)
 print('VIEWS_DONE',len(node),'all-node case rows;',len(roster),'stock roster rows; future wait metadata clipped',int(outside.sum()))
if __name__=='__main__':main()
