"""Independent raw cash/share and sector ownership replays; no policy search."""
from budget_common import *
import collections,gzip
sys.path.append(str(OLD/'code'));sys.path.append(str(IX/'code'))
from analyze_ix import IndependentPrices
import analyze_accounts as audit
D=Decimal;ZERO=D(0);EPS=D('1e-18')

def owner_audit(obj,ds,owners,isolate):
 cash={s:D('333333.33') for s in SECTORS};cash[SECTORS[-1]]+=D(1000000)-sum(cash.values());fees={};settlement={};events=obj['audit_log'];i=0;maxerr=ZERO;minimum=dict(cash);count=0
 def at(e):return pd.Timestamp(e.get('at') or e.get('receipt',{}).get('at') or e.get('receivable',{}).get('ex_at'))
 for d in ds:
  cutoff=pd.Timestamp(d['at'])
  while i<len(events) and at(events[i])<=cutoff:
   e=events[i];i+=1;k=e['kind'];owner=owners[e['sid']] if 'sid' in e else None
   if k=='reserve':cash[owner]-=D(e['gross_budget_cny'])+D(e['fee_reserved_cny']);fees[e['order_id']]=D(e['fee_reserved_cny'])
   elif k=='release_buy':
    assert abs(fees[e['order_id']]-D(e['fee_released']))<EPS
    cash[owner]+=D(e['gross_released'])+D(e['fee_released']);del fees[e['order_id']]
   elif k=='fill':
    f=e['receipt'];owner=owners[f['security_id']];settlement[f['settlement_id']]=owner
    if f['side']=='buy':
     previous=fees[e['order_id']];topup=max(ZERO,D(f['fees_cny'])-previous);cash[owner]-=topup;fees[e['order_id']]=previous+topup-D(f['fees_cny'])
    else:cash[owner]+=min(ZERO,D(f['gross_cny'])-D(f['fees_cny']))
   elif k=='settle':
    s=e['settlement'];owner=settlement.pop(s['settlement_id'])
    if not s['debit']:cash[owner]+=D(s['cny_amount'])
   elif k=='dividend_payment':cash[owners[e['entitlement']['security_id']]]+=D(e['entitlement']['net_local'])*D(e['fx_rate'])
   elif k=='expense':raise AssertionError('Unattributed expense')
   for s in SECTORS:minimum[s]=min(minimum[s],cash[s])
   if isolate:assert min(cash.values())>=-EPS,(e,cash)
   count+=1
  err=max(abs(cash[s]-D(d['owner_cash'][s])) for s in SECTORS);maxerr=max(maxerr,err);assert err<EPS
  assert abs(sum(cash.values())-D(d['available']))<EPS
  assert len(set(d['positions'])|set(d['pending_buys']))<=6
  for s in SECTORS:assert sum(owners[x]==s for x in set(d['positions'])|set(d['pending_buys']))<=2
 assert i==len(events)
 return dict(passed=True,event_checks=count,daily_checks=len(ds),max_error_cny=maxerr,min_settled_available_by_owner=minimum)

