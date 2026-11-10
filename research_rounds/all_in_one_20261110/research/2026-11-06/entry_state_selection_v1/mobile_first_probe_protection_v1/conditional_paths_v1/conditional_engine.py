"""Auditable bounded native adapter. Definitions only; no path runs at import."""
import inspect,copy,textwrap,hashlib
from decimal import Decimal as D
from dataclasses import replace
import pandas as pd
from inputs import J,A,END,START,canon
Z=D(0);ARMS=('CP_CONTROL_COMMON_I_SIZE','I_PROBE_COMMON_I_SIZE');DIFFS={}

def compile_method(name,source,changes,env):
 original=source
 for old,new in changes:
  assert source.count(old)==1,(name,old,source.count(old));source=source.replace(old,new)
 DIFFS[name]={'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'derived_sha256':hashlib.sha256(source.encode()).hexdigest(),'changes':[{'old':a,'new':b}for a,b in changes],'derived_source':source}
 g=dict(env);exec(compile(textwrap.dedent(source),__file__+':'+name,'exec'),g);return g[name]

def nominal_risk(q,p,f,schedule,par=None):return J.LR.protection_risk(q,p,f,schedule,par)
def freeze_probe(i,a,factor,arm):
 q=i['quote'];p=q.raw_price*(1+J.LR.SLIP);risk=a.current_nav*D('.0025');gross=a.current_nav*D('.02');floor=i['I_floor']/factor
 cap=J.LR.maximum_quantity(q.quantity,int(gross/p),lambda n:nominal_risk(n,p,floor,q.fees,q.par_value)<=risk)
 i.update(common_probe=True,probe_arm=arm,seed_signal_nav=a.current_nav,risk_budget=risk,budget=gross,cap=cap,risk_floor=i['I_floor'],guard_floor=i['floor'],reference_price=p,signal_factor=factor,signal_nominal_risk=nominal_risk(cap,p,floor,q.fees,q.par_value),size_reject=None if cap else 'minimum_unit_exceeds_common_I_risk_or_2pct')
 if arm=='I_PROBE_COMMON_I_SIZE':i['kind']='probe_mobile'

class RemainingCost:
 def __init__(self):self.qty=0;self.cost=Z;self.round=0;self.cursor=0
 def sync(self,a):
  for r in a.journal[self.cursor:]:
   if r['kind']=='real_buy_fill':
    if not self.qty:self.round+=1;assert self.cost==0
    self.qty+=r['shares'];self.cost+=D(r['shares'])*r['price']+r['fees']
   elif r['kind']=='real_sell_fill':
    q=r['shares'];assert 0<q<=self.qty;self.cost=self.cost*D(self.qty-q)/D(self.qty);self.qty-=q
    if not self.qty:self.cost=Z
   elif r['kind']=='actual_split':
    self.qty=int(D(self.qty)*r['ratio'])
    if not self.qty:self.cost=Z
  self.cursor=len(a.journal);assert self.qty==sum(a.quantity(s)for s in a.positions);return self

class Account(J.Account):pass
# Native pending reservation mirror uses I risk reference separately from OPEN guard.
Account.sync=compile_method('sync',inspect.getsource(J.Account.sync),[("bo.floor=float(self.order_meta[o.order_id]['floor']/self.facts.factor(sid,at))","bo.floor=float(self.order_meta[o.order_id].get('risk_floor',self.order_meta[o.order_id]['floor'])/self.facts.factor(sid,at))")],J.__dict__)
# Keep native receipt/core-epoch/fees/cash callbacks. Change only candidate layer responsibility floor before mirror sync.
Account.fill_buy=compile_method('fill_buy',inspect.getsource(J.Account.fill_buy),[("super().fill_buy(sid,w)","J.C.Account.fill_buy(self,sid,w)"),("x=self.layers[-1];self.jmeta", "x=self.layers[-1]\n   if i.get('common_probe'):\n    x.update(common_probe=True,guard_floor=i['guard_floor'],signal_I_floor=i['I_floor'],frozen_signal_nav=i['seed_signal_nav'],frozen_risk_budget=i['risk_budget'])\n    if x['kind']=='probe_mobile':x['floor']=i['I_floor']\n   self.jmeta")],dict(J.__dict__,J=J))

PROFIT_ROUTE=compile_method('route',A.P.NEW_ROUTE,[
 ("  routes=['probe']","  profit_ok=self.profit_permission(a,i,x,at)\n  routes=['probe']"),
 ("    if sr+risk>.01*nav+1e-9:fails.append('sector_risk')","    if sr+risk>.01*nav+1e-9:fails.append('sector_risk')\n    if not profit_ok:fails.append('nonprofitable_remaining_holding')")
 ],J.__dict__)

class Runner(J.Runner):
 def __init__(self,shared,receipts,cp,states,ir,case,arm):
  assert arm in ARMS
  super().__init__(shared,receipts,policies=('B',),stock_cp=cp,industry_states=states,industry_receipts=ir)
  self.case=case;self.arm=arm;self.sid=case['sid'];self.profit_events=[];self.seed_checks=[];self.cost_book=RemainingCost();self.open_risks=[]
  a=self.accounts.pop('B');a.__class__=Account;a.budget.__class__=A.NoConfirmed60Budget;a.label=arm;a.name=arm;self.accounts={arm:a};self.account=a
  n=D(case['seed_nav']);a.available=a.initial_cash=a.current_nav=a.minimum_available=n;a.budget.cash=float(n);a.risk_state=dict(on=True,peak=n,saw_off=False,previous_fast=False,episode=0)
  if case['seed_core_epoch']is not None:a.core_epoch[self.sid]=tuple(case['seed_core_epoch'])
  self.open_checks=[];self.seed_role_suppressed=[]
 def profit_permission(self,a,i,x,at):
  b=self.cost_book.sync(a);q=b.qty;op=x['known_open'];sellpx=op*(1-J.LR.SLIP);sf=J.LR.fees(q,sellpx,x['schedule'],'sell',i['quote'].par_value)if q else Z;value=D(q)*sellpx-sf;allowed=not q or value>b.cost
  self.profit_events.append(dict(at=at,sid=i['sid'],role=i['role'],kind=i['kind'],qty=q,cost=b.cost,net_liquidation=value,allowed=allowed,round=b.round))
  return allowed
 def route(self,a,i,x,at):
  # Risk shrink follows original OPEN preview; profit gate stays INSIDE native route allowed(q).
  q=self.cost_book.sync(a).qty
  if i.get('common_probe'):
   assert q==0,('fresh empty probe acquired preexisting inventory',i)
   floor=i['I_floor']/self.facts.factor(i['sid'],at)
   maxq=J.LR.maximum_quantity(x['rule'],x['maxq'],lambda n:nominal_risk(n,x['price'],floor,x['schedule'],i['quote'].par_value)<=i['risk_budget'])
   if not maxq:return None,'OPEN_minimum_exceeds_frozen_I_risk'
   x=dict(x,maxq=maxq,floor=floor)
   assert x['maxq']<=i['cap']and D(x['maxq'])*x['price']<=i['budget']
   self.open_risks.append(dict(at=at,sid=i['sid'],guard=i['guard_floor']/self.facts.factor(i['sid'],at),I_floor=floor,maxq=x['maxq'],frozen_q=i['cap'],frozen_N=i['seed_signal_nav'],gross_budget=i['budget'],risk_budget=i['risk_budget'],risk=nominal_risk(x['maxq'],x['price'],floor,x['schedule'],i['quote'].par_value)))
  return PROFIT_ROUTE(self,a,i,x,at)
 def warm(self,calendar):
  # No intent, financial order, fill, or risk-account replay during warmup.
  a=self.account;seed=self.case['signal_day']
  for day in calendar:
   if day>=seed:break
   at=J.M.N.iso(day+'T15:10:00+08:00');self.market.set_phase(at,'CLOSE');self.warm_signals(at);a.current_nav=D(self.case['seed_nav']);a.sync(at);self.industry(a,at)
  assert not a.trades and not a.layers and not a.pending and not a.positions
  self.daily=[];self.stage_events=[];a.sync_rows=[]
 def freeze_probe(self,i,a,at):freeze_probe(i,a,self.facts.factor(i['sid'],at),self.arm)

src=inspect.getsource(J.Runner.planning)
# The exact market qualification/epoch prefix is separately callable for seed warmup.
prefix=src[:src.index('  ordered=')].replace('def planning(', 'def warm_signals(',1)
Runner.warm_signals=compile_method('warm_signals',prefix,[],J.__dict__)
Runner.planning=compile_method('planning',src,[
 ("for role in roles:", "for role in roles:\n     if str(at.date())==self.case['signal_day'] and role=='core':\n      self.seed_role_suppressed.append(dict(day=str(at.date()),sid=sid,role=role,epoch=epoch,reason='FIXED_ORIGINAL_MOBILE_INTENT_SEED_ONLY'));continue"),
 ("M.E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]","a.pending=[] # Original NOACT CONTROL noop; ACT always on."),
 ("if x['kind']!='add' or x['id'] in a.sell_layers.get(sid,set()):continue", "if x['kind']=='probe_mobile':\n      known_floor=self.facts.floor(sid,at,'I')\n      if known_floor is not None:x['floor']=known_floor\n      continue\n     if x['kind']!='add' or x['id'] in a.sell_layers.get(sid,set()):continue"),
 ("if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))", "if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))\n     elif not held:\n      i['I_floor']=floor;self.freeze_probe(i,a,at)")
 ],J.__dict__)

def seed_plan(r):
 at=J.M.N.iso(r.case['signal_day']+'T15:10:00+08:00');r.market.set_phase(at,'CLOSE');r.planning(at);a=r.account
 intents=[i for i in a.pending if i['sid']==r.sid]
 assert not any(i['role']=='core'for i in intents),('seed spurious CORE',r.case['round_id'],a.core_epoch,r.global_watch,intents)
 assert all(i['role']=='mobile'and i.get('common_probe')for i in intents)
 assert r.global_watch.get(r.sid)==tuple(r.case['original_initial_trade']['epoch']),('seed epoch mismatch',r.case['round_id'],r.global_watch,r.case['original_initial_trade']['epoch'])
 opp=r.opportunities[-1];old=r.case['original_seed_opportunity'];assert opp['core_Q']==old['core_Q']and opp['mobile_Q']==old['mobile_Q']and opp['roles']==old['roles'],('seed market role mismatch',r.case['round_id'],opp,old)
 assert opp['mobile_Q'] is True and opp['CP1_id']==r.receipts[r.sid][r.case['signal_day']]['receipt_id']
 return dict(round_id=r.case['round_id'],arm=r.arm,core_epoch=a.core_epoch.get(r.sid),global_watch=r.global_watch.get(r.sid),original_epoch=r.case['original_initial_trade']['epoch'],core_Q=opp['core_Q'],mobile_Q=opp['mobile_Q'],roles=opp['roles'],original_seed_roles=old['roles'],seed_suppressed=r.seed_role_suppressed,intents=[{k:v for k,v in i.items()if k not in ('clock','quote','CP1_trace')}for i in intents],funding=r.funding,seed_NAV=a.current_nav)
