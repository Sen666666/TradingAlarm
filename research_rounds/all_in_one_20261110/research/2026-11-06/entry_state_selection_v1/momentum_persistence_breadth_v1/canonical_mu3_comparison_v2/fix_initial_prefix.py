from pathlib import Path
import importlib.util,json,hashlib,time,shutil,warnings
import pandas as pd,numpy as np
warnings.filterwarnings('ignore',category=FutureWarning)
O=Path(__file__).resolve().parent;V=O.parent;R=V.parent;P=R/'pvr_persistence_breadth_v1';B=O/'BEFORE_INITIAL_PREFIX_FIX';B.mkdir(exist_ok=True)
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load('mbv1',V/'analyze.py');PV=load('pvr_original',P/'experiment.py');sm=json.load(open(A.U/'STOCK_MANIFEST.json'));im=json.load(open(A.U/'INDUSTRY_MANIFEST.json'));roster=pd.read_csv(V/'FIXED_ROSTER.csv');ids=sorted(roster.symbol)
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index)for x in im])));pre=cal[cal<A.START][-3:];cut='2022-01-06';smallcal=cal[cal<=cut]
k=pd.read_parquet(O/'KNOWN3.parquet');r=pd.read_parquet(O/'RIGHT3.parquet');sk=pd.read_parquet(O/'STRICT_KNOWN3.parquet');sr=pd.read_parquet(O/'STRICT_RIGHT3.parquet');pvd=pd.read_parquet(P/'STOCK_DAILY.parquet',columns=['sid','day','state']);ps=pvd.pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids)
preK={};preR={};preS={};preSK={};preSR={};t0=time.monotonic();aud=[]
for i,rec in enumerate(sm):
 sid=rec['symbol'];sp=Path(next(p for p in rec['source_sha256']if p.endswith('/signal.parquet')));raw=pd.read_parquet(sp).loc[:cut];g=pd.read_parquet(A.IX/(sid+'.parquet'),columns=['close','volume','segment_id','valid_strength_observation']).loc[:cut];m=pd.Series(np.nan,index=g.index)
 for _,gg in g.groupby('segment_id',sort=False):
  q=gg[gg.valid_strength_observation];c=q.close.to_numpy()
  if not len(c):continue
  x=np.log(c/c[0]);v=np.full(len(c),np.nan);mv=np.nan
  for j in range(1,len(c)):
   rr=x[j]-x[j-1];mv=rr if j==1 else (1/3)*rr+(1-1/3)*mv
   if j>=64:v[j]=mv
  m.loc[q.index]=v
 q=g.reindex(smallcal);p=raw.reindex(smallcal);mu=m.reindex(smallcal);identity=p.segment_id.astype('string')+'|'+p.source_kind.astype('string')+'|'+p.source_path.astype('string');valid=q.valid_strength_observation.eq(True)&p.observed_bar.eq(True)&p.price_eligible.eq(True)&p.volume_eligible.eq(True)&~p.source_invalid.eq(True)&p.close.gt(0)&p.volume.gt(0)&np.isfinite(mu);kk=valid&valid.shift(1,fill_value=False)&valid.shift(2,fill_value=False)&identity.eq(identity.shift(1)).fillna(False)&identity.eq(identity.shift(2)).fillna(False);rr=kk&mu.gt(0)&mu.shift(1).gt(0)&mu.shift(2).gt(0)
 pp=PV.state(raw,PV.original_pvr(raw).score,smallcal).state
 ix=k.index[k.index<=cut];np.testing.assert_equal(kk.reindex(ix).to_numpy(),k.loc[ix,sid].to_numpy());np.testing.assert_equal(rr.reindex(ix).to_numpy(),r.loc[ix,sid].to_numpy());np.testing.assert_equal(pp.reindex(ix).to_numpy(),ps.loc[ix,sid].to_numpy())
 gs=g.copy();gr=raw.reindex(g.index);gs.segment_id=gr.segment_id.astype('string')+'|'+gr.source_kind.astype('string')+'|'+gr.source_path.astype('string');ss=A.calc(gs,smallcal)
 preK[sid]=kk.reindex(pre);preR[sid]=rr.reindex(pre);preS[sid]=pp.reindex(pre);preSK[sid]=ss.known.reindex(pre);preSR[sid]=ss.right.reindex(pre);aud.append(dict(sid=sid,first3_M3_exact=True,first3_PVR_exact=True))
 if (i+1)%500==0:print('PREFIX',i+1,round(time.monotonic()-t0,2),flush=True)
