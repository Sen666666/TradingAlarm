"""Existing candidates/resources, first D intention, execution precheck only; no D ledger."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS
from collections import Counter,defaultdict
import csv,json,gzip,sys,hashlib,time,bisect,math,importlib.util
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;P=O.parent/'old-side-exit-all69-20261030';F=O.parent/'old-warning-recovery-timing-20261030';E=O.parent/'down-event-transfer-exposure-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');B=R/'pvr-local-finite-capital-20261029/baseline/accounts-v2';S=R/'s-entry-mechanism-audit-20261029';Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def csvrows(p):return list(csv.DictReader(Path(p).open()))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(n,x):pd.DataFrame(x).to_csv(O/n,index=False)
def stamp(t):return datetime.fromisoformat(str(t))
def logs(p):
 with gzip.open(p,'rt') as f:return [x for line in f if (x:=json.loads(line))['account']=='I__S0_base']
sources=[O/'PROTOCOL.txt',Path(__file__),P/'FROZEN_69_CYCLES.csv',P/'full/audit.json.gz',P/'cycle-differences.csv',F/'recovery-with-old-loss-timing.csv',E/'new-candidate-background.csv',B/'I__S0_base.json',B/'daily.jsonl.gz',B/'decisions.jsonl.gz',S/'market-cache.parquet',R/'fat-tail-opportunity-ledger-20261029/full/daily-observed-funnel.parquet']
identity={str(p):sha(p) for p in sources};save('INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),before_D_selection=True,D_paths=0,sha256=identity))
spec=importlib.util.spec_from_file_location('existing_new_use_helpers',S/'code/audit.py');H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
mother=csvrows(P/'FROZEN_69_CYCLES.csv');es=[x for x in mother if x['triggered']=='True'];assert len(es)==57 and len(mother)==69
timing={r['cycle_id']:r for r in csvrows(F/'recovery-with-old-loss-timing.csv')};cache=pd.read_parquet(S/'market-cache.parquet');cc={(r.symbol,str(r.date.date())):r for r in cache.itertuples(index=False)};ids=set(cache.symbol);bundle,m,_,_=H.context(ids,False);meta={r['symbol']:r for r in H.roster()};lines={x.security_id:x for x in bundle.lines};sec={s:meta[s]['sector_id'] for s in ids};days=sorted({x[1] for x in cc})
fn=pd.read_parquet(sources[-1],columns=['date','symbol','event_id']);eid={(r.symbol,str(pd.Timestamp(r.date).date())):r.event_id for r in fn.itertuples(index=False)}
states={x['at'][:10]:x for x in logs(B/'daily.jsonl.gz')};dec={x['at'][:10]:x for x in logs(B/'decisions.jsonl.gz')};obj=read(B/'I__S0_base.json');audit=obj['audit_log'];cp={x['at'][:10]:x for x in audit if x['kind']=='risk_checkpoint'}
ag=defaultdict(list)
for x in audit:
 at=x['receipt']['at'] if x['kind']=='fill' else x.get('at')
 if at:ag[at[:10]].append(x)
pending={};fees={};gross={};reserve_checks=0
for day,state in sorted(states.items()):
 for x in ag[day]:
  if x['kind']=='reserve':pending[x['order_id']]=D(x['gross_budget_cny']);fees[x['order_id']]=D(x['fee_reserved_cny'])
  elif x['kind']=='fill' and x['receipt']['side']=='buy':pending[x['order_id']]=D(x['gross_budget_remaining']);fees[x['order_id']]-=D(x['receipt']['fees_cny'])
  elif x['kind']=='release_buy':pending.pop(x['order_id'],None);fees.pop(x['order_id'],None)
 gross[day]=sum(pending.values(),Z);assert gross[day]+sum(fees.values(),Z)==D(state['order_reserved']);reserve_checks+=1
rawby=defaultdict(list);cby=defaultdict(list)
for r in cache.itertuples(index=False):
 day=str(r.date.date())
 if r.i_buy and r.Q and cp[day]['on']:rawby[day].append(r.symbol)
for x in csvrows(E/'new-candidate-background.csv'):cby[x['date']].append(x)
with gzip.open(P/'full/audit.json.gz','rt') as f:old=json.load(f)
sales={};settled={}
for x in old:
 if x['arm']!='B':continue
 sales[x['cycle_id'],x['cost']]=next(y for y in x['fills'] if y['side']=='sell')
 settled[x['cycle_id'],x['cost']]=stamp(next(y['at'] for y in x['audit'] if y['kind']=='settle' and not y['settlement']['debit']))
def priority(day,tm,clock):
 candidates=cby[day];positive=[x for x in candidates if x['R21'] and float(x['R21'])>0];ss={};sects={};res={}
 for x in positive:
  s=x['symbol'];h=float(x['H1']) if x['H1'] else None;sh=float(x['sector_H1']) if x['sector_H1'] else None
  ss[s]=NS(rank=H.A.Fact(h,tm,tm));res[s]=NS(sector_id=sec[s]);sects[sec[s]]=NS(rank=H.A.Fact(sh,tm,tm))
 ordered=H.A._priority([x['symbol'] for x in positive],ss,sects,res,clock,'S0',[],'first_new_use') if positive else []
 return candidates,ordered
def project(e,new,day,tm,Snet):
 state=states[day];old=e['old'];occ=dec[day]['occupancy'];after=[x for x in occ if x['security_id']!=old];counts=Counter(x['sector_id'] for x in after);why=[]
 if len(after)>=6:why.append('total_slots_full')
 if counts[sec[new]]>=2:why.append('same_sector_issuer_slots_full')
 if sec[new] not in counts and len(counts)>=3:why.append('third_sector_lock')
 if lines[new].issuer_id in {x['issuer_id'] for x in after}:why.append('issuer_already_occupied')
 q=m.quote(new,tm);mark=m.latest_mark(old,tm);oq=int(state['positions'].get(old,0));unknown=q is None or mark is None or oq<=0
 if unknown:why.append('quote_or_old_held_quantity_unknown');return dict(cycle_id=e['cycle_id'],date=day,new=new,feasible=False,unknown=True,reasons='|'.join(why))
 mv=D(oq)*mark.raw_price;N=D(state['nav']);other=D(state['inventory'])-mv;head=D('.90')*N-other-gross[day];cap=max(Z,min(Snet,D('.15')*N,head));minimum=q.quantity.buy_minimum;mp=D(minimum)*q.raw_price*(1+D('.0005'));mf=sum(q.fees.incremental('buy',mp,{}, {},1,shares=minimum,par_value=q.par_value).values(),Z)
 if head<=0:why.append('90pct_headroom_exhausted')
 if mp>cap:why.append('gross_cap_below_minimum')
 if mp+mf>Snet:why.append('sealed_sale_cash_below_minimum_with_fees')
 floor=cc[new,day].i_floor
 if not math.isfinite(floor):why.append('frozen_support_unknown');unknown=True
 return dict(cycle_id=e['cycle_id'],date=day,new=new,new_name=meta[new]['name'],sector=sec[new],old_sector=sec[old],same_old_sector=sec[new]==sec[old],feasible=not why,unknown=unknown,reasons='|'.join(why),net_sale=Snet,original_NAV=N,old_actual_market_value=mv,other_inventory=other,pending_other_gross=gross[day],original_order_reserved=D(state['order_reserved']),original_available_not_used=D(state['available']),cap15=D('.15')*N,head90=head,gross_cap=cap,cap_to_sale=cap/Snet,min_decision_gross=mp,min_decision_fee=mf,min_decision_spend=mp+mf,sealed_cash_alone_pass=mp+mf<=Snet,other_occupancy='|'.join(x['security_id'] for x in after),frozen_floor=str(floor))

OLD=O.parent/'old-warning-new-use-coverage-20261030';prior={x['cycle_id']:x for x in csvrows(OLD/'first-D-before-execution.csv')}
for p,h in read(OLD/'SELECTION_FREEZE.json')['sha256'].items():assert sha(p)==h,p
identity[str(OLD/'SELECTION_FREEZE.json')]=sha(OLD/'SELECTION_FREEZE.json');identity[str(OLD/'first-D-before-execution.csv')]=sha(OLD/'first-D-before-execution.csv');identity[str(O.parent/'old-warning-single-recovery-20261030/full/C-unit-ledgers.csv')]=sha(O.parent/'old-warning-single-recovery-20261030/full/C-unit-ledgers.csv')
save('INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),before_new_economic_returns=True,sha256=identity))
out=[];allchecks=[];D_exact=0
for e in es:
 key=e['cycle_id'];r=timing[key];sold=stamp(r['sold_at']);request=stamp(r['original_exit_request']);Snet=D(sales[key,1]['net']);chosen={};unknown21=False;C_attempts=0;C_blocks=Counter()
 for day in days[days.index(str(sold.date())):days.index(str(request.date()))+1]:
  tm=H.at(day,dt(15,10))
  if not(sold<tm<request):continue
  assert settled[key,1]<=tm and settled[key,2]<=tm
  if not(eid.get((e['old'],day))==r['original_structure'] and cc[e['old'],day].i_target and cp[day]['on']):continue
  clock=H.A.Clock(tm,m.sessions['A'][bisect.bisect_right(m.sessions['A'],tm)],tm.date())
  if 'C_R' not in chosen:
   z=cc[e['old'],day]
   if z.i_buy and z.Q:
    p=project(e,e['old'],day,tm,Snet);C_attempts+=1;C_blocks.update(p['reasons'].split('|') if p['reasons'] else []);allchecks.append(p|dict(arm='C_R'))
    if p['feasible']:chosen['C_R']=p
  if 'D' not in chosen:
   cs,order=priority(day,tm,clock);unknown21|=any(not x['R21'] for x in cs);opts=[project(e,n,day,tm,Snet) for n in order if n!=e['old']];allchecks.extend(x|dict(arm='D') for x in opts);p=next((x for x in opts if x['feasible']),None)
   if p:chosen['D']=p
  if len(chosen)==2:break
 for arm in ['C_R','D']:
  z=chosen.get(arm);oldC=r['policy_IQ'];record=dict(cycle_id=key,arm=arm,old=e['old'],old_name=e['name'],sold_at=r['sold_at'],original_exit_request=r['original_exit_request'],original_exit=e['original_exit'],base_sale=Snet,cost2_sale=D(sales[key,2]['net']),old_C_signal=oldC,signal=z['date'] if z else None,new=z['new'] if z else None,new_name=z['new_name'] if z else None,base_gross_cap=z['gross_cap'] if z else None,cap_to_sale=z['cap_to_sale'] if z else None,original_pending=z['pending_other_gross'] if z else None,status='selected' if z else 'unknown_R21_no_selection' if arm=='D' and unknown21 else 'no_selection',CR_resource_attempts=C_attempts if arm=='C_R' else None,CR_resource_blocks=json.dumps(dict(C_blocks)) if arm=='C_R' else None)
  if arm=='D':
   before=prior[key];assert (record['signal'] or '',record['new'] or '')==(before['D_date'],before['D_new']),(key,'D identity changed')
   if z:assert z['gross_cap']==D(before['selected_cap'])
   D_exact+=1
  else:record['changed_from_C']=(record['signal'] or '')!=oldC
  out.append(record)
for e in mother:
 if e['triggered']=='False':
  for arm in ['C_R','D']:out.append(dict(cycle_id=e['cycle_id'],arm=arm,old=e['old'],old_name=e['name'],status='no_warning_unchanged'))
export('FROZEN_SELECTIONS.csv',out);export('resource-checks.csv',allchecks)
def first(which):
 rr=[x for x in out if which(x)];return min(rr,key=lambda x:(x.get('sold_at') or '9999',x['cycle_id']))['cycle_id'] if rr else None
samples=list(dict.fromkeys(x for x in [first(lambda x:x['status']=='selected' and x['cap_to_sale']<1),first(lambda x:x['arm']=='C_R' and x.get('changed_from_C')),first(lambda x:x['arm']=='D' and x['status']=='selected'),'605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'] if x))
freeze={str(O/x):sha(O/x) for x in ['PROTOCOL.txt','FROZEN_SELECTIONS.csv','resource-checks.csv']};save('SELECTION_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_CR_D_economic_returns=True,sample_ids=samples,sha256=freeze))
cr=[x for x in out if x['arm']=='C_R'];dr=[x for x in out if x['arm']=='D'];summary=dict(mother=69,CR_selected=sum(x['status']=='selected' for x in cr),CR_changed_from_C=sum(x.get('changed_from_C',False) for x in cr),CR_later=sum(bool(x.get('signal')) and bool(x.get('old_C_signal')) and x['signal']>x['old_C_signal'] for x in cr),CR_original_C_but_no_entry=sum(bool(x.get('old_C_signal')) and not x.get('signal') for x in cr),D_selected=sum(x['status']=='selected' for x in dr),D_unknown21=sum(x['status']=='unknown_R21_no_selection' for x in dr),D_all57_identity_exact=D_exact,CR_changes=[x for x in cr if x.get('changed_from_C')],sample_ids=samples,original_reserve_days_exact=reserve_checks,common_project_function=True,D_paths=0,CR_paths=0,seconds=time.monotonic()-T)
assert D_exact==57 and all(sha(p)==h for p,h in identity.items());save('SELECTION_SUMMARY.json',summary);print(json.dumps(summary,ensure_ascii=False,default=str),flush=True)
