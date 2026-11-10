from common import *
import gzip,collections
from decimal import Decimal as D
sys.path.append(str(OLD/'code'));sys.path.append(str(IX/'code'));from analyze_ix import IndependentPrices
import analyze_accounts as audit

def main(include_first=False):
 out=HERE/('financial-analysis-5' if include_first else 'financial-analysis-4');out.mkdir(exist_ok=False);dirs=[HERE/'accounts']+([HERE/'first-account/accounts'] if include_first else []);meta=read(OLD/'inputs-v2/metadata.json');prices=IndependentPrices();calendar=[audit.t(x) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']];rows=[];curves=[];camps=[];receipts=[]
 for folder in dirs:
  daily=collections.defaultdict(list)
  with gzip.open(folder/'daily.jsonl.gz','rt') as f:
   for line in f:r=json.loads(line);daily[r['account']].append(r)
  for aid,ds in daily.items():
   obj=read(folder/f'{aid}.json');cc,rc=audit.audit_account(aid.split('__')[1],obj,ds,prices,meta,calendar);rc['account']=aid;receipts.append(rc)
   for c in cc:c['account']=aid
   camps.extend(cc);f=pd.DataFrame(ds);nav=f.nav.astype(float).to_numpy();dd=nav/np.maximum.accumulate(np.r_[1e6,nav])[1:]-1;closed=[c for c in cc if c['closed']];tail=sum((c['net_pnl'] for c in closed if c['tail_closed']),D(0));ordinary=sum((c['net_pnl'] for c in closed if not c['tail_closed']),D(0))
   rows.append(dict(account=aid,net_return=nav[-1]/1e6-1,max_drawdown=float(-dd.min()),final_nav=nav[-1],exposure=float((f.inventory.astype(float)/f.nav.astype(float)).mean()),closed=len(closed),win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed) if closed else None,tail_pnl=float(tail),ordinary_pnl=float(ordinary),fees=float(f.fees_cny.iloc[-1]),unique_stocks=len({c['symbol'] for c in cc})))
   for i,d in enumerate(ds):curves.append(dict(account=aid,date=d['at'][:10],nav=float(d['nav']),drawdown=float(dd[i]),exposure=float(d['inventory'])/float(d['nav'])))
 pd.DataFrame(rows).to_csv(out/'summary.csv',index=False);pd.DataFrame(curves).to_csv(out/'curves.csv',index=False)
 for c in camps:
  for k,v in c.items():
   if isinstance(v,D):c[k]=float(v)
 pd.DataFrame(camps).to_csv(out/'campaigns.csv',index=False);write(out/'accounting.json',dict(passed=True,accounts=len(receipts),rows=sum(r['checks']['daily_independent_nav_and_shares'] for r in receipts),max_error=str(max(D(r['max_absolute_nav_difference_cny']) for r in receipts)),receipts=receipts));print(pd.DataFrame(rows).to_string(index=False),flush=True)
if __name__=='__main__':main('--first' in sys.argv)
