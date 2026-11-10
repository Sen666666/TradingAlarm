"""Independent raw-price cash/share accounting and descriptive statistics."""
from common import *
from decimal import Decimal as D
from collections import defaultdict
from bisect import bisect_right
import collections

old=import_path('tech_independent_audit',OLD/'code/analyze_accounts.py')
fund=import_path('tech_independent_funding',ROOT/'research_rounds/unlimited-capital-20261026/code/funding_audit.py');fund.PAD=D(1000000)

class IndependentPrices(old.Prices):
 def __init__(self):self.records={r['series_id']:r for r in read(CORE/'manifest.json')['series']};self.cache={}

def check_contract(aid,obj,ds,facts,records):
 intents={};rotations={};buy_ids={};checks=collections.Counter();mode=aid.split('__')[0];idx={str(pd.Timestamp(r['at']).date()):r for r in ds};sources={}
 rules=read(HERE/'execution-rules-v2.json');proto=read(OLD/'inputs-v2/economic-protocol.json')
 from market_rules import market_identity_on,version_on
 for r in obj['audit_log']:
  k=r['kind']
  if k=='entry_contract':
   intents[r['order_id']]=r;N=D(r['nav']);budget=D(r['budget']);assert budget<=N*(D('.075') if mode=='H50' else D('.15'))+D('.01'),(aid,k,budget,N)
   assert D(r['risk_budget'])==D('.01')*N;checks['entry_budgets']+=1
  elif k=='rotation_started':
   z=r['rotation'];day=r['at'][:10];new,held=z['candidate'],z['victim'];assert D(z['candidate_amount'])>=D('1.5')*D(z['victim_amount'])
   for sid,field in [(new,'candidate_amount'),(held,'victim_amount')]:
    if sid not in sources:sources[sid]=pd.read_parquet(records[sid]['raw']['path']).set_index('trade_date')
    v=sources[sid].loc[pd.Timestamp(day),'amount'];assert D(str(v))==D(z[field])
   f=facts[new];assert pd.Timestamp(day) in f.index and bool(f.loc[day,'i_buy']);rotations[z['id']]=dict(z);checks['rotation_original_amount_and_signal']+=1
  elif k=='rotation_buy_reserved':
   z=r['rotation'];assert z['id'] in rotations and z['candidate']==rotations[z['id']]['candidate'];assert z['sold_at'][:10]<=r['at'][:10];buy_ids[r['order_id']]=z;checks['paired_buy_reservation']+=1
  elif k=='risk_fill_bound':assert D(r['estimated_loss'])<=D(r['risk_budget']);checks['risk_open_bounds']+=1
  elif k=='fill' and r['receipt']['side']=='buy':
   oid=r['order_id'];f=r['receipt'];z=intents[oid];at=pd.Timestamp(f['at']);sid=f['security_id'];day=str(at.date());decision=pd.Timestamp(z['decision_at']);support=z['floor_signal']
   if mode!='BH':
    ff=facts[sid];j=ff.index.searchsorted(pd.Timestamp(day),side='right')-1;factor=D(str(ff.iloc[j].factor));assert support is not None and D(r['raw_open'])>D(support)/factor,(aid,sid,'open support violation')
   if mode=='RB1':
    identity=market_identity_on(rules,sid,at.date(),proto['approved_proxy_ids']);spec=version_on(rules['fee_versions'][identity['venue']],day,proto['approved_proxy_ids'])['schedule'];schedule=ledger.FeeSchedule(spec['schedule_id'],tuple(ledger.FeeComponent(**v) for v in spec['components']));mult=2 if aid.endswith('cost2') else 1;floor=D(support)/factor;stopprice=floor*(1-D('.0005')*mult);qty=int(f['shares']);stopfees=sum(schedule.incremental('sell',qty*stopprice,{}, {},mult,shares=qty,par_value=rules['security_metadata'].get(sid,{}).get('par_value')).values(),D(0));nominal=D(f['gross_cny'])+D(f['fees_cny'])-qty*stopprice+stopfees
    assert nominal<=D(z['risk_budget'])+D('1e-8'),(aid,sid,'actual fill exceeds nominal risk budget',nominal,z['risk_budget']);checks['independent_actual_fill_risk']+=1
   if oid in buy_ids:
    rr=buy_ids[oid];assert at>pd.Timestamp(rr['sold_at']);assert day<=rr['buy_deadline'];assert sid==rr['candidate'];checks['paired_actual_buy_after_sale']+=1
   elif mode!='BH':
    ff=facts[sid];day0=pd.Timestamp(decision.date());pol='ix' if mode=='IX' else 'e0' if mode=='E0' else 'i'
    if pol!='e0':assert day0 in ff.index and bool(ff.loc[day0,pol+'_buy']),(aid,sid,'not original entry event',day0)
   checks['actual_buy_contracts']+=1
 return dict(passed=True,checks=dict(checks))

