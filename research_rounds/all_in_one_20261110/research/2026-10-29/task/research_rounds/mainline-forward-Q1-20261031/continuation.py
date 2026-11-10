"""Frozen single-account executors, own quarter states, one Q1 pair."""
from pathlib import Path
import sys,importlib.util,copy,pickle,json,gzip,time,hashlib,traceback
from datetime import datetime,time as dt
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;ATT=W/'mainline-attention-top3-Q4-20261031';ABS=W/'mainline-absolute-Q4-20261031'
s=importlib.util.spec_from_file_location('Q1_frozen_attention',ATT/'attention.py');A=importlib.util.module_from_spec(s);sys.modules[s.name]=A;s.loader.exec_module(A);T,X,M=A.T,A.X,A.M
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def pack(r,cursor):
 a=r.accounts['T3'];return dict(policy=r.policy,cursor=cursor,runner={k:copy.deepcopy(getattr(r,k)) for k in ['last_epoch','epoch','global_watch','applied_actions']},b0=copy.deepcopy(r.b0.__dict__),account=copy.deepcopy({k:v for k,v in a.__dict__.items() if k not in X.EXCLUDE}))
def write_checkpoint(path,states):
 raw=pickle.dumps(states,protocol=5);reloaded=pickle.loads(raw);assert states==reloaded and X.fingerprint(states)==X.fingerprint(reloaded);Path(path).write_bytes(raw);M.save(str(path)+'.json',dict(sha256=hashlib.sha256(raw).hexdigest(),fingerprint=X.fingerprint(states),policies=list(states),all_private_account_fields_preserved=True));return reloaded
def raw_references(shared):
 b,m,facts=shared;refs={r['day']:r for r in rows(ABS/'results/selection.jsonl.gz') if r['policy']=='RAW'};matrix=pd.read_parquet(M.F);quarter=matrix[matrix.quarter.eq('2026Q1')];assert not quarter[['H1_original','attention_ratio','R21']].isna().any().any();sector={l.security_id:l.sector_id for l in b.lines};order={l.security_id:i for i,l in enumerate(b.lines)}
 for day,g in quarter.groupby('day',sort=False):
  g=g.set_index('sector');date=pd.Timestamp(day);raw=[];available=[]
  for sid in m.lines:
   f=facts.f[sid]
   if date not in f.index:continue
   r=f.loc[date]
   if bool(r.i_buy) and bool(r.i_target):
    raw.append(sid)
    if np.isfinite(g.loc[sector[sid],'H1_original']) and np.isfinite(g.loc[sector[sid],'R21']):available.append(sid)
  n=(len(available)+1)//2;ordered=sorted(available,key=lambda sid:(-float(g.loc[sector[sid],'H1_original']),sector[sid],order[sid],sid));refs[day]=dict(day=day,raw_I_count=len(raw),candidates=available,maximum_B=n,selected=ordered[:n])
 return refs
