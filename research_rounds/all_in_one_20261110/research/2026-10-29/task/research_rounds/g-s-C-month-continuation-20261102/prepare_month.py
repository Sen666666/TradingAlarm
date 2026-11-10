"""Append original cached rows to immutable third-session full inputs."""
from pathlib import Path
import sys,json,time,copy,shutil
import pandas as pd,numpy as np,pyarrow.parquet as pq
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-nextsession-native-20261102'));import c_horizon as C
X=C.X;P=C.P;E=C.E
SPECS={'2022':('2022-01-07','2022-01-28'),'2025_26':('2025-07-04','2025-07-31')}
def main():
 t=time.perf_counter();C.guard();inventory=X.LD.read(X.LD.B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json');expected=X.LD.read(P.H.INPUT/'SOURCE_BINDINGS.json');bound={}
 def bind(p):
  p=Path(p)
  if str(p) not in bound:assert P.sha(p)==expected[str(p)];bound[str(p)]=expected[str(p)]
  return p
 roots={};acc={};days={}
 for k,(start,end) in SPECS.items():
  old=C.HERE/'inputs'/k/'full';m=C.read(old/'MANIFEST.json');root=HERE/'inputs'/k;root.parent.mkdir(exist_ok=True);shutil.copytree(old,root)
  roots[k]=root;days[k]=[d[:10] for d in C.read(old/'rules.json')['calendars']['A'] if start<=d[:10]<=end and d[11:16]=='09:30'];acc[k]={n:[] for n in ('facts','cp','raw','pvr','h1','f1_observations','receipts','actions','payments')};acc[k]['metadata']={}
 for n,item in enumerate(inventory):
  sid=item['symbol'];ref=item['refs'];ff=X.PREP.filtered(bind(ref['facts']),'2025-07-31');cp=X.PREP.filtered(bind(ref['CP1']),'2025-07-31');pv=X.PREP.filtered(bind(ref['PVR']),'2025-07-31','day');raw=X.PREP.filtered(bind(ref['raw_bars']),'2025-07-31','trade_date').set_index('trade_date');rights=X.LD.read(bind(ref['actions']))['events'] if ref['actions'] else []
  for k,(start,end) in SPECS.items():
   wanted=days[k][1:];a=acc[k]
   for name,f in [('facts',ff),('cp',cp),('raw',raw),('pvr',pv)]:a[name].append(X.PREP.longframe(f[f.index.isin(pd.to_datetime(wanted))],sid))
   observed=[d for d in wanted if pd.Timestamp(d) in ff.index];a['metadata'][sid]=X.PREP.structure_observations(sid,ff,observed)
   receipts=X.LD.read(bind(ref['receipts_2022' if k=='2022' else 'receipts']));a['receipts'] += [z for z in receipts if z['confirmed_day'] in wanted]
   for ev in rights:
    term=dict(sid=sid,**ev,known_action_date=ev['effective_date'],unpaid_policy='original unknown date stays attributed receivable, 80% net research proxy; no financing',sellability_proxy='unknown new-share sellable date follows original next source trading day proxy; not certified')
    if ev['effective_date'] in wanted:a['actions'].append(term)
    if ev.get('paid_at') and ev['paid_at'][:10] in wanted:a['payments'].append(term)
  if (n+1)%500==0:print('MONTH_INPUT',n+1,round(time.perf_counter()-t,2),flush=True)
 hp=bind(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'));h=np.load(hp,allow_pickle=False);hd=pd.DatetimeIndex(h['dates']);hc={str(s):i for i,s in enumerate(h['symbols'])};scores=h['score']
 catalogue=X.LD.read(X.LD.B/'industry-coverage/run-v1/NODE_CATALOGUE.json');nodes=[dict(node_id='NATIVE1709_global',input_file=str(X.LD.B/'input-preparation/prepared-v2/NATIVE1709/market.parquet'))]+[z for z in catalogue if z['domain']=='NATIVE1709']
 for k,root in roots.items():
  old=X.ExtendedInputs(root/'MANIFEST.json');wanted=days[k][1:]
  for day in wanted:
   ix=hd.get_indexer([pd.Timestamp(day)])[0];assert ix>=0
   acc[k]['h1'] += [dict(sid=sid,day=day,score=float(scores[ix,hc[sid]])) for sid in old.ids+old.m['sectors']]
  for node in nodes:
   f=X.PREP.filtered(bind(node['input_file']),SPECS[k][1]);z=f[f.index.isin(pd.to_datetime(wanted))].copy();seed=old.seeds[node['node_id']];z['node_id']=node['node_id'];z['policy_scope']=seed['policy_scope'];z['original_F1_scope']=seed['original_F1_scope'];acc[k]['f1_observations'].append(X.PREP.longframe(z,node['node_id']))
  m=C.read(root/'MANIFEST.json');prior=C.P.sha(root/'MANIFEST.json');m['days']=sorted(set(m['days']+days[k]));m['month_extension']={};ext=root/'month';ext.mkdir()
  for name in ('facts','cp','raw','pvr','f1_observations','h1'):
   z=pd.DataFrame(acc[k][name]) if name=='h1' else pd.concat(acc[k][name],ignore_index=True);p=ext/(name+'.parquet');z.to_parquet(p,index=False);m['month_extension'][name]=dict(path=str(p.relative_to(root)),sha256=P.sha(p),rows=len(z))
  for name in ('metadata','receipts','actions','payments'):
   p=ext/(name+'.json');E.IO.write_json(p,acc[k][name],encoder=E.encode);m['month_extension'][name]=dict(path=str(p.relative_to(root)),sha256=P.sha(p),rows=len(acc[k][name]))
  m['month_data_scope']=dict(start=SPECS[k][0],end=SPECS[k][1],parent_full_manifest_sha256=prior,all_old_files_and_extensions_preserved=True,financial_permission_not_conferred=True)
  E.IO.write_json(root/'MANIFEST.json',m)
 E.IO.write_json(HERE/'MONTH_INPUT_FREEZE.json',dict(models_recomputed=0,financial_events=0,source_files=len(bound),seconds=time.perf_counter()-t,windows={k:dict(path=str(root/'MANIFEST.json'),sha256=P.sha(root/'MANIFEST.json'),days=days[k]) for k,root in roots.items()}));E.IO.write_json(HERE/'SOURCE_BINDINGS.json',bound);print('MONTH_PREPARED',round(time.perf_counter()-t,2),flush=True)
if __name__=='__main__':main()
