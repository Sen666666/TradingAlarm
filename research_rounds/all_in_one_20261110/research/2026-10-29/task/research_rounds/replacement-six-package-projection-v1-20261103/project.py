"""Fixed six-package, bounded original-order repair; no account progression."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,copy,hashlib,ast,time,traceback,collections,argparse
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O));import extract as X
from matching import witness,relation
B=X.B;J=X.J

def native_eval(s,ds,Q,dm,book):
 r=B.evaluate(s,ds,Q,dm)
 if book is not None:
  a=book.preview({str(p['layer']):p['q'] for p in r['donors']['rows']});r['batch20']=a
  r['validation']['checks'].append(dict(stage='full_batch_D',constraint='opportunity_gross_batch20',value=str(D(a['carry'])+D(a['already_new'])+D(a['additional'])),limit=a['limit'],residual=a['residual']))
  if not a['ok']:r['validation']['ok']=False;r['validation']['violations'].append('opportunity_gross_batch20')
 return r

def solve(x,mode):
 started=time.perf_counter();originalQ=x['certificate']['Q'];originalD=x['original_D'];s=x['snapshot'];ordered=sorted(x['demands'],key=lambda d:(d['priority'],d['sid']))
 before=J.digest(x);book=X.budget_book(x) if x['old_budget_mode']=='C_BATCH20' else None;book_before=book.dumps() if book else None
 original=native_eval(s,ordered,originalQ,originalD,book)
 initial_ok,initial_w=witness(J,s,ordered,originalQ,original['donors'],original['validation'],x['scores'],mode,True)
 if initial_ok:
  return dict(mode=mode,preserved_original_full_plan=True,Q=originalQ,D=originalD,native=original,matching=initial_w,
   seconds=time.perf_counter()-started,financial_events=0,selector_search_needed=False)
 # Same fixed iteration code in an isolated namespace. Originals remain intact.
 tree=ast.parse(Path(B.__file__).read_text());ns=dict(B.__dict__)
 defs=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[])
 exec(compile(ast.fix_missing_locations(defs),str(O/'project.py')+'::frozen_original_loop', 'exec'),ns)
 ss=copy.deepcopy(s);ds=copy.deepcopy([d for d in ordered if originalQ.get(d['sid'],0)])
 limits={str(p['layer']):p['q'] for p in x['original_D_parts']}
 for z in ss['lots']:
  # Resource rows are NOT changed or removed. Only legal supplier domain shrinks.
  z['B_donor_eligible']=bool(z.get('B_donor_eligible') and str(z['id']) in limits and any(relation(x['scores'][z['sid']],x['scores'][d['sid']],mode) is True for d in ds))
 for d in ds:d['max_q']=min(d['max_q'],originalQ[d['sid']])
 calls=0;native_reject=collections.Counter();matching_reject=collections.Counter();first_failure={}
 def evaluate(s0,d0,Q,dm):
  nonlocal calls
  calls+=1
  if any(q>originalD.get(sid,0) for sid,q in dm.items()):raise ValueError('original D stock upper exceeded')
  r=native_eval(s0,d0,Q,dm,book)
  if any(p['q']>limits.get(str(p['layer']),0) for p in r['donors']['rows']):raise ValueError('original D layer upper exceeded')
  if not r['validation']['ok']:native_reject.update(r['validation']['violations']);return r
  ok,w=witness(J,s0,d0,Q,r['donors'],r['validation'],x['scores'],mode,False)
  if not ok:
   why=w['why'];matching_reject[why]+=1;first_failure.setdefault(why,w)
   r['validation']['ok']=False;r['validation']['violations'].append(why)
  return r
 original_sell=ns['sell_totals'];original_upper=ns['necessary_upper']
 def bounded_sell(lots,already,whole):return [q for q in original_sell(lots,already,whole) if q<=originalD.get(lots[0]['sid'],0)]
 def bounded_upper(s0,d0,Q,d,plan):
  if book is not None and not book.preview({str(p['layer']):p['q'] for p in plan['rows']})['ok']:return 0,['opportunity_gross_batch20']
  return original_upper(s0,d0,Q,d,plan)
 ns['evaluate']=evaluate;ns['sell_totals']=bounded_sell;ns['necessary_upper']=bounded_upper
 def progress(tr):
  X.save(O/'PROGRESS.json',dict(case=x['case'],arm=x['arm'],day=x['day'],mode=mode,last_sid=tr['sid'],q=tr['q'],pure_evaluations=calls,seconds=time.perf_counter()-started,financial_events=0))
  print('PREFIX',x['arm'],x['day'],mode,tr['sid'],tr['q'],'calls',calls,'seconds',round(time.perf_counter()-started,2),flush=True)
 result=ns['solve_B'](ss,ds,max_native_checks=250000,progress=progress)
 # Complete original positive/zero universe retained for clear denominator.
 Q={sid:result['Q'].get(sid,0) for sid in originalQ};dm=result['D']
 native=native_eval(s,ordered,Q,dm,book)
 assert native['validation']['ok']
 assert all(Q[s]<=originalQ[s] for s in originalQ) and all(dm[s]<=originalD[s] for s in dm)
 assert all(p['q']<=limits[str(p['layer'])] for p in native['donors']['rows'])
 ok,w=witness(J,s,ordered,Q,native['donors'],native['validation'],x['scores'],mode,True)
 assert ok,('final full snapshot resource witness failed',w)
 assert J.digest(x)==before and (book is None or book.dumps()==book_before)
 return dict(mode=mode,preserved_original_full_plan=False,Q=Q,D=dm,native=native,matching=w,initial_original_plan_failure=initial_w,
  trace=result['trace'],pure_evaluations=calls,native_checks=result['native_checks'],donor_views=result['donor_views'],
  native_failure_occurrences=dict(native_reject),matching_failure_occurrences=dict(matching_reject),first_matching_failures=first_failure,
  original_ordered_positive_Q=[d['sid'] for d in ds],D_stock_upper=originalD,D_layer_upper=limits,
  patched_original_functions=['evaluate (matching predicate)','sell_totals (original D bound)','necessary_upper (unchanged native bound plus existing C20 predicate)'],
  loop_source_sha256=hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest(),original_loop_AST=ast.dump(defs,include_attributes=False),
  seconds=time.perf_counter()-started,financial_events=0,selector_search_needed=True,analysis_only=True,submit_allowed=False)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case');ap.add_argument('--mode',choices=['HARD','WEAK']);a=ap.parse_args()
 freeze=X.read(O/'CONTRACT_FREEZE.json');assert X.sha(O/'CONTRACT.txt')==freeze['contract_sha256'];assert X.sha(O/'matching.py')==freeze['matching_source_sha256'];assert X.read(O/'PREFLIGHT.json')['passed']
 m=X.read(O/'INPUT_MANIFEST.json')
 for c in m['cases']:
  label=c['arm']+'-'+c['day']
  if a.case and label!=a.case:continue
  p=O/c['input'];assert X.sha(p)==m['inputs_sha256'][c['input']];x=X.read(p)
  for mode in [a.mode] if a.mode else ['HARD','WEAK']:
   out=O/(mode+'-'+label+'.json')
   if out.exists():
    old=X.read(out);assert old['contract_sha256']==freeze['contract_sha256'] and old['source_sha256']==X.sha(__file__);print('EXISTING_COMPLETE_NO_RERUN',out.name,flush=True);continue
   r=solve(x,mode);r.update(contract_sha256=freeze['contract_sha256'],source_sha256=X.sha(__file__),input_sha256=X.sha(p),case=x['case'],arm=x['arm'],day=x['day'])
   X.save(out,r);print('COMPLETE',mode,label,'Q/D',sum(q>0 for q in r['Q'].values()),len(r['D']),'seconds',round(r['seconds'],2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:X.save(O/'PROJECTION_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
