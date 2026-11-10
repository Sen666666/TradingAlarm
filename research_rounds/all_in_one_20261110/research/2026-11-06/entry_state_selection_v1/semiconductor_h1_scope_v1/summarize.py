"""Complete-cohort explanatory summary. No account/portfolio selection or fitting."""
from pathlib import Path
import json,hashlib,sys,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');M=Path('/Users/bytedance/Documents/ChatGPT/money')
P=Path(json.load(open(M/'TradingAlarm/runtime/market/current.json'))['path'])
FORMULA=W/'pvr-current-v3-information-capital-20261101/original_score_function.py';OLD=W/'pvr-slot1-native-readiness-20261101';END='2026-06-30';BASE='2025-12-31';CUT='2026-05-15'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 if isinstance(x,pd.Timestamp):return str(x.date())
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
assert sha(FORMULA)=='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
env=dict(np=np,pd=pd);exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),env);score=env['score']
d=pd.read_parquet(O/'ALL_STOCK_DAILY.parquet');rr=pd.read_csv(O/'ALL_I_ROOTS.csv');px=pd.read_csv(O/'ALL_STOCK_PRICE_AND_SIGNAL_SUMMARY.csv');c=pd.read_csv(O/'COVERAGE.csv');ss=pd.read_csv(O/'SECTOR_DAILY.csv');ss=ss[ss.day>='2026-01-01'].copy()
meta=json.load(open(M/'research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json'))['security_metadata']
names={k:v['name'] for k,v in meta.items()};d['name']=d.name.fillna(d.sid.map(names));rr['name']=rr.name.fillna(rr.sid.map(names));px['name']=px.name.fillna(px.sid.map(names));c['name']=c.name.fillna(c.sid.map(names))
manifest={x['symbol']:x for x in json.load(open(OLD/'SCORES_MANIFEST.json'))['entries']}
hashes={str(FORMULA):sha(FORMULA),str(OLD/'SCORES_MANIFEST.json'):sha(OLD/'SCORES_MANIFEST.json'),str(Path(__file__)):sha(__file__)}
a=[];parts=[];raws={}
for sid in c.loc[c.H1_rows.gt(0),'sid']:
 path=P/'signals'/(sid+'.parquet');f=pd.read_parquet(path).loc[:END];raws[sid]=f
 z=score(f);oldpath=OLD/'scores'/(sid+'.parquet');assert sha(oldpath)==manifest[sid]['output_sha256'];old=pd.read_parquet(oldpath);old=old.loc[:END]
 pd.testing.assert_frame_equal(z[['score']].reindex(old.index),old,check_exact=True,check_freq=False,check_names=False)
 for cut in [BASE,CUT]:pd.testing.assert_frame_equal(score(f.loc[:cut]),z.loc[:cut],check_exact=True,check_freq=False)
 hashes[str(path)]=sha(path);hashes[str(oldpath)]=sha(oldpath)
 zz=z.loc['2026-01-01':END].copy();zz['sid']=sid;zz['day']=zz.index.strftime('%Y-%m-%d');parts.append(zz.reset_index(drop=True));a.append(dict(sid=sid,all_score_cells_exact=True,physical_prefix_exact=True,H1_known=int(zz.score.notna().sum()),H1_unknown=int(zz.score.isna().sum())))
pvr=pd.concat(parts,ignore_index=True);pvr.to_parquet(O/'PVR_DAILY.parquet',index=False);pd.DataFrame(a).to_csv(O/'PVR_EXACT_AUDITS.csv',index=False)
d=d.merge(pvr[['sid','day','score','E','u','b']],on=['sid','day'],validate='one_to_one');d=d.rename(columns={'score':'PVR_score'});d.to_parquet(O/'ENRICHED_DAILY.parquet',index=False)
stock=[]
for sid,g in d.groupby('sid'):
 p=px[px.sid.eq(sid)].iloc[0].to_dict();raw=raws[sid];base=raw.loc[:BASE];p['I_active_first_H1']=bool(g.i_target.iloc[0]);p['E0_active_first_H1']=bool(g.e0_target.iloc[0]);p['first_H1_day']=g.day.iloc[0]
 for k,mask in [('I_birth',g.I_birth),('I_buy',g.i_buy),('old_CP',g.old_receipt),('new_CP',g.new_receipt)]:
  ev=g[mask];p['first_'+k]=ev.day.iloc[0] if len(ev) else None
  p['return_already_'+k]=float(ev.close.iloc[0]/base.close.iloc[-1]-1) if len(ev) and len(base) else None
  p['PVR_at_'+k]=float(ev.PVR_score.iloc[0]) if len(ev) else None
  p['sector_E0_at_'+k]=bool(ev.sector_E0.iloc[0]) if len(ev) else None
  p['sector_stage_at_'+k]=int(ev.sector_stage.iloc[0]) if len(ev) else None
 stock.append(p)
