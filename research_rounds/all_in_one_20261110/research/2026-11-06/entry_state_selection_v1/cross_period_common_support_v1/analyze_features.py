"""One frozen cross-period common-support diagnostic. No outcomes in this file."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time,math
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
IX=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/signals')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
SOURCES={};T=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expect=None):
 p=Path(p);p=p if p.is_absolute() else R/p;h=sha(p)
 if expect is not None:assert h==expect,(p,'changed')
 SOURCES[str(p)]=h;return p
def norm(v):
 if isinstance(v,dict):return {str(k):norm(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [norm(x) for x in v]
 if isinstance(v,np.generic):return norm(v.item())
 if isinstance(v,(pd.Timestamp,Path)):return str(v)
 if isinstance(v,float) and not math.isfinite(v):return None
 if v is pd.NA or v is pd.NaT:return None
 return v
def save(n,v):
 with (O/n).open('x') as f:json.dump(norm(v),f,ensure_ascii=False,indent=2,allow_nan=False)
P=json.loads(src(O/'PROTOCOL_V1.json').read_text())
for n in ['analyze_features.py','SCOPE_IDENTITIES.csv','PRE_FEATURE_SOURCE_HASHES.json']:src(O/n)
for p,h in json.loads((O/'PRE_FEATURE_SOURCE_HASHES.json').read_text()).items():src(p,h)
with (O/'RUN_ONCE.lock').open('x') as f:f.write(pd.Timestamp.now(tz='UTC').isoformat())
fullcal=pd.DatetimeIndex(np.load(src(H),allow_pickle=False)['dates']);fullcal=fullcal[(fullcal>='2013-01-01')&(fullcal<='2024-12-31')]
mp={x['symbol']:x for x in json.loads(src(M).read_text())}
ids=pd.read_csv(O/'SCOPE_IDENTITIES.csv')
old=pd.read_csv(src(R/'m3_q1_entry_path_strata_v1/ENTRY_FEATURES_PRELABEL.csv'))
a=ids[['round_id','period']].merge(old,on='round_id',validate='one_to_one')
paths=[R/p for p in P['outcomes']['sources']]
orig=pd.concat([pd.read_csv(src(p),usecols=['round_id','arm','PVR_score']) for p in paths])
orig=orig[orig.arm.eq('A_UNION_B')].drop(columns='arm')
a=a.merge(orig,on='round_id',validate='one_to_one')
a['i_buy_today']=a.i_buy_today.astype(str).str.upper()
a['log_amount_ratio']=np.log(a.amount_ratio.where(a.amount_ratio.gt(0)))
a['log_vol_ratio']=np.log(a.vol_ratio.where(a.vol_ratio.gt(0)))
a['log1p_I_age']=np.log1p(a.I_root_age_n.where(a.I_root_age_n.ge(0)))
a['log1p_sector_M3_age']=np.log1p(a.sector_M3_age_n.where(a.sector_M3_age_n.ge(0)))
a['event_cluster']=a.period+'|'+a.signal_day+'|'+a.sector+'|'+a.entry_type
a['root_id']=a.sid+'|'+a.root_day.astype(str)
a=a.sort_values('round_id').reset_index(drop=True)
cols=['open','high','low','close','raw_open','raw_high','raw_low','raw_close','raw_volume','amount','adjustment_factor','volume_factor','segment_id','source_kind','source_path','price_eligible','volume_eligible','observed_bar','is_observed_bar','source_invalid','synthetic_event_bar','volume_unit','amount_unit']
def calc(p,calendar):
 q=p.reindex(calendar)
 pc=['open','high','low','close'];rc=['raw_'+c for c in pc]
 valid=np.isfinite(q[pc+rc]).all(axis=1)&q[pc+rc].gt(0).all(axis=1)&q.high.gt(q.low)&q.raw_high.gt(q.raw_low)&q.segment_id.notna()
 valid &= q.high.ge(q[pc].max(axis=1))&q.low.le(q[pc].min(axis=1))&q.raw_high.ge(q[rc].max(axis=1))&q.raw_low.le(q[rc].min(axis=1))
 for k in ['price_eligible','volume_eligible','observed_bar','is_observed_bar']:valid &=q[k].eq(True)
 for k in ['source_invalid','synthetic_event_bar']:valid &=q[k].eq(False)
 for k in ['source_kind','source_path']:valid &= q[k].notna()&q[k].astype(str).str.strip().str.len().gt(0)
 for k in ['adjustment_factor','volume_factor']:valid &=np.isfinite(q[k])&q[k].gt(0)
 for k in pc:valid &= (q[k]-q['raw_'+k]*q.adjustment_factor).abs().le(1e-10)
 change=pd.Series(False,index=calendar)
 for k in ['segment_id','source_kind','source_path','adjustment_factor','volume_factor']:change |= q[k].ne(q[k].shift())
 block=((~valid)|(~valid.shift(fill_value=False))|change).cumsum()
 dmi=pd.Series(np.nan,index=calendar);dage=dmi.copy()
 for _,g in q[valid].groupby(block[valid],sort=False):
  if len(g)<15:continue
  up=np.diff(g.high.to_numpy());dn=-np.diff(g.low.to_numpy())
  u=np.where((up>dn)&(up>0),up,0.);v=np.where((dn>up)&(dn>0),dn,0.)
  def rma(x):
   z=x[13:].copy();z[0]=x[:14].mean();return pd.Series(z).ewm(alpha=1/14,adjust=False).mean().to_numpy()
  uu=rma(u);vv=rma(v);den=uu+vv
  dmi.loc[g.index[14:]]=np.divide(uu-vv,den,out=np.full(len(uu),np.nan),where=den>0)
  dage.loc[g.index[14:]]=np.arange(14,len(g))
 # CMF has explicit missing common dates and same-factor/source windows.
 cv=valid & q.volume_unit.eq('shares')&q.amount_unit.eq('CNY')&np.isfinite(q.raw_volume)&q.raw_volume.gt(0)&np.isfinite(q.amount)&q.amount.gt(0)
 avg=q.amount/q.raw_volume;tol=.5/q.raw_volume+1e-8
 cv &=avg.ge(q.raw_low-tol)&avg.le(q.raw_high+tol)
 clv=(2*q.raw_close-q.raw_high-q.raw_low)/(q.raw_high-q.raw_low)
 native=(2*q.close-q.high-q.low)/(q.high-q.low)
 cv &= (clv-native).abs().le(1e-8)
 cb=((~cv)|(~cv.shift(fill_value=False))|change).cumsum();cmf=pd.Series(np.nan,index=calendar)
 for _,g in q[cv].groupby(cb[cv],sort=False):
  if len(g)<21:continue
  v=g.raw_volume
  cmf.loc[g.index]=(clv.loc[g.index]*v).rolling(21,min_periods=21).sum()/v.rolling(21,min_periods=21).sum()
 return pd.DataFrame(dict(DMI14=dmi,CMF21=cmf,D_age=dage,valid=valid,cmf_input_valid=cv),index=calendar)
# Deterministic implementation checks before actual feature extraction.
tc=pd.bdate_range('2000-01-03',periods=65);base=100.+np.arange(len(tc),dtype=float)
fx=pd.DataFrame(index=tc)
for c,arr in [('open',base),('high',base+1),('low',base-1),('close',base)]:
 fx[c]=arr;fx['raw_'+c]=arr
for c,v in dict(raw_volume=100.,amount_unit='CNY',volume_unit='shares',adjustment_factor=1.,volume_factor=1.,segment_id=0,source_kind='fixture',source_path='fixture',price_eligible=True,volume_eligible=True,observed_bar=True,is_observed_bar=True,source_invalid=False,synthetic_event_bar=False).items():fx[c]=v
fx['amount']=fx.raw_close*fx.raw_volume
fz=calc(fx,tc);assert fz.DMI14.iloc[14:].eq(1).all() and fz.CMF21.iloc[20:].eq(0).all()
flat=fx.copy()
for c,v in [('open',100.),('high',101.),('low',99.),('close',100.)]:flat[c]=flat['raw_'+c]=v
flat.amount=flat.raw_close*flat.raw_volume
ff=calc(flat,tc);assert ff.DMI14.isna().all() and ff.CMF21.iloc[20:].eq(0).all()
gap=calc(fx.drop(tc[25]),tc);assert gap.DMI14.iloc[25:40].isna().all() and gap.DMI14.iloc[40]==1 and gap.CMF21.iloc[25:46].isna().all() and gap.CMF21.iloc[46]==0
factor=fx.copy();factor.loc[tc[25]:,'adjustment_factor']=2
for c in ['open','high','low','close']:factor[c]=factor['raw_'+c]*factor.adjustment_factor
fs=calc(factor,tc);assert fs.DMI14.iloc[25:39].isna().all() and fs.DMI14.iloc[39]==1 and fs.CMF21.iloc[25:45].isna().all() and fs.CMF21.iloc[45]==0
save('SYNTHETIC_QA.json',dict(monotone_up_DMI=True,flat_direction_UNKNOWN=True,CMF_midpoint_zero=True,missing_common_day_rewarm=True,factor_change_rewarm=True))
rows=[];checks=[];prefix=[]
for no,(sid,g) in enumerate(a.groupby('sid',sort=True)):
 md=mp[sid];sp=[p for p in md['source_sha256'] if p.endswith('/signal.parquet')]
 assert len(sp)==1
 sp=src(sp[0],md['source_sha256'][sp[0]])
 raw=pd.read_parquet(sp,columns=cols).loc[:'2024-12-31'];assert raw.index.is_unique and raw.index.is_monotonic_increasing
 gp=src(IX/(sid+'.parquet'))
 ng=pd.read_parquet(gp,columns=['close','segment_id','z5','z21','strength_ready','valid_strength_observation']).loc[:'2024-12-31']
 ix=ng.index.intersection(raw.index)
 np.testing.assert_allclose(ng.loc[ix,'close'],raw.loc[ix,'close'],rtol=0,atol=0,equal_nan=True)
 np.testing.assert_equal(ng.loc[ix,'segment_id'].to_numpy(),raw.loc[ix,'segment_id'].to_numpy())
 out=calc(raw,fullcal)
 for idx,r in g.iterrows():
  day=pd.Timestamp(r.signal_day);v=out.loc[day];nt=ng.reindex([day]).iloc[0]
  ready=bool(nt.strength_ready==True and nt.valid_strength_observation==True)
  rows.append(dict(index=idx,DMI14=v.DMI14,CMF21=v.CMF21,D_age=v.D_age,z5=nt.z5 if ready else np.nan,z21=nt.z21 if ready else np.nan,native_G_ready=ready))
 if no%100==0:
  day=pd.Timestamp(g.sort_values('signal_day').iloc[0].signal_day)
  cut=calc(raw.loc[:day],fullcal[fullcal<=day])
  pd.testing.assert_frame_equal(cut,out.loc[:day],check_exact=True)
  poisoned=raw.copy();future=poisoned.index>day
  for col in ['open','high','low','close','amount','raw_volume']:poisoned.loc[future,col]=-9
  poison=calc(poisoned,fullcal)
  pd.testing.assert_frame_equal(poison.loc[:day],out.loc[:day],check_exact=True)
  prefix.append(dict(sid=sid,day=day,full_prefix_exact=True,future_mutation_exact=True,native_G_replayed=False))
 checks.append(dict(sid=sid,observations=len(raw),native_G_common_rows=len(ix),target_rows=len(g),signal_source=str(sp),signal_hash=SOURCES[str(sp)],g_source=str(gp),g_hash=SOURCES[str(gp)]))
 if (no+1)%200==0:print('FEATURE_PROGRESS',no+1,'/',a.sid.nunique(),round(time.monotonic()-T,2),flush=True)
new=pd.DataFrame(rows).set_index('index').sort_index();a=a.join(new)
features=P['features'];exact=P['exact_match']
a['unknown_fields']=a[features].apply(lambda r:'|'.join(r.index[~np.isfinite(r.to_numpy(float))]),axis=1)
badexact=~a.i_buy_today.isin(['TRUE','FALSE'])|a.CP_root_context.astype(str).str.startswith('UNKNOWN')|a[exact].isna().any(axis=1)
a.loc[badexact,'unknown_fields']=a.loc[badexact,'unknown_fields']+'|EXACT_STATE_UNKNOWN'
a['feature_known']=a.unknown_fields.eq('')
a.to_csv(O/'FEATURES_PRELABEL.csv',index=False)
pd.DataFrame(checks).to_csv(O/'SOURCE_CHECKS.csv',index=False)
pd.DataFrame(prefix).to_csv(O/'PREFIX_CHECKS.csv',index=False)
coverage=[]
for per,g in a.groupby('period'):
 coverage.append(dict(period=per,permits=len(g),stocks=g.sid.nunique(),dates=g.signal_day.nunique(),event_clusters=g.event_cluster.nunique(),feature_known=int(g.feature_known.sum()),feature_unknown=int((~g.feature_known).sum()),complete_events=g[g.feature_known].event_cluster.nunique()))
pd.DataFrame(coverage).to_csv(O/'FEATURE_COVERAGE.csv',index=False)
unknown=[]
for per,g in a.groupby('period'):
 for c in features:unknown.append(dict(period=per,field=c,unknown=int((~np.isfinite(g[c].to_numpy(float))).sum())))
 unknown.append(dict(period=per,field='EXACT_STATE',unknown=int(badexact.loc[g.index].sum())))
pd.DataFrame(unknown).to_csv(O/'UNKNOWN_BY_FIELD.csv',index=False)
tr=a[a.period.eq('Q1')&a.feature_known]
sc=pd.DataFrame({'median':tr[features].median(),'q25':tr[features].quantile(.25,interpolation='linear'),'q75':tr[features].quantile(.75,interpolation='linear')});sc['scale']=(sc.q75-sc.q25)/1.349
sc.to_csv(O/'Q1_ONLY_SCALER.csv');tr[['round_id','sid','signal_day','event_cluster']].to_csv(O/'SCALER_TRAINING_IDENTITIES.csv',index=False)
badscale=sc[~np.isfinite(sc.scale)|sc.scale.le(0)]
if len(badscale):
 save('MATCHING_STOP.json',dict(reason='Q1_ZERO_OR_UNKNOWN_SCALE',features=list(badscale.index),Q1_training_n=len(tr),matches=0))
else:
 z=(a[features]-sc['median'])/sc['scale'];a[[c+'_z' for c in features]]=z
 a.to_csv(O/'FEATURES_SCALED_PRELABEL.csv',index=False)
 edge=[];trips=[]
 for key,g in a[a.feature_known].groupby(exact,dropna=False,sort=True):
  aa=g[g.period.eq('Q1')];bb=g[g.period.eq('Q3')];cc=g[g.period.eq('AUTUMN')]
  for ia in aa.index:
   va=z.loc[ia].to_numpy(float)
   dx=np.abs(z.loc[bb.index].to_numpy(float)-va);dy=np.abs(z.loc[cc.index].to_numpy(float)-va)
   ibs=list(bb.index[np.all(dx<=1,axis=1)]);ics=list(cc.index[np.all(dy<=1,axis=1)])
   for per,candidates in [('Q3',ibs),('AUTUMN',ics)]:
    for j in candidates:
     delta=z.loc[j].to_numpy(float)-va;edge.append(dict(anchor_id=a.loc[ia,'round_id'],other_id=a.loc[j,'round_id'],other_period=per,rms=float(np.sqrt(np.mean(delta*delta))),max_abs=float(np.max(abs(delta)))))
   for ib in ibs:
    for ic in ics:
     ab=z.loc[ib].to_numpy(float)-va;ac=z.loc[ic].to_numpy(float)-va;bc=z.loc[ib].to_numpy(float)-z.loc[ic].to_numpy(float)
     if not np.all(abs(bc)<=1):continue
     ds=[float(np.sqrt(np.mean(v*v))) for v in [ab,ac,bc]]
     trips.append(dict(iQ1=int(ia),iQ3=int(ib),iAUTUMN=int(ic),idQ1=a.loc[ia,'round_id'],idQ3=a.loc[ib,'round_id'],idAUTUMN=a.loc[ic,'round_id'],dQ1Q3=ds[0],dQ1AUTUMN=ds[1],dQ3AUTUMN=ds[2],max_rms=max(ds),total_rms=sum(ds)))
 edgecols=['anchor_id','other_id','other_period','rms','max_abs'];pd.DataFrame(edge,columns=edgecols).to_csv(O/'ALL_ANCHOR_EDGES_PRELABEL.csv',index=False)
 tripcols=['iQ1','iQ3','iAUTUMN','idQ1','idQ3','idAUTUMN','dQ1Q3','dQ1AUTUMN','dQ3AUTUMN','max_rms','total_rms']
 tf=pd.DataFrame(trips,columns=tripcols).sort_values(['max_rms','total_rms','idQ1','idQ3','idAUTUMN'])
 tf.to_csv(O/'ALL_FEASIBLE_TRIPLETS_PRELABEL.csv',index=False)
 used=set();selected=[];audit=[]
 for r in tf.to_dict('records'):
  cs=[a.loc[r['i'+per],'event_cluster'] for per in ['Q1','Q3','AUTUMN']]
  conflict=any(c in used for c in cs)
  audit.append({**r,'selected':not conflict,'reason':'EVENT_ALREADY_USED' if conflict else 'SELECTED'})
  if not conflict:used.update(cs);selected.append(r)
 sel=pd.DataFrame(selected,columns=tripcols);sel.insert(0,'triplet_id',np.arange(1,len(sel)+1))
 sel.to_csv(O/'SELECTED_TRIPLETS_PRELABEL.csv',index=False)
 pd.DataFrame(audit,columns=tripcols+['selected','reason']).to_csv(O/'GREEDY_ORDER_AUDIT.csv',index=False)
 members=[]
 for r in sel.to_dict('records'):
  for per in ['Q1','Q3','AUTUMN']:
   row=a.loc[r['i'+per]].to_dict();members.append(dict(triplet_id=r['triplet_id'],**row))
 members=pd.DataFrame(members,columns=['triplet_id']+list(a.columns))
 members.to_csv(O/'SELECTED_MEMBERS_PRELABEL.csv',index=False)
 assert members.round_id.is_unique and members.event_cluster.is_unique
 support=dict(status='MATCHES_SEALED_BEFORE_OUTCOMES',original_permits=len(a),known=int(a.feature_known.sum()),anchor_edges=len(edge),feasible_triplets=len(tf),selected_triplets=len(sel),source_stocks=a.sid.nunique(),no_outcome_columns_read=True,no_strategy=True,seconds=time.monotonic()-T)
 save('MATCHING_SUMMARY.json',support);print('SUPPORT',json.dumps(norm(support)),flush=True)
for p,h in SOURCES.items():assert sha(p)==h,(p,'source drift')
save('SOURCE_HASHES.json',SOURCES)
save('FEATURE_MATCH_SEAL.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()})
print('COMPLETE_FEATURES_SEALED',round(time.monotonic()-T,2),flush=True)
