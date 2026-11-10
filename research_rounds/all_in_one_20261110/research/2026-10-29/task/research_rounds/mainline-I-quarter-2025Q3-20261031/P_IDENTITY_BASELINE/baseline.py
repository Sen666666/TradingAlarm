from pathlib import Path
import sys,importlib.util,time,json,gzip,collections,traceback
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;OLD=O.parent
s=importlib.util.spec_from_file_location('mainline_quarter_frozen',OLD/'adapter.py');M=importlib.util.module_from_spec(s);sys.modules[s.name]=M;s.loader.exec_module(M)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
class Pilot(M.Pilot):
 def __init__(self):
  super().__init__(policies=('NO_P',));self.frozen={x['day']:x for x in rows(OLD/'results/selection.jsonl.gz') if x['policy']=='H1'};self.cap_rows=[]
 def make_lists(self,at):
  day=str(at.date());g=self.matrix_days[day];raw=[];available=[];unknown=[];p_set=[]
  for sid in self.market.lines:
   f=self.facts.f[sid];today=pd.Timestamp(day)
   if today not in f.index:continue
   r=f.loc[today]
   if not bool(r.i_buy) or not bool(r.i_target):continue
   raw.append(sid);q=g.loc[self.line_sector[sid]]
   if not np.isfinite(q.H1_original) or not np.isfinite(q.attention_ratio):unknown.append(sid);continue
   available.append(sid)
   if bool(q.price_qualified):p_set.append(sid)
  old=self.frozen[day];assert raw==[sid for sid in self.market.lines if pd.Timestamp(day) in self.facts.f[sid].index and bool(self.facts.f[sid].loc[pd.Timestamp(day),'i_buy']) and bool(self.facts.f[sid].loc[pd.Timestamp(day),'i_target'])];assert p_set==old['candidates'];assert len(raw)==old['raw_I_count']
  b=old['B'];ordered=sorted(available,key=lambda sid:(-float(g.loc[self.line_sector[sid],'H1_original']),self.line_sector[sid],self.line_order[sid],sid));take=min(b,len(ordered));chosen=ordered[:take]
  assert len(set(chosen))==take;self.shortlists={'NO_P':set(chosen)}
  self.cap_rows.append(dict(day=day,frozen_B=b,actual_B=take,available_all_I=len(available),raw_I=len(raw),rank_unknown=len(unknown),P_candidate_count=len(p_set),selected_outside_P=sum(s not in p_set for s in chosen),selected_same_as_P=len(set(chosen)&set(old['selected'])),shortage=b-take))
  self.selection_rows.append(dict(day=day,policy='NO_P',raw_I_count=len(raw),P_score_known_count=len(p_set),P_rank_unknown_count=sum(s in old['unknown'] for s in unknown),B=take,frozen_B=b,candidates=available,selected=chosen,unknown=unknown,attention_at_or_below1_selected=sum(float(g.loc[self.line_sector[s],'attention_ratio'])<=1 for s in chosen)))
def main():
 prep=time.monotonic();f=M.read(OLD/'FREEZE.json');assert all(M.sha(p)==v for p,v in f['sha256'].items());assert M.read(OLD/'analysis/VERIFICATION.json')['passed'];r=Pilot()
 # All 66 lists checked without reading any future outcomes or state changes.
 for day in r.frozen:r.make_lists(M.N.iso(day+'T15:10:00+08:00'))
 gate=dict(passed=True,days=len(r.cap_rows),P_identity_and_original_rawI_exact=True,B_frozen_from_existing_P_arm=True,source_planning_ledger_unchanged=True,rank_unknown_stock_days=sum(x['rank_unknown'] for x in r.cap_rows),shortage_stock_days=sum(x['shortage'] for x in r.cap_rows),NO_P_selected_outside_P_stock_days=sum(x['selected_outside_P'] for x in r.cap_rows),P_selected_overlap_stock_days=sum(x['selected_same_as_P'] for x in r.cap_rows),prepare_seconds=time.monotonic()-prep)
 M.save(O/'GATE.json',gate);M.save(O/'LIST_GATE.json',r.cap_rows);r.cap_rows=[];r.selection_rows=[]
 files=[O/'PROTOCOL.txt',O/'baseline.py',OLD/'FREEZE.json',OLD/'analysis/VERIFICATION.json',OLD/'results/selection.jsonl.gz',OLD/'recovery.csv',OLD/'adapter.py'];M.save(O/'FREEZE.json',dict(before_unique_new_economic_path=True,paths=['NO_P'],budget_seconds=60,sha256={str(p):M.sha(p) for p in files}))
 print('GATE',json.dumps(gate,ensure_ascii=False),flush=True)
 t=time.monotonic()
 try:r.run(max_seconds=60);r.dump(O/'results')
 except BaseException:
  r.run_seconds=time.monotonic()-t;r.dump(O/'failed-partial');raise
 M.save(O/'ECONOMIC_DONE.json',dict(passed=True,new_paths=1,old_paths_reused=2,seconds=r.run_seconds,wall_with_dump=time.monotonic()-t));M.save(O/'CAP_DAYS.json',r.cap_rows)
 ds=r.daily;nav=np.array([float(x['nav']) for x in ds]);dd=1-nav/np.maximum.accumulate(np.r_[1e6,nav])[1:]
 print('RESULT_NO_P',dict(net_return=float(nav[-1]/1e6-1),max_drawdown=float(dd.max()),final_nav=str(ds[-1]['nav']),seconds=r.run_seconds),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