class Actor(M.Pilot):
 make_lists=A.ranked_lists
 industry_target=A.Pilot.industry_target
 def __init__(self,state,shared,policy,references):
  M.Pilot.__init__(self,policies=('T3',),shared=shared)
  if 'policy' in state:assert state['policy']==policy
  for k,v in state['runner'].items():setattr(self,k,copy.deepcopy(v))
  self.b0.__dict__.clear();self.b0.__dict__.update(copy.deepcopy(state['b0']));a=self.accounts['T3'];a.__dict__.clear();a.__dict__.update(copy.deepcopy(state['account']));a.market=self.market;a.facts=self.facts;a.check();assert X.fingerprint({k:v for k,v in a.__dict__.items() if k not in X.EXCLUDE})==X.fingerprint(state['account']);a.label='T3';a.rank_policy='T3';self.policy=policy;self.off=policy=='RAW';self.rank_enabled=policy=='ATT';self.raw_selection=references;self.capacity=[];self.targets=[];self.run_seconds=0
 def run_from(self,cursor,end,budget=None):
  started=time.monotonic();begin=M.N.iso(cursor+'T15:10:00+08:00');finish=M.N.iso(end+'T15:10:00+08:00');closes={x for x in self.market.cutoffs if begin<x<=finish};opens={x for x in self.market.sessions['A'] if begin<x<=finish};acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,M.N.TZ) for d in self.actions_by_date};events=sorted(closes|opens|{x for x in acts if begin<x<=finish});assert finish in closes;M.E.risk_policy.RECOVERY=pd.read_csv(ABS/'recovery.csv',index_col=0,parse_dates=True).loc[:end]
  for at in events:
   if budget and time.monotonic()-started>budget:raise TimeoutError('Q1 remaining90s budget')
   for a in self.accounts.values():a.settle_due(at)
   self._actions(at)
   for a in self.accounts.values():self._payments(a,at)
   if at in opens:
    for a in self.accounts.values():self.opening(a,at)
   if at in closes:
    self.planning(at)
    if len(self.daily)%20==0:print('CLOSE',self.policy,str(at.date()),len(self.daily),round(time.monotonic()-started,3),flush=True)
  self.run_seconds=time.monotonic()-started;return self
def physical_view(shared,end):
 b,m,f=shared;date=pd.Timestamp(end);b2=copy.copy(b);b2.series={k:copy.copy(v) for k,v in b.series.items()}
 for v in b2.series.values():v.states=v.states.loc[:end]
 d,col,score=b._h1_cache;mask=d<=date;b2._h1_cache=(d[mask],col,score[mask]);m2=copy.copy(m);m2.bundle=b2;m2.raw={k:v.loc[:end] for k,v in m.raw.items()};m2.arr={}
 for sid,a in m.arr.items():
  n=len(m2.raw[sid]);m2.arr[sid]={k:(v[v<n] if k in ['good','positive'] else v[:n] if isinstance(v,np.ndarray) else v) for k,v in a.items()}
 m2.actions={sid:[e for e in es if e['effective_date']<=end] for sid,es in m.actions.items()};m2.cache_at=None;m2.mark_verified=set();m2.window_verified=set();m2.notices=[];m2._notice_keys={};f2=M.E.Facts.__new__(M.E.Facts);f2.b=b2;f2.market=m2;f2.f={k:v.loc[:end] for k,v in f.f.items()};f2.cache={};f2.day=None;f2.structure_lookup=copy.copy(f.structure_lookup);return b2,m2,f2
def observable(r):
 a=r.accounts['T3'];return dict(daily=r.daily,trades=a.trades,audit=a.audit_log,decisions=a.decisions,counts=dict(a.counts),layers=a.layers)
def recover(shared,references):
 path=O/'boundary-2025-12-31.chk'
 if path.exists():
  info=M.read(str(path)+'.json');assert M.sha(path)==info['sha256'];states=pickle.loads(path.read_bytes());assert X.fingerprint(states)==info['fingerprint'];return states
 seed=T.original_seed();states={};receipts=[]
 for policy,root,name in [('RAW',ABS,'RAW'),('ATT',ATT,'T3')]:
  t=time.monotonic();r=Actor(seed,shared,policy,references);r.run_from('2025-09-30','2025-12-31');old=obj(root/'results'/f'{name}.json.gz');old_daily=[z for z in rows(root/'results/daily.jsonl.gz') if z['account']==name];a=r.accounts['T3'];assert X.canon([dict(z,account=name) for z in r.daily])==X.canon(old_daily)
  for key,v in dict(trades=a.trades,layers=a.layers,audit=a.audit_log,decisions=a.decisions,counts=dict(a.counts),minimum_available=a.minimum_available,ops=a.ops,layer_structures=a.layer_structures,risk_rows=a.risk_rows,structure_risk=a.structure_risk).items():assert X.canon(v)==X.canon(old[key]),(policy,'Q4 restore',key)
  states[policy]=pack(r,'2025-12-31');receipts.append(dict(policy=policy,restore_seconds=time.monotonic()-t,run_seconds=r.run_seconds,NAV=str(a.current_nav),positions=len(a.positions),buys_pending=len(a.buys),sells_pending=len(a.exits),unexecuted_next_open_intents=len(a.pending),risk_state=a.risk_state,exact_original_daily_and_all_audits=True));print('RESTORED',policy,r.run_seconds,str(a.current_nav),len(a.positions),flush=True)
 states=write_checkpoint(path,states);M.save(O/'Q4_RECOVERY_GATE.json',dict(passed=True,receipts=receipts,no_old_economic_selection=True,own_private_states_not_equalized=True));return states
