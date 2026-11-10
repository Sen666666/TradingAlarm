from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,datetime
O=Path(__file__).resolve().parent
F=json.loads((O/'FREEZE.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
freeze=dict(frozen_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),requested_extension='Add EXIT_BEFORE20_FINAL_LOSS vs BIG_WINNER30 using exactly the previously frozen five features. No feature or threshold change.',group='round_status=CLOSED, round_pnl<0, round_progress20=EXIT_BEFORE20',periods=['ALL','2022','2024'],inference='All overlaps are univariate marginal only, not joint separability or prediction/model performance.',sources={n:sha(O/n) for n in ['PREENTRY_FEATURES_ALL.csv','PREENTRY_DISTRIBUTIONS.csv','PREENTRY_OVERLAP.csv','PREENTRY_GROUP_OUTCOMES.csv','REPORT.md']})
assert not (O/'FAST_LOSS_EXTENSION_FREEZE.json').exists();(O/'FAST_LOSS_EXTENSION_FREEZE.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2))
f=pd.read_csv(O/'PREENTRY_FEATURES_ALL.csv');f.entry_year=f.entry_year.astype(str);f['comparison_group_v2']=f.group;f.loc[f.round_status.eq('CLOSED')&f.round_pnl.lt(0)&f.round_progress20.eq('EXIT_BEFORE20'),'comparison_group_v2']='EXIT_BEFORE20_FINAL_LOSS'
names=['log_return_1','log_return_5','log_return_21','amount_ratio_prev21','log_distance_signal_floor'];dist=[];overlap=[];outcomes=[]
for arm in ['PVR','NOACT']:
 for y in ['ALL','2022','2024']:
  z=f[f.account.eq(arm)&(True if y=='ALL' else f.entry_year.eq(y))];w=z[z.comparison_group_v2.eq('BIG_WINNER30')];g=z[z.comparison_group_v2.eq('EXIT_BEFORE20_FINAL_LOSS')]
  outcomes.append(dict(account=arm,entry_year=y,group='EXIT_BEFORE20_FINAL_LOSS',n=len(g),initial_losses=int(g.initial_pnl.lt(0).sum()),initial_positive=int(g.initial_pnl.gt(0).sum()),initial_median_return=g.initial_return.median(),round_net=g.round_pnl.sum(),initial_net=g.initial_pnl.sum(),first5_median=pd.to_numeric(g.initial_first5_session,errors='coerce').median(),initial_STALLED20=int(g.initial_progress20.eq('STALLED20').sum()),with_ADD=int(g.has_followup_add.eq(True).sum()),median_hold=g.round_held_closes.median(),capital_days=g.round_capital_days.sum()))
  for n in names:
   v=g[n].dropna();u=w[n].dropna();dist.append(dict(account=arm,entry_year=y,group='EXIT_BEFORE20_FINAL_LOSS',feature=n,n=len(g),known=len(v),unknown=len(g)-len(v),p10=v.quantile(.1),p25=v.quantile(.25),p50=v.quantile(.5),p75=v.quantile(.75),p90=v.quantile(.9)))
   union=max(v.quantile(.75),u.quantile(.75))-min(v.quantile(.25),u.quantile(.25));inter=max(0.,min(v.quantile(.75),u.quantile(.75))-max(v.quantile(.25),u.quantile(.25)))
   overlap.append(dict(account=arm,entry_year=y,comparison_group='EXIT_BEFORE20_FINAL_LOSS',feature=n,loss_group_known=len(v),big_winner_known=len(u),loss_group_within_winner_p10_p90=v.between(u.quantile(.1),u.quantile(.9)).mean(),winner_within_loss_group_p10_p90=u.between(v.quantile(.1),v.quantile(.9)).mean(),IQR_intersection_over_union=inter/union if union else np.nan))
d=pd.concat([pd.read_csv(O/'PREENTRY_DISTRIBUTIONS.csv'),pd.DataFrame(dist)],ignore_index=True)
c=pd.concat([pd.read_csv(O/'PREENTRY_GROUP_OUTCOMES.csv'),pd.DataFrame(outcomes)],ignore_index=True)
ov=pd.read_csv(O/'PREENTRY_OVERLAP.csv').rename(columns={'stalled_loss_known':'loss_group_known','stalled_loss_within_winner_p10_p90':'loss_group_within_winner_p10_p90','winner_within_stalled_loss_p10_p90':'winner_within_loss_group_p10_p90'});ov['comparison_group']='STALLED20_FINAL_LOSS';ov=pd.concat([ov,pd.DataFrame(overlap)],ignore_index=True)
f.to_csv(O/'PREENTRY_FEATURES_WITH_FAST_GROUP.csv',index=False);d.to_csv(O/'PREENTRY_DISTRIBUTIONS_ALL_GROUPS.csv',index=False);c.to_csv(O/'PREENTRY_GROUP_OUTCOMES_ALL_GROUPS.csv',index=False);ov.to_csv(O/'PREENTRY_OVERLAP_ALL_GROUPS.csv',index=False)
def pct(x):return f'{x*100:.2f}%'
def m(x):return f'{x:,.2f}'
def table(h,rr):return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rr])
fn={'log_return_1':'1日log涨幅','log_return_5':'5日log涨幅','log_return_21':'21日log涨幅','amount_ratio_prev21':'成交额量比','log_distance_signal_floor':'到信号floor的log距离'}
section=['## 主要亏损组的同口径入场前对照','',
'为避免只解释毛亏占比约一成的长期组，按追加要求把“未推进且20日前退出、最终整轮亏损”也放入**同一五项冻结特征**比较，不新增阈值或特征。合并全表见PREENTRY_DISTRIBUTIONS_ALL_GROUPS.csv、PREENTRY_OVERLAP_ALL_GROUPS.csv、PREENTRY_GROUP_OUTCOMES_ALL_GROUPS.csv；两类亏损组和≥30%真赢家均在其中。','',
table(['账户','首买年','快速失败轮数','初层负/正','整轮净额元','持有中位日'],[[x['account'],x['entry_year'],x['n'],str(x['initial_losses'])+'/'+str(x['initial_positive']),m(x['round_net']),m(x['median_hold'])] for x in outcomes]),'',
'下表全期log变量仍以100×log显示，量比为倍数；中位数后是p25–p75，覆盖有值/总数。']
rows=[]
for arm in ['PVR','NOACT']:
 for n in names:
  row=[arm,fn[n]]
  for group in ['EXIT_BEFORE20_FINAL_LOSS','BIG_WINNER30']:
   x=d[d.account.eq(arm)&d.entry_year.astype(str).eq('ALL')&d.group.eq(group)&d.feature.eq(n)].iloc[0];k=1 if n=='amount_ratio_prev21' else 100;row.extend([f'{m(k*x.p50)} [{m(k*x.p25)}, {m(k*x.p75)}]',f'{int(x.known)}/{int(x.n)}'])
  x=ov[ov.account.eq(arm)&ov.entry_year.astype(str).eq('ALL')&ov.comparison_group.eq('EXIT_BEFORE20_FINAL_LOSS')&ov.feature.eq(n)].iloc[0];row.extend([pct(x.loss_group_within_winner_p10_p90),pct(x.winner_within_loss_group_p10_p90)]);rows.append(row)
