"""Frozen2024 input export: original pure trace/PVR only, zero account events."""
from pathlib import Path
import ast, collections, hashlib, json, math, time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
P=W/'pvr-slot1-native-readiness-20261101';H=P/'continuation-2023-readiness';U=W/'universe-cp1-inputs-20261031'
TRACE=W/'cp1-evidence-trace-20261031/trace.py'
FORMULA=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
MODEL=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
BEGIN,END,CUT='2024-01-01','2024-12-31','2024-06-28'

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
 t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)
def calendar(m,y):
 v=m['decision_calendars'][y];return v['dates'] if isinstance(v,dict) else v

def main():
 started=time.monotonic();sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json')
 oldm=read(H/'SCORES_MANIFEST.json');oldscore={x['symbol']:x for x in oldm['entries']}
 assert len(sm)==1709 and len(im)==90 and oldm['fixed_stock_ids']==[r['symbol'] for r in sm]
 h=np.load(H1);hd=pd.DatetimeIndex(h['dates']);days24=[str(x.date()) for x in hd[(hd>=BEGIN)&(hd<=END)]]
 cals={'2022':calendar(oldm,'2022'),'2023':calendar(oldm,'2023'),'2024':days24}
 assert all(len(x)==242 for x in cals.values())
 dates=pd.DatetimeIndex(sum(cals.values(),[]),name='day');assert dates.is_unique and len(dates)==726
 controls={y:{r['sid']:r for r in read(root/'inputs/MANIFEST.json')} for y,root in
           [('2022',W/'2022-normal-reference-20261031'),('2023',W/'recovery-2023-readiness-20261101')]}
 paths=[Path(__file__),TRACE,FORMULA,MODEL,H1,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',U/'FREEZE.json',
        H/'SCORES_MANIFEST.json',W/'2022-normal-reference-20261031/inputs/MANIFEST.json',
        W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',W/'2022-normal-reference-20261031/export_receipts.py',
        W/'mainline-absolute-Q4-20261031/recovery.csv']
 freeze=dict(scope='2024_full_data_only',account_events=0,numeric_I_CP1_stage_calculations=0,
             window=[BEGIN,END],prefix_cut=CUT,fixed_stock_ids=oldm['fixed_stock_ids'],
             industries=[r['series'] for r in im],sources={str(p):sha(p) for p in paths})
 if (O/'SOURCE_FREEZE.json').exists():assert read(O/'SOURCE_FREEZE.json')==freeze
 else:save(O/'SOURCE_FREEZE.json',freeze)
 assert sha(FORMULA)==oldm['formula_sha256']=='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
 env=dict(np=np,pd=pd);exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),env);score=env['score']
 nodes=[n for n in ast.parse(TRACE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'ident','norm','trace'}]
 assert {n.name for n in nodes}=={'ident','norm','trace'}
 tenv=dict(np=np,pd=pd,math=math,json=json,hashlib=hashlib,collections=collections,
           SCALE='CP1-original:'+sha(MODEL)[:16],BEGIN='2022-01-01',END=END)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(TRACE),'exec'),tenv)
 kn=next(n for n in ast.parse(paths[-2].read_text()).body if isinstance(n,ast.Assign)
         and any(isinstance(k,ast.Name) and k.id=='KEYS' for k in n.targets))
 keys=ast.literal_eval(kn.value);compact=lambda rr:[{k:r[k] for k in keys} for r in rr]
 samples=set([r['symbol'] for r in sm[:3]]+[r['series'] for r in im[:3]])
 canonical=[];score_rows=[];reused=0
 for i,r in enumerate(sm+im,1):
  industry='series'in r;sid=r['series' if industry else 'symbol'];item=O/'items'/(sid+'.json')
  if item.exists():
   m=read(item)
   assert m['source_freeze_sha256']==sha(O/'SOURCE_FREEZE.json')
   assert m['original_output_sha256']==r['output_sha256']
   assert sha(m['output_path'])==m['output_sha256']
   if not industry:assert sha(O/'scores'/(sid+'.parquet'))==m['score']['output_sha256']
   reused+=1
  else:
   for path,expected in {**r['source_sha256'],**r['output_sha256']}.items():assert sha(path)==expected,(sid,path)
   q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];z=pd.read_parquet(r['refs']['CP1']).loc[:END]
   assert q.index.equals(z.index)
   episode=q.e0_valid if industry else pd.read_parquet(r['refs']['facts'],columns=['e0_target']).e0_target.reindex(q.index).astype(bool)
   eventpath=next(p for p in r['source_sha256'] if p.endswith('/events.parquet'))
   events=pd.read_parquet(eventpath).reindex(q.index)
   rr,_,_=tenv['trace'](sid,q,z,events,episode)
   assert not any(x['trace_unknown'] for x in rr),(sid,'unknown canonical origin')
   new=[x for x in rr if BEGIN<=x['confirmed_day']<=END]
   assert [x['confirmed_day']for x in new]==[str(d.date())for d in z.loc[BEGIN:END].index[z.loc[BEGIN:END].receipt.eq(True)]]
   assert len({x['receipt_id']for x in new})==len(new)
   for y in ['2022','2023']:
    ctrl=controls[y][sid];assert ctrl['original_output_sha256']==r['output_sha256']
    assert sha(ctrl['output_path'])==ctrl['output_sha256']
    assert compact([x for x in rr if x['confirmed_day'].startswith(y)])==read(ctrl['output_path']),(sid,y,'old canonical body changed')
   small,_,_=tenv['trace'](sid,q.loc[:CUT],z.loc[:CUT],events.loc[:CUT],episode.loc[:CUT])
   assert compact(small)==compact([x for x in rr if x['confirmed_day']<=CUT]),(sid,'physical canonical prefix')
   if industry:
    state=pd.read_parquet(r['refs']['state']);by={x['day']:x for x in state.to_dict('records')}
    assert all(by[x['confirmed_day']]['receipt_id']==x['receipt_id']for x in new)
   out=O/'inputs'/('industry-receipts'if industry else'stock-receipts')/(sid+'.json');save(out,compact(new))
   m=dict(sid=sid,industry=industry,refs=r['refs'],source_freeze_sha256=sha(O/'SOURCE_FREEZE.json'),
          sources=r['source_sha256'],original_output_sha256=r['output_sha256'],output_path=str(out),
          output_sha256=sha(out),receipt_count=len(new),checks=dict(original_numeric_receipt_dates_exact=True,
          trace_unknown=0,canonical_unique=True,old2022_2023_complete_body_exact=True,
          physical_June28_complete_body_prefix_exact=True,industry_state_receipt_ID_exact=industry))
   if not industry:
    sr=oldscore[sid];src=Path(sr['source']);assert sha(src)==sr['source_sha256']
    oldpath=H/'scores'/(sid+'.parquet');assert sha(oldpath)==sr['output_sha256']
    f=pd.read_parquet(src).loc[:END];v=score(f);past=pd.read_parquet(oldpath)
    pd.testing.assert_frame_equal(v[['score']].reindex(past.index),past,check_exact=True,check_freq=False)
    pd.testing.assert_frame_equal(score(f.loc[:CUT]),v.loc[:CUT],check_exact=True,check_freq=False)
    if sid in samples:
     altered=f.copy();altered.loc[altered.index>CUT,'close']*=7;altered.loc[altered.index>CUT,'amount']*=.013
     pd.testing.assert_frame_equal(score(altered).loc[:CUT],v.loc[:CUT],check_exact=True,check_freq=False)
    keep=v[['score']].reindex(dates);sp=O/'scores'/(sid+'.parquet');sp.parent.mkdir(exist_ok=True)
    tmp=sp.with_name(sp.name+'.tmp');keep.to_parquet(tmp);tmp.replace(sp)
    m['score']=dict(symbol=sid,source=str(src),source_sha256=sha(src),formula_sha256=sha(FORMULA),
      output_sha256=sha(sp),input_cutoff=END,full_warm_start=str(f.index.min())if len(f)else None,
      output_rows=len(keep),ready_2024=int(keep.loc[days24].score.notna().sum()),NA_2024=int(keep.loc[days24].score.isna().sum()),
      old2022_2023_score_cells_exact=len(past),physical_June28_all_original_fields_exact=True,
      future_poison_prefix_exact=True if sid in samples else None,old_score_file_sha256=sha(oldpath))
   save(item,m)
  canonical.append({k:v for k,v in m.items()if k!='score'})
  if not industry:score_rows.append(m['score'])
  if i%100==0:
   save(O/'PROGRESS.json',dict(series=i,total=1799,reused=reused,seconds=time.monotonic()-started));print('DATA2024',i,'/1799',round(time.monotonic()-started,2),flush=True)
 assert len(canonical)==1799 and len(score_rows)==1709
 assert sum(x['receipt_count']for x in canonical if not x['industry'])==25251
 assert sum(x['receipt_count']for x in canonical if x['industry'])==1762
 save(O/'inputs/MANIFEST.json',canonical)
 save(O/'inputs/COMPLETION.json',dict(passed=True,series=1799,stock_receipts=25251,industry_receipts=1762,
      old2022_2023_controls_all1799_exact=True,physical_June28_all1799_exact=True,new_models=0,new_account_events=0))
 save(O/'SCORES_MANIFEST.json',dict(stocks=1709,fixed_stock_ids=oldm['fixed_stock_ids'],entries=score_rows,
      formula_sha256=sha(FORMULA),windows=[['2022-01-01','2022-12-30'],['2023-01-03','2023-12-29'],[BEGIN,END]],
      decision_calendars=cals,explicit_cells=1709*726,source_cutoff=END,old_score_manifest_sha256=sha(H/'SCORES_MANIFEST.json'),
      old2022_2023_score_prefix_exact_cells=1709*484,physical_June28_all1709_exact=True,
      future_poison_sample=sorted(s for s in samples if not s.startswith('URFI')),account_events=0))
 assert all(sha(p)==h for p,h in freeze['sources'].items())
 result=dict(passed=True,series=1799,stocks=1709,industries=90,account_events=0,new_I_CP1_stage_models=0,
      original_PVR_formula_unchanged=True,old_canonical_controls_exact_series=1799,physical_canonical_prefix_exact_series=1799,
      old_score_prefix_exact_cells=1709*484,physical_score_prefix_exact_stocks=1709,
      ready_2024=sum(x['ready_2024']for x in score_rows),NA_2024=sum(x['NA_2024']for x in score_rows),
      stock_receipts=25251,industry_receipts=1762,source_freeze_sha256=sha(O/'SOURCE_FREEZE.json'),
      score_manifest_sha256=sha(O/'SCORES_MANIFEST.json'),canonical_manifest_sha256=sha(O/'inputs/MANIFEST.json'),
      reused=reused,seconds=time.monotonic()-started)
 save(O/'DATA_GATE.json',result);print('DATA2024_DONE',json.dumps(result),flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as e:
  save(O/'ERROR.json',dict(error=repr(e),traceback=__import__('traceback').format_exc(),account_events=0));raise
