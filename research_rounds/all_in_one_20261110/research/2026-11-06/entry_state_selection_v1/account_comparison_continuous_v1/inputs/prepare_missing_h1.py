"""Only missing 2025H1 native receipt/PVR export; never account execution."""
from pathlib import Path
import ast,collections,hashlib,json,math,time
from concurrent.futures import ProcessPoolExecutor
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
U=W/'universe-cp1-inputs-20261031'
D=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full')
P=W/'pvr-slot1-native-readiness-20261101'
TRACE=W/'cp1-evidence-trace-20261031/trace.py'
FORMULA=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
MODEL=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
BEGIN,END,CUT='2025-01-01','2025-06-30','2025-03-31'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2,allow_nan=False));tmp.replace(p)
def setup():
 assert sha(FORMULA)=='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
 nodes=[n for n in ast.parse(TRACE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'ident','norm','trace'}]
 env=dict(np=np,pd=pd,math=math,json=json,hashlib=hashlib,collections=collections,SCALE='CP1-original:'+sha(MODEL)[:16],BEGIN=BEGIN,END=END)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(TRACE),'exec'),env)
 scoreenv=dict(np=np,pd=pd);exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),scoreenv)
 tree=ast.parse((W/'2022-normal-reference-20261031/export_receipts.py').read_text())
 keys=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(k,ast.Name) and k.id=='KEYS' for k in n.targets)))
 return env['trace'],scoreenv['score'],keys

def one(r):
 sid=r.get('symbol',r.get('series'));industry='series'in r
 path=O/'items'/f'{sid}.json'
 if path.exists():
  m=read(path);assert m['input_identity']==r['output_sha256']
  assert sha(m['receipt_path'])==m['receipt_sha256']
  if not industry:assert sha(m['score_path'])==m['score_sha256']
  return m
 trace,score,keys=setup()
 for p,h in {**r['source_sha256'],**r['output_sha256']}.items():assert sha(p)==h,(sid,p)
 q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];z=pd.read_parquet(r['refs']['CP1']).loc[:END]
 episode=q.e0_valid if industry else pd.read_parquet(r['refs']['facts'],columns=['e0_target']).e0_target.reindex(q.index).astype(bool)
 eventpath=next(p for p in r['source_sha256'] if p.endswith('/events.parquet'));events=pd.read_parquet(eventpath).reindex(q.index)
 rr,_,_=trace(sid,q,z,events,episode);compact=lambda rows:[{k:x[k] for k in keys} for x in rows]
 expected=z.loc[BEGIN:END];assert [x['confirmed_day']for x in rr]==[str(t.date())for t in expected.index[expected.receipt.eq(True)]]
 assert not any(x['trace_unknown']for x in rr);assert len({x['receipt_id']for x in rr})==len(rr)
 small,_,_=trace(sid,q.loc[:CUT],z.loc[:CUT],events.loc[:CUT],episode.loc[:CUT]);assert compact(small)==compact([x for x in rr if x['confirmed_day']<=CUT])
 if industry:
  states=pd.read_parquet(r['refs']['state']);by={x['day']:x for x in states.to_dict('records')};assert all(by[x['confirmed_day']]['receipt_id']==x['receipt_id']for x in rr)
 out=O/'receipts'/f'{sid}.json';save(out,compact(rr))
 m=dict(sid=sid,industry=industry,input_identity=r['output_sha256'],source_identity=r['source_sha256'],receipt_path=str(out),receipt_sha256=sha(out),receipt_count=len(rr),prefix_exact=True,trace_unknown=0,CP1_recomputed=False)
 if not industry:
  src=Path(next(p for p in r['source_sha256'] if p.endswith('/signal.parquet')));f=pd.read_parquet(src).loc[:END];v=score(f)
  oldmeta=next(x for x in read(D/'SCORES_MANIFEST.json')['entries'] if x['symbol']==sid);oldpath=D/'scores'/f'{sid}.parquet';assert sha(oldpath)==oldmeta['output_sha256'];old=pd.read_parquet(oldpath)
  pd.testing.assert_frame_equal(v[['score']].reindex(old.index),old,check_exact=True,check_freq=False)
  pd.testing.assert_frame_equal(score(f.loc[:CUT]),v.loc[:CUT],check_exact=True,check_freq=False)
  hd=pd.DatetimeIndex(np.load(H1)['dates']);dates=hd[(hd>=BEGIN)&(hd<=END)];assert len(dates)==117
  keep=v[['score']].reindex(dates);keep.index.name='day';sp=O/'scores'/f'{sid}.parquet';sp.parent.mkdir(parents=True,exist_ok=True);keep.to_parquet(sp)
  m.update(score_path=str(sp),score_sha256=sha(sp),score_rows=len(keep),score_NA=int(keep.score.isna().sum()),historical_726_score_cells_exact=True,original_PVR_formula_executed=True)
 save(path,m);return m

def main():
 start=time.monotonic();sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json');assert len(sm)==1709 and len(im)==90
 sources=[Path(__file__),TRACE,FORMULA,MODEL,H1,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',U/'FREEZE.json',D/'SCORES_MANIFEST.json',P/'SCORES_MANIFEST.json']
 freeze={str(p):sha(p)for p in sources}
 if (O/'SOURCE_FREEZE.json').exists():assert read(O/'SOURCE_FREEZE.json')==freeze
 else:save(O/'SOURCE_FREEZE.json',freeze)
 rows=[]
 with ProcessPoolExecutor(max_workers=4)as pool:
  for r in pool.map(one,sm+im,chunksize=4):
   rows.append(r)
   if len(rows)%100==0:print('export',len(rows),round(time.monotonic()-start,1),flush=True)
 assert sum(r['receipt_count']for r in rows if not r['industry'])==9507
 assert sum(r['receipt_count']for r in rows if r['industry'])==708
 assert all(sha(p)==h for p,h in freeze.items())
 save(O/'H1_MANIFEST.json',rows)
 save(O/'COMPLETION.json',dict(status='PASS_MISSING_2025H1_EXPORT',stocks=1709,industries=90,stock_receipts=9507,industry_receipts=708,score_cells=1709*117,score_NA=sum(r.get('score_NA',0)for r in rows),original_I_CP1_stage_recomputations=0,original_PVR_formula_executions=1709,account_events=0,seconds=time.monotonic()-start,manifest_sha256=sha(O/'H1_MANIFEST.json')))
 print(read(O/'COMPLETION.json'),flush=True)
if __name__=='__main__':main()