def main(stage):
 source=HERE/('technical/short-v2' if stage=='short' else 'accounts-v2');out=HERE/('technical/short-analysis' if stage=='short' else 'analysis');out.mkdir(exist_ok=False);daily=defaultdict(list)
 for x in rows(source/'daily.jsonl.gz'):daily[x['account']].append(x)
 records={r['series_id']:r for r in read(CORE/'manifest.json')['series']};meta=read(OLD/'inputs-v2/metadata.json');facts={s:pd.read_parquet(PREP/'facts'/f'{s}.parquet') for s,r in records.items() if r['kind']=='stock'};prices=IndependentPrices();rules=read(HERE/'execution-rules-v2.json');calendar=sorted([old.t(x) for x in rules['calendars']['A']]+[old.t(f'2026-10-{d}T09:30:00+08:00') for d in ['27','28','29','30']]);result=[];curves=[];annual=[];campaigns=[];audits=[];funding=[];stocks=[];contributions=[];rotation_rows=[]
 for aid,ds in daily.items():
  obj=read(source/f'{aid}.json');cs,receipt=old.audit_account(aid,obj,ds,prices,meta,calendar,contributions);receipt['contracts']=check_contract(aid,obj,ds,facts,records);audits.append(receipt);final=dict(available=ds[-1]['available'],peak_funding=ds[-1]['peak_cash_committed']);funding.append(dict(account=aid,**fund.verify(obj['audit_log'],ds,final)))
  frame=pd.DataFrame(ds);frame['date']=pd.to_datetime(frame['at'],utc=True).dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
  frame=frame.loc[frame.date.ge('2024-01-01')].copy();nav=frame.nav.astype(float).to_numpy();mv=frame.inventory.astype(float).to_numpy();peak=np.maximum.accumulate(np.r_[1e6,nav])[1:];dd=1-nav/peak;closed=[c for c in cs if c['closed']];tails=[c for c in closed if c['tail_closed']];normal=[c for c in closed if not c['tail_closed']];tail=sum((c['net_pnl'] for c in tails),D(0));ordinary=sum((c['net_pnl'] for c in normal),D(0));opened=sum((c['net_pnl'] for c in cs if not c['closed']),D(0));loss=-sum((c['net_pnl'] for c in closed if c['net_pnl']<0),D(0));assert abs(tail+ordinary+opened-(D(ds[-1]['nav'])-D(1000000)))<D('1e-8')
  counts=ds[-1]['counts'];years=(frame.date.iloc[-1]-pd.Timestamp('2024-01-02')).days/365.25
  row=dict(account=aid,policy=aid.split('__')[0],scenario=aid.rsplit('_',1)[-1],final_nav=float(nav[-1]),net_profit=float(nav[-1]-1e6),net_return=float(nav[-1]/1e6-1),cagr=float((nav[-1]/1e6)**(1/years)-1),max_drawdown=float(dd.max()),max_drawdown_cny=float((peak-nav).max()),mean_exposure=float((mv/nav).mean()),peak_market_value=float(mv.max()),peak_cash_committed=float(D(ds[-1]['peak_cash_committed'])),fees=float(ds[-1]['fees_cny']),closed=len(closed),open=len(cs)-len(closed),win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed) if closed else None,tail_count=len(tails),tail_profit=float(tail),ordinary_profit=float(ordinary),open_profit=float(opened),all_closed_losses=float(loss),tail_over_all_losses=float(tail/loss) if loss else None,maximum_stock_weight=receipt['max_stock_weight'],maximum_sector_weight=receipt['max_sector_weight'],buy_fills=sum(f['side']=='buy' for f in obj['fills']),sell_fills=sum(f['side']=='sell' for f in obj['fills']),rotation_started=counts.get('rotation_started',0),rotation_sold=counts.get('rotation_sold',0),rotation_completed=counts.get('rotation_bought',0),rotation_sell_incomplete=counts.get('rotation_sell_incomplete',0),rotation_candidate_checks=counts.get('rotation_candidate_checks',0),rotation_no_feasible_victim=counts.get('rotation_no_feasible_victim',0),rotation_below_1_5=counts.get('rotation_below_1_5',0),open_support_reject=counts.get('open_support_reject',0),risk_rejections=sum(v for k,v in counts.items() if k.startswith('reject_risk')))
  result.append(row)
  for d,v,m,p,drop in zip(frame.date,nav,mv,peak,dd):curves.append(dict(account=aid,policy=row['policy'],scenario=row['scenario'],date=str(d.date()),nav=float(v),market_value=float(m),drawdown=float(drop),peak=float(p)))
  for year in sorted(frame.date.dt.year.unique()):
   mask=frame.date.dt.year.eq(year);part=frame.loc[mask];i=list(frame.index).index(part.index[0]);base=nav[i-1] if i else 1e6;v=part.nav.astype(float).to_numpy();peaks=np.maximum.accumulate(np.r_[base,v])[1:];annual.append(dict(account=aid,policy=row['policy'],scenario=row['scenario'],year=int(year),net_return=float(v[-1]/base-1),max_drawdown=float((1-v/peaks).max()),net_profit=float(v[-1]-base)))
  for c in cs:c.update(policy=row['policy'],scenario=row['scenario']);campaigns.append(c)
  bystock=defaultdict(list)
  for c in cs:bystock[c['symbol']].append(c)
  for s,ss in bystock.items():stocks.append(dict(account=aid,policy=row['policy'],scenario=row['scenario'],symbol=s,name=meta[s]['name'],industry=meta[s]['industry'],net_profit=float(sum((c['net_pnl'] for c in ss),D(0))),campaigns=len(ss)))
  swaps={};fill_by_order=defaultdict(list)
  for r in obj['audit_log']:
   if r['kind']=='fill':fill_by_order[r['order_id']].append(r['receipt'])
   if r['kind']=='rotation_started':swaps[r['rotation']['id']]=dict(account=aid,scenario=row['scenario'],**r['rotation'],status='open')
   if r['kind']=='rotation_buy_reserved':swaps[r['rotation']['id']].update(sold_at=r['rotation']['sold_at'],buy_order=r['order_id'])
   if r['kind']=='rotation_finished':swaps[r['rotation']['id']].update(status=r['reason'],**r['rotation'])
  for z in swaps.values():
   fills=fill_by_order.get(z.get('buy_order'),[]);z['actual_new_buy_fills']=len(fills);z['actual_new_buy_gross']=str(sum((D(f['gross_cny']) for f in fills),D(0)));z['first_new_buy_at']=fills[0]['at'] if fills else None;rotation_rows.append(z)
  print(dict(audited=aid,days=len(ds),fills=len(obj['fills'])),flush=True)
 for name,rs in [('summary',result),('curves',curves),('annual',annual),('campaigns',campaigns),('stocks',stocks),('contributions',contributions),('rotations',rotation_rows)]:pd.DataFrame(native.encoded(rs)).to_csv(out/f'{name}.csv',index=False)
 write(out/'accounting.json',dict(passed=True,accounts=len(audits),daily_rows=sum(len(x) for x in daily.values()),max_nav_difference=str(max(D(r['max_absolute_nav_difference_cny']) for r in audits)),receipts=audits));write(out/'funding.json',dict(passed=True,receipts=funding))
 print(dict(done=True,stage=stage,accounts=len(result)),flush=True)
if __name__=='__main__':main(sys.argv[1])
