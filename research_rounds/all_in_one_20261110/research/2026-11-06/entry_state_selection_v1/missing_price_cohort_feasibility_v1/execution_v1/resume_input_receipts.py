"""Resume interrupted INPUT-ONLY preparation; zero economic loops were started."""
from pathlib import Path
import json,sys,hashlib,time,resource,gc
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent.parent;J=R/'independent_channel_joint_economic_v1';start=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False,default=str);f.write('\n')
assert not (O/'INPUTS_COMPLETE.json').exists() and not list(O.glob('ECONOMIC_RUN_ONCE_*'))
assert not (O/'PRICE_CANDIDATES.parquet').exists()
for p,h in json.loads((O.parent/'OLD_TREE_SHA256_BEFORE.json').read_text()).items():assert sha(p)==h
native=O/'NATIVE_QUAL_EXTRA.parquet';nativehash=sha(native);sources=json.loads((J/'ROOT_ECONOMIC_AUTHORIZATION.json').read_text())['input_sha256'].copy();sources.update(json.loads((O.parent/'SOURCE_SHA256.json').read_text()));sources[str(native)]=nativehash;sources[str(__file__)]=sha(__file__)
save('INPUT_RESUME_STARTED.json',dict(cause='exec-session transport loss; process confirmed absent; precise termination reason unknown',native_sha256=nativehash,only_input_resume=True,old_tree_unchanged=True))
# Load native rows once then retain only four projected sector booleans and PVR.
qual=pd.read_parquet(native);assert not qual.duplicated(['sid','day']).any();assert qual.sid.nunique()==1709
sys.path.insert(0,str(J));from market_adapter import MarketAdapter,_reasons
fields=['sector_known','sector_observed_today','sector_rs_ready_fresh','sector_up']
for c in fields:
    v=pd.Series(True,index=qual.index,dtype='boolean');v.loc[qual.event_Q_reasons.str.contains(c+':false',regex=False,na=False)]=False;v.loc[qual.event_Q_reasons.isna()|qual.event_Q_reasons.str.contains(c+':unknown',regex=False,na=False)]=pd.NA;qual[c]=v
qual=qual.drop(columns='event_Q_reasons');qual['sid']=qual.sid.astype('category');qual['sector']=qual.sector.astype('category');groups={str(sid):g.set_index('day').drop(columns='sid') for sid,g in qual.groupby('sid',observed=True)};ndays=qual.day.nunique();assert len(qual)==1709*ndays;del qual;gc.collect()
a=MarketAdapter(native_cache_limit=1);proto=json.loads((O.parent/'PROTOCOL.json').read_text());checks=[]
for sid in proto['fixture_sids']:
 for wn,ds in proto['fixture_dates'].items():
  for d in pd.DatetimeIndex([ds[0],ds[-1]]):
   actual=a.native_industry(sid,d,cut=d);row=groups[sid].loc[d];got=dict(sector=row.sector,**{c:None if pd.isna(row[c]) else bool(row[c]) for c in fields});assert actual==got,(sid,d,actual,got);checks.append(dict(sid=sid,day=str(d.date()),original_native_prefix_equal=True))
 a._native.clear();gc.collect()
 print('RESUME_PREFIX',sid,'seconds',round(time.monotonic()-start,1),flush=True)
save('NATIVE_SAMPLE_QA.json',checks)
roster=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid');ids=sorted(roster.index);parts=[];counts=[];wins={'2023':('2023-01-01','2023-12-31'),'2024JanAug':('2024-01-01','2024-08-31')}
for n,sid in enumerate(ids):
 z=a.load_sid(sid)
 for wn,(lo,hi) in wins.items():
  g=z.loc[lo:hi];g=g[g.receipt].copy();g['sid']=sid;g['day']=g.index;g['window']=wn;g['name']=roster.loc[sid,'name'];g['industry']=roster.loc[sid,'industry'];g['valid']=g.price_valid;g['receipt_id']=g.legacy_receipt_id;g['volume_capacity_shares']=g.capacity_shares
  if len(g):
   qq=groups[sid].loc[g.index];g['sector']=qq.sector.to_numpy();g['old_PVR_known']=qq.PVR_known.to_numpy();g['old_PVR_score']=qq.PVR_score.to_numpy()
   for c in fields:g['old_'+c]=qq[c].to_numpy()
   cols=['sid','day','name','industry','sector','window','root_day','identity','receipt_id','valid','raw_close','adjustment_factor','S_new','phase','born','receipt','old_PVR_known','old_PVR_score','old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up','volume_capacity_shares'];parts.append(g[cols].reset_index(drop=True))
  counts.append(dict(sid=sid,window=wn,receipts=len(g)))
 a._market.clear()
 if (n+1)%100==0:print('PRICE_INPUT_SIDS',n+1,1709,'seconds',round(time.monotonic()-start,1),'peak_mb',round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20),flush=True)
x=pd.concat(parts,ignore_index=True);assert not x.duplicated(['window','sid','day']).any();x.to_parquet(O/'PRICE_CANDIDATES.parquet',index=False);pd.DataFrame(counts).to_csv(O/'PRICE_RECEIPT_COUNTS.csv',index=False)
sources.update(a.verify_sources());assert sha(native)==nativehash
for p,h in sources.items():assert sha(p)==h,(p,'source drift')
save('PREPARED_SOURCE_SHA256.json',sources);save('PREPARED_OUTPUT_SHA256.json',{n:sha(O/n) for n in ['NATIVE_QUAL_EXTRA.parquet','PRICE_CANDIDATES.parquet','PRICE_RECEIPT_COUNTS.csv','NATIVE_SAMPLE_QA.json']})
save('INPUTS_COMPLETE.json',dict(no_economics=True,stocks=1709,native_extra_days=ndays,native_extra_rows=1709*ndays,candidate_counts=x.groupby('window').size().to_dict(),sample_prefix_checks=len(checks),resumed_input_only=True,seconds=time.monotonic()-start,peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20))
print('INPUTS_COMPLETE',json.loads((O/'INPUTS_COMPLETE.json').read_text()),flush=True)
