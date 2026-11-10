"""Read saved No60 book/daily/cache only. No Account, indicator or strategy run."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
import bisect,csv,gzip,hashlib,json,math
import pandas as pd

getcontext().prec=50
O=Path(__file__).resolve().parent;Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
B=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
P10=Q/'structural_failure_v1/accounting/results_v2/2022_2024_P10_after2024Oct8_DETAIL.json'
BRIDGE=Q/'trend_exit_controls_v1/execution_review/account_comparison/results_v2/BASELINE_POST_OCT8_OLD_NEW_WEALTH.json'
CUT='2024-10-08';END='2024-12-31';Z=D(0);SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(s) for s in f] if lines else json.load(f)
def frame(p,expected):
 p=Path(p);h=sha(p);assert h==expected,(str(p),h,expected);SRC[str(p.resolve())]=h;return pd.read_parquet(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(D,pd.Timestamp)):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def total(rr,key):return sum((D(r[key]) for r in rr),Z)
def asof(f,day):
 j=f.index.searchsorted(pd.Timestamp(day),side='right')-1
 return (None,None) if j<0 else (str(f.index[j].date()),f.iloc[j].to_dict())
def csvsave(name,rows):
 with (O/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(r) for r in rows)

stage=read(P10);bridge=read(BRIDGE);lr=stage['layer_rows'];book=read(B/'B.json.gz',True);daily=read(B/'daily.jsonl.gz',True,True)
cutidx,cut=next((i,d) for i,d in enumerate(daily) if d['at'][:10]==CUT and d['account']=='B')
endidx,end=next((i,d) for i,d in enumerate(daily) if d['at'][:10]==END and d['account']=='B')
assert len([r for r in lr if r['cohort']=='old_inventory_previous_CLOSE'])==75
assert len([r for r in lr if r['cohort']!='old_inventory_previous_CLOSE'])==303
assert abs(total(lr,'wealth')-D(bridge['net_wealth_change']))<D('1e-18')
validation=read(Q/'dec2022_authorization_v1/account_comparison/results_v1/VALIDATION.json')['native_daily_mark_wealth_and_partial_basis']['BASELINE|2022_2024']
assert validation['partial_layer_ids']==[] and validation['paid_dividends']==0
rank=[]
for sec in sorted({r['sector'] for r in lr}):
 rr=[r for r in lr if r['sector']==sec];old=[r for r in rr if r['cohort']=='old_inventory_previous_CLOSE'];new=[r for r in rr if r['cohort']!='old_inventory_previous_CLOSE']
 rank.append(dict(sector=sec,industry=rr[0]['industry'],wealth=total(rr,'wealth'),old_inventory_wealth=total(old,'wealth'),new_layer_wealth=total(new,'wealth'),layers=len(rr),stocks=len({r['sid'] for r in rr}),negative_layer_wealth=sum((min(Z,D(r['wealth'])) for r in rr),Z),positive_layer_wealth=sum((max(Z,D(r['wealth'])) for r in rr),Z)))
rank.sort(key=lambda r:(r['wealth'],r['sector']))
for i,r in enumerate(rank,1):r['loss_rank']=i
selected=[];sector_summaries=[]
for sec in ['URFI881157','URFI881156']:
 rr=[r for r in lr if r['sector']==sec];stocks=[]
 for sid in sorted({r['sid'] for r in rr}):
  ss=[r for r in rr if r['sid']==sid];old=[r for r in ss if r['cohort']=='old_inventory_previous_CLOSE'];new=[r for r in ss if r['cohort']!='old_inventory_previous_CLOSE']
  stocks.append(dict(sid=sid,name=ss[0]['name'],sector=sec,industry=ss[0]['industry'],stage_wealth=total(ss,'wealth'),old_stage_wealth=total(old,'wealth'),new_stage_wealth=total(new,'wealth'),layer_ids=[r['lid'] for r in ss]))
 stocks.sort(key=lambda r:(r['stage_wealth'],r['sid']));selected.extend(stocks[:3]);s=next(r for r in rank if r['sector']==sec)
 sector_summaries.append(dict(**s,stock_rows=stocks,selected_top3_wealth=sum((r['stage_wealth'] for r in stocks[:3]),Z),selected_top3_net_loss_share=sum((r['stage_wealth'] for r in stocks[:3]),Z)/s['wealth']))
save('SELECTION_AND_CONCENTRATION.json',dict(status='ORIGINAL_STAGE_WEALTH_SELECTION',cutoff=cut['at'],end=end['at'],account_stage_wealth=bridge['net_wealth_change'],old75_wealth=bridge['old_inventory_period_wealth_change'],new303=bridge['post_cutoff_new_actual_layers'],all_industry_ranking=rank,focus_industries=sector_summaries,selected_stocks=selected,selection_is_descriptive_not_signal=True))
csvsave('INDUSTRY_STAGE_RANKING.csv',rank)
csvsave('SELECTED_SIX_STOCK_STAGE_WEALTH.csv',selected)
print('Core selection table saved: securities rank6, insurance rank2; six stocks',flush=True)

manifest={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
native={r['id']:r for r in book['layers']};buy={t['layer']:(i,t) for i,t in enumerate(book['trades']) if t['side']=='buy'}
fill={a['receipt']['receipt_id']:(i,a) for i,a in enumerate(book['audit']) if a['kind']=='fill'}
req={a['event_id']:(i,a) for i,a in enumerate(book['audit']) if a['kind']=='exit_request'}
cutlayer={r['id']:r for r in cut['layers']};endlayer={r['id']:r for r in end['layers']};oldbridge={r['key']:r for r in bridge['old_inventory_details']}
summary=[];stock_results=[];daily_csv=[];sell_csv=[];buy_csv=[]
for sample in selected:
 sid=sample['sid'];ids=set(sample['layer_ids']);m=manifest[sid]
 facts=frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]);cp=frame(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])
 sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));bars=frame(sp,m['source_sha256'][sp])
 ep=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'));events=frame(ep,m['source_sha256'][ep])
 layers=[]
 for lid in sorted(ids):
  sr=next(r for r in lr if r['lid']==lid);ti,t=buy[lid];cost=D(t['gross_cny'])+D(t['fees_cny']);fn=native[lid]
  partrows=[]
  for si,st in enumerate(book['trades']):
   if st['side']!='sell':continue
   for pi,part in enumerate(st['parts']):
    if part['layer']!=lid:continue
    afi,af=fill[st['receipt_id']];ri,rq=req[af['order_id']]
    rr=dict(book_trade_index=si,part_index=pi,actual_trade=st,actual_part=part,fill_audit_index=afi,actual_fill_audit=af,exit_request_audit_index=ri,original_order_create=rq,allocated_actual_sell_fee=D(part['shares'])*D(st['price'])-D(part['net_cash']))
    partrows.append(rr)
    sell_csv.append(dict(sid=sid,layer=lid,order_id=af['order_id'],order_created_at=rq['at'],proxy_fill_at=st['at'],part_shares=part['shares'],raw_OPEN=st['raw_open'],execution_price=st['price'],part_net_cash=part['net_cash'],part_allocated_actual_fee=rr['allocated_actual_sell_fee'],whole_order_actual_fee=st['fees_cny'],part_reason=part['reason'],execution_basis=st['execution_basis'],trade_index=si,part_index=pi))
  post=[p for p in partrows if p['actual_trade']['at']>cut['at']]
  postnet=sum((D(p['actual_part']['net_cash']) for p in post),Z)
  start=cutlayer.get(lid);finish=endlayer.get(lid)
  fd,fr=asof(facts,CUT);assert fr is not None
  _,endf=asof(facts,END)
  q0=0 if start is None else start['qty'];v0=D(q0)*D(str(fr['raw_close']));basis0=Z if start is None else cost
  if start is not None:assert D(start['cash'])==-cost,'No partial basis guessed'
  unreal0=v0-basis0;AR0=Z if start is None else D(start['dividend']);AR1=D(fn['dividend'])
  q1=0 if finish is None else finish['qty'];v1=D(q1)*D(str(endf['raw_close']))
  if start is not None:
   delta=postnet+v1-v0+AR1-AR0;assert abs(delta-D(sr['wealth']))<D('1e-18')
   assert abs(D(oldbridge[sr['key']]['cutoff_layer_wealth'])-(D(start['cash'])+v0+AR0))<D('1e-18')
   giveback=min(max(Z,unreal0),max(Z,-delta));beyond=max(Z,-delta-giveback)
  else:delta=D(sr['wealth']);giveback=None;beyond=None
  life_net=D(fn['cash'])+v1+AR1
  record=dict(sid=sid,name=sample['name'],layer=lid,role=sr['role'],cohort=sr['cohort'],signal_at=t['signal_at'],original_buy_at=t['at'],original_buy_qty=t['shares'],original_buy_price=t['price'],original_buy_fee=t['fees_cny'],
   cutoff_qty=q0,cutoff_raw_mark=None if start is None else str(fr['raw_close']),cutoff_factor=None if start is None else str(fr['factor']),cutoff_mark_value=v0,cutoff_remaining_paid_basis=basis0,cutoff_unreal=unreal0,cutoff_dividend_AR=AR0,
   post_cutoff_actual_net_sale_cash=postnet,ending_qty=q1,ending_mark_value=v1,ending_dividend_AR=AR1,stage_wealth=delta,life_net_separate=life_net,
   descriptive_cutoff_profit_giveback_amount=giveback,descriptive_decline_beyond_initial_positive_unreal=beyond,
   stage_cost_note='Old wealth change uses post-cutoff net actual sale cash + end value - Oct8 value + delta AR; old entry fees are already in cutoff paid basis, not charged again to P10. New layers use actual stage endpoint contribution including entry fees. Giveback is min(positive Oct8 unreal, negative stage wealth), descriptive only; later peaks are not used.')
  summary.append(record)
  fi=next((i,a) for i,a in enumerate(book['audit']) if a['kind']=='fill' and a['receipt']['receipt_id']==t['receipt_id'])
  jr=next((i,a) for i,a in enumerate(book['journal']) if a['kind']=='real_buy_fill' and a.get('layer')==lid)
  dd=next((i,a) for i,a in enumerate(book['decisions']) if a['at']==t['signal_at'])
  intent=[dict(intent_index=i,original=x) for i,x in enumerate(dd[1]['intents']) if x['sid']==sid and x['role']==sr['role']]
  request_rows=[dict(audit_index=i,original=a) for i,a in enumerate(book['audit']) if a['kind']=='pilot_layer_exit' and a.get('sid')==sid and lid in a['layers']]
  layers.append(dict(summary=record,stage_source_row=sr,cutoff_original_live_layer=start,final_original_native_layer=fn,actual_buy_trade_index=ti,actual_buy=t,actual_buy_fill_audit_index=fi[0],actual_buy_fill_audit=fi[1],actual_buy_journal_index=jr[0],actual_buy_journal=jr[1],original_signal_decision_index=dd[0],original_signal_NAV=dd[1]['nav'],original_frozen_intents=intent,actual_exit_request_extensions=request_rows,all_actual_exit_parts=partrows))
  buy_csv.append(dict(sid=sid,layer=lid,role=sr['role'],cohort=sr['cohort'],signal_at=t['signal_at'],actual_buy_at=t['at'],qty=t['shares'],raw_OPEN=t['raw_open'],execution_price=t['price'],actual_buy_fee=t['fees_cny'],original_adjusted_entry_floor=t['floor'],original_pool_at_fill=jr[1]['pool'],trade_index=ti))
 observations=[]
 for di in range(cutidx,endidx+1):
  d=daily[di];day=d['at'][:10];prior=daily[di-1] if di else None
  fd,f=asof(facts,day);bd,bar=asof(bars,day);cpday,cpr=asof(cp,day)
  live=[h for h in d['layers'] if h['id'] in ids];prev=[] if prior is None else [h for h in prior['layers'] if h['id'] in ids]
  current=[]
  for h in live:
   rawh=D(h.get('last_core_line',h['floor']) if h['kind']=='core' else h['floor'])/D(str(f['factor']))
   current.append(dict(original_snapshot=h,known_quote_source_day=fd,raw_CLOSE_mark=f['raw_close'],raw_effective_protection_after_original_CLOSE_checks=rawh,protection_coordinate='core:last_core_line; mobile:floor; divided by original fact factor'))
   old=next((p for p in prev if p['id']==h['id']),None)
   daily_csv.append(dict(sid=sid,day=day,layer=h['id'],role=h['role'],qty=h['qty'],raw_mark=f['raw_close'],factor=f['factor'],prior_observed_snapshot_day=None if old is None else prior['at'][:10],prior_adjusted_floor=None if old is None else old['floor'],prior_last_core_line=None if old is None else old.get('last_core_line'),after_CLOSE_adjusted_floor=h['floor'],after_CLOSE_last_core_line=h.get('last_core_line'),after_CLOSE_raw_effective_protection=rawh,i_target=f.get('i_target'),i_buy=f.get('i_buy'),i_floor=f.get('i_floor'),cp_receipt=None if cpr is None else cpr.get('receipt'),cp_candidate=None if cpr is None else cpr.get('candidate'),fact_source_day=fd,CP_source_day=cpday,daily_index=di))
  au=[dict(audit_index=i,original=a) for i,a in enumerate(book['audit']) if a.get('sid')==sid and a.get('at','')[:10]==day and a['kind'] in ['exit_request','pilot_layer_exit']]
  actual_today=[dict(trade_index=i,original=t) for i,t in enumerate(book['trades']) if t['security_id']==sid and t['at'][:10]==day]
  relevant_fact={k:f[k] for k in ['close','raw_close','factor','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready'] if k in f}
  observations.append(dict(day=day,CLOSE_clock=d['at'],daily_index=di,original_ACT_on=d['on'],account_NAV=d['nav'],previous_saved_CLOSE_live_layers=prev,
   actual_live_layers_after_original_CLOSE_checks=current,original_pending_sells=[s for s in d['pending_sells'] if s==sid],fact_source_day=fd,original_facts=relevant_fact,CP_source_day=cpday,original_CP_cache=cpr,bar_source_day=bd,original_raw_and_adjusted_bar=bar,
   native_event=None if pd.Timestamp(day) not in events.index else events.loc[pd.Timestamp(day)].to_dict(),actual_exit_requests_today=au,actual_trades_today=actual_today,
   missing_execution_reason_note='Pending with no fill does not establish an actual exchange halt/limit-down cause. Daily OHLCV proxy fills are not historical broker ACKs.'))
  # No exact-day source is invented when an as-of row is older.
 result=dict(stock=sample,layers=layers,original_daily_observations=observations,source_paths=dict(facts=m['refs']['facts'],CP1=m['refs']['CP1'],signal=sp,events=ep),scope='Original No60 facts only, no EMA/slope or candidate exit date/payoff')
 save(sid.replace('.','_')+'_ORIGINAL_FACTS.json',result);stock_results.append(dict(sid=sid,path=sid.replace('.','_')+'_ORIGINAL_FACTS.json',layers=sample['layer_ids'],observations=len(observations)))
csvsave('LAYER_CUTOFF_AND_STAGE_BRIDGE.csv',summary);save('LAYER_CUTOFF_AND_STAGE_BRIDGE.json',summary)
csvsave('ACTUAL_BUYS.csv',buy_csv);csvsave('ACTUAL_SELL_PARTS.csv',sell_csv);csvsave('DAILY_HELD_LAYERS_AND_PROTECTION.csv',daily_csv)
save('INDEX.json',dict(status='COMPLETE_READ_ONLY_ORIGINAL_FACTS',stocks=stock_results,cutoff_daily_index=cutidx,ending_daily_index=endidx,partial_basis_state_points=validation['partial_basis_state_points'],original_paid_dividends=validation['paid_dividends'],new_accounts=0,new_models=0,new_backtests=0,new_indicators=0,candidate_exits=0))
for p in [Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py'),Q/'trend_exit_controls_v1/execution_review/account_comparison/compare_accounts.py']:
 SRC[str(p.resolve())]=sha(p)
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,script_sha256=sha(__file__),original_files_changed=False))
print(json.dumps(dict(status='PASS',stocks=len(stock_results),layers=len(summary),held_layer_CLOSE_rows=len(daily_csv),actual_sell_parts=len(sell_csv),new_accounts=0,new_backtests=0),ensure_ascii=False))
