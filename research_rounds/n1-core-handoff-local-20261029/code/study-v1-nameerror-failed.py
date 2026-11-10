"""Two-arm existing-inventory diagnostic. A factual layers; B existing I/ACT exits."""
from pathlib import Path
import sys,json,gzip,time,hashlib,importlib.util,bisect,collections
from datetime import time as dt,datetime,timezone
from decimal import Decimal as D,getcontext
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/n1-core-handoff-local-20261029';SRC=ROOT/'research_rounds/broad-stage-reentry-20261029';HF=ROOT/'research_rounds/s-entry-mechanism-audit-20261029/code/audit.py'
spec=importlib.util.spec_from_file_location('core_local_existing_tools',HF);H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
Z=D(0);ONE=D(1);END='2026-10-27';STARTED=time.monotonic();stage=sys.argv[1];assert stage in ('sample','full');out=O/stage;out.mkdir(exist_ok=False)
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(x):return pd.Timestamp(x).to_pydatetime()
def near(x,y,n=1):
 bound=D(1).scaleb(max(abs(x),abs(y),ONE).adjusted()-getcontext().prec+1)*max(1,n)*64
 assert abs(x-y)<=bound,('Decimal accounting mismatch',str(x),str(y),str(bound))
 return abs(x-y)
obj=read(SRC/'results/N1.json');layers={x['id']:x for x in obj['layers']};prom={x['layer']:x for x in obj['audit'] if x['kind']=='stage_promote'}
assert len(prom)==1084 and set(pd.read_csv(SRC/'analysis/promotions.csv').layer)==set(prom)
exits=collections.defaultdict(list);buys={};sales=collections.defaultdict(list);fill_audit={};divs=collections.defaultdict(list)
for x in obj['audit']:
 if x['kind']=='pilot_layer_exit':
  for lid in x['layers']:exits[lid].append(x)
 elif x['kind']=='fill':fill_audit[x['receipt']['receipt_id']]=x
 elif x['kind']=='dividend_accrual':divs[x['receivable']['security_id']].append(x['receivable'])
for x in obj['trades']:
 if x['side']=='buy':buys[x['layer']]=x
 else:
  for part in x['parts']:sales[part['layer']].append((x,part))
first={lid:next(x for x in exits[lid] if x['at']>=pr['at']) for lid,pr in prom.items()}
sample=[next(k for k in prom if first[k]['reason']=='core_local_protection'),next(k for k in prom if first[k]['reason']=='I_structure_exit')]
files=[SRC/'results/N1.json',SRC/'results/daily.jsonl.gz',SRC/'analysis/promotions.csv',ROOT/'research_rounds/s-entry-mechanism-audit-20261029/market-cache.parquet',HF,O/'PROTOCOL.txt',Path(__file__)]
if stage=='sample':save(O/'INPUT_IDENTITY.json',dict(mother_layers=list(prom),samples=sample,sha256={str(p):sha(p) for p in files},freeze_utc=datetime.now(timezone.utc).isoformat()))
identity=read(O/'INPUT_IDENTITY.json');assert list(prom)==identity['mother_layers'] and sample==identity['samples']
for p,h in identity['sha256'].items():assert sha(p)==h,p
mother=sample if stage=='sample' else list(prom);ids={layers[k]['sid'] for k in mother}
_,m,_,dd=H.context(ids,False);calendar=[str(d.date()) for d in dd];calendar_set=set(calendar)
cache=pd.read_parquet(files[3]);grids={s:g.set_index('date').sort_index() for s,g in cache[cache.symbol.isin(ids)].groupby('symbol')};known={s:{str(d.date()):r._asdict() for r in g.itertuples()} for s,g in grids.items()}
daily={};quantity=collections.defaultdict(dict);total_qty=collections.defaultdict(dict)
with gzip.open(SRC/'results/daily.jsonl.gz','rt') as f:
 for line in f:
  row=json.loads(line)
  if row['account']!='N1':continue
  day=row['at'][:10];daily[day]=row
  for sid,q in row['positions'].items():
   if sid in ids:total_qty[sid][day]=q
  for x in row['layers']:
   if x['id'] in mother:quantity[x['id']][day]=x['qty']
