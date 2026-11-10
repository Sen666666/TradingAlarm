"""Append original source observations in separate chunks. Old prefix bytes stay.
No account objects, financial events, or signal formula recalculation.
"""
from common_next import *
import time,shutil,numpy as np,pandas as pd
import pyarrow.parquet as pq

def run():
 original_guard();root=O/'inputs';root.mkdir(exist_ok=False);t=time.monotonic()
 inv=LD.read(LD.B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json');sources=LD.read(H.INPUT/'SOURCE_BINDINGS.json');access={}
 def bind(p):
  p=Path(p)
  if str(p) not in access:
   actual=sha(p);assert actual==sources[str(p)],('original source changed',str(p));access[str(p)]=actual
  return p
 def frame(p,end,key='date'):
  return pq.read_table(bind(p),filters=[(key,'<=',pd.Timestamp(end).to_pydatetime())]).to_pandas()
 accum={k:dict(facts=[],cp=[],raw=[],pvr=[],h1=[],metadata={},receipts=[],actions=[],payments=[],f1_observations=[]) for k in SPECS}
 invariants={k:[] for k in SPECS}
 for n,item in enumerate(inv):
  sid=item['symbol'];r=item['refs'];f=frame(r['facts'],'2025-07-03');cp=frame(r['CP1'],'2025-07-03');pv=frame(r['PVR'],'2025-07-03','day');raw=frame(r['raw_bars'],'2025-07-03','trade_date').set_index('trade_date')
  actions=LD.read(bind(r['actions']))['events'] if r['actions'] else []
  for k,spec in SPECS.items():
   day=spec['next_day'];a=accum[k]
   for name,data in [('facts',f),('cp',cp),('pvr',pv),('raw',raw)]:
    z=data[data.index==pd.Timestamp(day)]
    if len(z):a[name].append(PREP.longframe(z,sid))
   if pd.Timestamp(day) in f.index:
    a['metadata'][sid]=PREP.structure_observations(sid,f.loc[:day],[day])
   else:a['metadata'][sid]=[]
   receiptpath=r['receipts_2022' if k=='2022' else 'receipts'];records=LD.read(bind(receiptpath));new=[x for x in records if x['confirmed_day']==day]
   assert len(new)==int(pd.Timestamp(day) in cp.index and bool(cp.loc[pd.Timestamp(day),'receipt']))
   assert not any(x['trace_unknown'] for x in new);a['receipts'].extend(new)
   for ev in actions:
    term=dict(sid=sid,**ev,known_action_date=ev['effective_date'],unpaid_policy='original unknown date stays attributed receivable, 80% net research proxy; no financing',sellability_proxy='unknown new-share sellable date follows original next source trading day proxy; not certified')
    if ev['effective_date']==day:a['actions'].append(term)
    if ev.get('paid_at') and spec['old_end']<ev['paid_at'][:10]<=day:a['payments'].append(term)
  if (n+1)%500==0:print('ORIGINAL_NEXT_INPUT',n+1,round(time.monotonic()-t,2),flush=True)
 hp=bind(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'));h=np.load(hp,allow_pickle=False);dates=pd.DatetimeIndex(h['dates']);hc={str(s):i for i,s in enumerate(h['symbols'])};scores=h['score']
 catalogue=LD.read(LD.B/'industry-coverage/run-v1/NODE_CATALOGUE.json')
 nodes=[dict(node_id='NATIVE1709_global',input_file=str(LD.B/'input-preparation/prepared-v2/NATIVE1709/market.parquet'))]+[r for r in catalogue if r['domain']=='NATIVE1709']
 for k,s in SPECS.items():
  old=LD.HistoricalInputs(H.INPUT/k/'MANIFEST.json');day=s['next_day'];index=dates.get_indexer([pd.Timestamp(day)])[0];assert index>=0
  at=day+'T09:30:00+08:00';assert at in old.rules['calendars']['A'] and day+'T15:10:00+08:00' in old.rules['decision_cutoffs']
  accum[k]['h1']=[dict(sid=sid,day=day,score=float(scores[index,hc[sid]])) for sid in old.ids+old.m['sectors']]
  for node in nodes:
   data=frame(node['input_file'],day);z=data[data.index==pd.Timestamp(day)].copy();assert len(z)==1,('missing actual F1 observation',k,node['node_id'],day)
   seed=old.seeds[node['node_id']];z['node_id']=node['node_id'];z['policy_scope']=seed['policy_scope'];z['original_F1_scope']=seed['original_F1_scope']
   accum[k]['f1_observations'].append(PREP.longframe(z,node['node_id']))
  rootk=root/k;shutil.copytree(H.INPUT/k,rootk);ext=rootk/'extensions';ext.mkdir();m=LD.read(rootk/'MANIFEST.json')
  before={n:sha(rootk/r['path']) for n,r in m['files'].items()};m['original_prefix_days']=m['days'];m['days']=m['days']+[day];m['extensions']={}
  for name in ('facts','cp','raw','pvr','f1_observations'):
   p=ext/(name+'.parquet');base=pd.read_parquet(rootk/m['files'][name]['path']);rows=accum[k][name];z=pd.concat(rows,ignore_index=True) if rows else base.iloc[:0].copy()
   z=z.reindex(columns=base.columns);z.to_parquet(p,index=False);m['extensions'][name]=dict(path=str(p.relative_to(rootk)),sha256=sha(p),rows=len(z))
  p=ext/'h1.parquet';pd.DataFrame(accum[k]['h1']).to_parquet(p,index=False);m['extensions']['h1']=dict(path=str(p.relative_to(rootk)),sha256=sha(p),rows=len(accum[k]['h1']))
  for name in ('metadata','receipts','actions','payments'):
   p=ext/(name+'.json');LD.write(p,accum[k][name]);m['extensions'][name]=dict(path=str(p.relative_to(rootk)),sha256=sha(p),rows=len(accum[k][name]))
  assert before=={n:sha(rootk/r['path']) for n,r in m['files'].items()}
  m['horizon_extension']=dict(parent_manifest=str(H.INPUT/k/'MANIFEST.json'),parent_manifest_sha256=sha(H.INPUT/k/'MANIFEST.json'),
   old_end=s['old_end'],authorized_next_session=day,all_base_file_hashes_preserved=before,real_original_sources=True,diagnostic=False)
  LD.write(rootk/'MANIFEST.json',m)
 save(root/'SOURCE_BINDINGS.json',access)
 save(root/'PREPARATION.json',dict(original_source_only=True,source_files=len(access),source_bindings_sha256=sha(root/'SOURCE_BINDINGS.json'),
  originals_unchanged=True,financial_events=0,models_recomputed=0,seconds=time.monotonic()-t,
  summary={k:{name:(sum(len(x) for x in v) if isinstance(v,list) and v and isinstance(v[0],pd.DataFrame) else len(v)) for name,v in data.items()} for k,data in accum.items()}))
 print('COMPLETE_ORIGINAL_NEXTDAY_INPUTS',round(time.monotonic()-t,2),flush=True)
if __name__=='__main__':run()
