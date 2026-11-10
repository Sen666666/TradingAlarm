"""Reuse the verified local inventory functions; remove every new-stock selection gate."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D,getcontext
from dataclasses import replace
from collections import Counter
import ast,sys,json,gzip,csv,time,hashlib,importlib.util,bisect
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;P=O.parent/'down-event-transfer-exposure-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');B=R/'pvr-local-finite-capital-20261029/baseline';S=R/'s-entry-mechanism-audit-20261029';PREV=O.parent/'down-event-transfer-local-20261030/study.py';Z=D(0);ONE=D(1)
stage=sys.argv[1];assert stage in ['sample','full'];dest=O/stage;dest.mkdir(exist_ok=False)
sp=importlib.util.spec_from_file_location('old_exit_same_helpers',S/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def export(p,x):pd.DataFrame(H.encoded(x)).to_csv(p,index=False)
def stamp(x):return datetime.fromisoformat(x)
obj=read(B/'accounts-v2/I__S0_base.json');audit=obj['audit_log'];actualfills=[x for x in audit if x['kind']=='fill'];cs=[x for x in csv.DictReader((B/'analysis/campaigns.csv').open()) if x['scenario']=='base'];cycles={f"{x['symbol']}|{x['entry_at'][:10]}":x for x in cs};assert len(cycles)==69 and all(c['closed']=='True' for c in cs)
exp=pd.read_csv(P/'all-holding-exposure-before-labels.csv');known=exp[exp.old_signal].sort_values(['date','cycle_id']).groupby('cycle_id',sort=False).head(1).set_index('cycle_id');assert len(known)==57
paired=set(pd.read_csv(P/'selected-events-before-labels.csv').cycle_id);mother=[]
for key,c in sorted(cycles.items(),key=lambda kv:(kv[1]['entry_at'],kv[1]['symbol'])):
 g=exp[exp.cycle_id==key];u=list(g[g.event.isna()].date);row=known.loc[key] if key in known.index else None
 mother.append(dict(cycle_id=key,old=c['symbol'],new='',name=c['name'],triggered=row is not None,date=str(row.date) if row is not None else None,old_quantity=int(row.shares) if row is not None else None,source_event_date=str(row.date) if row is not None else None,source_pivot_date=row.pivot_date if row is not None else None,unknown_event_days=u,unknown_before_first=[d for d in u if row is not None and d<row.date],original_entry=c['entry_at'],original_exit=c['exit_at'],previous32=key in paired))
assert sum(e['triggered'] for e in mother)==57 and sum(not e['triggered'] for e in mother)==12 and len(paired)==32
targets=['605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'];first_tail=next(e['cycle_id'] for e in mother if float(cycles[e['cycle_id']]['net_return'])>=.30);sample_ids=list(dict.fromkeys(targets+[first_tail]));assert all(next(e for e in mother if e['cycle_id']==k)['triggered'] for k in sample_ids)
files=[O/'PROTOCOL.txt',Path(__file__),PREV,P/'all-holding-exposure-before-labels.csv',P/'selected-events-before-labels.csv',B/'accounts-v2/I__S0_base.json',B/'analysis/campaigns.csv',S/'market-cache.parquet',O.parent/'act-loss-facts-20261030/actual-holding-close-paths.csv']
if stage=='sample':
 export(O/'FROZEN_69_CYCLES.csv',mother);save(O/'INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),samples=sample_ids,mother_cycle_ids=[e['cycle_id'] for e in mother],triggered=57,no_trigger=12,unknown_rows=int(exp.event.isna().sum()),sha256={str(p):sha(p) for p in files},before_this_exit_only_economic_run=True))
identity=read(O/'INPUT_IDENTITY.json');assert [e['cycle_id'] for e in mother]==identity['mother_cycle_ids']
for p,h in identity['sha256'].items():assert sha(p)==h,p
events=mother if stage=='full' else [e for e in mother if e['cycle_id'] in sample_ids];ids={e['old'] for e in events};_,m,_,_=H.context(ids,False)
cache=pd.read_parquet(S/'market-cache.parquet');cc={(x.symbol,str(x.date.date())):x for x in cache.itertuples(index=False)};calendar=sorted(set(k[1] for k in cc));cp={x['at'][:10]:x for x in audit if x['kind']=='risk_checkpoint'};olddiv=[x['receivable'] for x in audit if x['kind']=='dividend_accrual'];paths=list(csv.DictReader((O.parent/'act-loss-facts-20261030/actual-holding-close-paths.csv').open()));path_by={k:[x for x in paths if x['cycle_id']==k] for k in cycles}
checks=Counter();maxres=Z;results=[];curves=[];flowlogs=[];baseline=[]
# Import only the named verified function bodies, never the old script's CLI/paths.
names=['near','seed','consume','marks_at','snapshot'];tree=ast.parse(PREV.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];assert {n.name for n in nodes}==set(names);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(PREV),'exec'),globals())
def endpoints(e):
 t=H.at(e['date'],dt(15,10));first=m.sessions['A'][bisect.bisect_right(m.sessions['A'],t)];end=H.at(cycles[e['cycle_id']]['exit_at'][:10],dt(15,10));return t,first,end,end,'original_cycle_exit_only'
def risk(values):
 peak=values[0];dd=Z
 for v in values:peak=max(peak,v);dd=max(dd,ONE-v/peak)
 return min(values)/values[0]-ONE,dd
def actual_check(e):
 c=cycles[e['cycle_id']];bu=[x for x in actualfills if x['receipt']['security_id']==e['old'] and x['receipt']['side']=='buy' and x['receipt']['at']==c['entry_at']];se=[x for x in actualfills if x['receipt']['security_id']==e['old'] and x['receipt']['side']=='sell' and x['receipt']['at']==c['exit_at']];assert len(bu)==len(se)==1
 for x in bu+se:
  f=x['receipt'];tm=stamp(f['at']);fs=m.fees(e['old'],tm);ex=fs.incremental(f['side'],D(f['gross_cny']),{}, {},1,shares=f['shares'],par_value=m.rules.get('security_metadata',{}).get(e['old'],{}).get('par_value'));assert ex=={k:D(v) for k,v in x['fee_components'].items()} and sum(ex.values(),Z)==D(f['fees_cny']);checks['original_fill_fee_checks']+=1
 div=sum((D(x['net_local']) for x in olddiv if x['security_id']==e['old'] and c['entry_at'][:10]<=x['ex_at'][:10]<=c['exit_at'][:10]),Z);basis=D(c['buy_gross'])+D(c['buy_fees']);net=D(c['sell_gross'])-D(c['sell_fees'])+div-basis;assert net==D(c['net_pnl']) and div==D(c['dividends']);checks['original_cycle_exact']+=1;return basis,div,se[0]
loadsec=time.monotonic()-T
for n,e in enumerate(events):
 c=cycles[e['cycle_id']];basis,source_div,sale=actual_check(e);orig_values=[basis]+[basis+D(x['nav_mark_pnl']) for x in path_by[e['cycle_id']]]+[basis+D(c['net_pnl'])]
 if not e['triggered']:
  mn,dd=risk(orig_values)
  for cost in [1,2]:
   for arm in ['A','B']:results.append(dict(cycle_id=e['cycle_id'],symbol=e['old'],name=c['name'],cost=cost,arm=arm,triggered=False,trigger=None,unknown_event_days=json.dumps(e['unknown_event_days']),unknown_before_first=json.dumps(e['unknown_before_first']),previous32=e['previous32'],original_tail30=float(c['net_return'])>=.30,original_profitable=D(c['net_pnl'])>0,original_entry=c['entry_at'],original_exit=c['exit_at'],initial_actual_cost=basis,original_pretrigger_pnl=D(c['net_pnl']),trigger_equity=None,final_equity=basis+D(c['net_pnl']),full_cycle_net=D(c['net_pnl']),full_cycle_return=D(c['net_return']),post_trigger_pnl=Z,fees_after_trigger=Z,full_fees=D(c['buy_fees'])+D(c['sell_fees']),dividend=source_div,first_sell=c['exit_at'],last_sell=c['exit_at'],sold_quantity=sale['receipt']['shares'],sell_fill_count=1,final_shares=0,terminal_claim=source_div,min_full_cycle_return=mn,max_full_cycle_DD=dd,min_post_trigger_return=None,max_post_trigger_DD=None,holding_close_observations=len(path_by[e['cycle_id']]),cash_close_after_trigger=0,status='no_known_trigger_exact_original_identity'))
  baseline.append(dict(cycle_id=e['cycle_id'],triggered=False,source_net=c['net_pnl'],A_reproduced_net=c['net_pnl'],residual=Z));continue
 t,first,end,_,_=endpoints(e);states=[seed(e,cost,arm) for cost in [1,2] for arm in ['A','B']]
 for st in states:snapshot(st,e,t,'trigger_close')
 for day in calendar[calendar.index(str(first.date())):bisect.bisect_right(calendar,str(end.date()))]:
  op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
  for st in states:
   a=st['a']
   for act in m.actions.get(e['old'],[]):
    if act['effective_date']==day:H.action(a,m,e['old'],act)
   H.pay(a,m,op)
   for s in tuple(a.exits):
    w=m.window(s,op,'sell',st['cost'])
    if w:a.fill_exit(s,w)
   H.pay(a,m,op);snapshot(st,e,op,'open');H.pay(a,m,cl)
   if a.quantity(e['old']) and e['old'] not in a.exits:
    r=cc[e['old'],day];assert pd.notna(r.i_target)
    if not bool(r.i_target) or not cp[day]['on']:
     quote=m.quote(e['old'],cl);assert quote is not None;a.request_exit(quote,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));st['requests'].append(dict(sid=e['old'],at=cl,reason='ACT' if not cp[day]['on'] else 'I_structure'))
   snapshot(st,e,cl,'close')
 for st in states:
  sr=st['snapshots'][-1];assert sr['at']==end;prefix=[basis]+[basis+D(x['nav_mark_pnl']) for x in path_by[e['cycle_id']] if x['day']<=e['date']];near(prefix[-1],st['I0']);fullvalues=prefix+[x['nav'] for x in st['snapshots'][1:]];mn,dd=risk(fullvalues);postmn,postdd=risk([x['nav'] for x in st['snapshots']]);sells=[x for x in st['fills'] if x['side']=='sell'];fullnet=sr['nav']-basis;close=[x for x in st['snapshots'] if x['phase']=='close'];prefixheld=sum(x['day']<=e['date'] for x in path_by[e['cycle_id']])
  results.append(dict(cycle_id=e['cycle_id'],symbol=e['old'],name=c['name'],cost=st['cost'],arm=st['arm'],triggered=True,trigger=e['date'],unknown_event_days=json.dumps(e['unknown_event_days']),unknown_before_first=json.dumps(e['unknown_before_first']),previous32=e['previous32'],original_tail30=float(c['net_return'])>=.30,original_profitable=D(c['net_pnl'])>0,original_entry=c['entry_at'],original_exit=c['exit_at'],initial_actual_cost=basis,original_pretrigger_pnl=st['prior_pnl'],trigger_equity=st['I0'],final_equity=sr['nav'],full_cycle_net=fullnet,full_cycle_return=fullnet/basis,post_trigger_pnl=sr['nav']-st['I0'],fees_after_trigger=sr['fees'],full_fees=D(c['buy_fees'])+sr['fees'],dividend=sr['dividend'],first_sell=sells[0]['at'] if sells else None,last_sell=sells[-1]['at'] if sells else None,sold_quantity=sum(x['shares'] for x in sells),sell_fill_count=len(sells),final_shares=st['a'].quantity(e['old']),terminal_claim=sr['claim'],min_full_cycle_return=mn,max_full_cycle_DD=dd,min_post_trigger_return=postmn,max_post_trigger_DD=postdd,holding_close_observations=prefixheld+sum(x['inventory']>0 for x in close),cash_close_after_trigger=sum(x['inventory']==0 for x in close),status='warning_exit_requested' if st['arm']=='B' else 'original_hold'))
  if st['arm']=='A' and st['cost']==1:
   assert len(sells)==1 and sells[0]['at']==stamp(c['exit_at']) and sells[0]['shares']==sale['receipt']['shares'] and sells[0]['gross']==D(c['sell_gross']) and sells[0]['fees']==D(c['sell_fees']);res=near(fullnet,D(c['net_pnl']),len(st['a'].audit_log)+1);baseline.append(dict(cycle_id=e['cycle_id'],triggered=True,source_net=c['net_pnl'],A_reproduced_net=fullnet,residual=res));checks['A_modeled_cycle_exact']+=1
  maxres=max(maxres,st['maxres']);curves.extend(st['snapshots']);flowlogs.append(dict(cycle_id=e['cycle_id'],cost=st['cost'],arm=st['arm'],fills=st['fills'],audit=st['a'].audit_log))
 if stage=='sample' or (n+1)%16==0:print(json.dumps(dict(stage=stage,processed=n+1,total=len(events),seconds=time.monotonic()-T),ensure_ascii=False),flush=True)
 if time.monotonic()-T+float(identity.get('sample_seconds',0) if stage=='full' else 0)>300:raise TimeoutError('300s sample plus full budget')
export(dest/'unit-ledgers.csv',results);export(dest/'A-original-cycle-checks.csv',baseline);pd.DataFrame(H.encoded(curves)).to_parquet(dest/'local-equity.parquet',index=False)
with gzip.open(dest/'audit.json.gz','wt') as f:json.dump(H.encoded(flowlogs),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);fu=pd.read_csv(dest/'unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True);assert sum((D(x['full_cycle_net']) for x in results if x['arm']=='A' and x['cost']==1),Z)==D('2984160.2756603511085')
for p,h in identity['sha256'].items():assert sha(p)==h,p
elapsed=time.monotonic()-T;save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,cycles=len(events),triggered=sum(e['triggered'] for e in events),no_trigger=sum(not e['triggered'] for e in events),ledgers=len(results),original_baseline_checks=len(baseline),checks=dict(checks),max_NAV_residual=maxres,sample_full_equal=stage=='full',load_seconds=loadsec,seconds=elapsed,new_portfolio_paths=0,no_new_stock_or_pair_gate=True,source_functions_reused=names))
if stage=='sample':identity['sample_seconds']=elapsed;save(O/'INPUT_IDENTITY.json',identity)
print(json.dumps(dict(stage=stage,complete=True,cycles=len(events),seconds=elapsed)),flush=True)
