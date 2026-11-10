from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
m=pd.read_csv(O/'MATCHED_COMPLETE_DATE_RESULTS.csv');q=pd.read_csv(O/'QUARTER_PAIRED_RESULTS.csv');roots=pd.read_csv(O/'ROOT_EPISODES.csv',keep_default_na=False)
cov=pd.read_csv(O/'ANNUAL_BIG_ROOT_COVERAGE.csv');rep=pd.read_csv(O/'ANNUAL_REPLACEMENTS.csv');coverage=pd.read_csv(O/'SCORE_COVERAGE_BY_YEAR.csv');sc=pd.read_parquet(O/'CANDIDATE_Q.parquet');sel=pd.read_parquet(O/'SELECTED_WITH_FIXED_LABELS.parquet');cases=pd.read_csv(O/'FIXED_CASE_QUEUE_EFFECTS.csv');audit=json.loads((O/'SUMMARY.json').read_text())
def tab(d,cols=None,digits=3):
 z=d.copy() if cols is None else d[cols].copy()
 for c in z:
  if pd.api.types.is_float_dtype(z[c]):z[c]=z[c].map(lambda x:f'{x:.{digits}f}' if pd.notna(x) else 'UNKNOWN')
 return '| '+' | '.join(map(str,z.columns))+' |\n| '+' | '.join(['---']*len(z.columns))+' |\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in z.itertuples(index=False,name=None))
known=[]
for (a,y),g in roots[roots.epoch.ne('None')].groupby(['account','year']):
 b=g[g.big60];known.append(dict(account=a,year=int(y),explicit_epoch_roots=len(g),complete60_roots=int(g.complete60.sum()),big_roots=len(b),base_captured=int(b.ORIGINAL_PVR_early_capture.sum()),Q_captured=int(b.CONTINUOUS_Q_early_capture.sum()),lost=int(b.lost.sum()),added=int(b.added.sum()),net_added=int(b.added.sum()-b.lost.sum())))
known=pd.DataFrame(known);known.to_csv(O/'EXPLICIT_EPOCH_BIG_ROOT_COVERAGE.csv',index=False)
readouts=[]
for (a,y),g in m.groupby(['account','year']):
 x=g.set_index('horizon');h5=x.loc[5];h20=x.loc[20]
 readouts.append(dict(account=a,year=int(y),paired_days5=int(h5.common_complete_dates),base_ret5_pct=100*h5.base_day_equal_ret,Q_ret5_pct=100*h5.Q_day_equal_ret,delta_ret5_pp=100*h5.day_paired_diff,paired_days20=int(h20.common_complete_dates),base_ret20_pct=100*h20.base_day_equal_ret,Q_ret20_pct=100*h20.Q_day_equal_ret,delta_ret20_pp=100*h20.day_paired_diff,base_close_MAE20_pct=100*h20.base_day_equal_mae,Q_close_MAE20_pct=100*h20.Q_day_equal_mae,delta_close_MAE20_pp=100*h20.mae_day_paired_diff))
readouts=pd.DataFrame(readouts);readouts.to_csv(O/'ANNUAL_READOUT_PERCENT.csv',index=False)
exposure=sel.groupby(['account','year','strategy']).agg(original_H1_mean=('original_H1','mean'),original_PVR_mean=('original_PVR','mean'),Q_mean=('Q','mean')).reset_index();exposure.to_csv(O/'SELECTED_EXPOSURES.csv',index=False)
quarter=[]
for (a,H),g in q.groupby(['account','horizon']):
 quarter.append(dict(account=a,horizon=H,quarters_with_paired_dates=len(g),return_positive_blocks=int(g.day_paired_diff.gt(0).sum()),return_negative_blocks=int(g.day_paired_diff.lt(0).sum()),close_MAE_worse_blocks=int(g.mae_day_paired_diff.lt(0).sum())))
