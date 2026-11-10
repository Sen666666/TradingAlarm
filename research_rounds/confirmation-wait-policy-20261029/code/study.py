"""Frozen 1917 first-trial policies; only cached market evidence, no portfolio."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import time as dt,datetime,timezone
import sys,json,gzip,time,hashlib,bisect,collections,importlib.util
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/confirmation-wait-policy-20261029';SRC=ROOT/'research_rounds/broad-stage-reentry-20261029';HF=ROOT/'research_rounds/s-entry-mechanism-audit-20261029/code/audit.py';FROOT=ROOT/'research_rounds/intent-support-20261027/signals';CPROOT=ROOT/'research_rounds/continuous-protection-lines-20261028/signals'
sp=importlib.util.spec_from_file_location('waiting_policy_existing_helpers',HF);H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
Z=D(0);ONE=D(1);END='2026-10-27';stage=sys.argv[1];assert stage in ['sample','full'];t0=time.monotonic();out=O/stage;out.mkdir(exist_ok=False)
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(x):return pd.Timestamp(x).to_pydatetime()
def near(a,b,n=1):
 bound=D(1).scaleb(max(abs(a),abs(b),ONE).adjusted()-getcontext().prec+1)*64*max(1,n)
 assert abs(a-b)<=bound,('Decimal precision residual',a,b,bound)
 return abs(a-b)
obj=read(SRC/'results/N1.json');all_layers={x['id']:x for x in obj['layers']};trial=sorted([x for x in obj['layers'] if x.get('origin')=='trial'],key=lambda x:(x['opened'],x['id']));first={}
for x in trial:first.setdefault((x['sid'],tuple(x['epoch'])),x)
mother=list(first.values());assert len(trial)==2352 and len(mother)==1917
buys={x['layer']:x for x in obj['trades'] if x['side']=='buy'};sales=collections.defaultdict(list)
for x in obj['trades']:
 if x['side']=='sell':
  for p in x['parts']:sales[p['layer']].append((x,p))
divdates=collections.defaultdict(list)
for x in obj['audit']:
 if x['kind']=='dividend_accrual':divdates[x['receivable']['security_id']].append(x['receivable']['ex_at'][:10])
negative=lambda x:D(x['cash'])+D(x['dividend'])<0
cases={
 'original_later_promoted':next(x['id'] for x in mother if x.get('promoted_at')),
 'original_unpromoted_failure':next(x['id'] for x in mother if not x.get('promoted_at') and negative(x)),
 'original_ACT_exit':next(x['id'] for x in mother if x['reason']=='ACT_pause'),
 'original_I_exit':next(x['id'] for x in mother if x['reason']=='I_structure_exit'),
 'original_held_dividend':next(x['id'] for x in mother if any(x['opened'][:10]<d<=x['closed'][:10] for d in divdates[x['sid']]))}
sample=list(dict.fromkeys(cases.values()));wanted=sample if stage=='sample' else [x['id'] for x in mother];xs=[all_layers[k] for k in wanted];ids={x['sid'] for x in xs};allids={x['sid'] for x in mother}
basefiles=[SRC/'results/N1.json',SRC/'FREEZE-v2.json',SRC/'VERIFICATION.json',HF,O/'PROTOCOL.txt',Path(__file__),ROOT/'research_rounds/broad-stage-reentry-20261029/code/policy.py',ROOT/'research_rounds/s-entry-mechanism-audit-20261029/market-cache.parquet',ROOT/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json',ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/economic-protocol.json']
cachefiles=[root/(s+'.parquet') for s in sorted(allids) for root in [FROOT,CPROOT]]
if stage=='sample':
 fields=['layer','symbol','source_epoch','opened','signal_at','shares','raw_open','execution_price','gross','buy_fee','initial_floor','original_K']
 records=[dict(layer=x['id'],symbol=x['sid'],source_epoch=json.dumps(x['epoch']),opened=x['opened'],signal_at=x['signal_at'],shares=x['initial_qty'],raw_open=buys[x['id']]['raw_open'],execution_price=buys[x['id']]['price'],gross=buys[x['id']]['gross_cny'],buy_fee=buys[x['id']]['fees_cny'],initial_floor=buys[x['id']]['floor'],original_K=x['entry_cost']) for x in mother]
 pd.DataFrame(records,columns=fields).to_csv(O/'FROZEN_MOTHER.csv',index=False)
 basefiles.append(O/'FROZEN_MOTHER.csv');save(O/'INPUT_IDENTITY.json',dict(mother_layers=[x['id'] for x in mother],sample_cases=cases,sample=sample,sha256={str(p):sha(p) for p in basefiles+cachefiles},frozen_utc=datetime.now(timezone.utc).isoformat()))
identity=read(O/'INPUT_IDENTITY.json');assert [x['id'] for x in mother]==identity['mother_layers'] and cases==identity['sample_cases']
for p,h in identity['sha256'].items():assert sha(p)==h,p
_,m,_,dates=H.context(ids,False);calendar=[str(d.date()) for d in dates];dateidx={d:j for j,d in enumerate(calendar)};pauses=set(x['at'][:10] for x in obj['audit'] if x['kind']=='risk_checkpoint' and x.get('event')=='pause')
cache=pd.read_parquet(basefiles[7]);grids={s:g.set_index('date').sort_index() for s,g in cache[cache.symbol.isin(ids)].groupby('symbol')};known={s:{str(r.Index.date()):r._asdict() for r in g.itertuples()} for s,g in grids.items()}
# Events remain on their original observation dates, never forward-filled.
fine={};cp={};actions={}
for s in ids:
 f=pd.read_parquet(FROOT/(s+'.parquet'));c=pd.read_parquet(CPROOT/(s+'.parquet'))
 fine[s]={str(r.Index.date()):r._asdict() for r in f.itertuples()};cp[s]={str(r.Index.date()):r._asdict() for r in c.itertuples()};actions[s]=collections.defaultdict(list)
 for e in m.actions.get(s,[]):actions[s][e['effective_date']].append(e)
loadsec=time.monotonic()-t0
checks=collections.Counter();maxres=Z

def candidate(s,day,opened):
 out=[];f=fine[s].get(day);c=cp[s].get(day)
 if f is not None and pd.notna(f['event']) and f['event']==1:
  assert pd.notna(f['pivot_date']) and pd.notna(f['pivot']);pday=str(pd.Timestamp(f['pivot_date']).date());assert pday<=day
  if pday>=opened:out.append(('F',D(str(f['pivot']))))
 if c is not None and pd.notna(c['receipt']) and bool(c['receipt']):
  assert bool(c['ready']) and pd.notna(c['candidate']);out.append(('CP1',D(str(c['candidate']))))
 return out

def fast_decision(mode,held,pending,close,floor,e,cands,K,arm):
 # Pure semantic guard. Original old line must win over today's confirmation.
 if not held or pending:return 'inactive',floor
 if mode=='structure':return 'hold',floor
 if close<=floor:return 'exit',floor
 raised=max([floor,e]+[p for _,p in cands])
 if arm=='B' and any(p>K for _,p in cands):return 'switch',e
 return 'hold',raised

def semantic_checks():
 assert fast_decision('fast',True,False,D(9),D(10),D(7),[('F',D(12))],D(8),'B')[0]=='exit'
 assert fast_decision('fast',False,False,D(15),D(10),D(7),[('F',D(12))],D(8),'B')[0]=='inactive'
 assert fast_decision('fast',True,True,D(15),D(10),D(7),[('F',D(12))],D(8),'B')[0]=='inactive'
 assert fast_decision('fast',True,False,D(15),D(10),D(7),[('F',D(12))],D(8),'B')==('switch',D(7))
 return dict(old_line_before_new_confirmation=True,no_revival_after_sale=True,no_cancel_pending_exit=True,switch_effective_after_close=True)
semantic=semantic_checks();curves=[];writer=None;summary=[];fillsink=gzip.open(out/'ledger-audit.jsonl.gz','wt');signals=gzip.open(out/'policy-events.jsonl.gz','wt')
def flush():
 global writer,curves
 if not curves:return
 tb=pa.Table.from_pylist(curves)
 if writer is None:writer=pq.ParquetWriter(out/'daily-equity.parquet',tb.schema,compression='zstd')
 writer.write_table(tb);curves=[]

def new_state(x,arm,cost):
 s=x['sid'];buy=buys[x['id']];at=stamp(x['opened']);q=x['initial_qty'];purchase=D(buy['gross_cny'])+D(buy['fees_cny']);quote=m.quote(s,at);nextopen=m.sessions['A'][bisect.bisect_right(m.sessions['A'],at)]
 a=H.L.SectorAccount(initial_cash=purchase,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);a.available=Z;a.positions[s]=H.L.Position(s,quote.issuer_id,quote.sector_id,quote.currency,[H.L.InventoryLot(q,nextopen)])
 return dict(a=a,arm=arm,cost=cost,mode='structure' if arm=='C' else 'fast',floor=D(buy['floor']),K=D(x['entry_cost']),purchase=purchase,cursor=0,q=q,flow=Z,div=Z,paid=Z,fee=Z,slip=Z,peak=purchase,dd=Z,minnav=purchase,mvobs=Z,qtyobs=0,helddays=0,switch=None,switch_sources=None,request=None,reason=None,sells=[],fee_state={},lastnav=purchase,candidate_reads=0,maxres=Z,closed_at=None)

def consume(st,s):
 a=st['a']
 for ev in a.audit_log[st['cursor']:]:
  k=ev['kind']
  if k=='fill':
   r=ev['receipt'];assert r.side=='sell' and r.at>stamp(st['entry_at']);assert st['request'] is not None and r.at>st['request'];assert r.gross_cny==r.shares*ev['price'] and sum(ev['fee_components'].values(),Z)==r.fees_cny
   fs=m.fees(s,r.at);pp,pa=st['fee_state'].get(ev['order_id'],({},{}));kw=dict(shares=r.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));ff=fs.incremental('sell',r.gross_cny,pp,pa,st['cost'],**kw);assert ff==ev['fee_components'];ra=fs.rate_accrual('sell',r.gross_cny,st['cost'],**kw);st['fee_state'][ev['order_id']]=({k:pp.get(k,Z)+v for k,v in ff.items()},{k:pa.get(k,Z)+v for k,v in ra.items()})
   st['q']-=r.shares;st['flow']+=r.gross_cny-r.fees_cny;st['fee']+=r.fees_cny;st['slip']+=abs(ev['price']-ev['raw_open'])*r.shares;st['sells'].append(dict(at=r.at,shares=r.shares,gross=r.gross_cny,fees=r.fees_cny,components=ev['fee_components']))
   if not a.quantity(s):st['closed_at']=r.at
  elif k in ('split','split_fraction_floor_proxy'):st['q']=int(D(st['q'])*ev['ratio']);checks['split_observations']+=1
  elif k=='dividend_accrual':st['div']+=ev['receivable'].net_local;checks['dividend_observations']+=1
  elif k=='dividend_payment':st['paid']+=ev['entitlement'].net_local
 st['cursor']=len(a.audit_log);assert st['q']==a.quantity(s) and a.available>=0 and not a.buys

# Existing N1 factual cash reconstruction is separate from A/B/C policy accounting.
for x in xs:
 buy=buys[x['id']];purchase=D(buy['gross_cny'])+D(buy['fees_cny']);cash=-purchase+sum((D(p['net_cash']) for t,p in sales[x['id']]),Z);maxres=max(maxres,near(cash,D(x['cash']),len(sales[x['id']])+2));assert buy['shares']==x['initial_qty'] and buy['at']==x['opened'] and buy['security_id']==x['sid']
 fs=m.fees(x['sid'],stamp(x['opened']));fee=sum(fs.incremental('buy',D(buy['gross_cny']),{}, {},1,shares=buy['shares'],par_value=m.rules.get('security_metadata',{}).get(x['sid'],{}).get('par_value')).values(),Z);assert fee==D(buy['fees_cny']);checks['original_buy_fee_identity']+=1
print(json.dumps(dict(stage=stage,loaded=loadsec,mother=len(xs),sample_cases=cases,original_N1_factual_cash_residual=str(maxres))),flush=True)

for n,x in enumerate(xs):
 lid=x['id'];s=x['sid'];start=x['opened'][:10];source=x['epoch'][0];buy=buys[lid];entry=stamp(x['opened']);states=[new_state(x,arm,cost) for cost in [1,2] for arm in ['A','B','C']]
 for st in states:st['entry_at']=x['opened']
 common=None;terminal=None
 for day in calendar[dateidx[start]:]:
  row=known[s][day];op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
  if day!=start:
   for e in actions[s].get(day,[]):
    for st in states:H.action(st['a'],m,s,e)
   for st in states:
    a=st['a'];H.pay(a,m,op)
    if s in a.exits:
     w=m.window(s,op,'sell',st['cost'])
     if w:a.fill_exit(s,w)
    H.pay(a,m,op);H.pay(a,m,cl)
  for k in ['i_target','segment_id','close']:
   if pd.isna(row[k]):raise ValueError('required_current_market_unknown:'+s+':'+day+':'+k)
  valid=bool(row['i_target']) and int(row['segment_id'])==source
  if common is None and (day in pauses or not valid):common=(day,'ACT_pause' if day in pauses else 'I_structure_or_source_exit')
  price=D(str(row['close']));e=D(str(row['i_floor'])) if valid and pd.notna(row['i_floor']) else None
  if valid and e is None:raise ValueError('active_I_floor_unknown:'+s+':'+day)
  for st in states:
   a=st['a'];consume(st,s);mode_before=st['mode'];p_before=st['floor'];event=None
   if a.quantity(s) and s not in a.exits:
    if common is not None:
     event='exit';reason=common[1]
    elif st['mode']=='fast' and price<=st['floor']:
     event='exit';reason='fast_old_protection';checks['old_protection_exit']+=1
    elif st['mode']=='fast':
     cands=candidate(s,day,start);st['candidate_reads']+=1;event,pnext=fast_decision(st['mode'],True,False,price,st['floor'],e,cands,st['K'],st['arm']);st['floor']=pnext
     if event=='switch':
      assert st['arm']=='B' and cl>entry and st['switch'] is None;st['switch']=cl;st['switch_sources']=[name for name,p in cands if p>st['K']];st['mode']='structure';checks['switches']+=1
     elif pnext!=p_before:event='raise'
    if event=='exit':
     quote=m.quote(s,cl)
     if quote is None:raise ValueError('required_exit_quote_unknown:'+s+':'+day)
     a.request_exit(quote,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));st['request']=cl;st['reason']=reason;st['mode']='exit_pending'
    if event in ['exit','switch','raise']:signals.write(json.dumps(H.encoded(dict(layer=lid,cost=st['cost'],arm=st['arm'],date=day,event=event,mode_before=mode_before,mode_after=st['mode'],old_floor=p_before,new_floor=st['floor'],original_K=st['K'],close=price,switch_sources=st['switch_sources'])),ensure_ascii=False)+'\n')
   else:
    # No candidate lookup, no historical promoted_at and no eligibility renewal.
    checks['inactive_or_pending_skips']+=1
   consume(st,s);mark=m.latest_mark(s,cl) if st['q'] else None;mv=st['q']*mark.raw_price if mark else Z;bal=a.balance(cl,{s:mark} if mark else {});nav=bal['nav'];st['maxres']=max(st['maxres'],near(nav,st['flow']+st['div']+mv,len(a.audit_log)+1));near(nav,bal['available']+bal['inventory']+bal['dividend_receivable']+bal['sale_receivable'],len(a.audit_log)+1)
   st['lastnav']=nav;st['peak']=max(st['peak'],nav);st['dd']=max(st['dd'],ONE-nav/st['peak']);st['minnav']=min(st['minnav'],nav);st['mvobs']+=mv;st['helddays']+=st['q']>0;st['qtyobs']+=1;st['balance']=bal
   curves.append(dict(layer=lid,arm=st['arm'],cost=st['cost'],date=day,shares=st['q'],nav=str(nav),cash=str(bal['available']),inventory=str(mv),claim=str(bal['dividend_receivable']),sale_receivable=str(bal['sale_receivable']),mode=st['mode'],protection=str(st['floor'])))
  terminal=day
  if common is not None and all(st['q']==0 for st in states):break
  if day==END:break
 if common is None:common=(END,'cutoff')
 # Original promotion timestamps are tested only after all decisions are complete.
 for cost in [1,2]:
  bstate=next(st for st in states if st['cost']==cost and st['arm']=='B');original=stamp(x['promoted_at']) if x.get('promoted_at') else None
  assert bstate['switch']==original,(lid,'B original trigger reconstruction',bstate['switch'],original);checks['B_original_trigger_identity']+=1
 for st in states:
  bal=st['balance'];q=st['q'];cl=H.at(terminal,dt(15,10));est=sum(m.fees(s,cl).incremental('sell',bal['inventory'],{}, {},st['cost'],shares=q,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).values(),Z) if q else Z
  summary.append(dict(layer=lid,symbol=s,source_epoch=json.dumps(x['epoch']),entry_at=x['opened'],entry_date=start,arm=st['arm'],cost=st['cost'],initial_shares=x['initial_qty'],initial_cost=st['purchase'],buy_fee=D(buy['fees_cny']),buy_slippage=(D(buy['price'])-D(buy['raw_open']))*x['initial_qty'],original_K=st['K'],initial_frozen_protection=D(buy['floor']),switch_at=st['switch'],switch_sources=json.dumps(st['switch_sources']),exit_request=st['request'],exit_reason=st['reason'],first_sell=st['sells'][0]['at'] if st['sells'] else None,last_sell=st['sells'][-1]['at'] if st['sells'] else None,common_terminal_decision=common[0],common_terminal_reason=common[1],valuation_date=terminal,final_equity=st['lastnav'],net_pnl=st['lastnav']-st['purchase'],net_return=(st['lastnav']-st['purchase'])/st['purchase'],sell_fees=st['fee'],sell_slippage=st['slip'],dividend_accrued=st['div'],dividend_paid=st['paid'],terminal_claim=bal['dividend_receivable'],terminal_sale_receivable=bal['sale_receivable'],terminal_stock_value=bal['inventory'],terminal_shares=q,estimated_unexecuted_liquidation_fee=est,minimum_entry_return=st['minnav']/st['purchase']-ONE,max_local_drawdown=st['dd'],holding_observations=st['helddays'],valuation_observations=st['qtyobs'],inventory_yuan_observations=st['mvobs'],candidate_reads=st['candidate_reads'],independent_nav_residual=st['maxres'],original_was_promoted=bool(x.get('promoted_at'))))
  fillsink.write(json.dumps(H.encoded(dict(layer=lid,arm=st['arm'],cost=st['cost'],sells=st['sells'],audit=st['a'].audit_log)),ensure_ascii=False)+'\n')
 if (n+1)%100==0 or stage=='sample':print(json.dumps(dict(stage=stage,processed=n+1,total=len(xs),seconds=time.monotonic()-t0)),flush=True);flush()
 if time.monotonic()-t0+float(identity.get('sample_runtime_seconds',0) if stage=='full' else 0)>300:raise TimeoutError('300s cumulative sample+full calculation budget')
flush();writer.close();signals.close();fillsink.close();df=pd.DataFrame(H.encoded(summary));df.to_csv(out/'unit-ledgers.csv',index=False)
# Cutoff pending-sale valuation edge: an unexecuted last-close exit keeps inventory.
last=states[0];s=xs[-1]['sid'];at=H.at(END,dt(15,10));quote=m.quote(s,at);mark=m.latest_mark(s,at);edge=H.L.SectorAccount(initial_cash=D(10000));edge.available=Z;edge.positions[s]=H.L.Position(s,quote.issuer_id,quote.sector_id,quote.currency,[H.L.InventoryLot(100,at)]);edge.request_exit(quote,H.A.Clock(at,m.sessions['A'][bisect.bisect_right(m.sessions['A'],at)],at.date()));vb=edge.balance(at,{s:mark});assert edge.quantity(s)==100 and not edge.fills and vb['nav']==100*mark.raw_price;semantic['cutoff_pending_exit_is_marked_not_filled']=True
if stage=='full':
 sm=pd.read_csv(O/'sample/unit-ledgers.csv',dtype=str).fillna('').set_index(['layer','arm','cost']);fu=pd.read_csv(out/'unit-ledgers.csv',dtype=str).fillna('').set_index(['layer','arm','cost']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True)
for p,h in identity['sha256'].items():assert sha(p)==h,p
elapsed=time.monotonic()-t0;save(out/'VERIFICATION.json',dict(passed=True,stage=stage,mother=len(xs),ledgers=len(summary),source_N1_cash_residual=maxres,maximum_independent_nav_residual=max(st['maxres'] for st in states),checks=checks,semantic_checks=semantic,sample_full_equal=stage=='full',load_seconds=loadsec,runtime_seconds=elapsed,cumulative_calculation_seconds=elapsed+float(identity.get('sample_runtime_seconds',0) if stage=='full' else 0),new_portfolio_paths=0,no_external_cash=True,common_independent_complete_fees=True))
if stage=='sample':identity['sample_runtime_seconds']=elapsed;save(O/'INPUT_IDENTITY.json',identity)
print(json.dumps(dict(stage=stage,complete=True,units=len(xs),ledgers=len(summary),seconds=elapsed)),flush=True)
