"""Single pre-outcome M hypothesis. Original v9 facts and accounting, research only."""
from pathlib import Path
import sys, importlib.util, json, copy, hashlib, argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent; ROOT=O.parent; BASE=ROOT/'joint51_candidate_v9_facts'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
b=module('frozen_v9',BASE/'engine.py')
rules=module('allocation_m_rules',ROOT/'allocation_ablation_v1/allocation_rules.py')
D=b.D;ZERO=b.ZERO;INITIAL=b.INITIAL;SLIP=b.SLIP;pd=b.pd;np=b.np;dec=b.dec;day=b.day;finite=b.finite;truth=b.truth;false=b.false;valid=b.valid;lineage=b.lineage;sha=b.sha;save=b.save;read=b.read;Blocked=b.Blocked;sha_text=b.sha_text;trigger=b.trigger

def tri_and(*a):return 0 if 0 in a else (-1 if -1 in a else 1)
def tri_or(*a):return 1 if 1 in a else (-1 if -1 in a else 0)
def pos(x):return -1 if not finite(x) else int(x>0)
def streak(x):
 out=[];n=0
 for v in x:n=n+1 if v else 0;out.append(n)
 return out

def compute_evidence(data):
 cal=data.cal[(data.cal>=pd.Timestamp('2023-11-01'))&(data.cal<=data.end)];ids=data.ids
 px=pd.DataFrame(np.nan,index=cal,columns=ids);vf=pd.DataFrame(False,index=cal,columns=ids);chg=vf.copy()
 for s in ids:
  z=data.raw[s].reindex(cal);cols=['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor'];vv=z[cols].to_numpy(float)
  basic=z.observed_bar.eq(True)&z.price_eligible.eq(True)&z.volume_eligible.eq(True)&z.source_invalid.eq(False)&z.synthetic_event_bar.eq(False)
  lin=z[['source_kind','source_path','segment_id']].astype('string');ok=basic.to_numpy(bool)&np.isfinite(vv).all(axis=1)&(vv>0).all(axis=1)&lin.notna().all(axis=1).to_numpy()&lin.ne('').all(axis=1).to_numpy()
  p=z.raw_close*z.adjustment_factor;ok &= np.isclose(p.to_numpy(float),z.close.to_numpy(float),rtol=1e-10,atol=1e-10,equal_nan=False)
  vf[s]=ok;px[s]=p.where(ok);chg[s]=lin.ne(lin.shift()).fillna(True).any(axis=1)
 rets={};known={}
 for h in [5,10,20]:
  known[h]=vf.astype(int).rolling(h+1,min_periods=h+1).sum().eq(h+1)&chg.astype(int).rolling(h,min_periods=h).sum().eq(0)
  rets[h]=(px/px.shift(h)-1).where(known[h])
 hi=px.shift(1).rolling(20,min_periods=20).max();br=(px>hi).where(known[20]);market={h:rets[h].median(axis=1) for h in rets}
 records=[]
 for sector in data.sector_ids:
  ss=[s for s in ids if data.sid_sector[s]==sector];sf=data.sectors[sector].reindex(cal);z=pd.DataFrame(index=cal);N=len(ss)
  for h in rets:
   z[f'return{h}_median']=rets[h][ss].median(axis=1);z[f'rs{h}']=100*(z[f'return{h}_median']-market[h]);z[f'return{h}_K']=known[h][ss].sum(axis=1);z[f'market{h}_K']=known[h].sum(axis=1)
  z['breakout20_count']=br[ss].sum(axis=1,min_count=1);z['breakout20_K']=known[20][ss].sum(axis=1);z['N']=N;z['n']=sf.n;z['K']=sf.K;z['state']=sf.state;z['diff']=sf['diff'];z['U']=sf.U;z['prev_U']=sf.U.shift();z['prev_n']=sf.n.shift();z['prev_rs5']=z.rs5.shift()
  states=[];qv=[];sv=[];fv=[]
  for _,r in z.iterrows():
   half=lambda n,u: -1 if not finite(n) or not finite(u) else (1 if 2*n>=N else 0 if 2*(n+u)<N else -1)
   Q=tri_and(int(r.state) if r.state in [-1,0,1] else -1,half(r.n,r.U),half(r.prev_n,r.prev_U))
   S=tri_and(Q,pos(r.rs10),pos(r.rs20),pos(r.return10_median))
   improve=-1 if not finite(r.rs5) or not finite(r.prev_rs5) else int(r.rs5>r.prev_rs5)
   breakout=-1 if not finite(r.breakout20_count) else (1 if 2*r.breakout20_count>=N else 0 if 2*(r.breakout20_count+N-r.breakout20_K)<N else -1)
   F=tri_and(Q,pos(r.rs5),improve,pos(r.return5_median),breakout)
   m=tri_or(S,F)
   if m==1 and not finite(r.rs5):m=-1
   qv.append(Q);sv.append(S);fv.append(F);states.append(m)
  z['Q']=qv;z['S']=sv;z['F']=fv;z['M']=states;z['M_streak']=streak(z.M.eq(1));z['E']=z.rs5.clip(lower=0)*z.n/N
  neg=z.rs5.lt(0)&z.rs10.lt(0);z['W']=(neg&neg.shift(fill_value=False))|(sf.state.eq(0)&sf.state.shift().eq(0));z['sector51']=sector;z['day']=z.index
  records.extend(z[z.index>=pd.Timestamp('2024-01-02')].to_dict('records'))
 out=pd.DataFrame(records).sort_values(['day','sector51']);return out