pauses=[x['at'][:10] for x in obj['audit'] if x['kind']=='risk_checkpoint' and x.get('event')=='pause']
load_seconds=time.monotonic()-STARTED
# Original aggregate sell fills are independently repriced/fee-checked, then allocated
# using exactly the historical share partition. No hypothetical sibling positions.
fee_by={};state={};fee_residue=Z
needed_receipts={t['receipt_id'] for lid in mother for t,part in sales[lid]}
for cost in [1,2]:
 for t in obj['trades']:
  if t['side']!='sell' or t['receipt_id'] not in needed_receipts:continue
  x=fill_audit[t['receipt_id']];sid=t['security_id'];at=stamp(t['at']);fs=m.fees(sid,at);oid=(cost,x['order_id']);paid,accr=state.get(oid,({},{}));price=D(t['raw_open'])*(ONE-D('.0005')*cost);gross=price*t['shares'];kw=dict(shares=t['shares'],par_value=m.rules.get('security_metadata',{}).get(sid,{}).get('par_value'))
  components=fs.incremental('sell',gross,paid,accr,cost,**kw);fee=sum(components.values(),Z);ra=fs.rate_accrual('sell',gross,cost,**kw);state[oid]=({k:paid.get(k,Z)+v for k,v in components.items()},{k:accr.get(k,Z)+v for k,v in ra.items()})
  if cost==1:
   assert price==D(t['price']) and gross==D(t['gross_cny']) and components=={k:D(v) for k,v in x['fee_components'].items()};assert fee==D(t['fees_cny'])
  fee_by[(cost,t['receipt_id'])]=(gross,fee,components)

curves=[];results=[];validations=[];audit_out=[]
def source_div(lid):
 sid=layers[lid]['sid'];acc=[]
 for e in divs[sid]:
  day=e['ex_at'][:10];j=bisect.bisect_left(calendar,day)-1
  if j<0:continue
  prev=calendar[j];q=quantity[lid].get(prev,0);total=total_qty[sid].get(prev,0)
  if q:
   assert total>=q>0;acc.append(dict(date=day,amount=D(e['net_local'])*D(q)/D(total),paid_at=e.get('paid_at'),event_id=e['event_id']))
 return acc

def actual_check(lid):
 x=layers[lid];b=buys[lid];purchase=D(b['gross_cny'])+D(b['fees_cny']);cash=-purchase
 for t,z in sales[lid]:
  gross,fee,_=fee_by[(1,t['receipt_id'])];allocated=(gross-fee)*D(z['shares'])/D(t['shares']);near(allocated,D(z['net_cash']));cash+=allocated
 r1=near(cash,D(x['cash']),len(sales[lid])+1);sd=source_div(lid);r2=near(sum((r['amount'] for r in sd),Z),D(x['dividend']),len(sd)+1)
 assert x['qty']==0 and x['closed'] is not None and all(t['at']>prom[lid]['at'] for t,z in sales[lid])
 return purchase,sd,max(r1,r2)

def factual(lid,cost,end,sd):
 x=layers[lid];s=x['sid'];start=prom[lid]['at'][:10];stock0=D(quantity[lid][start])*m.latest_mark(s,stamp(prom[lid]['at'])).raw_price
 initial_claim=sum((a['amount'] for a in sd if a['date']<=start and (a['paid_at'] is None or a['paid_at']>prom[lid]['at'])),Z)
 initial=stock0+initial_claim;cash=Z;newdiv=Z;fees=Z;slip=Z;rows=[];fills=[];byday=collections.defaultdict(list)
 for t,z in sales[lid]:byday[t['at'][:10]].append((t,z))
 for day in calendar[bisect.bisect_left(calendar,start):bisect.bisect_right(calendar,end)]:
  for t,z in byday[day]:
   gross,fee,comp=fee_by[(cost,t['receipt_id'])];ratio=D(z['shares'])/D(t['shares']);sg=D(t['price'])*z['shares'] if cost==1 else gross*ratio;sf=fee*ratio;net=(gross-fee)*D(z['shares'])/D(t['shares']);cash+=net;fees+=sf;slip+=D(t['raw_open'])*D('.0005')*cost*z['shares'];fills.append(dict(at=t['at'],shares=z['shares'],gross=sg,fees=sf,net=net,source_receipt=t['receipt_id'],shared_layers=len(t['parts'])))
  newdiv=sum((a['amount'] for a in sd if start<a['date']<=day),Z);q=quantity[lid].get(day,0);mv=D(q)*m.latest_mark(s,H.at(day,dt(15,10))).raw_price if q else Z;carry_cash=sum((a['amount'] for a in sd if a['date']<=start and a['paid_at'] and prom[lid]['at']<a['paid_at']<=H.at(day,dt(15,10)).isoformat()),Z);paid_new=sum((a['amount'] for a in sd if start<a['date']<=day and a['paid_at'] and a['paid_at']<=H.at(day,dt(15,10)).isoformat()),Z)
  nav=cash+newdiv+mv+initial_claim;rows.append(dict(layer=lid,cost=cost,arm='A',date=day,shares=q,nav=nav,cash=cash+paid_new+carry_cash,inventory=mv,claim=newdiv-paid_new+initial_claim-carry_cash))
 assert rows and rows[-1]['shares']==0
 return initial,stock0,initial_claim,rows,fills,fees,slip

