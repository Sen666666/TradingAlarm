from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,gzip
from collections import defaultdict,Counter
O=Path(__file__).resolve().parent;B=O.parent;ROOT=B.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda x:x.item()if isinstance(x,np.generic)else str(x)))
# Direct selected-row feature replication from explicit trailing windows, not the cached column.
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/selection.json')
f=pd.read_csv(O/'ORIGINAL_FIRST_MOBILE_PREDICTIONS.csv');h=np.load(H,allow_pickle=False);dates=pd.DatetimeIndex(h['dates']);symbols=list(h['symbols'])
cl=h['close'];seg=h['segment'];mapping={r['security_id']:r['sector_id']for r in json.loads(M.read_text())['lines']}
secix={s:[i for i,z in enumerate(symbols)if mapping.get(z)==s]for s in f.sector.unique()}
err=[];prefix=[]
for r in f.itertuples():
 t=dates.get_loc(pd.Timestamp(r.signal_day));ix=secix[r.sector];x=cl[t-19:t+1,ix];valid=np.isfinite(x).all(axis=0)&(x>0).all(axis=0)&(seg[t,ix]==seg[t-19,ix])
 b=float((x[-1,valid]>x[:,valid].mean(axis=0)).mean());err.append(abs(b-r.industry_breadth20))
 if r.signal_day in ['2023-07-03','2024-01-02','2025-01-02']:
  # Direct prefix use proves this operation accesses no post-signal prices.
  cp=cl[:t+1,ix];sp=seg[:t+1,ix];xp=cp[-20:];vp=np.isfinite(xp).all(axis=0)&(xp>0).all(axis=0)&(sp[-1]==sp[-20])
  bp=float((xp[-1,vp]>xp[:,vp].mean(axis=0)).mean());prefix.append(dict(sid=r.sid,day=r.signal_day,exact=bp==b))
dump('FEATURE_DIRECT_AUDIT.json',dict(rows=len(f),max_abs_error=max(err),differences_above_1e12=sum(e>1e-12 for e in err),prefix_rows=prefix,sources={str(p):sha(p)for p in [H,M]},limitation='Static original sector roster is not historical PIT membership; direct calculation confirms price cutoff only. Floating point equality at exactly MA20 investigated separately if differences appear.'))
print('FEATURE',max(err),sum(e>1e-12 for e in err),len(prefix))
# Reuse exact fixed pairs. Never reconstruct pairs or infer any rejected complete-round labels.
P=B/'supported_trajectory_risk_v1/EXACT_151_MATCHED_PAIRS_BEFORE_SCORES.csv';pairs=pd.read_csv(P);ph=hashlib.sha256(json.dumps([(r.day,r.funded_sid,r.rejected_sid)for r in pairs.itertuples()]).encode()).hexdigest()
assert len(pairs)==151 and ph=='4e1400bce427bba682b1511d7c07ccf1a75f877b6527eff01ba8c45fe5ccf7e8'
rows=[];detail=[]
q=pd.read_csv(B/'supported_trajectory_risk_v1/PAIRED_SEALED_DECISIONS.csv')
for role,g in q.groupby('role'):
 known=g.f_known&g.r_known
 rows.append(dict(model='Q_role_correct_existing',funded_role=role,pairs=len(g),both_scores_known=int(known.sum()),prefers_rejected=int((known&g.swap).sum()),applicability='Original role-specific score and floor; already executed existing pair diagnostic.'))
sources=[
 ('CE',B/'cp1_signal_mechanism_v1/cp_timing_quality_v1/candidate_test/CANDIDATE_CE.parquet','CE'),
 ('MIX_EV_ES',B/'conditional_distribution_numerical_fix_v2/PREDICTIONS.parquet','MIX_EV_ES'),
 ('DIRECT_MEAN',B/'conditional_distribution_numerical_fix_v2/PREDICTIONS.parquet','DIRECT_MEAN'),
 ('PC',B/'conditional_distribution_numerical_fix_v2/PREDICTIONS.parquet','PC'),
 ('PA18',ROOT/'china_multiscale_monthly_v1/PREDICTIONS.parquet','PA18'),
 ('P9',ROOT/'china_multiscale_monthly_v1/PREDICTIONS.parquet','P9'),
 ('INTRADAY_STAR',ROOT/'intraday_overnight_attribution_v1/CANDIDATE_SCORES.parquet','star_score')]
for name,path,col in sources:
 c=pd.read_parquet(path,columns=['account','day','sid',col]);c=c[c.account.eq('PVR')].drop(columns='account');c.day=c.day.astype(str).str[:10]
 g=pairs[pairs.role.eq('mobile')].copy()
 for side,short in [('funded','f'),('rejected','r')]:
  g=g.merge(c.rename(columns={'sid':side+'_sid',col:short+'_score'}),on=['day',side+'_sid'],how='left',validate='one_to_one')
 known=np.isfinite(g[['f_score','r_score']]).all(axis=1);sw=known&g.r_score.round(12).gt(g.f_score.round(12))
 rows.append(dict(model=name,funded_role='mobile',pairs=len(g),both_scores_known=int(known.sum()),prefers_rejected=int(sw.sum()),applicability='Only existing mobile-domain scores on23 mobile-funded pairs; CORE128 not evaluated or extrapolated.'))
 for i,r in g.iterrows():detail.append(dict(model=name,day=r.day,funded_sid=r.funded_sid,rejected_sid=r.rejected_sid,known=bool(known.loc[i]),prefers_rejected=bool(sw.loc[i]),f_score=r.f_score,r_score=r.r_score))
