"""Market-clock overlap with original fast CORE/CP, and historical account intersections only."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;E=R/'m3_stock_birth_during_sector_v1';P=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
sources={str(p) for p in [Path(__file__),O/'I_BIRTH_CLOSE_FEASIBILITY.csv',R/'core_stock_selection_dmi_v1/DOMAIN.parquet',R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv',U/'STOCK_MANIFEST.json',H,P/'COMMON_K_COMPARISON.parquet',P/'RIGHT3.parquet',P/'KNOWN3.parquet',P/'WARM_PREFIX_M_R.parquet',P/'WARM_PREFIX_M_K.parquet']}
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
cal=cal[cal<=pd.Timestamp('2026-06-30')];di={d:i for i,d in enumerate(cal)}
rr=pd.concat([pd.read_parquet(P/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(P/'RIGHT3.parquet')]).sort_index().reindex(cal)
kk=pd.concat([pd.read_parquet(P/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(P/'KNOWN3.parquet')]).sort_index().reindex(cal)
panel=pd.read_parquet(P/'COMMON_K_COMPARISON.parquet');sec={s:g.set_index('day').M3_candidate.reindex(cal) for s,g in panel.groupby('sector')}
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
c=pd.read_csv(O/'I_BIRTH_CLOSE_FEASIBILITY.csv');core=pd.read_parquet(R/'core_stock_selection_dmi_v1/DOMAIN.parquet')
mobile=pd.read_parquet(R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet')
assert 'day' in mobile and 'sid' in mobile
mobile=mobile[mobile.account.eq('PVR')].copy()
first=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv',usecols=['account','sid','signal_day','entry_day','first_kind'])
first=first[first.account.eq('PVR')]
corekey=set(zip(core.sid,core.day));mobilekey=set(zip(mobile.sid,mobile.day))
firstkey=set(zip(first.sid,first.signal_day));corefill=set(zip(first[first.first_kind.eq('core')].sid,first[first.first_kind.eq('core')].signal_day));mobilefill=set(zip(first[first.first_kind.eq('add')].sid,first[first.first_kind.eq('add')].signal_day))
rows=[]
for sid,g in c.groupby('sid'):
 m=manifest[sid];fp=m['refs']['facts'];cp=m['refs']['CP1'];sources.update([fp,cp]);assert sha(fp)==m['output_sha256'][fp] and sha(cp)==m['output_sha256'][cp]
 f=pd.read_parquet(fp).reindex(cal);p=pd.read_parquet(cp).reindex(cal);s=sec[g.iloc[0].sector]
 active=f.i_target.eq(1).fillna(False)&f.segment_id.notna()
 same=f.segment_id.eq(f.segment_id.shift()).fillna(False)
 joint=s.eq(1)&rr[sid].eq(True)&kk[sid].eq(True)
 for r in g.itertuples():
  t=pd.Timestamp(r.day);k=di[t];end=k+1
  while end<len(cal) and active.iloc[end] and same.iloc[end]:end+=1
  jend=k+1
  while jend<end and joint.iloc[jend]:jend+=1
  days=cal[k:end];jointdays=cal[k:jend]
  cptrue=p.receipt.eq(True).fillna(False)
  cpknown=p.receipt.notna()
  latercp=days[cptrue.reindex(days).to_numpy(dtype=bool)&(days>t)]
  jointcp=jointdays[cptrue.reindex(jointdays).to_numpy(dtype=bool)&(jointdays>t)]
  laterbuy=days[f.i_buy.eq(True).fillna(False).reindex(days).to_numpy(dtype=bool)&(days>t)]
  oldcore=core[core.sid.eq(sid)&core.day.ge(r.day)&core.day.lt(str(cal[end].date()) if end<len(cal) else '9999-12-31')]
  oldmob=mobile[mobile.sid.eq(sid)&mobile.day.ge(r.day)&mobile.day.lt(str(cal[end].date()) if end<len(cal) else '9999-12-31')]
  oldfill=first[first.sid.eq(sid)&first.signal_day.ge(r.day)&first.signal_day.lt(str(cal[end].date()) if end<len(cal) else '9999-12-31')]
  rows.append(dict(day=r.day,sid=sid,name=r.name,sector=r.sector,residual_close_proxy=bool(r.baseline_residual_slot_proxy),same_day_i_buy=bool(f.at[t,'i_buy']),same_day_CP=bool(cptrue.at[t]),same_day_CP_known=bool(cpknown.at[t]),root_end=str(cal[end].date()) if end<len(cal) else None,root_end_reason='I_OFF' if end<len(cal) and f.i_target.iloc[end]==0 else 'UNKNOWN_OR_SOURCE_GAP' if end<len(cal) else 'DATA_END',same_root_later_CP=len(latercp),first_later_CP=str(latercp[0].date()) if len(latercp) else None,first_later_CP_lag=di[latercp[0]]-k if len(latercp) else None,continuous_joint_later_CP=len(jointcp),first_continuous_joint_CP=str(jointcp[0].date()) if len(jointcp) else None,same_root_later_i_buy=len(laterbuy),first_later_i_buy=str(laterbuy[0].date()) if len(laterbuy) else None,same_root_CP_unknown_days=int((~cpknown.reindex(days)).sum()),old_legal_CORE_same_day=(sid,r.day) in corekey,old_legal_empty_MOBILE_same_day=(sid,r.day) in mobilekey,old_actual_CORE_first_same_day=(sid,r.day) in corefill,old_actual_MOBILE_first_same_day=(sid,r.day) in mobilefill,old_legal_CORE_same_root_any=len(oldcore)>0,old_legal_empty_MOBILE_same_root_any=len(oldmob)>0,old_actual_first_same_root_any=len(oldfill)>0))
z=pd.DataFrame(rows)
assert len(z)==825 and z.same_day_i_buy.all()
z.to_csv(O/'FAST_CP_OVERLAP.csv',index=False)
def summ(g):
 return dict(n=len(g),same_day_i_buy=int(g.same_day_i_buy.sum()),same_day_CP=int(g.same_day_CP.sum()),same_day_CP_unknown=int((~g.same_day_CP_known).sum()),later_CP_within_same_I=int(g.same_root_later_CP.gt(0).sum()),same_day_or_later_CP_same_I=int((g.same_day_CP|g.same_root_later_CP.gt(0)).sum()),later_CP_while_S_M3_continuously_true=int(g.continuous_joint_later_CP.gt(0).sum()),median_first_later_CP_lag=float(g.first_later_CP_lag.median()),later_i_buy_same_I=int(g.same_root_later_i_buy.gt(0).sum()),old_legal_CORE_same_day=int(g.old_legal_CORE_same_day.sum()),old_legal_empty_MOBILE_same_day=int(g.old_legal_empty_MOBILE_same_day.sum()),old_actual_CORE_first_same_day=int(g.old_actual_CORE_first_same_day.sum()),old_actual_MOBILE_first_same_day=int(g.old_actual_MOBILE_first_same_day.sum()),old_legal_CORE_same_root_any=int(g.old_legal_CORE_same_root_any.sum()),old_legal_empty_MOBILE_same_root_any=int(g.old_legal_empty_MOBILE_same_root_any.sum()),old_actual_first_same_root_any=int(g.old_actual_first_same_root_any.sum()))
summary={'all825':summ(z),'residual_close_proxy':summ(z[z.residual_close_proxy]),'limits':['825/515 are market/old-baseline slot probes, not orders or fills.','Old legal and actual intersections use previous PVR account state, industry E0/stage/H1 and budgets, with old rights coverage. Not counterfactual execution of new C.','Future same-root CP/i_buy dates are descriptive clock-overlap labels only, never trigger inputs.','C_I is a strict subset of existing market i_buy; no new alpha or underlying evidence.']}
save(O/'FAST_CP_OVERLAP_SUMMARY.json',summary);save(O/'FAST_CP_SOURCE_HASHES.json',{p:sha(p) for p in sorted(sources)})
save(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,indent=2))
