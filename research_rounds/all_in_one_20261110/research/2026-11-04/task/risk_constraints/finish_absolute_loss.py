"""Readable scale summary of already saved absolute-loss arithmetic; no replay."""
from pathlib import Path
from decimal import Decimal as D
import json, hashlib

HERE=Path(__file__).resolve().parent
OUT=HERE/'absolute_loss_2022_2023'
def read(p):return json.loads(p.read_text())
def n(x):return D(str(x))
def fmt(x):return f'{n(x):,.2f}'
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    periods=read(OUT/'PERIODS.json');sectors=read(OUT/'SECTORS.json');summary=read(OUT/'SUMMARY.json')
    meta=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
    sm=read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))
    universe={meta[x['symbol']]['sector_id']:meta[x['symbol']]['industry'] for x in sm}
    breadth={};buckets=[('NO60_2022_2023','year','2022'),('NO60_2022_2023','year','2023'),('NO60_2022_2023','all','all'),('NO60_STRONG','all','all')]
    for ref,grain,period in buckets:
        rr=[r for r in sectors if (r['reference'],r['grain'],r['period'])==(ref,grain,period)]
        negative=sorted([r for r in rr if n(r['wealth_change'])<0],key=lambda r:n(r['wealth_change']))
        positive=sorted([r for r in rr if n(r['wealth_change'])>0],key=lambda r:-n(r['wealth_change']))
        g={r['sector'] for r in rr}
        breadth[ref+'_'+period]=dict(funded_sector_mother_set=len(g),universe_sectors=len(universe),negative_sector_count=len(negative),positive_sector_count=len(positive),zero_sector_count=len(rr)-len(negative)-len(positive),
            negative_sector_net_sum=sum((n(r['wealth_change']) for r in negative),D(0)),positive_sector_net_sum=sum((n(r['wealth_change']) for r in positive),D(0)),
            never_funded_in_whole_source_book=[dict(sector=s,industry=universe[s],contribution=0) for s in sorted(universe.keys()-g)],
            largest_negative_sectors=negative[:10],largest_positive_sectors=positive[:10],
            largest5_negative_share_of_negative_sector_net= -sum((n(r['wealth_change']) for r in negative[:5]),D(0)) / -sum((n(r['wealth_change']) for r in negative),D(0)))
    save(OUT/'LOSS_BREADTH_AND_CAPITAL.json',breadth)
    ys=[r for r in periods if r['reference']=='NO60_2022_2023' and r['grain']=='year']
    qs=[r for r in periods if r['reference']=='NO60_2022_2023' and r['grain']=='quarter']
    months=sorted([r for r in periods if r['reference']=='NO60_2022_2023' and r['grain']=='month'],key=lambda r:n(r['wealth_change']))
    ds=read(OUT/'NO60_2022_2023_DAILY.json');act=[]
    for y in ['2022','2023']:
        for on in [True,False]:
            rr=[r for r in ds if r['day'].startswith(y) and r['ACT_at_OPEN']==on]
            act.append(dict(year=y,ACT_at_OPEN=on,closes=len(rr),wealth_change=sum((n(r['wealth_change']) for r in rr),D(0)),actual_buy_cash=sum((n(r['actual_buy_cash']) for r in rr),D(0)),actual_fees=sum((n(r['actual_fees']) for r in rr),D(0))))
    save(OUT/'ACT_YEAR_CLOCK_GROUPS.json',act)
    text='''# 2022→2023 绝对亏损规模与资金归因

No60 两年从 100 万降至 745,426.96 元，仍亏 254,573.04 元（25.46%）。较旧 PVR 多 82,869.05 元是相对改善，不能视为可接受结果，35% 只是用户可接受回撤边界。2022 损失广泛分布，2023 的赢家恢复未覆盖之前亏损；减少实际投入本身也不是策略修复的证明。

主分析仅读取已有完整账、原冻结价格和财务收据，没有账户运行。下表全部是区间增量，保留跨年原持仓成本，不将某年买入层的终生损耗误当该年损失。货币单位为元。

| 区间 | 财富变化 | 严格已实现交易损益 | 未实现变化 | 新计未收股息 |
|---|---:|---:|---:|---:|
'''
    for r in ys:text+='| '+r['period']+' | '+' | '.join(fmt(r[k]) for k in ['wealth_change','realized_trade_net','unrealized_change','recognized_dividend'])+' |\n'
    a=summary['NO60_2022_2023'];text+='| 累计 | '+' | '.join(fmt(a[k]) for k in ['wealth_change','realized_trade_net','unrealized_change','recognized_dividend'])+' |\n'
    text+='''
2022 另一条桥为：净成交对价 −929,449.11 + 期末库存 631,570.40 + 新计股息应收 2,366.56 = −295,512.15。2023 为净成交对价 +668,113.23 − 期初库存 631,570.40 + 新计股息应收 4,396.28 = +40,939.11。成交确认的卖款包含待结算应收，不等于可支用现金；本批所有股息均未支付，始终单列 AR。

| 区间 | 含费累计买款（可循环使用资金） | 平均仍持仓含费成本 | 平均市值暴露 | 平均记录名义风险 / NAV | 实际买卖费 |
|---|---:|---:|---:|---:|---:|
'''
    for r in ys:text+='| '+r['period']+' | '+' | '.join(fmt(r[k]) for k in ['actual_buy_cash','mean_held_cost_basis','mean_exposure_pct','mean_nominal_risk_pct','actual_fees'])+' |\n'
    text+='''
累计含费买款 15,427,691.65 元是循环使用的交易资本，不能当作 1542 万独立本金。累计买卖费 32,037.08 元；加回这些明确费用后仍损失 222,535.96 元，故费用不是全部绝对亏损来源。成交价已保留原执行近似，未额外虚构滑点或成本减项。`net / cumulative_buycash` 只用于同单位的描述，带期初库存的年度/行业更不能把该比率当投资回报或 alpha；未做暴露线性缩放。

| 季度 | 财富变化 | 含费实际买款 |
|---|---:|---:|
'''
    for r in qs:text+=f"| {r['period']} | {fmt(r['wealth_change'])} | {fmt(r['actual_buy_cash'])} |\n"
    text+='''
2022Q1 和 Q3 合计亏 246,157.36 元；季度净值会掩盖内部反复。最亏月份分别为 2022-12 −94,806.65、2022-01 −91,320.74、2022-04 −79,204.91、2022-03 −76,280.51、2023-05 −75,256.49、2022-08 −67,795.27 元。2023Q1/Q2 合计恢复 96,393.03 元，Q3 又损失 55,453.92 元，Q4 没有新增交易或持仓贡献，不能把年末停止波动误作持续捕获行情。

行业归因覆盖全量实际参与股，不只挑两只坏股。当前冻结 1709 股共 90 行业；No60 两年实际曾参与 89 行业，未参与“综合”隐含零。某年统计仍以该两年曾参与母体为分母，零贡献可以包括当年未参与的行业。行业净额先在行业内部抵扣赢家和输家，不能与逐股/逐层毛损额混称。

| 范围 | 负净额行业 / 正净额行业 | 负行业净额合计 | 正行业净额合计 | 财富变化 |
|---|---:|---:|---:|---:|
'''
    for ref,grain,p in buckets:
        z=breadth[ref+'_'+p];text+=f"| {ref} {p} | {z['negative_sector_count']} / {z['positive_sector_count']} | {fmt(z['negative_sector_net_sum'])} | {fmt(z['positive_sector_net_sum'])} | {fmt(z['negative_sector_net_sum']+z['positive_sector_net_sum'])} |\n"
    text+='''
| 两年累计最亏行业 | 区间净贡献 | 实际含费买款 | 平均市值暴露（%） |
|---|---:|---:|---:|
'''
    for r in breadth['NO60_2022_2023_all']['largest_negative_sectors']:text+=f"| {r['industry']} | {fmt(r['wealth_change'])} | {fmt(r['actual_buy_cash'])} | {fmt(r['mean_exposure_pct'])} |\n"
    text+='''
2023 恢复最大的行业是计算机设备 +73,396.02、影视院线 +38,145.76、通信设备 +21,406.56 元；与此同时港口航运 −12,161.60、半导体 −9,925.88、化学制药 −8,561.58 元。正常强窗（2025Jul→2026Jun）虽盈利 1,263,281.23 元，46 个行业仍合计净亏 305,209.36 元，由 40 个盈利行业贡献 1,568,490.59 元覆盖。其最大赢家电子化学品 +381,114.65、光学光电子 +181,240.05、元件 +134,249.97 元；严格半导体全强窗仍 −12,631.38 元（H1 单独为 −16,783.58 元）。这是事后规模对照，不是新行业筛选信号。

ACT 时钟用前一收盘记录归属当日 OPEN，不用同日15:10的暂停决定回贴上午交易。2022 active/paused OPEN 204/38 日；2023 132/110 日（按 CLOSE 状态则暂停111日，口径不同）。两年 active OPEN 日财富变动 −246,559.69 元、实际买款 15,427,691.65 元；paused OPEN 日 −8,013.35 元、实际买款为零，仍有 139 笔存量清仓卖出。该分组只说明损失发生时段和清仓兑现时钟，不是“关闭 ACT 会改善”的反事实。

全量文件：`PERIODS.json` 包含四账共108个 all/year/quarter/month 区间；`SECTORS.json` 为9,409条全行业区间桥；`*_DAILY.json` 与 `*_SECTOR_DAILY.json` 保留日级金额和时钟；`LOSS_BREADTH_AND_CAPITAL.json` 保留正负规模、实际资本及未参与行业；`ACT_YEAR_CLOCK_GROUPS.json` / `ACT_CLOCK_GROUPS.json` 保留状态分组；`SOURCE_MANIFEST.json` 绑定1,194个输入SHA。源账所有484/242日均通过数量、原始收盘库存、预算/资本/池证书、AR、净交易对价财富桥及严格已实现/未实现桥。逐层实际拆股的碎股数量为零，未把非交易basis核销混入已实现交易损益。

逐层初试/加仓/再入、退出原因与重复试错行为由 loss_correction 独立分工输出，必须保持同一财富桥和实际买款分母。下一研究应解释广泛普通损失为何持续、恢复赢家为何不能覆盖，不因相对优于旧 PVR 或只降投入就晋升候选。此处仍限 A 股当前幸存者开发样本与原日线执行近似；120万真实规模、港股与样本外未验证。
'''
    audit_path=HERE.parent/'independent_review/PVR_ABSOLUTE_PERIOD_SECTOR_AUDIT.json'
    audit=read(audit_path)
    assert all(audit[ref]['passed'] for ref in summary)
    assert audit['reviewer_account_events']==0 and audit['source_SHA_checks']==1194
    assert sum(audit[ref]['period_rows'] for ref in summary)==len(periods)
    assert sum(audit[ref]['sector_rows'] for ref in summary)==len(sectors)
    text+='\n独立全量审查已通过：`../independent_review/PVR_ABSOLUTE_PERIOD_SECTOR_AUDIT.json` 核同全部108区间、9,409行业区间、104,753个数值格及1,194个源SHA；独立方法由原交易现金流、冻结rawmark、当前数量和按实际拆股调整的原买入成本重建，未复用本分析的卖出basis分配器。ACT时钟分组亦核同；双方均为0新账户事件。\n'
    (OUT/'READOUT.md').write_text(text)
    save(OUT/'INDEPENDENT_AUDIT_BINDING.json',dict(passed=True,account_events=0,reviewer_account_events=0,
        independent_audit_path=str(audit_path),independent_audit_sha256=sha(audit_path),
        source_SHA_checks=audit['source_SHA_checks'],independently_checked_numeric_cells=audit['independently_checked_numeric_cells'],
        bound_analysis={str(OUT/f):sha(OUT/f) for f in ['PERIODS.json','SECTORS.json','SUMMARY.json','SOURCE_MANIFEST.json','ACT_CLOCK_GROUPS.json','ACT_YEAR_CLOCK_GROUPS.json','ACT_CLOCK_VERIFICATION.json']},
        scope=audit['scope']))
    save(OUT/'READOUT_BINDING.json',dict(account_events=0,analysis_state='own finance assertions and independent absolute period/sector audit complete',
        source_inputs=1194,readout_sha256=sha(OUT/'READOUT.md'),reader_sha256=sha(HERE/'analyze_absolute_loss.py'),
        finishing_reader_sha256=sha(Path(__file__)),scopes='period attribution not entry-cohort lifecycle or counterfactual capital efficiency'))
    print('ABSOLUTE_READOUT_READY',len(breadth),'breadth summaries',len(act),'ACT year groups')

if __name__=='__main__':main()
