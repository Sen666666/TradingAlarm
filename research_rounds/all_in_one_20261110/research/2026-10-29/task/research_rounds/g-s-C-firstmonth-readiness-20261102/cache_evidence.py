"""Pure saved-input equality/timing probe. Does NOT install a runtime cache."""
from pathlib import Path
import sys,pickle,copy,time,json
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-nextsession-native-20261102'));import c_horizon as C
E=C.E
def main():
 C.guard();rows=[]
 for rec in C.read(C.HERE/'CONTINUATION_CHECKPOINTS.json'):
  p=Path(rec['path']);assert C.P.sha(p)==rec['sha256']
  with p.open('rb') as f:r=pickle.load(f)
  cert=r.active;v=r.trusted[cert['trusted_id']];body=dict(snapshot=v['snapshot'],demands=v['demands'],evidence=v['evidence'],budget_before=v['budget_before'],mode=r.mode,sources=r.source_binding())
  key=E.digest(body);finance=E.digest(r.account.exported(r.last_completed_event));before=E.digest(v)
  samples=[];answers=[]
  for _ in range(2):
   t=time.perf_counter();answer=r._solve(v['snapshot'],v['demands'],v['evidence'],v['budget_before']);samples.append(time.perf_counter()-t);answers.append(answer)
  assert E.digest(answers[0])==E.digest(answers[1])==cert['projection_hash']
  t=time.perf_counter();cached_candidate=copy.deepcopy(answers[0]);copy_seconds=time.perf_counter()-t
  assert json.loads(json.dumps(cached_candidate,default=E.encode))==json.loads(json.dumps(answers[1],default=E.encode))
  changed={}
  for axis in ('snapshot','receipt','budget','mode','source'):
   b=copy.deepcopy(body)
   if axis=='snapshot':b['snapshot']['available']+=1
   elif axis=='receipt':b['demands'][0]['receipt_id']+='|DIAGNOSTIC_ONLY'
   elif axis=='budget':b['budget_before']+=' '
   elif axis=='mode':b['mode']='OTHER_MODE_DIAGNOSTIC'
   else:b['sources'][next(iter(b['sources']))]='0'*64
   changed[axis]=E.digest(b)!=key
  assert all(changed.values()) and E.digest(v)==before and E.digest(r.account.exported(r.last_completed_event))==finance
  rows.append(dict(window=rec['window'],mode=rec['mode'],demands=len(v['demands']),donor_lots=len(v['snapshot']['lots']),native_checks_per_solve=answers[0]['native_checks'],pure_solve_seconds=samples,deepcopy_candidate_seconds=copy_seconds,full_result_all_fields_exact=True,actual_cached_runtime_installed=False,key_invalidations=changed,financial_state_unchanged=True))
  print(rec['window'],rec['mode'],samples,flush=True)
 E.IO.write_json(HERE/'CACHE_EVIDENCE.json',dict(rows=rows,scope='4 saved immutable projections, each twice; not new policy outcomes or account replay',financial_events=0,no_runtime_code_change=True,cannot_cache=['live native resource/price/fee/quantity preview','settlement or cancel/fill callbacks','new close snapshot or changed canonical receipt or budget/carry','original source/mode identity guards']),encoder=E.encode)
if __name__=='__main__':main()