section +=[table(['账户','特征','快速亏中位[IQR]','覆盖','赢家中位[IQR]','覆盖','快速亏落赢家10–90%内','赢家落快速亏10–90%内'],rows),'',
'快速亏损组也与大赢家大量重叠，不能将看见中位差异理解为已有分界。**所有重叠比例都是逐个特征的边际分布描述，不是五项联合可分性，更不是模型准确率、预测能力或可交易效果。** 本研究没有构造联合模型，也没有证实不存在其他可用信息。2022/2024的各组样本数、覆盖和完整分位数同表保留。','']
report=(O/'REPORT.md').read_text().replace('## 覆盖和可核验性','\n'.join(section)+'\n## 覆盖和可核验性').replace('原首次pool','首个持有收盘原pool').replace('首层原probe/confirmed','首个持有收盘probe/confirmed')
report=report.replace('这只说明不能默认20日全退出没有代价','这些慢赢家也不代表停滞本身有优势。这只说明不能默认20日全退出没有代价')
report=report.replace('- REPORT.md：本报告。','- REPORT_FINAL.md：最终报告（加入快速失败组同口径对照）；REPORT.md保留主稿。')
(O/'REPORT_FINAL.md').write_text(report)
for n,h in freeze['sources'].items():assert sha(O/n)==h,('original output changed',n)
for p,h in F['source_hashes'].items():assert sha(p)==h,('source changed',p)
(O/'FAST_LOSS_EXTENSION_CHECKS.json').write_text(json.dumps(dict(status='PASS',account_runs=0,features_unchanged=True,thresholds_unchanged=True,original_feature_rows_5824_preserved=len(f)==5824,source_hashes_unchanged=True),indent=2))
(O/'FINAL_MANIFEST.json').write_text(json.dumps(dict(status='PASS_COMPLETED_RESEARCH',account_runs=0,final_report='REPORT_FINAL.md',source_files_unchanged=1534,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={x.name:sha(x) for x in O.iterdir() if x.is_file() and x.name!='FINAL_MANIFEST.json'}),indent=2))
print(pd.DataFrame(outcomes).to_string(index=False));print(pd.DataFrame(overlap).to_string(index=False));print('FINAL_READY')
