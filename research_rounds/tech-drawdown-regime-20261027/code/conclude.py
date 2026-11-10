from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parents[1]
s=pd.read_csv(O/'results-final/scoreboard.csv');p=pd.read_csv(O/'results-final/periods.csv');c=pd.read_csv(O/'results-final/curves.csv');a=pd.read_csv(O/'results-final/h2-attribution.csv')
cols=['version','net_return','max_drawdown','pre_profit_retention','h2_return','h2_exposure','empty_days']
def table(df):
 rows=['|方案|累计收益|全程回撤|前期盈利保留|H2收益|H2平均仓位|H2空仓日|','|---|---:|---:|---:|---:|---:|---:|']
 for r in df.itertuples():rows.append('|'+r.version+'|'+ '|'.join(f'{getattr(r,k):.2%}' for k in cols[1:-1])+f'|{r.empty_days}/78|')
 return '\n'.join(rows)
body='''# 科技2024—当前账户：第一至四线研究结论

**阶段研究已完成42路径，但总目标尚未完全实现。** 已找到在本次2026H2实质降低仓位和损失的SHADOW20取舍，不能据此宣称已得到全程风险可控、稳定保留前期收益的策略。活动目标继续，原I-NR1不替换。

## 主要判断

优先检验交易策略的组合风险层，不能继续把问题全部归结为个股趋势算法反应慢。原I知道G1转冷但按E0结构持有；同时在弱环境中用新局部强势补满空位。真正的风险层既要约束存量，也要控制新增与恢复，且参考实际账户自身风险。

7/2原I仓位90.63%，低于暖持仓占NAV84.66%；7/6全部79.31%仓位低于暖，7/7又升至89.83%。源杰6/30距E0支持44.96%、7/2G1冷、7/21才实际卖出。最高单股49.04%、行业57.35%，初仓15%不是持续市值上限。见DIAGNOSIS.md、逐日图及原始OHLC。

## 结果口径

407科技股/11行业，2024初100万元纯现金起至最新核验2026-10-26；每条是同一资金池的替代模拟，不合计为4200万元。当前存续/行业/市值快照，开发历史而非历史时点全池或样本外。原入场I/结构/排名/槽位/费用/整手/T+1/开盘执行保持，新增规则全部事前文件记录。未下载新行情或分钟资料。

前期盈利保留=(该组2026-06-30NAV−100万)/(同执行情景原I该日NAV−100万)，不是财富保留比例。2026H2是7/1至10/26相对6/30的收益，不能混成全程最大回撤。

## 全部基础路径

'''+table(s[s.scenario=='base'])+'''

## 机制尝试与裁决

1. 第一批七组：个股m21快退出、行业广度、市场只停新买/全退出、慢背景、纯价格消融及原I。快退出H2−48.72%；只停新买仍−37.07%；统一市场退出H2−15.46%但仅保留5.50%前期利润。否定一刀切快退出/市场开关即可完成目标。
2. 第二批四组：市场和个股共同弱才退，分离新买门槛，另以已有G1代替新m21。JOINT_SLOW保留63.81%前期盈利，但H2仍−39.40%；其余亦未解。没有因个股看起来强就保留持仓后自动得到风险控制。
3. 第三线影子回撤：持续纸面运行固定原I基础账户，SHADOW20于影子回撤20%关闭、回到10%恢复；SHADOW10为10%/5%。停止后真实账户次开盘退出、阻止新买，恢复仍需原I有效买事件，不复制影子持仓。
4. 第四线集中损失：影子5交易观察跌10%暂停，收复触发前5观察净值才恢复。SHOCK10仅保留21.59%前期利润，H2−10.30%，没有解决收益保留；不再围绕它搜索阈值。

## 最有价值但未晋升的候选：SHADOW20

基础：6月底NAV306.85万元（原397.00万），保留69.65%的累计盈利；7/13收盘触发，7/14六股实际全部卖出，随后至期末没有新买。H2平均仓位10.87%、69/78日空仓，H2−19.61%，期末246.68万元、累计146.68%（原239.14万元、139.14%）。它减少了本次下跌后段损失，代价是少赚了一部分上涨利润。

闭合尾部贡献196.28万元、普通净损耗49.60万元、未结0，净146.68万；原I为282.16万、−155.09万、未结+12.07万。不是保住了每只原赢家：源杰实际贡献由112.66万降至44.48万，另有宏景、利通等贡献改变。少亏普通交易比减少尾部贡献更多，才形成最终小幅改善，不能只拿卖出源杰早晚解释。

'''
for sc in ['cost2','delay1']:
 body+='\n### '+sc+'\n\n'+table(s[(s.scenario==sc)&s.version.isin(['CONTROL','SHADOW10','SHADOW20','SHOCK10'])])+'\n'
body+='''
## 为什么还不能宣布目标完成

SHADOW20全程最大回撤43.92%：实际账户从2024-03-18的106.58万元降到2025-07-30的59.78万元。它在此前的入场/退出后已与原I影子分叉，所以影子20%阈值并不是实际账户20%风控。双成本全程回撤44.39%、延迟44.88%，仍不理想；前期收益也未完整保留。10%版本更早空仓，却牺牲过多上涨参与。

下一有限问题已经由证据明确：风险预算需以实际账户衡量，恢复则必须使用独立可观察的市场/策略事实，避免用已空仓且净值静止的实际账户等自身恢复的死锁。不能直接把SHADOW20扩大成实盘方案，也不能改成事后识别7月的日期规则。下一步先诊断影子与实际持仓/回撤分叉及恢复损耗，再冻真实账户风险—恢复对照；未自动启动新的经济批次。

## 核验和可复现性

- 三次407股全历史物理截断，市场状态与完整序列一致；影子回撤6门槛前缀、集中损失3前缀及固定恢复锚合成核验通过。
- 42路径均先短期三情景独立核账，再完整经济，每版完整仅一次。42个2025末真实执行截断、3旧I完整控制精确一致，核验收据account-validation-final.json共45项。
- 冻结文件全部哈希一致。各账户股数/现金/权息/费用由独立账本重放，净值最大差0。完整数字见RESULTS_RECEIPT.json。
- 所有失败方案、技术失败、第一次图字体/后端问题及修复版保留。无经济重跑，无事后改变已运行模型规则。四线14方案并非14个独立样本外试验。
- 日线开盘代理不保证分钟实际成交；当前快照偏差/已见历史不被前缀测试消除。10%/20%风险阈值是研究约定，不是收益或止损保证。
'''
(O/'CONCLUSION.md').write_text(body)
receipts=[]
for root in O.iterdir():
 f=root/'analysis/accounting.json'
 if f.exists():receipts.append(json.loads(f.read_text()))
R={'status':'phase_complete_goal_active','paths':len(s),'daily_rows':sum(r['daily_rows'] for r in receipts),'fills':sum(x['checks']['fills_causal_and_fee_components'] for r in receipts for x in r['receipts']),'max_nav_difference':'0','economic_replays':14,'economic_reruns':0,'post_result_changes_to_frozen_versions':0,'verification':'account-validation-final.json','limitations':['full objective not yet achieved','actual-vs-shadow risk divergence','current survivor snapshot','daily execution proxy','seen development history']}
(O/'RESULTS_RECEIPT.json').write_text(json.dumps(R,ensure_ascii=False,indent=2));print(R)
