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
events=[];attempts=[];dayrows=[];candidate_checks=0
for e in es:
 key=e['cycle_id'];r=timing[key];sold=stamp(r['sold_at']);request=stamp(r['original_exit_request']);Snet=D(sales[key,1]['net']);first_positive=None;selected=None;first_unknown=None;eventrows=[]
 for day in days[days.index(str(sold.date())):days.index(str(request.date()))+1]:
  tm=H.at(day,dt(15,10))
  if not(sold<tm<request):continue
  assert settled[key,1]<=tm and settled[key,2]<=tm
  if not (eid.get((e['old'],day))==r['original_structure'] and cc[e['old'],day].i_target and cp[day]['on']):continue
  st=states[day];free=set(rawby[day])-set(st['positions'])-set(st['pending_buys'])-set(st['pending_sells'])-set(dec[day]['accepted']);assert free=={x['symbol'] for x in cby[day]};candidate_checks+=1
  clock=H.A.Clock(tm,m.sessions['A'][bisect.bisect_right(m.sessions['A'],tm)],tm.date());cs,order=priority(day,tm,clock);cs=[x for x in cs if x['symbol']!=e['old']];order=[s for s in order if s!=e['old']];unknown21=sum(not x['R21'] for x in cs)
  if unknown21 and first_unknown is None:first_unknown=day
  if order and first_positive is None:first_positive=day
  opts=[project(e,n,day,tm,Snet) for n in order];attempts.extend(opts);eventrows.extend(opts)
  dayrows.append(dict(cycle_id=key,date=day,raw_new_IQ_nonold=len(set(rawby[day])-{e['old']}),free_new_IQ=len(cs),R21_unknown=unknown21,positive_ranked=len(order),feasible_candidates=sum(x['feasible'] for x in opts),unknown_resources=sum(x['unknown'] for x in opts)))
  yes=next((x for x in opts if x['feasible']),None)
  if yes:selected=yes;break
 chosen=dict(cycle_id=key,old=e['old'],old_name=e['name'],sold_at=r['sold_at'],old_original_exit_request=r['original_exit_request'],old_original_exit=e['original_exit'],C_first_IQ=r['policy_IQ'],net_sale_base=Snet,net_sale_cost2=D(sales[key,2]['net']),first_positive_new=first_positive,first_unknown21=first_unknown,D_date=selected['date'] if selected else None,D_new=selected['new'] if selected else None,D_name=selected['new_name'] if selected else None,relation_to_C=('D_before_C' if selected['date']<r['policy_IQ'] else 'same_decision' if selected['date']==r['policy_IQ'] else 'D_after_C') if selected and r['policy_IQ'] else 'D_only_no_C' if selected else 'C_only_no_D' if r['policy_IQ'] else 'neither',candidate_resource_checks=len(eventrows),blocked_reasons=json.dumps(dict(Counter(z for x in eventrows for z in x['reasons'].split('|') if z)),ensure_ascii=False),resource_unknown=any(x['unknown'] for x in eventrows),status='selected_single_attempt' if selected else 'no_resource_feasible_candidate',extra_cap_binding=selected['gross_cap']<Snet if selected else None,selected_cap=selected['gross_cap'] if selected else None,selected_cap_fraction=selected['cap_to_sale'] if selected else None,pending_original_gross_at_selection=selected['pending_other_gross'] if selected else None,selected_same_old_sector=selected['same_old_sector'] if selected else None)
 events.append(chosen)
