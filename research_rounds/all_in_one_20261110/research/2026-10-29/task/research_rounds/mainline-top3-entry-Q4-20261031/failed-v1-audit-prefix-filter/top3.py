from pathlib import Path
import sys,importlib.util,pickle,copy,json,gzip,time,hashlib,collections,traceback
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;PREV=W/'mainline-absolute-Q4-20261031'
s=importlib.util.spec_from_file_location('top3_frozen_Q4_engine',PREV/'experiment.py');X=importlib.util.module_from_spec(s);sys.modules[s.name]=X;s.loader.exec_module(X);M=X.M
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def original_seed():
 raw=(PREV/'seed.chk').read_bytes();g=M.read(PREV/'RECOVERY_GATE.json');assert hashlib.sha256(raw).hexdigest()==g['checkpoint_sha256'];v=pickle.loads(raw);assert X.fingerprint(v)==g['fingerprint'];return v
class Pilot(X.Pilot):
 def __init__(self,state,shared,off=False):
  M.Pilot.__init__(self,policies=('T3',),shared=shared)
  for k,v in state['runner'].items():setattr(self,k,copy.deepcopy(v))
  self.b0.__dict__.clear();self.b0.__dict__.update(copy.deepcopy(state['b0']));a=self.accounts['T3'];a.__dict__.clear();a.__dict__.update(copy.deepcopy(state['account']));a.market=self.market;a.facts=self.facts;a.check()
  self.initial_account_fingerprint=X.fingerprint({k:v for k,v in a.__dict__.items() if k not in X.EXCLUDE});assert self.initial_account_fingerprint==M.read(PREV/'GATE.json')['seed_fingerprints']['RAW'];a.label='T3';a.rank_policy='T3'
  self.off=off;self.capacity=[];self.targets=[];self.raw_selection={r['day']:r for r in rows(PREV/'results/selection.jsonl.gz') if r['policy']=='RAW'};self.input_rows=[]
 def industry_target(self,at):
  clock,stocks,sectors=self.facts.packet(at,'I');eligible=[];measure=[]
  for q in sectors:
   up=q.trend_up.read(clock);score=q.rank.read(clock) if q.rank else None;observed=q.trend_up.observed_at;same_day=bool(observed and observed.date()==at.date());qualified=up is True and same_day and score is not None and np.isfinite(score)
   if qualified:eligible.append((q.sector_id,float(score)))
   measure.append(dict(sector=q.sector_id,up=up,score=score,observed_at=observed,qualified=bool(qualified)))
  eligible.sort(key=lambda x:(-x[1],x[0]));return [g for g,_ in eligible[:3]],measure
 def make_lists(self,at):
  day=str(at.date());target,measure=self.industry_target(at);g=self.matrix_days[day];raw=[];available=[];unknown=[]
  for sid in self.market.lines:
   f=self.facts.f[sid];today=pd.Timestamp(day)
   if today not in f.index:continue
   r=f.loc[today]
   if not bool(r.i_buy) or not bool(r.i_target):continue
   raw.append(sid);q=g.loc[self.line_sector[sid]]
   if not np.isfinite(q.H1_original):unknown.append(sid);continue
   available.append(sid)
  maximum=(len(available)+1)//2;ref=self.raw_selection[day];assert raw==[x for x in available]+[x for x in unknown] or len(raw)==len(available)+len(unknown);assert available==ref['candidates'] and maximum==ref['maximum_B']
  ordered=sorted(available,key=lambda sid:(-float(g.loc[self.line_sector[sid],'H1_original']),self.line_sector[sid],self.line_order[sid],sid));pool=ordered if self.off else [sid for sid in ordered if self.line_sector[sid] in target];chosen=pool[:maximum];self.shortlists={'T3':set(chosen)};assert len(chosen)==min(maximum,len(pool)) and len(set(chosen))==len(chosen)
  if self.off:assert chosen==ref['selected']
  else:assert all(self.line_sector[sid] in target for sid in chosen)
  raw_per={sec:sum(self.line_sector[s]==sec for s in available) for sec in target}
  self.targets.append(dict(day=day,targets=target,eligible_industries=sum(q['qualified'] for q in measure),target_rawI=raw_per,target_without_rawI=[s for s in target if not raw_per[s]],industry_inputs=measure))
  self.selection_rows.append(dict(day=day,policy='T3',raw_I_count=len(raw),P_score_known_count=len(available),P_rank_unknown_count=len(unknown),maximum_B=maximum,B=len(chosen),targets=target,target_pool_count=len(pool),candidates=available,selected=chosen,unknown=unknown,attention_at_or_below1_selected=0))
  self.capacity.append(dict(day=day,maximum_B=maximum,actual_selected=len(chosen),shortage=maximum-len(chosen),target_pool_count=len(pool),targets=target))
