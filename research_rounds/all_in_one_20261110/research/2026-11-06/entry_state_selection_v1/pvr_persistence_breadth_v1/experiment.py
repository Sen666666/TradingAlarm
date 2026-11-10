"""Frozen PVR>=60 on three common sessions. Signal diagnostics only, never orders."""
from pathlib import Path
import sys,json,hashlib,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money')
F=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py')
C=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/scores')
H=M/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'
META=M/'research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json'
OLD=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full')
MID=R/'account_comparison_continuous_v1/inputs'
CURRENT=M/'TradingAlarm/runtime/market/update-20261106-153022-0641f0/prepared'
sys.dont_write_bytecode=True;sys.path.insert(0,str(F.parent));from features import original_observation_clock
FORMULA=U.parent/'pvr-current-v3-information-capital-20261101/original_score_function.py'
env=dict(np=np,pd=pd);exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),env);original_pvr=env['score']
START='2022-01-04';END='2026-06-30';CUTS=['2022-06-30','2024-09-24','2026-05-15']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,float)and not np.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def state(p,score,cal):
 a=score.reindex(cal);v,b=original_observation_clock(p)
 ok=v.reindex(cal).fillna(False).astype(bool)&a.notna()
 if 'raw_volume' in p:ok &=p.raw_volume.reindex(cal).gt(0)
 seg=p.segment_id.reindex(cal).astype(float)
 identity=seg.astype('string')
 for col in ['source_kind','source_path']:
  if col in p:identity=identity+'|'+p[col].reindex(cal).astype('string')
 full=ok.rolling(3,min_periods=3).sum().eq(3)
 same=identity.eq(identity.shift(1)).fillna(False)&identity.eq(identity.shift(2)).fillna(False)
 known=full&same
 out=pd.DataFrame(index=cal);out['score']=a;out['state']=np.where(known,a.rolling(3,min_periods=3).min().ge(60).astype(int),-1).astype('int8')
 out['reason']=np.where(known,'KNOWN',np.where(~full,'UNKNOWN_MISSING_INVALID_OR_WARMUP','UNKNOWN_SOURCE_CHANGE'))
 out['source_segment']=seg;out['valid_observation']=ok;return out

def aggregate(st,meta,im,cal):
 rows=[]
 for rec in im:
  sec=rec['series'];ids=[s for s in st.columns if meta.get(s,{}).get('sector_id')==sec]
  if not ids:continue
  x=st[ids];known=x.ge(0);N=len(ids);K=known.sum(axis=1);n=x.eq(1).sum(axis=1);prior=x.shift(3);both=known&prior.ge(0);J=both.sum(axis=1);nc=(x.eq(1)&both).sum(axis=1);npast=(prior.eq(1)&both).sum(axis=1);diff=nc-npast
  a=pd.DataFrame(dict(day=cal,sector=sec,industry=meta[ids[0]]['industry'],N=N,K=K,n=n,unknown=N-K,known_share=n/K.replace(0,np.nan),lower_share=n/N,upper_share=(n+N-K)/N,paired_K=J,paired_n_now=nc,paired_n_3ago=npast,paired_delta_n=diff,paired_delta_share=diff/J.replace(0,np.nan)))
  rising=np.where(J.gt(0),diff.gt(0).astype(int),-1)
  def gate(count,den,up):return ((count>=3)&(count*3>=den)&(up==1))|(count*2>=den)
  lower=gate(n,N,rising);upper=gate(n+N-K,N,np.where(rising<0,1,rising))
  a['observed_candidate']=np.where(K.gt(0),gate(n,K,rising).astype(int),-1)
  a['candidate']=np.where(lower,1,np.where(~upper,0,-1))
  native=pd.read_parquet(rec['refs']['state']).set_index('day');native.index=pd.to_datetime(native.index)
  for c in ['close','E0_valid','E0_episode','receipt','action','authorization_usable']:a['original_sector_'+c]=native[c].reindex(cal).to_numpy()
  a['candidate_onset']=a.candidate.eq(1)&~a.candidate.shift().eq(1)
  rows.append(a.reset_index(drop=True))
 return pd.concat(rows,ignore_index=True)

