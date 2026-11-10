"""Saved financial ledger aggregation and original-row selection only."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import csv,gzip,hashlib,json,time
import pandas as pd

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
PAIR=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
H={};Z=D(0)
def bind(path):
 p=Path(path).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(path):return json.loads(bind(path).read_text())
def gz(path,lines=False):
 with gzip.open(bind(path),'rt')as f:return [json.loads(x)for x in f]if lines else json.load(f)
def save(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def csvsave(name,rows):
 with(OUT/name).open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 t0=time.monotonic();bind(__file__)
 book=gz(PAIR/'B.json.gz');all_daily=gz(PAIR/'daily.jsonl.gz',True);ds={r['at'][:10]:r for r in all_daily};days=list(ds)
 initial=ds['2022-12-30'];end=ds['2023-12-29'];peak=ds['2023-05-04'];trough=ds['2023-07-21']
 assert not end['positions']and not trough['positions']
 start=read(ROOT/'annual_loss_mechanisms_v1/shared/END2022_STOCK_INVENTORY.json')
 start_marks={r['sid']:D(r['inventory'])for r in start['rows']}
 sm={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 metadata={r['sid']:r for r in read(ROOT/'new_price_trend_v1/analysis/long_OFF_STOCKS.json')}
 frames={}
 def facts(sid):
  if sid not in frames:
   m=sm[sid];p=bind(m['refs']['facts']);assert H[str(p)]==m['output_sha256'][str(p)]
   frames[sid]=pd.read_parquet(p)
  return frames[sid]
 marks=[]
 for sid,qty in peak['positions'].items():
  f=facts(sid).loc[pd.Timestamp('2023-05-04')];p=D(str(f.raw_close));v=D(qty)*p
  marks.append(dict(sid=sid,date='2023-05-04',saved_shares=qty,saved_facts_raw_close=str(p),inventory=str(v),source=sm[sid]['refs']['facts']))
 assert sum((D(r['inventory'])for r in marks),Z)==D(peak['inventory'])
 save('PEAK2023_05_04_ORIGINAL_STOCK_MARKS.json',dict(rows=marks,stocks=len(marks),inventory=peak['inventory'],residual='0'))
 peak_marks={r['sid']:D(r['inventory'])for r in marks}
 def aggregate(lo,hi,beginmarks,begin,endrow):
  cash=defaultdict(lambda:Z);div=defaultdict(lambda:Z);fees=defaultdict(lambda:Z);buy=defaultdict(lambda:Z);sell=defaultdict(lambda:Z);nt=defaultdict(int)
  for t in book['trades']:
   if not lo<=t['at'][:10]<=hi:continue
   sid=t['security_id'];g=D(t['gross_cny']);f=D(t['fees_cny']);fees[sid]+=f;nt[sid]+=1
   if t['side']=='buy':cash[sid]-=g+f;buy[sid]+=g+f
   else:cash[sid]+=g-f;sell[sid]+=g-f
  for a in book['audit']:
   if a['kind']=='dividend_accrual':
    d=a['receivable']
    if lo<=d['ex_at'][:10]<=hi:div[d['security_id']]+=D(d['net_local'])
  rows=[]
  for sid in set(cash)|set(beginmarks)|set(div):
   net=cash[sid]+div[sid]-beginmarks.get(sid,Z);m=metadata.get(sid,{})
   rows.append(dict(sid=sid,name=m.get('name'),industry=m.get('industry'),begin_inventory=beginmarks.get(sid,Z),end_inventory=Z,trade_net_cash=cash[sid],recognized_dividend=div[sid],fees=fees[sid],buy_cash=buy[sid],sell_net=sell[sid],fill_sides=nt[sid],stock_wealth_change=net,contribution_over_begin_NAV_pct=net/D(begin['nav'])*100))
  rows.sort(key=lambda r:r['stock_wealth_change'])
  total=sum((r['stock_wealth_change']for r in rows),Z);expected=D(endrow['nav'])-D(begin['nav']);assert total==expected,(total,expected)
  summary=dict(begin_CLOSE=begin['at'],end_CLOSE=endrow['at'],begin_NAV=begin['nav'],end_NAV=endrow['nav'],wealth_change=total,return_pct=total/D(begin['nav'])*100,stock_contribution_residual=total-expected,
   negative_stock_sum=sum((r['stock_wealth_change']for r in rows if r['stock_wealth_change']<0),Z),positive_stock_sum=sum((r['stock_wealth_change']for r in rows if r['stock_wealth_change']>0),Z),negative_stock_count=sum(r['stock_wealth_change']<0 for r in rows),positive_stock_count=sum(r['stock_wealth_change']>0 for r in rows),all_buy_cash=sum(buy.values(),Z),all_sell_net=sum(sell.values(),Z),all_fees=sum(fees.values(),Z),all_dividend_accrual=sum(div.values(),Z),fill_sides=sum(nt.values()),top5_negative=rows[:5],top3_positive=rows[-3:][::-1])
  return rows,summary
 annual,asum=aggregate('2023-01-01','2023-12-31',start_marks,initial,end)
 drawdown,dsummary=aggregate('2023-05-05','2023-07-21',peak_marks,peak,trough)
 save('ANNUAL_STOCK_CONTRIBUTIONS.json',annual);csvsave('ANNUAL_STOCK_CONTRIBUTIONS.csv',annual)
 save('DRAWDOWN_STOCK_CONTRIBUTIONS.json',drawdown);csvsave('DRAWDOWN_STOCK_CONTRIBUTIONS.csv',drawdown)
 save('ACCOUNT_AND_STOCK_CONTRIBUTION_SUMMARY.json',dict(annual=asum,drawdown=dsummary,annual_is_net_positive=True,prior_year_inventory_deducted=True,not_lifecycle_PnL=True,
  original_boundaries=[initial,peak,trough,end],execution_boundary='Original daily-bar-proxy account, not broker executions.'))
 # Select by total original stock contribution, no future price or signal recomputation.
 selected={r['sid']for r in annual[:5]+annual[-3:]+drawdown[:5]+drawdown[-3:]}
 ops=[];fund=[];inds=[]
 for name,out in [('opportunities',ops),('funding',fund),('industry',inds)]:
  with gzip.open(bind(PAIR/(name+'.jsonl.gz')),'rt')as f:
   for line in f:
    r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
    if day>'2023-12-31':break
    if name=='industry':
     if '2023-01-01'<=day:out.append(r)
    elif r.get('sid')in selected and'2022-01-01'<=day:out.append(r)
 opmap={(r['sid'],r['day']):r for r in ops};decisions={r['at'][:10]:r for r in book['decisions']}
 layerout={r['layer']:r for r in read(ROOT/'new_price_trend_v1/analysis/long_OFF_LAYERS.json')}
 records=[]
 for sid in sorted(selected):
  tx=[(k,t)for k,t in enumerate(book['trades'])if t['security_id']==sid and t['at'][:10]<='2023-12-31'];year_tx=[(k,t)for k,t in tx if t['at'][:4]=='2023']
  carry=[l for l in initial['layers']if l['sid']==sid];relevant={l['id']for l in carry}|{t['layer']for _,t in year_tx if t['side']=='buy'}
  chain=[]
  for k,t in year_tx:
   day=t['at'][:10];prev=days[days.index(day)-1];item=dict(original_book_trade_index=k,original_trade=t,previous_CLOSE_saved_stock_layers=[l for l in ds[prev]['layers']if l['sid']==sid])
   if t['side']=='buy':
    # Actual accounting identity, not an ex-ante trading input. Opening executes sells first.
    buys=[b for _,b in year_tx if b['at'][:10]==day and b['side']=='buy'];assert len(buys)==1
    before=ds[day]['positions'].get(sid,0)-t['shares'];assert before>=0
    prior=any(a['side']=='buy'and j<k for j,a in tx)
    classification='HELD_ADD'if before>0 else'REOPEN_AFTER_FLAT'if prior else'FIRST_ACTUAL_OPEN'
    sd=t['signal_at'][:10];role='core'if t['kind']=='core'else'mobile';intent=next(i for i in decisions[sd]['intents']if i['sid']==sid and i['role']==role)
    jr=next(j for j in book['journal']if j.get('kind')=='real_buy_fill'and j.get('layer')==t['layer']);bo=book['budget']['orders'][jr['budget_order']]
    sf=facts(sid).loc[pd.Timestamp(sd)]
    sector=jr.get('sector',bo.get('sector'))
    latest=[r for r in inds if r['sector']==sector and r['day']<=sd]
    item.update(actual_qty_immediately_before_buy=before,actual_quantity_classification=classification,classification_is_ledger_reconciliation_not_signal=True,signal_original_opportunity=opmap.get((sid,sd),'NOT_SAVED'),original_frozen_intent=intent,
     original_signal_facts={c:sf[c]for c in ['close','raw_close','factor','e0_target','i_target','i_floor','i_buy','g_grade']},
     actual_entry_raw_guard=bo['floor'],actual_entry_continuous_guard=t['floor'],actual_pool_at_fill=jr['pool'],original_funding=[r for r in fund if r['sid']==sid and r['at']==t['at']],
     latest_saved_industry_event=latest[-1]if latest else'NOT_SAVED',original_frozen_order=bo)
   else:
    requests=[r for r in book['audit']if r.get('sid')==sid and r.get('kind')=='pilot_layer_exit'and prev<=r.get('at','')[:10]<=day]
    item['original_close_exit_requests_near_actual_sell']=requests
   chain.append(item)
  evals=[layerout[l]for l in sorted(relevant)]
  for l in evals:assert not l['qty']and l['closed'][:4]=='2023'
  records.append(dict(sid=sid,annual_contribution=next(r for r in annual if r['sid']==sid),drawdown_contribution=next((r for r in drawdown if r['sid']==sid),None),
   original_2022_yearend_carry_layers=carry,original_2023_trade_chain=chain,original_relevant_layer_full_lifecycle_evaluation_only=evals,
   lifecycle_is_not_annual=True,original_2023_all_funding_attempts=[r for r in fund if r['sid']==sid and r['at'][:4]=='2023'],
   original_year_stock_opportunities=[r for r in ops if r['sid']==sid and r['day'][:4]=='2023'],
   missing='Exact per-order pre-route resource and each tested quantity failure certificate not saved. Stored entry/order guards and original daily guards are separate; no terminal floor backfill.'))
 save('SELECTED_FULL_STOCK_CHAINS.json',records)
 save('SELECTED_SOURCE_INDUSTRY_EVENTS.json',inds)
 save('SOURCE_SHA256.json',H)
 save('SCOPE.json',dict(new_accounts=0,new_models=0,new_backtests=0,new_parameters=0,selected_stock_chains=len(records),original_facts_read_for_saved_rows_only=True,yearend2022_shared_anchor=str(ROOT/'annual_loss_mechanisms_v1/shared/END2022_STOCK_INVENTORY.json'),peak_66_stock_mark_exact=True,elapsed_read_extract_seconds=time.monotonic()-t0))

if __name__=='__main__':main()
