"""M3: single combined core-reference hypothesis, not a single-factor ablation."""
from pathlib import Path
import sys,importlib.util,copy,json,inspect,ast,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;V2=ROOT/'mainline_candidate_v2_pending_quote_pause'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
m2=module('m3_frozen_m2',V2/'engine.py');v1=m2.v1;b=v1.b
D=v1.D;ZERO=v1.ZERO;INITIAL=v1.INITIAL;SLIP=v1.SLIP;pd=v1.pd;np=v1.np;dec=v1.dec;day=v1.day;finite=v1.finite;truth=v1.truth;false=v1.false;valid=v1.valid;lineage=v1.lineage;sha=v1.sha;save=v1.save;read=v1.read;Blocked=v1.Blocked;sha_text=v1.sha_text;trigger=v1.trigger
assert sha(V2/'engine.py')=='21434c3c5ab54c5aeac247a4893edad707c848dfc7f02b3b78c7a224531452cb'
# A local namespace reuses unchanged D functions, changing exactly capital-retention allowed keys.
import types
rules=types.ModuleType('m3_reference_rules');sys.modules[rules.__name__]=rules;exec(compile((ROOT/'allocation_ablation_v1/allocation_rules.py').read_text().replace("{'cash_reserve', 'sector_cap'}","{'cash_reserve', 'reference_cap'}"),str(ROOT/'allocation_ablation_v1/allocation_rules.py'),'exec'),rules.__dict__)

def water(lower,es,budget):
 if budget<sum(lower.values(),ZERO):return {},None,'INFEASIBLE_LOWER_EXCEEDS_BUDGET'
 if not es:return {},None,'NO_POSITIVE_E_M'
 lo=ZERO;hi=max(ZERO,budget)/sum(es.values(),ZERO)+max(lower[s]/es[s] for s in es)
 for _ in range(180):
  mid=(lo+hi)/2
  if sum((max(lower[s],mid*es[s]) for s in es),ZERO)>budget:hi=mid
  else:lo=mid
 targets={s:max(lower[s],lo*es[s]) for s in es};total=sum(targets.values(),ZERO);assert abs(total-budget)<=D('1e-18')*max(D(1),abs(budget));assert all(targets[s]>=lower[s] for s in es)
 return targets,lo,'PASS'

class Data(m2.Data):
 def __init__(self,end='2024-10-08'):
  super().__init__(end)
  supplement=ROOT/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_300870_V1.json'
  assert sha(supplement)=='8b575ede04d12775e518216e9be498bb985d4d6b6c0c165f308c09146c291bad'
  self.hashes[str(supplement)]=sha(supplement)
  for e in read(supplement):
   s=e['sid'];dt=pd.Timestamp(e['ex_date'])
   if dt>self.end:continue
   assert (s,dt) not in self.events
   paths=dict(e.get('evidence_hashes',{}))
   for stem in ['source_fact','local_action','signal']:
    if e.get(stem+'_path'):paths[e[stem+'_path']]=e[stem+'_sha256']
   if e.get('notice',{}).get('pdf_path'):paths[e['notice']['pdf_path']]=e['notice']['pdf_sha256']
   for p,h in paths.items():assert sha(Path(p))==h;self.hashes[p]=h
   terms=[x for x in self.actions[s]['events'] if x['effective_date']==e['ex_date']];assert len(terms)==1 and dec(terms[0]['split_ratio'])==1 and dec(terms[0]['cash_per_old_share'])==dec(e['d_source'])
   z=self.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt];fo=dec(prev.adjustment_factor);fn=dec(cur.adjustment_factor);pc=dec(prev.raw_close)
   assert lineage(prev)==lineage(cur) and abs(fo*pc/(pc-dec(e['d_source']))/fn-1)<D('1e-11')
   assert pd.Timestamp(e['record_date'])==prev.name and pd.Timestamp(e['record_date'])<dt<=pd.Timestamp(e['pay_date'])
   assert abs(fo/dec(e['factor_old'])-1)<D('1e-11') and abs(fn/dec(e['factor_new'])-1)<D('1e-11') and dec(e['d_cash'])>=0
   self.events[(s,dt)]=dict(e,factor_old=str(fo),factor_new=str(fn));self.admission.append(dict(sid=s,sector51=self.sid_sector[s],ex_date=day(dt),event_id=e['economic_event_id_candidate'],status='BOUNDED_RESEARCH_NET80_ONLY',factor_bridge_verified=True,not_PIT=True,not_production_admission=True))
  calendar_path=b.R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet';self.cal=pd.read_parquet(calendar_path,columns=[]).index;self.hashes[str(calendar_path)]=sha(calendar_path)
  for p in [O/'engine.py',O/'CONTRACT.md']:self.hashes[str(p)]=sha(p)