st=pd.DataFrame(stock);st.to_csv(O/'ALL_126_COVERAGE_WITH_NAMES.csv',index=False) if False else None
st.to_csv(O/'ALL_120_SIGNAL_TIMING.csv',index=False);c.to_csv(O/'ALL_126_COVERAGE_WITH_NAMES.csv',index=False)
# Pre-existing H1 roots grouped only by original I calendar, all roots retained.
rr['cohort']=np.where(rr.left_truncated_H1,'carry_from_2025',np.where(rr.I_root<'2026-04-01','born_Q1','born_Q2'))
rr['first_timing']=np.select([rr.old_first.notna()&rr.new_first.notna()&rr.old_first.eq(rr.new_first),rr.old_first.notna()&rr.new_first.notna()&rr.new_first.gt(rr.old_first),rr.old_first.notna()&rr.new_first.notna()&rr.new_first.lt(rr.old_first),rr.old_first.notna()&rr.new_first.isna(),rr.old_first.isna()&rr.new_first.notna()],['same','dual_later','dual_earlier','old_only','dual_only'],default='neither')
cal=pd.DatetimeIndex(pd.read_parquet(P/'signals/URFI881121.parquet').loc[:END].index)
for j,r in rr.iterrows():
 raw=raws[r.sid]
 for k in ['old','new']:
  day=r[k+'_first']
  if pd.isna(day) or day<'2026-01-01':continue
  expected=cal[cal>pd.Timestamp(day)][:20];future=raw.loc[raw.index>pd.Timestamp(day)].iloc[:20]
  okay=len(expected)==20 and list(future.index)==list(expected)
  rr.loc[j,k+'_common20']=okay
  if okay:
   op=future.raw_open.iloc[0]*future.adjustment_factor.iloc[0];rr.loc[j,k+'_common20_return']=future.close.iloc[-1]/op-1
rr.to_csv(O/'ALL_ROOTS_EXPLAINED.csv',index=False)
rows=[]
for group,g in rr.groupby('cohort',sort=False):
 row=dict(cohort=group,roots=len(g),stocks=g.sid.nunique(),old_any=int(g.old_first.notna().sum()),dual_any=int(g.new_first.notna().sum()),first_timing=g.first_timing.value_counts().to_dict())
 for k in ['old','new']:
  v=g.loc[g[k+'_common20'].eq(True),k+'_common20_return'];row[k+'_common20_n']=len(v);row[k+'_common20_negative']=int(v.lt(0).sum());row[k+'_common20_median']=float(v.median());row[k+'_lag_median']=float(g[k+'_lag'].median());row[k+'_move_already_median']=float(g[k+'_move_already'].median())
 rows.append(row)
# Fixed calendar snapshots: future labels join AFTER original score calculation.
fixed=['2026-01-05','2026-01-15','2026-01-30','2026-03-06','2026-03-31','2026-04-17','2026-05-15','2026-06-30']
snap=d[d.day.isin(fixed)].merge(st[['sid','H1_return','after_May15']],on='sid',how='left')
snap['PVR_sector_rank']=snap.groupby('day').PVR_score.rank(method='min',ascending=False);snap.to_csv(O/'FIXED_DATE_ALL_STOCK_SNAPSHOTS.csv',index=False)
# Price tiers are explicitly retrospective attribution, NOT selectors.
st['retrospective_price_tier']=pd.cut(st.H1_return,[-np.inf,0,.5,1,np.inf],right=False,labels=['negative','0_to_50pct','50_to_100pct','100pct_plus'])
tiers=[]
for tier,g in st.groupby('retrospective_price_tier',observed=True):
 tiers.append(dict(tier=str(tier),stocks=len(g),I_active_first_H1=int(g.I_active_first_H1.sum()),first_old_CP_by_Jan15=int(g.first_old_CP.le('2026-01-15').sum()),first_old_CP_after_Q1=int(g.first_old_CP.gt('2026-03-31').sum()),no_CP=int(g.first_old_CP.isna().sum()),median_return_already_first_CP=float(g.return_already_old_CP.median()),median_PVR_at_first_CP=float(g.PVR_at_old_CP.median())))
st.to_csv(O/'ALL_STOCK_TIMING_WITH_RETROSPECTIVE_TIERS.csv',index=False)
# Sector intervals and delayed authorization versus signals. Not actual eligibility.
sector_episodes=[]
for ep,g in ss[ss.E0_valid].groupby('E0_episode',sort=False):
 g=g.sort_values('day');ev=g[g.action.eq('probe')];root=g.day.iloc[0];first=ev.day.iloc[0] if len(ev) else None
 sector_episodes.append(dict(H1_visible_start=root,first_probe=first,last_visible=g.day.iloc[-1],left_truncated=root==ss.day.iloc[0],from_visible_start_to_probe=float(ev.close.iloc[0]/g.close.iloc[0]-1) if len(ev) else None,probe_to_end=float(g.close.iloc[-1]/ev.close.iloc[0]-1) if len(ev) else None))
summary=dict(pvr='120 stocks original score exact to cached full-H1 scores, all 2 physical prefixes exact; score is signed recent normalized price-volume evidence, not probability',root_groups=rows,retrospective_price_tiers=tiers,sector_intervals=sector_episodes,raw_CP_sector_context=dict(total=int(d.old_receipt.sum()),sector_E0_false=int((d.old_receipt&~d.sector_E0).sum()),sector_E0_true_no_authorization=int((d.old_receipt&d.sector_E0&~d.sector_authorization).sum()),sector_authorized=int((d.old_receipt&d.sector_authorization).sum()),warning='Conjunction only, not original full legal candidate/ACT/capital eligibility'),all_sources_unchanged=all(sha(p)==v for p,v in hashes.items()))
assert summary['all_sources_unchanged'];save('EXPLANATORY_SUMMARY.json',summary);save('SUPPLEMENT_SOURCE_HASHES.json',hashes);save('SUPPLEMENT_OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name not in ['SUPPLEMENT_OUTPUT_HASHES.json']});print(json.dumps(clean(summary),ensure_ascii=False,indent=2))
