"""Completed output only; no Account/Runner construction or strategy invocation."""
from pathlib import Path
import json,gzip,hashlib,argparse,sys
from decimal import Decimal as D
from bisect import bisect_left
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent.parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def gz(p):return json.load(gzip.open(p,'rt'))
def rows(p):return [json.loads(l)for l in gzip.open(p,'rt')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,default=str))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();out=args.out;assert not out.exists();run=args.run.resolve();base=ROOT/'run_1200000'
 pres={k:read(p/'PREDECLARED.json')for k,p in [('BASE_PVR',base),('NO_LOSS_ADD_PVR',run)]}
 for k,p in [('BASE_PVR',base),('NO_LOSS_ADD_PVR',run)]:
  assert read(p/'DONE.json')['completed'];assert pres[k]['end']=='2026-05-15';assert D(pres[k]['initial_cash_each'])==D(1200000)
  for src,h in pres[k]['source_freeze'].items():assert sha(src)==h,('source drift',src)
 assert pres['NO_LOSS_ADD_PVR']['arms']==['PVR'];out.mkdir(parents=True)
 daily={k:{r['at'][:10]:r for r in rows(p/'pair/daily.jsonl.gz')if r['account']=='PVR'}for k,p in [('BASE_PVR',base),('NO_LOSS_ADD_PVR',run)]};days=sorted(daily['BASE_PVR']);assert days==sorted(daily['NO_LOSS_ADD_PVR'])
 sys.path.insert(0,str(ROOT/'inputs'));import continuous_inputs as C
 ids=read(C.U/'FREEZE.json')['stocks'];_,market,_=C.J.M.context(days[-1],ids=ids);marks={};gap=Z
 for day in days:
  held=set().union(*(set(v[day]['positions'])for v in daily.values()));at=C.J.M.N.iso(daily['BASE_PVR'][day]['at']);marks[day]={s:m.cny_price(at)for s,m in market.marks(at,held).items()}
  for label,v in daily.items():
   inv=sum((D(q)*marks[day][s]for s,q in v[day]['positions'].items()),Z);gap=max(gap,abs(inv-D(v[day]['inventory'])));assert gap<D('1e-8')
 annual=[];period=[];rr=[];summary={}
 for label,path in [('BASE_PVR',base),('NO_LOSS_ADD_PVR',run)]:
  ds=[daily[label][d]for d in days];prev=D(pres[label]['initial_cash_each']);initial=prev;original={str(x['year']):x for x in read(path/'ANNUAL_METRICS.json')if x['account']=='PVR'}
  for year in sorted({d[:4]for d in days}):
   z=[r for r in ds if r['at'].startswith(year)];nav=np.array([float(prev)]+[float(r['nav'])for r in z]);ret=float(D(z[-1]['nav'])/prev-1);dd=float(np.min(nav/np.maximum.accumulate(nav)-1));ex=np.mean([float(D(r['inventory'])/D(r['nav']))for r in z]);assert abs(ret-original[year]['return_fraction'])<1e-12 and abs(dd-original[year]['max_drawdown_fraction'])<1e-12
   annual.append(dict(account=label,year=year,start_nav=str(prev),end_nav=z[-1]['nav'],return_fraction=ret,max_drawdown_fraction=dd,mean_inventory_fraction=ex,mean_stock_count=np.mean([len(r['positions'])for r in z])));prev=D(z[-1]['nav'])
  for r in ds:period.append(dict(account=label,day=r['at'][:10],nav=r['nav'],inventory=r['inventory'],exposure=float(D(r['inventory'])/D(r['nav'])),stock_count=len(r['positions']),ACT_on=r['on']))
  a=gz(path/'pair/PVR.json.gz');assert not any(r['qty']==0 and r['closed']is None for r in a['layers']),'Zero-quantity open layer invalidates interval merge';layers=[]
  for r in a['layers']:
   q=dict(r);q['pnl']=D(r['cash'])+D(r['dividend'])+(D(r['qty'])*marks[days[-1]][r['sid']]if r['qty']else Z);layers.append(q)
  net=sum((r['pnl']for r in layers),Z);assert abs(net-(D(ds[-1]['nav'])-initial))<D('1e-8')
  local=[]
  for sid in sorted({r['sid']for r in layers}):
   group=sorted([r for r in layers if r['sid']==sid],key=lambda r:(r['opened'],r['id']));cur=[];right=None
   def emit():
    if not cur:return
    closed=max(r['closed']for r in cur)if all(r['closed']for r in cur)else None
    local.append(dict(account=label,sid=sid,round_id=len(local)+1,opened=min(r['opened']for r in cur),closed=closed,layers=len(cur),pnl=sum((r['pnl']for r in cur),Z),ending_quantity=sum(r['qty']for r in cur),layer_ids=[r['id']for r in cur]))
   for r in group:
    if cur and right is not None and r['opened']>=right:emit();cur=[];right=None
    cur.append(r)
    if r['closed']is None:right=None
    elif len(cur)==1:right=r['closed']
    elif right is not None:right=max(right,r['closed'])
   emit()
  assert abs(sum((r['pnl']for r in local),Z)-net)<D('1e-8');rr+=local;closed=[r for r in local if r['closed']];wins=[r['pnl']for r in closed if r['pnl']>0];loss=[r['pnl']for r in closed if r['pnl']<0];nav=np.array([float(initial)]+[float(r['nav'])for r in ds]);mw=sum(wins,Z)/len(wins)if wins else None;ml=sum(loss,Z)/len(loss)if loss else None
  summary[label]=dict(total_pnl=str(net),final_nav=ds[-1]['nav'],max_drawdown_fraction=float(np.min(nav/np.maximum.accumulate(nav)-1)),first_recovery_above_initial=next((r['at'][:10]for r in ds if D(r['nav'])>initial),None),closed_rounds=len(closed),winning_rounds=len(wins),losing_rounds=len(loss),win_rate=len(wins)/len(closed),mean_win=str(mw),mean_loss=str(ml),payoff_ratio=float(mw/-ml)if mw is not None and ml else None,closed_round_net=str(sum((r['pnl']for r in closed),Z)),live_rounds=len(local)-len(closed),live_round_net=str(sum((r['pnl']for r in local if not r['closed']),Z)),fees=str(sum((D(t['fees_cny'])for t in a['trades']),Z)))
 closeyear=[]
 for label in daily:
  closed=[r for r in rr if r['account']==label and r['closed']]
  for year in sorted({r['closed'][:4]for r in closed}):
   z=[r for r in closed if r['closed'].startswith(year)];wins=[r['pnl']for r in z if r['pnl']>0];loss=[r['pnl']for r in z if r['pnl']<0];mw=sum(wins,Z)/len(wins)if wins else None;ml=sum(loss,Z)/len(loss)if loss else None
   closeyear.append(dict(account=label,close_year=year,n=len(z),wins=len(wins),losses=len(loss),flat=len(z)-len(wins)-len(loss),win_rate=len(wins)/len(z),mean_win=str(mw),mean_loss=str(ml),payoff_ratio=float(mw/-ml)if mw is not None and ml else None,net_pnl=str(sum((r['pnl']for r in z),Z)),attribution='Entire multi-year round PnL assigned to closing year for round statistics; not annual NAV PnL'))
 pd.DataFrame(closeyear).to_csv(out/'CLOSED_ROUNDS_BY_CLOSE_YEAR.csv',index=False)
 specified=[]
 for label,v in daily.items():
  for name,start,end in [('2024_0924_1008','2024-09-24','2024-10-08'),('2026_0115_0130','2026-01-15','2026-01-30')]:
   selected=[d for d in days if start<=d<=end];before=[d for d in days if d<start];initial=D(v[before[-1]]['nav'])if before else D(pres[label]['initial_cash_each']);nav=np.array([float(initial)]+[float(v[d]['nav'])for d in selected]);specified.append(dict(account=label,period=name,start=selected[0],end=selected[-1],start_nav=str(initial),end_nav=v[selected[-1]]['nav'],return_fraction=float(D(v[selected[-1]]['nav'])/initial-1),max_drawdown_fraction=float(np.min(nav/np.maximum.accumulate(nav)-1)),mean_inventory_fraction=np.mean([float(D(v[d]['inventory'])/D(v[d]['nav']))for d in selected])))
 pd.DataFrame(specified).to_csv(out/'SPECIFIED_PERIOD_COMPARISON.csv',index=False)
 labelsfile=ROOT.parent/'equal_entry_validation_v1/FIXED_ORIGINAL_I_ENTRY_LABELS.parquet';f=pd.read_parquet(labelsfile);f=f[f.sid.isin(ids)];big=f[f.complete60.eq(True)&f.mfe60.ge(.30)&f.ret60.ge(.20)];events=[]
 for row in big.to_dict('records'):
  day=str(row['entry_day'])[:10];k=bisect_left(days,day)
  if k>=len(days)or days[k]!=day or k+6>len(days):continue
  e=dict(sid=row['sid'],original_epoch=row['original_epoch'],entry_day=day,year=day[:4]);sid=row['sid']
  for label,v in daily.items():
   win=days[k:k+6];e[label+'_participated']=any(int(v[d]['positions'].get(sid,0))>0 for d in win);e[label+'_mean_NAV_fraction']=sum(float(D(v[d]['positions'].get(sid,0))*marks[d].get(sid,Z)/D(v[d]['nav']))for d in win)/6
  e['change']='BOTH'if e['BASE_PVR_participated']and e['NO_LOSS_ADD_PVR_participated']else'ADDED'if e['NO_LOSS_ADD_PVR_participated']else'LOST'if e['BASE_PVR_participated']else'NEITHER';events.append(e)
 ev=pd.DataFrame(events);ev.to_csv(out/'BIG60_EVENT_PARTICIPATION.csv',index=False);ev.groupby(['year','change']).size().rename('events').to_csv(out/'BIG60_ANNUAL_COUNTS.csv');ev[ev.change.isin(['ADDED','LOST'])].to_csv(out/'BIG60_ADDED_LOST.csv',index=False);ev.groupby('year')[[c for c in ev.columns if c.endswith('_mean_NAV_fraction')or c.endswith('_participated')]].mean().to_csv(out/'BIG60_ANNUAL_WEIGHTS_RATES.csv')
 ge=pd.DataFrame(rows(run/'PROFIT_GATE_EVENTS.jsonl.gz'));ge['year']=ge['at'].str[:4];ge['net_profit']=pd.to_numeric(ge.net_profit);ge['cost_exact']=ge.cost;ge['cost']=pd.to_numeric(ge.cost);ge.groupby(['year','allowed','reason']).agg(decisions=('sid','size'),unique_stocks=('sid','nunique'),sum_predecision_remaining_cost=('cost','sum')).to_csv(out/'GATE_DECISION_COUNTS.csv');ge.to_csv(out/'GATE_DECISIONS.csv',index=False)
 rejected=ge[~ge.allowed].copy();rejected['day']=rejected['at'].str[:10]
 rejected['raw_open_mark_minus_cost']=[str(D(str(q))*D(str(op))-D(str(cost)))for q,op,cost in zip(rejected.qty,rejected.known_open,rejected.cost_exact)]
 rejected['raw_vs_net_class']=['PRICE_LOSS_OR_FLAT'if D(v)<=0 else'PRICE_SMALL_PROFIT_INSUFFICIENT_FOR_SLIPPAGE_AND_ESTIMATED_SELL_FEE'for v in rejected.raw_open_mark_minus_cost]
 rejected.to_csv(out/'GATE_REJECTIONS_RAW_VS_NET.csv',index=False)
 rejected.drop_duplicates(['sid','day','raw_vs_net_class']).groupby(['year','raw_vs_net_class']).size().rename('unique_stock_days_with_class').to_csv(out/'GATE_RAW_VS_NET_STOCK_DAY_COUNTS.csv')
 reject_counts=[]
 funding=pd.DataFrame(rows(run/'pair/funding.jsonl.gz'));funding=funding[funding.account.eq('PVR')].copy();funding['year']=funding['at'].str[:4];funding['gate_mentioned']=funding.result.astype(str).str.split(',').apply(lambda x:'nonprofitable_remaining_holding'in x);funding['gate_only']=funding.result.eq('nonprofitable_remaining_holding')
 for year,z in ge.groupby('year'):
  rz=rejected[rejected.year.eq(year)];fz=funding[funding.year.eq(year)];reject_counts.append(dict(year=year,total_gate_decisions=len(z),negative_gate_decisions=len(rz),negative_unique_stock_days=len(rz[['sid','day']].drop_duplicates()),funding_gate_only_rejections=int(fz.gate_only.sum()),funding_gate_with_other_reasons=int((fz.gate_mentioned&~fz.gate_only).sum())))
 pd.DataFrame(reject_counts).to_csv(out/'GATE_REJECTION_CLASSIFICATION.csv',index=False);funding[funding.gate_mentioned].to_csv(out/'FUNDING_GATE_REJECTIONS.csv',index=False)
 pd.DataFrame(annual).to_csv(out/'ANNUAL_METRICS.csv',index=False);pd.DataFrame(period).to_csv(out/'DAILY_RISK.csv',index=False);pd.DataFrame(rr).to_csv(out/'STOCK_ROUNDS.csv',index=False)
 sources=[base/'DONE.json',base/'PREDECLARED.json',base/'pair/PVR.json.gz',base/'pair/daily.jsonl.gz',run/'DONE.json',run/'PREDECLARED.json',run/'pair/PVR.json.gz',run/'pair/daily.jsonl.gz',run/'PROFIT_GATE_EVENTS.jsonl.gz',run/'pair/funding.jsonl.gz',labelsfile,Path(__file__)]
 save(out/'SUMMARY.json',dict(summary=summary,max_inventory_gap=str(gap),account_runs=0,sources={str(p):sha(p)for p in sources},limitations=['Only completed rounds define round win rate/payoff; live rounds separate.','Gate decisions are not necessarily effective prevented fills: original constraints may also reject.','Main gate excludes dividends from cost; accrued dividend receivables must not be called paid cash. Original engine payment timing/cash availability assumptions are inherited.','Summed predecision remaining cost is repeated exposure, not saved cash or rejected notional.','Big60 future labels posthoc only; early6 actual closing holdings, not returns.','Fixed future1709 pool, O+/-5bp proxy not guaranteed executable, corporate action terms preknown.']))
 save(out/'OUTPUT_SHA256.json',{p.name:sha(p)for p in out.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'});print('PASS',out)
if __name__=='__main__':main()
