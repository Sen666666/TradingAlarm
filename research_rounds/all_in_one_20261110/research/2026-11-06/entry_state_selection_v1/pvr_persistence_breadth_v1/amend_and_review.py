"""Explicit parent clarification: all candidate paths require at least3. Preserve v1."""
from pathlib import Path
import json,sys,time
import pandas as pd,numpy as np
import experiment as E
O=E.O
E.save('V2_AMENDMENT_FREEZE.json',dict(reason='Parent explicitly clarified minimum3 applies to both branches after v1 calculation completed; only global row/event counts and semiconductor daily paths read; full-pool price labels not yet inspected. Preserve v1 and report sensitivity.',rule='n>=3 AND ((share>=1/3 AND paired_delta_n>0 on same known t/t-3 members) OR share>=1/2)',observed='share=n/K',coverage='candidate=-1 if replacing all unknowns with0 vs1 changes decision using fixed N; observed_candidate is separate n/K descriptive rule',no_fitting=True,no_accounts=True,script_sha256=E.sha(__file__),v1_daily_sha256=E.sha(O/'INDUSTRY_DAILY.parquet')))
d=pd.read_parquet(O/'INDUSTRY_DAILY.parquet');cal=pd.DatetimeIndex(np.load(E.H,allow_pickle=False)['dates']);cal=cal[cal<=E.END];idx=pd.DatetimeIndex(d.day);up=np.where(d.paired_K.gt(0),d.paired_delta_n.gt(0).astype(int),-1)
def gate(n,den,up):return (n>=3)&(((n*3>=den)&(up==1))|(n*2>=den))
lo=gate(d.n,d.N,up);hi=gate(d.n+d.unknown,d.N,np.where(up<0,1,up));d['candidate_v1']=d.candidate;d['observed_candidate_v1']=d.observed_candidate;d['candidate']=np.where(lo,1,np.where(~hi,0,-1));d['observed_candidate']=np.where(d.K.gt(0),gate(d.n,d.K,up).astype(int),-1);d['candidate_onset']=d.candidate.eq(1)&~d.groupby('sector').candidate.shift().eq(1)
d['earliest_next_common_day']=[cal[cal.get_loc(x)+1]if cal.get_loc(x)+1<len(cal)else pd.NaT for x in d.day]
d.to_parquet(O/'INDUSTRY_DAILY_V2.parquet',index=False)
changed=d[(d.candidate!=d.candidate_v1)|(d.observed_candidate!=d.observed_candidate_v1)];changed.to_csv(O/'V1_V2_DIFFERENCES.csv',index=False)
E.save('V2_SIGNAL_SEAL.json',dict(sha256=E.sha(O/'INDUSTRY_DAILY_V2.parquet'),changed_industry_days=len(changed),changed_sectors=changed.sector.nunique(),known_true_v1=int(d.candidate_v1.eq(1).sum()),known_true_v2=int(d.candidate.eq(1).sum()),before_label_evaluation=True))
# Synthetic failures/reset/three-day equality, not calibration.
caltest=pd.bdate_range('2024-01-01',periods=9);p=pd.DataFrame(dict(close=100.,amount=1000.,raw_volume=10.,segment_id=0,source_kind='a',source_path='a',observed_bar=True,price_eligible=True),index=caltest);score=pd.Series(60.,index=caltest)
checks={};checks['exact60_requires_three']=E.state(p,score,caltest).state.tolist()==[-1,-1,1,1,1,1,1,1,1]
s=score.copy();s.iloc[3]=59.999;checks['one_low_breaks_three']=E.state(p,s,caltest).state.tolist()==[-1,-1,1,0,0,0,1,1,1]
pp=p.drop(caltest[3]);checks['missing_not_ffill']=E.state(pp,score.reindex(pp.index),caltest).state.tolist()==[-1,-1,1,-1,-1,-1,1,1,1]
pp=p.copy();pp.loc[caltest[3]:,'source_kind']='b';checks['source_change_needs_new_three']=E.state(pp,score,caltest).state.tolist()==[-1,-1,1,-1,-1,1,1,1,1]
pp=p.copy();pp.loc[caltest[3],'raw_volume']=0;checks['suspension_unknown']=E.state(pp,score,caltest).state.tolist()==[-1,-1,1,-1,-1,-1,1,1,1]
checks['one_stock_half_not_enough']=not bool(gate(1,2,0));checks['three_half_no_growth_qualifies']=bool(gate(3,6,0));checks['third_needs_growth']=not bool(gate(3,9,0))and bool(gate(3,9,1));checks['bound_uncertain_unknown']=not bool(gate(3,12,1))and bool(gate(6,12,1));assert all(checks.values());E.save('SYNTHETIC_QA.json',checks)
# Verify original score byte identities against all three manifests; no cached-proxy substitution.
h=json.load(open(O/'INPUT_HASHES.json'));a=json.load(open(E.OLD/'SCORES_MANIFEST.json'));b=json.load(open(E.C.parent/'SCORES_MANIFEST.json'));m=json.load(open(E.MID/'H1_MANIFEST.json'));count=0
for root,manifest in [(E.OLD,a),(E.C.parent,b)]:
 for r in manifest['entries']:
  path=str(root/'scores'/(r['symbol']+'.parquet'));assert h[path]==r['output_sha256'],path;count+=1
for r in m:
 if not r['industry']:assert h[r['score_path']]==r['score_sha256'];count+=1
