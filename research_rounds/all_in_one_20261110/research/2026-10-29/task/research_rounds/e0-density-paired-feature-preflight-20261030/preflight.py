"""Historical feature-only freeze and deterministic matching. No label input."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import sys,time,json,hashlib,math
import numpy as np
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;stage=sys.argv[1];assert stage in ['freeze','match']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
feature=O/'frozen-features.csv';identity=O/'FEATURE_ONLY_FREEZE.json'
if stage=='freeze':
 assert not identity.exists()
 parent=O.parent/'e0-density-direction-observation-20261030';src=parent/'full/features-before-labels.csv';pool=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/tech-compound-design-20261026/proposed-pool.csv')
 prior=json.loads((parent/'FEATURE_FREEZE.json').read_text());assert sha(src)==prior['sha256'][str(src)]
 prior_inputs=json.loads((parent/'full/INPUT_IDENTITY.json').read_text());assert sha(pool)==prior_inputs['sha256'][str(pool)]
 f=pd.read_csv(src);assert not any(c.startswith(('H21_','H63_')) for c in f.columns);assert f.epoch_id.is_unique
 cohort=f[f.open_date.between('2023-12-29','2026-10-27') & f.I_event & f.Q_known & f.Q.eq(True) & f.T21.gt(0) & f.feature_status.eq('complete')].copy()
 cohort=cohort.merge(pd.read_csv(pool)[['symbol','industry','sector_id']],on='symbol',how='left',validate='many_to_one');assert cohort.epoch_id.is_unique and not cohort.duplicated(['symbol','open_date']).any();assert cohort.D_open.ge(0).all()
 cohort['arm']=np.where(cohort.D_open.ge(1),'restart','no_restart');cohort.sort_values(['open_date','sector_id','symbol','epoch_id']).to_csv(feature,index=False)
 save(identity,dict(at=datetime.now(timezone.utc).isoformat(),stage='before_matching',all_inputs_feature_only=True,labels_opened=False,cohort_rule='research E0 open; contemporaneous I and Q; positive T21; complete historical features',rows=len(cohort),sha256={str(src):sha(src),str(pool):sha(pool),str(O/'PROTOCOL.txt'):sha(O/'PROTOCOL.txt'),str(Path(__file__)):sha(Path(__file__)),str(feature):sha(feature)}))
 print(json.dumps(dict(stage='feature_only_frozen',mother=len(cohort),arms=dict(Counter(cohort.arm)),sha256=sha(feature),seconds=time.monotonic()-T)),flush=True);raise SystemExit

ident=json.loads(identity.read_text());assert all(sha(p)==h for p,h in ident['sha256'].items());assert not (O/'SUMMARY.json').exists()
f=pd.read_csv(feature);assert not any(c.startswith(('H21_','H63_')) for c in f.columns)
f['match_fields_known']=f.sector_id.notna() & f.industry.notna() & np.isfinite(f.past_return21) & np.isfinite(f.past_vol21) & f.past_vol21.gt(0)
f['opponent_count']=0;f['eligible_edges']=0;f['match_status']='matching_fields_unknown';f.loc[f.match_fields_known,'match_status']='no_same_date_industry_opponent';f['pair_id']=None
pairrows=[];all_edges=[];edge_reasons=Counter();chosen=set();num=0
for (day,ind),block in f[f.match_fields_known].groupby(['open_date','sector_id'],sort=True):
 dense=block[block.arm.eq('restart')];control=block[block.arm.eq('no_restart')]
 f.loc[dense.index,'opponent_count']=len(control);f.loc[control.index,'opponent_count']=len(dense)
 if not len(dense) or not len(control):continue
 f.loc[block.index,'match_status']='all_opponents_outside_calipers';edges=[]
 for i,r in dense.iterrows():
  for j,c in control.iterrows():
   diff=float(r.past_return21-c.past_return21);ratio=float(r.past_vol21/c.past_vol21);pr=abs(diff)<=.05;vr=.8<=ratio<=1.25
   reason='eligible' if pr and vr else 'return_only_rejected' if not pr and vr else 'vol_only_rejected' if pr and not vr else 'both_rejected';edge_reasons[reason]+=1
   if not (pr and vr):continue
   dist=(diff/.05)**2+(math.log(ratio)/math.log(1.25))**2;edges.append((dist,r.symbol,c.symbol,r.epoch_id,c.epoch_id,i,j,diff,ratio));f.at[i,'eligible_edges']+=1;f.at[j,'eligible_edges']+=1
   all_edges.append(dict(date=day,sector_id=ind,restart_epoch_id=r.epoch_id,control_epoch_id=c.epoch_id,distance=dist,return_diff=diff,vol_ratio=ratio))
 for dist,rs,cs,re,ce,i,j,diff,ratio in sorted(edges):
  if i in chosen or j in chosen:continue
  chosen.update([i,j]);num+=1;pid=f'P{num:04d}';f.loc[[i,j],'match_status']='matched';f.loc[[i,j],'pair_id']=pid
  r=f.loc[i];c=f.loc[j];row=dict(pair_id=pid,date=day,year=day[:4],industry=r.industry,sector_id=ind,restart_symbol=rs,control_symbol=cs,restart_epoch_id=re,control_epoch_id=ce,distance=dist,past_return21_diff=diff,past_vol21_ratio=ratio)
  for field in ['past_return21','past_vol21','T21','D_open','D_continue','active_days']:
   row['restart_'+field]=r[field];row['control_'+field]=c[field];row[field+'_diff']=r[field]-c[field]
  pairrows.append(row)
f.loc[f.match_fields_known & f.eligible_edges.gt(0) & ~f.match_status.eq('matched'),'match_status']='unmatched_after_greedy_competition'
pairs=pd.DataFrame(pairrows);f.to_csv(O/'all-mother-disposition.csv',index=False);pairs.to_csv(O/'frozen-pairs.csv',index=False);pd.DataFrame(all_edges).to_csv(O/'eligible-edges.csv',index=False)
assert len(chosen)==2*len(pairs);assert f.loc[f.match_status.eq('matched'),'epoch_id'].is_unique
if len(pairs):
 assert pairs.date.nunique()<=len(pairs);assert set(pairs.restart_epoch_id).isdisjoint(pairs.control_epoch_id);assert pairs.past_return21_diff.abs().le(.05).all() and pairs.past_vol21_ratio.between(.8,1.25).all()
 matched=f[f.match_status.eq('matched')];years=pairs.groupby('year').agg(pairs=('pair_id','size'),dates=('date','nunique'),industries=('sector_id','nunique')).reset_index();years.to_csv(O/'matched-year-coverage.csv',index=False)
 for keys,fn in [(['date'],'matched-date-coverage.csv'),(['sector_id','industry'],'matched-industry-coverage.csv')]:pairs.groupby(keys).size().reset_index(name='pairs').to_csv(O/fn,index=False)
else:matched=f.iloc[0:0];years=pd.DataFrame(columns=['year','pairs','dates','industries'])
balances=[]
for phase,z in [('before',f),('after',matched)]:
 for field in ['past_return21','past_vol21','T21','D_continue','active_days']:
  row=dict(phase=phase,field=field)
  for arm in ['restart','no_restart']:
   x=z.loc[z.arm.eq(arm),field].dropna();row.update({f'{arm}_n':len(x),f'{arm}_mean':x.mean(),f'{arm}_SD':x.std(ddof=1),f'{arm}_q10':x.quantile(.1),f'{arm}_median':x.quantile(.5),f'{arm}_q90':x.quantile(.9)})
  delta=row['restart_mean']-row['no_restart_mean'];pooled=np.sqrt((row['restart_SD']**2+row['no_restart_SD']**2)/2);row.update(mean_diff=delta,SMD=delta/pooled if np.isfinite(pooled) and pooled>0 else None);balances.append(row)
pd.DataFrame(balances).to_csv(O/'balance-before-after.csv',index=False)
coverage=f.groupby(['arm','match_status'],dropna=False).agg(events=('epoch_id','size'),stocks=('symbol','nunique'),dates=('open_date','nunique'),industries=('sector_id','nunique')).reset_index();coverage.to_csv(O/'coverage-and-unmatched.csv',index=False)
stock=matched.groupby(['symbol','name']).size().reset_index(name='matched_legs').sort_values(['matched_legs','symbol'],ascending=[False,True]);stock['share_all_legs']=stock.matched_legs/len(matched) if len(matched) else np.nan;stock.to_csv(O/'matched-stock-concentration.csv',index=False)
dates=int(pairs.date.nunique()) if len(pairs) else 0;gate=dates>=20 and len(years)>=2 and bool(years.dates.ge(5).all());summary=dict(passed_implementation=True,labels_opened=False,models_or_trade_paths=0,mother=len(f),mother_arms=dict(Counter(f.arm)),matched_pairs=len(pairs),matched_legs=len(matched),matched_stocks=int(matched.symbol.nunique()),matched_dates=dates,matched_industries=int(matched.sector_id.nunique()),years=years.to_dict('records'),minimum_coverage_gate=gate,coverage_gate_rule='>=20 dates; >=2 represented years; every represented year >=5 distinct dates',unmatched_status=dict(Counter(f.match_status)),edge_rejections=dict(edge_reasons),top5_stock_leg_share=float(stock.head(5).share_all_legs.sum()),balance=balances,feature_hashes_unchanged=all(sha(p)==h for p,h in ident['sha256'].items()),seconds=time.monotonic()-T)
assert summary['feature_hashes_unchanged'];save(O/'SUMMARY.json',summary);save(O/'PAIR_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_future_labels=True,labels_opened=False,sha256={str(O/n):sha(O/n) for n in ['PROTOCOL.txt','frozen-features.csv','frozen-pairs.csv','all-mother-disposition.csv','balance-before-after.csv','SUMMARY.json']}));print(json.dumps(clean(summary),ensure_ascii=False),flush=True)
