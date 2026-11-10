"""Append existing frozen source values only. No financial object or model run."""
from pathlib import Path
import sys,json,time,copy,shutil
import pandas as pd,numpy as np
W=Path(__file__).resolve().parent.parent;P=Path(__file__).resolve().parent
sys.path.insert(0,str(W/'g-s-C-nextsession-native-20261102'));import c_horizon as C
X=C.X;E=C.E;LD=X.LD
OLD=W/'g-s-C-month-continuation-20261102/inputs/2025_26';OUT=P/'inputs';START='2025-08-01';END='2025-09-30'
def main():
 t=time.perf_counter();expected=LD.read(C.P.H.INPUT/'SOURCE_BINDINGS.json');inv=LD.read(LD.B/'g-s-minimal-input-readiness/STOCK_INPUT_INVENTORY.json');bound={}
 def bind(p):
  p=Path(p)
  if str(p) not in bound:
   assert str(p) in expected and C.P.sha(p)==expected[str(p)],'original source identity changed '+str(p);bound[str(p)]=expected[str(p)]
  return p
 assert not OUT.exists(),'no overwrite/re-export uncertain result';shutil.copytree(OLD,OUT);m=LD.read(OLD/'MANIFEST.json');days=[d[:10] for d in LD.read(OLD/'rules.json')['calendars']['A'] if START<=d[:10]<=END and d[11:16]=='09:30'];wanted=pd.to_datetime(days);acc={n:[] for n in ['facts','cp','raw','pvr','h1','f1_observations','receipts','actions','payments']};acc['metadata']={}
 for k,item in enumerate(inv):
  sid=item['symbol'];r=item['refs'];ff=X.PREP.filtered(bind(r['facts']),END);cp=X.PREP.filtered(bind(r['CP1']),END);pv=X.PREP.filtered(bind(r['PVR']),END,'day');raw=X.PREP.filtered(bind(r['raw_bars']),END,'trade_date').set_index('trade_date')
  for key,f in [('facts',ff),('cp',cp),('raw',raw),('pvr',pv)]:acc[key].append(X.PREP.longframe(f[f.index.isin(wanted)],sid))
  acc['metadata'][sid]=X.PREP.structure_observations(sid,ff,[d for d in days if pd.Timestamp(d) in ff.index]);acc['receipts'] += [z for z in LD.read(bind(r['receipts'])) if z['confirmed_day'] in days]
  for ev in (LD.read(bind(r['actions']))['events'] if r['actions'] else []):
   term=dict(sid=sid,**ev,known_action_date=ev['effective_date'],unpaid_policy='original unknown date stays attributed receivable, 80% net research proxy; no financing',sellability_proxy='unknown new-share sellable date follows original next source trading day proxy; not certified')
   if ev['effective_date'] in days:acc['actions'].append(term)
   if ev.get('paid_at') and ev['paid_at'][:10] in days:acc['payments'].append(term)
  if (k+1)%500==0:print('EXPORTED_SOURCE_STOCKS',k+1,round(time.perf_counter()-t,2),flush=True)
 hp=bind(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'));h=np.load(hp,allow_pickle=False);hd=pd.DatetimeIndex(h['dates']);hc={str(s):i for i,s in enumerate(h['symbols'])}
 for d in days:
  ix=hd.get_indexer([pd.Timestamp(d)])[0];assert ix>=0;acc['h1'] += [dict(sid=sid,day=d,score=float(h['score'][ix,hc[sid]])) for sid in m['ids']+m['sectors']]
 old=X.ExtendedInputs(OLD/'MANIFEST.json');cat=LD.read(LD.B/'industry-coverage/run-v1/NODE_CATALOGUE.json');nodes=[dict(node_id='NATIVE1709_global',input_file=str(LD.B/'input-preparation/prepared-v2/NATIVE1709/market.parquet'))]+[z for z in cat if z['domain']=='NATIVE1709']
 for node in nodes:
  f=X.PREP.filtered(bind(node['input_file']),END);z=f[f.index.isin(wanted)].copy();seed=old.seeds[node['node_id']];z['node_id']=node['node_id'];z['policy_scope']=seed['policy_scope'];z['original_F1_scope']=seed['original_F1_scope'];acc['f1_observations'].append(X.PREP.longframe(z,node['node_id']))
 ext=OUT/'augsep';ext.mkdir();m['continuation_extension']={};counts={}
 for key in ['facts','cp','raw','pvr','h1','f1_observations']:
  f=pd.DataFrame(acc[key]) if key=='h1' else pd.concat(acc[key],ignore_index=True);q=ext/(key+'.parquet');f.to_parquet(q,index=False);m['continuation_extension'][key]=dict(path=str(q.relative_to(OUT)),sha256=C.P.sha(q),rows=len(f));counts[key]=dict(rows=len(f),stock_or_node_ids=f['sid'].nunique(),days=f['day'].nunique())
 for key in ['metadata','receipts','actions','payments']:
  q=ext/(key+'.json');E.IO.write_json(q,acc[key],encoder=E.encode);m['continuation_extension'][key]=dict(path=str(q.relative_to(OUT)),sha256=C.P.sha(q),rows=len(acc[key]))
 m['days']=sorted(set(m['days']+days));m['continuation_data_scope']=dict(start=START,end=END,old_manifest_sha256=C.P.sha(OLD/'MANIFEST.json'),original_groups_byte_preserved=True,financial_permission=False,needs_thin_fourth_generation_input_loader=True)
 E.IO.write_json(OUT/'MANIFEST.json',m);E.IO.write_json(P/'EXPORTED_INPUTS.json',dict(passed=True,days=days,additional_sessions=len(days),identities=1709,industry_identities=90,F1_nodes=91,counts=counts,receipts=len(acc['receipts']),actions=len(acc['actions']),payments=len(acc['payments']),manifest=str(OUT/'MANIFEST.json'),manifest_sha256=C.P.sha(OUT/'MANIFEST.json'),sources=len(bound),seconds=time.perf_counter()-t,model_recomputations=0,financial_events=0));E.IO.write_json(P/'SOURCE_BINDINGS.json',bound)
 print('AUGSEP_INPUT_EXPORTED',len(days),round(time.perf_counter()-t,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as ex:
  import traceback;E.IO.write_json(P/'EXPORT_ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc(),financial_events=0));raise
