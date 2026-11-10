"""Cached industry evidence/ranks only. No model, account or network imports."""
from pathlib import Path
from datetime import date,datetime
from typing import Mapping
from collections import defaultdict,Counter
import ast,hashlib,json,math,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;B=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
U=W/'universe-cp1-inputs-20261031';N=W/'g-s-historical-native-nextsession-20261101'
H1={d:Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market')/p/'prepared/h1.npz' for d,p in [('NATIVE1709','update-20261030-153010-c551af'),('OLD407','update-20261027-153013-2ffe04')]}
CASES={'2022':('NATIVE1709','2022-06-17','2022-12-29'),'2023':('NATIVE1709','2023-01-19','2023-08-25'),
       'OLD924':('OLD407','2024-09-24','2024-12-31'),'LOCAL2026':('NATIVE1709','2026-04-30','2026-06-30')}
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p);v=sha(p)
 if str(p) in SRC:assert SRC[str(p)]==v,('source changed during read',p)
 SRC[str(p)]=v
 if expected:assert v==expected,('declared source hash differs',p)
 return p
def read(p):return json.loads(bind(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(date,datetime,pd.Timestamp,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def frame(p,expected=None,cols=None):return pd.read_parquet(bind(p,expected),columns=cols)

def pure_rules():
 p=RR/'rs-h1-execution-20261025/code/market_rules.py';tree=ast.parse(bind(p).read_text())
 names={'RuleUnavailable','day','version_on','market_identity_on'};ns={'date':date,'datetime':datetime,'Mapping':Mapping}
 body=[x for x in tree.body if isinstance(x,(ast.ClassDef,ast.FunctionDef)) and x.name in names]
 exec(compile(ast.Module(body=body,type_ignores=[]),str(p)+'::pure_rules','exec'),ns)
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

def load_h1(domain,ids,sectors,case_days):
 z=np.load(bind(H1[domain]),allow_pickle=False);dates=pd.DatetimeIndex(z['dates']);sym=[str(s) for s in z['symbols']];cols={s:i for i,s in enumerate(sym)}
 sector_cols=[cols[s] for s in sectors];ix=dates.get_indexer(case_days);assert (ix>=0).all()
 score=z['score']
 out=dict(dates=dates,sectors=sectors,sector_score=score[:,sector_cols].copy(),
   stock_score=pd.DataFrame(score[np.ix_(ix,[cols[s] for s in ids])],index=case_days,columns=ids))
 del score
 for key in ['close','segment','h','raw','nref']:out[key]=z[key][:,sector_cols].copy()
 return out

def saved_context(df):
 current=None;first_advance=last_advance=None;count=0;rows=[]
 for day,r in df.iterrows():
  for e in r.events:
   if e.startswith('price_failure') or e=='source_changed_context_ended':current=None;first_advance=last_advance=None;count=0
   elif e in ['break_started','repair_restored']:current=day;first_advance=last_advance=None;count=0
   elif e=='price_advance' and current:
    count+=1;last_advance=day
    if first_advance is None:first_advance=day
  support=r['mode']=='ACTIVE' and pd.isna(r['pending_failure_at'])
  rows.append(dict(day=day,F1_mode=r['mode'],F1_status=r['effective_status'],F1_permit=bool(r.permit_next_open),
    F1_support=support,F1_mature=bool(support and count),context_started=current,
    context_first_advance=first_advance,last_native_advance=last_advance,context_advance_count=count,
    breadth=r.breadth,ready_m=r.ready_m,events=list(r.events),unknown=list(r.unknown)))
 return pd.DataFrame(rows).set_index('day')

def count_opportunities(domain,ids,days,meta,lines,h,stock_manifest,receipts,rules,protocol):
 sectors=sorted({meta[s]['sector'] for s in ids});metrics=['fixed_stocks','facts_exact','stock_Q_known','stock_Q_pass','source_legality_unknown','stock_H1_ready','I_entry_Q','numeric_CP1_Q','canonical_CP1_Q','union_I_or_canonical_Q']
 totals={(str(d.date()),s):dict.fromkeys(metrics,0) for d in days for s in sectors}
 day_set={str(d.date()) for d in days}
 for n,sid in enumerate(ids):
  sec=meta[sid]['sector'];x=stock_manifest[sid]
  f=frame(x['facts'],x.get('facts_sha'));cp=frame(x['cp'],x.get('cp_sha'))
  ff=f.reindex(days);cc=cp.reindex(days);hs=h['stock_score'][sid].to_numpy()
  can={}
  if domain=='NATIVE1709':
   for year,mp in receipts.items():
    rec=mp[sid];rr=read(bind(rec['path'],rec['sha']))
    for q in rr:
     if q['confirmed_day'] in day_set:
      assert not q['trace_unknown'];can[q['confirmed_day']]=q
  frs=list(ff.itertuples(index=False));crs=list(cc.itertuples(index=False))
  for j,d in enumerate(days):
   day=str(d.date());row=totals[day,sec];row['fixed_stocks']+=1;fr=frs[j];cr=crs[j]
   exact=d in f.index;row['facts_exact']+=int(exact);hh=bool(np.isfinite(hs[j]));row['stock_H1_ready']+=hh
   av=input_legal(sid,day,rules,protocol,meta);row['source_legality_unknown']+=av is None
   ready=exact and pd.notna(fr.e0_ready) and bool(fr.e0_ready)
   known=bool(exact and ready and pd.notna(fr.i_target) and av is not None and hh)
   row['stock_Q_known']+=known
   line=lines[sid];common=bool(line['current_stock'] and line['company_cap_cny'] is not None and line['company_cap_cny']>1e10 and line['issuer_id'] and line['sector_id']==sec)
   q=bool(known and ready and bool(fr.i_target) and av is True and common)
   quote=bool(q and np.isfinite(fr.raw_close) and fr.raw_close>0 and np.isfinite(fr.factor) and fr.factor>0 and np.isfinite(fr.i_floor) and fr.raw_close>fr.i_floor/fr.factor)
   row['stock_Q_pass']+=q
   core=bool(quote and pd.notna(fr.i_buy) and fr.i_buy);row['I_entry_Q']+=core
   numeric=bool(quote and pd.notna(cr.receipt) and bool(cr.receipt) and np.isfinite(cr.candidate) and fr.raw_close>max(fr.i_floor,cr.candidate)/fr.factor)
   row['numeric_CP1_Q']+=numeric
   if domain=='NATIVE1709':
    ca=can.get(day)
    if ca:assert pd.notna(cr.receipt) and bool(cr.receipt) and float(cr.candidate)==ca['original_candidate'],(sid,day,'canonical/numeric mismatch')
    legal=bool(numeric and ca);row['canonical_CP1_Q']+=legal;row['union_I_or_canonical_Q']+=bool(core or legal)
  if (n+1)%500==0:print('CACHED_STOCK_Q',domain,n+1,flush=True)
 out=[]
 for (day,sec),r in totals.items():
  if domain=='OLD407':r.update(canonical_CP1_Q=None,union_I_or_canonical_Q=None)
  out.append(dict(day=day,sector=sec,**r,canonical_status='READY' if domain=='NATIVE1709' else 'UNKNOWN_old924_canonical_export_missing'))
 return pd.DataFrame(out).set_index(['day','sector'])

def main():
 assert not (O/'COMPLETION.json').exists();begun=time.monotonic()
 cat=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json');registry=read(B/'input-preparation/prepared-v2/FIXED_CASE_INPUT_REGISTRY.json')
 sm=read(U/'STOCK_MANIFEST.json');meta=read(N/'inputs/2025_26/metadata.json');selection=read(N/'inputs/2025_26/selection.json');lines={x['security_id']:x for x in selection['lines']}
 oldpool=pd.read_csv(bind(RR/'tech-compound-design-20261026/proposed-pool.csv'));ids={'NATIVE1709':[x['symbol'] for x in sm],'OLD407':oldpool.symbol.tolist()}
 assert len(ids['NATIVE1709'])==1709 and len(ids['OLD407'])==407
 assert all(s in meta and s in lines for ss in ids.values() for s in ss)
 globals={d:frame(B/'historical-shadow/run-v1'/f'{d}_global_daily.parquet') for d in ids}
 calendars={k:pd.DatetimeIndex(globals[d].loc[a:b].index) for k,(d,a,b) in CASES.items()}
 all_days={d:pd.DatetimeIndex(sorted(set().union(*(set(calendars[k]) for k,(dd,a,b) in CASES.items() if dd==d)))) for d in ids}
 nodes={d:[n for n in cat if n['domain']==d] for d in ids};assert len(nodes['NATIVE1709'])==90 and len(nodes['OLD407'])==11
 hc={d:load_h1(d,ids[d],[n['sector'] for n in nodes[d]],all_days[d]) for d in ids}
 bind(RR/'rs-h1-execution-20261025/code/rs_h1_model.py');bind(RR/'rs-h1-execution-20261025/code/prepare_h1.py');bind(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/refresh.py'))
 bind(RR/'pv-rank-q1-20261027/FORMULA.json');bind(RR/'pvr-act-comparison-20261027/CONCLUSION.txt');bind(RR/'pvr-act-comparison-20261027/code/experiment.py')
 m22=read(W/'2022-normal-reference-20261031/inputs/MANIFEST.json');m23=read(W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json')
 receipts={'2022':{x['sid']:dict(path=x['output_path'],sha=x['output_sha256']) for x in m22 if not x['industry']},
  '2023':{x['sid']:dict(path=x['output_path'],sha=x['output_sha256']) for x in m23 if not x['industry']},
  '2026':{x['symbol']:dict(path=x['refs']['receipts'],sha=x['output_sha256'][x['refs']['receipts']]) for x in sm}}
 manifests={'NATIVE1709':{x['symbol']:dict(facts=x['refs']['facts'],facts_sha=x['output_sha256'][x['refs']['facts']],cp=x['refs']['CP1'],cp_sha=x['output_sha256'][x['refs']['CP1']]) for x in sm},
  'OLD407':{s:dict(facts=str(H1['OLD407'].parent/'facts'/f'{s}.parquet'),cp=str(RR/'continuous-protection-lines-20261028/signals'/f'{s}.parquet')) for s in ids['OLD407']}}
 rules={d:read(N/'inputs/2025_26/rules.json' if d=='NATIVE1709' else RR/'pvr-act-comparison-20261027/execution-rules-v2.json') for d in ids}
 protocol=read(N/'inputs/2025_26/protocol.json')
 save('FREEZE.json',dict(before_stock_count_and_rank_calculation=True,script_sha256=sha(__file__),protocol_sha256=sha(O/'PROTOCOL.txt'),
  cases=CASES,sectors={d:len(nodes[d]) for d in ids},industry_PVR='NOT_CACHED; original index amount contract unverified',no_new_indicator_calculation=True))
 opp={d:count_opportunities(d,ids[d],all_days[d],meta,lines,hc[d],manifests[d],receipts if d=='NATIVE1709' else {},rules[d],protocol) for d in ids}
 tables={};price_checks=[];global_events=[]
 for key,(domain,a,b) in CASES.items():
  h=hc[domain];rows=[];days=calendars[key];dates=h['dates'];di={str(d.date()):i for i,d in enumerate(dates)}
  global_part=globals[domain].loc[a:b]
  for day,r in global_part.iterrows():
   if len(r.events):global_events.append(dict(case=key,domain=domain,day=day,mode=r['mode'],permit=bool(r.permit_next_open),breadth=r.breadth,events=list(r.events)))
  for j,node in enumerate(nodes[domain]):
   sec=node['sector'];daily=frame(node['daily_result_path']);cx=saved_context(daily.loc[:b]);inp=frame(node['input_file'])
   for d in days:
    day=str(d.date());i=di[day];r=cx.loc[day].to_dict() if day in cx.index else dict(F1_mode='UNKNOWN',F1_permit=False,F1_mature=False,unknown=['missing_industry_observation'])
    if d in inp.index and pd.notna(inp.loc[d,'price_input']) and np.isfinite(h['close'][i,j]):
     assert inp.loc[d,'price_input']==h['close'][i,j],(domain,sec,day,'industry price source differs')
    op=opp[domain].loc[day,sec].to_dict();score=h['sector_score'][i,j]
    rows.append(dict(case=key,domain=domain,day=day,sector=sec,industry=node['name'],**r,**op,
     industry_H1_score=score,industry_H1_raw=h['raw'][i,j],industry_H1_h=int(h['h'][i,j]),industry_H1_reference_count=int(h['nref'][i,j]),
     industry_PVR_score=None,industry_PVR_rank=None,industry_PVR_status='UNKNOWN_not_cached_and_amount_units_unverified',
     global_F1_permit=bool(global_part.loc[day,'permit_next_open']),global_F1_mode=global_part.loc[day,'mode'],
     local_expansion_stock_opportunities=op['canonical_CP1_Q'] if r.get('F1_permit') and r.get('F1_mature') else 0,
     local_trial_stock_opportunities=op['union_I_or_canonical_Q'] if r.get('F1_permit') else 0))
  df=pd.DataFrame(rows)
  for day,g in df.groupby('day',sort=False):
   for flag,out in [(None,'H1_rank_all_original_sectors'),('F1_permit','H1_rank_among_permitted'),('F1_mature','H1_rank_among_mature_permitted')]:
    known=g[g.industry_H1_score.notna()]
    if flag=='F1_permit':known=known[known.F1_permit]
    elif flag=='F1_mature':known=known[known.F1_permit&known.F1_mature]
    order=known.assign(_order=known.industry_H1_score.round(12)).sort_values(['_order','sector'],ascending=[False,True],kind='stable').index
    df.loc[order,out]=np.arange(1,len(order)+1)
  assert len(df)==len(days)*len(nodes[domain])
  df.to_parquet(O/(key+'-RANKS_AND_OPPORTUNITIES.parquet'),index=False);tables[key]=df
  price_checks.append(dict(case=key,rows=len(df),source_known_prices_exact=True))
 rankhash={p.name:sha(p) for p in O.glob('*-RANKS_AND_OPPORTUNITIES.parquet')};save('PRE_EVALUATION_RANK_SHA256.json',rankhash)
 # Later prices are consulted only after the complete contemporaneous tables freeze.
 evaluation=[];paths=[]
 for key,df in tables.items():
  domain=CASES[key][0];h=hc[domain];di={str(d.date()):i for i,d in enumerate(h['dates'])};sj={s:j for j,s in enumerate(h['sectors'])}
  ev=[];path=[]
  for row in df.itertuples(index=False):
   i=di[row.day];j=sj[row.sector];close=h['close'][:,j];seg=h['segment'][:,j];origin=close[i];rec=dict(case=key,domain=domain,day=row.day,sector=row.sector,evaluation_origin_price=origin)
   p=close[i:min(len(close),i+64)].copy();ss=seg[i:min(len(seg),i+64)];rec['future_path_missing_observations']=int((~np.isfinite(p)).sum());rec['evaluation_cache_end']=str(h['dates'][-1].date())
   for n in [21,63]:
    why=[];end=i+n
    if not np.isfinite(origin):why.append('origin_price_unknown')
    if end>=len(close):why.append('horizon_beyond_cache')
    elif not np.isfinite(close[end]):why.append('target_price_unknown')
    segment=seg[i:min(len(seg),end+1)];different=np.isfinite(segment)&np.isfinite(seg[i])&(segment!=seg[i])
    if different.any():why.append('source_segment_changed')
    rec['price_return_'+str(n)]=None if why else float(close[end]/origin-1)
    rec['price_at_'+str(n)]=None if end>=len(close) else close[end]
    rec['date_at_'+str(n)]=None if end>=len(close) else str(h['dates'][end].date())
    rec['censor_'+str(n)]=why
   ev.append(rec);path.append(dict(case=key,day=row.day,sector=row.sector,original_common_calendar_dates=[str(d.date()) for d in h['dates'][i:min(len(close),i+64)]],industry_index_price_path_0_63=p.tolist()))
  edf=pd.DataFrame(ev);pd.DataFrame(path).to_parquet(O/(key+'-EVALUATION_PATHS.parquet'),index=False)
  edf.to_parquet(O/(key+'-EVALUATION.parquet'),index=False)
  df.merge(edf,on=['case','domain','day','sector'],validate='one_to_one').to_parquet(O/(key+'-FULL_TABLE.parquet'),index=False)
  evaluation.append(dict(case=key,rows=len(edf),endpoint21_censored=sum(bool(x) for x in edf.censor_21),endpoint63_censored=sum(bool(x) for x in edf.censor_63),paths_with_missing=int(edf.future_path_missing_observations.gt(0).sum())))
 assert rankhash=={p:sha(O/p) for p in rankhash}
 save('GLOBAL_F1_EVENTS.json',global_events);save('PRICE_SOURCE_GATE.json',price_checks);save('EVALUATION_COVERAGE.json',evaluation)
 summaries={}
 for key,df in tables.items():
  daily=[]
  for day,g in df.groupby('day',sort=True):
   daily.append(dict(day=day,sectors=len(g),H1_known=int(g.industry_H1_score.notna().sum()),F1_permit=int(g.F1_permit.sum()),mature_permit=int((g.F1_permit&g.F1_mature).sum()),
    core_I_entry_Q=int(g.I_entry_Q.sum()),canonical_CP1_Q=None if key=='OLD924' else int(g.canonical_CP1_Q.sum()),canonical_missing=key=='OLD924',
    permitted_industries_with_I_entries=int((g.F1_permit&g.I_entry_Q.gt(0)).sum()),
    permitted_industries_with_canonical_CP1=None if key=='OLD924' else int((g.F1_permit&g.canonical_CP1_Q.gt(0)).sum())))
  summaries[key]=dict(domain=CASES[key][0],window=CASES[key][1:],observations=len(daily),sectors=int(df.sector.nunique()),rows=len(df),daily=daily,
   industry_PVR='UNKNOWN_all_rows; no score calculation',stock_mobile_complete=key!='OLD924')
 save('CASE_COVERAGE.json',summaries);save('SOURCE_SHA256.json',SRC)
 assert SRC=={p:sha(p) for p in SRC}
 save('COMPLETION.json',dict(passed=True,read_only=True,case_count=4,rows=sum(len(d) for d in tables.values()),all_original_sectors_and_observations=True,
  cached_H1_only=True,industry_PVR_blocked='no existing cache; source_index_amount_units not certified under original formula contract',
  OLD924_canonical_mobile_blocked=True,original_sources_unchanged=True,rank_hash_unchanged_after_future_evaluation=True,
  accounts_created=0,account_restores=0,financial_events=0,orders=0,new_indicators=0,downloads=0,seconds=time.monotonic()-begun))
 print('INDUSTRY_H1_TABLES_DONE',json.dumps(clean(dict(rows=sum(len(d) for d in tables.values()),coverage=evaluation,seconds=time.monotonic()-begun))),flush=True)

if __name__=='__main__':main()
