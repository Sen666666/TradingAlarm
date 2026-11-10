"""Read-only market/admission reconstruction; never creates a cash account."""
from common_atlas import *
from dataclasses import replace,asdict
from collections import defaultdict,Counter
from datetime import datetime
from decimal import Decimal as D

def stamp(x):return datetime.fromisoformat(str(x))
def event_day(r):return (r['receipt']['at'] if r['kind']=='fill' else r.get('at',''))[:10]
class PathState:
 def __init__(self,sector,mode,scenario,source,decisions,daily):
  self.sector,self.mode,self.scenario=sector,mode,scenario;self.aid=f'{mode}__S0_{scenario}';self.source=Path(source);self.obj=read(self.source/f'{self.aid}.json')
  self.ds={r['at'][:10]:r for r in decisions if r['account']==self.aid};self.daily={r['at'][:10]:r for r in daily if r['account']==self.aid}
  self.events=defaultdict(list)
  for r in self.obj['audit_log']:
   day=event_day(r)
   if day:self.events[day].append(r)
  self.watch={};self.previous=();self.completed=sorted(self.obj['completed_exits'],key=lambda r:r['completed_at']);self.cursor=0;self.snapshots={};self.verified=Counter();self.orders={}
  self.contracts={r['order_id']:r for r in self.obj['audit_log'] if r['kind']=='entry_contract'}
  self.reserves={r['order_id']:r for r in self.obj['audit_log'] if r['kind']=='reserve'}
  self.classes={r['order_id']:r for r in self.obj['audit_log'] if r['kind']=='intent_entry_class'}
  self.pending_before={};pending={};self.cash_before={}
  for r in self.obj['audit_log']:
   if r['kind']=='reserve':self.pending_before[r['order_id']]=str(sum(pending.values(),D(0)));pending[r['order_id']]=D(r['gross_budget_cny'])
   elif r['kind']=='fill' and r['receipt']['side']=='buy':pending[r['order_id']]=D(r['gross_budget_remaining'])
   elif r['kind']=='release_buy':pending.pop(r['order_id'],None)
  for day,rs in self.events.items():
   if day not in self.daily:continue
   cash=D(self.daily[day]['available']);cut=self.daily[day]['at']
   for r in reversed(rs):
    if r.get('at')!=cut:continue
    if r['kind']=='reserve':
     cash+=D(r['gross_budget_cny'])+D(r['fee_reserved_cny']);self.cash_before[r['order_id']]=str(cash)
    elif r['kind']=='release_buy':cash-=D(r['gross_released'])+D(r['fee_released'])

 def step(self,day,clock,base,sectors,market,facts,strict,admission,keep=True):
  d=self.ds[day];events=self.events[day];at=clock.decision_at
  risk=next(r for r in events if r['kind']=='risk_checkpoint');held={r['security_id'] for r in d['occupancy'] if r['has_position']};cancelled=set();down=set();expired=set()
  for r in events:
   k=r['kind'];sid=r.get('sid')
   if k=='intent_create':self.watch[sid]=dict(r)
   elif k=='waiting_support_raise':self.watch[sid]['floor']=r['floor']
   elif k=='intent_end':
    self.watch.pop(sid,None)
    if r['reason'] in ['waiting_floor_breach','updated_floor_breach','structure_or_source','risk_pause']:cancelled.add(sid)
   elif k=='cp_checkpoint' and r['reason'] is not None:down.add(sid)
   elif k=='fast_support_exit':down.add(sid)
   elif k=='buy_day_expiry' and r['rearm']:expired.add(sid)
   elif k=='open_support_reject' and sid not in held:expired.add(sid)
  stocks=[];marketable=None
  for s in base:
   sid=s.security_id
   if self.mode in STRICT and (day not in strict[sid].index or not bool(strict[sid].loc[day,'strict_target'])):s=replace(s,buy_allowed=admission.Fact(False,at,at,source_id='atlas_strict'))
   if self.mode in WAIT:
    if sid in cancelled:s=replace(s,buy_allowed=admission.Fact(False,at,at,source_id='atlas_wait_cancel'))
    elif sid in self.watch and sid not in held:
     r=facts.row(sid,at)
     if r is not None and bool(r.g_ready and r.g_grade>=2):
      if marketable is None:marketable=market.market_buyable(at)
      s=replace(s,buy_allowed=marketable[sid])
   if sid in down:s=replace(s,trend_up=admission.Fact(False,at,at,source_id='atlas_recorded_exit'))
   if not risk['on']:s=replace(s,trend_up=admission.Fact(False,at,at,source_id='atlas_risk'),buy_allowed=admission.Fact(False,at,at,source_id='atlas_risk'))
   stocks.append(s)
  stock={s.security_id:s for s in stocks};sect={s.sector_id:s for s in sectors}
  accepted=d['accepted'];reject=dict(d['rejected']);occupied=[admission.Occupancy(**(r|{'known_at':at})) for r in d['occupancy'] if r['security_id'] not in accepted]
  pre_occupied=[asdict(r) for r in occupied]
  if expired:self.previous=tuple(replace(m,waiting=True,created_at=at,origin='expired_unfilled_recompetition') if m.security_id in expired else m for m in self.previous)
  completions=[]
  while self.cursor<len(self.completed) and stamp(self.completed[self.cursor]['completed_at'])<=at:
   r=self.completed[self.cursor];completions.append(admission.ExitCompletion(r['security_id'],r['event_id'],stamp(r['completed_at'])));self.cursor+=1
  first=admission.decide(clock=clock,variant='S0',securities=stocks,sectors=sectors,previous=self.previous,occupied=occupied,bootstrap=not self.previous,completed_exits=completions)
  eq={e.security_id for e in first.eligibility if e.q is True};assert eq==set(d['eligible']),(self.aid,day,'eligibility',sorted(eq-set(d['eligible'])),sorted(set(d['eligible'])-eq))
  base_mem={m.security_id:m for m in first.memories};current=first;blocked=set();actual=[];actual_rej=[];stages=[]
  reserve_by_sid={r['sid']:r for r in events if r['kind']=='reserve' and r['at'][:10]==day}
  for stage in range(len(stocks)+2):
   resolved={e.security_id:e for e in current.eligibility};mem={m.security_id:m for m in current.memories};occids={o.security_id for o in occupied};candidates=[i for i,m in mem.items() if m.waiting and resolved[i].q is True and i not in occids]
   priority=admission._priority(candidates,stock,sect,resolved,clock,'S0',[],'atlas');sec_order=list(dict.fromkeys(resolved[s].sector_id for s in priority));groups={g:sorted([i for i in candidates if resolved[i].sector_id==g],key=lambda i:(-stock[i].rank.read(clock),i)) for g in sec_order}
   result=dict(priority=priority,sectors=sec_order,groups=groups,selected=list(current.selected),rejected=[list(x) for x in current.rejected],occupied=[asdict(o) for o in occupied])
   if current.selected:stages.append(result)
   got=[];bad=[]
   for sid in current.selected:
    if sid in accepted:
     r=reserve_by_sid[sid];m=mem[sid];expected=f'{sid}:{m.created_at.isoformat()}:{m.origin}';assert r['candidate_id']==expected,(self.aid,day,sid,'memory identity',r['candidate_id'],expected)
     seq=len(actual)+len(got)+1;sec=resolved[sid].sector_id;sector_rank=sec_order.index(sec)+1;stock_rank=groups[sec].index(sid)+1
     self.orders[r['order_id']]=dict(decision_at=day,stage=len(stages)-1,accept_sequence=seq,sector_rank=sector_rank,sector_count=len(sec_order),stock_rank=stock_rank,stock_count=len(groups[sec]),priority_rank=priority.index(sid)+1,candidate_origin=m.origin,candidate_created_at=m.created_at.isoformat(),occupancy_before=[asdict(o) for o in occupied],contract=self.contracts[r['order_id']],reserve=r,entry_class=self.classes[r['order_id']])
     order=self.orders[r['order_id']];oid=r['order_id'];contract=self.contracts[oid];N=D(contract['nav']);mv=D(self.daily[day]['inventory']);pending=D(self.pending_before[oid]);expected_budget=max(D(0),min(N*D('.15'),N*D('.90')-mv-pending));assert abs(expected_budget-D(contract['budget']))<D('1e-8'),(self.aid,day,sid,'budget decomposition',expected_budget,contract['budget'])
     assert D(r['gross_budget_cny'])+D(r['fee_reserved_cny'])<=D(self.cash_before[oid])+D('1e-8')
     quote=market.quote(sid,at);order.update(available_before=self.cash_before[oid],pending_gross_before=self.pending_before[oid],inventory_at_decision=str(mv),cap15=str(N*D('.15')),remaining90=str(N*D('.90')-mv-pending),reference_raw_price=str(quote.raw_price),quantity_rule=asdict(quote.quantity),floor_raw_at_decision=str(D(contract['floor_signal'])/facts.factor(sid,at)))
     row=next(x for x in d['occupancy'] if x['security_id']==sid);occupied.append(admission.Occupancy(**(row|{'known_at':at})));got.append(sid);self.verified['reservation_memories']+=1
    elif sid in reject:bad.append((sid,reject[sid]))
    else:raise AssertionError((self.aid,day,'unexplained recommendation',sid,current.selected,d['accepted'],d['rejected']))
   actual+=got;actual_rej+=bad;blocked.update(sid for sid,_ in bad)
   if not got and not bad:
    self.previous=tuple(base_mem[m.security_id] if m.security_id in blocked else m for m in current.memories);break
   temporary=tuple(replace(m,waiting=False) if sid in blocked else m for sid,m in base_mem.items())
   current=admission.decide(clock=clock,variant='S0',securities=stocks,sectors=sectors,previous=temporary,occupied=occupied,bootstrap=False,completed_exits=())
  else:raise AssertionError('admission trace not bounded')
  assert actual==accepted and actual_rej==[tuple(x) for x in d['rejected']],(self.aid,day,'ack sequence',actual,accepted,actual_rej,d['rejected'])
  self.verified['cutoffs']+=1;self.verified['eligible_sets']+=1
  if accepted and keep:self.snapshots[day]=dict(date=day,eligible=sorted(eq),stages=stages,initial_occupied=pre_occupied,risk=risk,daily=self.daily[day],watch={sid:dict(w) for sid,w in self.watch.items()})

