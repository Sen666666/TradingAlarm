"""One read-only cached-input join. No strategy/account/indicator imports."""
from pathlib import Path
from datetime import date,datetime
from typing import Mapping
from collections import defaultdict,Counter
import ast,gzip,hashlib,json,math,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;B=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
U=W/'universe-cp1-inputs-20261031';N=W/'g-s-historical-native-nextsession-20261101'
OLD=W/'opportunity-quality-ranking-20261031'
CASES={'2022':('2022-01-04','2022-12-30'),'2023':('2023-01-03','2023-12-29'),'2026':('2026-04-30','2026-06-30')}
COHORTS=['RAW','STOCK','OLD_Q','F1_PERMIT','F1_MATURE']
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p);v=sha(p)
 if str(p) in SRC:assert SRC[str(p)]==v,('source changed',p)
 SRC[str(p)]=v
 if expected:assert v==expected,('declared hash mismatch',p)
 return p
def read(p,expected=None):return json.loads(bind(p,expected).read_text())
def stream(p):
 with gzip.open(bind(p),'rt') as f:
  for line in f:yield json.loads(line)
def frame(p,expected=None,columns=None):return pd.read_parquet(bind(p,expected),columns=columns)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(date,datetime,pd.Timestamp,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def pure_rules():
 p=RR/'rs-h1-execution-20261025/code/market_rules.py';tree=ast.parse(bind(p).read_text())
 names={'RuleUnavailable','day','version_on','market_identity_on'}
 ns={'date':date,'datetime':datetime,'Mapping':Mapping}
 exec(compile(ast.Module(body=[x for x in tree.body if isinstance(x,(ast.ClassDef,ast.FunctionDef)) and x.name in names],type_ignores=[]),str(p)+'::pure_rules','exec'),ns)
 return ns
MR=pure_rules()
def input_legal(sid,day,rules,protocol,meta):
 try:
  rec=meta[sid]['runtime_record']
  if rec.get('unavailable_from') and day>=rec['unavailable_from']:return None
  if any(a['end']<day<b['start'] for a,b in zip(rec.get('segments',[]),rec.get('segments',[])[1:])):return None
  proxy=protocol['approved_proxy_ids'];v=MR['market_identity_on'](rules,sid,day,proxy)
  av=MR['version_on'](rules['availability_versions'].get(sid,[]),day,proxy)
  MR['version_on'](rules['quantity_versions'].get(sid,[]),day,proxy)
  MR['version_on'](rules['fee_versions'].get(v['venue'],[]),day,proxy)
  return av['buy_allowed']
 except MR['RuleUnavailable']:return None

def contexts(node,end):
 """Read saved history from its actual left endpoint, never call F1.step."""
 df=frame(node['daily_result_path']).loc[:end];context=None;count=0;start=None;seq=0;out=[];ends={}
 for day,r in df.iterrows():
  for e in r.events:
   if e.startswith('price_failure') or e=='source_changed_context_ended':
    if context:ends[context]=dict(day=day,reason=e)
    context=None;count=0;start=None
   elif e in ['break_started','repair_restored']:
    assert context is None,(node['node_id'],day,'new context before old ended')
    seq+=1;start=day;context=f"{node['node_id']}:{r.source_segment}:{seq}:{day}";count=0
   elif e=='price_advance':
    assert context is not None,(node['node_id'],day,'advance without context')
    count+=1
  support=r['mode']=='ACTIVE' and pd.isna(r.pending_failure_at)
  assert not support or context is not None
  out.append(dict(day=day,sector=node['sector'],industry=node['name'],F1_context=context,context_started=start,
   mode=r['mode'],status=r.effective_status,permit=bool(r.permit_next_open),support=support,
   mature=bool(support and count>0),advance='price_advance' in r.events,context_advances=count,
   breadth=r.breadth,ready_m=r.ready_m,source_segment=r.source_segment,events=list(r.events),unknown=list(r.unknown)))
 return pd.DataFrame(out),ends

def old_mothers(legacy_states):
 out={}
 for case,win in [('2022','2022'),('2026','2025_26')]:
  a,b=CASES[case];rs=[r for r in stream(OLD/win/'CANDIDATES.jsonl.gz') if a<=r['day']<=b]
  out[case]={(r['sid'],r['day'],r['receipt']):r for r in rs}
 p=W/'recovery-2023-readiness-20261101/runs/Bdiag/pair/opportunities.jsonl.gz';out['2023']={};old_q_status={}
 for r in stream(p):
  if not (r['CP1_id'] and CASES['2023'][0]<=r['day']<=CASES['2023'][1]):continue
  k=r['sid'],r['day'],r['CP1_id'];assert k not in old_q_status;old_q_status[k]=r['mobile_Q']
  st=legacy_states[r['sector']].loc[r['day']]
  if r['mobile_Q'] is True and st.E0_valid and st.stage_name in ['confirmed','expanded'] and st.authorization_usable and pd.notna(st.attempt_id) and st.action!='unknown':
   out['2023'][k]=dict(sid=r['sid'],day=r['day'],receipt=r['CP1_id'],sector=r['sector'],industry_attempt=st.attempt_id,industry_stage=st.stage_name)
 return out,old_q_status

def distribution(values):
 a=np.asarray(values,float)
 return dict(n=len(a),mean=float(a.mean()) if len(a) else None,
   **{n:float(np.quantile(a,q)) if len(a) else None for n,q in [('min',0),('p10',.1),('p25',.25),('median',.5),('p75',.75),('p90',.9),('max',1)]})

def main():
 assert not (O/'COMPLETION.json').exists();started=time.monotonic()
 kernel=bind(B/'v2-frozen/signal_core.py','962275bd41b5c7bbc062a1191780a6b6a9c616f8d3097ea669b602eabbc9ac59')
 contract=bind(B/'v2-frozen/CONTRACT.md','c3914aed1896563253961ea40d6065614a115cef21e13a93e1e74ad71779c54a')
 sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json');cat=[x for x in read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json') if x['domain']=='NATIVE1709']
 assert len(sm)==1709 and len(im)==90 and len(cat)==90
 meta=read(N/'inputs/2025_26/metadata.json');selection=read(N/'inputs/2025_26/selection.json');lines={r['security_id']:r for r in selection['lines']}
 rules=read(N/'inputs/2025_26/rules.json');protocol=read(N/'inputs/2025_26/protocol.json')
 gd=frame(B/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet');cal={c:gd.loc[a:b].index.tolist() for c,(a,b) in CASES.items()}
 assert [len(cal[c]) for c in CASES]==[242,242,40]
 all_days=sorted(set(d for ds in cal.values() for d in ds));all_ts=pd.DatetimeIndex(all_days);pos={c:{d:i for i,d in enumerate(ds)} for c,ds in cal.items()}
 day_case={d:c for c,ds in cal.items() for d in ds}
 legacy={r['series']:frame(r['refs']['state'],r['output_sha256'][r['refs']['state']]).set_index('day') for r in im}
 mothers,q23=old_mothers(legacy)
 manifests={c:read(W/root/'inputs/MANIFEST.json') for c,root in [('2022','2022-normal-reference-20261031'),('2023','recovery-2023-readiness-20261101')]}
 receipts={c:{x['sid']:dict(path=x['output_path'],sha=x['output_sha256']) for x in mp if not x['industry']} for c,mp in manifests.items()}
 receipts['2026']={r['symbol']:dict(path=r['refs']['receipts'],sha=r['output_sha256'][r['refs']['receipts']]) for r in sm}
 for mp in receipts.values():assert len(mp)==1709
 hp=bind('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
 with np.load(hp,allow_pickle=False) as z:
  hi=pd.DatetimeIndex(z['dates']);hj={str(s):j for j,s in enumerate(z['symbols'])};ix=hi.get_indexer(all_ts);assert (ix>=0).all()
  full=z['score'];hs=pd.DataFrame(full[np.ix_(ix,[hj[r['symbol']] for r in sm])],index=all_days,columns=[r['symbol'] for r in sm]);del full
 industry=[];ends={}
 for n in cat:
  cx,en=contexts(n,CASES['2026'][1]);ends.update(en)
  part=cx[cx.day.isin(all_days)].copy();part['case']=part.day.map(day_case);assert len(part)==len(all_days)
  industry.append(part)
 ind=pd.concat(industry,ignore_index=True);assert len(ind)==len(all_days)*90
 ind['global_permit']=ind.day.map(gd.permit_next_open);ind.to_parquet(O/'INDUSTRY_DAILY_CONTEXTS.parquet',index=False)
 ii=ind.set_index(['day','sector']);save('CONTEXT_ENDS.json',ends)
 save('FREEZE.json',dict(protocol_sha256=sha(O/'PROTOCOL.txt'),script_sha256=sha(__file__),before_stock_coverage=True,
  cases=CASES,observations={c:len(ds) for c,ds in cal.items()},stocks=1709,sectors=90,kernel_sha256=sha(kernel),contract_sha256=sha(contract),cohorts=COHORTS,
  label_source='existing PRICE_LABELS only, no 2023 same-contract labels',no_new_indicators=True,no_accounts=True))
 print('READINESS_FROZEN',len(ind),'industry observations',flush=True)
 rows=[];validity={};source_status=Counter()
 for number,rec in enumerate(sm,1):
  sid=rec['symbol'];sec=meta[sid]['sector'];line=lines[sid]
  ff=frame(rec['refs']['facts'],rec['output_sha256'][rec['refs']['facts']]);cp=frame(rec['refs']['CP1'],rec['output_sha256'][rec['refs']['CP1']]);source_status[rec['status']]+=1
  # Retain source/I validity daily solely to stop an alleged waiting episode at known failure/unknown.
  for c,ds in cal.items():
   f=ff.reindex(pd.DatetimeIndex(ds));status=[]
   for day,fr in zip(ds,f.itertuples(index=False)):
    if pd.isna(fr.e0_ready) or pd.isna(fr.i_target) or pd.isna(fr.segment_id):st='unknown'
    elif not bool(fr.e0_ready) or not bool(fr.i_target):st='invalid'
    else:st='valid'
    status.append((day,st,None if pd.isna(fr.segment_id) else fr.segment_id))
   validity[c,sid]=status
  ff_lookup={str(d.date()):r for d,r in zip(ff.index,ff.itertuples(index=False))};cp_lookup={str(d.date()):r for d,r in zip(cp.index,cp.itertuples(index=False))}
  for c,mp in receipts.items():
   rr=read(mp[sid]['path'],mp[sid]['sha']);a,b=CASES[c]
   for ca in rr:
    day=ca['confirmed_day']
    if not a<=day<=b:continue
    assert day in day_case and day_case[day]==c
    k=sid,day,ca['receipt_id'];fr=ff_lookup.get(day);cr=cp_lookup.get(day);hh=bool(np.isfinite(hs.loc[day,sid]));av=input_legal(sid,day,rules,protocol,meta)
    ready=None if fr is None or pd.isna(fr.e0_ready) else bool(fr.e0_ready)
    up=None if fr is None or ready is not True or pd.isna(fr.i_target) else bool(fr.i_target)
    checks=dict(common_ready=ready,buy_allowed=None if av is None else bool(av),cap_above_10bn=None if line['company_cap_cny'] is None else line['company_cap_cny']>1e10,
     stock_up=up,issuer_known=True if line['issuer_id'] else None,sector_known=True if line['sector_id']==sec else None,stock_rs_ready_fresh=True if hh else None,
     current_stock=bool(line['current_stock']))
    unknown=[n for n,v in checks.items() if v is None];failed=[n for n,v in checks.items() if v is False];q=None if unknown else not failed
    quote=bool(q is True and fr and np.isfinite(fr.raw_close) and fr.raw_close>0 and np.isfinite(fr.factor) and fr.factor>0 and np.isfinite(fr.i_floor) and fr.raw_close>fr.i_floor/fr.factor)
    numeric=bool(cr and pd.notna(cr.receipt) and bool(cr.receipt) and np.isfinite(cr.candidate))
    assert numeric and float(cr.candidate)==ca['original_candidate'],(c,sid,day,'canonical numeric differs')
    protected=bool(quote and fr.raw_close>max(fr.i_floor,cr.candidate)/fr.factor)
    stock=bool(protected and not ca['trace_unknown']);r=ii.loc[day,sec]
    rows.append(dict(case=c,day=day,market_observation=pos[c][day],sid=sid,name=meta[sid]['name'],sector=sec,industry=r.industry,receipt=ca['receipt_id'],
     stock_source_segment=None if fr is None or pd.isna(fr.segment_id) else fr.segment_id,canonical_E0_episode=ca['original_E0_episode_id'],
     canonical_unknown=list(ca['trace_unknown']),stock_Q=q,stock_Q_unknown=unknown,stock_Q_false=failed,quote_above_I_floor=quote,quote_above_CP1_and_I=protected,
     RAW=True,STOCK=stock,OLD_Q=k in mothers[c],F1_PERMIT=bool(stock and r.permit),F1_MATURE=bool(stock and r.permit and r.mature),
     F1_context=r.F1_context,context_started=r.context_started,F1_mode=r['mode'],F1_permit=bool(r.permit),F1_mature=bool(r.mature),F1_advance=bool(r.advance),
     breadth=r.breadth,ready_m=r.ready_m,F1_unknown=list(r.unknown),global_permit=bool(r.global_permit)))
  if number%400==0:print('CANONICAL_STOCKS_JOINED',number,round(time.monotonic()-started,2),flush=True)
 ev=pd.DataFrame(rows).sort_values(['case','day','sid','receipt']).reset_index(drop=True)
 assert not ev.duplicated(['case','sid','day','receipt']).any()
 assert not ev.duplicated(['case','sid','day']).any()
 for c in CASES:
  part=ev[ev.case==c];ks={(r.sid,r.day,r.receipt) for r in part.itertuples(index=False)}
  assert set(mothers[c])<=ks,(c,'old reference outside canonical domain')
  assert int(part.OLD_Q.sum())==len(mothers[c])
  if c=='2023':assert set(q23)==ks,('2023 full original opportunities vs canonical mismatch',len(q23),len(ks))
 ev.to_parquet(O/'STOCK_CANONICAL_EVENTS.parquet',index=False);before_labels=sha(O/'STOCK_CANONICAL_EVENTS.parquet')
 daily=[];summary=[];wait=[]
 for c,ds in cal.items():
  part=ev[ev.case==c]
  for co in COHORTS:
   base=part[part[co]]
   daily_co=[]
   for day in ds:
    e=base[base.day==day];ic=ind[(ind.case==c)&(ind.day==day)];keep=e[e.F1_advance]
    daily_co.append(dict(case=c,cohort=co,day=day,all_industries=90,industries_advance=int(ic.advance.sum()),industries_permit=int(ic.permit.sum()),industries_mature_permit=int((ic.permit&ic.mature).sum()),
     fresh=len(e),kept=len(keep),excluded=len(e)-len(keep),fresh_stocks=e.sid.nunique(),fresh_industries=e.sector.nunique(),kept_industries=keep.sector.nunique()))
   daily+=daily_co
   for (sid,cx),group in base[base.F1_context.notna()].groupby(['sid','F1_context'],sort=False):
    first=group.iloc[0];match=group[group.F1_advance];hit=None if match.empty else match.iloc[0];end=ends.get(cx)
    # A later requalification is visible but does not revive the original still-valid opportunity.
    subsequent=[(d,st,seg) for d,st,seg in validity[c,sid] if d>first.day]
    bad=next(((d,st,'source_segment_changed' if seg is not None and seg!=first.stock_source_segment else st) for d,st,seg in subsequent if st!='valid' or seg!=first.stock_source_segment),None)
    candidate=[]
    if hit is not None:candidate.append((hit.day,0,'same_close' if hit.day==first.day else 'later_hit'))
    if end and end['day']<=ds[-1]:candidate.append((end['day'],1,'context_failed_before_gate'))
    if bad:candidate.append((bad[0],2,'stock_unknown_before_gate' if bad[1]=='unknown' else 'stock_invalidated_before_gate'))
    # On a source switch even a same-day later receipt is not continuation of the old stock context.
    if bad and bad[2]=='source_segment_changed':candidate=[x for x in candidate if not (x[0]==bad[0] and x[1]==0)]+[(bad[0],-1,'stock_invalidated_before_gate')]
    event=min(candidate) if candidate else (ds[-1],3,'right_censored_open_context')
    wait.append(dict(case=c,cohort=co,sid=sid,name=first['name'],sector=first.sector,industry=first.industry,F1_context=cx,context_started=first.context_started,
     left_inherited=first.context_started<ds[0],first_fresh=first.day,first_fresh_and_advance=None if hit is None else hit.day,
     raw_next_hit_wait=None if hit is None else pos[c][hit.day]-pos[c][first.day],outcome=event[2],outcome_day=event[0],
     wait_if_continuously_valid=pos[c][event[0]]-pos[c][first.day] if event[2] in ['same_close','later_hit'] else None,
     observations_to_outcome=pos[c][event[0]]-pos[c][first.day],context_failure_day=None if end is None else end['day'],
     context_failure_reason=None if end is None else end['reason'],first_stock_nonvalid_day=None if bad is None else bad[0],
     first_stock_nonvalid_reason=None if bad is None else bad[2],fresh_events=len(group),same_day_gate_events=int(group.F1_advance.sum())))
   contextless=base[base.F1_context.isna()]
   summary.append(dict(case=c,cohort=co,market_observations=len(ds),fresh=len(base),stocks=base.sid.nunique(),sectors=base.sector.nunique(),
    days_with_fresh=base.day.nunique(),kept=int(base.F1_advance.sum()),excluded=int((~base.F1_advance).sum()),
    kept_fraction=float(base.F1_advance.mean()) if len(base) else None,contextless_events=len(contextless),
    F1_permit_fresh=int(base.F1_permit.sum()),F1_mature_permit_fresh=int((base.F1_permit&base.F1_mature).sum()),
    global_weak_local_permit=int((base.F1_permit&~base.global_permit).sum())))
 daily=pd.DataFrame(daily);daily.to_parquet(O/'DAILY_COVERAGE.parquet',index=False)
 waits=pd.DataFrame(wait);waits.to_parquet(O/'STOCK_CONTEXT_WAIT.parquet',index=False)
 for s in summary:
  w=waits[(waits.case==s['case'])&(waits.cohort==s['cohort'])];valid=w[w.outcome.isin(['same_close','later_hit'])]
  s.update(stock_contexts=len(w),left_inherited_contexts=int(w.left_inherited.sum()),waiting_outcomes=w.outcome.value_counts().to_dict(),
   continuously_valid_wait=distribution(valid.wait_if_continuously_valid),
   raw_eventual_hit_even_after_stock_invalidation=int(w.first_fresh_and_advance.notna().sum()),
   hits_after_prior_stock_invalidation=int((w.first_fresh_and_advance.notna()&~w.outcome.isin(['same_close','later_hit'])).sum()))
 # Existing labels are opened only after stock/event/cohort output is frozen.
 labelled=[]
 for c,win in [('2022','2022'),('2026','2025_26')]:
  for r in stream(OLD/win/'PRICE_LABELS.jsonl.gz'):
   if not CASES[c][0]<=r['day']<=CASES[c][1]:continue
   for h in [21,63]:labelled.append(dict(case=c,sid=r['sid'],day=r['day'],receipt=r['receipt'],horizon=h,**r['labels'][str(h)]))
 labels=pd.DataFrame(labelled);joined=ev.merge(labels,on=['case','sid','day','receipt'],how='left',validate='one_to_many')
 joined.to_parquet(O/'EXISTING_LABEL_JOIN.parquet',index=False)
 label_summary=[]
 for c in CASES:
  for co in COHORTS:
   base=ev[(ev.case==c)&ev[co]]
   for h in [21,63]:
    j=joined[(joined.case==c)&joined[co]&joined.horizon.eq(h)]
    valid=j[j.valid.eq(True)];tail=valid[valid.right_tail_MFE30.eq(True)]
    rec=dict(case=c,cohort=co,horizon=h,all_fresh=len(base),labels_available=len(j),labels_missing=len(base)-len(j),valid_labels=len(valid),invalid_labels=len(j)-len(valid),
     invalid_reasons=j[j.valid.eq(False)].reason.value_counts().to_dict() if 'reason' in j else {},
     total_existing_tail_events=len(tail),kept_existing_tail_events=int(tail.F1_advance.sum()),
     existing_tail_event_coverage=float(tail.F1_advance.mean()) if len(tail) else None,
     tail_stocks=tail.sid.nunique(),kept_tail_stocks=tail[tail.F1_advance].sid.nunique(),
     tail_stock_contexts=len(tail[['sid','F1_context']].drop_duplicates()),kept_tail_stock_contexts=len(tail[tail.F1_advance][['sid','F1_context']].drop_duplicates()))
    for name,flag in [('kept',True),('excluded',False)]:
     x=valid[valid.F1_advance.eq(flag)]
     rec[name]=dict(events=len(x),stocks=x.sid.nunique(),dates=x.day.nunique(),return_pct=distribution(x.return_pct),MFE_pct=distribution(x.MFE_pct),MAE_pct=distribution(x.MAE_pct),
      MFE30=int(x.right_tail_MFE30.eq(True).sum()),negative_endpoints=int(x.return_pct.lt(0).sum()))
    label_summary.append(rec)
 save('COVERAGE_SUMMARY.json',summary);save('EXISTING_LABEL_SUMMARY.json',label_summary)
 focus=(ev.sid.isin(['300502.SZ','300308.SZ'])|ev.sector.isin(['URFI881121','URFI881172']))
 ev[focus].to_parquet(O/'FOCUS_EVENTS.parquet',index=False)
 wf=waits.sid.isin(['300502.SZ','300308.SZ'])|waits.sector.isin(['URFI881121','URFI881172']);waits[wf].to_parquet(O/'FOCUS_WAITS.parquet',index=False)
 assert before_labels==sha(O/'STOCK_CANONICAL_EVENTS.parquet')
 save('SOURCE_COVERAGE.json',dict(domain='NATIVE1709 only',stock_status=source_status,stock_count=len(sm),sectors=len(cat),case_calendars=cal,
  canonical_events_by_case=ev.groupby('case').size().to_dict(),old_mother_by_case={c:len(x) for c,x in mothers.items()},
  stock_Q_dispositions=ev.groupby(['case','stock_Q'],dropna=False).size().to_dict(),trace_unknown_events=int(ev.canonical_unknown.map(len).gt(0).sum()),
  old_Q_not_new_strategy_domain=True,F1_replacement_domain_complete_from_all_canonical=True,stock_execution_scope='close-input ready only, no account/cash/open fills',
  labels_2023='NOT_AVAILABLE_same_contract; no new labels calculated',labels_elsewhere='original old-Q cohort only; F1-only unlabelled',
  left_censor='window first opportunity; inherited F1 context identified, no assertion of first-ever opportunity'))
 save('SOURCE_SHA256.json',SRC)
 assert SRC=={p:sha(p) for p in SRC}
 save('COMPLETION.json',dict(passed=True,all_original_sectors=True,all_canonical_fresh=True,observations=len(all_days),industry_rows=len(ind),canonical_rows=len(ev),
  new_indicators=0,F1_runs=0,account_creates=0,account_restores=0,financial_events=0,orders=0,downloads=0,source_mutations=0,
  original_sources_unchanged=True,prelabel_stock_output_unchanged=True,seconds=time.monotonic()-started))
 print('COVERAGE_DONE',len(ev),len(waits),round(time.monotonic()-started,2),flush=True)

if __name__=='__main__':main()
