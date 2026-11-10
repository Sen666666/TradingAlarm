"""Read-only independent money/share replay and the fixed economic comparisons."""
from pathlib import Path
import gzip,json,csv,collections,math
from decimal import Decimal as D
import pandas as pd,numpy as np
from build_inputs import HERE,read,write,ref,now

ZERO=D(0);ONE=D(1)
def dec(x):return D(str(x))
def t(x):return pd.Timestamp(x)
def export(path,rows):
 pd.DataFrame(rows).to_csv(path,index=False,encoding='utf-8-sig')

class Prices:
 def __init__(self):
  self.records={x['series_id']:x for x in read(HERE/'inputs-v2/input-manifest.json')['series']};self.cache={}
 def mark(self,sid,day):
  if sid not in self.cache:
   r=self.records[sid];f=pd.read_parquet(r['raw']['path']);d=pd.DatetimeIndex(pd.to_datetime(f.trade_date if 'trade_date' in f else f.index));
   a=read(r['adjustment']['actions']['path'])['events'];self.cache[sid]=(d,f.close.to_numpy(),a)
  d,c,a=self.cache[sid];i=d.searchsorted(pd.Timestamp(day),side='right')-1
  assert i>=0
  p=dec(c[i]);old=d[i].date().isoformat()
  for e in a:
   if old<e['effective_date']<=day:
    p=(p-dec(e.get('signal_cash_per_old_share',e['cash_per_old_share'])))/dec(e.get('signal_split_ratio',e['split_ratio']))
  return p

