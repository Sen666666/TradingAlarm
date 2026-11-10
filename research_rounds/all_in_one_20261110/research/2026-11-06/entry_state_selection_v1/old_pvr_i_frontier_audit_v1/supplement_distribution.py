"""Append-only descriptive distribution of existing PVR rounds. No consumer or new model."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent
names=['DISTRIBUTION_SUPPLEMENT_PROTOCOL.json','DISTRIBUTION_SUMMARY.csv','DISTRIBUTION_QUALITY_CROSS.csv','TAIL_GE30_ROUNDS.csv','DISTRIBUTION_FOOTNOTE.md','DISTRIBUTION_SUPPLEMENT_QA.json','DISTRIBUTION_SUPPLEMENT_SEAL.json']
assert not any((O/n).exists()for n in names),'Never overwrite prior supplement'
prior={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name!=Path(__file__).name}
oldseal=json.loads((O/'FINAL_OUTPUT_SHA256.json').read_text())
for n,h in oldseal.items():assert prior[n]==h,('prior artifact changed',n)
protocol=dict(mode='EXISTING_OLD_PVR_FILLED_ROUND_DESCRIPTIVE_ONLY_NOT_AB',management_end='2026-05-15',windows={'2022_full':['2022-01-01','2022-12-31'],'2024_full':['2024-01-01','2024-12-31'],'2024_Sep_Dec':['2024-09-01','2024-12-31']},closed_only_for_outcome_metrics=True,mean_win='Arithmetic mean of positive original round_pnl in CNY',mean_loss='Arithmetic mean of negative original round_pnl in CNY; negative sign retained',payoff='mean_win / abs(mean_loss), undefined without wins or losses',mean_net='Arithmetic mean original round_pnl over all closed rounds',tail='Original round_return_on_cumulative_cost >= 0.30; original cumulative buy gross plus fees denominator, includes all original layers; no new R denominator',empty_groups='n=0 explicit; undefined means and sums remain null. For nonempty closed groups with no tail, tail_n=0 and tail_net=0.',quality='Signal-source UNKNOWN, observed holding-facts gaps and financial certification are different axes. No CP today is an observed category, not UNKNOWN.',financial_contract='Old proxy cash plus accrued dividends; every row remains NOT_NET80_CERTIFIED. No new financial validation.',original_artifacts='Keep every prior artifact byte unchanged. New supplementary report is a footnote, not a replacement.')
(O/names[0]).write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
f=pd.read_csv(O/'ALL_PVR_ROUNDS.csv')
raw=pd.read_csv(O/'ALL_PVR_ROUNDS.csv',dtype=str,keep_default_na=False)
f['pnl_decimal']=raw.round_pnl.map(lambda x:D(x)if x else None)
f['signal_unknown']=(f.market_i_buy_class.isin(['UNKNOWN','OUTSIDE_I'])|f.market_cp_class.isin(['UNKNOWN','OUTSIDE_I'])|f.actual_round_in_i_class.eq('UNKNOWN_I')|f.source_status.ne('ORIGINAL_LEDGER_AND_MANIFEST')|(~f.i_start_observed_0to1)| (f.cp_receipt & (f.canonical_CP1_id.isna()|f.cp_trace_unknown_n.fillna(0).gt(0))))
f['held_gap']=f.held_source_absent_days.gt(0)
f['tail_ge30']=f.closed & f.round_return_on_cumulative_cost.ge(.30)
assert f.loc[f.closed,'round_pnl'].notna().all();assert f.loc[f.closed,'round_return_on_cumulative_cost'].notna().all()
dims={'ALL':['ALL'],'market_i_buy_class':['FIRST_I_BUY','LATER_I_BUY','NON_I_BUY_DAY','UNKNOWN','OUTSIDE_I'],'market_cp_class':['FIRST_CP_RECEIPT','LATER_CP_RECEIPT','NO_CP_RECEIPT_DAY','UNKNOWN','OUTSIDE_I'],'actual_round_in_i_class':['FIRST_ACTUAL_ROUND_IN_I','REPEAT_ACTUAL_ROUND_IN_I','UNKNOWN_I']}
Z=D(0)
def sm(g):return sum(g.pnl_decimal,Z)if len(g)else None
def metric(g):
 c=g[g.closed];w=c[c.round_pnl.gt(0)];l=c[c.round_pnl.lt(0)];z=c[c.round_pnl.eq(0)];t=c[c.tail_ge30];mw=sm(w)/D(len(w))if len(w)else None;ml=sm(l)/D(len(l))if len(l)else None
 return dict(n=len(g),closed_n=len(c),unclosed_n=int((~g.closed).sum()),win_n=len(w),loss_n=len(l),zero_n=len(z),win_rate=len(w)/len(c)if len(c)else None,mean_win_cny=str(mw)if mw is not None else None,mean_loss_cny=str(ml)if ml is not None else None,payoff=float(mw/abs(ml))if mw is not None and ml is not None else None,mean_net_cny=str(sm(c)/D(len(c)))if len(c)else None,closed_net_cny=str(sm(c))if len(c)else None,median_net_cny=float(c.round_pnl.median())if len(c)else None,p10_net_cny=float(c.round_pnl.quantile(.1))if len(c)else None,p90_net_cny=float(c.round_pnl.quantile(.9))if len(c)else None,mean_original_return=float(c.round_return_on_cumulative_cost.mean())if len(c)else None,tail_ge30_n=len(t),tail_ge30_net_cny=str(sm(t)if len(t)else Z)if len(c)else None,tail_ge30_share_closed=len(t)/len(c)if len(c)else None,non_tail_closed_n=len(c)-len(t),non_tail_net_cny=str(sm(c)- (sm(t)or Z))if len(c)else None,signal_unknown_n=int(g.signal_unknown.sum()),held_facts_gap_n=int(g.held_gap.sum()),held_raw_close_bad_n=int(g.held_raw_close_bad_days.gt(0).sum()),held_factor_bad_n=int(g.held_factor_bad_days.gt(0).sum()),financial_uncertified_n=len(g),financial_NET80_certified_n=0,financial_status='OLD_PROXY_ONLY_NOT_NET80_CERTIFIED',group_status='OBSERVED'if len(g)else 'EMPTY_NO_OBSERVATIONS')
summary=[];quality=[];tails=[]
for window,(lo,hi)in protocol['windows'].items():
 z=f[f.entry_day.between(lo,hi)]
 for dim,values in dims.items():
  for value in values:
   g=z if dim=='ALL'else z[z[dim].eq(value)]
   summary.append(dict(window=window,dimension=dim,value=value,**metric(g)))
   for signal in ['ALL_SIGNAL_STATES','KNOWN_SIGNAL_SOURCE','UNKNOWN_SIGNAL_SOURCE']:
    a=g if signal=='ALL_SIGNAL_STATES'else g[g.signal_unknown.eq(signal=='UNKNOWN_SIGNAL_SOURCE')]
    for gap in ['ALL_HELD_FACTS','NO_HELD_FACTS_GAP','HELD_FACTS_GAP']:
     b=a if gap=='ALL_HELD_FACTS'else a[a.held_gap.eq(gap=='HELD_FACTS_GAP')]
     quality.append(dict(window=window,dimension=dim,value=value,signal_source_axis=signal,held_facts_axis=gap,**metric(b)))
 for r in z[z.tail_ge30].sort_values(['entry_day','sid','first_layer']).to_dict('records'):
  tails.append(dict(window=window,**{k:r[k]for k in ['round_id','sid','signal_day','entry_day','closed_day','first_kind','first_reason','i_key','market_i_buy_class','market_i_buy_ordinal','market_cp_class','market_cp_ordinal','actual_round_in_i_class','actual_round_ordinal_in_i','round_cost','round_pnl','round_return_on_cumulative_cost','round_trade_cash','round_dividend_accrual','held_source_absent_days','financial_status']}))
s=pd.DataFrame(summary);q=pd.DataFrame(quality);pd.DataFrame(tails).to_csv(O/'TAIL_GE30_ROUNDS.csv',index=False);s.to_csv(O/'DISTRIBUTION_SUMMARY.csv',index=False);q.to_csv(O/'DISTRIBUTION_QUALITY_CROSS.csv',index=False)
# Additive/weighted-mean identities; tail and non-tail are partitions, not new accounts.
for window,z in s.groupby('window'):
 allrow=z[z.dimension.eq('ALL')].iloc[0]
 for dim in dims:
  if dim=='ALL':continue
  a=z[z.dimension.eq(dim)];assert a.n.sum()==allrow.n;assert a.closed_n.sum()==allrow.closed_n;assert a.tail_ge30_n.sum()==allrow.tail_ge30_n
  for col in ['closed_net_cny','tail_ge30_net_cny']:
   total=sum((D(v)for v in a[col]if pd.notna(v)),Z);assert abs(total-D(allrow[col]))<D('.00000001'),(window,dim,col)
 for r in z[z.closed_n.gt(0)].to_dict('records'):
  assert abs(D(r['closed_net_cny'])-D(r['tail_ge30_net_cny'])-D(r['non_tail_net_cny']))<D('.00000001')
  cash=(D(r['mean_win_cny'])*r['win_n']if r['win_n']else Z)+(D(r['mean_loss_cny'])*r['loss_n']if r['loss_n']else Z)
  assert abs(cash-D(r['closed_net_cny']))<D('.00000001')
for n,h in prior.items():assert hashlib.sha256((O/n).read_bytes()).hexdigest()==h,('prior output changed',n)
sourcehash=json.loads((O/'SOURCE_SHA256.json').read_text())
for p,row in sourcehash.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==row['sha256'],('source changed',p)
lines=['# 旧 PVR 完整回合分布补充脚注','','本补充保留原报告及所有既有hash，未修改任何原产物。仅描述旧真实PVR连续消费者已经发生的完整股票回合，不是新A+B同日CP关联收益。三窗统一管理终点2026-05-15。','','## 原CP分层分布','', '| 窗口 | 当日CP类别 | 回合/赢 | 均赢 | 均亏 | payoff | 平均净额 | 总净额 | ≥30%尾数 | 尾净额 |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in summary:
 if r['dimension']=='market_cp_class'and r['n']:
  lines.append(f"| {r['window']} | {r['value']} | {r['n']}/{r['win_n']} | {float(r['mean_win_cny']):,.2f} | {float(r['mean_loss_cny']):,.2f} | {r['payoff']:.3f} | {float(r['mean_net_cny']):,.2f} | {float(r['closed_net_cny']):,.2f} | {r['tail_ge30_n']} | {float(r['tail_ge30_net_cny']):,.2f} |")
lines+=['','## 定义与限制','- 金额为元。均赢仅正净额回合均值，均亏仅负净额回合均值且保留负号；payoff=均赢/绝对值(均亏)，平均净额对全部已闭回合取均值。没有赢或亏时不填造payoff。','- ≥30%使用原round_return_on_cumulative_cost，即完整回合净额/各买层累计含费成本。多层、加仓、仓位大小不同，不把它改写为统一风险R。尾部净额是原回合净额合计，不是新组合、反事实或可实现增量。','- 第一CP意为原市场I周期内第一张receipt恰在首仓信号日；不是账户首次消费CP，也不是首次实际回合。完整市场前史与实际回合序号继续分开。','- NO_CP_RECEIPT_DAY、UNKNOWN、OUTSIDE_I和缺行轴均显式列出；n=0表示未观测到该类，均值/净额为空。持有期原facts缺行不自动等于原账mark未知，更不补零。','- 所有回合仍为旧proxy。金融独立认证未完成：红利应计不等于已到账现金，真实可成交性、权益合同与NET80等价财务认证均不作通过声明。','- 均赢/均亏及尾净额是金额加权暴露结果，第一CP的2024Sep-Dec仅16个回合；不据此声称样本外有效、建立门槛或消除重复CP的大赢家。','','## 追加文件','- DISTRIBUTION_SUMMARY.csv：三窗ALL、i_buy、CP、实际回合首/重复分组，含显式空未知类。','- DISTRIBUTION_QUALITY_CROSS.csv：每组分别交叉信号源已知/未知与持有facts缺行/无缺行轴。','- TAIL_GE30_ROUNDS.csv：按时间排列的全部≥30%原回合，保留成本、净额与类别，可逐笔复核。','- DISTRIBUTION_SUPPLEMENT_QA.json与DISTRIBUTION_SUPPLEMENT_SEAL.json：原产物/原源不变核验及追加后封存。']
(O/'DISTRIBUTION_FOOTNOTE.md').write_text('\n'.join(lines)+'\n')
qa=dict(status='PASS_APPEND_ONLY_PVR_DISTRIBUTION',prior_artifacts_unchanged=len(prior),prior_final_seal_verified=True,original_sources_unchanged=len(sourcehash),summary_rows=len(s),quality_rows=len(q),tail_rows_with_overlapping_window_membership=len(tails),group_and_tail_partitions_exact=True,mean_cash_identity_exact=True,new_consumers=0,new_trades=0,new_risk_R=0,all_financial_status='OLD_PROXY_ONLY_NOT_NET80_CERTIFIED')
(O/'DISTRIBUTION_SUPPLEMENT_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
seal={'prior_artifact_snapshot_unchanged':prior,'current_all_artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()},'scope':'Append-only supplementary seal; original FINAL_OUTPUT_SHA256.json remains byte-identical.'}
(O/'DISTRIBUTION_SUPPLEMENT_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2))
print(json.dumps(qa));print(s[s.dimension.isin(['ALL','market_cp_class'])&s.n.gt(0)][['window','value','n','win_n','mean_win_cny','mean_loss_cny','payoff','mean_net_cny','closed_net_cny','tail_ge30_n','tail_ge30_net_cny']].to_string(index=False))
