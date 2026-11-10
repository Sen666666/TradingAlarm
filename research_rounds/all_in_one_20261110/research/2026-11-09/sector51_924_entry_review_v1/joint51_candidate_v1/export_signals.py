from pathlib import Path
import json,hashlib,sys
import numpy as np,pandas as pd
sys.dont_write_bytecode=True
from engine import sector_frame,trigger,R,O,sha,save
seal=json.loads((O/'FREEZE.json').read_text());Q=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';paths=[O/'CLASSIFICATION_ALL1709.csv',Q/'KNOWN3.parquet',Q/'RIGHT3.parquet',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',O/'engine.py']
for p in paths:assert sha(p)==seal['hashes'][str(p)]
ro=pd.read_csv(paths[0]);ro=ro[ro.eligible];ids=sorted(ro.symbol);k=pd.read_parquet(paths[1])[ids].loc[:'2024-10-31'];r=pd.read_parquet(paths[2])[ids].loc[:'2024-10-31'];ps=pd.read_parquet(paths[3],columns=['sid','day','state']);ps=ps[ps.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids);known=k&ps.ge(0);right=r&known;stock=pd.DataFrame(np.where(known,np.where(right,1,0),-1),index=k.index,columns=ids)
rows=[];milestones=[]
for sec,gg in ro.groupby('sector51'):
 members=sorted(gg.symbol);sf=sector_frame(known[members],right[members]);window=sf.loc['2024-09-02':];first=lambda mask: str(window.index[mask][0].date()) if mask.any() else None
 births=sf.state.eq(1)&sf.state.shift().eq(0)
 milestones.append(dict(sector51=sec,N=len(members),first_TRUE=first(window.state.eq(1)),first_sector_A=first(births.reindex(window.index)),first_strength=first(window.strength),true_dates=[str(x.date()) for x in window.index[window.state.eq(1)]],birth_dates=[str(x.date()) for x in window.index[births.reindex(window.index)]],strength_dates=[str(x.date()) for x in window.index[window.strength]]))
 for dt,x in window.iterrows():
  prev=sf.index[sf.index.get_loc(dt)-1];ats=[];bts=[]
  for s in members:
   typ=trigger(int(sf.at[prev,'state']),int(x.state),int(stock.at[prev,s]),int(stock.at[dt,s]));
   if typ=='A':ats.append(s)
   if typ=='B':bts.append(s)
  rows.append(dict(day=str(dt.date()),sector51=sec,**{key:int(x[key]) for key in ['N','K','n','U','paired_K','entered3','left3','diff','state']},strength=bool(x.strength),new_sector_A=bool(births.at[dt]),new_A_count=len(ats),new_B_count=len(bts),new_A_symbols=';'.join(ats),new_B_symbols=';'.join(bts)))
save(O/'ALL50_DAILY_RECOGNITION.json',rows);pd.DataFrame(rows).to_csv(O/'ALL50_DAILY_RECOGNITION.csv',index=False);save(O/'ALL50_SIGNAL_MILESTONES.json',milestones);pd.DataFrame(milestones).to_csv(O/'ALL50_SIGNAL_MILESTONES.csv',index=False);save(O/'RECOGNITION_SOURCE_HASHES.json',{str(p):sha(p) for p in paths+[Path(__file__)]});print(json.dumps(dict(rows=len(rows),sectors=len(milestones),scope='signals only; no account reexecution or winner filtering',focus=[x for x in milestones if x['sector51'] in ['证券保险','半导体','软件与IT服务','电子元件材料','动力电池']]),ensure_ascii=False))
