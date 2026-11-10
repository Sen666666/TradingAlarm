"""Saved-journal behavior audit only. No runner, order generation or policy replay."""
import bisect, collections, gzip, hashlib, json, time
from decimal import Decimal as D
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'behavior-audit'
BASE=ROOT.parent/'case-stage-ledger-20261031/v3/run-universe/pair'
NEW=ROOT/'run/pair'
CACHE=ROOT.parent/'universe-cp1-inputs-20261031'
META=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text())
ZERO=D(0)
def read(p): return json.loads(Path(p).read_text())
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def day(x):return str(x)[:10]
def enc(x):
 if isinstance(x,D):return str(x)
 if hasattr(x,'item'):return x.item()
 raise TypeError(type(x).__name__)
def save(name,x):(OUT/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=enc)+'\n')
def clean(x):return None if pd.isna(x) else x
def main():
 start=time.monotonic();OUT.mkdir(exist_ok=True)
 sources={'original_B':BASE,'B_diag':NEW}
 accounts={k:gz(p/'B.json.gz') for k,p in sources.items()}
 daily={k:[r for r in rows(p/'daily.jsonl.gz') if r['account']=='B'] for k,p in sources.items()}
 opp={k:[r for r in rows(p/'opportunities.jsonl.gz') if r['account']=='B'] for k,p in sources.items()}
 funding={k:[r for r in rows(p/'funding.jsonl.gz') if r['account']=='B'] for k,p in sources.items()}
 stages={k:[r for r in rows(p/'industry.jsonl.gz') if r['account']=='B'] for k,p in sources.items()}
 sm={x['symbol']:x for x in read(CACHE/'STOCK_MANIFEST.json')}
 im={x['series']:x for x in read(CACHE/'INDUSTRY_MANIFEST.json')}
 market={};market_days={};attempt_map={}
 for sec,m in im.items():
  rr=pd.read_parquet(m['refs']['state']).to_dict('records');market[sec]={r['day']:r for r in rr};market_days[sec]=list(market[sec])
  for r in rr:
   if r['action']=='probe':attempt_map[r['attempt_id']]=str(r['E0_episode'])+':'+str(r['receipt_id'])
 def state(sec,d):
  days=market_days[sec];i=bisect.bisect_right(days,d)-1
  return market[sec][days[i]] if i>=0 else None
 def market_info(sec,d):
  r=state(sec,d)
  if r is None:return {'known':False}
  return dict(day=r['day'],stage=r['stage_name'],action=r['action'],E0_valid=bool(r['E0_valid']),
   E0_episode=clean(r['E0_episode']),attempt=attempt_map.get(clean(r['attempt_id'])),close=r['close'],
   mobile=clean(r['mobile_after']),receipt_id=clean(r['receipt_id']))
 prices={sid:pd.read_parquet(sm[sid]['refs']['facts'],columns=['raw_close']).raw_close for sid in {t['security_id'] for a in accounts.values() for t in a['trades']}}
 def mark(sid,d):return D(str(prices[sid].asof(pd.Timestamp(d))))
 # Receipt-to-stock-date joins do not use mutable numeric trade receipt counters.
 case_funnels=[];military=[];loss_records=[];categories={};partitions={};stock_loss={};industry_loss={};attempt_loss={};cycles_all={}
 specs=[('URFI881267','2025-07-01','2025-09-30'),('URFI881107','2026-01-01','2026-03-31')]
 for account,a in accounts.items():
  dr={day(r['at']):r for r in daily[account]};calendar=sorted(dr);previous={calendar[i]:calendar[i-1] if i else None for i in range(len(calendar))}
  buy_journal={x['layer']:x for x in a['journal'] if x['kind']=='real_buy_fill'}
  meta=a['metadata'];final_layers={int(x['id']):x for x in a['layers']}
  opportunities={(r['sid'],r['day']):r for r in opp[account]}
  fby=collections.defaultdict(list)
  for f in funding[account]:
   dd=day(f['at']);signalday=previous.get(dd) if '09:30' in f['at'] else dd
   fby[(f['sid'],signalday,f['role'])].append(f)
  actual_cp={x['CP1_id'] for x in buy_journal.values() if x.get('CP1_id')}
  reserved_cp={x.get('CP1_id') for x in funding[account] if x['result']=='reserved' and x['role']=='mobile'}
  for sec,lo,hi in specs:
   rr=[r for r in opp[account] if r['sector']==sec and lo<=r['day']<=hi and r['CP1_id']]
   assert len({r['CP1_id'] for r in rr})==len(rr)
   table=[];counts=collections.Counter()
   for r in rr:
    ff=fby[(r['sid'],r['day'],'mobile')];results=[f['result'] for f in ff]
    if r['mobile_Q'] is None:category='Q_unknown'
    elif not r['mobile_Q']:category='Q_false'
    elif r['barriers']:category='pre_intent_barrier'
    elif r['CP1_id'] in actual_cp:category='actual_mobile_fill'
    elif r['CP1_id'] in reserved_cp:category='reserved_no_mobile_fill'
    elif results:category='rejected:'+','.join(sorted(set(results)))
    else:category='no_mobile_funding_record_unknown_or_same_stock_core_preempted'
    counts[category]+=1
    table.append(dict(**r,category=category,funding=ff,market=market_info(sec,r['day'])))
   eligible=[r for r in table if r['mobile_Q'] is True and not r['barriers']]
   blocked=[r for r in eligible if r['category'] not in ('actual_mobile_fill','reserved_no_mobile_fill')]
   first=blocked[0] if blocked else None
   snapshot=None
   if first:
    # This is the saved close before opening admission, NOT a manufactured opening snapshot.
    ss=dr[first['day']];snapshot={k:ss[k] for k in ('at','nav','available','inventory','pool_probe','pool_confirmed','pending_sells')}
    holders=collections.defaultdict(lambda:dict(capital=ZERO,ids=[],roles=collections.Counter()))
    for x in ss['layers']:
     h=holders[(x['pool'],META[x['sid']]['industry'],x['sid'])];h['capital']+=D(x['qty'])*mark(x['sid'],first['day']);h['ids'].append(x['id']);h['roles'][x['role']]+=1
    snapshot['top_probe_capital_holders']=[dict(pool=k[0],industry=k[1],sid=k[2],name=META[k[2]]['name'],**v) for k,v in sorted(holders.items(),key=lambda kv:kv[1]['capital'],reverse=True) if k[0]=='probe'][:10]
    snapshot['top_confirmed_capital_holders']=[dict(pool=k[0],industry=k[1],sid=k[2],name=META[k[2]]['name'],**v) for k,v in sorted(holders.items(),key=lambda kv:kv[1]['capital'],reverse=True) if k[0]=='confirmed'][:10]
    snapshot['opening_admission_exact_resource_composition']='unknown: no pre-route snapshot; this close precedes next opening sells/open marks/serial reservations'
   case_funnels.append(dict(account=account,sector=sec,industry=META[rr[0]['sid']]['industry'] if rr else sec,window=[lo,hi],all_unique_CP1=len(rr),Q_true=sum(r['mobile_Q'] is True for r in rr),eligible_before_size=len(eligible),mutually_exclusive_counts=dict(counts),first_blocked=first,saved_close_before_first_block=snapshot,receipt_table=table))
  # Actual military purchases, each joined to its own original evidence and then-known industry state.
  for t in a['trades']:
   if t['side']!='buy' or META[t['security_id']]['sector_id']!='URFI881276' or not '2025-10-01'<=day(t['at'])<='2025-12-31':continue
   j=buy_journal[t['layer']];dd=day(j['signal_at']);state_now=state('URFI881276',dd);attempt_id=clean(state_now['attempt_id']);probe=next((r for r in market['URFI881276'].values() if clean(r['attempt_id'])==attempt_id and r['action']=='probe'),None)
   rec=None
   if j.get('CP1_id'):
    rec=next(r for r in read(sm[t['security_id']]['refs']['receipts']) if r['receipt_id']==j['CP1_id'])
   value=sum(D(q)*mark(sid,day(t['at'])) for sid,q in dr[day(t['at'])]['positions'].items() if META[sid]['sector_id']=='URFI881276')
   military.append(dict(account=account,sid=t['security_id'],name=META[t['security_id']]['name'],at=t['at'],signal_at=j['signal_at'],shares=t['shares'],price=t['price'],cash=D(t['gross_cny'])+D(t['fees_cny']),pool=j['pool'],role=j['role'],industry=market_info('URFI881276',dd),industry_attempt_probe_day=probe['day'] if probe else None,industry_progress_since_attempt_probe_pct=(D(str(state_now['close']))/D(str(probe['close']))-1)*100 if probe else None,CP1_id=j.get('CP1_id'),CP1_formation=[rec['formation_start_exclusive'],rec['formation_end_inclusive']] if rec else None,industry_close_weight_after_open_pct=value/D(dr[day(t['at'])]['nav'])*100))
  # Stock flat-to-flat cycles from actual fills, including every subsequent layer in that cycle.
  qty=collections.Counter();cycle_num=collections.Counter();cycle_map={};cycles={}
  for t in a['trades']:
   sid=t['security_id']
   if t['side']=='buy':
    if qty[sid]==0:cycle_num[sid]+=1;cycles[(sid,cycle_num[sid])]=dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],cycle=cycle_num[sid],opened=t['at'],closed=None,transactions=[],layer_ids=[])
    c=cycles[(sid,cycle_num[sid])];c['layer_ids'].append(t['layer']);cycle_map[t['layer']]=(sid,cycle_num[sid]);qty[sid]+=t['shares']
   else:
    c=cycles[(sid,cycle_num[sid])];qty[sid]-=t['shares'];assert qty[sid]>=0
    if qty[sid]==0:c['closed']=t['at']
   c['transactions'].append({k:t[k] for k in ('at','side','shares','gross_cny','fees_cny','layer','reason') if k in t})
  ever_positive=collections.defaultdict(bool)
  for r in daily[account]:
   for x in r['layers']:
    pnl=D(x['cash'])+D(x['dividend'])+D(x['qty'])*mark(x['sid'],day(r['at']))
    if pnl>0:ever_positive[x['id']]=True
  cc=collections.defaultdict(lambda:dict(layers=0,loss=ZERO));ss=collections.defaultdict(lambda:ZERO);gg=collections.defaultdict(lambda:ZERO);aa=collections.defaultdict(lambda:ZERO);partition=collections.defaultdict(lambda:ZERO)
  for lid,x in final_layers.items():
   initial=next(t for t in a['trades'] if t['side']=='buy' and t['layer']==lid);cost=D(initial['gross_cny'])+D(initial['fees_cny']);pnl=D(x['cash'])+D(x['dividend'])+(D(x['qty'])*mark(x['sid'],'2026-03-31') if x['qty'] else ZERO)
   prefix='open' if x['qty'] else 'closed';partition[prefix+('_loss' if pnl<0 else '_tail_profit' if pnl/cost>=D('.3') else '_ordinary_profit')]+=pnl
   if x['qty'] or pnl>=0:continue
   j=buy_journal[lid];m=meta[str(lid)];sid=x['sid'];cyc=cycle_map[lid][1]
   if cyc>1:category='reentry_cycle_loss'
   elif ever_positive[lid]:category='positive_then_closed_loss'
   elif any(other!=lid and other in cycle_map and cycle_map[other]==cycle_map[lid] and final_layers[other]['opened']<x['opened'] for other in final_layers):category='existing_holding_add_never_positive'
   elif j['pool']=='confirmed':category='first_confirmed_pool_entry_never_positive'
   else:category='first_probe_entry_never_positive'
   exday=previous[day(x['closed'])];mi=market_info(m['sector'],exday)
   if not mi.get('known',True):attempt_status='unknown'
   elif mi.get('E0_episode')!=m['episode']:attempt_status='original_E0_no_longer_current'
   elif mi['attempt']==m['attempt']:attempt_status='original_attempt_still_active'
   else:attempt_status='same_E0_original_attempt_ended_or_replaced'
   z=dict(account=account,layer=lid,sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],loss=-pnl,category=category,ever_positive_at_saved_close=ever_positive[lid],initial_pool=j['pool'],role=j['role'],cycle=cyc,original_attempt=m['attempt'],original_E0=m['episode'],attempt_status_at_exit_last_known=attempt_status,entry=x['opened'],exit=x['closed'],exit_reason=x['reason'],entry_cash=cost)
   loss_records.append(z);cc[category]['layers']+=1;cc[category]['loss']-=pnl;ss[sid]-=pnl;gg[META[sid]['industry']]-=pnl;aa[attempt_status]-=pnl
  assert abs(sum(partition.values(),ZERO)-(D(a['ending_NAV'])-D(1000000)))<D('.00000001'),(account,'partition',partition)
  assert all(abs(sum(v['loss'] for v in cc.values())-sum(vals.values()))<D('.00000001') for vals in (ss,gg,aa))
  for c in cycles.values():
   c['buy_cash']=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in c['transactions'] if t['side']=='buy'),ZERO)
   c['sell_cash']=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in c['transactions'] if t['side']=='sell'),ZERO)
   c['economic_contribution']=sum((D(final_layers[lid]['cash'])+D(final_layers[lid]['dividend'])+(D(final_layers[lid]['qty'])*mark(c['sid'],'2026-03-31') if final_layers[lid]['qty'] else ZERO) for lid in c['layer_ids']),ZERO)
  categories[account]=dict(cc);stock_loss[account]=dict(ss);industry_loss[account]=dict(gg);attempt_loss[account]=dict(aa);partitions[account]=dict(partition);cycles_all[account]=list(cycles.values())
 stock_deltas=[dict(sid=s,name=META[s]['name'],industry=META[s]['industry'],original_B_loss=stock_loss['original_B'].get(s,ZERO),B_diag_loss=stock_loss['B_diag'].get(s,ZERO),loss_increase=stock_loss['B_diag'].get(s,ZERO)-stock_loss['original_B'].get(s,ZERO)) for s in set(stock_loss['original_B'])|set(stock_loss['B_diag'])]
 stock_deltas.sort(key=lambda x:x['loss_increase'],reverse=True)
 industry_deltas=[dict(industry=s,original_B_loss=industry_loss['original_B'].get(s,ZERO),B_diag_loss=industry_loss['B_diag'].get(s,ZERO),loss_increase=industry_loss['B_diag'].get(s,ZERO)-industry_loss['original_B'].get(s,ZERO)) for s in set(industry_loss['original_B'])|set(industry_loss['B_diag'])]
 industry_deltas.sort(key=lambda x:x['loss_increase'],reverse=True)
 selected=[r['sid'] for r in stock_deltas if sum(c['sid']==r['sid'] for c in cycles_all['B_diag'])>1][:3]
 defs=dict(unit='actual buy layers; overlapping layers are not independent trials or win-rate observations',economic='net sale cash - actual buy cash including allocated fees + accrued net dividends + remaining marked inventory; same as NAV contribution',classification='exclusive priority: later flat-to-flat reentry cycle; else ever positive at saved daily close; else later actual addition while held; else first entry into confirmed pool; else first probe entry. The last three had no positive saved-close economic contribution. A first confirmed-pool entry is not relabeled an actual position upgrade. Within-day unobserved floating profit is unknown, not inferred.',attempt='last completed industry decision before actual exit; historical immutable layer episode/attempt retained',delta='difference of descriptive loss totals in endogenous account paths; not matched counterfactual loss attributable to each stock mechanism',open_and_closed='all six signed partitions sum each terminal NAV gain; no added subtraction of already included fees')
 save('DEFINITIONS',defs);save('MILITARY_ACTUAL_BUYS',military);save('TWO_CASE_RECEIPT_FUNNELS',case_funnels)
 save('CLOSED_LOSS_LAYERS',loss_records);save('LOSS_SUMMARY',dict(categories=categories,attempt_status=attempt_loss,stock_deltas=stock_deltas,industry_deltas=industry_deltas,signed_NAV_partitions=partitions))
 save('FAILURE_CYCLES',dict(selection='largest closed-loss increase among stocks with more than one actual flat-to-flat cycle; all their cycles retained',sids=selected,cycles={a:[c for c in cc if c['sid'] in selected] for a,cc in cycles_all.items()}))
 save('COMPLETION',dict(read_only=True,new_account_paths=0,seconds=time.monotonic()-start,source_hashes={str(p/'B.json.gz'):hashlib.sha256((p/'B.json.gz').read_bytes()).hexdigest() for p in sources.values()},limitations=['No opening pre-route holdings/risk snapshots were saved; exact migration refusal holder attribution remains unknown. Saved preceding close labeled separately.','No new indicators, signals, strategy thresholds or unit exceptions.','Layer classifications are retrospective descriptions, not causal decomposition.']))
 print('SAVED_BEHAVIOR',time.monotonic()-start)
 print('LOSSES',json.dumps(dict(categories=categories,attempt_status=attempt_loss,top10_stock=stock_deltas[:10],top5_industry=industry_deltas[:5],partitions=partitions),ensure_ascii=False,default=enc))
 for x in case_funnels:
  print('FUNNEL',x['account'],x['industry'],x['all_unique_CP1'],x['Q_true'],x['eligible_before_size'],x['mutually_exclusive_counts'],'first',None if x['first_blocked'] is None else (x['first_blocked']['day'],x['first_blocked']['sid'],x['first_blocked']['category'],x['first_blocked']['market']['stage']))
 print('FAILURE_SIDS',selected)
if __name__=='__main__':main()
