from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,ast,sys
O=Path(__file__).resolve().parent;B=O.parent/'selection_entry_diagnosis_v1'
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
f=pd.read_csv(O/'ACTUAL_ROUND_ASSOCIATION.csv');m=f[f.first_kind.eq('add')];out=[]
for per,g in [('ALL',m)]+[(str(y),m[m.year.eq(y)]) for y in [2022,2023,2024,2025,2026]]:
 for group,z in [('all_original_mobile_firsts',g),('base_top20_mobile',g[g.PVR_chosen]),('retained_original_top20_mobile',g[g.PVR_chosen&g.ATTR_chosen]),('lost_original_top20_mobile',g[g.PVR_chosen&~g.ATTR_chosen])]:
  c=z[z.closed];out.append(dict(period=per,group=group,n=len(z),closed=len(c),wins=int(c.round_pnl.gt(0).sum()),net_winrate=c.round_pnl.gt(0).mean(),pnl=c.round_pnl.sum(),positive_pnl=c.loc[c.round_pnl.gt(0),'round_pnl'].sum(),cross_year=int((c.closed_day.str[:4]!=c.entry_day.str[:4]).sum())))
pd.DataFrame(out).to_csv(O/'MOBILE_FIRST_ROUND_ASSOCIATION_SUMMARY.csv',index=False)
meta=json.load(open('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
assert meta['300666.SZ']['industry']=='半导体' and meta['301611.SZ']['industry']=='半导体' and meta['688603.SH']['industry']=='电子化学品'
a=pd.read_parquet(O/'ALL_CANDIDATES_WITH_LABELS.parquet');moves=pd.read_csv(O/'RANK_MOVES.csv');a=a.merge(moves[['sid','day','old_rank','new_rank']],on=['sid','day'],validate='one_to_one')
a[a.day.between('2026-01-01','2026-03-31')&a.sector.eq('URFI881121')].to_csv(O/'SEMICONDUCTOR_2026Q1_CANDIDATES.csv',index=False)
a[a.day.between('2026-01-01','2026-03-31')&a.sector.eq('URFI881172')].to_csv(O/'ELECTRONIC_CHEMICAL_2026Q1_CANDIDATES.csv',index=False)
sel=pd.read_parquet(O/'SELECTIONS_WITH_LABELS.parquet');sem=[]
for sec,label in [('URFI881121','半导体'),('URFI881172','电子化学品')]:
 q=a[a.day.between('2026-01-01','2026-03-31')&a.sector.eq(sec)];v=sel[sel.day.between('2026-01-01','2026-03-31')&sel.sector.eq(sec)]
 for st,g in v.groupby('strategy'):
  row=dict(sector=sec,industry=label,strategy=st,candidates=len(q),candidate_dates=q.day.nunique(),selected=len(g),selected_dates=g.day.nunique(),changed_out=int((q.old_rank.le(20)&q.new_rank.gt(20)).sum()),changed_in=int((q.old_rank.gt(20)&q.new_rank.le(20)).sum()))
  for h in [5,20,60]:
   z=g[g['strict'+str(h)]];row.update({f'complete{h}':len(z),f'event_mean{h}':z['ret'+str(h)].mean(),f'price_winrate{h}':z['ret'+str(h)].gt(0).mean()})
  sem.append(row)
pd.DataFrame(sem).to_csv(O/'2026Q1_SECTOR_DETAIL.csv',index=False)
# Formula/coordinate tail audit without changing any score or ranking.
sys.path.insert(0,'/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design');from features import original_pvr,original_observation_clock
code=ast.parse((O/'compute.py').read_text());fn=next(n for n in code.body if isinstance(n,ast.FunctionDef) and n.name=='compute');W=.9**np.arange(20,-1,-1);W/=W.sum()
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);calmap={d:i for i,d in enumerate(cal)}
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(O/'compute.py'),'exec'))
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={x['symbol']:x for x in json.loads(M.read_text())};stats=[];full_ext=[];parts=[];numeric=[]
for sid in sorted(a.sid.unique()):
 x=manifest[sid];p=next(p for p in x['source_sha256'] if p.endswith('/signal.parquet'));f0=pd.read_parquet(p).loc[:'2026-05-15'];z=compute(f0)
 raw_n=np.log(f0.raw_open)-np.log(f0.raw_close.shift());fac_n=np.log(f0.adjustment_factor)-np.log(f0.adjustment_factor.shift());err=float((z.n-raw_n-fac_n).abs().max());numeric.append(err)
 j=z.star_e.abs().idxmax();full_ext.append(dict(sid=sid,day=str(j.date()),r=z.at[j,'r'],scale=z.at[j,'scale'],n=z.at[j,'n'],d=z.at[j,'d'],m=z.at[j,'m'],prev_m=z.at[j,'prev_m'],e=z.at[j,'e'],star_e=z.at[j,'star_e'],delta=z.at[j,'delta']))
 study=z.loc['2022-01-01':];q=study[study.star_e.notna()].copy();q['ca']=q.factor_change.abs()>1e-12
 for ca,g in q.groupby('ca'):
  stats.append(dict(sid=sid,corporate_action_factor_change=bool(ca),n=len(g),sum_abs_delta=g.delta.abs().sum(),sum_abs_e=g.e.abs().sum(),outside_bound=int(g.star_e.abs().gt(1.5).sum()),zero_return=int(g.r.eq(0).sum()),zero_return_nonzero=int((g.r.eq(0)&g.star_e.ne(0)).sum()),scale_floor=int(g.scale.eq(1e-8).sum()),observational_gaps=int(g.observation_gap.sum())))
 parts.append(q[['delta','star_e']])
 # A per-signal descriptive tail share, never used to change ranking.
 z['tail21']=z.star_e.abs().gt(1.5).rolling(21,min_periods=21).sum();z['ca21']=z.factor_change.abs().gt(1e-12).rolling(21,min_periods=21).sum()
 idx=pd.DatetimeIndex(a.loc[a.sid.eq(sid),'day']);rows=z.reindex(idx)
 a.loc[a.sid.eq(sid),'tail21']=rows.tail21.to_numpy();a.loc[a.sid.eq(sid),'ca21']=rows.ca21.to_numpy()