quarter=pd.DataFrame(quarter);quarter.to_csv(O/'QUARTER_DIRECTION_SUMMARY.csv',index=False)
text='''# 原合法 MOBILE 候选：连续量价涨跌比同日同K检验

## 结论

这轮不支持把原PVR直接替换为这个单独的新排序分数。不是依据七个已知案例作否决，而是完整原条件母体上的一次冻结比较：

- 两账户各五个年度，20观察收益增减不一致。PVR在2024较明显改善，2022/2025/2026下降，2023很小改善；E31也无跨年一致收益优势。
- 两账户所有五个年度，双方全部入选标签完整的共同日期上，20观察收盘MAE均更负。5观察MAE同样各年更差。
- 原大行情root早期捕获，十个账户年度净数全下降。仅看明确epoch的根，十个年度仍全下降。2025的丢失最突出。
- 七例真实同日队列均没有改变同K入选成员。不能再把跨日期分数大小解释为这七例已被实际挤出；总体漏选结论来自全母体根覆盖。

这些是原静态1709股票条件域、原账户持仓/资格被冻结时的离线候选路径结果，不是新账户、可成交组合收益或实际交易胜率，不是真正样本外。两个账户的股票与日期高度重叠，不能当两组独立试验。

## 冻结公式与决策时钟

沿原CP m的21期连续加权涨跌比，数学上近似量价加权Wilder RSI：

λ=20/21，α=1/21；U_t=λU_prev+αm_t max(r_t,0)；D_t=λD_prev+αm_t max(−r_t,0)；Q_t=100U_t/(U_t+D_t)，分母0时为50。

r/m直接读原CP缓存，不重算CP、E0、I、G、PVR或H1。完整原缓存暖历史；仅source segment改变或r/m不可用时清零。原E0/I有效性、native-down、SEEK降锚、receipt消费均不清零。只在当日收盘与成交额已知后用于排名，不能用于同日开盘。

21是指数平均长度，半衰14.2067个原有效观察；不是只看21行。无观察的停牌/假日不造行、不按自然日泄漏。新分数是上涨记账量占比，不是盈利概率。下跌使Q单调不增、上涨使Q单调不减，在0<Q<100内部才严格；旧上涨与旧下跌都保留。

唯一实际计算公式在七例计算前冻结，此后全母体没有改公式、扫参数、加旧高项或混入成熟响应。原双收盘加新证等待规则没有复活。

## 完整候选母体与同K接口

103766条原合法空仓MOBILE候选，PVR 53121、E31 50645；1631只原条件域股票，54852个唯一股票日。保留原当时空仓、fresh CP、I、行业、nominal gap等资格。使用完整原母体，不按旧accepted过滤，不从已成交样本倒推队列。

基线按original_priority_rank、sid升序，逐项等于既有ORIGINAL_PVR入选清单。每个账户每日K=min(20,N)。已知且原PVR有限的槽位按Q.round(12)降序、原PVR.round(12)降序、原priority、sid排序；Q未知或原PVR未知固定原槽。没有最低分入场门槛，没有延迟，没有修改CORE/MOBILE资金竞争、持仓或退出。

Q有限103766，Q UNKNOWN为0；原PVR未知91条另保原槽，可替换103675条。i_buy=False的15530条全部保留在母体。连续有效暖历史<21的77条占0.0742%，没有被事后判UNKNOWN或加门；它们恰好全部属于原PVR未知、因原框架保原槽。这只是可用性诊断。

'''
text+=tab(coverage,['account','year','candidates','known','unknown','short_warm','i_buy_false'])+'\n\n'
text+='''## 标签与主比较口径

直接复用原FIXED_NATIVE_PRICE_LABELS，不重算标签、不混合价格坐标。入口是下一共同观察原raw.open×原facts.factor；终点是信号后第H个共同观察的调整收盘。MAE/MFE是相对该入口、随后H个共同观察收盘的最不利/最有利路径，**不是日内Low/High**，不含费用滑点，不保证开盘订单可成交。

主表只取同日两种队列的所有K条都completeH的日期，未来完整性仅用于评价，不用于选股。每个信号日先对K条路径均值，再对共同日期等权，避免不同队列缺失率或每日候选数量冒充收益优势。2026尾部删失，不将不成熟收益设0。

原ANNUAL_OUTCOMES另保留各方案可成熟事件均值/事件总和/日期等权均值，但不同完整集合的裸差不作为主结论。正收益路径比例也不是原策略已闭局胜率。

## 逐年共同完整日期结果

百分数列表示原/Q平均路径收益；差值为百分点（pp），MAE负得更多即更差。

'''
for a in ['PVR','E31']:
 z=readouts[readouts.account==a]
 text+='### '+a+'\n\n'
 text+=tab(z,['year','paired_days5','base_ret5_pct','Q_ret5_pct','delta_ret5_pp','paired_days20','base_ret20_pct','Q_ret20_pct','delta_ret20_pp'])+'\n\n'
 text+=tab(z,['year','base_close_MAE20_pct','Q_close_MAE20_pct','delta_close_MAE20_pp'])+'\n\n'
