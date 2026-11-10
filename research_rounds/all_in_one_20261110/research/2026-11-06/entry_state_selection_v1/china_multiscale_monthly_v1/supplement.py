"""Post-ranking diagnostics only. Does not fit or alter model, scores, or picks."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
models=json.loads((O/'MONTHLY_MODELS.json').read_text());md={(x['month'],x['model']):x for x in models if x.get('status')=='FIT'}
m=pd.read_parquet(O/'MONTHLY.parquet');c=pd.read_parquet(O/'PREDICTIONS.parquet');sel=pd.read_parquet(O/'SELECTIONS_WITH_LABELS.parquet');pa=pd.read_csv(O/'PAIRED_60BLOCK_RESULTS.csv');pa['ci_status']=np.where(pa.blocks<2,'UNKNOWN_ONE_BLOCK',np.where(pa.blocks<8,'VERY_FEW_BLOCKS_DESCRIPTIVE','DESCRIPTIVE_CONSUMED_HISTORY'));pa.loc[pa.blocks<2,['lo','hi']]=np.nan;pa.to_csv(O/'PAIRED_60BLOCK_RESULTS_QUALIFIED.csv',index=False)
P=[f'P{n}'for n in [3,5,10,20,50,100,200,300,400]];F=P+[v.replace('P','A')for v in P];ics=[]
for month,g in m.groupby('month'):
 tr=g[g.label_known&np.isfinite(g[F]).all(axis=1)&np.isfinite(g.y)];prev=md.get((month,'PA18'))
 if prev is None or not prev['warm']or len(tr)<30:continue
 for name,cols in [('P9',P),('PA18',F)]:
  b=np.array(md[(month,name)]['ema']);score=b[0]+tr[cols].to_numpy()@b[1:];rank=pd.Series(score,index=tr.index).rank();yrank=tr.y.rank();ics.append(dict(signal_month=month,target_month=tr.target_month.iloc[0],model=name,n=len(tr),spearman=float(rank.corr(yrank)),pearson=float(np.corrcoef(score,tr.y)[0,1]),high_score_mean_prior21=float(tr.loc[rank>=rank.quantile(.8),'past21'].mean())))
ics=pd.DataFrame(ics);ics['period']=np.where(ics.signal_month<'2022-01','2017_2021','2022_2026');ics.to_csv(O/'MONTHLY_FORWARD_IC.csv',index=False);ics.groupby(['period','model']).agg(months=('spearman','size'),mean_rank_ic=('spearman','mean'),positive_ic_fraction=('spearman',lambda x:(x>0).mean()),median_rank_ic=('spearman','median')).to_csv(O/'MONTHLY_IC_SUMMARY.csv')
# Fixed 99th percentile of same selected-union rows, cap each identical stockday identically; preserve dates and counts.
tails=[];acceler=[];covers=[];daily=[];pair=[];rng=np.random.default_rng(20261106)
for h in [5,20,60]:
 good=sel.groupby('day')['complete'+str(h)].all();s=sel[sel.day.isin(good[good].index)].copy()
 for year,g in sel.groupby('year'):covers.append(dict(H=h,year=year,total_dates=g.day.nunique(),common_complete_dates=int(good.loc[g.day.unique()].sum()),total_picks_per_arm=len(g)//4,complete_picks_per_arm=len(s[s.year.eq(year)])//4))
 for period,start,end in [('ALL','2022-01-01','2026-05-15'),('2024_924','2024-09-24','2024-10-31'),('2026Q1','2026-01-01','2026-03-31')]:
  z=s[s.day.between(start,end)].copy();ycol='ret'+str(h);cut=z.drop_duplicates(['sid','day'])[ycol].quantile(.99);z['capret']=z[ycol].clip(upper=cut);raw=z.groupby(['day','method'])[ycol].mean().unstack();cap=z.groupby(['day','method']).capret.mean().unstack()
  for name in ['H1','P9','PA18']:tails.append(dict(H=h,period=period,method=name,common_days=len(raw),threshold=cut,raw_delta=float((raw[name]-raw.PVR).mean()),same_denominator_top1_cap_delta=float((cap[name]-cap.PVR).mean()),top1_tail_component=float(((raw[name]-raw.PVR)-(cap[name]-cap.PVR)).mean())))
  d=raw.PA18-raw.P9;blocks=pd.DataFrame({'d':d,'block':pd.to_datetime(d.index).map(lambda x:(x-pd.Timestamp('2013-01-04')).days//90)}).groupby('block').d.agg(['sum','count']);draw=rng.integers(0,len(blocks),(2000,len(blocks)));boot=blocks['sum'].to_numpy()[draw].sum(1)/blocks['count'].to_numpy()[draw].sum(1);lo,hi=np.quantile(boot,[.025,.975]);pair.append(dict(H=h,period=period,comparator='PA18_minus_P9',days=len(d),blocks=len(blocks),delta=float(d.mean()),lo=float(lo)if len(blocks)>=2 else np.nan,hi=float(hi)if len(blocks)>=2 else np.nan,block_definition='fixed90calendar_days_descriptive'))
  for(method,acc),g in z.groupby(['method','accelerating']):acceler.append(dict(H=h,period=period,method=method,accelerating=bool(acc),n=len(g),mean=float(g[ycol].mean()),positive40bp=float(g[ycol].gt(.004).mean())))
  if h==60:
   dd=raw.assign(delta_PA18=raw.PA18-raw.PVR,period=period);daily.append(dd.reset_index())
pd.DataFrame(tails).to_csv(O/'COMMON_DENOMINATOR_RIGHTTAIL.csv',index=False);pd.DataFrame(acceler).to_csv(O/'ACCELERATION_RESULTS.csv',index=False);pd.DataFrame(covers).to_csv(O/'EVALUATION_DATE_COVERAGE.csv',index=False);pd.concat(daily).to_csv(O/'DAILY60_DELTAS.csv',index=False);pd.DataFrame(pair).to_csv(O/'AMOUNT_ABLATION_PAIRED.csv',index=False)
# Identify the monthly raw feature leverage outlier from frozen fitting inputs. Diagnostic algebra only.
w=max([x for x in models if x.get('model')=='PA18'],key=lambda x:x['max_leverage']);g=m[m.target_month.eq(w['month'])];g=g[g.label_known&np.isfinite(g[F]).all(axis=1)&np.isfinite(g.y)].copy();X=g[F].to_numpy();Z=(X-np.array(w['mean']))/np.array(w['sd']);hat=np.sum((Z@np.linalg.inv(Z.T@Z+len(g)*.01*np.eye(18)))*Z,axis=1)+1/len(g);g['ridge_leverage']=hat;g.nlargest(10,'ridge_leverage')[['sid','month','target_month','y','ridge_leverage']+F].to_csv(O/'WORST_MONTH_LEVERAGE.csv',index=False)
q=pd.read_csv(O/'QUEUE_AUDIT.csv');cor=pd.read_csv(O/'RANK_CORRELATIONS.csv');a=pd.read_csv(O/'SOURCE_AUDIT.csv');summary=dict(known=int(c.common_known.sum()),total=len(c),selection_changes=q.groupby('method').changed.sum().to_dict(),rank_correlations=cor.groupby('comparator').spearman.mean().to_dict(),all1709_source_native_max=float(a.max_native_error.max()),all1709_factor_max=float(a.max_factor_error.max()),worst_leverage_month=w['month'],worst_leverage=w['max_leverage'],monthly_ic=ics.groupby(['period','model']).spearman.mean().to_dict())
summary['monthly_ic']={str(k):v for k,v in summary['monthly_ic'].items()};(O/'SUPPLEMENT_SUMMARY.json').write_text(json.dumps(summary,indent=2));seal=json.loads((O/'RANK_SEAL.json').read_text());assert seal['predictions']==sha(O/'PREDICTIONS.parquet')and seal['picks']==sha(O/'SEALED_PICKS.parquet')and seal['code']==sha(O/'experiment.py');(O/'FINAL_SEAL_CHECK.json').write_text(json.dumps(dict(scores_picks_code_unchanged=True,no_new_models=True,no_new_rankings=True),indent=2))
print(json.dumps(summary,indent=2));print(pd.DataFrame(tails).query('H==60').to_string(index=False));print(pd.DataFrame(covers).query('H==60').to_string(index=False));print(pd.read_csv(O/'WORST_MONTH_LEVERAGE.csv').head(2).to_string(index=False))