export('first-D-before-execution.csv',events);export('candidate-resource-checks.csv',attempts);export('decision-coverage.csv',dayrows)
freeze={str(O/f):sha(O/f) for f in ['PROTOCOL.txt','first-D-before-execution.csv','candidate-resource-checks.csv','decision-coverage.csv']};save('SELECTION_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_nextopen_execution_precheck=True,D_future_returns_read=False,D_economic_paths=0,sha256=freeze));print(json.dumps(dict(stage='selection_frozen',mother=69,warning=57,selected=sum(bool(x['D_new']) for x in events),seconds=time.monotonic()-T)),flush=True)
# Only after freezing the same choice: next-open minimum/execution proxies, never returns.
execs=[]
for x in events:
 if not x['D_new']:continue
 new=x['D_new'];day=x['D_date'];tm=H.at(day,dt(15,10));op=m.sessions['A'][bisect.bisect_right(m.sessions['A'],tm)];floor=D(str(cc[new,day].i_floor));basecap=D(x['selected_cap'])
 for cost in [1,2]:
  Snet=D(x['net_sale_base'] if cost==1 else x['net_sale_cost2']);cap=min(basecap,Snet);w=m.window(new,op,'buy',cost);why=[]
  if op>=stamp(x['old_original_exit']):why.append('old_endpoint_before_buy')
  if w is None:why.append('execution_window_unknown')
  else:
   if not w.buy_allowed:why.append('buy_not_allowed')
   if w.capacity_shares<w.quantity.buy_minimum:why.append('capacity_below_minimum')
   if w.raw_open<=floor/D(str(cc[new,str(op.date())].factor)):why.append('next_open_below_frozen_support')
   mg=D(w.quantity.buy_minimum)*w.execution_price;mf=sum(w.fees.incremental('buy',mg,{}, {},cost,shares=w.quantity.buy_minimum,par_value=w.par_value).values(),Z)
   if mg>cap:why.append('execution_gross_cap_below_minimum')
   if mg+mf>Snet:why.append('execution_sealed_cash_below_minimum_with_fees')
  execs.append(dict(cycle_id=x['cycle_id'],cost=cost,new=new,signal=day,next_open=op,executable_minimum_proxy=not why,reasons='|'.join(why),sealed_cash=Snet,gross_cap=cap,capacity=w.capacity_shares if w else None,minimum_shares=w.quantity.buy_minimum if w else None,minimum_cash=mg+mf if w else None,raw_open=w.raw_open if w else None,future_HL_proxy_not_decision_input=True))
export('execution-precheck.csv',execs)
labels={x['cycle_id']:x for x in csvrows(P/'cycle-differences.csv') if x['cost']=='1'};combined=[]
for x in events:
 la=labels[x['cycle_id']];combined.append(x|dict(old_group='benefit37' if D(la['B_minus_A'])>0 else 'harm20',original_tail30=la['original_tail30']=='True',base_proxy=next((z['executable_minimum_proxy'] for z in execs if z['cycle_id']==x['cycle_id'] and z['cost']==1),None),base_exec_reasons=next((z['reasons'] for z in execs if z['cycle_id']==x['cycle_id'] and z['cost']==1),None),cost2_proxy=next((z['executable_minimum_proxy'] for z in execs if z['cycle_id']==x['cycle_id'] and z['cost']==2),None)))
export('coverage57.csv',combined);export('mother69-status.csv',[next((x for x in combined if x['cycle_id']==e['cycle_id']),dict(cycle_id=e['cycle_id'],old=e['old'],old_name=e['name'],status='no_warning_D_equals_A_B_C')) for e in mother])
targets={'605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'}
def coverage(g):
 selected=[x for x in g if x['D_new']]
 return dict(cycles=len(g),has_C=sum(bool(x['C_first_IQ']) for x in g),positive_new=sum(bool(x['first_positive_new']) for x in g),selected=len(selected),base_proxy_pass=sum(x['base_proxy'] is True for x in g),cost2_proxy_pass=sum(x['cost2_proxy'] is True for x in g),relations=dict(Counter(x['relation_to_C'] for x in g)),extra_cap_binding=sum(x['extra_cap_binding'] is True for x in selected),unknown21_cycles=sum(bool(x['first_unknown21']) for x in g),resource_unknown_cycles=sum(x['resource_unknown'] for x in g),base_exec_blocks=dict(Counter(x['base_exec_reasons'] for x in selected if x['base_exec_reasons'])))
sm={k:coverage(g) for k,g in dict(all57=combined,no_C22=[x for x in combined if not x['C_first_IQ']],harm20=[x for x in combined if x['old_group']=='harm20'],benefit37=[x for x in combined if x['old_group']=='benefit37'],tail14=[x for x in combined if x['original_tail30']],targets3=[x for x in combined if x['cycle_id'] in targets]).items()};sm['target_rows']=[x for x in combined if x['cycle_id'] in targets];sm['all_resource_blocks']=dict(Counter(z for x in attempts for z in x['reasons'].split('|') if z));sm['S_alone_enough_but_resource_blocked']=sum(not x['feasible'] and x.get('sealed_cash_alone_pass',False) for x in attempts);sm['selected_rows']=sum(bool(x['D_new']) for x in events);save('SUMMARY.json',sm)
assert all(sha(p)==h for p,h in identity.items());assert all(sha(p)==h for p,h in freeze.items());assert len(combined)==57 and len({x['cycle_id'] for x in combined})==57
save('VERIFICATION.json',dict(passed=True,mother=69,warning=57,original_reserve_rows_exact=reserve_checks,candidate_cache_rows_exact=candidate_checks,selected_before_execution_proxy=True,base_cost2_same_identity=True,new_D_economic_paths=0,indicator_recomputations=0,source_hashes_unchanged=True,seconds=time.monotonic()-T));print(json.dumps(dict(stage='complete',seconds=time.monotonic()-T,summary=sm),ensure_ascii=False,default=str),flush=True)
