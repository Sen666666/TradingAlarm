"""Post-hoc 2022 frozen-checkpoint attribution; zero Account/Runner instantiation."""
from pathlib import Path
import sys,json,pickle,hashlib
from decimal import Decimal as D
from collections import defaultdict
from bisect import bisect_left
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;ROOT=O.parents[1];P=ROOT/'run_1200000/latest_checkpoint/checkpoint-2022-12-30.pkl'
sys.path.insert(0,str(ROOT/'inputs'));import continuous_inputs as C
Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v): (O/n).write_text(json.dumps(v,indent=2,default=str,allow_nan=False))
def stats(rows):
 ps=[float(r['pnl'])for r in rows];win=[v for v in ps if v>0];lose=[v for v in ps if v<0];ordered=sorted(rows,key=lambda r:(str(r['closed']),r['sid'],r.get('id',0)));chain=best=0
 for r in ordered:
  chain=chain+1 if r['pnl']<0 else 0;best=max(best,chain)
 return dict(n=len(ps),wins=len(win),losses=len(lose),flat=sum(v==0 for v in ps),win_rate=len(win)/len(ps)if ps else None,mean_win=np.mean(win)if win else None,mean_loss=np.mean(lose)if lose else None,total_net=sum(ps),max_consecutive_losing_closures=best,closure_tie_order='timestamp then security ID then layer ID; simultaneous closures are not independent time trials',mean_calendar_days=np.mean([r['calendar_days']for r in rows])if rows else None,median_calendar_days=np.median([r['calendar_days']for r in rows])if rows else None)