for name,data in [('M_K',preK),('M_R',preR),('P_STATE',preS),('STRICT_K',preSK),('STRICT_R',preSR)]:pd.DataFrame(data).to_parquet(O/('WARM_PREFIX_'+name+'.parquet'))
k=pd.concat([pd.DataFrame(preK),k]);r=pd.concat([pd.DataFrame(preR),r]);sk=pd.concat([pd.DataFrame(preSK),sk]);sr=pd.concat([pd.DataFrame(preSR),sr]);ps=pd.concat([pd.DataFrame(preS),ps]);both=k&ps.ge(0);pr=ps.eq(1)
def gate(b):
 n=b.n;N=b.N;U=b.U;J=b.common3_K;d=b.entered3-b.left3;rule=lambda nn,dd:(nn>=3)&(((nn*3>=dd)&J.gt(0)&d.gt(0))|(nn*2>=dd));lo=rule(n,N);hi=(n+U>=3)&(((3*(n+U)>=N)&(d.gt(0)|J.eq(0)))|(2*(n+U)>=N));b['observed_candidate']=np.where(b.K.gt(0),rule(n,b.K).astype(int),-1);b['candidate']=np.where(lo,1,np.where(~hi,0,-1));return b
parts={n:[]for n in ['SECTOR_DAILY','STRICT_SECTOR_DAILY','COMMON_K_COMPARISON']};native=pd.read_parquet(O/'SECTOR_DAILY.parquet');native=native[['day','sector']+[c for c in native if c.startswith('sector_')]];changes=[]
for sec,g in roster.groupby('sector_id'):
 cols=g.symbol.tolist()
 for name,kk,rr in [('SECTOR_DAILY',k,r),('STRICT_SECTOR_DAILY',sk,sr)]:
  b=gate(A.breadth(sec,cols,kk,rr)).loc[A.START:];b.index.name='day';parts[name].append(b.reset_index())
 bm=gate(A.breadth(sec,cols,both,r&both));bp=gate(A.breadth(sec,cols,both,pr&both));z=bm[['sector','N','K','U','common3_K']].copy()
 for label,df in [('M3',bm),('PVR3',bp)]:
  for c in ['n','right_known','right_fixed_lower','right_fixed_upper','entered3','left3','delta3','observed_candidate','candidate']:z[label+'_'+c]=df[c]
 z['both_right']=(r[cols]&pr[cols]&both[cols]).sum(axis=1);z['M3_only']=((r[cols]&~pr[cols])&both[cols]).sum(axis=1);z['PVR3_only']=((pr[cols]&~r[cols])&both[cols]).sum(axis=1);z=z.loc[A.START:];z.index.name='day';parts['COMMON_K_COMPARISON'].append(z.reset_index())
for name,pss in parts.items():
 path=O/(name+'.parquet');shutil.copy2(path,B/path.name);prev=pd.read_parquet(path);new=pd.concat(pss).merge(native,on=['day','sector'],how='left');assert len(prev)==len(new);keys=['day','sector'];v=prev.sort_values(keys).reset_index(drop=True);n=new.sort_values(keys).reset_index(drop=True);cols=[c for c in n if c.endswith('candidate')];delta=v[keys+cols].merge(n[keys+cols],on=keys,suffixes=('_before','_after'));changed=np.column_stack([delta[c+'_before'].ne(delta[c+'_after'])for c in cols]).any(axis=1);delta=delta[changed];delta['file']=name;changes.append(delta)
 pd.testing.assert_frame_equal(v[v.day.gt(cut)].reset_index(drop=True),n[n.day.gt(cut)].reset_index(drop=True),check_exact=True)
 new.to_parquet(path,index=False);new[new.day.dt.strftime('%Y-%m-%d').isin(A.FIXED)].to_csv(O/('FIXED_'+name+'.csv'),index=False);new[new.sector.eq('URFI881121')].to_csv(O/('SEMICONDUCTOR_'+name+'.csv'),index=False)
pd.concat(changes).to_csv(O/'INITIAL_PREFIX_FIX_CHANGES.csv',index=False);pd.DataFrame(aud).to_csv(O/'INITIAL_PREFIX_EXACT_AUDITS.csv',index=False);(O/'INITIAL_PREFIX_FIX.json').write_text(json.dumps(dict(prefix_dates=[str(x.date())for x in pre],stocks=1709,first3_stock_states_exact=True,all_industry_fields_after_Jan6_exact=True,changed_candidate_rows=sum(len(z)for z in changes),seconds=time.monotonic()-t0),indent=2));print('DONE',round(time.monotonic()-t0,2),flush=True)
