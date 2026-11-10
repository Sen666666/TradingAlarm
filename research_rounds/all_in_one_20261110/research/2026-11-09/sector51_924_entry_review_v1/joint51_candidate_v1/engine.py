"""Frozen multi-sector joint-account research candidate. No real orders."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json, hashlib, sys, math, argparse, copy
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent; P=O.parent
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
E=R/'m3_stock_birth_during_sector_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
sys.dont_write_bytecode=True;sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
ZERO=D(0); INITIAL=D(1200000); SLIP=D('.0005')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
def finite(x):
 try:return bool(np.isfinite(x))
 except (TypeError,ValueError):return False
def dec(x):return D(str(x))
def day(d):return str(pd.Timestamp(d).date())
def truth(x):return pd.notna(x) and x in (True,1)
def false(x):return pd.notna(x) and x in (False,0)
def lineage(z):return tuple(str(z.get(c)) for c in ('source_kind','source_path','segment_id'))
def valid(z):return all(truth(z.get(c)) for c in ('observed_bar','price_eligible','volume_eligible')) and false(z.get('source_invalid')) and false(z.get('synthetic_event_bar'))
def trigger(secprev,secnow,stockprev,stocknow):
 if secprev==0 and secnow==1 and stocknow==1:return 'A'
 if secprev==1 and secnow==1 and stockprev==0 and stocknow==1:return 'B'
 return None
def strengthened(n0,n1,N,diff):return 2*n0>=N and 2*n1>=N and diff>0
def sector_frame(known,right):
 N=len(known.columns);K=known.sum(axis=1);n=right.sum(axis=1);pair=known&known.shift(3,fill_value=False);J=pair.sum(axis=1);entered=(pair&right&~right.shift(3,fill_value=False)).sum(axis=1);left=(pair&~right&right.shift(3,fill_value=False)).sum(axis=1);diff=entered-left;u=N-K
 lo=n.ge(3)&((3*n>=N)&J.gt(0)&diff.gt(0)|(2*n>=N));hi=(n+u).ge(3)&((3*(n+u)>=N)&(diff.gt(0)|J.eq(0))|(2*(n+u)>=N))
 return pd.DataFrame(dict(N=N,K=K,n=n,U=u,paired_K=J,entered3=entered,left3=left,diff=diff,state=np.where(lo,1,np.where(~hi,0,-1)),strength=(2*n>=N)&(2*n.shift()>=N)&diff.gt(0)))
class Data:
 def __init__(self,end='2024-10-31'):
  self.end=pd.Timestamp(end);self.hashes={};self.admission=[]
  def hashed(p):
   p=Path(p)
   if str(p) not in self.hashes:self.hashes[str(p)]=sha(p)
   return p
  def checked(p,h):
   hashed(p);assert self.hashes[str(p)]==h,('INPUT_DRIFT',str(p))
  self.ro=pd.read_csv(hashed(O/'CLASSIFICATION_ALL1709.csv'),keep_default_na=False);assert len(self.ro)==1709 and self.ro.symbol.is_unique
  for p,h in read(hashed(O/'MAPPING_SOURCE_HASHES.json')).items():checked(p,h)
  self.excluded=self.ro[~self.ro.eligible.eq(True)].to_dict('records')
  selected=self.ro[self.ro.eligible.eq(True)];self.ids=sorted(selected.symbol);self.sid_sector=selected.set_index('symbol').sector51.to_dict();self.names=selected.set_index('symbol').name.to_dict();self.sector_ids=sorted(set(self.sid_sector.values()));assert len(self.sector_ids)<=50
  self.manifest={m['symbol']:m for m in read(hashed(U/'STOCK_MANIFEST.json'))};assert set(self.ro.symbol)==set(self.manifest)
  self.rules=read(hashed(B/'inputs-v2/market-rules.json'));self.proxies=read(hashed(B/'inputs-v2/economic-protocol.json'))['approved_proxy_ids']
  for p in [B/'code/market_rules.py',B/'code/sector_account.py',O/'FROZEN_CONTRACT.md',O/'engine.py',O/'SYNTHETIC_QA.json',O/'synthetic_joint.py']:hashed(p)
  Q=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
  k=pd.read_parquet(hashed(Q/'KNOWN3.parquet'))[self.ids].loc[:self.end];r=pd.read_parquet(hashed(Q/'RIGHT3.parquet'))[self.ids].loc[:self.end]
  ps=pd.read_parquet(hashed(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'),columns=['sid','day','state']);ps=ps[ps.sid.isin(self.ids)].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=self.ids)
  known=k&ps.ge(0);right=r&known;self.stock=pd.DataFrame(np.where(known,np.where(right,1,0),-1),index=k.index,columns=self.ids)
  self.sectors={}
  for sector in self.sector_ids:
   ids=[s for s in self.ids if self.sid_sector[s]==sector];self.sectors[sector]=sector_frame(known[ids],right[ids])
  self.cal=k.index;self.days=self.cal[self.cal>=pd.Timestamp('2024-09-02')];self.raw={};self.facts={};self.cp={};self.cap={};self.actions={};self.events={};self.meta={}
  for sid in self.ids:
   m=self.manifest[sid];ex={**m['source_sha256'],**m['output_sha256']};paths=[next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')),m['refs']['facts'],m['refs']['CP1']]
   for p in paths:checked(p,ex[p])
   z,f,c=[pd.read_parquet(p).loc[:self.end] for p in paths];self.raw[sid]=z;self.facts[sid]=f;self.cp[sid]=c
   v=z.raw_volume[z.raw_volume.gt(0)];self.cap[sid]=(v.rolling(20,min_periods=20).mean()*.01).reindex(z.index).ffill()
   ap=AS/'inputs-v1/actions'/(sid+'.json');a=read(hashed(ap));assert a['series_id']==sid and a['currency']=='CNY';self.actions[sid]=a
   for ce in a.get('coverage_evidence',[]):checked(ce['path'],ce['sha256'])
  ep=E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json';events=read(hashed(ep))
  au=E/'cash_dividend_2024_coverage_v1/FINAL_INDEPENDENT_AUDIT.json';audit=read(hashed(au));assert audit['result']=='PASS_COMPANY_FACT_EVIDENCE_ONLY';checked(ep,audit['audited_artifact_sha256'][ep.name])
  xp=P/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json';events+=read(hashed(xp))
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
  core=pd.read_csv(hashed(P/'CORE_DAILY_51CLASS_SIGNALS.csv'),parse_dates=['day']);core=core[core.day<=self.end]
  for sector,g in core.groupby('sector51'):
   g=g.set_index('day')
   for col in ['N','K','n','U','state']:assert np.array_equal(g[col].to_numpy(dtype=int),self.sectors[sector].loc[g.index,col].to_numpy(dtype=int)),('CORE_SECTOR_MISMATCH',sector,col)
 def z(self,s,d):return self.raw[s].loc[d] if d in self.raw[s].index else {}
 def f(self,s,d):return self.facts[s].loc[d] if d in self.facts[s].index else {}
 def c(self,s,d):return self.cp[s].loc[d] if d in self.cp[s].index else {}
 def getmeta(self,s,d):
  key=(s,day(d))
  if key not in self.meta:
   ident=market_identity_on(self.rules,s,key[1],self.proxies);v=version_on(self.rules['fee_versions'][ident['venue']],key[1],self.proxies)['schedule'];q=QuantityRule(**version_on(self.rules['quantity_versions'][s],key[1],self.proxies)['rule']);self.meta[key]=(q,FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),dec(self.rules['security_metadata'][s]['par_value']))
  return self.meta[key]
 def fee(self,s,d,q,p,side):
  if not q:return ZERO
  _,fs,pa=self.getmeta(s,d);return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=pa).values(),ZERO)
 def size(self,s,d,p,budget,cap):
  qr,_,_=self.getmeta(s,d);q=qr.buy_floor(max(0,min(int(budget/p),int(cap))))
  while q and q*p+self.fee(s,d,q,p,'buy')>budget:q=qr.buy_floor(q-1)
  return q
 def action(self,s,d):return [x for x in self.actions[s]['events'] if x['effective_date']==day(d)]
class Blocked(Exception):pass
class Engine:
 def __init__(self,data):
  self.d=data;self.cash=INITIAL;self.receivable=ZERO;self.active={};self.archive={};self.seq=defaultdict(int);self.orders=[];self.candidates=[];self.cp_log=[];self.profit=[];self.ledger=[];self.holdings=[];self.equity=[];self.claims={};self.snapshots={};self.blockers=[];self.sector_daily=[]
 def quantity(self,a):return sum(l['q'] for l in a['lots'])
 def qvalue(self,a,d,field):
  z=self.d.z(a['sid'],d)
  if not finite(z.get(field)) or z[field]<=0:raise Blocked(f"{day(d)} {a['sid']} {field.upper()}_MISSING")
  return self.quantity(a)*dec(z[field])
 def nav(self,d,field):return self.cash+self.receivable+sum((self.qvalue(a,d,field) for a in self.active.values()),ZERO)
 def net(self,a,d,field):
  s=a['sid'];p=dec(self.d.z(s,d)[field])*(1-SLIP);q=self.quantity(a)
  return a['cashflow']+a['dividend']+q*p-self.d.fee(s,d,q,p,'sell')
 def cpvalid(self,a,cp,z,field):return cp is not None and not cp['consumed'] and not cp['invalid'] and cp['origin']==lineage(z) and dec(z[field])*dec(z['adjustment_factor'])>cp['floor']
 def eventlog(self,a,d,phase,typ,cp=None,**kw):self.cp_log.append(dict(round_id=a['id'],sid=a['sid'],day=day(d),phase=phase,event=typ,cp_id=cp['id'] if cp else None,**kw))
 def invalidate_cp(self,a,d,phase,field):
  c=a.get('cp');z=self.d.z(a['sid'],d)
  if c is not None and not c['invalid'] and not self.cpvalid(a,c,z,field):c['invalid']=True;self.eventlog(a,d,phase,'INVALIDATED',c)
 def economic_preflight(self,d,pending):
  targets=set(self.active)|{r['sid'] for r in pending}
  for s in sorted(targets):
   z=self.d.z(s,d)
   if not finite(z.get('raw_open')) or z['raw_open']<=0:raise Blocked(f'{day(d)} {s} OPEN_MISSING')
   a=self.active.get(s);origin=a['origin'] if a else next(r['origin'] for r in pending if r['sid']==s)
   if lineage(z)!=origin:raise Blocked(f'{day(d)} {s} SOURCE_CHANGE')
   f0=a['factor'] if a else next(r['factor'] for r in pending if r['sid']==s);f1=dec(z['adjustment_factor'])
   if not f1.is_finite() or f1<=0:raise Blocked(f'{day(d)} {s} FACTOR_INVALID')
   ev=self.d.events.get((s,d));act=self.d.action(s,d)
   if act and ev is None:raise Blocked(f'{day(d)} {s} UNADMITTED_EQUITY_EVENT')
   if abs(f1/f0-1)>D('1e-11') and ev is None:raise Blocked(f'{day(d)} {s} UNADMITTED_FACTOR_CHANGE')
   if ev is not None:
    if abs(f0/dec(ev['factor_old'])-1)>D('1e-11') or abs(f1/dec(ev['factor_new'])-1)>D('1e-11'):raise Blocked(f'{day(d)} {s} FACTOR_BRIDGE_MISMATCH')
    if a:a['factor']=f1
    self.equity.append(dict(day=day(d),sid=s,event='FACTOR_BRIDGE',record_qty=self.snapshots.get((s,ev['record_date']),{'q':0})['q'],cash_delta='0',receivable_delta='0',event_id=ev.get('economic_event_id_candidate',f'{s}|{day(d)}')))
 def accrue(self,d):
  for (s,dt),ev in self.d.events.items():
   if dt!=d:continue
   key=(s,ev['record_date']);snap=self.snapshots.get(key,{'q':0,'round':None})
   if isinstance(snap,int):raise AssertionError('snapshot schema')
   if snap['q']:
    a=self.archive[snap['round']];amount=snap['q']*dec(ev['d_cash'])*D('.8');a['dividend']+=amount;self.receivable+=amount;self.claims[(s,dt)]={'amount':amount,'round':a['id'],'paid':False}
    self.equity.append(dict(day=day(d),sid=s,round_id=a['id'],event='ACCRUE_NET80',record_qty=snap['q'],cash_delta='0',receivable_delta=str(amount)))
 def register_pay(self,d):
  for (s,dt),ev in self.d.events.items():
   if ev['record_date']==day(d):
    a=self.active.get(s);self.snapshots[(s,ev['record_date'])]={'q':self.quantity(a) if a else 0,'round':a['id'] if a else None}
   c=self.claims.get((s,dt))
   if ev['pay_date']==day(d) and c and not c['paid']:
    self.cash+=c['amount'];self.receivable-=c['amount'];c['paid']=True;self.equity.append(dict(day=day(d),sid=s,round_id=c['round'],event='PAY_CLOSE_NET80',cash_delta=str(c['amount']),receivable_delta=str(-c['amount'])))
 def order(self,a,d,side,q,p,reason,**kw):
  s=a['sid'];f=self.d.fee(s,d,q,p,'buy' if side.startswith('BUY') else 'sell');cash=-(q*p+f) if side.startswith('BUY') else q*p-f
  self.cash+=cash;a['cashflow']+=cash;a['fees']+=f
  self.orders.append(dict(order_seq=len(self.orders)+1,round_id=a['id'],sid=s,name=self.d.names[s],day=day(d),signal_day=kw.pop('signal_day',None),side=side,qty=q,price=str(p),notional=str(q*p),fee=str(f),cash_delta=str(cash),reason=reason,**kw));return f
 def exit_open(self,d):
  for s,a in sorted(list(self.active.items())):
   z=self.d.z(s,d);px=dec(z['raw_open']);adj=px*a['factor'];self.invalidate_cp(a,d,'OPEN','raw_open')
   if adj<=a['ifloor']:a['exit']='I_OPEN_PROTECTION'
   exiting=[]
   for l in a['lots']:
    if a['exit'] or l.get('exit') or (l['kind']=='ADD' and adj<=l['floor']):
     if d>pd.Timestamp(l['bought']):exiting.append(l)
     else:l['exit']='T1_LOCKED_EXIT'
   if exiting:
    q=sum(l['q'] for l in exiting);reason=a['exit'] or 'CP_LAYER_EXIT';self.order(a,d,'SELL_ALL' if q==self.quantity(a) else 'SELL_LAYERS',q,px*(1-SLIP),reason,lots=[l['id'] for l in exiting]);a['lots']=[l for l in a['lots'] if l not in exiting];a['plan']=None
   if not self.quantity(a):a['exit_day']=day(d);self.active.pop(s)
 def alloc_open(self,d,pending):
  pre_nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()};sec=defaultdict(lambda:ZERO);cash=self.cash
  for s,v in sv.items():sec[self.d.sid_sector[s]]+=v
  requests=[]
  for s,a in self.active.items():
   r=a.get('plan');a['plan']=None
   if r:requests.append(r)
  requests.sort(key=lambda r:(r['cp_date'],r['sid']));requests+=sorted(pending,key=lambda r:(r['signal_day'],r['sid']))
  reserved=[]
  for rank,r in enumerate(requests):
   s=r['sid'];a=self.active.get(s);z=self.d.z(s,d);op=dec(z['raw_open']);p=op*(1+SLIP);fac=dec(z['adjustment_factor']);reason='PASS';net=None
   if r['kind']=='ADD':
    if a is None or a['exit'] or any(l.get('exit') for l in a['lots']):reason='LOCKED_EXIT'
    elif a.get('cp') is None or a['cp']['id']!=r['cp_id'] or not self.cpvalid(a,a['cp'],z,'raw_open'):reason='CP_INVALID_OR_REPLACED'
    else:
     net=self.net(a,d,'raw_open')
     if net<=0:reason='OPEN_NET_NOT_POSITIVE'
     elif op*fac<=max(a['ifloor'],a['cp']['floor']):reason='OPEN_BELOW_PROTECTION'
    budget=min(r['budget'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,'raw_open'))) if a else ZERO
   else:
    if a is not None:reason='ALREADY_HELD'
    elif op*fac<=r['ifloor']:reason='OPEN_BELOW_PROTECTION'
    budget=r['budget']
   caps={'attempt_budget':budget,'stock_cap':max(ZERO,D('.10')*pre_nav-sv.get(s,ZERO)),'sector_cap':max(ZERO,D('.10')*pre_nav-sec[self.d.sid_sector[s]]),'cash_reserve':max(ZERO,cash-D('.10')*pre_nav)}
   q=0
   if reason=='PASS':
    if r['kind']=='SEED':
     q=self.d.getmeta(s,d)[0].buy_minimum
     if q>r['planned_q'] or q>r['capacity']:reason='DATED_LOT_OR_CAPACITY_CHANGED'
     elif q*p+self.d.fee(s,d,q,p,'buy')>min(caps.values()):reason='MIN_LOT_CAPITAL_REJECT:'+min(caps,key=caps.get)
    else:
     q=self.d.size(s,d,p,min(caps.values()),min(r['planned_q'],r['capacity']))
     if not q:reason='ADD_NO_LEGAL_Q:'+min(caps,key=caps.get)
   row=dict(day=day(d),phase='OPEN',sid=s,round_id=a['id'] if a else None,event=r['kind'],signal_day=r['signal_day'],decision=reason,allocation_rank=rank+1,cp_id=r.get('cp_id'),close_net=r.get('close_net'),open_net=str(net) if net is not None else None,planned_q=r['planned_q'],executed_q=q if reason=='PASS' else 0,**{k:str(v) for k,v in caps.items()});self.candidates.append(row)
   if reason!='PASS':continue
   cost=q*p+self.d.fee(s,d,q,p,'buy');cash-=cost;sec[self.d.sid_sector[s]]+=cost;sv[s]=sv.get(s,ZERO)+cost;reserved.append((r,q,p,net,cost))
  for r,q,p,net,cost in reserved:
   s=r['sid']
   if r['kind']=='SEED':
    self.seq[s]+=1;rid=f'{s}|{self.seq[s]}|{r["signal_day"]}';a=dict(id=rid,sid=s,signal_day=r['signal_day'],birth_type=r['birth_type'],nav0=r['nav0'],seed_day=day(d),cashflow=ZERO,dividend=ZERO,fees=ZERO,lots=[],ifloor=r['ifloor'],factor=dec(self.d.z(s,d)['adjustment_factor']),origin=r['origin'],exit=None,plan=None,cp=None,add_count=0);self.active[s]=a;self.archive[rid]=a
   else:a=self.active[s]
   cp=a['cp'] if r['kind']=='ADD' else None;fl=max(a['ifloor'],cp['floor']) if cp else a['ifloor'];lid=f'{a["id"]}|{len(self.orders)+1}'
   a['lots'].append(dict(id=lid,kind=r['kind'],q=q,bought=day(d),floor=fl,cp_id=cp['id'] if cp else None));self.order(a,d,'BUY_'+r['kind'],q,p,'NEW_A_B_MIN_UNIT' if not cp else 'STRENGTH_POSITIVE_UNCONSUMED_CP',signal_day=r['signal_day'],lot_id=lid,cp_id=cp['id'] if cp else None,close_net=r.get('close_net'),open_net=str(net) if net is not None else None,frozen_attempt_NAV=str(a['nav0']),all_in_cost=str(cost))
   if cp:cp['consumed']=True;a['add_count']+=1;self.eventlog(a,d,'OPEN','CONSUMED_ON_FILL',cp);a['cp']=None
 def close(self,d,prev):
  nav=self.nav(d,'raw_close');pending=[]
  for s,a in sorted(self.active.items()):
   sec=self.d.sectors[self.d.sid_sector[s]].loc[d];z=self.d.z(s,d);f=self.d.f(s,d);c=self.d.c(s,d)
   if not valid(z) or not finite(z.get('raw_close')) or z['raw_close']<=0 or lineage(z)!=a['origin']:raise Blocked(f'{day(d)} {s} CLOSE_INVALID')
   self.invalidate_cp(a,d,'CLOSE','raw_close');adj=dec(z['raw_close'])*a['factor'];i=f.get('i_target');reason='WAIT';net=self.net(a,d,'raw_close')
   if false(i):a['exit']='I_INVALID'
   elif truth(i) and finite(f.get('i_floor')) and f['i_floor']>0:a['ifloor']=max(a['ifloor'],dec(f['i_floor']))
   if adj<=a['ifloor']:a['exit']='I_CLOSE_PROTECTION'
   if a['add_count']==0 and sec.state==0:a['exit']=a['exit'] or 'TRIAL_SECTOR_FALSE'
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
   elif not sec.strength:reason='SECTOR_NOT_STRENGTHENED'
   elif not cpstate_known:reason='CP_UNKNOWN'
   elif cpk is None or not self.cpvalid(a,cpk,z,'raw_close'):reason='NO_VALID_UNCONSUMED_POSTSEED_CP'
   elif net<=0:reason='CLOSE_NET_NOT_POSITIVE'
   else:
    budget=min(D('.02')*a['nav0'],max(ZERO,D('.04')*a['nav0']-self.qvalue(a,d,'raw_close')));cap=self.d.cap[s].get(d,np.nan)
    if not finite(cap):reason='CAPACITY_UNKNOWN'
    else:
     q=self.d.size(s,d,dec(z['raw_close'])*(1+SLIP),budget,int(cap))
     if q:
      a['plan']=dict(kind='ADD',sid=s,signal_day=day(d),cp_date=cpk['date'],cp_id=cpk['id'],budget=budget,planned_q=q,capacity=int(cap),close_net=str(net),origin=a['origin'],factor=a['factor']);reason='ADD_PLANNED'
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
  self.register_pay(d);nav=self.nav(d,'raw_close');mv=sum((self.qvalue(a,d,'raw_close') for a in self.active.values()),ZERO)
  self.ledger.append(dict(day=day(d),cash=str(self.cash),receivable=str(self.receivable),market_value=str(mv),NAV=str(nav),net_liquidation_NAV=str(self.cash+self.receivable+sum((self.quantity(a)*dec(self.d.z(s,d)['raw_close'])*(1-SLIP)-self.d.fee(s,d,self.quantity(a),dec(self.d.z(s,d)['raw_close'])*(1-SLIP),'sell') for s,a in self.active.items()),ZERO)),stocks=len(self.active),shares=sum(self.quantity(a) for a in self.active.values()),weight_pct=str(100*mv/nav),fees_paid=str(sum((a['fees'] for a in self.archive.values()),ZERO))))
  for s,a in self.active.items():
   for l in a['lots']:self.holdings.append(dict(day=day(d),round_id=a['id'],sid=s,lot_id=l['id'],kind=l['kind'],qty=l['q'],bought=l['bought'],raw_mark=str(self.d.z(s,d)['raw_close']),market_value=str(l['q']*dec(self.d.z(s,d)['raw_close'])),protection_signal=str(a['ifloor'] if l['kind']=='SEED' else l['floor']),factor=str(a['factor']),cp_id=l.get('cp_id'),locked_exit=a['exit'] or l.get('exit')))
  self.attribute(d,nav)
  return pending
 def attribute(self,d,nav):
  for sector in self.d.sector_ids:
   sec=self.d.sectors[sector].loc[d];attempts=[a for a in self.archive.values() if self.d.sid_sector[a['sid']]==sector];active=[a for a in self.active.values() if self.d.sid_sector[a['sid']]==sector];trades=[t for t in self.orders if t['day']==day(d) and self.d.sid_sector[t['sid']]==sector];cand=[t for t in self.candidates if t['day']==day(d) and self.d.sid_sector[t['sid']]==sector];mv=sum((self.qvalue(a,d,'raw_close') for a in active),ZERO);cf=sum((a['cashflow'] for a in attempts),ZERO);div=sum((a['dividend'] for a in attempts),ZERO)
   self.sector_daily.append(dict(day=day(d),sector51=sector,**{k:int(sec[k]) for k in ['N','K','n','U','paired_K','entered3','left3','diff','state']},strength=bool(sec.strength),stocks=len(active),market_value=str(mv),account_weight_pct=str(100*mv/nav),trade_cashflow=str(cf),net80_entitlement=str(div),marked_net_pnl=str(cf+div+mv),seeds_filled=sum(t['side']=='BUY_SEED' for t in trades),adds_filled=sum(t['side']=='BUY_ADD' for t in trades),sells_filled=sum(t['side'].startswith('SELL') for t in trades),seed_buy_cash=str(-sum((dec(t['cash_delta']) for t in trades if t['side']=='BUY_SEED'),ZERO)),add_buy_cash=str(-sum((dec(t['cash_delta']) for t in trades if t['side']=='BUY_ADD'),ZERO)),sell_cash=str(sum((dec(t['cash_delta']) for t in trades if t['side'].startswith('SELL')),ZERO)),new_A=sum(t['phase']=='CLOSE' and t['event']=='A' for t in cand),new_B=sum(t['phase']=='CLOSE' and t['event']=='B' for t in cand),open_rejected=sum(t['phase']=='OPEN' and t['decision']!='PASS' for t in cand)))
 def run(self,checkpoint=False):
  pending=[]
  for d in self.d.days:
   prev=self.d.cal[self.d.cal.get_loc(d)-1]
   keys=['cash','receivable','active','archive','seq','claims','snapshots'];snap=copy.deepcopy({k:getattr(self,k) for k in keys});logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily'];lengths={k:len(getattr(self,k)) for k in logs}
   try:
    self.economic_preflight(d,pending);self.accrue(d);self.exit_open(d);self.alloc_open(d,pending);pending=self.close(d,prev)
    if checkpoint and day(d)=='2024-09-23':
     self.pending=pending;self.export(O/'prefix_20240923_once');print('CHECKPOINT_20240923 '+json.dumps(self.ledger[-1]),flush=True)
   except Blocked as ex:
    self.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=self.orders[lengths['orders']:]);
    for k,v in snap.items():setattr(self,k,v)
    for k,n in lengths.items():del getattr(self,k)[n:]
    self.blockers.append(str(ex));break
  self.pending=pending;return self
 def export(self,path):
  path.mkdir(exist_ok=False)
  rows={'ORDERS':self.orders,'CANDIDATES':self.candidates,'CP_EVENTS':self.cp_log,'DAY_LEDGER':self.ledger,'HOLDINGS':self.holdings,'EQUITY_EVENTS':self.equity,'SECTOR_DAILY':self.sector_daily}
  for name,rr in rows.items():
   rr=[dict(r,sector51=self.d.sid_sector[r['sid']]) if 'sid' in r else r for r in rr];save(path/(name+'.json'),rr);pd.DataFrame(rr).to_csv(path/(name+'.csv'),index=False)
  archive=[]
  for a in self.archive.values():
   r={k:v for k,v in a.items() if k not in ['lots','cp','plan']};r['sector51']=self.d.sid_sector[a['sid']];r['final_qty']=self.quantity(a);r['marked_net_pnl']=str(a['cashflow']+a['dividend']+(self.qvalue(a,pd.Timestamp(self.ledger[-1]['day']),'raw_close') if self.quantity(a) else ZERO));archive.append(r)
  save(path/'ATTEMPTS.json',archive);pd.DataFrame(archive).to_csv(path/'ATTEMPTS.csv',index=False);save(path/'UNCERTIFIED_DAY.json',getattr(self,'uncertified_day',None));save(path/'BLOCKERS.json',self.blockers);save(path/'PENDING_AT_END.json',self.pending)
  save(path/'EXCLUDED_UNCLASSIFIED.json',self.d.excluded);save(path/'EVENT_ADMISSION.json',self.d.admission)
  save(path/'SOURCE_HASHES.json',self.d.hashes);assert all(sha(p)==h for p,h in self.d.hashes.items())
  save(path/'OUTPUT_HASHES.json',{p.name:sha(p) for p in path.iterdir() if p.is_file()})
def sha_text(v):return hashlib.sha256(json.dumps(v,default=str).encode()).hexdigest()[:24]
def synthetic():
 assert trigger(0,1,-1,1)=='A';assert trigger(1,1,0,1)=='B';assert trigger(1,1,-1,1) is None;assert trigger(-1,1,0,1) is None
 assert not strengthened(20,34,52,25);assert strengthened(26,29,52,22);assert not strengthened(26,29,52,0)
 q=QuantityRule('x',100,100,100,True,1);assert q.buy_floor(99)==0 and q.buy_floor(199)==100 and q.sell_floor(13,13)==13
 assert D('10')*100-D('5')-D('995')==0 # zero is not strictly profitable
 cp=dict(consumed=False,invalid=False,origin=('s','p','0'),floor=D(10));a={};fake=Engine.__new__(Engine);z=dict(raw_open=11,adjustment_factor=1,source_kind='s',source_path='p',segment_id=0)
 assert fake.cpvalid(a,cp,z,'raw_open');cp['consumed']=True;assert not fake.cpvalid(a,cp,z,'raw_open');cp['consumed']=False;z['raw_open']=10;assert not fake.cpvalid(a,cp,z,'raw_open')
 # Real execution-method test with a stub: T+1 locks and exits override a queued ADD.
 class Stub:
  names={'x':'x'};sid_sector={'x':'TEST'}
  def z(self,s,d):return dict(raw_open=9,adjustment_factor=1,source_kind='s',source_path='p',segment_id=0)
  def fee(self,*args):return D(5)
 e=Engine(Stub());a=dict(id='r',sid='x',lots=[dict(id='l',q=100,kind='SEED',bought='2024-09-09',floor=D(10))],ifloor=D(10),factor=D(1),exit=None,plan={'kind':'ADD'},cp=None,cashflow=D(-1005),fees=D(5));e.active['x']=a;e.archive['r']=a;e.exit_open(pd.Timestamp('2024-09-09'));assert e.quantity(a)==100 and a['lots'][0]['exit']=='T1_LOCKED_EXIT';e.exit_open(pd.Timestamp('2024-09-10'));assert not e.active and a['plan'] is None and e.orders[-1]['side']=='SELL_ALL'
 return dict(result='PASS',checks=['A_B_UNKNOWN','strength_two_closes_diff','quantity_rule','strict_positive_fee_boundary','CP_single_consumption_and_breach','T1_lot_lock','exit_overrides_ADD'])
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['synthetic','freeze','run'],required=True);ap.add_argument('--end',default='2024-10-31');ap.add_argument('--output',default='full_20241031_once');ap.add_argument('--seal',default='FREEZE.json');args=ap.parse_args()
 if args.mode=='synthetic':
  v=synthetic();from synthetic_joint import run as joint_tests;v['checks']+=joint_tests();save(O/'SYNTHETIC_QA.json',v);print(v)
 elif args.mode=='freeze':
  assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert not (O/args.seal).exists();d=Data();save(O/args.seal,dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes=d.hashes,no_candidate_outcome_run=True,universe_total=1709,eligible=len(d.ids),excluded=len(d.excluded),populated_sectors=len(d.sector_ids),bounded_events=len(d.events)));print('FROZEN',len(d.hashes),'stocks',len(d.ids),'sectors',len(d.sector_ids),'events',len(d.events))
 else:
  assert args.end=='2024-10-31';f=read(O/args.seal);assert all(sha(p)==h for p,h in f['hashes'].items());d=Data(args.end);assert d.hashes==f['hashes'];e=Engine(d).run(checkpoint=True);e.export(O/args.output);print(json.dumps(dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None),ensure_ascii=False))
