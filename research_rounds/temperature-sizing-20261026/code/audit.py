"""Independent cash/share replay plus actual sizing-intent and cost-basis checks."""
from common import *
from decimal import Decimal as D,ROUND_CEILING
import inspect,collections
import analyze_accounts as old_audit
from analyze_ix import IndependentPrices
from funding_audit import verify as verify_funding
PAD=D('1000000000000');CAP=D('1000000');CORE=D('100000');LEVELS=[CORE,D('300000'),D('600000'),CAP];ZERO=D(0)
src=inspect.getsource(old_audit.audit_account).replace('D(1_000_000)','PAD').replace("if not aid.startswith('B0'):","if False:")
src=src.replace("later=[x for x in calendar if x.date()>when.date()];lots[sid].append([count,later[0]])","lots[sid].append([count,next_session[when.date()]])")
space=dict(old_audit.audit_account.__globals__,PAD=PAD);exec(compile(src,'same_independent_cash_share_replay','exec'),space);financial=space['audit_account']
def selected(path,aid):
 for r in rows(path):
  if r['account']==aid:yield r
def when(r):return r.get('at') or r.get('receipt',{}).get('at') or r.get('receivable',{}).get('ex_at')

def check_sizing(aid,log,ds,facts,prices,final):
 mode=aid.split('__')[0];symbols={str(s):j for j,s in enumerate(facts['symbols'])};dates={str(d):i for i,d in enumerate(facts['dates'])};q=collections.defaultdict(int);book=collections.defaultdict(lambda:ZERO);anchor={};stages={};intent={};reserved={};ordersid={};cycle={};cycleinfo={};checks=collections.Counter();cursor=0
 reductionkeys={(x['sid'],x['at']) for x in log if x['kind']=='sizing_reduction'}
 for d in ds:
  while cursor<len(log) and when(log[cursor])<=d['at']:
   r=log[cursor];cursor+=1;k=r['kind'];at=when(r);day=at[:10]
   if k=='reserve':reserved[r['order_id']]=D(r['gross_budget_cny']);ordersid[r['order_id']]=r['sid'];assert book[r['sid']]+reserved[r['order_id']]<=CAP+D('1e-8')
   elif k=='release_buy':assert abs(reserved.pop(r['order_id'])-D(r['gross_released']))<D('1e-8')
   elif k=='sizing_reset':
    sid=r['sid'];i=dates[day];j=symbols[sid];assert mode=='D' and (facts['grade'][i,j]<=-2 or facts['acute'][i,j]);stages[sid]=0
   elif k=='sizing_buy_intent':
    sid=r['sid'];i=dates[day];j=symbols[sid];assert facts['eligible'][i,j] and facts['up'][i,j]==1
    assert abs(D(r['held_cost'])-book[sid])<D('1e-8')
    if r['sizing_kind']=='initial':
     assert not q[sid];target=CAP if mode=='F100' else D('300000') if mode=='F30' else CORE
     assert D(r['amount'])==target
    else:
     grade=int(facts['grade'][i,j]);signal=float(facts['signal_price'][i,j]);assert q[sid] and grade>=2 and facts['fresh'][i,j] and signal>anchor[sid]
     assert prices.mark(sid,day)>book[sid]/D(q[sid])
     stage=int(r['stage'])
     if mode in ['A','D']:
      if mode=='A':assert stage==stages[sid]+1
      else:assert stage==stages[sid]+1 or (stage==1 and any((facts['grade'][a,j]<=-2 or facts['acute'][a,j]) for a in range(cycle[sid]['last_buy_i']+1,i+1)))
     else:assert stage=={2:1,3:2,4:3}[grade]
     target=LEVELS[stage];expected=((target-book[sid])*100).to_integral_value(rounding='ROUND_FLOOR')/100;assert D(r['amount'])==expected
    intent[r['order_id']]=r;checks[r['sizing_kind']+'_intent']+=1
   elif k=='sizing_reduction':
    sid=r['sid'];assert q[sid]>int(r['shares'])>0 and mode in ['C','D'];assert abs(D(r['held_cost'])-book[sid])<D('1e-8');i=dates[day];j=symbols[sid];grade=int(facts['grade'][i,j]);target=({4:CAP,3:LEVELS[2],2:LEVELS[1]}.get(grade,CORE) if mode=='C' else CORE);assert D(r['target_cost'])==target
    if mode=='D':assert grade<=-2 or facts['acute'][i,j]
    checks['reduction_intents']+=1
   elif k=='exit_request':
    sid=r['sid']
    if (sid,r['at']) not in reductionkeys:assert facts['up'][dates[day],symbols[sid]]==0
   elif k=='upgrade_full_exit':assert facts['up'][dates[day],symbols[r['sid']]]==0
   elif k=='fill':
    f=r['receipt'];sid=f['security_id'];n=int(f['shares']);gross=D(f['gross_cny'])
    if f['side']=='buy':
     z=intent[r['order_id']]
     if not q[sid]:cycle[sid]=dict(symbol=sid,entry_at=f['at'],initial_gross=ZERO,add_gross=ZERO,initial_fills=0,add_fills=0,last_buy_i=dates[z['at'][:10]])
     kind=z['sizing_kind'];cycle[sid][kind+'_gross']+=gross;cycle[sid][kind+'_fills']+=1;cycle[sid]['last_buy_i']=dates[z['at'][:10]]
     q[sid]+=n;book[sid]+=gross;reserved[r['order_id']]-=gross;anchor[sid]=float(z['signal_price']);stages[sid]=int(z['stage']);assert book[sid]+reserved[r['order_id']]<=CAP+D('1e-8');checks['cost_cap_fill_checks']+=1
    else:
     old=q[sid];assert old>=n;book[sid]=book[sid]*D(old-n)/D(old);q[sid]-=n
     if not q[sid]:
      cc=cycle.pop(sid);cycleinfo[(sid,cc['entry_at'])]=cc;book.pop(sid,None);anchor.pop(sid,None);stages.pop(sid,None)
   elif k.startswith('split'):
    sid=r['sid'];q[sid]=int(D(q[sid])*D(r['ratio']))
  assert abs(sum(book.values(),ZERO)-D(d['holding_cost']))<D('1e-8'),(aid,d['at'],'cost basis')
  assert abs(max(book.values(),default=ZERO)-D(d['max_single_cost']))<D('1e-8')
  assert {s:n for s,n in q.items() if n}=={s:n for s,n in d['positions'].items() if n}
  checks['daily_average_cost_checks']+=1
 for sid,c in cycle.items():cycleinfo[(sid,c['entry_at'])]=c
 assert cursor==len(log)
 return cycleinfo,dict(passed=True,checks=dict(checks))