def main():
 t=time.monotonic();f=M.read(PREV/'FREEZE.json');assert all(M.sha(p)==v for p,v in f['sha256'].items());assert M.read(PREV/'analysis/VERIFICATION.json')['passed'];state=original_seed();X.configure();shared=M.context();off=Pilot(state,shared,True);off.continuation('2025-10-15');old=obj(PREV/'results/RAW.json.gz');until='2025-10-15'
 reference=[r for r in rows(PREV/'results/daily.jsonl.gz') if r['account']=='RAW' and r['at'][:10]<=until];assert X.canon([dict(r,account='RAW') for r in off.daily])==X.canon(reference)
 a=off.accounts['T3'];assert X.canon(a.trades)==X.canon([r for r in old['trades'] if r['at'][:10]<=until]);assert X.canon(a.decisions)==X.canon([r for r in old['decisions'] if r['at'][:10]<=until]);old_audit=[r for r in old['audit'] if (r.get('at') or r.get('receivable',{}).get('ex_at') or '')[:10]<=until];assert X.canon(a.audit_log)==X.canon(old_audit)
 # Only current-dated causal Sector facts enter targets; raw inputs and engine
 # physical prefix already verified by the frozen Q4 implementation.
 assert all(q['observed_at'] is None or q['observed_at'].date().isoformat()<=r['day'] for r in off.targets for q in r['industry_inputs'])
 r=Pilot(state,shared,False);seed_target,_=r.industry_target(M.N.iso('2025-09-30T15:10:00+08:00'));carry=[dict(sid=i['sid'],sector=r.line_sector[i['sid']],outside_hypothetical_9_30_top3=r.line_sector[i['sid']] not in seed_target) for i in r.accounts['T3'].pending]
 M.save(O/'GATE.json',dict(passed=True,prepare_and_off_seconds=time.monotonic()-t,off_daily_trade_audit_decisions_exact=True,off_end=until,initial_account_fingerprint=r.initial_account_fingerprint,reused_original_physical_prefix=str(PREV/'GATE.json'),new_selector_current_causal_Sector_facts_only=True,old_S1_not_equivalent='S1 sector_slots_full caps occupied industries at1 even though daily Top1 can change',carry_in_intents=len(carry),carry_in_outside_hypothetical_9_30_targets=sum(q['outside_hypothetical_9_30_top3'] for q in carry),hypothetical_9_30_targets=seed_target));M.save(O/'CARRY_IN_INTENTS.json',carry)
 files=[O/'PROTOCOL.txt',O/'top3.py',PREV/'FREEZE.json',PREV/'seed.chk',PREV/'recovery.csv',PREV/'results/RAW.json.gz',PREV/'analysis/VERIFICATION.json',M.F,Path(M.BP.A.__file__)];M.save(O/'FREEZE.json',dict(before_one_T3_path=True,K=3,K_not_optimized=True,economic_budget_seconds=60,sha256={str(p):M.sha(p) for p in files}))
 print('GATE_PASSED',time.monotonic()-t,'carry',len(carry),flush=True);begin=time.monotonic()
 try:r.continuation(budget=60);r.dump(O/'results')
 except BaseException:r.run_seconds=time.monotonic()-begin;r.dump(O/'failed-partial');raise
 M.save(O/'TARGETS.json',r.targets);M.save(O/'CAPACITY.json',r.capacity);M.save(O/'ECONOMIC_DONE.json',dict(passed=True,new_paths=1,RAW_baseline_reused=True,seconds=r.run_seconds,wall_with_dump=time.monotonic()-begin,seed_NAV=str(state['account']['current_nav'])));nav=np.array([float(x['nav']) for x in r.daily]);seed=float(state['account']['current_nav']);dd=1-nav/np.maximum.accumulate(np.r_[seed,nav])[1:];print('T3_RESULT',dict(return_Q4=float(nav[-1]/seed-1),DD_Q4=float(dd.max()),end_NAV=nav[-1],seconds=r.run_seconds),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
