"""Independent cash/share replay; no new strategy calculations or retries."""
from common_abcd import *
import gzip,collections
from decimal import Decimal as D
import pandas as pd
sys.path.append(str(OLD/'code'));sys.path.append(str(SRC/'code'))
import analyze_accounts as audit
from analyze_ix import IndependentPrices
from runner_abcd import encoded

def folders():return [HERE/'technical/A-controls',HERE/'accounts']
def stream(name):
 for folder in folders():
  with gzip.open(folder/(name+'.jsonl.gz'),'rt') as f:
   for line in f:yield json.loads(line)
def account_path(aid):return (folders()[0] if aid.startswith('A__') else folders()[1])/(aid+'.json')

def main():
 out=HERE/'analysis';out.mkdir(exist_ok=False);daily=collections.defaultdict(list)
 for row in stream('daily'):daily[row['account']].append(row)
 assert len(daily)==12
 meta=read(OLD/'inputs-v2/metadata.json');prices=IndependentPrices();calendar=[audit.t(x) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']]
 board=np.load(HERE/'prepared/dual-board.npz');dates=pd.DatetimeIndex(board['dates']);columns={str(s):j for j,s in enumerate(board['symbols'])};gates=board['gate']
 buy={s:set(d) for s,d in read(HERE/'prepared/buy-events.json').items()}
 results=[];campaigns=[];contrib=[];curves=[];annual=[];fills=[];audits=[];rotations=[]
 for full,rows in daily.items():
  mode,aid=full.split('__',1);obj=read(account_path(full));details=[]
  camps,receipt=audit.audit_account(aid,obj,rows,prices,meta,calendar,details);receipt['account']=full;audits.append(receipt)
  for c in camps:c.update(account=full,scheme=mode,scenario=aid.split('_')[1])
  campaigns+=camps
  for c in details:c.update(account=full,scheme=mode)
  contrib+=details
  f=pd.DataFrame(rows);f['date']=pd.to_datetime(f['at'],utc=True).dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
  for col in ['nav','inventory','available','fees_cny']:f[col]=f[col].astype(float)
  nav=f.nav.to_numpy();dd=nav/np.maximum.accumulate(np.r_[1e6,nav])[1:]-1;exposure=f.inventory/f.nav
  closed=[c for c in camps if c['closed']];tail=sum((c['net_pnl'] for c in closed if c['tail_closed']),D(0));ordinary=sum((c['net_pnl'] for c in closed if not c['tail_closed']),D(0));opened=sum((c['net_pnl'] for c in camps if not c['closed']),D(0))
  assert abs(tail+ordinary+opened-D(receipt['total_expenses'])-D(str(rows[-1]['nav']))+D(1000000))<D('1e-8')
  rotation_events=[x for x in obj['audit_log'] if x['kind']=='portfolio_rotation_request']
  results.append(dict(account=full,scheme=mode,scenario=aid.split('_')[1],net_return=nav[-1]/1e6-1,cagr=(nav[-1]/1e6)**(365.25/(f.date.iloc[-1]-pd.Timestamp('2015-01-01')).days)-1,max_drawdown=float(-dd.min()),final_nav=float(nav[-1]),mean_exposure=float(exposure.mean()),fees_cny=float(f.fees_cny.iloc[-1]),closed_campaigns=len(closed),win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed) if closed else None,tail_closed_profit=float(tail),ordinary_closed_pnl=float(ordinary),open_campaign_pnl=float(opened),noncampaign_expenses=float(receipt['total_expenses']),unique_stocks=len(set(c['symbol'] for c in camps)),rotation_requests=len(rotation_events),sector_rotation_requests=sum(x['rotation_kind']=='sector' for x in rotation_events),max_stock_weight=receipt['max_stock_weight'],max_sector_weight=receipt['max_sector_weight']))
  for i,r in f.iterrows():curves.append(dict(account=full,scheme=mode,scenario=aid.split('_')[1],date=str(r.date.date()),nav=float(r.nav),drawdown=float(dd[i]),exposure=float(exposure.iloc[i]),cash=float(r.available)))
  previous=1e6
  for year,g in f.groupby(f.date.dt.year):
   x=g.nav.to_numpy();annual.append(dict(account=full,scheme=mode,scenario=aid.split('_')[1],year=int(year),net_return=float(x[-1]/previous-1),max_drawdown=float(-(x/np.maximum.accumulate(np.r_[previous,x])[1:]-1).min())));previous=float(x[-1])
  reservations={x['order_id']:x for x in obj['audit_log'] if x['kind']=='reserve'}
  for x in obj['audit_log']:
   if x['kind']!='fill':continue
   z=x['receipt'];fills.append(dict(account=full,scheme=mode,**z))
   if z['side']=='buy':
    sid=z['security_id'];day=reservations[x['order_id']]['decision_at'][:10];assert day in buy.get(sid,set());assert audit.t(z['at']).date()>audit.t(day).date()
    if mode in ['B','D']:
     i=dates.get_loc(day);assert gates[i,columns[sid]]==1 and gates[i,columns[meta[sid]['sector_id']]]==1
  for e in rotation_events:
   sold=[z for z in obj['fills'] if z['side']=='sell' and z['security_id'] in e['outgoing_stocks'] and audit.t(z['at'])>audit.t(e['at'])]
   first_sale=min((z['at'] for z in sold),default=None)
   rotations.append(dict(account=full,scheme=mode,**e,first_actual_sale=first_sale))
  print(dict(audited=full,rows=len(rows),closed=len(closed)),flush=True)
 for name,rs in [('summary',results),('campaigns',campaigns),('curves',curves),('annual',annual),('daily-stock-contributions',contrib),('fills',fills),('rotations',rotations)]:
  pd.DataFrame(rs).to_csv(out/f'{name}.csv',index=False);write(out/f'{name}.json',encoded(rs))
 write(out/'accounting-audit.json',dict(recorded_at=now(),passed=True,accounts=len(audits),all_actual_buys_original_IX_events=True,all_dual_buys_current_gates=True,details=audits))
 for name,key in [('stocks','symbol'),('industries','industry')]:
  a=pd.DataFrame(campaigns);a['net_pnl']=a.net_pnl.astype(float);a.groupby(['account','scheme',key],dropna=False).agg(net_pnl=('net_pnl','sum'),campaigns=('net_pnl','size')).reset_index().to_csv(out/f'actual-{name}.csv',index=False)
 print(pd.DataFrame(results).query("scenario=='base'").to_string(index=False),flush=True)
if __name__=='__main__':main()
