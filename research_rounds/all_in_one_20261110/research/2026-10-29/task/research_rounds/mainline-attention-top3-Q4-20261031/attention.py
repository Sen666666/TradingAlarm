from pathlib import Path
import sys,importlib.util,inspect,time,json,gzip,traceback
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;HT=W/'mainline-top3-entry-Q4-20261031'
s=importlib.util.spec_from_file_location('attention_frozen_top3',HT/'top3.py');T=importlib.util.module_from_spec(s);sys.modules[s.name]=T;s.loader.exec_module(T);X,M=T.X,T.M
# Exact same candidate/sizing/held/epoch/ledger code. Only industry sort key
# changes when the new rank is on; off is the existing H1 Top3 policy.
src=inspect.getsource(T.Pilot.make_lists).strip();needle="-float(g.loc[self.line_sector[sid],'H1_original'])";assert src.count(needle)==1
src=src.replace(needle,"-float(g.loc[self.line_sector[sid], 'attention_ratio' if self.rank_enabled else 'H1_original'])");env=dict(T.__dict__);exec(src,env);ranked_lists=env['make_lists']
class Pilot(T.Pilot):
 def __init__(self,state,shared,rank_enabled=True):super().__init__(state,shared,off=False);self.rank_enabled=rank_enabled
 make_lists=ranked_lists
 def industry_target(self,at):
  clock,stocks,sectors=self.facts.packet(at,'I');g=self.matrix_days[str(at.date())];eligible=[];measure=[];missing=[]
  for q in sectors:
   up=q.trend_up.read(clock);h=q.rank.read(clock) if q.rank else None;observed=q.trend_up.observed_at;same=bool(observed and observed.date()==at.date());base=up is True and same and h is not None and np.isfinite(h);r=g.loc[q.sector_id];a=float(r.attention_ratio);known=np.isfinite(a)
   if base and not known:missing.append(q.sector_id)
   qualified=bool(base and known);score=a if self.rank_enabled else h
   if qualified:eligible.append((q.sector_id,float(score)))
   measure.append(dict(sector=q.sector_id,up=up,score=score,H1_score=h,attention_ratio=a,observed_at=observed,qualified=qualified,original_qualified=bool(base),effective_members=int(r.attention_members),snapshot_members=int(r.member_count),R21=float(r.R21)))
  assert not missing,('rank eligibility comparability changed',str(at),missing)
  eligible.sort(key=lambda x:(-x[1],x[0]));return [sec for sec,_ in eligible[:3]],measure
def main():
 t=time.monotonic();f=M.read(HT/'FREEZE.json');assert all(M.sha(p)==h for p,h in f['sha256'].items());assert M.read(HT/'analysis/VERIFICATION.json')['passed'];state=T.original_seed();X.configure();shared=M.context();off=Pilot(state,shared,False);off.continuation('2025-10-15');old=T.obj(HT/'results/T3.json.gz');until='2025-10-15';ref=[r for r in T.rows(HT/'results/daily.jsonl.gz') if r['at'][:10]<=until];a=off.accounts['T3'];assert X.canon(off.daily)==X.canon(ref);assert X.canon(a.trades)==X.canon([r for r in old['trades'] if r['at'][:10]<=until]);assert X.canon(a.decisions)==X.canon([r for r in old['decisions'] if r['at'][:10]<=until]);ad=[r for r in old['audit'] if (r.get('at') or r.get('receipt',{}).get('at') or r.get('receivable',{}).get('ex_at') or '')[:10]<=until];assert X.canon(a.audit_log)==X.canon(ad)
  # Full-quarter preflight reads no future profit: shared eligibility mask and
  # the common-mask H1 targets must remain identical to frozen old H1 targets.
 matrix=pd.read_parquet(M.F);matrix=matrix[matrix.quarter.eq('2025Q4')];all_known=bool(np.isfinite(matrix.attention_ratio).all());assert all_known
 targets=M.read(HT/'TARGETS.json');lookup={r['day']:set(r['targets']) for r in targets};qualified_cells=0
 for day,g in matrix.groupby('day'):
  known={q['sector']:q for q in next(r for r in targets if r['day']==day)['industry_inputs']};valid=[q for q in known.values() if q['qualified'] and np.isfinite(float(g.set_index('sector').loc[q['sector'],'attention_ratio']))];qualified_cells+=len(valid);ranked=sorted(valid,key=lambda q:(-float(q['score']),q['sector']));assert set(q['sector'] for q in ranked[:3])==lookup[day]
 r=Pilot(state,shared,True);carrytargets,_=r.industry_target(M.N.iso('2025-09-30T15:10:00+08:00'));carry=r.accounts['T3'].pending
 M.save(O/'GATE.json',dict(passed=True,seconds=time.monotonic()-t,off_H1_Top3_daily_trade_decision_audit_exact=True,off_end=until,shared_rank_eligibility_cells=qualified_cells,attention_unknown_all_Q4_industry_cells=0,old_H1_targets_exact_after_common_mask=True,initial_state_fingerprint=r.initial_account_fingerprint,original_engine_physical_prefix_reused=str(T.PREV/'GATE.json'),new_ranking_current_Sector_and_frozen_attention_only=True,carry_in_intents=len(carry),carry_in_outside_hypothetical_9_30_attention_targets=sum(r.line_sector[i['sid']] not in carrytargets for i in carry)))
 files=[O/'PROTOCOL.txt',O/'attention.py',HT/'top3.py',HT/'FREEZE.json',HT/'results/T3.json.gz',T.PREV/'results/RAW.json.gz',T.PREV/'seed.chk',T.PREV/'recovery.csv',M.F,M.F.parent/'FEATURE_FREEZE.json'];M.save(O/'FREEZE.json',dict(before_single_attention_path=True,K=3,attention_now_main_industry_rank=True,only_ranking_changed=True,budget_seconds=60,sha256={str(p):M.sha(p) for p in files},candidate_rank_source_replacement=src))
 print('GATE_PASSED',time.monotonic()-t,'qualified',qualified_cells,flush=True);start=time.monotonic()
 try:r.continuation(budget=60);r.dump(O/'results')
 except BaseException:r.run_seconds=time.monotonic()-start;r.dump(O/'failed-partial');raise
 M.save(O/'TARGETS.json',r.targets);M.save(O/'CAPACITY.json',r.capacity);M.save(O/'ECONOMIC_DONE.json',dict(passed=True,new_paths=1,RAW_and_H1Top3_reused=True,seconds=r.run_seconds,wall_with_dump=time.monotonic()-start,seed_NAV=str(state['account']['current_nav'])));nav=np.array([float(v['nav']) for v in r.daily]);seed=float(state['account']['current_nav']);dd=1-nav/np.maximum.accumulate(np.r_[seed,nav])[1:];print('ATT_TOP3_RESULT',dict(Q4_return=float(nav[-1]/seed-1),DD=float(dd.max()),end_NAV=float(nav[-1]),seconds=r.run_seconds),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
