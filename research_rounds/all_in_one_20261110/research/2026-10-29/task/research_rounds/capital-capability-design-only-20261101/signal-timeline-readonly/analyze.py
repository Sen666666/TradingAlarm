"""Saved F1/market-opportunity reads and slot upper bounds; no account/model imports."""
from pathlib import Path
from collections import defaultdict, Counter
import gzip,json,hashlib,time,math
import pandas as pd

O=Path(__file__).resolve().parent; W=O.parents[1]
B=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101')
SRC={};FACT={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');q.replace(p)
def records(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def table(p):SRC[str(p)]=sha(p);f=pd.read_parquet(p);f.index=f.index.astype(str);return f
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def price(sid,d):
 if sid not in FACT:
  r=SM[sid];p=Path(r['refs']['facts']);assert sha(p)==r['output_sha256'][str(p)];SRC[str(p)]=sha(p)
  f=pd.read_parquet(p,columns=['raw_close']);f.index=f.index.strftime('%Y-%m-%d');FACT[sid]=f.raw_close.to_dict()
 return FACT[sid].get(d)
def order_minimum(sid,*,held_shares=0,same_order_partial=False,filled_in_this_order=0):
 # Position ownership never relaxes a NEW order's minimum. Only the unfilled
 # remainder of the SAME partially filled original order uses fill_step.
 if held_shares<0:raise ValueError('negative held quantity')
 if same_order_partial:
  if filled_in_this_order<=0:raise ValueError('same-order partial fill required')
  return 1 if sid.startswith('688') else 100
 return 200 if sid.startswith('688') else 100
def minimum_ok(sid,d,*,held_shares=0):
 p=price(sid,d)
 return None if p is None or not math.isfinite(p) or p<=0 else p*order_minimum(sid,held_shares=held_shares)<=20000

def describe(node,name,p,lo,hi,domain,sector=None):
 f=table(p);dates=list(f.index);nextday={d:dates[i+1] if i+1<len(dates) else None for i,d in enumerate(dates)};f=f.loc[:hi]
 ctx=None;contexts=[];hist={};timeline=[]
 for d,r in f.iterrows():
  ev=list(r.events)
  failure=any(e.startswith('price_failure') or e=='source_changed_context_ended' for e in ev)
  if failure and ctx is not None:ctx['end']=d;ctx=None
  if any(e in ('break_started','repair_restored') for e in ev):
   ctx=dict(id=node+'|'+d,start=d,kind='repair' if 'repair_restored' in ev else 'BREAK',first_permit=None,advances=[],first_mature_permission=None,end=None);contexts.append(ctx)
  if ctx:
   if bool(r.permit_next_open) and ctx['first_permit'] is None:ctx['first_permit']=d
   if 'price_advance' in ev:ctx['advances'].append(d)
   if ctx['advances'] and bool(r.permit_next_open) and ctx['first_mature_permission'] is None:ctx['first_mature_permission']=d
  hist[d]=dict(context=ctx['id'] if ctx else None,mature=bool(ctx and ctx['advances']),permit=bool(r.permit_next_open),advance_count=len(ctx['advances']) if ctx else 0)
  if lo<=d<=hi and (ev or isinstance(r.permission_change,str)):
   timeline.append(dict(node=node,name=name,day=d,events=ev,permission_change=r.permission_change if isinstance(r.permission_change,str) else None,permit=bool(r.permit_next_open),close=float(r.close),context=hist[d]['context'],advance_count=hist[d]['advance_count'],next_observed_session=nextday[d]))
 z=f.loc[lo:hi];inside={h['context'] for d,h in hist.items() if lo<=d<=hi and h['context']};cs=[c for c in contexts if c['id'] in inside or lo<=c['start']<=hi]
 for c in cs:
  s=c['start'];m=c['first_mature_permission'];startclose=float(f.loc[s,'close'])
  c['advance_price_returns_from_start_pct']=[dict(day=d,pct=(float(f.loc[d,'close'])/startclose-1)*100) for d in c['advances'] if d<=hi]
  c['first_advance']=c['advances'][0] if c['advances'] else None
  c['mature_next_session']=nextday.get(m) if m else None
  c['inherited_before_window']=s<lo
  c['advance_count_through_window_end']=sum(d<=hi for d in c['advances'])
 on=z[z.permit_next_open];first=on.index[0] if len(on) else None;fc=next((c for c in cs if c['id']==hist[first]['context']),None) if first else None
 out=dict(node=node,name=name,domain=domain,sector=sector,lo=lo,hi=hi,observations=len(z),permitted=len(on),first_window_permit=first,first_context=fc['id'] if fc else None,first_context_origin=fc['start'] if fc else None,first_context_advance=fc['first_advance'] if fc else None,first_context_mature_permission=fc['first_mature_permission'] if fc else None,first_mature_next_session=fc['mature_next_session'] if fc else None,window_first_close=float(z.close.iloc[0]),window_last_close=float(z.close.iloc[-1]),contexts=cs,events=timeline)
 return out,f,hist,nextday

def capacity(node,f,hist,nxt,ops,variant):
 lo,hi=node['lo'],node['hi'];lookup=defaultdict(list)
 for r in ops:
  if r['CP1_id'] and (variant=='raw_CP1' or r['mobile_Q'] is True):lookup[r['day']].append(r)
 # Fixed-reference capacity only; no prices/positions/returns or original account advancement.
 counts=Counter();trial=set();context=None;reaches={20:None,50:None,80:None};rows=[];ctxsummary=[];active=None
 for d,h in hist.items():
  if d>hi:break
  if h['context']!=context:
   if active:ctxsummary.append(active)
   context=h['context'];counts=Counter();trial=set();active=dict(context=context,first_reaches={20:None,50:None,80:None},max_units=0) if context else None
  rr=lookup.get(d,[])
  if context and h['permit']:
   for r in rr:
    sid=r['sid']
    # Each canonical CP1 here offers a NEW order, including stock ADDs.
    # It is never a remainder of an already partially filled native order.
    if minimum_ok(sid,d) is not True:continue
    if not h['mature']:trial.add(sid)
    else:counts[sid]+=1
  base=sum(min(5,n) for n in counts.values())
  # Pointwise optimistic envelope: the best initial trial may differ by day.
  # This is not one fixed executable choice of the initial trial stock.
  bonus=int(any(counts[s]<5 for s in trial));units=base+bonus
  if context and h['mature']:
   active['max_units']=max(active['max_units'],units)
   for threshold in reaches:
    if units*2>=threshold and active['first_reaches'][threshold] is None:
     active['first_reaches'][threshold]=dict(signal_close=d,next_observed_session=nxt.get(d),outside_evaluation_window=bool(nxt.get(d) and not lo<=nxt[d]<=hi),units=units,unique_postmature_stocks=sum(n>0 for n in counts.values()),optimistic_trial_bonus_units=bonus)
     if lo<=d<=hi and reaches[threshold] is None:reaches[threshold]=dict(active['first_reaches'][threshold],context=context)
   if lo<=d<=hi:rows.append(dict(day=d,context=context,units=units,weight_upper_pct=min(90,units*2),unique_stocks=sum(n>0 for n in counts.values()),trial_bonus_units=bonus))
 if active:ctxsummary.append(active)
 # A context may have capacity before lo; record inheritance, never reset it at lo.
 for c in ctxsummary:
  for k,z in c['first_reaches'].items():
   if z and z['signal_close']<lo and any(d>=lo and hist[d]['context']==c['context'] for d in hist if d<=hi):
    reaches[k]=dict(z,context=c['context'],inherited_capacity_before_window=True)
 valid_contexts={c['id'] for c in node['contexts']};ctxsummary=[c for c in ctxsummary if c['context'] in valid_contexts]
 return dict(variant=variant,first_reaches=reaches,max_slot_capacity_pct=max((x['weight_upper_pct'] for x in rows),default=0),by_context=ctxsummary,daily_capacity=rows,initial_trial_selection='pointwise optimistic envelope, not a fixed executable plan',candidate_scope='raw_CP1 superset' if variant=='raw_CP1' else 'original S0 Q subset, not complete new F1 eligibility')

def main():
 begun=time.monotonic();catalog=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json');focus=read(B/'industry-coverage/run-v1/FOCUS_2023.json');by={x['node_id']:x for x in catalog}
 specs=[('OLD407_global','924旧域全局',B/'historical-shadow/run-v1/OLD407_global_daily.parquet','2024-09-24','2024-12-31','OLD407',None)]
 for x in focus:
  c=by[x['node_id']];specs.append((x['node_id'],x['name'],Path(c['daily_result_path']),'2023-01-01','2023-12-31','NATIVE1709',c['sector']))
 for sid in ['URFI881121','URFI881172']:
  c=by['NATIVE1709_'+sid];specs.append((c['node_id'],c['name'],Path(c['daily_result_path']),'2026-04-30','2026-06-30','NATIVE1709',sid))
 scope=dict(protocol_sha256=sha(O/'PROTOCOL.txt'),specs=[[str(z) for z in x] for x in specs],financial_paths=0,indicator_calculations=0,failed_perstock_candidate='preserved; not repaired',source_F1='saved frozen outputs only')
 if (O/'SCOPE_FREEZE.json').exists():
  prior=json.loads((O/'SCOPE_FREEZE.json').read_text());assert prior['specs']==scope['specs'],'correction must not change fixed cases'
 else:save('SCOPE_FREEZE.json',scope)
 prepared=[describe(*x) for x in specs]
 groups={'2023':defaultdict(list),'2026':defaultdict(list)};daily=defaultdict(lambda:Counter());firstop={}
 paths={'2023':W/'recovery-2023-readiness-20261101/runs/Bdiag/pair/opportunities.jsonl.gz','2026':W/'pvr-slot1-native-readiness-20261101/runs/2025_26/pair/opportunities.jsonl.gz'}
 allowed={'2023':{x[6] for x in specs if x[3]=='2023-01-01'},'2026':{'URFI881121','URFI881172'}}
 for year,p in paths.items():
  seen=set()
  for r in records(p):
   d=r['day'];firstop[year]=min(d,firstop.get(year,d))
   if r['sector'] not in allowed[year] or (year=='2023' and d>'2023-12-31') or (year=='2026' and d>'2026-06-30'):continue
   key=(r['sid'],d,r['CP1_id']);assert key not in seen;seen.add(key);groups[year][r['sector']].append(r)
   c=daily[year,r['sector'],d];c['observed_stock_rows']+=1;c['original_core_Q_true']+=int(r['core_Q'] is True);c['original_mobile_Q_true']+=int(r['mobile_Q'] is True)
   if r['CP1_id']:
    c['raw_fresh_CP1']+=1;c['original_Q_fresh_CP1']+=int(r['mobile_Q'] is True)
    ok=minimum_ok(r['sid'],d)
    c['raw_CP1_reference_minimum_ok']+=int(ok is True);c['raw_CP1_reference_minimum_unknown']+=int(ok is None);c['Q_CP1_reference_minimum_ok']+=int(ok is True and r['mobile_Q'] is True)
 old=defaultdict(dict)
 p=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/RS/accounts-v2/decisions.jsonl.gz')
 for r in records(p):
  d=str(r['at'])[:10]
  if r.get('account')=='I__S0_base' and '2024-09-24'<=d<='2024-12-31':old[d]=dict(original_old_Q_eligible=len(set(r['eligible'])),fresh_CP1=None,CP1_source='not exported/verified in OLD407; native1709 not substituted')
 reports=[];events=[];dayrows=[];keydates=[]
 for node,f,hist,nxt in prepared:
  if node['domain']=='NATIVE1709':
   year='2023' if node['lo'].startswith('2023') else '2026';ops=groups[year][node['sector']]
   node['opportunity_log_first_day']=firstop[year]
   node['capacity_raw_CP1']=capacity(node,f,hist,nxt,ops,'raw_CP1');node['capacity_original_Q_subset']=capacity(node,f,hist,nxt,ops,'original_Q_subset')
   for d in f.loc[node['lo']:node['hi']].index:
    c=dict(daily[year,node['sector'],d]);dayrows.append(dict(node=node['node'],name=node['name'],day=d,permit=hist[d]['permit'],mature=hist[d]['mature'],context=hist[d]['context'],**c))
   for e in node['events']:e['candidate_counts']=dict(daily[year,node['sector'],e['day']])
   keys=defaultdict(list)
   for ctx in node['contexts']:
    keys[ctx['start']].append('true_context_origin')
    if ctx['first_permit']:keys[ctx['first_permit']].append('true_first_permit')
    for d in ctx['advances']:keys[d].append('price_advance')
    if ctx['end']:keys[ctx['end']].append('context_failure')
   for d,labels in sorted(keys.items()):
    keydates.append(dict(node=node['node'],name=node['name'],day=d,labels=labels,outside_fixed_report_window=not node['lo']<=d<=node['hi'],candidate_counts_status='observed' if daily[year,node['sector'],d] else 'unknown_log_coverage',candidate_counts=dict(daily[year,node['sector'],d])))
  else:
   node['capacity_raw_CP1']=dict(status='unknown: no matched OLD407 canonical CP1 opportunity table')
   for e in node['events']:e['candidate_counts']=old.get(e['day'],{})
  reports.append(node);events+=node['events']
 oldsector=[]
 for c in catalog:
  if c['domain']=='OLD407':oldsector.append(describe(c['node_id'],c['name'],Path(c['daily_result_path']),'2024-09-24','2024-12-31','OLD407',c['sector'])[0])
 save('TIMELINES.json',clean(reports));save('ALL_EVENTS_WITH_CANDIDATES.json',clean(events));save('CONTEXT_KEYDATES_WITH_CANDIDATES.json',clean(keydates));save('DAILY_CANDIDATE_COUNTS.json',clean(dayrows));save('OLD11_INDUSTRY_APPENDIX.json',clean(oldsector));save('SOURCE_SHA256.json',SRC)
 save('LOGIC_DEFECT.json',dict(failed_rule='T_i(0) allocated only to actually funded trials; future +2% retains the original asymmetry',example={'same_market_evidence':['A','B'],'initial_A':20000,'initial_B':0,'after_one_identical_advance_A':40000,'after_one_identical_advance_B':20000},verdict='capital funding leaked into market evidence target',minimal_correction='one industry target at trial/mature level; every unheld/held stock faces same eligibility and original per-order ceiling, holdings only consume remaining capacity',new_implemented_policy=False))
 save('COMPLETION.json',dict(completed=True,seconds=time.monotonic()-begun,main_nodes=len(reports),old_appendix_nodes=len(oldsector),daily_candidate_rows=len(dayrows),financial_runs=0,new_indicator_runs=0,ready_for_independent_review=True,limits=['raw_CP1 is broad optimistic mother; original_Q is restrictive old-sector-gated subset','OLD407 CP1 counts unknown','fixed1m/2% close-price minimum-unit preview, no future opening price','capacity is optimistic slots not actual allocations or profit']))
 print('TIMELINE_READY',round(time.monotonic()-begun,3),flush=True)
 for r in reports:
  print(r['name'],r['first_window_permit'],r['first_context_advance'],r['first_mature_next_session'],json.dumps(r['capacity_raw_CP1'].get('first_reaches'),ensure_ascii=False),flush=True)
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e),financial_runs=0));raise