pd.DataFrame(stats).to_csv(O/'CORPORATE_ACTION_STRATA.csv',index=False);ext=pd.DataFrame(full_ext).sort_values('star_e');ext.to_csv(O/'FULL_HISTORY_EXTREMES.csv',index=False)
p=pd.concat(parts,ignore_index=True);absd=p.delta.abs().sort_values(ascending=False);tot=absd.sum();tail=dict(n=len(p),sum_abs_delta=float(tot),top0_1pct_share=float(absd.head(int(np.ceil(len(absd)*.001))).sum()/tot),top1pct_share=float(absd.head(int(np.ceil(len(absd)*.01))).sum()/tot),native_factor_decomposition_max_error=max(numeric),candidate_windows_any_daily_outside_bound=int(a.tail21.gt(0).sum()),candidate_windows_any_factor_change=int(a.ca21.gt(0).sum()),candidate_score_exact_saturation=int((a.star_score.eq(0)|a.star_score.eq(100)).sum()),full_history_worst=ext.iloc[0].to_dict(),study_factor_strata=pd.DataFrame(stats).groupby('corporate_action_factor_change').sum(numeric_only=True).drop(columns=[],errors='ignore').to_dict('index'))
save('TAIL_AND_ACTION_AUDIT.json',tail);a[['sid','day','tail21','ca21','old_rank','new_rank']].to_csv(O/'CANDIDATE_TAIL_EXPOSURE.csv',index=False)
# Data support and descriptive policy exposure summary, no selection changes.
support=[]
for h in [5,20,60]:
 ok=sel.groupby('day')['strict'+str(h)].all();support.append(dict(H=h,total_dates=len(ok),common_complete_dates=int(ok.sum()),excluded_dates=int((~ok).sum()),complete_original_picks=int(sel[sel.strategy.eq('PVR')]['strict'+str(h)].sum()),complete_new_picks=int(sel[sel.strategy.eq('ATTR')]['strict'+str(h)].sum())))
save('FINAL_AUDIT.json',dict(role_note='MOBILE_FIRST_ROUND_ASSOCIATION_SUMMARY is the correctly role-restricted association. Initial ROUND_ASSOCIATION_SUMMARY Top20 groups include CORE firsts on dates with coexisting MOBILE intent; use the role-restricted file.',sector_note='URFI881121=半导体; URFI881172=电子化学品, not pooled as semiconductor. Initial EVALUATION_SUMMARY semiconductor_sector_ids named related-electronics sectors; corrected separate sector detail here.',unknown_original=int(a.score.isna().sum()),unknown_incremental=int((a.score.notna()&a.star_score.isna()).sum()),supports=support,source_hashes_unchanged=all(sha(p)==h for p,h in json.load(open(O/'SOURCE_SHA256.json')).items()),rank_selection_hash_matches=sha(O/'SEALED_SELECTIONS.parquet')==json.load(open(O/'RANK_SEAL.json'))['selection_sha'],numerical_test_change='Only aggregation QA tolerance changed from absolute1e-12 to absolute1e-12 plus relative2e-14 after historical183989 contribution. Formula and ranks unchanged.',independent_review='Separate read-only reviewer reconstructed all796 rankings exactly, checked52 unknown slots and all source hashes. No material formula/ranking bug. Initial role/sector reporting categories corrected in this supplement.',decision='STOP_NO_ACCOUNT_NO_RESCAN_NO_CLIPPING_RESCUE',accounts=0,fits=0,scans=0))
print('MOBILE',pd.DataFrame(out).to_string(index=False));print('SECTOR',pd.DataFrame(sem).to_string(index=False));print('TAIL',json.dumps(clean(tail),ensure_ascii=False,indent=2));print('SUPPORT',support)