class Engine(m2.Engine):
 def __init__(self,data):
  super().__init__(data);self.reference={};self.reference_log=[];self.capital_lots=[];self.reference_requests=[];self._ref_spent={}
 def close(self,d,prev):
  nav=self.nav(d,'raw_close');pending=[]
  for s,a in sorted(self.active.items()):
   sec=self.d.sectors[self.d.sid_sector[s]].loc[d];z=self.d.z(s,d);f=self.d.f(s,d);c=self.d.c(s,d)
   if not valid(z) or not finite(z.get('raw_close')) or z['raw_close']<=0 or lineage(z)!=a['origin']:raise Blocked(f'{day(d)} {s} CLOSE_INVALID')
   self.invalidate_cp(a,d,'CLOSE','raw_close');adj=dec(z['raw_close'])*a['factor'];i=f.get('i_target');reason='WAIT';net=self.net(a,d,'raw_close')
   if false(i):a['exit']='I_INVALID'
   elif truth(i) and finite(f.get('i_floor')) and f['i_floor']>0:a['ifloor']=max(a['ifloor'],dec(f['i_floor']))
   if adj<=a['ifloor']:a['exit']='I_CLOSE_PROTECTION'
   if not a.get('confirmed_history',False) and sec.state==0:a['exit']=a['exit'] or 'TRIAL_SECTOR_FALSE'
   fresh=truth(c.get('receipt')) and finite(c.get('candidate')) and c['candidate']>0 and day(d)>=a['seed_day']
   if fresh:
    fl=dec(c['candidate']);ident=sha_text([s,day(d),str(fl),a['origin']]);new=dict(id=ident,date=day(d),floor=fl,origin=a['origin'],consumed=False,invalid=False)
    if adj>fl:
     if a.get('cp'):self.eventlog(a,d,'CLOSE','SUPERSEDED',a['cp'],replacement=ident)
     a['cp']=new;self.eventlog(a,d,'CLOSE','CREATED_AFTER_SEED',new,candidate=str(fl))
    else:self.eventlog(a,d,'CLOSE','RECEIPT_ALREADY_BREACHED',new)
   for l in a['lots']:
    if l['kind']=='ADD':
     if adj<=l['floor']:l['exit']='CP_CLOSE_PROTECTION'
     l['floor']=max(l['floor'],a['ifloor'],dec(c['candidate']) if fresh else ZERO)
     if adj<=l['floor']:l['exit']='CP_CLOSE_PROTECTION'
   cpk=a.get('cp');has_i=truth(i) and finite(f.get('i_floor')) and f['i_floor']>0;cpstate_known=truth(c.get('receipt')) or false(c.get('receipt'))
   if a['exit'] or any(l.get('exit') for l in a['lots']):reason='LOCKED_EXIT'
   elif not has_i:reason='I_UNKNOWN'
   elif sec.state==-1:reason='SECTOR_UNKNOWN'
   elif self.d.m(s,d).M!=1:reason='MAINLINE_UNKNOWN' if self.d.m(s,d).M==-1 else 'NOT_MAINLINE'
   elif not cpstate_known:reason='CP_UNKNOWN'
   elif cpk is None or not self.cpvalid(a,cpk,z,'raw_close'):reason='NO_VALID_UNCONSUMED_POSTSEED_CP'
   elif net<=0:reason='CLOSE_NET_NOT_POSITIVE'
   else:
    self.info_close(a,d,cpk,net)
    budget=min(D('.02')*a['nav0'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,'raw_close')));cap=self.d.cap[s].get(d,np.nan)
    if not finite(cap):reason='CAPACITY_UNKNOWN'
    else:
     q=self.d.size(s,d,dec(z['raw_close'])*(1+SLIP),budget,int(cap))
     if q:
      a['plan']=dict(kind='ADD',sid=s,signal_day=day(d),cp_date=cpk['date'],cp_id=cpk['id'],budget=budget,planned_q=q,capacity=int(cap),close_net=str(net),origin=a['origin'],factor=a['factor']);self.decorate(a['plan'],d);reason='ADD_PLANNED'
     else:reason='ADD_ROUND_SLOT_NO_LEGAL_Q'
   self.candidates.append(dict(day=day(d),phase='CLOSE',sid=s,round_id=a['id'],event='ADD_GATE',decision=reason,sector_state=int(sec.state),sector_strength=bool(sec.strength),cp_id=cpk['id'] if cpk else None,close_net=str(net),add_count=a['add_count']))
  for s in self.d.ids:
   secframe=self.d.sectors[self.d.sid_sector[s]];sec=secframe.loc[d]
   typ=trigger(int(secframe.at[prev,'state']),int(sec.state),int(self.d.stock.at[prev,s]),int(self.d.stock.at[d,s]));z=self.d.z(s,d);f=self.d.f(s,d)
   if typ is None:
    if self.d.stock.at[d,s]==-1:self.candidates.append(dict(day=day(d),phase='CLOSE',sid=s,event='NO_NEW_TICKET',decision='STOCK_UNKNOWN'))
    continue
   reason='PASS';q=None;cap=self.d.cap[s].get(d,np.nan)
   if s in self.active:reason='HELD_NO_NEW_ATTEMPT'
   elif s in self.live_tickets():reason='TICKET_ALREADY_RETAINED'
   elif not truth(f.get('i_target')):reason='I_INELIGIBLE_OR_UNKNOWN'
   elif not valid(z) or not finite(z.get('raw_close')) or z['raw_close']<=0:reason='INVALID_CLOSE_SOURCE'
   elif not finite(f.get('i_floor')) or f['i_floor']<=0 or not finite(z.get('adjustment_factor')) or z['adjustment_factor']<=0:reason='INVALID_I_FLOOR_OR_FACTOR'
   elif dec(z['raw_close'])*dec(z['adjustment_factor'])<=dec(f['i_floor']):reason='CLOSE_BELOW_PROTECTION'
   elif not finite(cap):reason='CAPACITY_UNKNOWN'
   else:
    q=self.d.getmeta(s,d)[0].buy_minimum;p=dec(z['raw_close'])*(1+SLIP)
    if q>int(cap):reason='MIN_LOT_CAPACITY_REJECT'
    elif q*p+self.d.fee(s,d,q,p,'buy')>D('.02')*nav:reason='EXTREME_MIN_LOT_2PCT_REJECT'
   self.candidates.append(dict(day=day(d),phase='CLOSE',sid=s,event=typ,decision=reason,planned_q=q))
   if reason=='PASS':pending.append(dict(kind='SEED',birth_type=typ,sid=s,signal_day=day(d),ifloor=dec(f['i_floor']),factor=dec(z['adjustment_factor']),origin=lineage(z),budget=D('.02')*nav,nav0=nav,planned_q=q,capacity=int(cap)))
  pending=[self.decorate(r,d) for r in pending]
  pending+=self.refresh_tickets(d)
  self.register_pay(d)
  self.plan_transfers(d,pending)
  nav=self.nav(d,'raw_close');mv=sum((self.qvalue(a,d,'raw_close') for a in self.active.values()),ZERO)
  self.ledger.append(dict(day=day(d),cash=str(self.cash),receivable=str(self.receivable),market_value=str(mv),NAV=str(nav),net_liquidation_NAV=str(self.cash+self.receivable+sum((self.quantity(a)*dec(self.d.z(s,d)['raw_close'])*(1-SLIP)-self.d.fee(s,d,self.quantity(a),dec(self.d.z(s,d)['raw_close'])*(1-SLIP),'sell') for s,a in self.active.items()),ZERO)),stocks=len(self.active),shares=sum(self.quantity(a) for a in self.active.values()),weight_pct=str(100*mv/nav),fees_paid=str(sum((a['fees'] for a in self.archive.values()),ZERO))))
  for s,a in self.active.items():
   for l in a['lots']:self.holdings.append(dict(day=day(d),round_id=a['id'],sid=s,lot_id=l['id'],kind=l['kind'],qty=l['q'],bought=l['bought'],raw_mark=str(self.d.z(s,d)['raw_close']),market_value=str(l['q']*dec(self.d.z(s,d)['raw_close'])),protection_signal=str(a['ifloor'] if l['kind']=='SEED' else l['floor']),factor=str(a['factor']),cp_id=l.get('cp_id'),locked_exit=a['exit'] or l.get('exit')))
  self.attribute(d,nav)
  return pending
 def noncash(self,r,d,field,nav,sv):
  s=r['sid'];a=self.active.get(s);z=self.d.z(s,d);raw=dec(z[field]);p=raw*(1+SLIP);reason='PASS';net=None
  if r['kind']=='ADD':
   if a is None or a['exit'] or any(l.get('exit') for l in a['lots']):reason='LOCKED_EXIT'
   elif a.get('cp') is None or a['cp']['id']!=r['cp_id'] or not self.cpvalid(a,a['cp'],z,field):reason='CP_INVALID_OR_REPLACED'
   else:
    net=self.net(a,d,field)
    if net<=0:reason='OPEN_NET_NOT_POSITIVE' if field=='raw_open' else 'CLOSE_NET_NOT_POSITIVE'
    elif raw*a['factor']<=max(a['ifloor'],a['cp']['floor']):reason='BELOW_PROTECTION'
   budget=min(r['budget'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,field))) if a else ZERO
  else:
   if a is not None:reason='ALREADY_HELD'
   elif raw*dec(z['adjustment_factor'])<=r['ifloor']:reason='OPEN_BELOW_PROTECTION'
   budget=r['budget']
  caps=dict(attempt_budget=budget,stock_cap=max(ZERO,D('.10')*nav-sv.get(s,ZERO)))
  q=0
  if reason=='PASS':
   if r['kind']=='SEED':
    q=self.d.getmeta(s,d)[0].buy_minimum
    if q>r['planned_q'] or q>r['capacity']:reason='DATED_LOT_OR_CAPACITY_CHANGED'
    elif q*p+self.d.fee(s,d,q,p,'buy')>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
   else:
    q=self.d.size(s,d,p,min(caps.values()),min(r['planned_q'],r['capacity']))
    if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
  return dict(q=q if reason=='PASS' else 0,reason=reason,p=p,net=net,caps=caps,structural=reason=='PASS' or reason.startswith('MIN_LOT_CAPITAL_REJECT'))
 def alloc_open(self,d,pending):
  self._ref_spent={};self.info_open(d);nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()};reqs=[]
  for a in self.active.values():
   if a.get('plan'):reqs.append(a['plan'])
   a['plan']=None
  reqs=self.request_key_groups(reqs+pending);released=self.execute_transfers(d,reqs,nav,sv);cash=self.cash;reserved=[];main_filled=ZERO
  for rank,r in enumerate(reqs):
   s=r['sid'];x=self.noncash(r,d,'raw_open',nav,sv);q=x['q'];p=x['p'];caps=dict(x['caps'],cash_reserve=max(ZERO,cash-D('.10')*nav),reference_cap=self.reference_cap(r,sv));reason=x['reason'];a=self.active.get(s);qr=self.d.getmeta(s,d)[0]
   rawq=qr.buy_minimum if r['kind']=='SEED' else q;rawcost=rawq*p+self.d.fee(s,d,rawq,p,'buy') if rawq else ZERO
   if reason=='PASS':
    if r['kind']=='SEED':
     if rawcost>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
    else:
     q=self.d.size(s,d,p,min(caps.values()),min(q,r['planned_q'],r.get('_ref_q',q)))
     if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
   violated=sorted(k for k,v in caps.items() if rawcost>v)
   row=dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],plan_day=r['plan_day'],decision=reason,allocation_rank=rank+1,M=r['M'],E=str(r['E']),M_streak=r['M_streak'],cp_id=r.get('cp_id'),close_net=r.get('close_net'),open_net=str(x['net']) if x['net'] is not None else None,planned_q=r['planned_q'],executed_q=q if reason=='PASS' else 0,violated_caps=violated,reference_close_q=r.get('_ref_q'),reference_close_rank=r.get('_ref_rank'),**{k:str(v) for k,v in caps.items()});self.candidates.append(row);self.request_details.append(row)
   if r['kind']=='SEED':
    t=self.live_tickets().get(s)
    if t:
     rules.retry_open_outcome(t,filled=reason=='PASS',structural_pass=x['structural'],all_in_cost=rawcost,caps=caps);self.pause_unknown_ticket(t,r,reason);self.ticket_event(t,d,'OPEN_OUTCOME',decision=reason,violated_caps=violated)
    elif reason!='PASS':
     t=rules.ticket_from_seed(r,rawcost,caps,structural_pass=x['structural'])
     if t:
      t['current_factor']=dec(self.d.z(s,d)['adjustment_factor']);t['last_verified_day']=day(d);self.tickets[s]=t;self.pause_unknown_ticket(t,r,reason);self.ticket_event(t,d,'CAPITAL_REJECT_RETAINED',decision=reason,violated_caps=violated)
   if reason!='PASS':continue
   cost=q*p+self.d.fee(s,d,q,p,'buy');cash-=cost;self._ref_spent[self.d.sid_sector[s]]=self._ref_spent.get(self.d.sid_sector[s],ZERO)+cost;sv[s]=sv.get(s,ZERO)+cost;reserved.append((r,q,p,x['net'],cost));main_filled+=cost if r['M']==1 else ZERO
  for r,q,p,net,cost in reserved:
   s=r['sid']
   if r['kind']=='SEED':
    self.seq[s]+=1;rid=f'{s}|{self.seq[s]}|{r["signal_day"]}';a=dict(id=rid,sid=s,signal_day=r['signal_day'],birth_type=r['birth_type'],nav0=r['nav0'],seed_day=day(d),cashflow=ZERO,dividend=ZERO,fees=ZERO,lots=[],ifloor=r['ifloor'],factor=dec(self.d.z(s,d)['adjustment_factor']),origin=r['origin'],exit=None,plan=None,cp=None,add_count=0,confirmed_history=False);self.active[s]=a;self.archive[rid]=a
   else:a=self.active[s]
   cp=a['cp'] if r['kind']=='ADD' else None;fl=max(a['ifloor'],cp['floor']) if cp else a['ifloor'];lid=f'{a["id"]}|{len(self.orders)+1}'
   if cp:
    stop=fl/a['factor']*(1-SLIP);stop_net=q*stop-self.d.fee(s,d,q,stop,'sell');loss=cost-stop_net
    self.floor_risk.append(dict(day=day(d),sid=s,round_id=a['id'],cp_id=cp['id'],pre_add_close_net=r.get('close_net'),pre_add_open_net=str(net),add_qty=q,buy_all_in=str(cost),known_protection_signal=str(fl),hypothetical_raw_sell=str(stop),incremental_known_floor_loss=str(loss),not_profit_covered=loss>net,not_stop_execution_guarantee=True))
   a['lots'].append(dict(id=lid,kind=r['kind'],q=q,bought=day(d),floor=fl,cp_id=cp['id'] if cp else None));self.order(a,d,'BUY_'+r['kind'],q,p,'MAINLINE_CP_ADD' if cp else 'NEW_OR_RETAINED_A_B_MIN_UNIT',signal_day=r['signal_day'],lot_id=lid,cp_id=cp['id'] if cp else None,close_net=r.get('close_net'),open_net=str(net) if net is not None else None,frozen_attempt_NAV=str(a['nav0']),all_in_cost=str(cost),M=r['M'],E=str(r['E']))
   if cp:
    assert a.get('confirmed_history'), 'FILLED_ADD_MUST_INFORMATION_CONFIRM';cp['consumed']=True;a['add_count']+=1;self.eventlog(a,d,'OPEN','CONSUMED_ON_FILL',cp);a['cp']=None
  assert self.cash==cash
  self.transfers.append(dict(day=day(d),phase='OPEN',event='RECEIVER_FUNDING',released_cash=str(released),M_actual_buy_cost=str(main_filled),cash_after_all_buys=str(self.cash),cash_above_frozen_reserve=str(self.cash-D('.10')*nav)))
  sec={k:ZERO for k in self.d.sector_ids}
  for s,a in self.active.items():sec[self.d.sid_sector[s]]+=self.qvalue(a,d,'raw_open')
  actual_nav=self.nav(d,'raw_open')
  for k,v in sec.items():self.open_exposure.append(dict(day=day(d),sector51=k,market_value=str(v),NAV=str(actual_nav),weight_pct=str(100*v/actual_nav),frozen_allocation_NAV=str(nav)))

 def pause_unknown_ticket(self,t,r,reason):
  if r['M']==-1 and t['status']=='RETAINED':t['status']='PAUSED';t['reason']='MAINLINE_UNKNOWN_REFERENCE_PAUSE'
 def sector_values(self,sv):
  out={s:ZERO for s in self.d.sector_ids}
  for s,v in sv.items():out[self.d.sid_sector[s]]+=v
  return out
 def request_key_groups(self,reqs):
  return sorted(reqs,key=lambda r:(r.get('_ref_rank',10**9),r.get('cp_date',r['signal_day']),r['sid']))
 def reference_cap(self,r,sv,spent=None):
  if r['M']==0:return D('Infinity')
  if r['M']!=1 or r.get('_ref_q',0)<=0:return ZERO
  sec=self.d.sid_sector[r['sid']];ref=self.reference;spent=self._ref_spent if spent is None else spent
  return max(ZERO,min(ref.get('T',{}).get(sec,ZERO)-self.sector_values(sv)[sec],ref.get('envelope',{}).get(sec,ZERO)-spent.get(sec,ZERO)))
 def classify_reference(self,d):
  nxt=self.d.cal[self.d.cal.get_loc(d)+1] if self.d.cal.get_loc(d)+1<len(self.d.cal) else d+pd.Timedelta(days=1)
  sv={s:self.qvalue(a,d,'raw_close') for s,a in self.active.items()};sector=self.sector_values(sv);fixed=dict(sector);core={s:ZERO for s in self.d.sector_ids};rows=[];stress=ZERO
  buys={o['lot_id']:o for o in self.orders if o['side'].startswith('BUY')}
  for s,a in sorted(self.active.items()):
   sec=self.d.sid_sector[s];m=self.d.m(s,d);z=self.d.z(s,d);f=self.d.f(s,d);c=self.d.c(s,d);st=int(self.d.stock.at[d,s]);qr=self.d.getmeta(s,nxt)[0];mark=dec(z['raw_close']);net=self.net(a,d,'raw_close')
   winner=a.get('confirmed_history',False) and m.M==1 and net>0
   seedq=sum(o['qty'] for o in self.orders if o['round_id']==a['id'] and o['side']=='BUY_SEED')
   assert seedq>0,('ORIGINAL_SEED_ORDER_MISSING',a['id'])
   adds=sorted((l for l in a['lots'] if l['kind']=='ADD'),key=lambda l:(l['bought'],buys.get(l['id'],{}).get('order_seq',10**9),l['id']));first=adds[0]['id'] if adds else None
   unknown=[]
   if m.M==-1 or not finite(m.E):unknown.append('M_OR_E_UNKNOWN')
   if st==-1:unknown.append('STOCK_M3_UNKNOWN')
   if not valid(z) or not m2.known_origin(z) or lineage(z)!=a['origin']:unknown.append('QUOTE_SOURCE_UNKNOWN')
   if not (truth(f.get('i_target')) or false(f.get('i_target'))) or (truth(f.get('i_target')) and (not finite(f.get('i_floor')) or f['i_floor']<=0)):unknown.append('I_UNKNOWN')
   if not (truth(c.get('receipt')) or false(c.get('receipt'))):unknown.append('CP_UNKNOWN')
   locked=bool(a['exit'] or any(l.get('exit') for l in a['lots']))
   seed_ok=not a.get('confirmed_history',False) and not a.get('information_pending') and a['add_count']==0 and m.M==0 and int(self.d.sectors[sec].at[d,'state']) in [0,1] and st in [0,1] and finite(m.E)
   for l in a['lots']:
    cq=(l['q'] if l['kind']=='SEED' else min(l['q'],seedq) if l['id']==first else 0) if winner and not locked else 0
    why='UNCONFIRMED_NON_MAINLINE_SEED' if l['kind']=='SEED' and seed_ok else 'WEAK_SECTOR_ADD_LAYER' if l['kind']=='ADD' and m.M==0 and bool(m.W) else 'MAINLINE_REFERENCE_SURPLUS_ADD' if l['kind']=='ADD' and m.M==1 and finite(m.E) else None
    eligible=why is not None and not unknown and not locked and nxt>pd.Timestamp(l['bought'])
    mobile=qr.sell_floor(l['q']-cq,self.quantity(a)) if eligible else 0
    if l['kind']=='SEED' and mobile!=l['q']:mobile=0
    core[sec]+=cq*mark;fixed[sec]-=mobile*mark
    cost=mobile*mark-(mobile*mark*(1-SLIP)-self.d.fee(s,nxt,mobile,mark*(1-SLIP),'sell')) if mobile else ZERO;stress+=cost
    rows.append(dict(day=day(d),sid=s,round_id=a['id'],sector51=sec,lot_id=l['id'],kind=l['kind'],bought=l['bought'],qty=l['q'],raw_mark=mark,market_value=l['q']*mark,core_qty=cq,core_value=cq*mark,frozen_qty=l['q']-mobile,frozen_value=(l['q']-mobile)*mark,mobile_qty=mobile,mobile_value=mobile*mark,mobile_sell_stress=cost,donor_reason=why,unknown=unknown,locked=locked,confirmed_history=a.get('confirmed_history',False),current_winner=winner,round_net=net,original_seed_qty=seedq,earliest_surviving_ADD=first,stock_state=st,E=dec(m.E) if finite(m.E) else None,M=int(m.M)))
  es={sec:dec(self.d.main[sec].loc[d].E) for sec in self.d.sector_ids if self.d.main[sec].loc[d].M==1 and finite(self.d.main[sec].loc[d].E) and self.d.main[sec].loc[d].E>0}
  nav=self.nav(d,'raw_close');outside=sum((v for sec,v in fixed.items() if sec not in es),ZERO);budget=nav-D('.1')*nav-self.receivable-outside-stress;lower={sec:fixed[sec] for sec in es};targets,lam,status=water(lower,es,budget);T=dict(fixed);T.update(targets)
  # Infeasible/empty reference authorizes no mainline additions or mainline surplus donors.
  enabled=status=='PASS';envelope={sec:max(ZERO,T[sec]-sector[sec]) if enabled and sec in es else ZERO for sec in self.d.sector_ids}
  ref=dict(day=day(d),next_day=day(nxt),NAV=nav,cash=self.cash,receivable=self.receivable,reserve=D('.1')*nav,sector_value=sector,fixed=fixed,core=core,E=es,stress=stress,outside_fixed=outside,budget=budget,lower=lower,T=T,lambda_value=lam,status=status,envelope=envelope,frozen_lot_qty={r['lot_id']:r['frozen_qty'] for r in rows},rows=rows)
  self.capital_lots.extend(rows)
  for sec in self.d.sector_ids:self.reference_log.append(dict(day=day(d),sector51=sec,M=int(self.d.main[sec].loc[d].M),E=dec(self.d.main[sec].loc[d].E) if finite(self.d.main[sec].loc[d].E) else None,actual_value=sector[sec],core=core[sec],other_frozen=fixed[sec]-core[sec],fixed=fixed[sec],T=T[sec],buy_envelope=envelope[sec],budget=budget,stress=stress,receivable=self.receivable,outside_fixed=outside,status=status,lambda_value=lam))
  return ref
 def plan_requests(self,d,reqs):
  sv={s:self.qvalue(a,d,'raw_close') for s,a in self.active.items()};spent={};remaining=list(reqs);rank=0;details=[]
  while remaining:
   sectors=self.sector_values(sv)
   def key(r):
    sec=self.d.sid_sector[r['sid']];gap=max(ZERO,self.reference['T'].get(sec,ZERO)-sectors[sec]) if r['M']==1 and sec in self.reference['E'] and self.reference['status']=='PASS' else ZERO
    # Sector request heads ADD first, then date; global sector priority uses its oldest request.
    return (-gap,-r['M_streak'],-r['E'],r.get('cp_date',r['signal_day']),r['sid'])
   mains=[r for r in remaining if r['M']==1];pool=mains if mains else remaining
   heads=[]
   for sec in sorted({self.d.sid_sector[r['sid']] for r in pool}):heads.append(min((r for r in pool if self.d.sid_sector[r['sid']]==sec),key=lambda r:(r['kind']!='ADD',r.get('cp_date',r['signal_day']),r['sid'])))
   r=min(heads,key=key) if mains else min(pool,key=lambda r:(r['signal_day'],r['sid']));remaining.remove(r);rank+=1;s=r['sid'];sec=self.d.sid_sector[s];x=self.noncash(r,d,'raw_close',self.reference['NAV'],sv);q=x['q'];cap=max(ZERO,min(self.reference['T'][sec]-sectors[sec],self.reference['envelope'][sec]-spent.get(sec,ZERO))) if r['M']==1 else D('Infinity') if r['M']==0 else ZERO
   if self.reference['status']!='PASS' and r['M']==1:cap=ZERO
   if r['M']==1 and sec not in self.reference['E']:cap=ZERO
   reason=x['reason'];cost=q*x['p']+self.d.fee(s,d,q,x['p'],'buy') if q else ZERO
   if reason=='PASS':
    if r['kind']=='SEED':
     if cost>cap:q=0;reason='REFERENCE_CAP'
    else:
     q=self.d.size(s,d,x['p'],min(min(x['caps'].values()),cap),q)
     if not q:reason='REFERENCE_CAP'
    cost=q*x['p']+self.d.fee(s,d,q,x['p'],'buy') if q else ZERO
   r['_ref_q']=q;r['_ref_rank']=rank;r['_reference_close_cost']=cost
   if q and r['M']==1:sv[s]=sv.get(s,ZERO)+cost;spent[sec]=spent.get(sec,ZERO)+cost
   details.append(dict(day=day(d),phase='CLOSE',sid=s,sector51=sec,kind=r['kind'],M=r['M'],E=r['E'],cp_id=r.get('cp_id'),signal_day=r['signal_day'],rank=rank,base_planned_q=r['planned_q'],reference_q=q,reference_cap=cap,all_in_cost=cost,decision=reason))
  self.reference_requests.extend(details);return self.request_key_groups(reqs),details
 def demand(self,reqs,d,field,nav,sv):
  total=ZERO;details=[];sv=dict(sv);spent={}
  for r in self.request_key_groups(reqs):
   if r['M']!=1:continue
   x=self.noncash(r,d,field,nav,sv);cap=self.reference_cap(r,sv,spent);q=min(x['q'],r.get('_ref_q',0));p=x['p']
   if r['kind']=='SEED':q=q if q and q*p+self.d.fee(r['sid'],d,q,p,'buy')<=cap else 0
   else:q=self.d.size(r['sid'],d,p,min(min(x['caps'].values()),cap),q) if q else 0
   cost=q*p+self.d.fee(r['sid'],d,q,p,'buy') if q else ZERO;total+=cost;sec=self.d.sid_sector[r['sid']];spent[sec]=spent.get(sec,ZERO)+cost;sv[r['sid']]=sv.get(r['sid'],ZERO)+cost
   details.append(dict(sid=r['sid'],kind=r['kind'],q=q,cost=str(cost),reason=x['reason'] if x['reason']!='PASS' else 'PASS' if q else 'REFERENCE_CAP'))
  return total,details
 def plan_transfers(self,d,pending):
  self.reference=self.classify_reference(d);reqs,detail=self.plan_requests(d,[a['plan'] for a in self.active.values() if a.get('plan')]+pending);sv={s:self.qvalue(a,d,'raw_close') for s,a in self.active.items()};nav=self.reference['NAV'];cash=self.cash;nxt=pd.Timestamp(self.reference['next_day'])
  for s,a in self.active.items():
   q=sum(l['q'] for l in a['lots'] if (a['exit'] or l.get('exit')) and nxt>pd.Timestamp(l['bought']))
   if q:
    p=dec(self.d.z(s,d)['raw_close'])*(1-SLIP);cash+=q*p-self.d.fee(s,nxt,q,p,'sell')
  desired,receivers=self.demand(reqs,d,'raw_close',nav,sv);gap=max(ZERO,desired+self.reference['reserve']-cash) if desired>0 else ZERO;initial=gap;sectors=dict(self.reference['sector_value']);receiver_sectors={self.d.sid_sector[r['sid']] for r in reqs if r['M']==1 and r.get('_ref_q',0)>0};pool=[r for r in self.reference['rows'] if r['mobile_qty']>0 and r['sector51'] not in receiver_sectors];self.transfer_plan=[]
  def floor(sec):return max(self.reference['fixed'][sec],self.reference['T'][sec])
  while pool and gap>0:
   def key(r):
    tier=0 if r['donor_reason']=='UNCONFIRMED_NON_MAINLINE_SEED' else 1 if r['donor_reason']=='WEAK_SECTOR_ADD_LAYER' else 2
    return (tier,r['stock_state']!=0 if tier==0 else False,r['E'] if tier==0 else -max(ZERO,sectors[r['sector51']]-floor(r['sector51'])) if tier==2 else ZERO,r['E'] if tier==2 else ZERO,r['bought'],r['sid'],r['lot_id'])
   r=min(pool,key=key);pool.remove(r);sec=r['sector51'];s=r['sid'];a=self.active[s];qr=self.d.getmeta(s,nxt)[0];surplus=max(ZERO,sectors[sec]-floor(sec));maxq=qr.sell_floor(min(r['mobile_qty'],int(surplus/r['raw_mark'])),self.quantity(a));p=r['raw_mark']*(1-SLIP)
   if r['donor_reason']=='MAINLINE_REFERENCE_SURPLUS_ADD' and self.reference['status']!='PASS':continue
   if r['kind']=='SEED':q=maxq if maxq==r['qty'] else 0
   else:q=self.sell_quantity(s,nxt,p,gap,maxq,self.quantity(a))
   if not q:continue
   proceeds=q*p-self.d.fee(s,nxt,q,p,'sell');rank=len(self.transfer_plan)+1;plan=dict(signal_day=day(d),sid=s,sector51=sec,round_id=a['id'],lot_id=r['lot_id'],max_q=q,reason=r['donor_reason'],rank=rank,close_estimated_net=str(proceeds),initial_gap=str(initial),gap_before=str(gap),close_sector_floor=str(floor(sec)),frozen_lot_qty=r['frozen_qty']);self.transfer_plan.append(plan);sectors[sec]-=q*r['raw_mark'];gap=max(ZERO,gap-proceeds);self.transfers.append(dict(day=day(d),phase='CLOSE',event='DONOR_PLANNED',**plan,remaining_gap=str(gap)))
  self.transfers.append(dict(day=day(d),phase='CLOSE',event='DEMAND_PLAN',M_desired_cost=str(desired),cash_after_known_protection=str(cash),reserve=str(self.reference['reserve']),initial_gap=str(initial),remaining_gap=str(gap),receivers=receivers,planned_donors=len(self.transfer_plan)))
 def execute_transfers(self,d,reqs,nav,sv):
  desired,detail=self.demand(reqs,d,'raw_open',nav,sv);gap=max(ZERO,desired+D('.1')*nav-self.cash) if desired>0 else ZERO;initial=gap;proceeds=ZERO
  for r in self.transfer_plan:
   s=r['sid'];sec=r['sector51'];a=self.active.get(s);l=next((x for x in a['lots'] if x['id']==r['lot_id']),None) if a else None;q=0;why='PASS'
   if gap<=0:why='RECEIVER_GAP_ZERO'
   elif a is None or l is None:why='DONOR_ALREADY_EXITED'
   elif a['exit'] or any(x.get('exit') for x in a['lots']):why='PROTECTION_OR_LOCKED_EXIT'
   elif d<=pd.Timestamp(l['bought']):why='T1_LOCKED'
   else:
    mark=dec(self.d.z(s,d)['raw_open']);p=mark*(1-SLIP);qr=self.d.getmeta(s,d)[0];fixed_open=sum((min(x['q'],self.reference.get('frozen_lot_qty',{}).get(x['id'],0))*dec(self.d.z(ss,d)['raw_open']) for ss,aa in self.active.items() if self.d.sid_sector[ss]==sec for x in aa['lots']),ZERO);floor=max(dec(r['close_sector_floor']),fixed_open);surplus=max(ZERO,self.sector_values(sv)[sec]-floor);maxq=qr.sell_floor(min(r['max_q'],max(0,l['q']-r['frozen_lot_qty']),int(surplus/mark)),self.quantity(a))
    if l['kind']=='SEED':q=maxq if maxq==l['q'] else 0
    else:q=self.sell_quantity(s,d,p,gap,maxq,self.quantity(a))
    if not q:why='NO_LEGAL_SURPLUS_SELL_Q'
   if q:
    before=self.cash;oldq=self.quantity(a);self.order(a,d,'SELL_ALL' if q==oldq else 'SELL_LAYERS',q,p,r['reason'],signal_day=r['signal_day'],lots=[l['id']],lot_quantities={l['id']:q},transfer_rank=r['rank']);net=self.cash-before;proceeds+=net;gap=max(ZERO,gap-net);l['q']-=q;a['lots']=[x for x in a['lots'] if x['q']];sv[s]-=q*mark
    if not self.quantity(a):a['exit_day']=day(d);self.active.pop(s)
   self.transfers.append(dict(day=day(d),phase='OPEN',event='DONOR_EXECUTION',**r,decision=why,executed_q=q,remaining_gap=str(gap)))
  self.transfers.append(dict(day=day(d),phase='OPEN',event='TRANSFER_CASH',M_desired_cost=str(desired),initial_gap=str(initial),net_cash_released=str(proceeds),remaining_gap=str(gap),receivers=detail));self.transfer_plan=[];return proceeds
 def run(self,checkpoint=True):
  return run_loop(self,checkpoint)
 def export(self,path):
  super().export(path)
  for name,data in [('REFERENCE_DAILY',self.reference_log),('CAPITAL_LOTS',self.capital_lots),('REFERENCE_REQUESTS',self.reference_requests)]:save(path/(name+'.json'),data);pd.DataFrame(data).to_csv(path/(name+'.csv'),index=False)
  save(path/'REFERENCE_AT_END.json',self.reference);save(path/'OUTPUT_HASHES.json',{p.name:sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})