def audit_account(aid,obj,daily,prices,meta,calendar,contributions=None):
 orders={};q=collections.defaultdict(int);lots=collections.defaultdict(list);campaigns={};closed=[]
 cash=D(1_000_000);divtotal=ZERO;fee=ZERO;expenses=ZERO;events=[];checks=collections.Counter();max_error=ZERO;previous_values={};previous_nav=D(1_000_000);max_stock_weight=ZERO;max_sector_weight=ZERO
 def camp(sid,at):
  if sid not in campaigns:campaigns[sid]=dict(account=aid,symbol=sid,entry_at=at,exit_at=None,buy_gross=ZERO,buy_fees=ZERO,sell_gross=ZERO,sell_fees=ZERO,dividends=ZERO,buy_fills=0,sell_fills=0,first_buy_at=at)
  return campaigns[sid]
 def finish(sid,at,is_closed,mark=ZERO):
  c=campaigns.pop(sid);c.update(exit_at=at if is_closed else None,closed=is_closed,final_shares=q[sid],market_value=mark,
    name=meta[sid]['name'],industry=meta[sid]['industry'],sector_id=meta[sid]['sector_id'])
  c['net_pnl']=c['sell_gross']+mark+c['dividends']-c['buy_gross']-c['buy_fees']-c['sell_fees']
  basis=c['buy_gross']+c['buy_fees'];c['net_return']=float(c['net_pnl']/basis) if basis else None
  c['tail_closed']=bool(is_closed and c['net_return'] is not None and c['net_return']>=.30);closed.append(c)
 for row in obj['audit_log']:
  k=row['kind']
  if k=='reserve':orders[row['order_id']]=t(row['decision_at'])
  elif k=='exit_request':orders[row['event_id']]=t(row['at'])
  elif k=='fill':
   receipt=row['receipt'];at=t(receipt['at']);sid=receipt['security_id'];side=receipt['side'];shares=receipt['shares']
   assert at>orders[row['order_id']],(aid,'same/future decision fill')
   assert sum((dec(v) for v in row['fee_components'].values()),ZERO)==dec(receipt['fees_cny'])
   assert dec(row['price'])*shares==dec(receipt['gross_cny'])
   slip=D('.001') if aid.endswith('cost2') else D('.0005')
   assert dec(row['price'])==dec(row['raw_open'])*(ONE+slip if side=='buy' else ONE-slip)
   events.append((at,k,row));checks['fills_causal_and_fee_components']+=1
  elif k in ('split','split_fraction_floor_proxy','expense'):
   events.append((t(row['at']),k,row))
  elif k=='dividend_accrual':events.append((t(row['receivable']['ex_at']),k,row))
 events.sort(key=lambda x:x[0]);cursor=0
 for d in daily:
  at=t(d['at']);day=str(at.date());flow=collections.defaultdict(lambda:ZERO);dayexpense=ZERO
  while cursor<len(events) and events[cursor][0]<=at:
   when,k,row=events[cursor];cursor+=1
   if k=='fill':
    f=row['receipt'];sid=f['security_id'];count=int(f['shares']);gross=dec(f['gross_cny']);cost=dec(f['fees_cny']);fee+=cost
    c=camp(sid,f['at'])
    if f['side']=='buy':
     q[sid]+=count;cash-=gross+cost;flow[sid]-=gross+cost;c['buy_gross']+=gross;c['buy_fees']+=cost;c['buy_fills']+=1
     later=[x for x in calendar if x.date()>when.date()];lots[sid].append([count,later[0]])
    else:
     available=sum(x[0] for x in lots[sid] if x[1]<=when);assert available>=count,(aid,sid,'T+1 violation')
     remaining=count
     for lot in lots[sid]:
      if lot[1]<=when:used=min(lot[0],remaining);lot[0]-=used;remaining-=used
     lots[sid]=[x for x in lots[sid] if x[0]];q[sid]-=count;cash+=gross-cost;flow[sid]+=gross-cost;c['sell_gross']+=gross;c['sell_fees']+=cost;c['sell_fills']+=1
     assert q[sid]>=0
     if not q[sid]:finish(sid,f['at'],True)
   elif k.startswith('split'):
    sid=row['sid'];old=q[sid];new=int(dec(old)*dec(row['ratio']));q[sid]=new
    if new>=old and new>old:lots[sid].append([new-old,t(row['new_shares_sellable_at'])])
    elif new<old:lots[sid]=[[new,t(row['new_shares_sellable_at'])]] if new else []
    checks['corporate_actions_replayed']+=1
   elif k=='dividend_accrual':
    e=row['receivable'];sid=e['security_id'];net=dec(e['net_local']);divtotal+=net;flow[sid]+=net
    assert sid in campaigns and q[sid]>0
    campaigns[sid]['dividends']+=net
   elif k=='expense':amount=dec(row['cny_amount']);cash-=amount;expenses+=amount;fee+=amount;dayexpense+=amount
  held={sid:n for sid,n in q.items() if n}
  assert held==d['positions'],(aid,day,'share mismatch',held,d['positions'])
  values={sid:dec(n)*prices.mark(sid,day) for sid,n in held.items()};inventory=sum(values.values(),ZERO)
  independent_nav=cash+divtotal+inventory;err=abs(independent_nav-dec(d['nav']));max_error=max(max_error,err)
  sectors=collections.defaultdict(lambda:ZERO)
  for sid,value in values.items():max_stock_weight=max(max_stock_weight,value/independent_nav);sectors[meta[sid]['sector_id']]+=value
  max_sector_weight=max(max_sector_weight,max(sectors.values(),default=ZERO)/independent_nav)
  assert err<D('0.00000001'),(aid,day,'NAV mismatch',str(err))
  attributed=ZERO
  for sid in set(previous_values)|set(values)|set(flow):
   pnl=values.get(sid,ZERO)-previous_values.get(sid,ZERO)+flow[sid];attributed+=pnl
   if contributions is not None:contributions.append(dict(account=aid,symbol=sid,date=day,net_contribution=pnl,market_value=values.get(sid,ZERO),shares=held.get(sid,0)))
  assert abs(attributed-dayexpense-(independent_nav-previous_nav))<D('.00000001')
  previous_values=values;previous_nav=independent_nav
  assert abs(fee-dec(d['fees_cny']))<D('0.00000001')
  ledger_nav=sum((dec(d[k]) for k in ['available','order_reserved','sale_receivable','dividend_receivable','inventory']),ZERO)
  assert abs(ledger_nav-dec(d['nav']))<D('0.00000001')
  assert all(dec(d[k])>=0 for k in ['available','order_reserved','sale_receivable','dividend_receivable','inventory'])
  if not aid.startswith('B0'):
   assert len(held)<=6 and len({meta[s]['sector_id'] for s in held})<=(1 if aid.startswith('S1') else 3)
  checks['daily_independent_nav_and_shares']+=1
 for sid in list(campaigns):finish(sid,None,False,dec(q[sid])*prices.mark(sid,str(t(daily[-1]['at']).date())))
 pnl=sum((x['net_pnl'] for x in closed),ZERO)-expenses
 assert abs(pnl-(dec(daily[-1]['nav'])-D(1_000_000)))<D('.00000001')
 return closed,dict(account=aid,passed=True,checks=dict(checks),max_absolute_nav_difference_cny=str(max_error),campaign_pnl_reconciled=True,total_expenses=str(expenses),max_stock_weight=float(max_stock_weight),max_sector_weight=float(max_sector_weight))

