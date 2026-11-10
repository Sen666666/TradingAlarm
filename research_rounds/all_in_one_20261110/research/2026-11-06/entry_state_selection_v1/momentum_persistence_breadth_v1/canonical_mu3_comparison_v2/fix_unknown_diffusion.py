from pathlib import Path
import pandas as pd,numpy as np,json,shutil
O=Path(__file__).resolve().parent;B=O/'BEFORE_UNKNOWN_DIFFUSION_FIX';B.mkdir(exist_ok=True);dates=json.load(open(O/'PROTOCOL.json'))
fixed=json.load(open(O.parent/'PROTOCOL.json'))['fixed_cases'];changes=[]
for name in ['SECTOR_DAILY','STRICT_SECTOR_DAILY','COMMON_K_COMPARISON']:
 p=O/(name+'.parquet');shutil.copy2(p,B/p.name);b=pd.read_parquet(p);labels=['M3_','PVR3_']if name=='COMMON_K_COMPARISON'else ['']
 for label in labels:
  n=b[label+'n'];N=b.N;U=b.U;J=b.common3_K;d=(b[label+'entered3']-b[label+'left3']);lo=(n>=3)&(((3*n>=N)&J.gt(0)&d.gt(0))|(2*n>=N));hi=(n+U>=3)&(((3*(n+U)>=N)&(d.gt(0)|J.eq(0)))|(2*(n+U)>=N));new=np.where(lo,1,np.where(~hi,0,-1));diff=new!=b[label+'candidate'];q=b.loc[diff,['day','sector',label+'candidate']].copy();q['new_candidate']=new[diff];q['file']=name;q['model']=label;changes.append(q);b[label+'candidate']=new
 b.to_parquet(p,index=False);b[b.day.dt.strftime('%Y-%m-%d').isin(fixed)].to_csv(O/('FIXED_'+name+'.csv'),index=False);b[b.sector.eq('URFI881121')].to_csv(O/('SEMICONDUCTOR_'+name+'.csv'),index=False)
pd.concat(changes).to_csv(O/'UNKNOWN_DIFFUSION_FIX_CHANGES.csv',index=False);print('unknown fix',sum(len(q)for q in changes))