class Data(b.Data):
 def __init__(self,end='2024-10-31'):
  super().__init__(end)
  supplement=ROOT/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_603083_V1.json'
  assert sha(supplement)=='30bee171a5055cfabd8785cad3d62615ea2680aceab5eb0893124e54751cccb8'
  self.hashes[str(supplement)]=sha(supplement);events=read(supplement)
  def checked(p,h):
   assert sha(Path(p))==h,('SUPPLEMENT_INPUT_DRIFT',str(p));self.hashes[str(p)]=h
  for e in events:
   s=e['sid'];dt=pd.Timestamp(e['ex_date'])
   if s not in self.ids or not pd.Timestamp('2024-09-02')<=dt<=self.end:continue
   assert (s,dt) not in self.events,('DUPLICATE_EVENT',s,dt)
   for p,h in e.get('evidence_hashes',{}).items():checked(p,h)
   for stem in ['source_fact','local_action','signal']:
    if e.get(stem+'_path'):checked(e[stem+'_path'],e[stem+'_sha256'])
   notice=e.get('notice')
   if notice and notice.get('pdf_path'):checked(notice['pdf_path'],notice['pdf_sha256'])
   a=self.actions[s];terms=[x for x in a['events'] if x['effective_date']==e['ex_date']];assert len(terms)==1
   term=terms[0];assert dec(term['split_ratio'])==1 and dec(term['cash_per_old_share'])==dec(e['d_source'])
   z=self.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt];fo=dec(prev.adjustment_factor);fn=dec(cur.adjustment_factor);ds=dec(e['d_source']);pc=dec(prev.raw_close)
   assert lineage(prev)==lineage(cur) and abs(fo*pc/(pc-ds)/fn-1)<D('1e-11')
   assert pd.Timestamp(e['record_date'])==prev.name and pd.Timestamp(e['record_date'])<dt<=pd.Timestamp(e['pay_date'])
   if 'factor_old' in e:assert abs(fo/dec(e['factor_old'])-1)<D('1e-11') and abs(fn/dec(e['factor_new'])-1)<D('1e-11')
   assert dec(e['d_cash'])>=0
   e=dict(e,factor_old=str(fo),factor_new=str(fn));self.events[(s,dt)]=e;self.admission.append(dict(sid=s,sector51=self.sid_sector[s],ex_date=day(dt),event_id=e['economic_event_id_candidate'],status='BOUNDED_RESEARCH_NET80_ONLY',factor_bridge_verified=True,not_PIT=True,not_production_admission=True))
  self.evidence=compute_evidence(self);self.main={sec:g.set_index('day') for sec,g in self.evidence.groupby('sector51')}
  for p in [O/'engine.py',O/'FROZEN_CONTRACT_DRAFT.md',ROOT/'allocation_ablation_v1/allocation_rules.py',ROOT/'sector_strength_evidence_v1/build_strength.py']:self.hashes[str(p)]=sha(p)
  ref=ROOT/'sector_strength_evidence_v1/extension_1022/ALL50_DAILY_EVIDENCE.csv';r=pd.read_csv(ref,parse_dates=['day']).set_index(['day','sector51']);ours=self.evidence.set_index(['day','sector51']);ix=r.index.intersection(ours.index)
  for c in ['rs5','rs10','rs20']:
   assert np.allclose(ours.loc[ix,c],r.loc[ix,c+'_median_pp'],rtol=1e-10,atol=1e-9,equal_nan=True),(c,'STRENGTH_REPLAY')
  self.hashes[str(ref)]=sha(ref)
 def m(self,s,d):return self.main[self.sid_sector[s]].loc[d]