def main():
 out=HERE/'analysis-v2';out.mkdir(exist_ok=False);daily=collections.defaultdict(list)
 with gzip.open(HERE/'accounts/daily.jsonl.gz','rt') as f:
  for l in f:x=json.loads(l);daily[x['account']].append(x)
 prices=IndependentPrices();meta=read(OLD/'inputs-v2/metadata.json');calendar=[audit.t(x) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']];owners={x['symbol']:x['sector'] for x in read(HERE/'scope.json')['chosen']};receipts=[];camps=[];curves=[];rows=[];flows=[]
 for aid,ds in daily.items():
  obj=read(HERE/f'accounts/{aid}.json');cc,rc=audit.audit_account('S0_base',obj,ds,prices,meta,calendar,flows);rc['account']=aid
  mode=aid.split('__')[0]
  if mode!='CONTROL':rc['ownership']=owner_audit(obj,ds,owners,mode=='ISOLATED')
  receipts.append(rc)
  for c in cc:c['account']=mode
  camps.extend(cc);f=pd.DataFrame(ds);nav=f.nav.astype(float).to_numpy();dd=nav/np.maximum.accumulate(np.r_[1e6,nav])[1:]-1;closed=[c for c in cc if c['closed']]
  side=read(HERE/f'accounts/{mode}-ownership.json') if mode!='CONTROL' else None
  rows.append(dict(account=mode,net_return=nav[-1]/1e6-1,max_drawdown=float(-dd.min()),final_nav=nav[-1],exposure=float((f.inventory.astype(float)/f.nav.astype(float)).mean()),closed=len(closed),win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed),tail_pnl=float(sum((c['net_pnl'] for c in closed if c['tail_closed']),ZERO)),ordinary_pnl=float(sum((c['net_pnl'] for c in closed if not c['tail_closed']),ZERO)),open_pnl=float(sum((c['net_pnl'] for c in cc if not c['closed']),ZERO)),fees=float(f.fees_cny.iloc[-1]),buy_fills=sum(x['side']=='buy' for x in obj['fills']),owner_gross_constraints=len(side['budget_constraints']) if side else None))
  for i,d in enumerate(ds):
   row=dict(account=mode,date=d['at'][:10],nav=float(d['nav']),drawdown=float(dd[i]),exposure=float(d['inventory'])/float(d['nav']))
   if mode!='CONTROL':row.update({s:float(v) for s,v in d['owner_cash'].items()})
   curves.append(row)
 pd.DataFrame(rows).to_csv(out/'summary.csv',index=False);pd.DataFrame(curves).to_csv(out/'curves.csv',index=False)
 pd.DataFrame(clean(camps)).to_csv(out/'campaigns.csv',index=False)
 cf=pd.DataFrame(clean(camps));cf['net_pnl']=cf.net_pnl.astype(float);cf['buy_gross']=cf.buy_gross.astype(float)
 cf.groupby(['account','industry','symbol','name']).agg(pnl=('net_pnl','sum'),buy_gross=('buy_gross','sum'),campaigns=('symbol','size')).reset_index().to_csv(out/'stocks.csv',index=False)
 write(out/'accounting.json',dict(passed=True,accounts=3,independent_daily_rows=sum(len(x) for x in daily.values()),max_error_cny=max(D(x['max_absolute_nav_difference_cny']) for x in receipts),receipts=receipts))
 # Pair actual entries by symbol and frozen IX episode, including repeated entries.
 signals={s:pd.read_parquet(IX/'signals'/f'{s}.parquet',columns=['ix_target']) for s in owners};episodes={}
 for s,f in signals.items():episodes[s]=(f.ix_target.astype(bool)&~f.ix_target.astype(bool).shift(fill_value=False)).cumsum()
 entries={}
 for mode in ['SHARED','ISOLATED']:
  obj=read(HERE/f'accounts/{mode}__S0_base.json');seq=collections.Counter();entries[mode]={}
  for c in [c for c in camps if c['account']==mode]:
   sid=c['symbol'];d=pd.Timestamp(c['entry_at']).tz_localize(None).normalize();e=int(episodes[sid].loc[:d].iloc[-1]);key=(sid,e);seq[key]+=1;entries[mode][(*key,seq[key])]=c
 paired=[]
 for key in sorted(set(entries['SHARED'])|set(entries['ISOLATED'])):
  a=entries['SHARED'].get(key);b=entries['ISOLATED'].get(key)
  paired.append(dict(symbol=key[0],episode=key[1],attempt=key[2],shared_entry=a['entry_at'] if a else None,isolated_entry=b['entry_at'] if b else None,shared_gross=float(a['buy_gross']) if a else 0,isolated_gross=float(b['buy_gross']) if b else 0,shared_pnl=float(a['net_pnl']) if a else 0,isolated_pnl=float(b['net_pnl']) if b else 0,entry_same=bool(a and b and a['entry_at']==b['entry_at'])))
 pf=pd.DataFrame(paired);pf['pnl_difference']=pf.isolated_pnl-pf.shared_pnl;pf.to_csv(out/'entry-pairs.csv',index=False)
 write(out/'mechanism.json',dict(same_entry_pairs=int(pf.entry_same.sum()),union_pairs=len(pf),isolated_only=int(pf.shared_entry.isna().sum()),shared_only=int(pf.isolated_entry.isna().sum()),same_entry_different_amount=int(((pf.shared_gross-pf.isolated_gross).abs().gt(.01)&pf.entry_same).sum()),difference_reconciles=float(pf.pnl_difference.sum())))
 print(pd.DataFrame(rows).to_string(index=False));print(pd.read_csv(out/'stocks.csv').to_string(index=False));print(read(out/'mechanism.json'))
if __name__=='__main__':main()