def main():
 prep=time.monotonic();f=M.read(ATT/'FREEZE.json');assert all(M.sha(p)==h for p,h in f['sha256'].items());X.configure();shared=M.context();refs=raw_references(shared);states=recover(shared,refs);t=time.monotonic();cut=physical_view(shared,'2026-01-09');gates=[]
 for policy in ['RAW','ATT']:
  full=Actor(states[policy],shared,policy,refs);full.run_from('2025-12-31','2026-01-09');short=Actor(states[policy],cut,policy,{d:v for d,v in refs.items() if d<='2026-01-09'});short.run_from('2025-12-31','2026-01-09');assert X.canon(observable(full))==X.canon(observable(short));gates.append(dict(policy=policy,physical_prefix_exact=True,closes=len(full.daily),initial_NAV=str(states[policy]['account']['current_nav']),initial_positions=len(states[policy]['account']['positions'])))
 M.save(O/'GATE.json',dict(passed=True,whole_preparation_recovery_prefix_seconds=time.monotonic()-prep,prefix_seconds=time.monotonic()-t,prefix_end='2026-01-09',policies=gates,original_frozen_selectors_used=True,raw_selection_reference_only_replaced_by_same_day_pure_input_cache=True))
 files=[O/'PROTOCOL.txt',O/'continuation.py',O/'boundary-2025-12-31.chk',ATT/'attention.py',ATT/'FREEZE.json',ATT/'results/T3.json.gz',ABS/'results/RAW.json.gz',ABS/'recovery.csv',M.F];M.save(O/'FREEZE.json',dict(before_two_Q1_paths=True,no_Q2=True,normal_only=True,budget_seconds=90,sha256={str(p):M.sha(p) for p in files}));M.save(O/'RAW_MARKET_REFERENCES.json',refs)
 timer=time.monotonic();progress=[];ends={}
 for policy in ['RAW','ATT']:
  remaining=90-(time.monotonic()-timer)
  if policy=='ATT' and remaining<32:M.save(O/'BUDGET_BLOCK.json',dict(remaining=remaining,completed=progress,reason='measured remaining budget below safe ATT estimate'));return
  r=Actor(states[policy],shared,policy,refs)
  try:r.run_from('2025-12-31','2026-03-31',remaining);r.dump(O/policy/'results')
  except BaseException:r.run_seconds=time.monotonic()-timer;r.dump(O/policy/'failed-partial');raise
  ends[policy]=pack(r,'2026-03-31');progress.append(dict(policy=policy,seconds=r.run_seconds,end_NAV=str(r.accounts['T3'].current_nav)));M.save(O/'PROGRESS.json',progress);nav=np.array([float(z['nav']) for z in r.daily]);initial=float(states[policy]['account']['current_nav']);dd=1-nav/np.maximum.accumulate(np.r_[initial,nav])[1:];print('Q1_RESULT',policy,dict(return_Q1=float(nav[-1]/initial-1),DD_Q1=float(dd.max()),end_NAV=float(nav[-1]),run_seconds=r.run_seconds,total_seconds=time.monotonic()-timer),flush=True)
 write_checkpoint(O/'end-2026-03-31.chk',ends);M.save(O/'ECONOMIC_DONE.json',dict(passed=True,new_paths=2,quarter='2026Q1',seconds=time.monotonic()-timer,progress=progress,own_boundary_states_preserved=True,no_more_quarters=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
