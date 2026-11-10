"""PVR2022 loss concentration and full trade paths, verified checkpoint only."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,pickle,hashlib,sys
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parents[1];sys.path.insert(0,str(ROOT/'inputs'));import continuous_inputs as C
P=ROOT/'run_1200000/latest_checkpoint/checkpoint-2022-12-30.pkl';Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,indent=2,default=str,allow_nan=False))
def main():
 b=P.read_bytes();h=hashlib.sha256(b).hexdigest();assert h==json.loads(P.with_suffix('.json').read_text())['sha256']==json.loads(P.with_suffix('.provenance.json').read_text())['checkpoint_sha256'];x=pickle.loads(b);del b
 a=x['accounts']['PVR'];assert a['initial_cash']==D(1200000)
 stock=[dict(r,pnl=D(r['pnl']))for r in csv.DictReader((O/'STOCK_PNL_2022.csv').open())if r['account']=='PVR'];stock.sort(key=lambda r:r['pnl']);ids=[r['sid']for r in stock[:10]]
 rounds=[dict(r,pnl=D(r['pnl']))for r in csv.DictReader((O/'STOCK_ROUNDS_2022.csv').open())if r['account']=='PVR'];complete=sorted([r for r in rounds if r['closed']],key=lambda r:r['pnl'])
 _,market,_=C.J.M.context('2022-12-30',ids=ids)
 ds=sorted([r for r in x['runner']['daily']if r['account']=='PVR'],key=lambda r:r['at']);end=ds[-1]
 maximum={s:dict(max_daily_close_shares=0,max_daily_close_market_value=Z,max_daily_close_NAV_fraction=Z,max_value_at=None)for s in ids}
 for r in ds:
  held={s:q for s,q in r['positions'].items()if s in ids}
  marks=market.marks(r['at'],held)
  for s,q in held.items():
   value=D(q)*marks[s].cny_price(r['at']);m=maximum[s];m['max_daily_close_shares']=max(m['max_daily_close_shares'],q);m['max_daily_close_NAV_fraction']=max(m['max_daily_close_NAV_fraction'],value/r['nav'])
   if value>m['max_daily_close_market_value']:m.update(max_daily_close_market_value=value,max_value_at=str(r['at']))
 details=[];paths=[]
 for s in ids:
  ts=[t for t in a['trades']if t['security_id']==s];splits=[r for r in a['journal']if r['kind']=='actual_split'and r['sid']==s];ls=[r for r in a['layers']if r['sid']==s];rs=[r for r in rounds if r['sid']==s]
  costs={};qtys={};realized=Z;cumQ=0;netpaid=Z
  events=[(t['at'],1,i,'trade',t)for i,t in enumerate(ts)]+[(r['at'],0,i,'split',r)for i,r in enumerate(splits)]
  for at,_,i,kind,t in sorted(events,key=lambda x:x[:3]):
   if kind=='split':
    ks=[k for k in qtys if qtys[k]>0];old=sum(qtys[k]for k in ks);target=int(D(old)*t['ratio']);qs=[int(D(qtys[k])*t['ratio'])for k in ks]
    for k in range(target-sum(qs)):qs[k%len(qs)]+=1
    for k,q in zip(ks,qs):qtys[k]=q
    cumQ=target;paths.append(dict(sid=s,at=str(at),event='SPLIT',split_ratio=str(t['ratio']),Q_after=cumQ,round_cumulative_net_paid=str(netpaid)));continue
   if t['side']=='buy':costs[t['layer']]=t['gross_cny']+t['fees_cny'];qtys[t['layer']]=t['shares'];cumQ+=t['shares'];netpaid+=t['gross_cny']+t['fees_cny']
   else:
    for p in t['parts']:
     k=p['layer'];alloc=costs[k]*D(p['shares'])/D(qtys[k]);realized+=p['net_cash']-alloc;costs[k]-=alloc;qtys[k]-=p['shares']
    cumQ-=t['shares'];netpaid-=t['gross_cny']-t['fees_cny']
   paths.append(dict(sid=s,at=str(at),event=t['side'].upper(),shares=t['shares'],raw_open=str(t['raw_open']),price=str(t['price']),gross=str(t['gross_cny']),fees=str(t['fees_cny']),kind=t.get('kind'),layer=t.get('layer'),parts=t.get('parts'),reason=t.get('reason'),Q_after=cumQ,round_cumulative_net_paid=str(netpaid)))
   if not cumQ:netpaid=Z
  endQ=end['positions'].get(s,0);assert cumQ==endQ
  inv=D(endQ)*market.marks(end['at'],[s])[s].cny_price(end['at'])if endQ else Z
  unrealized=inv-sum(costs.values(),Z);div=sum((r['dividend']for r in ls),Z);pnl=realized+unrealized+div;old=next(r['pnl']for r in stock if r['sid']==s);assert abs(pnl-old)<D('1e-8')
  for r in a['audit_log']:
   if r['kind']=='dividend_accrual'and r['receivable'].security_id==s:
    d=r['receivable'];paths.append(dict(sid=s,at=str(d.ex_at),event='DIVIDEND_ACCRUAL_NOT_CASH',net_entitlement=str(d.net_local),payment_at=str(d.paid_at)))
  worst=min(rs,key=lambda r:r['pnl']);cr=[r for r in rs if r['closed']];buy=[t for t in ts if t['side']=='buy'];sell=[t for t in ts if t['side']=='sell']
  details.append(dict(rank=len(details)+1,sid=s,annual_pnl=pnl,realized_sales_net=realized,unrealized_net=unrealized,dividend_accrual=div,explicit_fees_included=sum((t['fees_cny']for t in ts),Z),buy_fills=len(buy),sell_fills=len(sell),buy_shares_transaction_units=sum(t['shares']for t in buy),sell_shares_transaction_units=sum(t['shares']for t in sell),buy_gross=sum((t['gross_cny']for t in buy),Z),sell_gross=sum((t['gross_cny']for t in sell),Z),total_rounds=len(rs),closed_rounds=len(cr),losing_closed_rounds=sum(r['pnl']<0 for r in cr),winning_closed_rounds=sum(r['pnl']>0 for r in cr),open_rounds=len(rs)-len(cr),worst_round_pnl=worst['pnl'],worst_round_opened=worst['opened'],worst_round_closed=worst['closed'],worst_round_layers=worst['layers'],ending_shares=endQ,**maximum[s]))
 neg=sum((r['pnl']for r in stock if r['pnl']<0),Z);pos=sum((r['pnl']for r in stock if r['pnl']>0),Z);net=neg+pos;assert abs(net-(end['nav']-a['initial_cash']))<D('1e-8')
 bridge=dict(worst5=sum((r['pnl']for r in stock[:5]),Z),worst10=sum((r['pnl']for r in stock[:10]),Z),all_negative_stocks=neg,all_positive_stocks=pos,negative_stock_count=sum(r['pnl']<0 for r in stock),positive_stock_count=sum(r['pnl']>0 for r in stock),net=net)
 pd.DataFrame(details).to_csv(O/'PVR_WORST10_STOCK_DETAILS.csv',index=False);pd.DataFrame(complete[:10]).to_csv(O/'PVR_WORST10_COMPLETE_ROUNDS.csv',index=False);pd.DataFrame(sorted(paths,key=lambda r:(r['sid'],r['at'],r['event']))).to_csv(O/'PVR_WORST10_FULL_TRADE_PATHS.csv',index=False)
 save('PVR_WORST10_DETAILS.json',dict(checkpoint_sha256=h,bridge=bridge,stocks=details,worst_complete_rounds=complete[:10],notes=['Annual stock PnL = fee-inclusive realized + fee-inclusive unrealized at2022-12-30 +accrued dividends.','Negative-group total and positive-group offset are stated separately; no negative/net loss ratio is called contribution.','Maximum position quantities and market values are observed daily closing snapshots, not guaranteed intraday maxima.','Transaction share totals can change units at corporate actions; the full path records splits explicitly.','Stock rounds merge overlapping buy layers and end only at zero stock inventory.','Attribution is descriptive on the actual proxy path, not a removal-of-stock/module counterfactual.']))
 print(json.dumps(dict(bridge=bridge,stocks=details),default=str,indent=2),flush=True)
if __name__=='__main__':main()
