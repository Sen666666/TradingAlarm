"""At most six preselected B_diag snapshots; saved inputs only, no runner."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import bisect,gzip,hashlib,importlib.util,json,time
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'incumbent-competition';CACHE=ROOT.parent/'universe-cp1-inputs-20261031'
METAPATH=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def known(v):return None if pd.isna(v) else v
def truth(v):return None if pd.isna(v) else bool(v)
def main():
 start=time.monotonic();OUT.mkdir(exist_ok=True)
 spec=importlib.util.spec_from_file_location('competition_atomic_IO',ROOT.parent/'_shared/research_output_io.py');IO=importlib.util.module_from_spec(spec);spec.loader.exec_module(IO)
 meta=read(METAPATH);sm={x['symbol']:x for x in read(CACHE/'STOCK_MANIFEST.json')};im={x['series']:x for x in read(CACHE/'INDUSTRY_MANIFEST.json')}
 daily={r['at'][:10]:r for r in rows(ROOT/'run/pair/daily.jsonl.gz') if r['account']=='B'};calendar=sorted(daily)
 with gzip.open(ROOT/'run/pair/B.json.gz','rt') as f:account=json.load(f)
 actual_buys={x['layer']:x for x in account['trades'] if x['side']=='buy'}
 initial_pool={x['layer']:x['pool'] for x in account['journal'] if x['kind']=='real_buy_fill'}
 cases=[x for x in read(ROOT/'behavior-audit/TWO_CASE_RECEIPT_FUNNELS.json') if x['account']=='B_diag']
 state={};state_days={};financial={};ended={}
 for sec,r in im.items():
  rr=pd.read_parquet(r['refs']['state']).to_dict('records');state[sec]={r['day']:r for r in rr};state_days[sec]=list(state[sec])
  for x in rr:
   if x['action']=='probe':financial[x['attempt_id']]=str(x['E0_episode'])+':'+str(x['receipt_id'])
  for x in rr:
   if x['action']=='end_attempt' and known(x['attempt_before']) in financial:ended[financial[x['attempt_before']]]=x['day']
 def status(sec,day):
  ix=bisect.bisect_right(state_days[sec],day)-1
  if ix<0:return dict(known=False)
  r=state[sec][state_days[sec][ix]]
  return dict(known=True,observed=r['day'],stage=r['stage_name'],E0_valid=bool(r['E0_valid']),E0_episode=known(r['E0_episode']),attempt=financial.get(known(r['attempt_id'])))
 z=np.load(H1,allow_pickle=False);dates=pd.DatetimeIndex(z['dates']);symbols={str(s):j for j,s in enumerate(z['symbols'])};score=z['score']
 def h1(sid,day):
  i=dates.get_indexer([pd.Timestamp(day)])[0];v=score[i,symbols[sid]] if i>=0 and sid in symbols else np.nan
  return None if not np.isfinite(v) else float(v)
 facts={}
 def frow(sid,day):
  if sid not in facts:facts[sid]=pd.read_parquet(sm[sid]['refs']['facts'])
  f=facts[sid];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1
  return (f.iloc[i],str(f.index[i].date())) if i>=0 else (None,None)
 def mark(sid,day):
  frow(sid,day);v=facts[sid].raw_close.dropna().asof(pd.Timestamp(day))
  if pd.isna(v):return None
  return D(str(v))
 resources=('pool_capital','probe_risk','sector_capital','sector_risk','cash')
 points={};selection=[]
 for case in cases:
  sec=case['sector'];lo,hi=case['window'];first=case['first_blocked'];s=state[sec][first['day']];aid=s['attempt_id']
  attempt=[r for r in state[sec].values() if known(r['attempt_id'])==aid]
  for anchor in ['known_first_block','confirmed','expanded']:
   origin=first['day'] if anchor=='known_first_block' else next((r['day'] for r in attempt if r['action']==anchor),None)
   if origin is None:selection.append(dict(sector=sec,anchor=anchor,unknown='no such transition in original attempt'));continue
   eligible=[r for r in case['receipt_table'] if max(origin,lo)<=r['day']<=hi and r['mobile_Q'] is True and not r['barriers'] and r['category'].startswith('rejected:') and any(k in r['category'] for k in resources)]
   if not eligible:selection.append(dict(sector=sec,anchor=anchor,origin=origin,no_resource_rejection=True));continue
   firstday=min(r['day'] for r in eligible);candidate=min([r for r in eligible if r['day']==firstday],key=lambda r:(r['rank'],r['sid']))
   key=(sec,firstday);points.setdefault(key,dict(sector=sec,industry=meta[candidate['sid']]['industry'],snapshot_day=firstday,candidate=candidate,anchors=[]))['anchors'].append(anchor)
   selection.append(dict(sector=sec,anchor=anchor,market_transition=origin,inherited_before_account_start=origin<'2025-07-01',snapshot_day=firstday,opening_refusal=candidate['funding'][0]['at']))
 assert len(points)<=6
 snapshots=[];all_layers=[]
 for (sec,day),p in sorted(points.items(),key=lambda kv:kv[0][1]):
  d=daily[day];cand=p['candidate'];cscore=h1(cand['sid'],day);cr,cd=frow(cand['sid'],day)
  intent=next((i for x in account['decisions'] if x['at'][:10]==day for i in x['intents'] if i['sid']==cand['sid'] and i['role']=='mobile'),None)
  assert intent and (cscore is None or abs(cscore-intent['score'])<1e-12)
  layers=[];classes=defaultdict(lambda:D(0));sources=defaultdict(lambda:D(0));numerators=defaultdict(lambda:D(0));stocks=defaultdict(list)
  for x in d['layers']:
   if x['pool']!='confirmed':continue
   sid=x['sid'];m=meta[sid];sr=status(m['sector_id'],day);r,rd=frow(sid,day);price=mark(sid,day);assert price is not None
   value=D(x['qty'])*price;sc=h1(sid,day);ival=None if r is None else truth(r.i_target);e0=None if r is None else truth(r.e0_target)
   end=ended.get(x['attempt']);expired=(end<=day) if end is not None else False if sr.get('attempt')==x['attempt'] else None
   still_active=sr.get('attempt')==x['attempt'];lower=None if sc is None or cscore is None else sc<cscore
   original=actual_buys[x['id']];cost=D(original['gross_cny'])/D(original['shares']);unrealized=D(x['qty'])*(price-cost)
   age=bisect.bisect_right(calendar,day)-bisect.bisect_right(calendar,x['opened'][:10])
   end_age=bisect.bisect_right(state_days[m['sector_id']],day)-bisect.bisect_right(state_days[m['sector_id']],end) if expired else None
   if x['role']=='core':category='original_core'
   elif x['role']=='mobile' and still_active:category='mobile_original_attempt_active'
   elif x['role']=='mobile' and expired is True:category='mobile_original_attempt_ended'
   else:category='source_or_attempt_unknown'
   initial=initial_pool.get(x['id']);sources[category+'|initial_pool='+str(initial)]+=value;classes[category]+=value
   if lower is True:numerators['H1_lower']+=value
   if lower is None:numerators['H1_comparison_unknown']+=value
   if ival is True and expired is True:numerators['I_valid_industry_original_attempt_ended']+=value
   if lower is True and ival is True and expired is True:numerators['both']+=value
   if category=='mobile_original_attempt_ended' and ival is True and sid not in d['pending_sells']:numerators['ended_mobile_I_valid_no_stock_sell_request']+=value
   line=dict(snapshot_day=day,sector=sec,layer=x['id'],sid=sid,name=m['name'],industry=m['industry'],role=x['role'],current_pool=x['pool'],initial_pool=initial,source_note='probe migration is not a new expansion buy' if initial=='probe' else 'native confirmed-pool buy',qty=x['qty'],mark=price,value=value,H1=sc,I_valid=ival,E0_valid=e0,facts_observed_day=rd,industry_state=sr,original_attempt=x['attempt'],original_attempt_still_active=still_active,original_attempt_ended=expired,attempt_end_known_at=end,observations_since_attempt_end=end_age,entry=x['opened'],holding_observations=age,holding_calendar_days=(pd.Timestamp(day)-pd.Timestamp(x['opened'][:10])).days,unrealized_gross=unrealized,unrealized_gross_pct=(price/cost-1)*100,stock_sell_request_pending=sid in d['pending_sells'],layer_sell_request_pending=None,actual_sellable_quantity=None,sellable_unknown_reason='saved close contains position quantity and stock-level sell intent, not lot sellable/locked quantity or a then-known executable opening window',category=category,H1_lower_than_candidate=lower)
   layers.append(line);stocks[sid].append(line);all_layers.append(line)
  holdings=sum((x['value'] for x in layers),D(0));capital=D(str(d['pool_confirmed'][0]));pending=capital-holdings
  assert abs(pending)<D('.000001') or pending>=0
  if abs(pending)<D('.000001'):pending=D(0)
  if pending:classes['source_or_attempt_unknown']+=pending
  top=[]
  for sid,ll in stocks.items():
   first=ll[0];top.append(dict(sid=sid,name=first['name'],industry=first['industry'],value=sum(x['value'] for x in ll),H1=first['H1'],I_valid=first['I_valid'],industry_stage=first['industry_state']['stage'],core_value=sum((x['value'] for x in ll if x['role']=='core'),D(0)),mobile_value=sum((x['value'] for x in ll if x['role']=='mobile'),D(0)),original_attempt_active_value=sum((x['value'] for x in ll if x['original_attempt_still_active']),D(0)),original_attempt_ended_value=sum((x['value'] for x in ll if x['original_attempt_ended'] is True),D(0)),unrealized_gross=sum(x['unrealized_gross'] for x in ll),holding_age_observation_range=[min(x['holding_observations'] for x in ll),max(x['holding_observations'] for x in ll)],stock_sell_request_pending=sid in d['pending_sells'],actual_sellable_quantity=None,layers=ll))
  top.sort(key=lambda x:x['value'],reverse=True)
  proportions={k:(v/capital*100 if capital else None) for k,v in numerators.items()}
  for k in ['H1_lower','I_valid_industry_original_attempt_ended','both','ended_mobile_I_valid_no_stock_sell_request']:proportions.setdefault(k,D(0) if capital else None)
  snapshots.append(dict(industry=p['industry'],sector=sec,snapshot_day=day,anchors=p['anchors'],opening_refusal=cand['funding'],candidate=dict(sid=cand['sid'],name=meta[cand['sid']]['name'],H1=cscore,original_order_rank=cand['rank'],I_valid=truth(cr.i_target),E0_valid=truth(cr.e0_target),industry_state=status(sec,day),canonical_CP1=cand['CP1_id'],original_Q=cand['mobile_Q']),capital_denominator=capital,held_confirmed_value=holdings,pending_confirmed_value=pending,confirmed_pool_pct_NAV=capital/D(d['nav'])*100,class_value=dict(classes),class_pct_confirmed={k:(v/capital*100 if capital else None) for k,v in classes.items()},class_source_breakdown=dict(sources),capital_conditions_value=dict(numerators),capital_conditions_pct=proportions,top10_confirmed_stocks=top[:10],all_confirmed_layer_count=len(layers),other_candidate_resources_independently_cleared='unknown: saved route reasons combine routes; no exact pre-route opening resource snapshot; not certified by previous-close comparison',exact_opening_snapshot=False))
 definitions=dict(selection='known first block, then original-attempt first confirmed/expanded transition and first in-window resource rejection; inherited pre-account states are not reset; coincident dates coalesced',candidate='within that named industry, original Q true/fresh canonical CP1/no planning barrier, first resource-rejection date then highest original H1 order; not selected by later returns',H1='same-date cached original H1 score; strictly lower, ties separate from lower; checked against actual saved intent score',I='original i_target and e0_target separately; last known observation date retained',denominator='all confirmed-pool marked holdings plus actual pending capital; zero capital is undefined percentage, not zero weakness',unrealized='remaining shares times marked raw price minus original gross actual buy unit cost; excludes dividends/fees and realized PnL; B_diag has zero split events',expired='original financial attempt canonical ID mapped to market trace end-attempt event; no later-than-snapshot end used',mobile_source='current confirmed mobile split by initial probe migration vs initial confirmed admission; neither migration nor core is called new expansion capital',sellability='not saved at these snapshots, unknown; stock-level sell request does not identify each layer sell request',limits='these are previous-close states, not exact next opening pre-admission states; no forward profit used; no recycle/sell algorithm or economic replay')
 IO.write_json(OUT/'SELECTION.json',selection);IO.write_json(OUT/'SNAPSHOTS.json',snapshots,encoder=str);IO.write_json(OUT/'ALL_CONFIRMED_LAYERS.json',all_layers,encoder=str);IO.write_json(OUT/'DEFINITIONS.json',definitions)
 IO.write_json(OUT/'COMPLETION.json',dict(complete=True,new_account_paths=0,snapshots=len(snapshots),maximum_allowed=6,seconds=time.monotonic()-start,source_sha256={str(ROOT/'run/pair/B.json.gz'):hashlib.sha256((ROOT/'run/pair/B.json.gz').read_bytes()).hexdigest(),str(H1):hashlib.sha256(H1.read_bytes()).hexdigest()},remaining_unknowns=['actual sellable quantities','exact pre-route opening composition and other-resource clearance'],no_new_policy=True))
 for r in snapshots:print(r['snapshot_day'],r['industry'],r['candidate']['name'],r['candidate']['H1'],'capital',r['capital_denominator'],'pool/NAV',r['confirmed_pool_pct_NAV'],'conditions%',r['capital_conditions_pct'],'classes',r['class_value'])
 print('READ_ONLY_DONE',time.monotonic()-start)
if __name__=='__main__':main()
