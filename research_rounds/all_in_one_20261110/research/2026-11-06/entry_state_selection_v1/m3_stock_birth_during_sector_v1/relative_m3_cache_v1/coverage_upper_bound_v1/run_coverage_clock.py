"""Frozen fixed-case clock diagnostic; all receipt counts assume FLAT, no financial strategy results."""
from pathlib import Path
import json,hashlib,time
import numpy as np,pandas as pd
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from clock_model import relative_clock,cached_receipts
SHARD=int(sys.argv[1]);NSHARDS=int(sys.argv[2])
O=Path(__file__).resolve().parent;B=O.parent;E=B.parent;R=E.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
IX=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/signals')
M=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
END=pd.Timestamp('2026-06-30')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def true(x):return pd.notna(x) and x in (True,1)
def native_mu(g):
 out=pd.Series(np.nan,index=g.index)
 for _,gg in g.groupby('segment_id',sort=False):
  q=gg[gg.valid_strength_observation];c=q.close.to_numpy();n=len(q)
  if not n:continue
  logs=np.log(c/c[0]);m=np.nan;vals=np.full(n,np.nan)
  for i in range(1,n):
   rr=logs[i]-logs[i-1];m=rr if i==1 else (1/3)*rr+(2/3)*m
   if i>=64:vals[i]=m
  out.loc[q.index]=vals
 return out
