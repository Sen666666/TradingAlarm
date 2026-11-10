import pathlib,json,hashlib,sys,warnings
warnings.filterwarnings('ignore',category=FutureWarning)
import numpy as np,pandas as pd
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'major_trends_2025_2026_review_v1/industry_specific_cycles/member_participation'
H=json.load(open(R/'account_comparison_continuous_v1/inputs/H1_MANIFEST.json'))
H={r['sid']:r for r in H}
mp=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv')
M=pd.read_csv(mp,dtype=str).drop_duplicates('symbol').set_index('symbol')
C=pd.read_csv(O.parent/'SIX_INDEPENDENT_CYCLES.csv').query("sid.str.startswith('URFI')",engine='python')
F=pd.read_csv(O.parent/'SIX_INDEPENDENT_PHASES.csv')
sourcehash={str(mp):hashlib.sha256(mp.read_bytes()).hexdigest()}
rows=[];members=[];daily=[];coverage=[];prices={}
def load(sid):
 r=H[sid]; p=next(p for p in r['source_identity'] if p.endswith('/signal.parquet'))
 sha=hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest(); assert sha==r['source_identity'][p]
 sourcehash[p]=sha
 q=pd.read_parquet(p).loc['2023-10-01':'2026-10-22']
 assert q.index.is_unique and q.index.is_monotonic_increasing
 ok=q.observed_bar.fillna(False)&q.price_eligible.fillna(False)&~q.source_invalid.fillna(True)&~q.synthetic_event_bar.fillna(True)&np.isfinite(q.close)&q.close.gt(0)
 return q.close.where(ok)
for c in C.to_dict('records'):
 sid=c['sid']; allmem=M[M.industry_index_symbol==sid].index.tolist()
 mem=[s for s in allmem if s in H and not H[s]['industry']]
 idx=load(sid); P=pd.DataFrame({s:load(s) for s in mem}).reindex(idx.index);prices[sid]=P
 coverage.append({'sector':sid,'name':c['name'],'current_master_n':len(allmem),'research_pool_n':len(mem),'outside_research_pool_n':len(allmem)-len(mem),'coverage_pct':100*len(mem)/len(allmem)})
 # Rolling window uses common sector dates, never forward filled; requires both endpoints observed.
 r21=P/P.shift(21)-1; k21=r21.notna().sum(axis=1); u21=r21.gt(0).sum(axis=1); b21=u21/k21.replace(0,np.nan)
 d=pd.DataFrame({'sector':sid,'date':P.index.strftime('%Y-%m-%d'),'pool_n':len(mem),'known21':k21,'unknown21':len(mem)-k21,'up21':u21,'breadth21_pct':100*b21,'breadth21_lower_pool_pct':100*u21/len(mem),'breadth21_upper_pool_pct':100*(u21+len(mem)-k21)/len(mem)})
 daily.append(d)
 windows=[('二次底部至行业峰值',c['secondary_base'],c['main_peak']),('重返前高至行业峰值',c['first_close_reclaim_date'],c['main_peak']),('行业峰值至截止',c['main_peak'],c['observation_end'])]
 windows += [('阶段'+str(int(f['phase']))+' '+f['description'],f['start'],f['end']) for f in F[F.sid==sid].to_dict('records')]
 for label,a,z in windows:
  a=pd.Timestamp(a);z=pd.Timestamp(z); ret=(P.loc[z]/P.loc[a]-1).dropna().sort_values(ascending=False); n=len(ret);g=ret.clip(lower=0);sg=g.sum()
  pr=P.loc[a:z]; valid=pr.notna(); complete=int(valid.all().sum()); nobs=pr.notna().sum()
  wi=(b21.index>a)&(b21.index<=z); bs=b21.loc[wi].dropna();count=len(bs)
  qq=ret.quantile([.1,.25,.5,.75,.9]);topn=max(1,int(np.ceil(.1*n)));trim=ret.iloc[topn:]
  rr={'sector':sid,'name':c['name'],'window':label,'start':str(a.date()),'end':str(z.date()),'industry_return_pct':100*(idx.loc[z]/idx.loc[a]-1),'current_master_n':len(allmem),'pool_n':len(mem),'known_endpoint_n':n,'unknown_endpoint_n':len(mem)-n,'full_path_valid_n':complete,'daily_intermediate_missing_cells':int(pr.isna().sum().sum()),'positive_n':int((ret>0).sum()),'over50_n':int((ret>=.5).sum()),'over100_n':int((ret>=1).sum()),'positive_pct_known':100*(ret>0).mean(),'positive_lower_current_master_pct':100*(ret>0).sum()/len(allmem),'positive_upper_current_master_pct':100*((ret>0).sum()+len(allmem)-n)/len(allmem),'p10_pct':100*qq.loc[.1],'p25_pct':100*qq.loc[.25],'median_pct':100*qq.loc[.5],'p75_pct':100*qq.loc[.75],'p90_pct':100*qq.loc[.9],'equal_initial_mean_pct':100*ret.mean(),'top1_positive_gain_share_pct':100*g.head(1).sum()/sg if sg>0 else np.nan,'top3_positive_gain_share_pct':100*g.head(3).sum()/sg if sg>0 else np.nan,'top10pct_n':topn,'top10pct_positive_gain_share_pct':100*g.head(topn).sum()/sg if sg>0 else np.nan,'exclude_top10pct_mean_pct':100*trim.mean(),'exclude_top10pct_median_pct':100*trim.median(),'exclude_top10pct_positive_pct':100*(trim>0).mean(),'positive_gain_effective_n':sg**2/(g**2).sum() if sg>0 else np.nan,'sessions_after_start':count,'breadth21_median_pct':100*bs.median(),'breadth21_majority_days':int((bs>=.5).sum()),'breadth21_two_thirds_days':int((bs>=2/3).sum()),'breadth21_unknown_member_days':int((len(mem)-k21.loc[wi]).sum()),'top1_symbol':ret.index[0],'top1_name':M.loc[ret.index[0],'name'],'top1_return_pct':100*ret.iloc[0]}
  # Longest run refers to observed sector sessions; UNKNOWN breadth days cannot count.
  flag=(bs>=2/3).tolist(); best=cur=0
  for val in flag:
   cur=cur+1 if val else 0;best=max(best,cur)
  rr['breadth21_two_thirds_longest_sessions']=best
  rows.append(rr)
  for st in mem:
   vv=P.loc[z,st]/P.loc[a,st]-1
   members.append({'sector':sid,'industry':c['name'],'window':label,'start':str(a.date()),'end':str(z.date()),'symbol':st,'name':M.loc[st,'name'],'start_close':P.loc[a,st],'end_close':P.loc[z,st],'return_pct':100*vv,'endpoint_known':bool(np.isfinite(vv)),'start_known':bool(np.isfinite(P.loc[a,st])),'end_known':bool(np.isfinite(P.loc[z,st])),'first_valid_date':str(P[st].first_valid_index().date()) if P[st].first_valid_index() is not None else '', 'last_valid_date':str(P[st].last_valid_index().date()) if P[st].last_valid_index() is not None else '','path_observed_n':int(nobs[st]),'path_expected_n':len(pr)})