def main(sector,probe=False):
 frozen=load('atlas_frozen_study',ROUND/'code/study.py');R=frozen.setup(sector,ROUND/sector);E=sys.modules['experiment'].E
 def forbidden(*a,**k):raise AssertionError('atlas may not run economic accounts')
 R.run=forbidden
 b,market=R.context();facts=E.Facts(b,market);A=E.admission;strict={sid:pd.read_parquet(OLD_TABLES[sector]/f'{sid}.parquet') for sid in pool(sector).symbol}
 sources=pd.read_csv(ROUND/'comparison/sources.csv');sources=sources[sources.sector.eq(sector)];cache={};states=[]
 if probe:sources=sources[sources.policy.eq('ACP')&sources.scenario.eq('base')]
 for _,r in sources.iterrows():
  source=Path(r.accounts)
  if source not in cache:cache[source]=(rows(source/'decisions.jsonl.gz'),rows(source/'daily.jsonl.gz'))
  assert sha(source/f'{r.policy}__S0_{r.scenario}.json')==r.account_sha256
  states.append(PathState(sector,r.policy,r.scenario,source,*cache[source]))
 dates=sorted(states[0].ds);ratings={};rank_metadata={}
 for j,day in enumerate(dates):
  at=stamp(day+'T15:10:00+08:00');clock,stocks,sectors=facts.packet(at,'I');sr={s.security_id:s.rank.read(clock) if s.rank else None for s in stocks};secr={s.sector_id:s.rank.read(clock) if s.rank else None for s in sectors};order=sorted([s for s,v in sr.items() if v is not None],key=lambda s:(-sr[s],s));seco=sorted([s for s,v in secr.items() if v is not None],key=lambda s:(-secr[s],s));orderidx={sid:i+1 for i,sid in enumerate(order)}
  if not probe:
   rr={}
   for s in stocks:
    sid=s.security_id;r=facts.row(sid,at);sec=s.sector_id.read(clock,for_execution=True)
    rr[sid]=[sr[sid],orderidx.get(sid),sec,None if r is None else float(r.g_grade),bool(r.i_buy) if r is not None and pd.Timestamp(day) in facts.f[sid].index else False,bool(r.i_target) if r is not None else False,bool(strict[sid].loc[day,'strict_target']) if pd.Timestamp(day) in strict[sid].index else False]
   ratings[day]=dict(stocks=rr,sectors={s.sector_id:[secr[s.sector_id],seco.index(s.sector_id)+1 if s.sector_id in seco else None,s.trend_up.read(clock)] for s in sectors},ranked_stocks=len(order),ranked_sectors=len(seco))
  for state in states:state.step(day,clock,stocks,sectors,market,facts,strict,A,keep=not probe)
  if j%100==0:print(sector,j,day,'paths',len(states),flush=True)
 out=O/('probe' if probe else 'data')/sector
 if not probe:
  save(out/'ratings.json.gz',ratings)
  for st in states:save(out/f'{st.mode}-{st.scenario}-trace.json.gz',dict(snapshots=st.snapshots,orders=st.orders))
 save(out/'trace-verification.json',dict(passed=True,economic_accounts_started=0,admission_only=True,paths=len(states),receipts=[dict(account=st.aid,**st.verified) for st in states]))
if __name__=='__main__':main(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='probe')