def wider(lid,cost,stop_day,stop_kind,sd):
 x=layers[lid];s=x['sid'];start=prom[lid]['at'][:10];at=stamp(prom[lid]['at']);q0=quantity[lid][start];quote=m.quote(s,at);initial_stock=q0*m.latest_mark(s,at).raw_price;nextopen=m.sessions['A'][bisect.bisect_right(m.sessions['A'],at)]
 a=H.L.SectorAccount(initial_cash=initial_stock,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);a.available=Z;a.positions[s]=H.L.Position(s,quote.issuer_id,quote.sector_id,quote.currency,[H.L.InventoryLot(q0,nextopen)])
 carry=sum((r['amount'] for r in sd if r['date']<=start and (r['paid_at'] is None or r['paid_at']>prom[lid]['at'])),Z);initial=initial_stock+carry
 acts=collections.defaultdict(list)
 for e in m.actions.get(s,[]):
  if start<e['effective_date']<=END:acts[e['effective_date']].append(e)
 rows=[];request=None;cursor=0;flow=Z;div=Z;fees=Z;slip=Z;fills=[];sharecheck=q0;last_original=x['closed'][:10];independent_residual=Z;feecheck={}
 for day in calendar[bisect.bisect_left(calendar,start):]:
  op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
  if day!=start:
   for e in acts.get(day,[]):H.action(a,m,s,e)
   H.pay(a,m,op)
   if s in a.exits:
    w=m.window(s,op,'sell',cost)
    if w:a.fill_exit(s,w)
   H.pay(a,m,op);H.pay(a,m,cl)
  if day==stop_day and stop_kind!='cutoff' and a.quantity(s) and s not in a.exits:
   qq=m.quote(s,cl)
   if qq is None:raise ValueError('common_exit_quote_unknown:'+str(lid))
   a.request_exit(qq,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));request=cl
  for ev in a.audit_log[cursor:]:
   k=ev['kind']
   if k=='fill':
    f=ev['receipt'];assert f.side=='sell' and f.at>at and (request is not None and f.at>request);assert f.gross_cny==f.shares*ev['price'] and sum(ev['fee_components'].values(),Z)==f.fees_cny
    fs=m.fees(s,f.at);pp,pa=feecheck.get(ev['order_id'],({},{}));kw=dict(shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));ff=fs.incremental('sell',f.gross_cny,pp,pa,cost,**kw);assert ff==ev['fee_components'];ra=fs.rate_accrual('sell',f.gross_cny,cost,**kw);feecheck[ev['order_id']]=({k:pp.get(k,Z)+v for k,v in ff.items()},{k:pa.get(k,Z)+v for k,v in ra.items()})
    sharecheck-=f.shares;flow+=f.gross_cny-f.fees_cny;fees+=f.fees_cny;slip+=abs(ev['price']-ev['raw_open'])*f.shares;fills.append(dict(at=f.at,shares=f.shares,gross=f.gross_cny,fees=f.fees_cny,net=f.gross_cny-f.fees_cny))
   elif k in ('split','split_fraction_floor_proxy'):sharecheck=int(D(sharecheck)*ev['ratio'])
   elif k=='dividend_accrual':div+=ev['receivable'].net_local
  cursor=len(a.audit_log);assert sharecheck==a.quantity(s) and a.available>=0 and not a.buys
  mark=m.latest_mark(s,cl) if sharecheck else None;mv=sharecheck*mark.raw_price if mark else Z;bal=a.balance(cl,{s:mark} if mark else {});res=near(bal['nav'],flow+div+mv,max(1,len(a.audit_log)));independent_residual=max(independent_residual,res)
  # Up to the first original exit request, quantity changes must isolate exactly.
  if day<=first[lid]['at'][:10] and sharecheck!=quantity[lid].get(day,0):raise ValueError('aggregate_split_quantity_not_isolatable:'+str(lid)+':'+day)
  carrycash=sum((r['amount'] for r in sd if r['date']<=start and r['paid_at'] and prom[lid]['at']<r['paid_at']<=cl.isoformat()),Z)
  rows.append(dict(layer=lid,cost=cost,arm='B',date=day,shares=sharecheck,nav=bal['nav']+carry,cash=bal['available']+carrycash,inventory=mv,claim=bal['dividend_receivable']+carry-carrycash,sale_receivable=bal['sale_receivable']))
  if not sharecheck and day>=stop_day and day>=last_original:break
 assert rows and (not a.quantity(s) or rows[-1]['date']==END)
 return rows,fills,fees,slip,a.audit_log,independent_residual,request

