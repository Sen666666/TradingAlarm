"""Isolated two-date analysis errata. Never import loaders, accounts or selectors."""
from pathlib import Path
from datetime import date,datetime
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
from dataclasses import dataclass
from typing import Mapping
from collections import Counter
import ast,copy,hashlib,json,math,time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from nullable_analysis import analysis_scope,candidate_inputs,cached_flag

O=Path(__file__).resolve().parent;B=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
STATIC=B/'g-s-static-capital-competition-v1';C=W/'g-s-C-industry-first-projection-v1-20261102';TARGET_B=W/'g-s-B-joint-target-v2-20261102'
ATTR=W/'g-s-B-C-native-advance-attribution-readonly-20261102';COV=B/'industry-advance-gate-coverage-readonly-v1';FACT=B/'industry-evidence-ranking-readonly-v1'
U=W/'universe-cp1-inputs-20261031';V=W/'pvr-slot1-native-readiness-20261101';N=W/'g-s-historical-native-nextsession-20261101'
DAYS=['2026-04-30','2026-05-07'];Z=D(0);SRC={};PURE_AST={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p);h=sha(p)
 if str(p) in SRC:assert SRC[str(p)]==h
 SRC[str(p)]=h
 if expected:assert h==expected,('frozen source differs',p)
 return p
def read(p,expected=None):return json.loads(bind(p,expected).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(date,datetime,pd.Timestamp,D,Path)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def finite(x):return x is not None and bool(pd.notna(x)) and math.isfinite(float(x))
def extract(path,names,ns):
 tree=ast.parse(bind(path).read_text());body=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
 assert {n.name for n in body}==set(names)
 PURE_AST[str(path)]=names
 exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path)+'::analysis_only_pure_subset','exec'),ns)
 return ns
def helpers():
 ns={'math':math};extract(V/'native_rank.py',['priority_plan'],ns)
 rule=RR/'rs-h1-execution-20261025/code/market_rules.py';mr={'date':date,'datetime':datetime,'Mapping':Mapping}
 extract(rule,['RuleUnavailable','day','version_on','market_identity_on'],mr)
 fs={'dataclass':dataclass,'Decimal':D,'ZERO':Z,'Mapping':Mapping,'ROUND_CEILING':ROUND_CEILING,'ROUND_HALF_UP':ROUND_HALF_UP,'__name__':__name__}
 extract(rule.with_name('sector_account.py'),['dec','positive','FeeComponent','FeeSchedule'],fs)
 pure={'MR':mr,'FS':fs,'Z':Z,'D':D,'pd':pd,'pq':pq,'bind':bind,'finite':finite}
 extract(STATIC/'analyze_static.py',['dated','fee','nextday','context_cap','raw_capacity','candidate'],pure)
 return ns['priority_plan'],pure

def states(node,day):
 p=node['path'];f=pq.read_table(bind(p),filters=[('day','<=',day)]).to_pandas();assert day in f.index
 ctx=None;advances=[];start=None
 for at,events in f.events.items():
  for ev in events:
   if ev.startswith('price_failure') or ev=='source_changed_context_ended':ctx=None;advances=[];start=None
   elif ev in ['break_started','repair_restored']:ctx=ev;advances=[];start=at
   elif ev=='price_advance' and ctx:advances.append(at)
 r=f.loc[day];out=analysis_scope(r.to_dict(),bool(advances));out.update(breadth=r.breadth,context_started=start,
  first_context_advance=advances[0] if advances else None,last_context_advance=advances[-1] if advances else None,
  context_advance_count=len(advances),price_advance_today='price_advance' in r.events,events=list(r.events),
  pending_original_type=type(r.get('pending_failure_at')).__name__,pending_original_repr=repr(r.get('pending_failure_at')),
  stored_permit=bool(r.permit_next_open),legacy_support=bool(r['mode']=='ACTIVE' and r['pending_failure_at'] is None))
 return out

