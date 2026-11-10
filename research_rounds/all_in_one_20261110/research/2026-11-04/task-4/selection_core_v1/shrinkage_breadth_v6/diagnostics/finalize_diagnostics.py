"""Bind and summarize existing frozen v6 diagnostic outputs; no re-evaluation."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 p=pd.read_parquet(O/'PATH_TAIL_EXPOSURE_BY_PERIOD_AND_N.parquet');net=pd.read_parquet(O/'ADDED_MINUS_REMOVED_TAIL_HITS.parquet')
 m=p.loc[p.grouping.eq('study_window')&p.stratum.eq('ALL')].sort_values(['period','method']).reset_index(drop=True)
 old=json.loads((O/'FIRST_EXECUTION_UNCHANGED_MAIN_AND_NET_CHECK.json').read_text());before=pd.DataFrame(old['main_stage_pooled_rows']).sort_values(['period','method']).reset_index(drop=True)
 pd.testing.assert_frame_equal(before[m.columns],m,check_dtype=False,check_exact=True)
 pd.testing.assert_frame_equal(pd.DataFrame(old['tail_net_rows']),net,check_dtype=False,check_exact=True)
 daily=pd.read_parquet(O/'DAILY_TAIL_EXPOSURE_COUNTS.parquet');assert len(daily)==10850 and daily.groupby(['method','stratum']).size().eq(1085).all()
 dump('REPORTING_FIX_INVARIANCE_CHECK.json',dict(all_main_columns_exact_unchanged=True,all_added_removed_net_columns_exact_unchanged=True,new_daily_rows=len(daily),each_method_stratum_full1085=True,old_daily_rows=old['old_daily_rows'],correction_scope='Emit absent sparse strata on known days; their all90 coverage is0 if all90 tail>0, within-stratum/precision denominator0 remains unknown.'))
 drift=pd.read_parquet(O/'NET_COUNT_UNCHANGED_MARKET_DRIFT_AND_ACCELERATION.parquet');focal=pd.read_parquet(O/'PREDECLARED_924_CUTOFF_AND_FOCAL.parquet');case=pd.read_parquet(O/'FIXED_V5_CASES_ALL_RANKS_AND_LABELS.parquet');status=json.loads((O/'RUN_STATUS.json').read_text())
 lines=['v6 κ=10固定收缩广度：完整行业信号级诊断','',
 '结论：固定收缩减少小子池极端排序，但本次单项代入没有跨阶段一致改善，且牺牲稀疏上行尾。924软件与2026半导体关键日仍未进T前三。平均MAE略改善与部分上尾损失须同时保留，不把统计平滑叫alpha。',
 '1085会话×90=97650行业日；T0与T10每天各3，原T0逐行与旧缓存exact。κ10、R5、权重和名额都冻结，P未改；仅复用旧20共同会话行业指数价格标签，零账户/新CP/新标签。',
 '',
 '主表（未来20相对MFE正且当日all90 midpercentile>=.90为评估上尾；行业日均值是log变化，不是账户收益）：']
 for period,g in m.groupby('period',sort=False):
  z=g.set_index('method');a=z.loc['T0_ORIGINAL'];b=z.loc['T10_KAPPA10'];lines.append(f'{period}: 各{int(a.industry_days)}行业日；尾命中{int(a.tail_hits)}→{int(b.tail_hits)}，尾分母{int(a.tailN_all90)}；coverage {a.coverage_of_all90_tail:.6%}→{b.coverage_of_all90_tail:.6%}；precision {a.precision:.6%}→{b.precision:.6%}；relative-final均值 {a.final20_rel_log_mean:.9f}→{b.final20_rel_log_mean:.9f}；absolute-final<=0 {a.final20_abs_nonpositive_rate:.6%}→{b.final20_abs_nonpositive_rate:.6%}；absolute MAE均值 {a.mae20_abs_log_mean:.9f}→{b.mae20_abs_log_mean:.9f}。')
 lines.extend(['','固定稀疏层及新增/移出代价：'])
 for r in net.loc[net.stratum.isin(['SPARSE_N_LE10','N1'])].itertuples():lines.append(f'{r.period} {r.stratum}: 新增{r.added}、移出{r.removed}；新增尾命中{r.added_tail_hits}、移出尾命中{r.removed_tail_hits}，净{r.net_tail_hits:+d}。')
 lines.extend(['','关键原例与市场漂移：'])
 for r in focal.itertuples():lines.append(f'924 {r.industry_static}: n={r.n}, Δu={r.du}; Self={r.Self:.9f}, Market={r.Market:.9f}, D原={r.D_original:.9f}, D收缩={r.D_shrunk:.9f}; D次序{r.D_original_order}→{r.D_shrunk_order}, T次序{r.T0_order}→{r.T10_order}。')
 for r in case.loc[case.relative_session.eq(0)&case.case_id.isin(['main_semis_2026jan5','aux_semis_2026jan15','counter_realestate_2022jan24','counter_multifinance_2024oct8'])].itertuples():lines.append(f'{r.case_id} {r.date}: n={r.n}, Δu={r.du}, Self={r.Self:.9f}, Market={r.Market:.9f}, D原={r.D_original:.9f}, D收缩={r.D_shrunk:.9f}; T{r.T0_order}→{r.T10_order}，选中{r.T0_selected}→{r.T10_selected}。')
 for r in drift.loc[drift.stratum.eq('ALL')&drift.drift_class.eq('NET_COUNT_UNCHANGED_POSITIVE_MARKET_DRIFT')].itertuples():lines.append(f'{r.study_window}: Δu=0但D收缩>0 共{r.industry_days}行业日，T0选中{r.T0_selected}、T10选中{r.T10_selected}；净人数不变不能说无个股穿越，且不能把漂移原值数量当选中数量。')
 lines.extend(['','计算与解释边界：',
 'n/u1/u0均同T U_T成员；原U需要25会话完整保证两端数据，不是两日均合格流动性资格交集。m1/m0则各自日期own-U。Lag B0收缩是T日回看当前cohort，不是T-5旧发布值。',
 'D收缩=(u1-u0)/(n+10)+10*(m1-m0)/(n+10)，市场项对小N更大，市场含本行业且两端U可迁移，κ10不是10个独立样本置信度。绝不能将市场借入项称行业自身扩散。',
 '前5日m0从旧B_lag5_ownU×N_U_previous5恢复整数；后1080日与主表实际T-5汇总exact。准备文件ORIGINAL_WARM_INPUT_COUNTS_2021不是执行输入。',
 'a5收缩严格分成a5_Self+a5_Market；前5日未知未填0。两端n及cohort可变，二阶变化不是纯行业加速度。',
 '主尾参考始终all90，不在稀疏层重新挑前10%。coverage_of_all90_tail分母为阶段全部all90尾，coverage_within_stratum另列该层尾分母；precision分母为已选且标签已知。空尾unknown，不造0。',
 '新增/移出基于T0/T10实时旗标，无未来挑选。稀疏固定n<=10、n1，不按结果改边界；已有168固定例与全部90行业排名/原路径均保留。',
 '日线行业指数标签不是股票篮子、可成交订单或账户收益；本批静态1709/当前行业映射非PIT，收缩不能修复历史非随机池与成员缺失。全部阶段是探索性历史诊断，非真正盲验证。',
 '仅补强潜在空层daily口径分支：本批首末日表均为10850行，没有实际补行。首执行source/hash与旧ALL/净hits已保，REPORTING_FIX_INVARIANCE_CHECK证明所有主列及added/removed列exact不变；规则明确潜在稀疏空日selected为0，对全90非空尾coverage为0，层内空分母仍NA。未改变κ/计数/排名/标签。',
 '',f'最终核心诊断耗时{status["seconds"]:.2f}秒；原特征生成成本另见features/SUMMARY.json。关键文件：PATH_TAIL_EXPOSURE_BY_PERIOD_AND_N、ADDED_MINUS_REMOVED_TAIL_HITS、ORIGINAL_ADDED_REMOVED_RETAINED_SIGNALS、NET_COUNT_UNCHANGED_MARKET_DRIFT_AND_ACCELERATION、FIXED_V5_CASES_ALL_RANKS_AND_LABELS。'])
 (O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
 dump('FINAL_STATUS.json',dict(status='COMPLETE_FROZEN_DIAGNOSTIC',rows=97650,days=1085,each_day_N90=True,each_method_selected=3,kappa=10,original_T0_exact=True,no_account=True,no_new_label=True,source_warm_consumed=False,main_outcome_unchanged_after_reporting_fix=True,not_cross_stage_consistent_improvement=True,sparse_tail_cost_retained=True))
 files={str(p.relative_to(O)):sha(p)for p in sorted(O.iterdir())if p.is_file()and p.name!='OUTPUT_SHA256.json'};dump('OUTPUT_SHA256.json',files)
 print(json.dumps({'complete':True,'bound_files':len(files),'main_and_net_invariance':True,'directory':str(O.resolve())},ensure_ascii=False))
if __name__=='__main__':main()