Q=pd.DataFrame(rows);U=pd.DataFrame(members);D=pd.concat(daily,ignore_index=True);V=pd.DataFrame(coverage)
assert V.research_pool_n.sum()==246
assert not U.duplicated(['sector','window','symbol']).any()
assert (Q.known_endpoint_n+Q.unknown_endpoint_n==Q.pool_n).all()
assert (Q.positive_n<=Q.known_endpoint_n).all()
assert (D.known21+D.unknown21==D.pool_n).all()
print('COVERAGE');print(V.to_string(index=False))
print('MAIN');print(Q[Q.window.isin(['二次底部至行业峰值','重返前高至行业峰值','行业峰值至截止'])][['name','window','start','end','pool_n','known_endpoint_n','unknown_endpoint_n','industry_return_pct','positive_n','over50_n','over100_n','p25_pct','median_pct','p75_pct','equal_initial_mean_pct','top1_positive_gain_share_pct','top3_positive_gain_share_pct','top10pct_n','top10pct_positive_gain_share_pct','exclude_top10pct_mean_pct','sessions_after_start','breadth21_majority_days','breadth21_two_thirds_days','breadth21_two_thirds_longest_sessions','breadth21_median_pct','full_path_valid_n','daily_intermediate_missing_cells','top1_symbol','top1_return_pct']].to_string(index=False))
if '--save' in sys.argv:
 O.mkdir(exist_ok=True)
 (O/'PROTOCOL.txt').write_text('研究仅描述五个已固定行业周期的成员分布。先固定行业周期日期再计算，未按个股最高点拼接。2026-10-22现有名单与原1709池交集，NON-PIT。复权日收盘仅在真实且有效观测使用，不前填。缺起点、终点或中途日均显式未知；两端分布可包含中途缺价，完整路径数量另列。未覆盖成员不按零。涨幅集中度为等初始本金的正涨幅份额，并非真实指数权重贡献。21日持续性是共同交易日两个端点的价格方向，未知单列，不要求中间21日全有效，不是新实时门。主升与回撤均列，不因暴涨单股变成必须捕获的目标。',encoding='utf-8')
 Q.to_csv(O/'WINDOW_PARTICIPATION.csv',index=False);U.to_csv(O/'ALL_MEMBER_WINDOW_RETURNS.csv',index=False);D.to_csv(O/'DAILY_MEMBER_BREADTH.csv',index=False);V.to_csv(O/'MEMBER_COVERAGE.csv',index=False)
 for sid,P in prices.items():P.to_csv(O/(sid+'_VALID_MEMBER_CLOSES.csv'))
 json.dump(sourcehash,open(O/'SOURCE_SHA256.json','w'),ensure_ascii=False,indent=2)
 for p,s in sourcehash.items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==s
 json.dump({'source_files':len(sourcehash),'source_hash_match':True,'source_unchanged':True,'stock_n':246,'current_master_total_n':int(V.current_master_n.sum()),'price_rule':'frozen adjusted close; observed and eligible and not invalid/synthetic; no forward fill; exact dates','member_rule':'2026-10-22 current industry roster intersect frozen1709; NON-PIT; uncovered member UNKNOWN','concentration_rule':'equal initial capital positive price gains; not true industry index weight attribution','rolling_rule':'21 common industry sessions exact two endpoints, before start history allowed','windows':'existing independent sector cycle dates unchanged, all hindsight descriptive, not live signal','not_proven':'survivorship-free breadth, true index weight concentration, causal tradability, mandatory stock targets','qa_pass':True},open(O/'QA.json','w'),ensure_ascii=False,indent=2)