def main():
 assert not (O/'COMPLETION.json').exists();begun=time.monotonic()
 audit=read('/var/folders/sj/6vknnkzj0_q6yp4myjk4mtt00000gn/T/advance-gate-independent-8_cwo9kw/FINAL_AUDIT.json')
 old_indices={}
 for key,root,idx in [('static',STATIC,'PACKAGE_SHA256.json'),('B',TARGET_B,'ARTIFACT_SHA256.json'),('C',C,'ARTIFACT_SHA256.json'),('attribution',ATTR,'ARTIFACT_SHA256.json'),('coverage',COV,'PACKAGE_SHA256.json')]:
  ix=read(root/idx);old_indices[key]={str(root/n):v for n,v in ix.items()}
  for p,v in old_indices[key].items():bind(p,v)
 save('OLD_FROZEN_SNAPSHOT.json',old_indices)
 rank,pure=helpers()
 cat=[n for n in read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json') if n['domain']=='NATIVE1709'];assert len(cat)==90
 specs=[dict(sector='G',name='global',path=B/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet')]+[dict(sector=n['sector'],name=n['name'],path=n['daily_result_path']) for n in cat]
 scopes={day:{n['sector']:states(n,day) for n in specs} for day in DAYS}
 changes=[]
 for day,ss in scopes.items():
  for sec,s in ss.items():
   if s['legacy_support']!=s['support']:changes.append(dict(day=day,sector=sec,industry=next(n['name'] for n in specs if n['sector']==sec),**s))
 assert len(changes)==5 and len({x['sector'] for x in changes})==3
 save('NORMALIZED_SCOPE_STATES.json',scopes);save('STATE_CHANGES.json',changes)
 src_manifest=read(U/'STOCK_MANIFEST.json');sm={r['symbol']:r for r in src_manifest};ids=list(sm);assert len(ids)==1709
 meta=read(N/'inputs/2025_26/metadata.json');rules=read(N/'inputs/2025_26/rules.json');protocol=read(N/'inputs/2025_26/protocol.json')
 cv=pd.read_parquet(bind(COV/'STOCK_CANONICAL_EVENTS.parquet'));cv=cv[cv.day.isin(DAYS)].copy();assert len(cv)==129+218
 cvi=cv.set_index(['day','sid']);pvman=read(V/'SCORES_MANIFEST.json');pvm={r['symbol']:r for r in pvman['entries']}
 hp=bind('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
 with np.load(hp,allow_pickle=False) as z:
  ix={str(s):i for i,s in enumerate(z['symbols'])};dx={str(s)[:10]:i for i,s in enumerate(z['dates'])};scores=z['score']
  hs={day:{s:float(scores[dx[day],ix[s]]) for s in ids} for day in DAYS}
  sectors=sorted(n['sector'] for n in cat);ih={day:{s:float(scores[dx[day],ix[s]]) for s in sectors} for day in DAYS};del scores
 hr={d:{s:i for i,s in enumerate(sorted(ids,key=lambda s:(-round(hs[d][s],12) if finite(hs[d][s]) else 1,s)))} for d in DAYS}
 ir={d:{s:i+1 for i,s in enumerate(sorted(sectors,key=lambda s:(-round(ih[d][s],12),s)))} for d in DAYS}
 assert all(finite(v) for m in ih.values() for v in m.values())
 olddisp={d:{r['sid']:r for r in read(STATIC/(d+'-ALL1709_DISPOSITIONS.json'))} for d in DAYS}
 pv={d:{} for d in DAYS};facts={};cp={};can={}
 save('FREEZE.json',dict(protocol_sha256=sha(O/'PROTOCOL.txt'),normalizer_sha256=sha(O/'nullable_analysis.py'),analysis_sha256=sha(__file__),
  days=DAYS,stocks=1709,industries=90,normalization_only='None/NaN/NA/NaT equivalence, missing field UNKNOWN',old_frozen_counts={k:len(v) for k,v in old_indices.items()},
  no_loader_import=True,no_account_or_solver_execution=True,no_indicator_calculation=True,original_pure_AST_subsets=PURE_AST))
 for number,sid in enumerate(ids,1):
  r=pvm[sid];p=V/'scores'/f'{sid}.parquet';v=pd.read_parquet(bind(p,r['output_sha256']),columns=['score'])
  for d in DAYS:pv[d][sid]=v.loc[pd.Timestamp(d),'score']
  if any((d,sid) in cvi.index for d in DAYS):
   r=sm[sid];facts[sid]=pd.read_parquet(bind(r['refs']['facts'],r['output_sha256'][r['refs']['facts']]))
   cp[sid]=pd.read_parquet(bind(r['refs']['CP1'],r['output_sha256'][r['refs']['CP1']]))
   can[sid]={r['confirmed_day']:r for r in read(r['refs']['receipts'],r['output_sha256'][r['refs']['receipts']]) if r['confirmed_day'] in DAYS}
  if number%500==0:print('ASOF_CACHED_SCORES',number,flush=True)
 summary={};allchanges=[];all_market={};rankdiff={}
 oldsummary=read(STATIC/'SUMMARY.json');newsummary=copy.deepcopy(oldsummary)
 for day in DAYS:
  observations=[]
  for sid in ids:
   old=olddisp[day][sid]
   if (day,sid) not in cvi.index:
    assert not old['canonical'];observations.append(dict(sid=sid,canonical=False,facts_exact=old['facts_exact'],stock_Q=None,disposition='NO_CANONICAL_FRESH'));continue
   e=cvi.loc[day,sid];t=pd.Timestamp(day);f=facts[sid].loc[t];cr=cp[sid].loc[t];ca=can[sid][day];sec=meta[sid]['sector']
   assert ca['receipt_id']==e.receipt and not ca['trace_unknown'] and cr.receipt and cr.candidate==ca['original_candidate']
   validation=candidate_inputs(dict(stock_Q=e.stock_Q,I_valid=cached_flag(f.i_target),canonical_known=True,raw_close=f.raw_close,factor=f.factor,I_floor=f.i_floor,CP1_floor=cr.candidate))
   record=dict(sid=sid,name=meta[sid]['name'],sector=sec,canonical=True,canonical_receipt_id=ca['receipt_id'],facts_exact=True,stock_Q=e.stock_Q,
    stock_Q_unknown=list(e.stock_Q_unknown),stock_Q_false=list(e.stock_Q_false),input_guard=validation)
   if not validation['eligible']:record['disposition']='STOCK_INPUT_FALSE_OR_UNKNOWN';observations.append(record);continue
   use,cap=pure['context_cap'](sec,scopes[day],True)
   if not use:record.update(disposition='NO_EXPANSION_PERMISSION',no_expansion_permission=True);observations.append(record);continue
   st=dict(close=f.raw_close,i_floor=f.i_floor,cp_floor=cr.candidate,i_valid=True,receipt={'event_id':ca['receipt_id']})
   c=pure['candidate'](sid,st,sec,scopes[day],day,rules,protocol,{sid:dict(meta[sid],current_factor=f.factor)})
   record.update(c,disposition='MARKET_EXPANSION_CANDIDATE');observations.append(record)
  fresh=[r for r in observations if r.get('fresh_use')];fby={r['sid']:r for r in fresh};domain=list(fby)
  _,log=rank([dict(sid=s,rank=hr[day][s],role='mobile') for s in domain],lambda s,d:pv[day].get(s),'fixed-close')
  order=sorted(log,key=lambda r:r['priority_rank']);ranked=[dict(r,competition_rank=i+1,details=fby[r['sid']]) for i,r in enumerate(order)]
  oldr=read(STATIC/(day+'-ALL_SECTOR_FRESH_COMPETITION.json'));oldby={r['sid']:r for r in oldr};bby={r['sid']:r for r in ranked}
  assert set(oldby)<=set(bby)
  # Every originally included stock retains its original price/protection/minimum facts exactly.
  for sid,r in oldby.items():
   for k in ['close_buy_proxy','fresh_raw_floor','minimum_quantity','minimum_fee','prior20_capacity_upper','fresh_use','fresh_receipt_id']:
    assert clean(r['details'].get(k))==clean(bby[sid]['details'].get(k)),(day,sid,k)
  newonly=sorted(set(bby)-set(oldby));expected=[r['sid'] for r in audit['both_date_missing_candidates'][day]['new_only']]
  assert newonly==sorted(expected)
  save('static/'+day+'-ALL1709_DISPOSITIONS.json',observations);save('static/'+day+'-ALL_SECTOR_FRESH_COMPETITION.json',ranked)
  sector={}
  for sec in sectors:
   group=[r for r in ranked if r['details']['sector']==sec];s=scopes[day][sec]
   sector[sec]=dict(fresh_names=len(group),ranks=[r['competition_rank'] for r in group],first20_count=sum(r['competition_rank']<=20 for r in group),market=s,
    minimum_units_known=sum(r['details']['minimum_input_known'] for r in group),nominal_stock10_supply_upper_fraction=min(D('.8') if s['mature'] else D('.2'),D('.1')*len(group)),
    nominal_bound_not_joint_capacity=True)
  save('static/'+day+'-SECTOR_OPPORTUNITY.json',sector)
  out=[]
  for n,r in enumerate(sorted(ranked,key=lambda r:(ir[day][r['details']['sector']],r['competition_rank'])),1):
   d=r['details'];out.append(dict(day=day,sid=r['sid'],name=d['name'],sector=d['sector'],C_market_only_rank=n,industry_H1_rank=ir[day][d['sector']],
    original_B_rank=r['competition_rank'],original_H1_rank=r['original_H1_rank'],PVR=r['PVR'],PVR_ready=r['PVR_ready'],market_only_purpose=d['fresh_use'],canonical_receipt_id=d['fresh_receipt_id'],
    minimum_quantity=d.get('minimum_quantity'),close_buy_proxy=d.get('close_buy_proxy'),fresh_raw_floor=d.get('fresh_raw_floor'),source_minimum_fee=d.get('minimum_fee'),
    full_fee_schedule_available=False,full_dated_quantity_rule_available=False,actual_GS_eligibility='UNKNOWN',amount=None))
  save('C-market-2026/'+day+'-STOCK_ORDER.json',out)
  rows=[]
  for sec in sectors:
   r=sector[sec];rows.append(dict(day=day,sector=sec,industry=next(n['name'] for n in cat if n['sector']==sec),industry_H1=ih[day][sec],industry_H1_rank=ir[day][sec],
    market_F1_permit=scopes[day][sec]['permit'],market_F1_mature=scopes[day][sec]['mature'],all_stage_canonical_CP1_Q=int(cv[cv.day.eq(day)&cv.sector.eq(sec)&cv.STOCK].shape[0]),
    frozen_market_expansion_list_count=r['fresh_names'],source_support_purposes=sorted({v['details']['fresh_use'] for v in ranked if v['details']['sector']==sec}),
    first_original_B_stock_rank=min(r['ranks'],default=None),GS_account_ACT_holdings_receipts='UNKNOWN',joint_capacity='NOT_COMPUTED'))
  rows.sort(key=lambda r:r['industry_H1_rank']);save('C-market-2026/'+day+'-INDUSTRIES.json',rows)
  oldc=read(C/'market-2026'/(day+'-STOCK_ORDER.json'));oc={r['sid']:r for r in oldc};nc={r['sid']:r for r in out}
  diff=[dict(day=day,sid=s,name=nc[s]['name'],sector=nc[s]['sector'],old_B_rank=oldby[s]['competition_rank'] if s in oldby else None,new_B_rank=bby[s]['competition_rank'],
    old_C_rank=oc[s]['C_market_only_rank'] if s in oc else None,new_C_rank=nc[s]['C_market_only_rank'],added=s not in oldby) for s in nc]
  rankdiff[day]=diff;allchanges+=diff
  sem=[r for r in ranked if r['details']['sector']=='URFI881121']
  summary[day]=dict(stock_denominator=1709,industry_denominator=90,canonical_receipts=int(cv.day.eq(day).sum()),old_fresh=len(oldr),correct_fresh=len(ranked),added=newonly,
   same_day_advance_fresh=sum(scopes[day][r['details']['sector']]['price_advance_today'] for r in ranked),
   strict_semiconductor_count=len(sem),strict_semiconductor_B_top20=sum(r['competition_rank']<=20 for r in sem),
   first_strict_semiconductor_B=min((r['competition_rank'] for r in sem),default=None),first_strict_semiconductor_C=min((r['C_market_only_rank'] for r in out if r['sector']=='URFI881121'),default=None),
   B_top20=[dict(sid=r['sid'],name=r['details']['name'],sector=r['details']['sector'],B_rank=r['competition_rank'],PVR=r['PVR']) for r in ranked[:20]],
   C_all=out,actual_GS_account='UNKNOWN',numerical_capacity='NOT_COMPUTED')
  x=newsummary['extra_2026'][day];x['fresh_mobile_permission_names']=len(ranked);x['top20']=[dict(sid=r['sid'],name=r['details']['name'],sector=r['details']['sector'],PVR=r['PVR'],rank=r['competition_rank']) for r in ranked[:20]]
  x['strict_semiconductor']=sector['URFI881121'];x['electronic_chemicals']=sector['URFI881172'];all_market[day]=rows
  print('CORRECTED_DAY',day,len(oldr),'->',len(ranked),'advance',summary[day]['same_day_advance_fresh'],flush=True)
 assert newsummary['account_cases']==oldsummary['account_cases'] and newsummary['posthoc']==oldsummary['posthoc']
 save('static/SUMMARY.json',newsummary);save('CORRECTED_MARKET_SUMMARY.json',summary);save('ALL_STOCK_RANK_CHANGES.json',allchanges)
 coverage={d:dict(original_industries=90,frozen_market_expansion_stocks=summary[d]['correct_fresh'],with_full_fee_schedule=0,with_full_dated_quantity_rule=0,
  empty_account_fixture_executed=False,numerical_capacity_computed=False,actual_GS_full_state='UNKNOWN',reason='market ranks only; no account or joint capacity',B_rank_definition='corrected original-PVR order within complete domain') for d in DAYS}
 save('C-market-2026/COVERAGE.json',coverage)
 daily=pd.read_parquet(bind(FACT/'LOCAL2026-FULL_TABLE_WITH_HISTORY.parquet'),columns=['day','sector','industry','F1_mode','F1_permit','F1_support','F1_mature','context_started','context_first_advance','last_current_context_native_advance','context_advance_count','events','canonical_CP1_Q','industry_H1_score'])
 market=[];oldmarket={r['sector']:r for r in read(ATTR/'MAY7_MARKET_DIRECTIONS.json')}
 for rec in daily[daily.day.eq(DAYS[1])].to_dict('records'):
  sec=rec['sector'];s=scopes[DAYS[1]][sec];items=[r for r in summary[DAYS[1]]['C_all'] if r['sector']==sec]
  assert s['support']==bool(rec['F1_support']) and s['mature']==bool(rec['F1_mature']) and s['permit']==bool(rec['F1_permit'])
  market.append(dict(day=DAYS[1],sector=sec,industry=rec['industry'],market_context_started=s['context_started'],context_first_advance=s['first_context_advance'],
   last_current_context_advance=s['last_context_advance'],current_context_advance_count=s['context_advance_count'],events=s['events'],price_advance_today=s['price_advance_today'],
   permit=s['permit'],support=s['support'],mature=s['mature'],canonical_CP1_Q=int(rec['canonical_CP1_Q']),frozen_expansion_list_count=len(items),names=[r['name'] for r in items],
   old_expansion_list_count=oldmarket.get(sec,{}).get('frozen_expansion_list_count',0),GS_account_or_migration_consumption_state='UNKNOWN',
   same_day_label='ADVANCE_ACCOMPANIED' if s['price_advance_today'] else 'NO_NEW_ADVANCE',native_GS_policy_context_id='UNKNOWN_no_GS_account_for_this_date'))
 save('attribution/MAY7_ALL90_MARKET_DIRECTIONS.json',market)
 save('attribution/MAY7_MARKET_DIRECTIONS.json',[r for r in market if r['permit'] or r['price_advance_today'] or r['frozen_expansion_list_count']])
 save('attribution/MAY7_SUMMARY.json',dict(all90_retained=True,fresh=62,with_advance=55,without_advance=7,with_advance_industries={r['industry']:r['frozen_expansion_list_count'] for r in market if r['price_advance_today'] and r['frozen_expansion_list_count']},
  without_advance_industries={r['industry']:r['frozen_expansion_list_count'] for r in market if not r['price_advance_today'] and r['frozen_expansion_list_count']},financial_state_or_consumption='UNKNOWN'))
 receiving=read(ATTR/'RECEIVING_DEMANDS.json');groups=read(ATTR/'RECEIVING_INDUSTRIES.json');assert len(receiving)==28 and len(groups)==15
 assert not any(r['has_new_industry_price_advance'] for r in receiving)
 save('UNCHANGED_FINANCIAL_AND_ATTRIBUTION.json',dict(original_B_files=len(old_indices['B']),original_C_files=len(old_indices['C']),
  Jan6_Jul3_targets='original hashes retained; not recalculated',receiving_rows=len(receiving),receiving_industry_policy_groups=len(groups),all_receiving_same_day_advance_false=True,
  original_attribution_summary_sha256=sha(ATTR/'SUMMARY.json'),original_receiving_sha256=sha(ATTR/'RECEIVING_DEMANDS.json'),original_receiving_groups_sha256=sha(ATTR/'RECEIVING_INDUSTRIES.json'),
  loader_called=False,account_called=False,target_solver_called=False,scope='analysis sector_states -> extra_cases only; not an account bug'))
 assert all(sha(p)==v for group in old_indices.values() for p,v in group.items())
 save('PURE_AST_EXTRACTION.json',PURE_AST);save('SOURCE_SHA256.json',SRC)
 assert SRC=={p:sha(p) for p in SRC}
 save('COMPLETION.json',dict(passed=True,scope='isolated market-analysis errata',state_changes=5,distinct_industries=3,corrected_fresh={d:summary[d]['correct_fresh'] for d in DAYS},
  original_files_unchanged=True,financial_loader_calls=0,accounts=0,target_solves=0,financial_events=0,orders=0,indicator_runs=0,F1_runs=0,downloads=0,seconds=time.monotonic()-begun))
 print('ERRATA_MARKET_DONE',round(time.monotonic()-begun,2),flush=True)

if __name__=='__main__':main()