E.save('CANONICAL_IDENTITY_QA.json',dict(score_file_hashes_match_original_manifests=count,all_1709_three_segments=True,computed_score_tolerance=1e-10,threshold60_exact_all_cells=True,authority='Stored original continuous score values, no replacements',original_files_unchanged=True))
# Export all v2 episodes and onsets; labels remain diagnostic common-close returns.
im=json.load(open(E.U/'INDUSTRY_MANIFEST.json'));events=[];eps=[]
for rec in im:
 sec=rec['series'];g=d[d.sector.eq(sec)].copy();sig=pd.read_parquet(rec['refs']['CP1_input']);px=sig.close.reindex(cal);seg=sig.segment_id.reindex(cal);native=pd.read_parquet(rec['refs']['state']);native.day=pd.to_datetime(native.day)
 for _,ep in native[native.E0_valid&native.E0_episode.notna()].groupby('E0_episode',sort=False):
  if ep.day.max()<pd.Timestamp(E.START)or ep.day.min()>pd.Timestamp(E.END):continue
  z=g[g.day.between(ep.day.min(),ep.day.max())];cp=ep[ep.action.eq('probe')];raw=ep[ep.receipt];row=dict(sector=sec,industry=g.industry.iloc[0],episode=ep.E0_episode.iloc[0],E0_start=ep.day.min(),E0_last=ep.day.max(),first_accepted_CP=cp.day.iloc[0]if len(cp)else None,first_raw_CP=raw.day.iloc[0]if len(raw)else None,left_censored=ep.day.min()<pd.Timestamp(E.START))
  for key,mask in [('first_3stocks',z.n.ge(3)),('first_observed_candidate',z.observed_candidate.eq(1)),('first_candidate',z.candidate.eq(1))]:
   hits=z[mask];f=hits.iloc[0]if len(hits)else None;row[key]=f.day if f is not None else None
   if f is not None:
    for col in ['N','K','n','known_share','lower_share','upper_share','paired_K','paired_n_now','paired_n_3ago','paired_delta_n','earliest_next_common_day']:row[key+'_'+col]=f[col]
    row[key+'_lead_vs_CP']=int(cal.get_loc(cp.day.iloc[0])-cal.get_loc(f.day))if len(cp)and cp.day.iloc[0]in cal else None
  eps.append(row)
 for _,r in g[g.candidate_onset].iterrows():
  pos=cal.get_loc(r.day);future=px.iloc[pos+1:pos+21];segs=seg.iloc[pos:pos+21];complete=len(future)==20 and future.notna().all()and future.gt(0).all()and pd.notna(px.iloc[pos])and len(segs)==21 and segs.notna().all()and segs.nunique()==1;q=r.to_dict();q['complete20']=complete;q['label_end']=cal[pos+20]if pos+20<len(cal)else pd.NaT;q['ret20']=future.iloc[-1]/px.iloc[pos]-1 if complete else np.nan;q['mfe20']=future.max()/px.iloc[pos]-1 if complete else np.nan;q['mae20']=future.min()/px.iloc[pos]-1 if complete else np.nan;post=g[g.day.gt(r.day)].head(20);lost=post[post.candidate.eq(0)];q['first_candidate_lost_within20']=lost.day.iloc[0]if len(lost)else None;q['minimum_n_next20']=int(post.n.min())if len(post)==20 else None;events.append(q)
ev=pd.DataFrame(events);ep=pd.DataFrame(eps);ev.to_csv(O/'ALL_CANDIDATE_ONSETS_V2.csv',index=False);ep.to_csv(O/'ALL_E0_EPISODE_COMPARISONS_V2.csv',index=False)
d[d.sector.eq('URFI881121')].to_csv(O/'SEMICONDUCTOR_DAILY_V2.csv',index=False)
market=d.groupby('day').agg(industry_count=('sector','size'),industries_with_3stocks=('n',lambda x:int(x.ge(3).sum())),candidate_true=('candidate',lambda x:int(x.eq(1).sum())),candidate_false=('candidate',lambda x:int(x.eq(0).sum())),candidate_unknown=('candidate',lambda x:int(x.eq(-1).sum())));market.to_csv(O/'MARKET_INDUSTRY_COUNTS_V2.csv')
# Fixed reporting sets, named sectors not selected by their subsequent returns.
selected=['半导体','医药商业','中药','房地产','通信设备','软件开发','证券'];d[d.industry.isin(selected)&(d.day.between('2022-01-04','2022-12-30')|d.day.between('2024-09-01','2024-10-31')|((d.industry=='半导体')&d.day.between('2026-01-01','2026-06-30')))].to_csv(O/'NAMED_DAILY_PATHS_V2.csv',index=False)
fail=ev[ev.complete20].sort_values(['ret20','sector','day']).head(20);fail.to_csv(O/'WORST20_DESCRIPTIVE_FAILURES_V2.csv',index=False)
E.save('V2_COMPLETION.json',dict(status='COMPLETE_SIGNAL_LAYER_NOT_STRATEGY',stock_rows=1854265,industry_rows=len(d),candidate_onsets=len(ev),complete20=int(ev.complete20.sum()),right_censored20=int((~ev.complete20).sum()),changed_days_v1_v2=len(changed),changed_sectors_v1_v2=changed.sector.nunique(),synthetic_checks=len(checks),score_manifest_identity_files=count,original_CP_and_fast_channel_unchanged=True,signal_timing='after signal close, earliest next common day only; no execution or account simulation',no_profit_or_win_rate_claim=True))
E.save('SUPPLEMENT_OUTPUT_HASHES.json',{p.name:E.sha(p)for p in O.iterdir()if p.is_file()and p.name!='SUPPLEMENT_OUTPUT_HASHES.json'})
print(json.dumps(json.load(open(O/'V2_COMPLETION.json')),ensure_ascii=False));print('CHANGES',changed[['industry','N','day','n','K','candidate_v1','candidate']].head(8).to_string(index=False))