def main():
 t=time.monotonic();sm=json.load(open(U/'STOCK_MANIFEST.json'));im=json.load(open(U/'INDUSTRY_MANIFEST.json'));meta=json.load(open(META))['security_metadata'];assert len(sm)==1709 and len(im)==90
 ids=sorted(r['symbol']for r in sm);mapping={s:meta.get(s,{}) for s in ids};calall=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);calall=calall[calall<=END];cal=calall[calall>=pd.Timestamp('2021-12-01')]
 source={str(p):sha(p)for p in [Path(__file__),F,FORMULA,H,META,OLD/'SCORES_MANIFEST.json',MID/'H1_MANIFEST.json',C.parent/'SCORES_MANIFEST.json',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',CURRENT/'manifest.json']}
 freeze=dict(version='pvr_persistence_breadth_v1',frozen_before_computation=True,score_authority='Original continuous account score files: 2024_full + continuous inputs missing2025H1 + slot1 2025H2..2026H1. Read unchanged original values; recomputation tolerance1e-10 and every >=60 decision exact; original physical prefix recomputation exact. Legacy daily cache rejected.',start=START,end=END,ids=ids,membership='fixed original 1709 stock pool and current known mapping; not PIT, future-listed/missing members remain UNKNOWN; 90 original industries, no re-selection',stock_rule='At close t: original PVR score >=60 on t,t-1,t-2 COMMON market sessions; three finite valid observed rows and identical segment/source kind/source path. Any missing/invalid/suspension/warmup or source change => UNKNOWN(-1), overriding a low score elsewhere in window; otherwise any score<60=>0; otherwise1. No ffill. Uses original 21/.9 smoothed PVR, not 3 independent observations.',breadth='N fixed members, K full known stocks, n state1, observed n/K plus conservative full-member n/N..(n+N-K)/N. Difference t vs t-3 uses exactly intersection known both dates, counts and fractions; not changing denominators.',candidate='Separate diagnostic only: >=3 stocks and share>=1/3 and paired breadth increase, OR share>=1/2. Report observed rule on K and robust three-valued rule from full-member lower/upper bounds; unknown threshold=>UNKNOWN. No arbitrary readiness gate imposed; preserve original CP and quick channel unchanged.',labels='Predeclared industry adjusted-close paths: return t+20 / close_t -1; future min/max close over exactly next20 common sessions /close_t -1. Only all20 available same industry source segment, no ffill. Frozen June30 end, right-censored=>UNKNOWN. Diagnostic not executable returns/net PnL. Failure examples selected transparently among all candidate onsets with complete20, sorted ret20 ascending; all events retained.',cuts=CUTS,case_windows={'2022':['2022-01-04','2022-12-30'],'2024_924':['2024-09-01','2024-10-31'],'semiconductor_H1':['2026-01-01','2026-06-30']},source_hashes=source,no_accounts=True,no_parameter_search=True)
 save('FREEZE.json',freeze);pd.DataFrame([dict(sid=s,**mapping[s])for s in ids]).to_csv(O/'FIXED_MEMBERSHIP.csv',index=False)
 states={};scores={};audits=[];prefix=[];parts=[];semipvr=pd.read_parquet(R/'semiconductor_h1_scope_v1/PVR_DAILY.parquet');semipvr.day=pd.to_datetime(semipvr.day)
 # Prioritize semiconductor only for first delivery. Universe/algorithm unchanged.
 sm=sorted(sm,key=lambda r:(meta.get(r['symbol'],{}).get('sector_id')!='URFI881121',r['symbol']))
 for j,rec in enumerate(sm):
  sid=rec['symbol'];sp=Path(next(x for x in rec['source_sha256']if x.endswith('/signal.parquet')));source[str(sp)]=sha(sp);assert source[str(sp)]==rec['source_sha256'][str(sp)]
  p=pd.read_parquet(sp).loc[:END];z=original_pvr(p)
  cachepaths=[OLD/'scores'/(sid+'.parquet'),MID/'scores'/(sid+'.parquet'),C/(sid+'.parquet')];pieces=[pd.read_parquet(x).score for x in cachepaths];canonical=pd.concat([pieces[0],pieces[1],pieces[2].loc['2025-07-01':]]).loc[:END];assert canonical.index.is_unique
  for cp in cachepaths:source[str(cp)]=sha(cp)
  ix=p.index.intersection(canonical.index);np.testing.assert_allclose(z.score.reindex(ix),canonical.reindex(ix),rtol=0,atol=1e-10,equal_nan=True);assert z.score.reindex(ix).ge(60).equals(canonical.reindex(ix).ge(60));maxerr=(z.score.reindex(ix)-canonical.reindex(ix)).abs().max()
  authority=z.score.copy();authority.loc[ix]=canonical.reindex(ix);np.testing.assert_equal(authority.reindex(ix).to_numpy(),canonical.reindex(ix).to_numpy());out=state(p,authority,cal)
  semi=meta.get(sid,{}).get('sector_id')=='URFI881121'
  if semi:
   cp=CURRENT/'signals'/(sid+'.parquet');new=pd.read_parquet(cp).loc[:END];cols=['open','high','low','close','raw_open','raw_close','raw_volume','amount','segment_id','price_eligible','observed_bar','source_invalid','synthetic_event_bar'];pd.testing.assert_frame_equal(p[cols],new[cols],check_exact=True,check_dtype=False,check_freq=False);source[str(cp)]=sha(cp)
   old=semipvr[semipvr.sid.eq(sid)].set_index('day');np.testing.assert_equal(authority.reindex(old.index).to_numpy(),old.score.to_numpy())
  for cut in CUTS:
   c=pd.Timestamp(cut);zz=original_pvr(p.loc[:c]);pd.testing.assert_frame_equal(zz,z.loc[:c],check_exact=True);zz.score=authority.loc[:c];oo=state(p.loc[:c],zz.score,cal[cal<=c]);pd.testing.assert_frame_equal(oo,out.loc[:c],check_exact=True);prefix.append(dict(sid=sid,cut=cut,rows=len(oo),exact=True))
  states[sid]=out.state;scores[sid]=out.score;out['sid']=sid;out['day']=out.index;out['sector']=meta.get(sid,{}).get('sector_id');parts.append(out.loc[START:].reset_index(drop=True))
  audits.append(dict(sid=sid,source_rows=len(p),cache_overlap_rows=len(ix),canonical_score_cells_exact=True,recomputed_score_max_abs_error=maxerr,threshold60_decisions_exact=True,semiconductor_latest_source_and_H1_PVR_exact=semi,known=int(out.loc[START:,'state'].ge(0).sum()),positive=int(out.loc[START:,'state'].eq(1).sum())))
  if (j+1)==126:
   partial=aggregate(pd.DataFrame(states).reindex(cal),meta,[r for r in im if r['series']=='URFI881121'],cal);partial=partial[partial.day.ge(START)];partial.to_csv(O/'SEMICONDUCTOR_FIRST_RESULT.csv',index=False);print('FIRST_SEMICONDUCTOR',partial[partial.day.isin(pd.to_datetime(['2026-01-05','2026-03-03','2026-04-08','2026-04-17','2026-06-11','2026-06-16','2026-06-30']))][['day','N','K','n','known_share','paired_delta_n','candidate','original_sector_action']].to_string(index=False),flush=True)
  if (j+1)%200==0:print('PROGRESS',j+1,round(time.monotonic()-t,1),flush=True)
 st=pd.DataFrame(states).reindex(cal);daily=aggregate(st,meta,im,cal);daily=daily[daily.day.ge(START)].reset_index(drop=True)
 pd.concat(parts,ignore_index=True).to_parquet(O/'STOCK_DAILY.parquet',index=False);daily.to_parquet(O/'INDUSTRY_DAILY.parquet',index=False);daily[daily.sector.eq('URFI881121')].to_csv(O/'SEMICONDUCTOR_DAILY.csv',index=False)
 for cut in CUTS:
  aa=aggregate(st.loc[:cut],meta,im,cal[cal<=cut]);aa=aa[aa.day.ge(START)].reset_index(drop=True);bb=daily[daily.day.le(cut)].reset_index(drop=True);pd.testing.assert_frame_equal(aa,bb,check_exact=True)
 save('SIGNAL_SEAL.json',dict(stock_daily_sha256=sha(O/'STOCK_DAILY.parquet'),industry_daily_sha256=sha(O/'INDUSTRY_DAILY.parquet'),frozen_before_labels=True,seconds=time.monotonic()-t))
 # Sector future labels loaded only after seal; causal signal never consumes these.
 events=[];eps=[]
 for rec in im:
  sec=rec['series'];g=daily[daily.sector.eq(sec)].copy();sig=pd.read_parquet(rec['refs']['CP1_input']);px=sig.close.reindex(calall);seg=sig.segment_id.reindex(calall);native=pd.read_parquet(rec['refs']['state']);native.day=pd.to_datetime(native.day);source[rec['refs']['CP1_input']]=sha(rec['refs']['CP1_input']);source[rec['refs']['state']]=sha(rec['refs']['state'])
  for _,ep in native[native.E0_valid&native.E0_episode.notna()].groupby('E0_episode',sort=False):
   if ep.day.max()<pd.Timestamp(START)or ep.day.min()>pd.Timestamp(END):continue
   a=g[g.day.between(ep.day.min(),ep.day.max())];positive=a[a.n.gt(0)];cand=a[a.candidate.eq(1)];cp=ep[ep.action.eq('probe')];raw=ep[ep.receipt];first=cand.iloc[0]if len(cand)else None
   row=dict(sector=sec,industry=meta[next(s for s in ids if meta.get(s,{}).get('sector_id')==sec)]['industry'],episode=ep.E0_episode.iloc[0],E0_start=ep.day.min(),E0_end=ep.day.max(),left_censored=ep.day.min()<pd.Timestamp(START),first_any_persistent=positive.day.iloc[0]if len(positive)else None,first_candidate=first.day if first is not None else None,first_accepted_CP=cp.day.iloc[0]if len(cp)else None,first_raw_CP=raw.day.iloc[0]if len(raw)else None)
   if first is not None:
    for col in ['N','K','n','known_share','lower_share','upper_share','paired_K','paired_delta_n']:row[col]=first[col]
    row['lead_common_sessions_vs_CP']=int(calall.get_loc(cp.day.iloc[0])-calall.get_loc(first.day))if len(cp)and cp.day.iloc[0]in calall else None
   eps.append(row)
  for _,row in g[g.candidate_onset].iterrows():
   d=row.day;pos=calall.get_loc(d);future=px.iloc[pos+1:pos+21];segments=seg.iloc[pos:pos+21];complete=len(future)==20 and future.notna().all()and future.gt(0).all()and pd.notna(px.iloc[pos])and len(segments)==21 and segments.notna().all()and segments.nunique()==1
   q=row.to_dict();q['complete20']=complete;q['label_end']=calall[pos+20]if pos+20<len(calall)else pd.NaT
   for name,value in [('ret20',future.iloc[-1]/px.iloc[pos]-1 if complete else np.nan),('mfe20',future.max()/px.iloc[pos]-1 if complete else np.nan),('mae20',future.min()/px.iloc[pos]-1 if complete else np.nan)]:q[name]=value
   post=g[g.day.gt(d)].head(20);fail=post[post.candidate.eq(0)];q['first_candidate_lost_within20']=fail.day.iloc[0]if len(fail)else None;q['minimum_n_next20']=int(post.n.min())if len(post)==20 else None;events.append(q)
 ev=pd.DataFrame(events);ep=pd.DataFrame(eps);ev.to_csv(O/'ALL_CANDIDATE_ONSETS_WITH_LABELS.csv',index=False);ep.to_csv(O/'ALL_E0_EPISODE_COMPARISONS.csv',index=False);pd.DataFrame(audits).to_csv(O/'SOURCE_EXACT_AUDITS.csv',index=False);pd.DataFrame(prefix).to_csv(O/'PREFIX_CHECKS.csv',index=False)
 save('INPUT_HASHES.json',source);assert all(sha(p)==h for p,h in source.items());save('SUMMARY.json',dict(status='COMPLETE_SIGNAL_ONLY',seconds=time.monotonic()-t,stocks=len(ids),sectors=daily.sector.nunique(),common_dates=daily.day.nunique(),stock_rows=sum(len(x)for x in parts),industry_rows=len(daily),stock_prefix_checks=len(prefix),industry_prefix_checks=len(CUTS),source_files=len(source),sources_unchanged=True,unknown_stock_rows=sum(int(x.state.lt(0).sum())for x in parts),candidate_onsets=len(ev),complete20_onsets=int(ev.complete20.sum()),no_account_run=True))
 save('OUTPUT_HASHES.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_HASHES.json'});print('DONE',json.dumps(clean(json.load(open(O/'SUMMARY.json'))),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