births=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day'])
births=births[births.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])]
spec=json.loads((O/'FROZEN_SCOPE.json').read_text())
sm={x['symbol']:x for x in json.loads((U/'STOCK_MANIFEST.json').read_text())};im={x['series']:x for x in json.loads((U/'INDUSTRY_MANIFEST.json').read_text())}
member=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid')
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input'],columns=[]).index) for x in im.values()])));cal=cal[cal<=END]
panel=pd.read_parquet(M/'COMMON_K_COMPARISON.parquet').set_index(['sector','day'])
K=pd.read_parquet(M/'KNOWN3.parquet');RIGHT=pd.read_parquet(M/'RIGHT3.parquet');MU=pd.read_parquet(M/'MU5.parquet')
old=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day']);oldids={(r.window,r.sid,r.day):r.event_type for r in old.itertuples()}
pvr=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet').set_index(['sid','day'])
base=[O/'PROTOCOL.json',O/'FROZEN_SCOPE.json',B/'clock_model.py',Path(__file__),B/'SYNTHETIC_TESTS.json',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',M/'COMMON_K_COMPARISON.parquet',M/'KNOWN3.parquet',M/'RIGHT3.parquet',M/'MU5.parquet',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv',E/'SEALED_ALL_BIRTH_EVENTS.csv',E/'entry_quality_2022_v1/CORE_LAYER_RESULTS.csv']
hashes={str(p):sha(p) for p in base}
save('RUN_SEAL_'+str(SHARD)+'.json',dict(hashes=hashes,prior_to_coverage_outputs=True,not_economic_test=True))
stocks=sorted(set().union(*(set(w['stocks']) for w in spec.values())))[SHARD::NSHARDS]
sources={};indraw={};data={};receipts=[];traces=[];daily=[];rels=[];qa=[];starttime=time.monotonic()
for sid in stocks:
 sec=member.loc[sid,'sector_id'];name=member.loc[sid,'name'];m=sm[sid]
 sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));gp=IX/(sid+'.parquet');fp=m['refs']['facts']
 raw=pd.read_parquet(sp).loc[:END];g=pd.read_parquet(gp).loc[:END];facts=pd.read_parquet(fp).loc[:END];sources[sid]=sp
 for pp in [sp,gp,fp]:hashes[str(pp)]=sha(pp)
 if sec not in indraw:
  ip=next(p for p in im[sec]['source_sha256'] if p.endswith('/signal.parquet'))
  indraw[sec]=pd.read_parquet(ip).loc[:END].reindex(cal);hashes[ip]=sha(ip)
 ip=indraw[sec];p=raw.reindex(cal);gf=g.reindex(cal);f=facts.reindex(cal);mu=native_mu(g).reindex(cal)
 identity=p.source_kind.astype('string')+'|'+p.source_path.astype('string')+'|'+p.segment_id.astype('string')
 si=ip.source_kind.astype('string')+'|'+ip.source_path.astype('string')+'|'+ip.segment_id.astype('string')
 valid=gf.valid_strength_observation.eq(True)&p.observed_bar.eq(True)&p.price_eligible.eq(True)&p.volume_eligible.eq(True)&~p.source_invalid.eq(True)&p.close.gt(0)&p.volume.gt(0)&np.isfinite(mu)
 known=valid&valid.shift(1,fill_value=False)&valid.shift(2,fill_value=False)&identity.eq(identity.shift()).fillna(False)&identity.eq(identity.shift(2)).fillna(False)
 right=known&mu.gt(0)&mu.shift(1).gt(0)&mu.shift(2).gt(0)
 ix=K.index.intersection(cal)
 assert np.array_equal(known.loc[ix].to_numpy(),K.loc[ix,sid].to_numpy()),(sid,'M3known')
 assert np.array_equal(right.loc[ix].to_numpy(),RIGHT.loc[ix,sid].to_numpy()),(sid,'M3right')
 np.testing.assert_allclose(mu.loc[ix].to_numpy(),MU.loc[ix,sid].to_numpy(),rtol=0,atol=1e-15,equal_nan=True)
 pv=p.observed_bar.eq(True)&p.price_eligible.eq(True)&p.volume_eligible.eq(True)&p.source_invalid.eq(False)&p.synthetic_event_bar.eq(False)&p.close.gt(0)&np.isfinite(p.close)
 sv=ip.observed_bar.eq(True)&ip.price_eligible.eq(True)&ip.volume_eligible.eq(True)&ip.source_invalid.eq(False)&ip.synthetic_event_bar.eq(False)&ip.close.gt(0)&np.isfinite(ip.close)
 comp=pv&sv&pv.shift(1,fill_value=False)&sv.shift(1,fill_value=False)&identity.eq(identity.shift()).fillna(False)&si.eq(si.shift()).fillna(False)
 assert p.close.dtype==np.dtype('float64') and ip.close.dtype==np.dtype('float64')
 out=relative_clock(p.close.to_numpy(),ip.close.to_numpy(),comp.to_numpy(dtype=bool));out.index=cal
 # Conservative comparable-I epoch. Do not invent original entered/exited events.
 epoch=pd.Series(np.nan,index=cal);e=0;active=False;bad=False;prev_f=None;prev_source=None;inconsistent=0
 for d,fr in f.iterrows():
  ident=identity.loc[d];iq=true(fr.i_target) and np.isfinite(fr.i_floor) and fr.i_floor>0 and np.isfinite(fr.close)
  if not iq:
   active=False;bad=False;prev_f=fr;prev_source=ident;continue
  source_same=prev_source is not None and pd.notna(ident) and pd.notna(prev_source) and ident==prev_source
  if not source_same:active=False;bad=False
  if active and source_same and prev_f is not None and true(prev_f.i_target):
   if fr.i_floor<prev_f.i_floor or fr.close<=prev_f.i_floor:
    bad=True;inconsistent+=1
  if not active:e+=1;active=True
  if not bad:epoch.loc[d]=e
  prev_f=fr;prev_source=ident
 ss=panel.loc[sec,'M3_candidate'].reindex(cal).fillna(-1)
 iq=f.e0_ready.eq(1)&f.g_ready.eq(True)&f.i_target.eq(1)&np.isfinite(f.i_floor)&f.i_floor.gt(0)
 frame=pd.DataFrame(dict(mu5=mu,M3_known=known,M3=right,sectorS=ss,I_qualified=iq,I_continuity_epoch=epoch,close=p.close,raw_close=p.raw_close,i_floor=f.i_floor),index=cal).join(out)
 data[sid]=frame
 for win,w in spec.items():
  if sid not in w['stocks']:continue
  st,en=pd.Timestamp(w['start']),pd.Timestamp(w['end'])
  bd=births[births.window.eq(win)&births.sid.eq(sid)].day;sub=frame.reindex(pd.DatetimeIndex(bd)).copy();sub['day']=sub.index;sub['window']=win;sub['sid']=sid;sub['name']=name;sub['sector']=sec;daily.append(sub.reset_index(drop=True))
  for arm in ['SAME_DAY','CACHED']:
   ev,tr=cached_receipts(frame,st,en,arm=arm,calendar=cal)
   tr=tr[tr.day.between(st,en)&tr.action.ne('NONE')].copy();tr['window']=win;tr['sid']=sid;tr['name']=name;tr['sector']=sec;tr['arm']=arm;traces.append(tr)
   if len(ev):
    ev['window']=win;ev['sid']=sid;ev['name']=name;ev['sector']=sec;ev['arm']=arm;ev['position_assumption']='FLAT_SIGNAL_DIAGNOSTIC_NOT_ACCOUNT'
    ev['old_birth_type']=[oldids.get((win,sid,d),'NONE') for d in ev.day]
    assert ev.loc[ev.receipt_type.eq('DEFERRED'),'old_birth_type'].eq('B_STOCK_BIRTH_DURING_SECTOR').all()
    for idx,row in ev.iterrows():
     d=row.day;fr=frame.loc[d];pp=pvr.loc[(sid,d)] if (sid,d) in pvr.index else None
     ev.loc[idx,'PVR_score']=pp.score if pp is not None else np.nan
     ev.loc[idx,'PVR_known']=bool(pp is not None and pp.state>=0 and pp.valid_observation==True and np.isfinite(pp.score))
     for col in ['close','raw_close','i_floor','mu5','I_continuity_epoch']:ev.loc[idx,col]=fr[col]
    receipts.append(ev)
  re=out.loc[st:en].copy();re=re[re.relative_event.ne(0)]
  re['day']=re.index;re['window']=win;re['sid']=sid;re['name']=name;re['sector']=sec;rels.append(re.reset_index(drop=True))
 qa.append(dict(sid=sid,M3_exact=True,mu_exact_at_1e15=True,I_continuity_inconsistent=inconsistent,relative_known=int(out.relative_known.sum()),relative_UNKNOWN=int((~out.relative_known).sum())))
 print('SHARD',SHARD,'STOCK',sid,len(qa),'/',len(stocks),round(time.monotonic()-starttime,1),flush=True)
