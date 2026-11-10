from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import importlib.util,sys,json,gzip,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0);ONE=D(1)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
K=load('full_budget_frozen_math',W/'entry-loss-budget-local153-20261031/core.py');Budget=K.Budget

def context(a,sid,at):
 day=pd.Timestamp(at.date());f=a.facts.f[sid];j=f.index.searchsorted(day,side='right')-1
 if j<0:return dict(structure_id=None,source_segment=None)
 r=f.iloc[j];cache=getattr(a.facts,'_budget_epochs',None)
 if cache is None:cache={};a.facts._budget_epochs=cache
 if sid not in cache:
  known=f.e0_ready.astype(bool)&f.e0_target.notna();on=f.e0_target.astype('boolean').where(known).groupby(f.segment_id).ffill().fillna(False).astype(bool);start=on&~on.groupby(f.segment_id).shift(fill_value=False);labels=pd.Series(None,index=f.index,dtype=object)
  for t in f.index[start]:labels.loc[t]=f'{sid}|source={int(f.loc[t,"segment_id"])}|E0={t.date()}'
  cache[sid]=labels.groupby(f.segment_id).ffill().where(on,None).to_dict()
 return dict(structure_id=cache[sid][f.index[j]],source_segment=int(r.segment_id))

def account_class(Parent,ctx=context):
 class Account(Parent):
  def __init__(self,*a,**kw):super().__init__(*a,**kw);self.loss_b=None;self.loss_states={};self.loss_groups={}
  def fill_buy(self,sid,w):
   order=self.buys.get(sid);oid=order.order_id if order else None;intent=self.intents.get(oid) if oid else None;before=self.quantity(sid);f=super().fill_buy(sid,w)
   if self.loss_b is not None and f:
    cost=f.gross_cny+f.fees_cny
    if not before:
     cxt=ctx(self,sid,intent['decision_at']);group=cxt['structure_id'] or f'{sid}|epoch_unknown|buy={f.receipt_id}';self.loss_states[sid]=dict(controller=Budget(cost,self.loss_b),K=cost,div=Z,sales=Z,fees=f.fees_cny,group=group,cycle=f.receipt_id,entry_at=w.at,context=cxt)
     g=self.loss_groups.setdefault(group,dict(symbol=sid,attempts=0,closed=0,net=Z,fees=Z,budget_exits=0));g['attempts']+=1;self.log('loss_start',w.at,sid=sid,cycle=f.receipt_id,group=group,b=self.loss_b,K=cost,decision_at=intent['decision_at'],context=cxt)
    else:
     c=self.loss_states[sid];c['K']+=cost;c['controller'].K=c['K'];c['fees']+=f.fees_cny
    self.log('loss_buy_cost',w.at,sid=sid,cycle=self.loss_states[sid]['cycle'],actual_cost_added=cost,K=self.loss_states[sid]['K'],shares=self.quantity(sid),buy_pending=sid in self.buys)
   return f
  def accrue_dividend(self,**kw):
   super().accrue_dividend(**kw)
   if self.loss_b is not None:
    c=self.loss_states[kw['sid']];c['div']+=D(kw['net_local']);self.log('loss_dividend',kw['ex_at'],sid=kw['sid'],cycle=c['cycle'],net=kw['net_local'])
  def fill_exit(self,sid,w):
   f=super().fill_exit(sid,w)
   if self.loss_b is not None and f:
    c=self.loss_states[sid];c['sales']+=f.gross_cny-f.fees_cny;c['fees']+=f.fees_cny
    if self.quantity(sid)==0 and sid not in self.buys and sid not in self.exits:
     net=c['sales']+c['div']-c['K'];g=self.loss_groups[c['group']];g['closed']+=1;g['net']+=net;g['fees']+=c['fees'];g['budget_exits']+=int(c['controller'].reason=='loss_budget');self.log('loss_end',w.at,sid=sid,cycle=c['cycle'],group=c['group'],net=net,K=c['K'],dividend=c['div'],sales=c['sales'],fees=c['fees'],reason=c['controller'].reason);del self.loss_states[sid]
   return f
 return Account