def main():
 meta=json.loads(P.with_suffix('.json').read_text());prov=json.loads(P.with_suffix('.provenance.json').read_text());raw=P.read_bytes();h=hashlib.sha256(raw).hexdigest();assert h==meta['sha256']==prov['checkpoint_sha256'];x=pickle.loads(raw);del raw
 assert str(x['last_completed_event'])[:10]=='2022-12-30';assert x['source_freeze']==meta['source_freeze']
 for p,v in x['source_freeze'].items():assert sha(p)==v,('source drift',p)
 fixed=C.read(C.U/'FREEZE.json')['stocks'];_,market,_=C.J.M.context('2022-12-30',ids=fixed)
 daily=x['runner']['daily'];assert all(r['at'].year==2022 for r in daily)
 rows=[];rounds=[];stocks=[];warnings=[];summaries={}
 for a,v in x['accounts'].items():
  assert v['initial_cash']==D(1200000)
  ds=sorted([r for r in daily if r['account']==a],key=lambda r:r['at']);end=ds[-1];days=[r['at'].date()for r in ds]
  marks=market.marks(end['at'],end['positions']);prices={s:m.cny_price(end['at'])for s,m in marks.items()}
  inv=sum((D(q)*prices[s]for s,q in end['positions'].items()),Z);assert abs(inv-end['inventory'])<D('1e-8')
  snap={r['id']:r for r in end['layers']};layers=[]
  for r in v['layers']:
   assert r['opened'].year==2022
   q=dict(snap[r['id']])if r['qty'] else dict(r)
   if r['qty']:assert q['qty']==r['qty']and q['cash']==r['cash']and q['dividend']==r['dividend']
   q['pnl']=q['cash']+q['dividend']+(D(q['qty'])*prices[q['sid']]if q['qty'] else Z);q['account']=a
   q['calendar_days']=((q['closed']or end['at'])-q['opened']).total_seconds()/86400
   q['common_sessions']=bisect_left(days,(q['closed']or end['at']).date())-bisect_left(days,q['opened'].date())+1
   layers.append(q);rows.append(q)
  net=sum((r['pnl']for r in layers),Z);assert abs(net-(end['nav']-v['initial_cash']))<D('1e-8'),('layer account bridge',a,net)
  # Exact remaining-cost replay: FIFO within a layer, same split rounding allocation as native.
  positions={};cost={};realized=Z
  actions=[(r['at'],0,i,r)for i,r in enumerate(v['journal'])if r['kind']=='actual_split']
  trades=[(r['at'],1,i,r)for i,r in enumerate(v['trades'])]
  buycost={};fees=Z;slip=Z
  for at,kind,idx,t in sorted(actions+trades,key=lambda q:q[:3]):
   if kind==0:
    live=[k for k in positions if positions[k]['sid']==t['sid']and positions[k]['qty']>0];old=sum(positions[k]['qty']for k in live)
    if not old:continue
    ratio=D(str(t['ratio']));target=int(D(old)*ratio);parts=[int(D(positions[k]['qty'])*ratio)for k in live]
    for i in range(target-sum(parts)):parts[i%len(parts)]+=1
    for k,q in zip(live,parts):
     positions[k]['qty']=q
     if q==0:realized-=cost[k];cost[k]=Z
   elif t['side']=='buy':
    k=t['layer'];positions[k]=dict(sid=t['security_id'],qty=t['shares']);cost[k]=t['gross_cny']+t['fees_cny'];buycost[k]=cost[k]
   else:
    for part in t['parts']:
     k=part['layer'];qty=part['shares'];allocated=cost[k]*D(qty)/D(positions[k]['qty']);realized+=part['net_cash']-allocated;cost[k]-=allocated;positions[k]['qty']-=qty
  for r in layers:assert positions[r['id']]['qty']==r['qty'],('split/sale quantity replay',a,r['id'])
  unrealized=inv-sum(cost.values(),Z);div=sum((r['dividend']for r in layers),Z);assert abs(realized+unrealized+div-net)<D('1e-8')
  for t in v['trades']:
   fees+=t['fees_cny'];slip+=D(t['shares'])*abs(t['price']-t['raw_open'])
   f=market.raw[t['security_id']];d=pd.Timestamp(t['at'].date());bar=f.loc[d]if d in f.index else None
   flags=[]
   if bar is None:flags.append('MISSING_DAY_ROW')
   else:
    if bar.high==bar.low:flags.append('FULLDAY_H_EQUALS_L')
    if bar.open==bar.high==bar.low==bar.close:flags.append('FULLDAY_OHLC_EQUAL')
    if pd.isna(bar.volume)or not np.isfinite(bar.volume)or bar.volume<=0:flags.append('FULLDAY_VOLUME_MISSING_OR_NONPOSITIVE')
    elif t['shares']>bar.volume:flags.append('FILL_SHARES_GT_FULLDAY_VOLUME')
   if flags:warnings.append(dict(account=a,day=str(d.date()),sid=t['security_id'],side=t['side'],shares=t['shares'],gross=t['gross_cny'],flags='|'.join(flags)))
  # Merge strictly overlapping holding intervals per stock; a same-timestamp full exit/re-entry starts a new round.
  local=[]
  for sid in sorted({r['sid']for r in layers}):
   group=sorted([r for r in layers if r['sid']==sid],key=lambda r:(r['opened'],r['id']));cur=[];right=None
   def emit(cur):
    if not cur:return
    opened=min(r['opened']for r in cur);closed=max(r['closed']for r in cur)if all(r['closed']is not None for r in cur)else None
    result=dict(account=a,sid=sid,id=len(local)+1,opened=opened,closed=closed,layers=len(cur),core_layers=sum(r['kind']=='core'for r in cur),mobile_layers=sum(r['kind']=='add'for r in cur),pnl=sum((r['pnl']for r in cur),Z),buy_cost_including_fees=sum((buycost[r['id']]for r in cur),Z),calendar_days=((closed or end['at'])-opened).total_seconds()/86400,layer_ids=[r['id']for r in cur]);local.append(result)
   for r in group:
    if cur and right is not None and r['opened']>=right:emit(cur);cur=[];right=None
    cur.append(r)
    if r['closed']is None:right=None
    elif len(cur)==1:right=r['closed']
    elif right is not None:right=max(right,r['closed'])
   emit(cur)
  assert abs(sum((r['pnl']for r in local),Z)-net)<D('1e-8');rounds.extend(local)
  stock={s:sum((r['pnl']for r in layers if r['sid']==s),Z)for s in {r['sid']for r in layers}}
  for s,pnl in stock.items():stocks.append(dict(account=a,sid=s,pnl=pnl))
  closed=[r for r in layers if not r['qty']];closedround=[r for r in local if r['closed']is not None]
  lossabs=sum((-p for p in stock.values()if p<0),Z);top10=sum((-p for p in sorted(stock.values())[:10]if p<0),Z)
  summaries[a]=dict(initial_cash=str(v['initial_cash']),year_end_NAV=str(end['nav']),net_PnL=str(net),return_fraction=float(net/v['initial_cash']),realized_sale_PnL_including_allocated_buy_and_sell_fees=str(realized),unrealized_mark_minus_remaining_fee_inclusive_cost=str(unrealized),dividend_accrual_income=str(div),explicit_fees_already_in_PnL=str(fees),embedded_5bp_price_slippage_already_in_PnL=str(slip),fixed_fill_PnL_before_fees=str(net+fees),fixed_fill_PnL_before_fees_and_embedded_slippage=str(net+fees+slip),closed_layer_net=str(sum((r['pnl']for r in closed),Z)),live_layer_net=str(sum((r['pnl']for r in layers if r['qty']),Z)),closed_layer_stats=stats(closed),closed_stock_round_stats=stats(closedround),all_layers=len(layers),all_stock_rounds=len(local),live_stock_rounds=len(local)-len(closedround),max_layers_one_round=max(r['layers']for r in local),mean_inventory_fraction=float(np.mean([float(r['inventory']/r['nav'])for r in ds])),mean_stocks=float(np.mean([len(r['positions'])for r in ds])),max_stocks=max(len(r['positions'])for r in ds),gross_losing_stock_PnL=str(lossabs),worst10_stock_loss_share=float(top10/lossabs),core_layer_net=str(sum((r['pnl']for r in layers if r['kind']=='core'),Z)),mobile_layer_net=str(sum((r['pnl']for r in layers if r['kind']=='add'),Z)),bridges_pass=True)
  print(a,json.dumps(summaries[a],default=str),flush=True)
 pd.DataFrame(rows).to_csv(O/'LAYER_PNL_2022.csv',index=False);pd.DataFrame(rounds).to_csv(O/'STOCK_ROUNDS_2022.csv',index=False);pd.DataFrame(stocks).to_csv(O/'STOCK_PNL_2022.csv',index=False);pd.DataFrame(warnings).to_csv(O/'POSTHOC_EXECUTION_WARNINGS_2022.csv',index=False)
 save('SUMMARY.json',dict(status='PASS_2022_LAYER_AND_ROUND_ATTRIBUTION',account_runs=0,checkpoint=str(P),checkpoint_sha256=h,checkpoint_at=str(x['last_completed_event']),summary=summaries,definitions=['A buy layer is one actual buy fill, not an independent strategy trade.','A stock round merges overlapping layer holding intervals from zero inventory back to zero. Same timestamp closed/reopened is a new round.','Account PnL includes all layers, marked inventory and accrued dividends.','Realized/unrealized split uses exact fee-inclusive remaining-cost allocation and native split rounding replay. Dividend accrual is shown separately.','Slippage is already in execution prices; fee/slippage addbacks are fixed-fill accounting diagnostics, not counterfactual NAV or recoverable profit.','Year-end live layers use 2022-12-30 daily snapshots, never later layer terminal values.','Full-day execution warnings are posthoc only; not official halt/limit or tradability judgements.']))
 save('OUTPUT_SHA256.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
if __name__=='__main__':main()