# A identity is checked before any wider-arm economics.
prepared={}
for lid in mother:
 prepared[lid]=actual_check(lid)
 if time.monotonic()-STARTED>300:raise TimeoutError('300s total calculation budget')
print(json.dumps(dict(stage=stage,A_identity_passed=len(prepared),load_seconds=load_seconds,sample=sample)),flush=True)
for n,lid in enumerate(mother):
 x=layers[lid];s=x['sid'];pr=prom[lid];start=pr['at'][:10];q0=quantity[lid].get(start);assert q0 and q0>0
 purchase,sd,a_res=prepared[lid];invalid=next((d for d in calendar if d>start and not bool(known[s][d]['i_target'])),None);pause=next((d for d in pauses if d>start),None);term=min([(d,k) for d,k in [(invalid,'I_structure_exit'),(pause,'ACT_pause')] if d]+[(END,'cutoff')]);stop_day,stop_kind=term
 if first[lid]['reason']!='core_local_protection':assert first[lid]['at'][:10]==stop_day,(lid,'A common-decision mismatch',first[lid],term)
 for cost in [1,2]:
  branched=first[lid]['reason']=='core_local_protection';unknown=None
  if branched:
   try:br,bf,bfees,bslip,audit,res,req=wider(lid,cost,stop_day,stop_kind,sd)
   except ValueError as e:
    results.append(dict(layer=lid,symbol=s,cost=cost,status='unknown',reason=str(e),paired_known=False));continue
   end=br[-1]['date']
  else:end=x['closed'][:10];res=Z;audit=[];req=first[lid]['at']
  initial,stock0,carry,ar,af,afees,aslip=factual(lid,cost,end,sd)
  if not branched:br=[dict(r,arm='B') for r in ar];bf=af;bfees=afees;bslip=aslip
  assert [r['date'] for r in ar]==[r['date'] for r in br]
  if not branched:assert all(r['nav']==v['nav'] and r['shares']==v['shares'] for r,v in zip(ar,br))
  for arm,rr in [('A',ar),('B',br)]:
   for r in rr:near(r['nav'],r['cash']+r['inventory']+r['claim']+r.get('sale_receivable',Z),len(rr))
  def risk(rr):
   peak=initial;dd=Z
   for r in rr:peak=max(peak,r['nav']);dd=max(dd,ONE-r['nav']/peak)
   return min(r['nav'] for r in rr)/initial-ONE,dd
  amin,add=risk(ar);bmin,bdd=risk(br);ap=ar[-1]['nav']-initial;bp=br[-1]['nav']-initial;delta=bp-ap
  prediv=sum((r['amount'] for r in sd if r['date']<=start),Z);whole=D(x['cash'])+D(x['dividend']);tail=whole/purchase>=D('.30');posttail=max(ap,bp)/initial>=D('.30')
  actual_div=sum((r['amount'] for r in sd if r['date']>start),Z);near(ar[-1]['nav']-carry,sum((D(p['net_cash']) for t,p in sales[lid]),Z)+actual_div if cost==1 else ar[-1]['nav']-carry,len(sd)+2)
  results.append(dict(layer=lid,symbol=s,source_epoch=json.dumps(x['epoch']),promoted_at=pr['at'],promotion_date=start,sources=json.dumps(pr.get('sources')),cost=cost,status='paired',paired_known=True,original_reason=first[lid]['reason'],initial_shares=q0,initial_stock=stock0,initial_claim=carry,initial_equity=initial,original_purchase_cost=purchase,pre_promotion_accrued_dividend=prediv,pre_promotion_lifecycle_gain=stock0+prediv-purchase,common_exit_decision=stop_day,common_exit_kind=stop_kind,terminal_date=end,A_exit_decision=first[lid]['at'],B_exit_decision=req,A_last_sale=af[-1]['at'] if af else None,B_last_sale=bf[-1]['at'] if bf else None,action_diverged=branched,A_final_equity=ar[-1]['nav'],B_final_equity=br[-1]['nav'],A_post_pnl=ap,B_post_pnl=bp,net_delta=delta,A_return=ap/initial,B_return=bp/initial,A_fees=afees,B_fees=bfees,A_slippage=aslip,B_slippage=bslip,A_min_return=amin,B_min_return=bmin,A_max_drawdown=add,B_max_drawdown=bdd,min_B_minus_A=min(v['nav']-r['nav'] for r,v in zip(ar,br)),A_holding_observations=sum(r['shares']>0 for r in ar),B_holding_observations=sum(r['shares']>0 for r in br),A_terminal_claim=ar[-1]['claim'],B_terminal_claim=br[-1]['claim'],B_terminal_shares=br[-1]['shares'],B_terminal_inventory=br[-1]['inventory'],original_layer_30pct=tail,post_either_30pct=posttail,A_identity_residual=a_res,B_accounting_residual=res))
  curves.extend(ar+br);audit_out.append(dict(layer=lid,cost=cost,A_fills=af,B_fills=bf,B_audit=audit))
 if (n+1)%100==0 or stage=='sample':print(json.dumps(dict(stage=stage,processed=n+1,total=len(mother),seconds=time.monotonic()-STARTED)),flush=True)
 if time.monotonic()-STARTED+float(identity.get('sample_seconds',0) if stage=='full' else 0)>300:raise TimeoutError('300s combined sample/full budget')
