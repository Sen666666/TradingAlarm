from gate_common import *
from decimal import Decimal
import gzip,collections,importlib.util
sys.path[:0]=[str(OLD/'code'),str(IX/'code')]
from analyze_ix import IndependentPrices
spec=importlib.util.spec_from_file_location('independent_gate_cash',OLD/'code/analyze_accounts.py');cash=importlib.util.module_from_spec(spec);spec.loader.exec_module(cash)
D=Decimal;ZERO=D(0)

def main():
 short='--short' in sys.argv;source=HERE/('technical/short' if short else 'accounts');out=HERE/('technical/short-audit' if short else 'analysis');out.mkdir(exist_ok=False)
 daily=collections.defaultdict(list)
 with gzip.open(source/'daily.jsonl.gz','rt') as f:
  for l in f:x=json.loads(l);daily[x['account']].append(x)
 meta=read(OLD/'inputs-v2/metadata.json');scope=read(SEC/'scope.json')
 for sid in scope['groups']['DRUG']:meta[sid]=dict(meta[sid],sector_id='THEME931152',industry='创新药')
 prices=IndependentPrices();calendar=[cash.t(t) for t in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']];summaries=[];campaigns=[];curves=[];years=[];checks=[];cache={};raw={};fillchecks=0;exitchecks=0
 def facts(sid):
  if sid not in cache:cache[sid]=pd.read_parquet(HERE/'facts'/f'{sid}.parquet');raw[sid]=pd.read_parquet(IX/'signals'/f'{sid}.parquet').join(pd.read_parquet(SEC/'signals'/f'{sid}.parquet'))
  return cache[sid],raw[sid]
 for aid,ds in daily.items():
  group,policy,stress=aid.split('__')[0].split('_');obj=read(source/f'{aid}.json');cc,receipt=cash.audit_account('S1_'+stress,obj,ds,prices,meta,calendar);receipt['account']=aid;checks.append(receipt)
  reservations={x['order_id']:x for x in obj['audit_log'] if x['kind']=='reserve'};first={}
  for x in obj['audit_log']:
   if x['kind']=='fill' and x['receipt']['side']=='buy':
    sid=x['receipt']['security_id'];day=reservations[x['order_id']]['decision_at'][:10];g,f=facts(sid);first.setdefault((sid,x['receipt']['at']),day)
    if policy.endswith('G'):assert bool(g.loc[day,'gate']),(aid,sid,day,'buy without EMA gate')
    if policy in ['I','IG']:assert bool(f.loc[day,'IX']),(aid,sid,day,'I no native event')
    assert bool(f.loc[day,'i_target' if policy in ['I','IG'] else 'e0_target'])
    fillchecks+=1
  for c in cc:
   c.update(account=aid,group=group,policy=policy,scenario=stress,decision_day=first[c['symbol'],c['entry_at']],name=scope['meta'][c['symbol']]['name']);campaigns.append(c)
  closed=[c for c in cc if c['closed']];tail=[c for c in closed if c['tail_closed']];ordinary=[c for c in closed if not c['tail_closed']];loss=-sum((c['net_pnl'] for c in closed if c['net_pnl']<0),ZERO);tailp=sum((c['net_pnl'] for c in tail),ZERO);ordp=sum((c['net_pnl'] for c in ordinary),ZERO);op=sum((c['net_pnl'] for c in cc if not c['closed']),ZERO)
  assert abs(tailp+ordp+op-(D(ds[-1]['nav'])-D(1000000)))<D('1e-8')
  df=pd.DataFrame(ds);nav=df.nav.astype(float).to_numpy();dd=nav/np.maximum.accumulate(np.r_[1e6,nav])[1:]-1
  summaries.append(dict(account=aid,group=group,policy=policy,scenario=stress,net_return=nav[-1]/1e6-1,max_drawdown=float(-dd.min()),final_nav=nav[-1],mean_exposure=float((df.inventory.astype(float)/df.nav.astype(float)).mean()),closed=len(closed),open=len(cc)-len(closed),win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed) if closed else None,tail_count=len(tail),tail_pnl=float(tailp),ordinary_pnl=float(ordp),open_pnl=float(op),all_loss=float(loss),tail_to_all_loss=float(tailp/loss) if loss else None,fees_cny=float(df.fees_cny.iloc[-1]),max_stock_weight=receipt['max_stock_weight']))
  for i,x in enumerate(ds):curves.append(dict(account=aid,group=group,policy=policy,scenario=stress,date=x['at'][:10],nav=float(x['nav']),drawdown=float(dd[i]),exposure=float(x['inventory'])/float(x['nav'])))
  prev=1e6
  for y,g in df.groupby(df['at'].str[:4],sort=True):
   v=g.nav.astype(float).to_numpy();years.append(dict(account=aid,group=group,policy=policy,scenario=stress,year=y,net_return=v[-1]/prev-1));prev=v[-1]
 if not short:
  with gzip.open(source/'decisions.jsonl.gz','rt') as f:
   for line in f:
    x=json.loads(line);policy=x['account'].split('_')[1];day=x['at'][:10]
    for ex in x['exits']:
     sid=ex['security_id'];_,d=facts(sid);field='i_target' if policy in ['I','IG'] else 'e0_target'
     assert day in d.index and not bool(d.loc[day,field]),(x['account'],sid,day,'EMA affected exit')
     exitchecks+=1
 def serial(x):
  if isinstance(x,D):return str(x)
  if isinstance(x,dict):return {k:serial(v) for k,v in x.items()}
  if isinstance(x,list):return [serial(v) for v in x]
  return clean(x)
 for name,rs in [('summary',summaries),('campaigns',campaigns),('curves',curves),('annual',years)]:
  pd.DataFrame(serial(rs)).to_csv(out/f'{name}.csv',index=False);write(out/f'{name}.json',serial(rs))
 result=dict(passed=True,short=short,accounts=len(daily),daily_rows=sum(len(x) for x in daily.values()),maximum_NAV_difference_cny=max(D(x['max_absolute_nav_difference_cny']) for x in checks),actual_buy_checks=fillchecks,native_exit_checks=exitchecks,independent_accounts=checks,code_sha256=sha(__file__))
 write(out/'accounting.json',serial(result));print({k:serial(v) for k,v in result.items() if k!='independent_accounts'},flush=True)
 if not short:print(pd.DataFrame(summaries)[['group','policy','scenario','net_return','max_drawdown','mean_exposure','closed','tail_count']].to_string(index=False),flush=True)

if __name__=='__main__':main()
