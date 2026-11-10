"""Saved2022 books only: exact contribution bridge and retrospective behavior."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,time,collections,importlib.util
import pandas as pd
O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixed_calendar2022_saved_analysis_view',O/'adapter.py');A=importlib.util.module_from_spec(spec);sys.modules[spec.name]=A;spec.loader.exec_module(A)
J,L=A.J,A.L;Z=D(0);END=A.END
META=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def num(x):return D(str(x))
def day(x):return str(x)[:10]
def main():
 begun=time.monotonic();books={};daily={};ids=set()
 for ref in ['B3','B_diag']:
  p=O/'runs'/ref
  if not (p/'DONE.json').exists():continue
  marker=O/'analysis'/ref/'COMPLETION.json'
  if marker.exists() and L.read(marker)['book_SHA256']==L.sha(p/'pair/B.json.gz'):
   print('SKIP_SAVED_ANALYSIS',ref,flush=True);continue
  a=obj(p/'pair/B.json.gz');books[ref]=a;daily[ref]=rows(p/'pair/daily.jsonl.gz');ids.update(t['security_id'] for t in a['trades'])
 if not books:return
 _,market,facts=J.M.context(END,ids=sorted(ids));manifest={r['symbol']:r for r in L.read(L.U/'STOCK_MANIFEST.json')}
 for sid in ids:facts.f[sid]=pd.read_parquet(manifest[sid]['refs']['facts']).loc[:END]
 state={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in L.read(L.U/'INDUSTRY_MANIFEST.json')};cache={}
 def price(sid,d):
  if (sid,d) not in cache:
   at=J.M.N.iso(d+'T15:10:00+08:00');cache[sid,d]=market.latest_mark(sid,at).cny_price(at)
  return cache[sid,d]
 summaries=[]
 for ref,a in books.items():
  dest=O/'analysis'/ref;q=daily[ref];journal={x['layer']:x for x in a['journal'] if x['kind']=='real_buy_fill'};cost=collections.defaultdict(lambda:Z)
  for t in a['trades']:
   if t['side']=='buy':cost[t['layer']]+=num(t['gross_cny'])+num(t['fees_cny'])
  partitions=collections.defaultdict(lambda:Z);stock=collections.defaultdict(lambda:Z);layers=[];svals={};groups=collections.defaultdict(lambda:dict(cost=Z,net=Z,open_value=Z,layers=0))
  for x in a['layers']:
   val=D(x['qty'])*price(x['sid'],END) if x['qty'] else Z;net=num(x['cash'])+num(x['dividend'])+val;meta=a['metadata'][str(x['id'])];prefix='open' if x['qty'] else 'closed';cat=prefix+('_loss' if net<0 else '_tail_profit' if cost[x['id']] and net/cost[x['id']]>=D('.3') else '_ordinary_profit');partitions[cat]+=net;stock[x['sid']]+=net
   r=dict(layer=x['id'],sid=x['sid'],name=META[x['sid']]['name'],industry=META[x['sid']]['industry'],role=meta['role'],pool_at_fill=journal[x['id']]['pool'],cost=cost[x['id']],net=net,terminal_value=val,qty=x['qty'],opened=x['opened'],closed=x['closed'],stock_structure=meta.get('stock_structure'),attempt=meta['attempt'],category=cat);layers.append(r)
   key=x['sid']+'|'+str(meta.get('stock_structure'));g=groups[key];g['cost']+=r['cost'];g['net']+=net;g['open_value']+=val;g['layers']+=1
  target=num(a['ending_NAV'])-D(1000000);assert abs(sum(partitions.values(),Z)-target)<D('.00000001')
  # Separate stock cashflow+rights+inventory bridge, not merely sum of layer PnLs.
  flows=collections.defaultdict(lambda:Z);div=collections.defaultdict(lambda:Z)
  for t in a['trades']:flows[t['security_id']]+=(num(t['gross_cny']) if t['side']=='sell' else -num(t['gross_cny']))-num(t['fees_cny'])
  for e in a['audit']:
   if e['kind']=='dividend_accrual':div[e['receivable']['security_id']]+=num(e['receivable']['net_local'])
  for sid in stock:
   inventory=sum((D(x['qty'])*price(sid,END) for x in a['layers'] if x['sid']==sid and x['qty']),Z);assert abs(flows[sid]+div[sid]+inventory-stock[sid])<D('.00000001')
  daily_behavior=[]
  for r in q:
   d=day(r['at']);nav=num(r['nav']);vv={s:D(n)*price(s,d) for s,n in r['positions'].items() if n};assert abs(sum(vv.values(),Z)-num(r['inventory']))<D('.00000001');svals[d]=vv
   inactive=sum((v for s,v in vv.items() if not state[META[s]['sector_id']][d]['attempt_id']),Z)
   risk=num(r['pool_probe'][1])+num(r['pool_confirmed'][1]);daily_behavior.append(dict(day=d,NAV=nav,exposure_pct=num(r['inventory'])/nav*100,available_cash_pct=num(r['available'])/nav*100,probe_committed_pct=num(r['pool_probe'][0])/nav*100,confirmed_committed_pct=num(r['pool_confirmed'][0])/nav*100,nominal_floor_risk_pct=risk/nav*100,old_or_inactive_industry_attempt_held_pct=inactive/nav*100,held_stocks=len(vv),held_industries=len({META[s]['sector_id'] for s in vv}),paused=not r['on']))
  requests={r['event_id']:r for r in a['audit'] if r['kind']=='exit_request'};sellfills=collections.defaultdict(list)
  for e in a['audit']:
   if e['kind']=='fill' and e['receipt']['side']=='sell':sellfills[e['order_id']].append(e['receipt'])
  calendar={str(d.date()):n for n,d in enumerate(market.sessions['A'])};exits=[]
  for eid,fs in sellfills.items():
   req=requests[eid];first=min(fs,key=lambda x:x['at']);exits.append(dict(sid=req['sid'],request=req['at'],first_fill=first['at'],last_fill=max(x['at'] for x in fs),actual_shares=sum(x['shares'] for x in fs),extra_source_sessions=calendar[day(first['at'])]-calendar[day(req['at'])]-1,event=eid))
  reentries=[];seen=set()
  for t in a['trades']:
   if t['side']!='buy':continue
   j=journal[t['layer']]
   if j['budget_order'] in seen:continue
   seen.add(j['budget_order']);previous=[x for x in a['layers'] if x['sid']==t['security_id'] and x['opened']<t['at']]
   if previous and all(x['closed'] and x['closed']<=t['at'] for x in previous):reentries.append(dict(sid=t['security_id'],at=t['at'],shares=t['shares'],role=j['role'],pool=j['pool'],receipt=j['CP1_id'],previous_exit=max(x['closed'] for x in previous)))
  rank=sorted(stock,key=stock.get,reverse=True);chosen=list(dict.fromkeys(rank[:3]+rank[-3:]));paths=[]
  for sid in chosen:
   trades=[t for t in a['trades'] if t['security_id']==sid];curve=[];active_days=0
   for r in q:
    d=day(r['at']);vv=svals[d].get(sid,Z);nav=num(r['nav']);held=[x for x in r['layers'] if x['sid']==sid];active_days+=int(bool(vv));protection=[]
    if held:
     at=J.M.N.iso(d+'T15:10:00+08:00');factor=facts.factor(sid,at)
     for x in held:
      line=num(x['last_core_line'] if x['role']=='core' else x['floor'])/factor;protection.append(dict(layer=x['id'],role=x['role'],pool=x['pool'],shares=x['qty'],raw_line=line,mark=price(sid,d),at_or_below=price(sid,d)<=line))
    curve.append(dict(day=d,weight_pct=vv/nav*100,pending_exit=sid in r['pending_sells'],layers=protection))
   paths.append(dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],net=stock[sid],actual_buy_cash=sum((num(t['gross_cny'])+num(t['fees_cny']) for t in trades if t['side']=='buy'),Z),peak_weight_pct=max(x['weight_pct'] for x in curve),held_closes=active_days,trades=trades,requests_and_fills=[x for x in exits if x['sid']==sid],layers=[x for x in layers if x['sid']==sid],reentries=[x for x in reentries if x['sid']==sid],daily=curve))
  cases=[]
  for sector in ['URFI881160','URFI881158','URFI881105']:
   stocks={s for s in stock if META[s]['sector_id']==sector};trades=[t for t in a['trades'] if META[t['security_id']]['sector_id']==sector];buys=[t for t in trades if t['side']=='buy'];weights=[dict(day=day(r['at']),weight_pct=sum((svals[day(r['at'])].get(s,Z) for s in stocks),Z)/num(r['nav'])*100) for r in q];adds=[]
   for t in buys:
    if any(x['sid']==t['security_id'] and x['opened']<t['at'] and (x['closed'] is None or x['closed']>t['at']) for x in a['layers']):adds.append(t)
   evidence=[dict(day=d,action=r['action'],stage=r['stage_name'],receipt=r['receipt_id']) for d,r in state[sector].items() if A.START<=d<=END and (r['receipt'] or r['action']=='end_attempt')]
   cases.append(dict(sector=sector,industry=next(v['industry'] for v in META.values() if v['sector_id']==sector),first_buy=buys[0] if buys else None,first_same_stock_add=adds[0] if adds else None,total_buy_cash=sum((num(t['gross_cny'])+num(t['fees_cny']) for t in buys),Z),peak=max(weights,key=lambda x:x['weight_pct']),net=sum((stock[s] for s in stocks),Z),trades=trades,weights=weights,evidence=evidence,evaluation_only=True))
  negative_terminal=[dict(sid=s,name=META[s]['name'],net=stock[s],terminal_value=svals[END].get(s,Z),first_buy=min(x['opened'] for x in a['layers'] if x['sid']==s),last_stage=state[META[s]['sector_id']][END]['stage_name']) for s in rank if stock[s]<0 and svals[END].get(s,Z)>0]
  result=dict(reference=ref,net_change=target,stock_and_layer_NAV_residual=sum(stock.values(),Z)-target,layer_partitions=dict(partitions),tail_definition='same prior diagnostic: terminal layer net / actual buy cash>=30%; no future online rule',layer_unit_not_independent_trial=True,stock_count=len(stock),closed_negative_layer_net_loss=-sum((x['net'] for x in layers if x['net']<0 and not x['qty']),Z),record_only_gross_negative_realization_plus_all_fees=sum((num(v) for v in a['budget']['losses'].values()),Z),actual_flat_reentries=len(reentries),exit_requests=len(requests),exit_orders_with_actual_fills=len(exits),sell_fill_records=sum(x['side']=='sell' for x in a['trades']),terminal_pending_stock_exits=len(a['exits']),exit_extra_session_counts=dict(collections.Counter(x['extra_source_sessions'] for x in exits)),worst3=[dict(sid=s,name=META[s]['name'],net=stock[s]) for s in rank[-3:]],best3=[dict(sid=s,name=META[s]['name'],net=stock[s]) for s in rank[:3]],actual_rights=dict(collections.Counter(x['kind'] for x in a['audit'] if x['kind'] in ['split','dividend_accrual'])))
  A.save(dest/'SUMMARY.json',result);A.save(dest/'STOCK_CONTRIBUTIONS.json',[dict(sid=s,name=META[s]['name'],industry=META[s]['industry'],net=stock[s]) for s in rank]);A.save(dest/'LAYER_PARTITIONS.json',layers);A.save(dest/'SAME_STOCK_STRUCTURE_BOOKS.json',groups);A.save(dest/'DAILY_CAPITAL_BEHAVIOR.json',daily_behavior);A.save(dest/'TOP3_POSITIVE_AND_NEGATIVE_PATHS.json',paths);A.save(dest/'THREE_RETROSPECTIVE_INDUSTRY_CASES.json',cases);A.save(dest/'ACTUAL_REENTRIES.json',reentries);A.save(dest/'EXIT_REQUESTS_AND_FILLS.json',exits);A.save(dest/'NEGATIVE_TERMINAL_HOLDINGS.json',negative_terminal);summaries.append(result);A.save(dest/'COMPLETION.json',dict(book_SHA256=L.sha(O/'runs'/ref/'pair/B.json.gz'),read_only=True))
  print('ANALYZED',ref,'net',str(target),'partition',J.W.canon(partitions),'reentries',len(reentries),flush=True)
 combined=[L.read(O/'analysis'/r/'SUMMARY.json') for r in ['B3','B_diag'] if (O/'analysis'/r/'COMPLETION.json').exists()]
 A.save(O/'BEHAVIOR_SUMMARY.json',combined);A.save(O/('ANALYSIS_COMPLETION_'+','.join(books)+'.json'),dict(seconds=time.monotonic()-begun,pricing_only_subset=len(ids),new_account_paths=0,original_mark_used=True,stock_layer_daily_journal_bridges=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:A.save(O/'ANALYSIS_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