text+='''### 事件加总与日期等权的同集合核对

以下仍只用两队列全部成熟的共同日期。事件均值差按每个入选事件等权，日期均值差每个日期等权；“事件收益差之和”是归一化路径收益的百分点相加，不是资金收益、净值或可累积投资回报，事件路径可能重叠。

'''
z=m[m.horizon==20].copy();z['事件均值差pp']=100*z.event_paired_diff;z['日期均值差pp']=100*z.day_paired_diff;z['事件收益差之和pp']=100*z.event_sum_diff
text+=tab(z,['account','year','complete_event_count','事件均值差pp','日期均值差pp','事件收益差之和pp'])+'\n\n'
text+='''## 季度日期块描述

不做网格或显著性筛选，只展示冻结结果跨日期块的方向。存在原母体没有候选的季度，因此每臂是16个有配对日期季度，不虚构缺失季度。2026Q2的PVR20观察仅8个共同完整日期。

'''
text+=tab(quarter)+'\n\n'
text+='''PVR的20观察收益差16季度中7正9负；20观察MAE有15季度更差，仅2024Q2小幅更好。2024Q3和Q4的收益增益不能掩盖其他阶段。由于日期/股票重复与重叠路径，这不是16个独立样本的显著性检验。

## 根周期大行情覆盖

严格复用原口径：每(account,sid,原epoch)最早合法MOBILE为birth；只有birth完整60观察且收盘MFE60≥30%、ret60≥20%才计后验big root。捕获是同根在birth.t到birth.t+5共同日期出现任一入选。big标签不参与Q或排名，绝不挑每根最好起点。

这只是原静态1709条件域的原根代理覆盖，不是历史PIT全A股大行情召回率，也不是买入后盈利兑现。

'''
text+=tab(cov,['account','year','roots','complete60_roots','unknown60_roots','big_roots','base_captured','Q_captured','lost','added','net_added'])+'\n\n'
text+='''### 无明确epoch的敏感性

原重建脚本把intent epoch转成str；445条候选的字面值是“None”，对应402个原root代理，其中39个被原口径记为big。主表完全保留原定义、不合并或重定义根。读取CSV用keep_default_na=False保留字面身份，避免“None”被默认转NA。

下面只是对已存在根表单独取epoch!='None'，不改母体/排序。十个年度净捕获仍均为负，所以全负方向不依赖这些无明确epoch代理。主表与明确epoch表都不证明真实完整I周期识别已经无误。

'''
text+=tab(known,['account','year','big_roots','base_captured','Q_captured','lost','added','net_added'])+'\n\n'
text+='''## 实际替换量与七例同日作用

每次added与removed数量相同；完整替换明细在REPLACEMENTS.csv，全部同日全队列名次在FULL_QUEUE_ORDERS.parquet。不存在只报告被资金选中交易的幸存者偏差，但仍条件于原账户当时资格。

'''
zz=rep.copy();zz['替换比例pct']=100*zz.replacement_fraction
text+=tab(zz,['account','year','days','changed_days','selected_per_strategy','added','替换比例pct'])+'\n\n'
text+=tab(cases,['account','sid','day','N','K','original_rank','Q_rank','original_selected','Q_selected'])+'\n\n'
text+='''七例全部在两账户该日原母体中，但成员无变化。002385和688582名次后移时N≤20，仍全部入选；300182和000506原本就不在离线Top20，Q也未进入。600056末端失败依然两臂第1。600606真反转名次下降一位但N≤20，仍入选。这避免把原实际账户的成交结果与本次独立同K队列混为一谈。

## 可交易性压力诊断与选中暴露

独立只读审计见[执行风险诊断](execution_sensitivity/README.md)及其CSV。one_price_up定义为下一执行观察原OHLC H=L且价高于前观察收盘，不能认定必然买不到，也不是信号时可用的筛选器。只在主实验双方全成熟日期，对这些事后标记槽收益设0，保持K、不替补、不重分资金，未改主体标签或排序。

PVR五年原/Q下一观察一价上涨入选数依次为20/23、10/14、52/54、27/48、13/15。此压力下20观察日均差(Q−原)为−0.1991、−0.1628、+0.5427、−0.0852、−0.5699pp。2024优势仍在，2023很小的主表收益优势消失。非一价也不证明具体订单成交。

同一入选清单的原H1事件均值，Q相对基线五年分别高4.2827、4.4222、3.5100、4.8678、5.4239分（PVR域）。说明Q选中样本有更高原累计涨势分暴露，但这是关联，不是已证明MAE更差的因果归因。完整两臂暴露在SELECTED_EXPOSURES.csv。

机制上，连续涨跌比在保存旧下跌的同时保存旧上涨。它能降低002385式尚未修复的反弹分数，却不自动区分早反转与末端再加速；七例600056仍高分，完整候选更漏big root。不能据此加旧高阈值、延长/缩短21或叠过滤器抢救这一轮结果。

## 校验与限制

- 完整源缓存与2022-03-31、2024-09-24、2026-01-15截断重算Q逐值一致：1631股×3=4893项。
- 新向量实现复现原七例Q；原facts/CP缓存3262文件读前后SHA一致，若manifest有预期hash亦一致。
- 原基线27990条顺序、CP1身份逐项与既有ORIGINAL_PVR一致；原root定义和原capture逐项一致。
- 1568个账户日期队列把所有未来标签物理改成毒值后，Q全队列顺序不变；所有UNKNOWN或原PVR缺失槽位保持原位。
- 先封存选中清单再读取未来评价标签；同日同K始终相同。原指标重算0、账户运行0、参数扫描0，主排名实验1次。后续只从封存结果完成审计，不试第二套参数。
- 2022–26均为已消费研发历史。原静态1709及行业非PIT、空仓/ACT/资金资格沿旧账户条件状态不变。新排序若真正运行账户会改变后续持仓与资格，此检验不能预言该路径。
- 2026的60观察大行情成熟比例很低；UNKNOWN不当失败，不据尾部评价完整年度。

## 交付索引

- FREEZE.json：唯一公式、时钟、排序、同K与评价定义。
- CANDIDATE_Q.parquet：全103766候选和Q/暖历史/UNKNOWN。
- SEALED_SELECTIONS_BEFORE_LABELS.parquet、RANK_SEAL.json：标签前封存入选。
- SELECTED_WITH_FIXED_LABELS.parquet：两队列全部入选及原标签。
- FULL_QUEUE_ORDERS.parquet、REPLACEMENTS.csv：完整队列及所有移入/移出。
- MATCHED_COMPLETE_DATE_RESULTS.csv、PAIRED_DATE_DETAILS.csv：主同日成熟配对。
- ANNUAL_OUTCOMES.csv、QUARTER_PAIRED_RESULTS.csv：完整逐年/季度路径。
- ROOT_EPISODES.csv、BIG_ROOT_LOST_ADDED.csv、EXPLICIT_EPOCH_BIG_ROOT_COVERAGE.csv：根明细、全漏选/新增及明确epoch敏感性。
- FIXED_CASE_QUEUE_EFFECTS.csv：七例真实同日作用。
- SUMMARY.json、PREFIX_TESTS.csv、CACHE_SOURCE_AUDIT.csv、audit_outputs.py：检查与可复现审计。

不建议将这一个Q直接接替PVR作为主排序。本轮保留它作为明确可计算、可审计的信号质量诊断；是否存在更合适的独立信息，需另立机制与预先冻结的新实验，不能把本轮混合结果包装成已提高胜率。
'''
(O/'REPORT.md').write_text(text,encoding='utf-8')
# Append follow-through to the earlier case report without rewriting its evidence.
p=O.parent/'REPORT.md';old=p.read_text();marker='\n## 后续完整母体检验已完成\n'
if marker in old:old=old.split(marker)[0]
old+=marker+'\n沿同一冻结公式完成103766条原合法候选的同日同K检验，详见[candidate_test/REPORT.md](candidate_test/REPORT.md)。收益没有跨年一致改善，双账户各年收盘MAE更差、原大行情根净捕获各年下降；七例真实队列成员均不变。不能从七例直接否定Q，最终判断以该完整条件母体检验及其限制为准。\n'
p.write_text(old,encoding='utf-8')
print('REPORT written',len(text),'characters; explicit epoch sensitivity:');print(known.to_string(index=False))
