from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent;rows=json.loads((O/'BASELINE_SUMMARY.json').read_text());rank=json.loads((O/'CLOSED_POSITIVE_RANKING.json').read_text())
labels={'FULL_OBSERVED_WINDOW':'全窗','SEPT_STARTUP_SEED_OPEN_0923_0930':'9月启动','PV_SEED_OPEN_1023_1029':'10月光伏','NEW_SEED_OPEN_FROM_1107':'11/7起新轮'}
f=lambda x:f'{D(x):,.2f}'
t='''# 抓主线肥尾：下一候选的已观测开发窗对照基线

本基线只读取冻结M7/v6，不改旧文件、不执行history、不联网。认证截止2025-01-20。下一候选尚未运行；此刻封存的是**已观测开发窗**的评估口径，不是样本外证明，也不把盈利分位当入场信息。

## 四组固定范围

- 全窗：全部1677个实际开仓轮，2024-09-02至认证截止。
- 9月启动：首笔实际SEED OPEN在2024-09-23至09-30，含端点，所有板块，共222轮。
- 10月光伏：光伏风电设备板块，首笔实际SEED OPEN在2024-10-23至10-29，含端点，共34轮。
- 11/7起新轮：首笔实际SEED OPEN≥2024-11-07，共954轮，与既有11/6旧仓/新轮归因一致。“严格11/7之后”则885轮，已另存DATE_SCOPE_NOTE，不能混作954轮。

四组有包含和重叠关系，不能把各组贡献相加。整轮盈亏可能在出生窗口之后实现，这不是相应月内账户收益。

## 已闭合轮肥尾贡献

“前10%正轮”明确为：已闭合且净盈利的轮数×10%，向上取整，按实际实现净利润排序。比例分母为所有盈利闭合轮的正利润总和。最大5/10轮同样使用实际净利润，不使用MFE或事后最高价。

| 组 | 闭合轮数 | 盈利/亏损轮数 | 闭合净损益 | 前10%正轮数 | 其贡献 | 占全部正利润 | 最大5轮贡献 | 最大10轮贡献 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
'''
for r in rows:t+='| '+labels[r['cohort']]+' | '+str(r['closed_rounds'])+' | '+str(r['positive_closed_rounds'])+'/'+str(r['negative_closed_rounds'])+' | '+f(r['closed_net'])+' | '+str(r['top10pct_positive_count'])+' | '+f(r['top10pct_positive_contribution'])+' | '+f(r['top10pct_share_positive_pct'])+'% | '+f(r['top5_positive_contribution'])+' | '+f(r['top10_positive_contribution'])+' |\n'
t+='''
全窗前62个盈利轮贡献32.64万元，显著高于全窗闭合净利润6.93万元，说明肥尾要覆盖大量亏损轮。9月启动的优势不只是某一只股票，188个盈利轮产生27.04万元正利润、34个亏损轮成本3.59万元；光伏虽然22亏/12赢，仍净赚2.87万元。相反，11/7起新轮235个赢家只有8.25万元正利润，589个亏损轮成本27.23万元，肥尾规模不足以覆盖成本。

## 盈利轮分布与亏损费用

盈利分位仅限已闭合净盈利轮，线性插值位置为(n−1)×p。手续费已经包含在实际净损益，不能再扣。

| 组 | 盈利P50 | 盈利P90 | 盈利P95 | 亏损轮总成本 | 其中手续费 | 手续费占比 | 模型滑点 | 费用+滑点占比 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
'''
for r in rows:t+='| '+labels[r['cohort']]+' | '+f(r['positive_closed_p50'])+' | '+f(r['positive_closed_p90'])+' | '+f(r['positive_closed_p95'])+' | '+f(r['gross_negative_cost'])+' | '+f(r['negative_closed_fees'])+' | '+f(r['negative_closed_fee_share_loss_pct'])+'% | '+f(r['negative_closed_model_slippage'])+' | '+f(r['negative_closed_fee_plus_slippage_share_loss_pct'])+'% |\n'
t+='''
各组亏损轮的手续费只占约1.92%–3.63%，加上固定5bp模型滑点也仅约3.41%–5.77%。主要损失仍来自价格路径，不能把“减少订单数”自动等同充分改善。全窗仅50个亏损轮在加回费用与模型滑点后原始价格/股息为非负，它们合计只亏707.42；新轮该类31轮合计只亏414.55。

## 开放轮必须单列

全窗和11/7起新轮都包含同一批130个截止开放轮：marked净利润+6,066.56，扣模拟立即卖出成本的净清算利润+4,195.22。9月启动和10月光伏开放轮为0。

开放轮不进入上述闭合赢家排名、盈利分位和亏损费用分布。OPEN_AT_CUTOFF保存每个机会、股数、首笔时间、marked与清算净利。很多在1/17–20刚买，不认定其最终成功或失败。

全账户现金闭合核对：1,200,000初始资金+69,259.49已闭合净利润+6,066.56开放marked净利润=1,275,326.04实际账面NAV；净清算NAV1,273,454.71。

## 固定身份，不允许延迟成交后换组逃离比较

下一候选应按以下口径提交，不能事后更换：

1. **机会键固定为sid＋原始signal_date。** 当前1677个实际机会键全部唯一。round序号不可作跨策略主键，因为候选跳过一次会让以后轮序号改变；原signal_date也不能被实际成交日替换。birth_type与原始票据来源作为审计辅助字段。
2. **冻结这四组的M7成员与原赢家名单。** 候选把9月信号推迟到10月才成交，仍归入原9月机会组作配对，不能因为候选seed日期移走就从原赢家比较里消失。对原光伏和11/7起组同理。候选自己的实际成交日分组可以另列，但不得取代冻结机会组。
3. 每个基线机会报告：双方original_signal_date、首笔OPEN、等待间隔、首笔股数/资金、后续ADD与供资卖出、是否未参与、是否改以后来新机会重入、相同截止日marked净收益及净清算收益。基线未匹配应显式列为“该原机会未成交”，不能静默删去。之后新signal是真正不同机会，单列而不是冒充原机会延迟。
4. 如候选一机会分多段执行，按原票据身份汇总现金流、费用、股息与剩余库存，避免靠拆分轮次改变盈利分位或尾部排名。原机会没有成交的贡献为零；若已开但截止未闭合，其marked与清算两列保留，状态不可伪装成完整实现利润。
5. **主对照必须是同一认证边界的实际cash NAV、完整现金/权益闭合及收盘峰谷回撤。** 冻结初始资金、价格、费用、滑点、股票池、分类、容量、T+1和未知原子停止。某个过滤组在M7亏多少钱不是候选可直接追回多少钱，资金供给和后续订单会变。
6. 肥尾对照同时给两组视角：①冻结M7前10%正轮与Top5/Top10机会，在候选中的总贡献、未参与数与份额；②候选自己完整闭合赢家的正利润、Top10%/Top5/Top10及P50/90/95。前者防止漏掉原行情后隐藏，后者允许候选捕获新赢家。两者结合整体NAV和亏损代价，不要求每一个原赢家都不能漏。
7. 普通行情代价用相同全窗闭合损失、费用、INITIAL/EVENT与EXPANSION/MATURE、旧仓/新仓及开放轮分别报告。不能仅因利润分位更高、订单更少或回撤更低就宣布抓肥尾更好。

本次不设置通过阈值，不设计新的入场门槛，不把事后盈利分位用于信号。原参数和这段开发窗已经看过；任何后续对照必须明确研究性与样本选择限制。

## 固定Top5机会

| 组 | 股票 | 原signal_date | 实际首笔OPEN | 已实现净利润 |
| --- | --- | --- | --- | --- |
'''
for r in rank:
 if r['positive_rank']<=5:t+='| '+labels[r['cohort']]+' | '+r['name']+' '+r['sid']+' | '+r['original_signal_date']+' | '+r['actual_seed_OPEN']+' | '+f(r['marked_net_pnl'])+' |\n'
t+='''
## 文件

- BASELINE_SUMMARY.json/csv：四组汇总及完整费用拆分。
- CLOSED_POSITIVE_RANKING.json/csv：所有闭合正轮排序，固定前10%标记与机会身份。
- COHORT_OPPORTUNITY_MEMBERSHIP.json/csv：冻结四组机会成员，未来延迟成交仍按此配对。
- ALL_OPPORTUNITIES.json/csv：1677机会完整基线，含手续费、滑点、实际现金贡献。
- OPEN_AT_CUTOFF.json/csv：开放轮单列；两重叠组重复行不能求和。
- BASELINE_DEFINITIONS.json、DATE_SCOPE_NOTE.json、SOURCE_HASHES.json、OUTPUT_SEAL.json：口径、来源与封存校验。
'''
(O/'READOUT.md').write_text(t)
(O/'OUTPUT_SEAL.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_SEAL.json'},ensure_ascii=False,indent=2))
print(O/'READOUT.md')