def run_loop(e,checkpoint=True,prefix='checkpoint'):
 pending=[];keys=['cash','receivable','active','archive','seq','claims','snapshots','tickets','transfer_plan','quote_gaps'];logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','ticket_log','confirmations','transfers','request_details','floor_risk','open_exposure','availability']
 if isinstance(e,Engine):keys+=['reference','_ref_spent'];logs+=['reference_log','capital_lots','reference_requests']
 for d in e.d.days:
  prev=e.d.cal[e.d.cal.get_loc(d)-1];snap=copy.deepcopy({k:getattr(e,k) for k in keys});p0=copy.deepcopy(pending);lengths={k:len(getattr(e,k)) for k in logs}
  try:
   e.economic_preflight(d,pending);e.accrue(d);e.exit_open(d);e.alloc_open(d,pending);pending=e.close(d,prev)
   if checkpoint and day(d) in ['2024-09-23','2024-09-27','2024-09-30','2024-10-08']:
    e.pending=pending;e.export(O/(prefix+'_'+day(d).replace('-','')));print('CHECKPOINT '+json.dumps(e.ledger[-1]),flush=True)
  except Blocked as ex:
   e.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=e.orders[lengths['orders']:])
   for k,v in snap.items():setattr(e,k,v)
   for k,n in lengths.items():del getattr(e,k)[n:]
   pending=p0;e._preflight_excluded=set();e.all_blockers=e.scan_restored_targets(d,pending);e.blockers.append(str(ex));print('ATOMIC_BLOCK '+str(ex),flush=True);break
  print('DAY '+day(d)+' orders='+str(len(e.orders))+' tickets='+str(len(e.live_tickets()))+' NAV='+e.ledger[-1]['NAV'],flush=True)
 e.pending=pending;return e

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['replay','run'],required=True);args=ap.parse_args()
 if args.mode=='replay':
  data=m2.Data('2024-10-08');data.days=data.days[data.days<=pd.Timestamp('2024-09-30')];e=run_loop(m2.Engine(data),False);e.export(O/'m2_replay_20240930');checks={}
  for name in m2.BASE_FAMILIES+['AVAILABILITY_EVENTS','QUOTE_GAPS']:
   aa=read(O/'m2_replay_20240930'/(name+'.json'));bb=read(V2/'checkpoint_20240930'/(name+'.json'));assert aa==bb,('M2_REPLAY_MISMATCH',name);checks[name]=len(aa)
  save(O/'M2_MIGRATION_REPLAY_QA.json',dict(result='PASS',days=19,exact_records=checks,engine_sha256=sha(O/'engine.py')));print('M2_REPLAY_PASS',flush=True)
 else:
  assert read(O/'CONTRACT_APPROVAL.json')['approved'];assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert read(O/'M2_MIGRATION_REPLAY_QA.json')['result']=='PASS';assert not (O/'RUN_STARTED.json').exists()
  data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md'),combined_hypothesis=True));save(O/'RUN_STARTED.json',dict(time=str(pd.Timestamp.now(tz='UTC')),end='2024-10-08'));e=Engine(data).run();e.export(O/'once_20241008');save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None));print(json.dumps(read(O/'RUN_STATUS.json')))