pd.DataFrame(rows).to_csv(O/'EXISTING_151_PAIR_RANK_REACH.csv',index=False);pd.DataFrame(detail).to_csv(O/'EXISTING_MOBILE_PAIR_SCORE_REACH.csv',index=False)
dump('PAIR_REUSE_AUDIT.json',dict(rows=151,dates=pairs.day.nunique(),hash=ph,core=int(pairs.role.eq('core').sum()),mobile=int(pairs.role.eq('mobile').sum()),new_pairing=False,new_rejected_predictions=False,source_sha256=sha(P)))
print('PAIR_REACH',pd.DataFrame(rows).to_string(index=False))
# Actual queue >20 reach: classify facts from original funding, no account replay.
c=pd.read_parquet(B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');c=c[c.account.eq('PVR')].sort_values(['day','original_priority_rank','sid']);c['pos']=c.groupby('day').cumcount()+1
a=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv',usecols=['account','sid','signal_day','entry_day','first_kind']);a=a[a.account.eq('PVR')&a.first_kind.eq('add')].rename(columns={'signal_day':'day'})
j=c.merge(a,on=['account','sid','day'],how='inner',validate='one_to_one');out=j[j.pos>20].copy();out['day_first_mobile_count']=out.day.map(a.groupby('day').size());out['over20_due_more_than20_fills']=out.day_first_mobile_count>20
FD=ROOT/'account_comparison_continuous_v1/run_1200000/pair/funding.jsonl.gz'
fund=defaultdict(list)
for line in gzip.open(FD,'rt'):
 r=json.loads(line)
 if r['account']=='PVR'and '09:30' in r['at']:fund[r['at'][:10],r['sid']].append(r)
count=Counter();details=[]
for r in out.itertuples():
 own=fund[r.entry_day,r.sid];reserved=[x for x in own if x['role']=='mobile'and x['result']=='reserved'];assert len(reserved)==1
 earlier=c[c.day.eq(r.day)&c.pos.lt(r.pos)]
 cnt=Counter()
 for q in earlier.itertuples():
  rr=fund[r.entry_day,q.sid];reserved_roles=[x['role']for x in rr if x['result']=='reserved']
  if 'mobile'in reserved_roles:cnt['earlier_mobile_reserved']+=1
  elif 'core'in reserved_roles:cnt['earlier_core_reserved']+=1
  else:
   results=sorted(set(x['result']for x in rr))
   cnt['earlier_no_reservation']+=1
   for v in results:cnt['reject_'+v]+=1
 details.append(dict(day=r.day,entry_day=r.entry_day,sid=r.sid,queue_position=int(r.pos),mobile_first_fills_that_day=int(r.day_first_mobile_count),own_pool=reserved[0].get('pool'),**dict(cnt)))
 count['outside20']+=1;count['dates_morethan20_mobile_fills']+=bool(r.day_first_mobile_count>20)
pd.DataFrame(details).to_csv(O/'ACTUAL_OUTSIDE_TOP20_REASONS.csv',index=False)
dump('OUTSIDE_TOP20_SUMMARY.json',dict(candidates=len(c),actual_mobile_first=len(j),outside20=len(out),outside20_dates=out.day.nunique(),outside20_on_days_over20_fills=int((out.day_first_mobile_count>20).sum()),outside20_on_days_atmost20_fills=int((out.day_first_mobile_count<=20).sum()),earlier_categories_sum=pd.DataFrame(details).filter(regex='^earlier_|^reject_').sum().to_dict(),note='Earlier-name counts repeat across outside20 rows and are explanatory context, not unique rejected candidates. No hardTop20 in actual allocator; funding/risk/role constraints and variable count matter. No causal attribution percentages inferred from co-occurrence.'))
print('OUTSIDE20',len(out),out.day.nunique(),int((out.day_first_mobile_count>20).sum()))
# Within selected main sample, does adding interaction actually reorder within sector?
main=f[f.known&f.mature120&f.signal_year.between(2023,2025)]
rr=[]
for cols in [['signal_day'],['signal_day','sector']]:
 n=changed=0
 for key,g in main.groupby(cols):
  if len(g)<2:continue
  x=g.sort_values(['additive','PVR_decision','sid'],ascending=[False,False,True]).sid.tolist();y=g.sort_values(['interaction','PVR_decision','sid'],ascending=[False,False,True]).sid.tolist();n+=1;changed+=x!=y
 rr.append(dict(domain='|'.join(cols),groups_with_multiple=len([1 for _,g in main.groupby(cols)if len(g)>1]),changed_order=changed))
dump('SAME_GROUP_ORDER_CHANGES.json',rr)