def process(a,stocks,clock,Fact):
 if a.loss_b is None:return stocks
 for s in stocks:
  sid=s.security_id
  if not a.quantity(sid):continue
  c=a.loss_states[sid];m=a.market;mk=m.latest_mark(sid,clock.decision_at);day=pd.Timestamp(clock.session_date);raw=m.raw[sid];known=bool(day in raw.index and raw.loc[day,'observed_bar'] and raw.loc[day,'valid_price'] and mk.known_at.date()==clock.session_date);q=a.quantity(sid);gross=D(q)*mk.raw_price;slip=gross*D('.0005')*a.cost_multiplier;schedule=m.fees(sid,clock.decision_at);fee=sum(schedule.incremental('sell',gross-slip,{}, {},a.cost_multiplier,shares=q,par_value=m.rules.get('security_metadata',{}).get(sid,{}).get('par_value')).values(),Z);V=gross+c['div']+c['sales']-fee-slip;original=s.trend_up.read(clock) is False or sid in a.exits;ctrl=c['controller'];hit=ctrl.close(V=V if known else None,known=known,at=str(clock.decision_at),original=original)
  a.log('loss_checkpoint',clock.decision_at,sid=sid,cycle=c['cycle'],group=c['group'],K=c['K'],V=V,known=known,b=a.loss_b,original_priority=original,locked=ctrl.locked,reason=ctrl.reason,shares=q,buy_pending=sid in a.buys,exit_pending=sid in a.exits)
  if ctrl.locked and ctrl.reason=='loss_budget' and sid not in a.exits:
   qt=m.quote(sid,clock.decision_at)
   if qt:
    a.request_exit(qt,clock);a.log('loss_budget_request',clock.decision_at,sid=sid,cycle=c['cycle'],group=c['group'],b=a.loss_b,K=c['K'],V=V,shares=q)
 # The original Security objects and their I/Q facts are returned unchanged.
 return stocks

def setup(sector,root,enabled,cutoff=None):
 prior=RR/'pvr-act-comparison-20261027'
 if sector=='TECH':
  P=load('budget_full_original_tech',prior/'code/experiment.py');P.setup('RS',cutoff);R,E=P.R,P.E;Parent=R.Account;prep=Path(read(prior/'input.json')['snapshot']['path']);core=prior/'input';mode='I'
 else:
  loc=RR/'innovative-drug-local-recovery-20261028';sys.path.insert(0,str(loc/'code'));P=load('budget_full_original_drug',loc/'code/study.py');P.setup(root,cutoff);R,E=P.R,P.E;Parent=R.Account;prep=RR/'innovative-drug-sfw3-20261028/prepared';core=prep;mode='ACT'
 R.HERE=root
 if cutoff:E.risk_policy.RECOVERY=E.risk_policy.RECOVERY.loc[:cutoff].copy()
 R.Account=account_class(Parent);oldspec=R.specs
 def specs(modes,stresses,variant):
  ss=oldspec(modes,stresses,variant)
  if not enabled:return ss
  from dataclasses import replace
  return tuple(replace(s,account_id=s.account_id.split('__')[0]+'__'+p+'_'+s.account_id.split('__')[1]) for p in ['C10','C20','C30'] for s in ss)
 R.specs=specs;Base=R.Runner
 class Runner(Base):
  def run_tech(self):
   for aid,a in self.accounts.items():a.loss_b=D(aid.split('__')[1].split('_')[0][1:])/100 if enabled else None
   return super().run_tech()
 R.Runner=Runner;orig=E.risk_policy.override
 def override(a,stocks,clock,riskmode,Fact):return process(a,orig(a,stocks,clock,riskmode,Fact),clock,Fact)
 E.risk_policy.override=override;commit0=E.ledger.commit_cutoff
 def commit(a,**kw):
  if a.loss_b is None:return commit0(a,**kw)
  factory=kw['decision_factory'];dd=[]
  def capture(**args):
   d=factory(**args);interesting={e.security_id for e in d.eligibility if e.q is True}|set(a.positions)|set(a.exits)|set(a.buys)|{x.security_id for x in kw.get('completed_exits',())};dd.append(dict(selected=d.selected,rejected=d.rejected,waiting=d.waiting,continue_buys=d.continue_buys,pause_buys=d.pause_buys,cancel_buys=d.cancel_buys,exit_requests=d.exit_requests,eligibility=[e for e in d.eligibility if e.security_id in interesting],memories=[m for m in d.memories if m.security_id in interesting]));return d
  before=a.balance(kw['clock'].decision_at,kw['marks']);ack=commit0(a,**dict(kw,decision_factory=capture));a.log('loss_admission',kw['clock'].decision_at,before=before,decisions=dd,accepted=ack.accepted,rejected=ack.rejected,occupancy=ack.occupancy);return ack
 E.ledger.commit_cutoff=commit
 return R,E,core,prep,mode