class Engine(b.Engine):
 def __init__(self,data):
  super().__init__(data);self.tickets={};self.ticket_log=[];self.confirmations=[];self.transfers=[];self.transfer_plan=[];self.request_details=[];self.floor_risk=[];self.open_exposure=[];self.last_targets=[];self.all_blockers=[]
 def ticket_event(self,t,d,event,**kw):self.ticket_log.append(dict(day=day(d),sid=t['sid'],ticket_id=t['ticket_id'],original_signal_day=t['signal_day'],event=event,status=t['status'],original_nav=str(t['nav0']),current_factor=str(t['current_factor']),ifloor=str(t['ifloor']),**kw))
 def live_tickets(self):return {s:t for s,t in self.tickets.items() if t['status'] not in ('CANCELLED','CONSUMED')}
 def scan_targets(self,d,pending):
  targets=set(self.active)|{r['sid'] for r in pending}|set(self.live_tickets());rows=[]
  for s in sorted(targets):
   a=self.active.get(s);t=self.live_tickets().get(s);r=next((x for x in pending if x['sid']==s),None);origin=a['origin'] if a else t['origin'] if t else r['origin'];factor=a['factor'] if a else t['current_factor'] if t else r['factor'];z=self.d.z(s,d);ev=self.d.events.get((s,d));act=self.d.action(s,d);issues=[]
   for c in ['raw_open','raw_close','adjustment_factor']:
    if not finite(z.get(c)) or z[c]<=0:issues.append(c.upper()+'_MISSING_OR_INVALID')
   if z is not None and len(z) and lineage(z)!=origin:issues.append('HELD_SOURCE_CHANGE' if a else 'PENDING_SOURCE_CHANGE_CANCEL')
   if act and ev is None:issues.append('UNADMITTED_EQUITY_EVENT')
   if finite(z.get('adjustment_factor')) and factor and ev is None and abs(dec(z['adjustment_factor'])/factor-1)>D('1e-11'):issues.append('UNADMITTED_FACTOR_CHANGE')
   if ev and (abs(factor/dec(ev['factor_old'])-1)>D('1e-11') or not finite(z.get('adjustment_factor')) or abs(dec(z['adjustment_factor'])/dec(ev['factor_new'])-1)>D('1e-11')):issues.append('FACTOR_BRIDGE_MISMATCH')
   rows.append(dict(day=day(d),sid=s,held_qty=self.quantity(a) if a else 0,pending=bool(r),retained_status=t['status'] if t else None,issues=issues))
  return rows
 def economic_preflight(self,d,pending):
  self.last_targets=self.scan_targets(d,pending)
  for s,t in list(self.live_tickets().items()):
   z=self.d.z(s,d)
   if len(z) and lineage(z)!=t['origin']:
    rules.cancel(t,'RETRY_SOURCE_CHANGED');self.ticket_event(t,d,'CANCEL_SOURCE_CHANGED')
  pending[:]=[r for r in pending if not r.get('ticket_id') or r['sid'] in self.live_tickets()]
  all_pending=list(pending)
  planned={r['sid'] for r in all_pending}
  all_pending.extend(dict(sid=s,origin=t['origin'],factor=t['current_factor']) for s,t in self.live_tickets().items() if s not in planned and s not in self.active)
  super().economic_preflight(d,all_pending)
  for s,t in self.live_tickets().items():
   z=self.d.z(s,d)
   if not finite(z.get('adjustment_factor')) or z['adjustment_factor']<=0:raise Blocked(f'{day(d)} {s} RETAINED_FACTOR_MISSING')
   ev=self.d.events.get((s,d));ev=dict(reviewed=True,factor_old=dec(ev['factor_old']),factor_new=dec(ev['factor_new'])) if ev else None
   try:rules.retained_ticket_preflight(t,date=day(d),origin=lineage(z),factor=dec(z['adjustment_factor']),action_present=bool(self.d.action(s,d)),admitted_event=ev)
   except rules.MissingBridge as ex:raise Blocked(f'{day(d)} {s} {ex}')
   self.ticket_event(t,d,'DAILY_BRIDGE_CHECK',record_qty=0)
 def info_open(self,d):
  for a in self.archive.values():
   proof=a.pop('information_pending',None)
   if not proof:continue
   s=a['sid'];reason='PASS'
   if s not in self.active or a['exit'] or any(l.get('exit') for l in a['lots']):reason='EXIT_OR_NO_POSITION'
   else:
    z=self.d.z(s,d);cp=a.get('cp');op=dec(z['raw_open']);net=self.net(a,d,'raw_open')
    if cp is None or cp['id']!=proof['cp_id'] or not self.cpvalid(a,cp,z,'raw_open'):reason='CP_INVALID_OR_REPLACED'
    elif op*a['factor']<=max(a['ifloor'],cp['floor']):reason='OPEN_BELOW_PROTECTION'
    elif net<=0:reason='OPEN_NET_NOT_POSITIVE'
   if reason=='PASS':a['confirmed_history']=True;a.setdefault('confirmed_day',day(d))
   self.confirmations.append(dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'],proof_id=proof['proof_id'],cp_id=proof['cp_id'],decision='INFORMATION_CONFIRMED' if reason=='PASS' else 'PROVISIONAL_WITHDRAWN',reason=reason,confirmed_history=a.get('confirmed_history',False),actual_add_count=a['add_count'],capacity_or_funding_required=False))
 def info_close(self,a,d,cp,net):
  proof=dict(cp_id=cp['id'],close_day=day(d),close_net=str(net),proof_id=b.sha_text([a['id'],day(d),cp['id']]))
  a['information_pending']=proof;self.confirmations.append(dict(day=day(d),phase='CLOSE',sid=a['sid'],round_id=a['id'],**proof,decision='INFORMATION_CLOSE_PASS',confirmed_history=a.get('confirmed_history',False),actual_add_count=a['add_count'],capacity_or_funding_required=False))
 def request_key_groups(self,reqs):
  groups={};other=[]
  for r in reqs:
   if r['M']==1:groups.setdefault(self.d.sid_sector[r['sid']],[]).append(r)
   else:other.append(r)
  def datekey(r):return (r.get('cp_date',r['signal_day']),r['sid'])
  def groupkey(item):
   sec,rs=item;v=rs[0];return (-v['E'],-v['M_streak'],min(datekey(r) for r in rs),sec)
  out=[]
  for sec,rs in sorted(groups.items(),key=groupkey):out.extend(sorted(rs,key=lambda r:(r['kind']!='ADD',*datekey(r))))
  out.extend(sorted(other,key=lambda r:(r['signal_day'],r['sid'])))
  return out
 def decorate(self,r,d):
  m=self.d.m(r['sid'],d);r.update(plan_day=day(d),M=int(m.M),E=dec(m.E) if finite(m.E) else ZERO,M_streak=int(m.M_streak));return r
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
    q=self.d.size(s,d,p,min(caps.values()),min(r['planned_q'],r['capacity'],self.quantity(a)))
    if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
  return dict(q=q if reason=='PASS' else 0,reason=reason,p=p,net=net,caps=caps,structural=reason=='PASS' or reason.startswith('MIN_LOT_CAPITAL_REJECT'))
 def demand(self,reqs,d,field,nav,sv):
  total=ZERO;detail=[];sv=dict(sv)
  for r in reqs:
   if r['M']!=1:continue
   x=self.noncash(r,d,field,nav,sv);q=x['q'];cost=q*x['p']+self.d.fee(r['sid'],d,q,x['p'],'buy') if q else ZERO;total+=cost;sv[r['sid']]=sv.get(r['sid'],ZERO)+cost;detail.append(dict(sid=r['sid'],kind=r['kind'],q=q,cost=str(cost),reason=x['reason']))
  return total,detail
 def sell_quantity(self,s,d,p,gap,maxq,held):
  qr=self.d.getmeta(s,d)[0];maxq=qr.sell_floor(maxq,held)
  if maxq<=0:return 0
  q=qr.sell_floor(min(maxq,max(1,int(gap/p))),held)
  if q==0:q=qr.sell_floor(min(maxq,qr.sell_step),held)
  while q<maxq and q*p-self.d.fee(s,d,q,p,'sell')<gap:
   nxt=qr.sell_floor(min(maxq,q+qr.sell_step),held)
   if nxt<=q:nxt=maxq
   q=nxt
  return q
 def plan_transfers(self,d,pending):
  reqs=self.request_key_groups([a['plan'] for a in self.active.values() if a.get('plan')]+pending);nav=self.nav(d,'raw_close');sv={s:self.qvalue(a,d,'raw_close') for s,a in self.active.items()};cash=self.cash
  # Protection orders already known at CLOSE; use only next-day-T1-eligible lots.
  nxt=self.d.cal[self.d.cal.get_loc(d)+1] if self.d.cal.get_loc(d)+1<len(self.d.cal) else d+pd.Timedelta(days=1)
  for s,a in self.active.items():
   q=sum(l['q'] for l in a['lots'] if (a['exit'] or l.get('exit')) and nxt>pd.Timestamp(l['bought']))
   if q:
    p=dec(self.d.z(s,d)['raw_close'])*(1-SLIP);cash+=q*p-self.d.fee(s,nxt,q,p,'sell');sv[s]-=q*dec(self.d.z(s,d)['raw_close'])
  desired,detail=self.demand(reqs,d,'raw_close',nav,sv);gap=max(ZERO,desired+D('.10')*nav-cash) if desired>0 else ZERO;initial_gap=gap;donors=[]
  for s,a in self.active.items():
   m=self.d.m(s,d);sec=self.d.sectors[self.d.sid_sector[s]].loc[d];st=int(self.d.stock.at[d,s])
   if a['exit'] or any(l.get('exit') for l in a['lots']) or m.M==1:continue
   # Revised first tier is pending explicit approval of draft 2.
   seed_ok=not a.get('confirmed_history',False) and not a.get('information_pending') and a['add_count']==0 and m.M==0 and sec.state in [0,1] and st in [0,1] and finite(m.E)
   for l in a['lots']:
    if nxt<=pd.Timestamp(l['bought']):continue
    if seed_ok and l['kind']=='SEED':donors.append(((0,st!=0,float(m.E),a['seed_day'],s,l['id']),a,l,'UNCONFIRMED_NON_MAINLINE_SEED'))
    elif bool(m.W) and l['kind']=='ADD':donors.append(((1,False,0,l['bought'],s,l['id']),a,l,'WEAK_SECTOR_ADD_LAYER'))
  self.transfer_plan=[]
  for rank,(_,a,l,why) in enumerate(sorted(donors,key=lambda x:x[0])):
   if gap<=0:break
   s=a['sid'];p=dec(self.d.z(s,d)['raw_close'])*(1-SLIP);q=l['q'] if l['kind']=='SEED' else self.sell_quantity(s,nxt,p,gap,l['q'],self.quantity(a))
   if not q:continue
   proceeds=q*p-self.d.fee(s,nxt,q,p,'sell');r=dict(signal_day=day(d),sid=s,round_id=a['id'],lot_id=l['id'],max_q=q,reason=why,rank=rank+1,close_estimated_net=str(proceeds),initial_gap=str(initial_gap),gap_before=str(gap));self.transfer_plan.append(r);gap=max(ZERO,gap-proceeds)
   self.transfers.append(dict(day=day(d),phase='CLOSE',event='DONOR_PLANNED',**r,remaining_gap=str(gap)))
  self.transfers.append(dict(day=day(d),phase='CLOSE',event='DEMAND_PLAN',M_desired_cost=str(desired),cash_after_known_protection=str(cash),reserve=str(D('.10')*nav),initial_gap=str(initial_gap),remaining_gap=str(gap),receivers=detail,planned_donors=len(self.transfer_plan)))
 def execute_transfers(self,d,reqs,nav,sv):
  desired,detail=self.demand(reqs,d,'raw_open',nav,sv);gap=max(ZERO,desired+D('.10')*nav-self.cash) if desired>0 else ZERO;initial=gap;proceeds=ZERO
  for r in self.transfer_plan:
   a=self.active.get(r['sid']);l=next((l for l in a['lots'] if l['id']==r['lot_id']),None) if a else None;why='PASS';q=0
   if gap<=0:why='RECEIVER_GAP_ZERO'
   elif a is None or l is None:why='DONOR_ALREADY_EXITED'
   elif a['exit'] or l.get('exit'):why='PROTECTION_OR_LOCKED_EXIT'
   elif d<=pd.Timestamp(l['bought']):why='T1_LOCKED'
   else:
    p=dec(self.d.z(a['sid'],d)['raw_open'])*(1-SLIP);maxq=min(r['max_q'],l['q']);q=maxq if l['kind']=='SEED' else self.sell_quantity(a['sid'],d,p,gap,maxq,self.quantity(a))
    if not q:why='NO_LEGAL_SELL_Q'
   if q:
    before=self.cash;oldq=self.quantity(a);self.order(a,d,'SELL_ALL' if q==oldq else 'SELL_LAYERS',q,p,r['reason'],signal_day=r['signal_day'],lots=[l['id']],lot_quantities={l['id']:q},transfer_rank=r['rank']);net=self.cash-before;proceeds+=net;gap=max(ZERO,gap-net);l['q']-=q;a['lots']=[v for v in a['lots'] if v['q']];sv[a['sid']]-=q*dec(self.d.z(a['sid'],d)['raw_open'])
    if not self.quantity(a):a['exit_day']=day(d);self.active.pop(a['sid'])
   self.transfers.append(dict(day=day(d),phase='OPEN',event='DONOR_EXECUTION',**r,decision=why,executed_q=q,remaining_gap=str(gap)))
  self.transfers.append(dict(day=day(d),phase='OPEN',event='TRANSFER_CASH',M_desired_cost=str(desired),initial_gap=str(initial),net_cash_released=str(proceeds),remaining_gap=str(gap),receivers=detail))
  self.transfer_plan=[];return proceeds
 def alloc_open(self,d,pending):
  self.info_open(d);nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()};reqs=[]
  for a in self.active.values():
   if a.get('plan'):reqs.append(a['plan'])
   a['plan']=None
  reqs=self.request_key_groups(reqs+pending);released=self.execute_transfers(d,reqs,nav,sv);cash=self.cash;reserved=[];main_filled=ZERO
  for rank,r in enumerate(reqs):
   s=r['sid'];x=self.noncash(r,d,'raw_open',nav,sv);q=x['q'];p=x['p'];caps=dict(x['caps'],cash_reserve=max(ZERO,cash-D('.10')*nav));reason=x['reason'];a=self.active.get(s);qr=self.d.getmeta(s,d)[0]
   rawq=qr.buy_minimum if r['kind']=='SEED' else q;rawcost=rawq*p+self.d.fee(s,d,rawq,p,'buy') if rawq else ZERO
   if reason=='PASS':
    if r['kind']=='SEED':
     if rawcost>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
    else:
     q=self.d.size(s,d,p,min(caps.values()),min(q,r['planned_q'],self.quantity(a)))
     if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
   violated=sorted(k for k,v in caps.items() if rawcost>v)
   row=dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],plan_day=r['plan_day'],decision=reason,allocation_rank=rank+1,M=r['M'],E=str(r['E']),M_streak=r['M_streak'],cp_id=r.get('cp_id'),close_net=r.get('close_net'),open_net=str(x['net']) if x['net'] is not None else None,planned_q=r['planned_q'],executed_q=q if reason=='PASS' else 0,violated_caps=violated,**{k:str(v) for k,v in caps.items()});self.candidates.append(row);self.request_details.append(row)
   if r['kind']=='SEED':
    t=self.live_tickets().get(s)
    if t:
     rules.retry_open_outcome(t,filled=reason=='PASS',structural_pass=x['structural'],all_in_cost=rawcost,caps=caps);self.ticket_event(t,d,'OPEN_OUTCOME',decision=reason,violated_caps=violated)
    elif reason!='PASS':
     t=rules.ticket_from_seed(r,rawcost,caps,structural_pass=x['structural'])
     if t:
      t['current_factor']=dec(self.d.z(s,d)['adjustment_factor']);t['last_verified_day']=day(d);self.tickets[s]=t;self.ticket_event(t,d,'CAPITAL_REJECT_RETAINED',decision=reason,violated_caps=violated)
   if reason!='PASS':continue
   cost=q*p+self.d.fee(s,d,q,p,'buy');cash-=cost;sv[s]=sv.get(s,ZERO)+cost;reserved.append((r,q,p,x['net'],cost));main_filled+=cost if r['M']==1 else ZERO
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
     q=self.d.size(s,d,dec(z['raw_close'])*(1+SLIP),budget,min(int(cap),self.quantity(a)))
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

 def refresh_tickets(self,d):
  pending=[]
  for s,t in self.live_tickets().items():
   z=self.d.z(s,d);f=self.d.f(s,d);cap=self.d.cap[s].get(d,np.nan);qr=self.d.getmeta(s,d)[0];p=dec(z['raw_close'])*(1+SLIP) if finite(z.get('raw_close')) else None
   i=f.get('i_target');state=1 if truth(i) else 0 if false(i) else -1;cost=qr.buy_minimum*p+self.d.fee(s,d,qr.buy_minimum,p,'buy') if p else ZERO
   out=rules.refresh_retained_ticket(t,date=day(d),sector_state=int(self.d.sectors[self.d.sid_sector[s]].at[d,'state']),stock_state=int(self.d.stock.at[d,s]),i_state=state,current_ifloor=dec(f['i_floor']) if finite(f.get('i_floor')) else None,raw_close=dec(z['raw_close']) if finite(z.get('raw_close')) else None,capacity=int(cap) if finite(cap) else None,buy_minimum=qr.buy_minimum,all_in_min_cost=cost,source_valid=valid(z))
   self.ticket_event(t,d,'CLOSE_'+out,reason=t.get('reason'))
   if out=='PLAN':pending.append(self.decorate(t['plan'],d))
  return pending
 def attribute(self,d,nav):
  super().attribute(d,nav)
  for r in self.sector_daily[-len(self.d.sector_ids):]:
   m=self.d.main[r['sector51']].loc[d]
   r.update({c:(int(m[c]) if c in ['M','Q','S','F','M_streak'] else bool(m[c]) if c=='W' else float(m[c]) if finite(m[c]) else None) for c in ['M','Q','S','F','M_streak','W','E','rs5','rs10','rs20','return5_median','return10_median','breakout20_count']})
   aa=[a for s,a in self.active.items() if self.d.sid_sector[s]==r['sector51']];r['information_confirmed_stocks']=sum(a.get('confirmed_history',False) for a in aa);r['historically_added_stocks']=sum(a['add_count']>0 for a in aa)
 def run(self,checkpoint=True):
  pending=[]
  keys=['cash','receivable','active','archive','seq','claims','snapshots','tickets','transfer_plan'];logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','ticket_log','confirmations','transfers','request_details','floor_risk','open_exposure']
  for d in self.d.days:
   prev=self.d.cal[self.d.cal.get_loc(d)-1];snap=copy.deepcopy({k:getattr(self,k) for k in keys});p0=copy.deepcopy(pending);lengths={k:len(getattr(self,k)) for k in logs}
   try:
    self.economic_preflight(d,pending);self.accrue(d);self.exit_open(d);self.alloc_open(d,pending);pending=self.close(d,prev)
    if checkpoint and day(d) in ['2024-09-23','2024-09-27','2024-10-08','2024-10-25','2024-10-31']:
     self.pending=pending;self.export(O/('checkpoint_'+day(d).replace('-','')));print('CHECKPOINT '+json.dumps(self.ledger[-1]),flush=True)
   except Blocked as ex:
    self.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=self.orders[lengths['orders']:]);self.all_blockers=self.scan_targets(d,pending)
    for k,v in snap.items():setattr(self,k,v)
    for k,n in lengths.items():del getattr(self,k)[n:]
    pending=p0;self.blockers.append(str(ex));print('ATOMIC_BLOCK '+str(ex),flush=True);break
   print('DAY '+day(d)+' orders='+str(len(self.orders))+' tickets='+str(len(self.live_tickets()))+' NAV='+self.ledger[-1]['NAV'],flush=True)
  self.pending=pending;return self
 def export(self,path):
  super().export(path)
  for n,v in dict(RETRY_TICKETS=self.ticket_log,INFORMATION_CONFIRMATIONS=self.confirmations,TRANSFERS=self.transfers,FUNDING_REQUESTS=self.request_details,ADD_FLOOR_RISK=self.floor_risk,OPEN_SECTOR_EXPOSURE=self.open_exposure).items():save(path/(n+'.json'),v);pd.DataFrame(v).to_csv(path/(n+'.csv'),index=False)
  save(path/'TICKET_STATE.json',self.tickets);save(path/'TRANSFER_PLAN_AT_END.json',self.transfer_plan);save(path/'ALL_TARGETS_BLOCKER_SCAN.json',self.all_blockers)
  save(path/'OUTPUT_HASHES.json',{p.name:sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['synthetic','run'],required=True);args=ap.parse_args()
 if args.mode=='synthetic':
  from synthetic_m import run
  out=run();save(O/'SYNTHETIC_QA.json',out);print(json.dumps(out))
 else:
  assert read(O/'CONTRACT_APPROVAL.json')['approved'] is True
  assert read(O/'SYNTHETIC_QA.json')['result']=='PASS'
  assert not (O/'RUN_STARTED.json').exists(),'ONE_OUTCOME_RUN_ONLY_UNLESS_DOCUMENTED_FACT_OR_BUG_FIX'
  data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,contract_sha256=sha(O/'FROZEN_CONTRACT_DRAFT.md'),engine_sha256=sha(O/'engine.py'),no_outcome_run=True));data.evidence.to_csv(O/'ALL50_MAINLINE_EVIDENCE.csv',index=False)
  save(O/'RUN_STARTED.json',dict(time=str(pd.Timestamp.now(tz='UTC')),end='2024-10-31'));engine=Engine(data).run();engine.export(O/'full_20241031_once');save(O/'RUN_STATUS.json',dict(days=len(engine.ledger),orders=len(engine.orders),blockers=engine.blockers,last=engine.ledger[-1] if engine.ledger else None));print(json.dumps(read(O/'RUN_STATUS.json')))