frame=pd.DataFrame(H.encoded(results));frame.to_csv(out/'paired-layers.csv',index=False);pd.DataFrame(H.encoded(curves)).to_parquet(out/'daily-paired-equity.parquet',index=False)
with gzip.open(out/'fill-audit.json.gz','wt') as f:json.dump(H.encoded(audit_out),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/paired-layers.csv',dtype=str).fillna('').set_index(['layer','cost']);fu=frame.astype(str).set_index(['layer','cost']);chk=pd.read_csv(out/'paired-layers.csv',dtype=str).fillna('').set_index(['layer','cost']);pd.testing.assert_frame_equal(sm,chk.loc[sm.index],check_exact=True)
for p,h in identity['sha256'].items():assert sha(p)==h,p
elapsed=time.monotonic()-STARTED;save(out/'VERIFICATION.json',dict(passed=True,stage=stage,mother=len(mother),pairs=len(results),A_exact_layers=len(prepared),unknown_pairs=sum(not r['paired_known'] for r in results),sample_full_equal=stage=='full',no_buys_no_external_cash=True,fixed_confirmation_identity=True,fixed_historical_ACT=True,load_seconds=load_seconds,run_wall_seconds=elapsed,total_calculation_seconds=elapsed+float(identity.get('sample_seconds',0)),max_A_accounting_residual=str(max(v[2] for v in prepared.values()))))
if stage=='sample':identity['sample_seconds']=elapsed;save(O/'INPUT_IDENTITY.json',identity)
print(json.dumps(dict(stage=stage,complete=True,pairs=len(results),seconds=elapsed,unknown=sum(not r['paired_known'] for r in results))),flush=True)
