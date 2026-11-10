"""Read saved20 cache/source/old outputs. Never imports producer or signal models."""
from pathlib import Path
import json,hashlib,math
import pandas as pd,numpy as np
import pyarrow.dataset as ds
O=Path(__file__).resolve().parent;R=O.parents[1];E=R.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
F=['e0_ready','e0_target','e0_floor','e0_entered','e0_exited','i_target','i_floor','i_entered','i_exited','i_buy','i_exit_reason','g_grade','g_ready','g_fresh_up','g_acute_down','g_up_reasons','numeric_event','numeric_leg_direction','close']
def series(a,b,label):
 assert a.index.equals(b.index),(label,'index')
 assert a.isna().equals(b.isna()),(label,'null')
 good=a.notna()
 if pd.api.types.is_numeric_dtype(a)and not pd.api.types.is_bool_dtype(a):
  assert np.array_equal(a[good].to_numpy(float).view(np.uint64),b[good].to_numpy(float).view(np.uint64)),(label,'bits')
 else:assert a[good].astype(str).equals(b[good].astype(str)),(label,'value')
def frame(a,b,label):
 assert a.index.equals(b.index)and a.columns.equals(b.columns),(label,'schema')
 for c in a:series(a[c],b[c],(label,c))
 return a.size
freeze=read(R/'FREEZE.json');run=read(R/'RUN_RECEIPT.json');stocks=freeze['stocks'];assert len(stocks)==len(set(stocks))==20
assert sha(R/'PILOT20_ROSTER.csv')==freeze['roster_sha256'] and sha(R/'SOURCE_DATE_UNION.parquet')==freeze['date_union_sha256']
for p,h in freeze['original_code_sha256'].items():assert sha(p)==h,('changed code',p)
source=Path(freeze['source']);st=source.stat();assert st.st_size==freeze['source_size'] and st.st_mtime_ns==freeze['source_mtime_ns']
roster=pd.read_csv(R/'PILOT20_ROSTER.csv');assert roster.sid.tolist()==stocks
union=pd.DatetimeIndex(pd.read_parquet(R/'SOURCE_DATE_UNION.parquet').day);assert union.is_unique and union.is_monotonic_increasing and str(union[0].date())>='2022-01-01' and str(union[-1].date())=='2026-05-15'
assert len(union)==freeze['output_dates_union_N']==1054 and 20*len(union)==freeze['output_grid_rows']==21080
raw=ds.dataset(source).to_table(columns=['symbol','trade_date','open','high','low','close','volume','amount','source'],filter=ds.field('symbol').isin(stocks)&(ds.field('trade_date')<=pd.Timestamp('2026-05-15'))).to_pandas()
original={d:pd.read_parquet(E/'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet'if d=='2024-09-24'else E/'full_local_signal_two_dates_v1'/d/'signals/ALL_SIGNALS.parquet').set_index('sid')for d in ['2022-01-24','2024-09-24','2026-01-15']}
pvrall=pd.read_parquet(E/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet')
stageold=pd.read_parquet(E/'e0_stage_pvr_v1/ALL_REQUEST_STAGE_SNAPSHOTS.parquet').set_index(['day','sid'])
runrows={r['sid']:r for r in run['records']};assert set(runrows)==set(stocks)
summary=[];bound=[R/'FREEZE.json',R/'RUN_RECEIPT.json',R/'pilot.py',R/'SOURCE_DATE_UNION.parquet',R/'PILOT20_ROSTER.csv'];old19=oldmissing=pvrchecks=stagechecks=gridcells=fullroundtrip=0;prefixcount=0;allvolume_valid=True
for sid in stocks:
 folder=R/'full'/sid;rec=read(folder/'RECEIPT.json');assert rec==runrows[sid]
 for name,h in rec['file_sha256'].items():assert sha(folder/name)==h
 b=pd.read_parquet(folder/'BASELINE_FULL_HISTORY.parquet');d=pd.read_parquet(folder/'DAILY2022_20260515.parquet');g=raw[raw.symbol.eq(sid)].sort_values('trade_date').set_index('trade_date')
 assert g.index.is_unique and g.source.nunique(dropna=False)==1 and g.source.notna().all()and g.source.str.strip().ne('').all()
 assert b.index.equals(g.index)and len(b)==rec['baseline_rows']==rec['profile']['input_rows'] and b.columns.is_unique
 assert d.sid.eq(sid).all()and pd.DatetimeIndex(d.day).equals(union)and len(d)==rec['daily_grid_rows']==1054
 x=d.set_index('day');x.index.name=b.index.name
 fullroundtrip+=b.size;assert b.size==rec['full_roundtrip_cells']
 expected=b.reindex(union);expected.index.name=x.index.name
 for c in b:series(x[c],expected[c],(sid,'daily-baseline',c));gridcells+=len(x)
 sourcepresent=union.isin(g.index);assert np.array_equal(x.source_row_present,sourcepresent)
 close=g[['open','high','low','close']];mask=np.isfinite(close).all(axis=1)&close.gt(0).all(axis=1)&g.high.ge(g.low)&g.high.ge(g[['open','close']].max(axis=1))&g.low.le(g[['open','close']].min(axis=1))
 assert b.native__close.notna().equals(mask)
 assert x.stock_eligible_price_observation.eq(x.native__close.notna()).all()
 for c in ['open','high','low','close','volume','amount']:
  series(x['price__'+c],g[c].reindex(union),(sid,'price',c))
 known=x.native__e0_ready.eq(1)&x.native__g_ready.eq(True)
 expected_status=np.where(~sourcepresent,'MISSING_SOURCE_ROW',np.where(~x.stock_eligible_price_observation,'INVALID_ORIGINAL_PRICE_MASK',np.where(known,'READY','WARMUP_OR_STRENGTH_UNKNOWN')))
 assert np.array_equal(x.stock_signal_knowledge,expected_status)and x.historical_trading_eligibility.eq('UNKNOWN_NONPIT').all()
 evvalid=mask&np.isfinite(g.volume)&g.volume.gt(0);allvolume_valid &= bool((np.isfinite(g.volume)&g.volume.gt(0)).all())
 ready=evvalid.cumsum().ge(65);series(b.loc[mask,'native__e0_ready'].astype(bool),ready[mask],(sid,'E0-ready-clock'))
 series(b.loc[mask,'native__g_ready'].astype(bool),(ready&evvalid)[mask],(sid,'G1-ready-clock'))
 pvalid=np.isfinite(g.close)&g.close.gt(0)&np.isfinite(g.amount)&g.amount.gt(0)
 block=((~pvalid)|(~pvalid.shift(fill_value=False))|pd.Series(0,index=g.index).ne(pd.Series(0,index=g.index).shift())).cumsum()
 series(b.pvr__valid_observation,pvalid,(sid,'PVR-valid'))
 series(b.pvr__clock_block,block,(sid,'PVR-block'))
 cpidx=b.index[b.native__close.notna()];bad=~(np.isfinite(g.loc[cpidx,'close'])&g.loc[cpidx,'close'].gt(0)&np.isfinite(g.loc[cpidx,'amount'])&g.loc[cpidx,'amount'].gt(0));first=str(bad[bad].index[0].date())if bad.any()else None
 assert first==rec['profile']['cp_first_bad_date']
 if first:
  after=cpidx[cpidx>=pd.Timestamp(first)];assert b.loc[after,'cp__input_status'].eq('BLOCKED_BY_PRIOR_INVALID_INPUT').all()
  cpc=[c for c in b if c.startswith('cp__')and c!='cp__input_status'];assert b.loc[after,cpc].isna().all().all()
  before=cpidx[cpidx<pd.Timestamp(first)];assert b.loc[before,'cp__input_status'].eq('VALID_OR_WARMUP').all()
 else:assert b.loc[cpidx,'cp__input_status'].eq('VALID_OR_WARMUP').all()
 oldchecks=[]
 for day,old in original.items():
  stamp=pd.Timestamp(day);z=old.loc[sid]
  if stamp not in b.index or pd.isna(b.loc[stamp,'native__close']):assert z.signal_status!='EXACT_TARGET_STOCK_SIGNAL';oldmissing+=1;oldchecks.append((day,str(z.signal_status),0));continue
  a=b.loc[[stamp],['native__'+c for c in F]].copy();a.columns=F
  v=pd.DataFrame([{c:z[c]for c in F}],index=a.index);frame(a,v,(sid,'old19',day));old19+=1;oldchecks.append((day,'EXACT19',19))
 assert oldchecks==[(z['day'],z['status'],z['exact_fields'])for z in rec['old19_checks']]
 oldp=pvrall[pvrall.sid.eq(sid)];present=[]
 for z in oldp.itertuples(index=False):
  stamp=pd.Timestamp(z.day)
  if stamp not in b.index:assert not z.target_row_present;continue
  pcols=['r','scale','amount_ref','u','b','e','E','score'];a=b.loc[[stamp],['pvr__'+c for c in pcols]].copy();a.columns=pcols
  v=pd.DataFrame([{c:getattr(z,c)for c in pcols}],index=a.index);frame(a,v,(sid,'oldPVR',z.day));pvrchecks+=1;present.append(str(z.day))
 assert present==rec['oldPVR_dates']
 mapping={'stage__phase':'phase','stage__reference_peak':'reference_peak','stage__reference_peak_occurred':'reference_peak_occurred','stage__reference_peak_confirmed':'reference_peak_confirmed','stage__start_date':'start_date','stage__breakout_date':'breakout_date','stage__downgrade_date':'downgrade_date','stage__last_peak':'last_confirmed_peak','stage__last_peak_occurred':'last_peak_occurred','stage__last_peak_confirmed':'last_peak_confirmed'}
 for day in original:
  if (day,sid)not in stageold.index:continue
  old=stageold.loc[(day,sid)]
  if old.status!='COMPLETE':continue
  stamp=pd.Timestamp(day)
  for a,c in mapping.items():
   v,w=b.loc[stamp,a],old[c]
   if pd.isna(v)or pd.isna(w):assert pd.isna(v)and pd.isna(w)
   elif isinstance(v,(float,np.floating))and isinstance(w,(float,np.floating)):assert np.float64(v).view(np.uint64)==np.float64(w).view(np.uint64)
   else:assert v==w,(sid,day,a,v,w)
  stagechecks+=1
 eligible=b.index[b.native__close.notna()];warm=eligible[min(64,len(eligible)-1)];observed=eligible[(eligible>=pd.Timestamp('2022-01-01'))&(eligible<pd.Timestamp('2026-05-15'))];middle=observed[len(observed)//2]if len(observed)else eligible[len(eligible)//2]
 cuts=sorted(set([warm,middle]));assert rec['physical_prefix_cuts']==[str(z.date())for z in cuts]and rec['physical_prefix_total_calls']==len(cuts)
 prefix=[]
 for cut in cuts:
  p=folder/f'PREFIX_{cut.date()}.json';a=read(p);subg=g.loc[:cut];baseline=b.loc[:cut]
  assert a['sid']==sid and a['cut']==a['input_max']==str(cut.date()) and a['input_rows']==len(subg)and a['compared_rows']==len(baseline)and a['compared_columns']==len(b.columns)and a['bitexact_cells']==baseline.size
  assert a['full_future_not_in_prefix_input'] is True
  cpbad=a['component_profile']['cp_first_bad_date'];assert cpbad==(first if first and first<=str(cut.date())else None)
  prefixcount+=1;bound.append(p);prefix.append({'cut':str(cut.date()),'rows':len(baseline),'columns':len(b.columns),'native_e0_ready_at_cut':bool(b.loc[cut,'native__e0_ready']),'native_g_ready_at_cut':bool(b.loc[cut,'native__g_ready'])})
 assert len(cuts)==2 and len(g.loc[g.index>middle])>0
 summary.append({'sid':sid,'input_rows':len(g),'eligible_rows':int(mask.sum()),'daily_source_rows':int(sourcepresent.sum()),'daily_missing_rows':int((~sourcepresent).sum()),'old19_exact':sum(v[1]=='EXACT19'for v in oldchecks),'old19_missing':sum(v[1]!='EXACT19'for v in oldchecks),'oldPVR_exact_dates':len(present),'first_bad_CP':first,'warm65_e0_ready':bool(b.loc[warm,'native__e0_ready']),'warm65_g_ready':bool(b.loc[warm,'native__g_ready']),'prefix_receipt_checks':prefix})
 bound += [folder/'RECEIPT.json',folder/'BASELINE_FULL_HISTORY.parquet',folder/'DAILY2022_20260515.parquet']
assert prefixcount==40 and run['calls_new_full_signal']==60 and run['stocks']==20 and run['accounts']==0
out={'status':'PASS_BOUNDED_SAVED20_DAILY_CACHE_OLD_OUTPUTS_AND_PREFIX_RECEIPT_REVIEW','remaining_blocks':[],'stocks':20,'grid_rows':21080,'grid_days':1054,'saved_baseline_cells':fullroundtrip,'daily_baseline_value_cells_independently_checked':gridcells,'old_same_source19_exact_requests':old19,'old_same_source19_missing_requests':oldmissing,'oldPVR_exact_dates':pvrchecks,'old_stage_exact_requests':stagechecks,'all20_source_volume_positive_finite':bool(allvolume_valid),'all20_warm65_E0_G1_ready':all(z['warm65_e0_ready']and z['warm65_g_ready']for z in summary),'producer_physical_prefix_receipts':prefixcount,'producer_original_stock_signal_calls':60,'per_stock':summary,'prefix_claim_boundary':'The40 producer tests run original kernel on clipped inputs and assert all common-prefix values, but prefix frames are not saved. Reviewer independently checked their cut/source/schema/count metadata and bound comparison code; did not independently recalculate/recompare40 prefix frames.','edge_controls':'PENDING_SEPARATE_BOUNDED_EDGE_RECEIPT','limits':['Only saved frames/old values/source20 rows read; zero reviewer model/numeric/account calls.','Main old cache overlap checks three dates19 and seven dates8PVR; not old daily native/CP caches for1054days.','No exhaustive every-day physical recomputation; no generic invalid/segment test coverage yet.','Single-source original adapter unchanged; current source fields/version are not historical publication/PIT evidence.','stock_signal_knowledge is combined fresh readiness only; raw I_hold-capable native19 remains separately preserved.','No executed holding protection P or stock/industry/cash/quantity/orders in CP market-only outputs.'],'source_sha256':{str(p.resolve()):sha(p)for p in bound},'reviewer_new_full_signal_models':0,'reviewer_new_numeric_calls':0,'reviewer_new_accounts':0}
p=O/'SAVED_OUTPUT_AUDIT.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({k:out[k]for k in ['status','stocks','grid_rows','old_same_source19_exact_requests','old_same_source19_missing_requests','oldPVR_exact_dates','old_stage_exact_requests','all20_source_volume_positive_finite','all20_warm65_E0_G1_ready','producer_physical_prefix_receipts']},ensure_ascii=False));print('AUDIT_SHA256',sha(p))