def main(mode):
 short=mode=='short';source=HERE/('technical/short' if short else 'accounts-v1');out=HERE/('technical/short-analysis' if short else 'analysis-v1');out.mkdir(exist_ok=False)
 facts=dict(np.load(HERE/'prepared/facts.npz'));meta=read(OLD/'inputs-v2/metadata.json');prices=IndependentPrices();calendar=[old_audit.t(t) for t in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']];space['next_session']={calendar[j].date():calendar[j+1] for j in range(len(calendar)-1)}
 reference=pd.read_csv(PREV/'analysis-v1/summary.csv');KREF=float(reference[(reference.policy=='E0')&(reference.scenario=='base')].peak_funding.iloc[0]);oldstocks=pd.read_csv(PREV/'analysis-v1/stocks.csv');top20=set(oldstocks[(oldstocks.policy=='E0')&(oldstocks.scenario=='base')].nlargest(20,'net_profit').symbol)
 sources={a:source for a in read(source/'summary.json')['accounts']}
 if not short:
  control=HERE/'technical/controls-v2';sources={**{a:control for a in read(control/'summary.json')['accounts']},**sources}
 aids=list(sources);result=[];curves=[];campaigns=[];stockrows=[];annual=[];receipts=[];funding=[]
 for aid in aids:
  source=sources[aid]
  ds=list(selected(source/'daily.jsonl.gz',aid));log=list(selected(source/'audit.jsonl.gz',aid));final=read(source/f'{aid}-final.json');cc,rc=financial(aid,dict(audit_log=log),ds,prices,meta,calendar);info,sizing=check_sizing(aid,log,ds,facts,prices,final);fund=verify_funding(log,ds,final);funding.append(dict(account=aid,**fund));rc['sizing']=sizing;receipts.append(rc)
  for c in cc:c.update(info[(c['symbol'],c['entry_at'])],has_add=info[(c['symbol'],c['entry_at'])]['add_fills']>0,policy=aid.split('__')[0],scenario=aid.rsplit('_',1)[-1]);c['account']=aid
  K=float(final['peak_funding']);df=pd.DataFrame(ds);p=df.pnl.astype(float).to_numpy();mv=df.inventory.astype(float).to_numpy();equity=K+p;peak=np.maximum.accumulate(np.r_[K,equity])[1:];dd=1-equity/peak;common=KREF+p;cp=np.maximum.accumulate(np.r_[KREF,common])[1:];common_dd=1-common/cp
  assert equity.min()>=-1e-6
  closed=[c for c in cc if c['closed']];tails=[c for c in closed if c['tail_closed']];ordinary=[c for c in closed if not c['tail_closed']];tail=sum((c['net_pnl'] for c in tails),ZERO);normal=sum((c['net_pnl'] for c in ordinary),ZERO);openp=sum((c['net_pnl'] for c in cc if not c['closed']),ZERO);loss=-sum((c['net_pnl'] for c in closed if c['net_pnl']<0),ZERO)
  assert abs(tail+normal+openp-D(ds[-1]['pnl']))<D('1e-8')
  failed_initial=[c for c in closed if not c['has_add'] and c['net_pnl']<0];added=[c for c in closed if c['has_add']];i=int(mv.argmax());counts=final['counts'];r=dict(account=aid,policy=aid.split('__')[0],scenario=aid.rsplit('_',1)[-1],net_profit=float(p[-1]),peak_market_value=float(mv[i]),peak_market_value_date=ds[i]['at'][:10],mean_market_value=float(mv.mean()),peak_funding=K,profit_over_funding=float(p[-1]/K),profit_over_peak_market_value=float(p[-1]/mv[i]),max_drawdown=float(dd.max()),common_capital_drawdown=float(common_dd.max()),max_drawdown_amount=float((peak-equity).max()),max_holdings=int(df.holding_count.max()),ending_market_value=float(mv[-1]),fees=float(df.fees_cny.iloc[-1]),closed=len(closed),open=len(cc)-len(closed),tail_count=len(tails),tail_profit=float(tail),ordinary_profit=float(normal),open_profit=float(openp),all_closed_losses=float(loss),tail_to_all_losses=float(tail/loss) if loss else None,win_rate=sum(c['net_pnl']>0 for c in closed)/len(closed) if closed else None,failed_initial_count=len(failed_initial),failed_initial_loss=-float(sum((c['net_pnl'] for c in failed_initial),ZERO)),failed_initial_mean_loss=-float(sum((c['net_pnl'] for c in failed_initial),ZERO))/len(failed_initial) if failed_initial else None,added_closed_count=len(added),added_cycle_profit=float(sum((c['net_pnl'] for c in added),ZERO)),top20_reference_profit=float(sum((c['net_pnl'] for c in cc if c['symbol'] in top20),ZERO)),initial_orders=counts.get('initial_orders',0),add_orders=counts.get('add_orders',0),reduction_orders=counts.get('reduction_orders',0),initial_fills=counts.get('initial_fills',0),add_fills=counts.get('add_fills',0),sell_fills=counts.get('sell_fills',0),minimum_quantity_rejections=counts.get('insufficient_budget_or_quantity',0),unique_stocks=len({c['symbol'] for c in cc}))
  result.append(r);campaigns.extend(cc)
  for k,d in enumerate(ds):curves.append(dict(account=aid,policy=r['policy'],scenario=r['scenario'],date=d['at'][:10],pnl=float(p[k]),market_value=float(mv[k]),funding_to_date=float(d['peak_funding']),drawdown=float(dd[k]),common_capital_drawdown=float(common_dd[k]),holdings=int(d['holding_count'])))
  prev=0
  for y,g in df.groupby(df['at'].str[:4],sort=True):annual.append(dict(account=aid,policy=r['policy'],scenario=r['scenario'],year=y,net_profit=float(g.pnl.astype(float).iloc[-1]-prev)));prev=float(g.pnl.astype(float).iloc[-1])
  by=collections.defaultdict(list)
  for c in cc:by[c['symbol']].append(c)
  for sid,cs in by.items():stockrows.append(dict(account=aid,policy=r['policy'],scenario=r['scenario'],symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],net_profit=float(sum((c['net_pnl'] for c in cs),ZERO)),tail_profit=float(sum((c['net_pnl'] for c in cs if c['tail_closed']),ZERO)),campaigns=len(cs),reference_top20=sid in top20))
  print(json.dumps(dict(audited=aid,days=len(ds),net_profit=r['net_profit'],peak_funding=K,max_drawdown=r['max_drawdown'],sizing_checks=sizing['checks'])),flush=True)
 for name,rr in [('summary',result),('curves',curves),('annual',annual),('stocks',stockrows),('campaigns',campaigns)]:pd.DataFrame(native.encoded(rr)).to_csv(out/f'{name}.csv',index=False)
 write(out/'accounting.json',dict(passed=True,accounts=len(aids),daily_rows=sum(r['checks']['daily_independent_nav_and_shares'] for r in receipts),max_nav_difference=max(D(r['max_absolute_nav_difference_cny']) for r in receipts),receipts=receipts));write(out/'funding.json',dict(passed=True,receipts=funding))
 if short:write(HERE/'technical/short-validation.json',dict(passed=True,accounts=len(aids),daily_rows=sum(len(list(selected(source/'daily.jsonl.gz',a))) for a in aids),all_ledger_and_sizing_checks=True))
if __name__=='__main__':main(sys.argv[1])
