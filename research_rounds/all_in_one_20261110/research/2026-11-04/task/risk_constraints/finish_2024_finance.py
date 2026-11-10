"""Aggregate existing 726-day saved finance into descriptive 9/24 phases."""
from pathlib import Path
from decimal import Decimal as D
import json,importlib.util,hashlib
HERE=Path(__file__).resolve().parent;OUT=HERE/'continuation2024_finance'
sp=importlib.util.spec_from_file_location('saved_finance_phase_only',HERE/'analyze_absolute_loss.py');F=importlib.util.module_from_spec(sp);sp.loader.exec_module(F)
def read(p):return json.loads(p.read_text())
def n(x):return D(str(x))
def fmt(x):return f'{n(x):,.2f}'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    dd=read(HERE/'continuation2024_drawdown/DRAWDOWN_COMPARISON.json');summ=read(OUT/'SUMMARY.json');phases=[];sectors=[]
    spans=[('pre_924','2024-01-01','2024-09-23'),('924_to_Oct8','2024-09-24','2024-10-08'),('post_Oct8','2024-10-09','2024-12-31')]
    for ref in ['PVR_SLOT1','PVR_NO_CONFIRMED60']:
        ds=read(OUT/(ref+'_DAILY.json'));ss=read(OUT/(ref+'_SECTOR_DAILY.json'))
        for label,lo,hi in spans:
            rr=[r for r in ds if lo<=r['day']<=hi];rr=[{k:n(v) if k in F.SUMKEYS or k in ['NAV_begin','NAV_end','inventory_begin','inventory_end','held_cost_basis','market_value','exposure_pct','nominal_risk','nominal_risk_pct','available_cash'] else v for k,v in r.items()} for r in rr]
            rec=F.period_summary(rr);rec.update(reference=ref,phase=label,lo=lo,hi=hi,
                mean_available_cash=sum((r['available_cash'] for r in rr),D(0))/len(rr),min_available_cash=min(r['available_cash'] for r in rr),
                ACT_events=[e for e in summ[ref]['ACT_events'] if lo<=e['at'][:10]<=hi]);phases.append(rec)
            for s in sorted({r['sector'] for r in ss}):
                zz=[r for r in ss if r['sector']==s and lo<=r['day']<=hi]
                z={k:sum((n(r[k]) for r in zz),D(0)) for k in F.SUMKEYS};z.update(reference=ref,phase=label,sector=s,industry=zz[0]['industry'],inventory_begin=n(zz[0]['inventory_begin']),inventory_end=n(zz[-1]['inventory_end']),
                    mean_held_cost_basis=sum((n(r['held_cost_basis']) for r in zz),D(0))/len(zz),mean_exposure_pct=sum((n(r['exposure_pct']) for r in zz),D(0))/len(zz));sectors.append(z)
            F.close(sum((z['wealth_change'] for z in sectors if z['reference']==ref and z['phase']==label),D(0)),rec['wealth_change'],(ref,label,'phase-sector bridge'))
        F.close(sum((r['wealth_change'] for r in phases if r['reference']==ref),D(0)),n(summ[ref]['year2024']['wealth_change']),(ref,'phases cover year'))
    F.save(OUT/'PHASES_924.json',dict(phases=phases,account_events=0,
        clock='Descriptions only: pre uses own2023Dec29 beginning; Sep24 starts from Sep23CLOSE; Oct9 starts from Oct8CLOSE. Oct8 coincides with observed policy NAV peaks; no event label enters any signal.',
        caveat='No2024HS300 benchmark added here; no comparison to non-synchronous basketOHLC extrema. net_per_actual_cumulative_buy_cash is descriptive and includes inherited inventory, never phase ROI/alpha.'))
    F.save(OUT/'PHASE_SECTORS_924.json',sectors)
    text='''# 2024 与三年连续账：收盘回撤、绝对亏损及 9/24 钱桥

No60 三年最大收盘回撤为 **38.09%**，期末本金亏损为 **36.20%**。这是两项不同指标；38.09% 已超过用户35%回撤边界，不能因为相对旧策略改善就视为合格。没有同步的全账户盘中价格，实际盘中最大回撤仍未知；这里未把各股票 OHLC high/low 拼成虚构的联合净值曲线。

| 指标 | 原 PVR | No60 |
|---|---:|---:|
'''
    vals=[('2024 自身起始净值',dd['original']['year2024_own_start_NAV'],dd['no60']['year2024_own_start_NAV']),('2024 年末净值',dd['original']['terminal_NAV'],dd['no60']['terminal_NAV']),('2024 段收益率（%）',dd['original']['year2024_return_pct'],dd['no60']['year2024_return_pct']),('2024 最大收盘回撤（%）',dd['original']['year2024_CLOSE_maxDD']['percent'],dd['no60']['year2024_CLOSE_maxDD']['percent']),('2022→2024 最大收盘回撤（%）',dd['original']['cumulative2022_2024_CLOSE_maxDD']['percent'],dd['no60']['cumulative2022_2024_CLOSE_maxDD']['percent']),('2024 期末相对原始100万本金损失（%）',dd['original']['terminal_original_principal_loss_pct'],dd['no60']['terminal_original_principal_loss_pct'])]
    text+='\n'.join(f'| {name} | {fmt(a)} | {fmt(b)} |' for name,a,b in vals)
    text+='''

真实历史峰谷来自完整726条收盘净值，包含初始100万，不使用会重置的 ACT episode peak：

| 口径 | 峰值日期 / 净值 | 谷值日期 / 净值 |
|---|---|---|
'''
    for ref,label in [('original','原 PVR'),('no60','No60')]:
        for k,scope in [('year2024_CLOSE_maxDD','2024年段'),('cumulative2022_2024_CLOSE_maxDD','三年全段')]:
            x=dd[ref][k];text+=f"| {label} {scope} | {x['peak_at']} / {fmt(x['peak_NAV'])} | {x['trough_at']} / {fmt(x['trough_NAV'])} |\n"
    text+='''
No60 的 Dec25 谷值之后至年末净值相同；表中保留首次到达该最大回撤的日期。三年峰值初始100万也等于 Jan4 首个实际收盘净值。2024段各自以自身2023末为起点，没有重置100万或用相同资本、持仓和ACT状态替代两条真实路径。

| 2024财富桥（元） | 严格已实现交易变化 | 未实现变化 | 新计未收股息 | 财富变化 | 实际含费买款 | 平均暴露（%） | 实际买卖费 |
|---|---:|---:|---:|---:|---:|---:|---:|
'''
    for ref in ['PVR_SLOT1','PVR_NO_CONFIRMED60']:
        y=summ[ref]['year2024'];text+='| '+ref+' | '+' | '.join(fmt(y[k]) for k in ['realized_trade_net','unrealized_change','recognized_dividend','wealth_change','actual_buy_cash','mean_exposure_pct','actual_fees'])+' |\n'
    text+='''
以下按 Jan2–Sep23 / Sep24–Oct8 / Oct9–Dec31 描述性分段。前锚分别为各自2023末、Sep23收盘和Oct8收盘；Oct8与观察到的峰值重合，只用于解释事件后资金路径，不进入信号。全量买入、卖出与库存重新估值都在，不能将多买或少投单独当成成功原因。

| 策略 / 分段 | 财富变化 | 段收益（%） | 实际含费买款 | 平均暴露（%） | 平均名义风险 / NAV（%） | 活跃 / 暂停OPEN日 |
|---|---:|---:|---:|---:|---:|---:|
'''
    for r in phases:text+=f"| {r['reference']} / {r['phase']} | {fmt(r['wealth_change'])} | {fmt(r['return_pct'])} | {fmt(r['actual_buy_cash'])} | {fmt(r['mean_exposure_pct'])} | {fmt(r['mean_nominal_risk_pct'])} | {r['active_OPEN_closes']} / {r['paused_OPEN_closes']} |\n"
    text+='''
资金分母为实际成交的累计含费买款（含资金循环）、平均仍持仓成本/市值和原生记录名义风险；买卖费仅扣一次。No60大涨段起初已有422,398.40元库存，新增买款121,446.43元，不能把179,319.69元全部利润除以新增买款解释为该段投资回报。保存表中net/buycash仅为描述字段，包含承接库存，不能称ROI或alpha。卖出确认对价含未结算应收，股息应收不混可支用现金。ACT状态按此前最后收盘归属下一OPEN，不能用同日收盘新状态回贴上午交易。每个分段/行业均闭合净成交对价+库存变化+AR，以及严格实际卖出损益+未实现变化+AR两条桥。

同1709股/90行业、canonical和score manifest身份、原execution源、各自父484日daily/trade/audit前缀和Jan2唯一性已核；旧/新所有726日数量、raw-close库存、费用/资本/池证书与财富桥通过。两本累计持仓拆股层事件各5、碎股转换为0、终态逐层数量精确；无新账户对象或事件。财务桥与身份检查不等于信号忠实性检查，2024全inputs/信号/原生恢复由owner及独审另行给结论。

交付：`SUMMARY.json`、`PERIODS.json`、`SECTORS.json`、`*_DAILY.json`、`PHASES_924.json`、`PHASE_SECTORS_924.json`、`SOURCE_MANIFEST.json`；逐层出口位于 `analysis/2022_2024/*/LAYERS.json`，供独立行为分工复用。DD曲线、峰谷及源/父接续门禁在 `../continuation2024_drawdown/`。没有补充2024指数或盘中联合回撤；港股、120万真实规模、样本外和执行近似仍未验证。
'''
    audit_path=HERE.parent/'independent_review/PVR_2024_INDEPENDENT_AUDIT.json';audit=read(audit_path);checks=[]
    assert audit['account_events']==0
    for ref,side in [('PVR_SLOT1','original'),('PVR_NO_CONFIRMED60','no60')]:
        q=audit[ref];a=summ[ref];d=dd[side]
        pairs=[('terminal_NAV',q['NAV'],d['terminal_NAV']),('cumulative_wealth',q['wealth_PNL'],a['cumulative2022_2024']['wealth_change']),('cumulative_fees',q['fees'],a['cumulative2022_2024']['actual_fees']),('cumulative_mean_exposure_pct',n(q['mean_exposure'])*100,a['cumulative2022_2024']['mean_exposure_pct']),('full_CLOSE_DD_pct',n(q['close_DD'])*100,d['cumulative2022_2024_CLOSE_maxDD']['percent']),('2024_return_pct',n(q['own_year_segment']['return_on_own_parent'])*100,d['year2024_return_pct']),('2024_CLOSE_DD_pct',n(q['own_year_segment']['own_year_close_DD'])*100,d['year2024_CLOSE_maxDD']['percent']),('2024_wealth',q['own_year_segment']['account_wealth_change'],a['year2024']['wealth_change'])]
        for label,x,y in pairs:
            error=abs(n(x)-n(y));assert error<D('.000000001'),(ref,label,error);checks.append(dict(policy=ref,metric=label,error=error))
        assert q['daily_bridges']==q['independent_price_days']==726 and q['day']==d['cumulative2022_2024_CLOSE_maxDD']['trough_at'][:10]
    text+='\n独立审核已完成：`../independent_review/PVR_2024_INDEPENDENT_AUDIT.json` 独立重建两臂全部726日raw-close库存、现金/数量/费用/股息及NAV，核同2024自身段及三年最大收盘回撤；本报告16项主要指标交叉误差小于1e-9。9/24分段及行业细分为本次已保存日级金额的闭合聚合，未宣称另一次9,308行逐格独审；输入信号忠实性继续按独立技术审查范围给结论。\n'
    (OUT/'READOUT.md').write_text(text)
    F.save(OUT/'INDEPENDENT_AUDIT_BINDING.json',dict(account_events=0,independent_audit_path=str(audit_path),independent_audit_sha256=sha(audit_path),key_metric_cross_checks=checks,full_raw_finance_observations_per_policy=726,
        not_claimed='No additional exhaustive independent cell review of9308phase/sector rows; no intradaymaxDD or signal-fidelity conclusion supplied by money bridge.'))
    F.save(OUT/'READOUT_BINDING.json',dict(account_events=0,independent_2024_finance_review='complete raw726day finance and closeDD;16 main metrics crosschecked',
        references={str(p):sha(p) for p in [Path(__file__),OUT/'SUMMARY.json',OUT/'PERIODS.json',OUT/'SECTORS.json',OUT/'PHASES_924.json',OUT/'SOURCE_MANIFEST.json',HERE/'continuation2024_drawdown/DRAWDOWN_COMPARISON.json']},
        readout_sha256=sha(OUT/'READOUT.md')))
    print('2024_PHASES_READY',json.dumps(phases,ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':main()
