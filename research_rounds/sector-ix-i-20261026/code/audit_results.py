"""Independently reconstruct real cash/share NAV and separate tails from costs."""
from sec_common import *
import collections,gzip,importlib.util
sys.path.insert(0,str(OLD/'code'));sys.path.append(str(IX/'code'))
from analyze_ix import IndependentPrices
spec=importlib.util.spec_from_file_location('original_finance_auditor',OLD/'code/analyze_accounts.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
D=Decimal;ZERO=D(0)

def main():
 out=HERE/'analysis-v2';out.mkdir(exist_ok=False);daily=collections.defaultdict(list)
 with gzip.open(HERE/'accounts-v2/daily.jsonl.gz','rt') as f:
  for l in f:r=json.loads(l);daily[r['account']].append(r)
 meta=read(OLD/'inputs-v2/metadata.json');scope=read(HERE/'scope.json');meta={s:dict(v) for s,v in meta.items()}
 for s in scope['groups']['DRUG']:meta[s]['sector_id']=GROUPS['DRUG'][1];meta[s]['industry']='创新药'
 prices=IndependentPrices();calendar=[audit.t(x) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']];rows=[];curves=[];camps=[];receipts=[];controls={}
 olddaily=collections.defaultdict(list)
 with gzip.open(PREV/'accounts/daily.jsonl.gz','rt') as f:
  for l in f:r=json.loads(l);olddaily[r['account']].append(r)
 for aid,ds in daily.items():
  group,policy=aid.split('__')[0].split('_');obj=read(HERE/f'accounts-v2/{aid}.json');cc,rc=audit.audit_account('S1_base',obj,ds,prices,meta,calendar);rc['account']=aid;receipts.append(rc)
  for c in cc:c.update(account=aid,group=group,policy=policy,source_industry=scope['meta'][c['symbol']]['industry'])
  camps.extend(cc);f=pd.DataFrame(ds);nav=f.nav.astype(float).to_numpy();dd=nav/np.maximum.accumulate(np.r_[1e6,nav])[1:]-1;closed=[c for c in cc if c['closed']];tail=[c for c in closed if c['tail_closed']];ordinary=[c for c in closed if not c['tail_closed']];openpnl=sum((c['net_pnl'] for c in cc if not c['closed']),ZERO)
  rows.append(dict(group=group,policy=policy,account=aid,net_return=nav[-1]/1e6-1,max_drawdown=float(-dd.min()),final_nav=nav[-1],exposure=float((f.inventory.astype(float)/f.nav.astype(float)).mean()),closed=len(closed),win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed) if closed else None,tail_trades=len(tail),tail_pnl=float(sum((c['net_pnl'] for c in tail),ZERO)),ordinary_pnl=float(sum((c['net_pnl'] for c in ordinary),ZERO)),open_pnl=float(openpnl),fees=float(f.fees_cny.iloc[-1]),unique_stocks=len({c['symbol'] for c in cc}),max_stock_weight=rc['max_stock_weight'],max_sector_weight=rc['max_sector_weight']))
  assert abs(sum((c['net_pnl'] for c in cc),ZERO)-(D(ds[-1]['nav'])-D(1000000)))<D('1e-8')
  for i,d in enumerate(ds):
   assert len(set(d['positions'])|set(d['pending_buys']))<=6
   curves.append(dict(group=group,policy=policy,date=d['at'][:10],nav=float(d['nav']),drawdown=float(dd[i]),exposure=float(d['inventory'])/float(d['nav'])))
  if group in ['SEMI','COMM'] and policy=='IX':
   oldaid=group+'__S1_base';assert obj==read(PREV/f'accounts/{oldaid}.json'),(group,'original financial identity')
   def dropaccount(x):return {k:v for k,v in x.items() if k!='account'}
   assert [dropaccount(x) for x in ds]==[dropaccount(x) for x in olddaily[oldaid]];controls[group]=dict(full_financial_json_exact=True,daily_rows=len(ds))
 pd.DataFrame(rows).to_csv(out/'summary.csv',index=False);pd.DataFrame(curves).to_csv(out/'curves.csv',index=False);pd.DataFrame(clean(camps)).to_csv(out/'campaigns.csv',index=False)
 cf=pd.DataFrame(clean(camps));cf['net_pnl']=cf.net_pnl.astype(float);cf['buy_gross']=cf.buy_gross.astype(float)
 stock=cf.groupby(['group','policy','symbol','name','source_industry']).agg(net_pnl=('net_pnl','sum'),campaigns=('symbol','size'),closed=('closed','sum'),tail_trades=('tail_closed','sum'),buy_gross=('buy_gross','sum')).reset_index();stock.to_csv(out/'stocks.csv',index=False)
 winners=[]
 for group in scope['groups']:
  gg=stock[stock.group==group];sids=set(gg.nlargest(3,'net_pnl').symbol)|({'688256.SH','300308.SZ','300502.SZ'}&set(scope['groups'][group]))
  for sid in sorted(sids):
   r=dict(group=group,symbol=sid,name=scope['meta'][sid]['name'])
   for policy in ['IX','I']:
    a=group+'_'+policy+'__S1_base';g=gg[(gg.symbol==sid)&(gg.policy==policy)];r.update({policy+'_pnl':float(g.net_pnl.sum()),policy+'_campaigns':int(g.campaigns.sum()),policy+'_tail_trades':int(g.tail_trades.sum()),policy+'_held_days':sum(d['positions'].get(sid,0)>0 for d in daily[a])})
   winners.append(r)
 pd.DataFrame(winners).to_csv(out/'winner-retention.csv',index=False)
 # Same opportunities/RS; only occupancy and active targets may differ.
 eligibility={};elig_checks=0
 with gzip.open(HERE/'accounts-v2/decisions.jsonl.gz','rt') as f:
  for l in f:
   r=json.loads(l);g,p=r['account'].split('__')[0].split('_');key=(g,r['at'])
   if p=='IX':eligibility[key]=r['eligible']
   else:assert eligibility[key]==r['eligible'];elig_checks+=1
 write(out/'accounting.json',dict(passed=True,accounts=8,daily_rows=sum(len(x) for x in daily.values()),max_absolute_nav_error_cny=max(D(x['max_absolute_nav_difference_cny']) for x in receipts),receipts=receipts,old_same_period_controls=controls,same_candidate_list_checks=elig_checks))
 print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(winners).to_string(index=False));print(dict(audit=True,controls=controls))
if __name__=='__main__':main()
