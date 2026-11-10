"""Format saved G1 original-fill statistics and seal; no strategy/account calls."""
from pathlib import Path
from decimal import Decimal as D
import hashlib,json
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=read('SUMMARY.json');clock=read('ACTUAL_FILL_PREVIOUS_CLOSE_CLOCK_AUDIT.json');carry=read('CARRY_SUMMARY.json');native=read('NATIVE_COLD_SUPPLEMENT.json')
groups={}
for r in s:groups.setdefault(r['cohort'],{})[r['grade_group']]=r
f=lambda x:f'{D(str(x)):,.2f}'
labels={'ALL_MOBILE':'全部MOBILE','LT2_READY':'G1<2 未达暖','NEGATIVE':'G1<0 负grade','ZERO':'G1=0','ONE':'G1=1','WARM_GE2':'G1>=2 暖'}
lines=['# 原MOBILE实际成交前G1：频率与原贡献','',
'只读既有No60两份原模拟账、原A市场daily日历、逐层表与SHA核同facts。0新账户、模型、回测、过滤策略收益或参数修改。A为2022-01-04—2024-12-31实际MOBILE新fill，终点2024-12-31；B为原strong连续账户2026-01-01—06-30实际新fill，终点2026-06-30。B没有在2026年重新起账；2025年带入MOBILE另表。','',
'## 时钟核验','',
'G1严格取实际fill之前最近一个原A市场CLOSE；不是fill日CLOSE，也不是intent再向前shift一bar。原book metadata预算订单decision、actual buytrade、原ROWS opened/decision均匹配：A1767/1767，B390/390，0不符。995个股票facts文件逐个核SHA；所有2157条直接facts的grade/ready与原ROWS一致，前一CLOSE都有exact观察且ready=True；NaN/unready/缺exact观察均0。原逐条source_day和索引在两份*_MOBILE_ROWS.csv/json，完整计数见ACTUAL_FILL_PREVIOUS_CLOSE_CLOCK_AUDIT.json。','',
'<2称“未达暖”，<0称“负grade”；两者都不能直接叫原生cold。policies_g1.py:18–19原公式为warm=ready且grade>=2；cold=ready且(grade<=−2或acute_down)。独立补件保原acute_down字段及cold公式：A native cold79层，另有3层grade=−1并非native cold；B2026 native cold12层。此补件不改主分组，也没有生成新G1状态。','',
'## 两个终点分别统计','',
'金额为元。投入是各实际buy gross+买费累计，不是峰值占资；real为原strict realized，unreal为终点未实现，AR为原应收分红、不是到账现金。net=real+unreal+AR；费用已经包含在原贡献中，不再扣一次。<2是负grade/0/1的汇总，与子组重叠，不能重复加总。','']
for cohort,title in [('A_2022_2024_NEW_FILLS','A：2022—24长账，2024-12-31终点'),('B_2026H1_NEW_FILLS','B：2026上半年新fill，2026-06-30终点')]:
 gg=groups[cohort];ratio=D(gg['LT2_READY']['layers'])/D(gg['ALL_MOBILE']['layers'])*100
 lines+=['### '+title,'',f'未达暖成交占比{ratio:.4f}%。','',
 '|成交前G1组|层数|累计投入gross+buyfee|real|unreal|AR|原net|已平/未平|原买卖费合计|',
 '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for key in ['ALL_MOBILE','LT2_READY','NEGATIVE','ZERO','ONE','WARM_GE2']:
  r=gg[key];lines.append(f'|{labels[key]}|{r["layers"]}|{f(r["actual_input_gross_plus_buy_fee"])}|{f(r["original_strict_realized"])}|{f(r["original_open_unrealized"])}|{f(r["original_dividend_AR"])}|{f(r["original_endpoint_net_contribution"])}|{r["fully_closed_layers"]}/{r["open_layers"]}|{f(r["total_actual_fees_by_endpoint"])}|')
 lines+=['','暖组拆分（同一终点）：','',
 '|grade|层数|原投入|原net|已平/未平|','|---|---:|---:|---:|---:|']
 for grade in [2,3,4]:
  r=gg['WARM_'+str(grade)];lines.append(f'|{grade}|{r["layers"]}|{f(r["actual_input_gross_plus_buy_fee"])}|{f(r["original_endpoint_net_contribution"])}|{r["fully_closed_layers"]}/{r["open_layers"]}|')
 lines+=['']
lines+=['A全部MOBILE已平，但原应收分红仍单列；“已平”不等于全部贡献已变成现金。A负grade组原贡献为+5108.00159457，不能仅因grade负就把这些层称为亏单。B暖组758749.44485835原net中，748266.88828858为期末unreal；原real只有6579.51336977，47层仍未平。不能把不同终点或未实现贡献混成已实现收益。','',
'## 跨年与2025带入仓','',
'A跨持仓年度的MOBILE共40层：未达暖12层（负9、grade1三），暖28层；原signal→fill跨年0。B的2026新fill无跨持仓年层，另有1条暖组原intent在2025而实际fill在2026；仍按实际fill归入B。CROSS_YEAR_LAYERS_AND_SIGNAL_FILL.json逐层列出这两种跨年定义，不按年度重置或分摊生命周期收益。','',
'原2025-12-31带入MOBILE为49层，全部在2025买入，不混入2026新390层。','',
f'- 2025买入至2026-06-30全生命周期累计投入{f(carry["lifetime_through_Jun30"]["actual_input_gross_plus_buy_fee"])}；real {f(carry["lifetime_through_Jun30"]["original_strict_realized"])}、unreal {f(carry["lifetime_through_Jun30"]["original_open_unrealized"])}、AR {f(carry["lifetime_through_Jun30"]["original_dividend_AR"])}，life net {f(carry["lifetime_through_Jun30"]["original_endpoint_net_contribution"])}，48平/1未平。',
f'- 独立的2026期内原财富差为{f(carry["original_2026H1_carry_wealth_change_sum_known_only"])}：逐层从原Dec31 cash+旧mark+AR财富到Jun30 cash+残值+AR财富作差。49层都有exact Dec31原raw观察，没有用生命周期net冒充该日历期收益。它只是该49层原财富金额差，不是账户收益率。',
'',
'B_2025_CARRY_MOBILE_ROWS.csv/json同时保留cutoff原层、旧q/mark/source_day/AR、life net与original_2026H1_wealth_change_from_carry。其G1是原2025实际买入前一CLOSE，不是2026新买分组，也不是2026持有期间每天grade。','',
'## 来源与限制','',
'SUMMMARY分组仅汇总原层投入与原终点贡献，不能将剔除某组原贡献当作策略改善或新收益：退出/新买/现金重用/排序与后续路径都未重算。原fill及fee为日线执行代理的模拟账，不是broker实成交。','',
'实际买费逐值对上原buytrade；卖费按原whole receipt parts净现金分摊，不重复每层最低佣金；逐层核对real+unreal+AR=net，以及native cash+原终点mark+AR=net、剩余basis关系。SOURCE_MANIFEST.json记录全部书、日历、ROWS、逐层财富和995个facts的SHA。grade_ready未知类单独留在SUMMARY.json/csv，本样本均为0；时钟/缺观察异常将显式记录，未填补。','',
'主文件：SUMMARY.csv/json；A_2022_2024_MOBILE_ROWS.csv/json；B_2026H1_NEW_MOBILE_ROWS.csv/json；B_2025_CARRY_MOBILE_ROWS.csv/json；ACTUAL_FILL_PREVIOUS_CLOSE_CLOCK_AUDIT.json；NATIVE_COLD_SUPPLEMENT.json；CROSS_YEAR_LAYERS_AND_SIGNAL_FILL.json；CARRY_SUMMARY.json；VALIDATION.json。本件自校验不冒充另一作者的独立审核。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
# A terminal zero position is called fully closed only when source closed_at exists.
for name in ['A_2022_2024_MOBILE_ROWS.json','B_2026H1_NEW_MOBILE_ROWS.json','B_2025_CARRY_MOBILE_ROWS.json']:
 rr=read(name);assert all(not r['closed_by_endpoint'] or r['closed_at'] is not None for r in rr)
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_STATIC_ORIGINAL_MOBILE_G1_FILL_STATISTICS',readout_sha256=sha(O/'READOUT.md'),summary_sha256=sha(O/'SUMMARY.json'),clock_audit_sha256=sha(O/'ACTUAL_FILL_PREVIOUS_CLOSE_CLOCK_AUDIT.json'),native_cold_supplement_sha256=sha(O/'NATIVE_COLD_SUPPLEMENT.json'),source_manifest_sha256=sha(O/'SOURCE_MANIFEST.json'),deliverable_sha256=sha(O/'DELIVERABLE_SHA256.json'),new_accounts=0,new_models=0,new_backtests=0,new_strategy_returns=0)
save('SEAL_RECEIPT.json',seal);print(json.dumps(seal,ensure_ascii=False))