ev=pd.concat(receipts,ignore_index=True);tr=pd.concat(traces,ignore_index=True);da=pd.concat(daily,ignore_index=True);re=pd.concat(rels,ignore_index=True)
ev.to_csv(O/('RECEIPTS_'+str(SHARD)+'.csv'),index=False);tr.to_csv(O/('CACHE_TRACE_'+str(SHARD)+'.csv'),index=False);da.to_csv(O/('DAILY_PATHS_'+str(SHARD)+'.csv'),index=False);re.to_csv(O/('RELATIVE_EVENTS_'+str(SHARD)+'.csv'),index=False);pd.DataFrame(qa).to_csv(O/('SOURCE_AND_CLOCK_QA_'+str(SHARD)+'.csv'),index=False)
a=set(map(tuple,ev[ev.arm.eq('SAME_DAY')][['window','sid','day']].to_numpy()));b=set(map(tuple,ev[ev.arm.eq('CACHED')&ev.receipt_type.eq('IMMEDIATE')][['window','sid','day']].to_numpy()));assert a==b
summary=ev.groupby(['window','arm','receipt_type']).size().rename('receipts').reset_index();summary.to_csv(O/('COUNTS_'+str(SHARD)+'.csv'),index=False)
assert all(sha(p)==v for p,v in hashes.items());save('SOURCE_HASHES_'+str(SHARD)+'.'+'json',hashes)
save('QA_'+str(SHARD)+'.'+'json',dict(fixed_stocks=len(stocks),immediate_branches_identical=True,all_deferred_are_originalB=True,all_sources_unchanged=True,no_new_return_labels=True,no_economic_backtest=True,original_M3_exact=True,seconds=time.monotonic()-starttime))
print(summary.to_string(index=False));print('DONE',round(time.monotonic()-starttime,1),flush=True)