def main():
 source=HERE/'accounts-v2';summary=read(source/'summary.json');assert summary['historical_account_runs']==13 and 'failed' not in summary.get('status','')
 out=HERE/'analysis-v2';out.mkdir(exist_ok=False)
 daily=collections.defaultdict(list)
 with gzip.open(source/'daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line);daily[x['account']].append(x)
 meta=read(HERE/'inputs-v2/metadata.json');prices=Prices();calendar=[t(x) for x in read(HERE/'inputs-v2/market-rules.json')['calendars']['A']]
 results=[];years=[];stages=[];allcampaign=[];audits=[];fills=[];stockrows=[];sectorrows=[];curves=[];contributions=[]
 for aid,rows in daily.items():
  obj=read(source/(aid+'.json'));campaigns,audit=audit_account(aid,obj,rows,prices,meta,calendar,contributions if not aid.startswith('B0') else None);audits.append(audit);allcampaign+=campaigns
  frame=pd.DataFrame(rows);frame['date']=pd.to_datetime(frame['at'],utc=True).dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
  for c in ['nav','inventory','available','order_reserved','dividend_receivable','fees_cny']:frame[c]=frame[c].astype(float)
  frame['exposure']=frame.inventory/frame.nav;nav=frame.nav.to_numpy();peak=np.maximum.accumulate(np.r_[1e6,nav])[1:];dd=nav/peak-1
  closed=[x for x in campaigns if x['closed']];tail=sum((x['net_pnl'] for x in closed if x['tail_closed']),ZERO);ordinary=sum((x['net_pnl'] for x in closed if not x['tail_closed']),ZERO)
  loss=max(ZERO,-ordinary);openpnl=sum((x['net_pnl'] for x in campaigns if not x['closed']),ZERO)
  duration=(frame.date.iloc[-1]-pd.Timestamp('2015-01-01')).days/365.25
  losses=best=0
  for x in sorted(closed,key=lambda c:c['exit_at']):losses=losses+1 if x['net_pnl']<0 else 0;best=max(best,losses)
  results.append(dict(account=aid,final_nav=nav[-1],net_return=nav[-1]/1e6-1,cagr=(nav[-1]/1e6)**(1/duration)-1,max_drawdown=float(-dd.min()),
   mean_exposure=float(frame.exposure.mean()),ending_exposure=float(frame.exposure.iloc[-1]),fees_cny=float(frame.fees_cny.iloc[-1]),
   max_stock_weight=audit['max_stock_weight'],max_sector_weight=audit['max_sector_weight'],mean_reserved_fraction=float((frame.order_reserved/frame.nav).mean()),mean_cash_fraction=float((frame.available/frame.nav).mean()),
   ending_cash=float(frame.available.iloc[-1]),ending_reserved=float(frame.order_reserved.iloc[-1]),ending_dividend_receivable=float(frame.dividend_receivable.iloc[-1]),
   closed_campaigns=len(closed),open_campaigns=len(campaigns)-len(closed),win_rate=sum(x['net_pnl']>0 for x in closed)/len(closed) if closed else None,
   tail_closed_profit=float(tail),ordinary_closed_pnl=float(ordinary),ordinary_loss_vs_initial=float(loss/dec(1e6)),ordinary_loss_to_tail=float(loss/tail) if tail>0 else None,
   open_campaign_pnl=float(openpnl),max_consecutive_closed_losses=best,unique_stocks=len({f['security_id'] for f in obj['fills'] if f['side']=='buy'}),
   buy_fills=sum(f['side']=='buy' for f in obj['fills']),sell_fills=sum(f['side']=='sell' for f in obj['fills']),research_DD20_goal_met=bool(-dd.min()<=.2)))
  for kind,groups in [('year',[(str(y),frame.date.dt.year.eq(y)) for y in range(2015,2027)]),
   ('stage',[(name,frame.date.dt.year.between(lo,hi)) for name,lo,hi in [('2015–2017',2015,2017),('2018–2020',2018,2020),('2021–2023',2021,2023),('2024–截点',2024,2026)]])]:
   for label,mask in groups:
    part=frame.loc[mask]
    if part.empty:continue
    ix=part.index[0];base=frame.nav.iloc[ix-1] if ix else 1e6;v=part.nav.to_numpy();p=np.maximum.accumulate(np.r_[base,v])[1:]
    row=dict(account=aid,period=label,net_return=float(v[-1]/base-1),max_drawdown=float(-(v/p-1).min()),mean_exposure=float(part.exposure.mean()),start_nav=float(base),end_nav=float(v[-1]))
    (years if kind=='year' else stages).append(row)
  for f in obj['fills']:fills.append(dict(account=aid,**f,**{k:meta[f['security_id']][k] for k in ['name','industry','sector_id']}))
  for sid in sorted({x['symbol'] for x in campaigns}):
   cs=[x for x in campaigns if x['symbol']==sid]
   stockrows.append(dict(account=aid,symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],sector_id=meta[sid]['sector_id'],
    net_contribution=float(sum((x['net_pnl'] for x in cs),ZERO)),buy_gross=float(sum((x['buy_gross'] for x in cs),ZERO)),
    campaigns=len(cs),closed=sum(x['closed'] for x in cs),first_buy=min(x['entry_at'] for x in cs),open_pnl=float(sum((x['net_pnl'] for x in cs if not x['closed']),ZERO))))
  bysector=collections.defaultdict(list)
  for x in stockrows:
   if x['account']==aid:bysector[x['industry']].append(x)
  for g,xs in bysector.items():sectorrows.append(dict(account=aid,industry=g,net_contribution=sum(x['net_contribution'] for x in xs),buy_gross=sum(x['buy_gross'] for x in xs),unique_stocks=len(xs),stocks='、'.join(x['name'] for x in xs)))
  for i,row in frame.iterrows():curves.append(dict(account=aid,date=str(row.date.date()),nav=row.nav,drawdown=float(dd[i]),exposure=row.exposure))
  print({'account_audited':aid,'final_nav':nav[-1],'campaigns':len(campaigns)},flush=True)
 def serial(rows):return [{k:str(v) if isinstance(v,D) else v for k,v in x.items()} for x in rows]
 for name,rows in [('summary',results),('annual',years),('stages',stages),('campaigns',serial(allcampaign)),('fills',fills),('actual-stocks',stockrows),('actual-industries',sectorrows),('curves',curves)]:
  export(out/(name+'.csv'),rows);write(out/(name+'.json'),rows)
 export(out/'daily-stock-contributions.csv',serial(contributions))
 write(out/'independent-accounting.json',dict(recorded_at=now(),all_passed=all(x['passed'] for x in audits),accounts=audits,source=ref(source/'provenance.json'),
  note='Independent cash+dividends+actual-share valuation replay, actual split floor and T+1, all daily marks, causality/fee components; does not certify daily HLV proxy as exchange execution.'))

if __name__=='__main__':main()
