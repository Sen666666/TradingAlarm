"""Render fixed-date evidence after models and price diagnostics are complete."""
from pathlib import Path
import argparse,json
import pandas as pd

ROOT=Path(__file__).resolve().parent


def pct(v):return 'NA'if pd.isna(v)else f'{float(v)*100:.2f}%'
def num(v):return '—'if pd.isna(v)else str(int(v))


def main(day):
    b=ROOT/day;a=json.loads((b/'ASSEMBLY_RECEIPT.json').read_text());p=json.loads((b/'PRIOR_RANKS_RECEIPT.json').read_text())
    coverage=json.loads((b/'paths/COVERAGE_METADATA.json').read_text());s=pd.read_csv(b/'GROUP_SUMMARIES.csv')
    q=pd.read_csv(b/'QUEUE_COUNTS.csv');signal=json.loads((b/'signals/COMPLETION.json').read_text())
    timing=(f"本日原会话中断后安全续算，COMPLETION中的{signal['full_batch_wall_seconds']/60:.2f}分钟只表示最后续跑调用；全程含暂停墙钟及首段可观测跨度另见signals中的恢复收据，不将其称为本日总耗时。" if (b/'signals/INTERRUPTION_STATUS.json').exists() else f"12worker原信号实际{signal['full_batch_wall_seconds']/60:.2f}分钟。")
    table=['|范围|PVR可评分|PVR且I有效|PVR且i_buy|','|---|---:|---:|---:|']
    for key,label in [('ALL_LOCAL','全本地池'),('OLD1709_STATIC_REFERENCE','旧1709静态交集'),('OUTSIDE_OLD1709','旧池外')]:
        z=q.loc[q.scope.eq(key)].set_index('queue').N
        table.append(f'|{label}|{z.PVR}|{z.I_HOLD}|{z.I_BUY}|')
    top=['|观察数|冻结组|原N/完整N|末端均值|末端中位数|MFE均值|MAE均值|末端为正|','|---|---|---:|---:|---:|---:|---:|---:|']
    for _,r in s.loc[s.view.eq('WITHIN_SCOPE_RANKS')&s.scope.eq('ALL')&s.band.isin(['ALL','RANKABLE','PVR_UNKNOWN','TOP20','REST20','TOP100','REST100'])].iterrows():
        top.append(f'|{r.horizon}|{r.band}|{r.prior_N}/{r.complete_N}|{pct(r.terminal_mean)}|{pct(r.terminal_median)}|{pct(r.MFE_mean)}|{pct(r.MAE_signed_mean)}|{pct(r.terminal_positive_rate_complete)}|')
    dec=['|PVR档|N|5观察均值/中位|20观察均值/中位|','|---|---:|---:|---:|']
    z=s.loc[s.view.eq('WITHIN_SCOPE_RANKS')&s.scope.eq('ALL')]
    for d in range(1,11):
        u=z.loc[z.band.eq('D'+str(d))].set_index('horizon')
        dec.append(f'|D{d}|{int(u.loc[5,"prior_N"])}|{pct(u.loc[5,"terminal_mean"])}/{pct(u.loc[5,"terminal_median"])}|{pct(u.loc[20,"terminal_mean"])}/{pct(u.loc[20,"terminal_median"])}|')
    split=['|子池|观察数|组|N|末端均值|末端中位数|MFE/MAE均值|','|---|---:|---|---:|---:|---:|---:|']
    for _,r in s.loc[s.view.eq('WITHIN_SCOPE_RANKS')&s.scope.ne('ALL')&s.band.isin(['ALL','TOP20','REST20','TOP100','REST100'])].iterrows():
        split.append(f'|{r.scope}|{r.horizon}|{r.band}|{r.prior_N}|{pct(r.terminal_mean)}|{pct(r.terminal_median)}|{pct(r.MFE_mean)}/{pct(r.MAE_signed_mean)}|')
    cases=pd.read_parquet(b/'FULL5517_CANDIDATES.parquet');names=json.loads((b/'FREEZE.json').read_text())['named_cases']
    labels=pd.read_parquet(b/'FROZEN_RANKS_WITH_PRICE_LABELS.parquet')[['sid','h5_return','h5_max_up','h5_max_adverse','h20_return','h20_max_up','h20_max_adverse']]
    cases=cases.loc[cases.sid.isin(names)].merge(labels,on='sid',how='left',validate='one_to_one')
    cases.to_csv(b/'PREDECLARED15_SIGNAL_AND_MEMBER_PATHS.csv',index=False)
    named=['|静态代码/名称注释|原i_buy|已知机会解释|PVR i_buy序|5观察末端|20观察末端|','|---|---|---|---:|---:|---:|']
    for _,r in cases.sort_values(['rank_ALL_LOCAL_I_BUY','sid'],na_position='last').iterrows():
        state='UNKNOWN'if pd.isna(r.i_buy_research)else str(bool(r.i_buy_research))
        named.append(f'|{r.sid} {r.current_name}|{r.i_buy}|{state}|{num(r.rank_ALL_LOCAL_I_BUY)}|{pct(r.h5_return)}|{pct(r.h20_return)}|')
    text=f'''# {day}：完整本地原信号与冻结PVR路径诊断

完成5517请求，{a['exact_target_bar']}有当日行情、{a['missing_target_bar']}缺行；E0/G1均就绪{a['G1_and_E0_ready']}，已知I有效{a['I_hold_true']}，已知当日i_buy {a['i_buy_true']}，i_buy解释未知{a['i_buy_unknown']}。缺行/未ready的原0或False不当作已知拒买；历史交易资格全部UNKNOWN。

每只正式模型只接收<=本日的完整可得canonical前缀。原11算法源码与924实现未修改；既存同日同源target仅复用，控制19字段核同。{timing}未重复924、未启动账户、订单、参数拟合或联网买数。

{chr(10).join(table)}

## 先验母体与缺PVR

在读取future路径之前冻结全部已知True i_buy，共{p['N']}。可排名{p['scopes']['ALL']['rankable_N']}，PVR未知{p['scopes']['ALL']['PVR_unknown_N']}。ALL保留全部信号；RANKABLE及十档/TOP/REST仅使用已知原PVR，未知单列PVR_UNKNOWN，不造最差分、不用未来表现补位。Top20/100小于容量时取已有N，空REST及空未知组统计NA。原排序、分母、代码SHA见[先验收据](PRIOR_RANKS_RECEIPT.json)。

当日排序源仅为此前已冻结原PVR，不用任何后验标签。D1最好，`floor((rank-1)*10/N_rankable)+1`。旧1709静态名单只是对照，精确数据交集1681而非完整1709；不授予历史资格，不等于历史PIT市值池。

## 全母体前列与余下

所有变化从信号日已知qfq收盘C0起算，`末端=C_h/C0-1`；MFE含0取最大未来收盘变化，MAE含0取最小未来收盘变化。MAE不是峰谷最大回撤，MFE不是可实现卖出价。h是个股有效价量观察，不是市场交易日。原N与完整N同时列；未知/删失不填零。前20/前100两对比较重叠，不能相加。

{chr(10).join(top)}

{chr(10).join(dec)}

## 旧池/池外：子池内部原排序

{chr(10).join(split)}

上述每个子池各取自己的前20/100，不能合成全池同数量。另有全池固定档×旧池身份、不重分档的交叉视图：GROUP_SUMMARIES中`GLOBAL_BANDS_BY_MEMBERSHIP`。

## 预定15案例与尾部

{chr(10).join(named)}

案例列表在日期/结果前已固定，不为未来赢家选样；非i_buy成员的未来价格未加入统计，NA不表示零变化。序号“—”表示未入对应队列，已知False与未就绪未知由解释列区别。名称仅本地静态注释，ST/*ST/DR字样不代表当日或当前真实状态。

尾部定义完全沿用924：完整全i_buy cohort的后验最高1%/5%末端变化，ceil取数、sid破同分；只作评价不回流PVR。GROUP中的capture/价格变化mass share用全cohort分母；TAIL_PRICE_CONCENTRATION各scope则用本scope分母。largest1/5/20及去最大1为解释敏感度，不是可执行筛股规则，不称利润贡献。详见[全部分组](GROUP_SUMMARIES.csv)、[价格集中度](TAIL_PRICE_CONCENTRATION.csv)、[后验标签仅诊断](EXPOST_DIAGNOSTIC_LABELS_ONLY.csv)。

## 实际日期、删失与非PIT

原始coverage见[路径覆盖](paths/COVERAGE_METADATA.json)。全源日期union的第5/20日期为{coverage['common_endpoint_dates']}；它是本地观察代理，不是经认证交易日历。个股终点分布{coverage['horizons']}。同源缺行代理{coverage['horizon_gap_proxy_stock_counts']}，不自动称停牌；观察窗口可延后。共同终点敏感度按这些union日期，不选表现最好的日期，也不替换主分组。

块内有效观察不足h即记NA（包括源尾、显式无效、来源变化等）；部分路径另列，不能充当完整h。源尾原因与退市身份未知；239份退市档案仍因单位/复权未统一未混入5517。0窗口删失也不消除幸存偏差。

当前qfq版本/参考日与真实行情发布时间非PIT，历史上市身份/ST/停牌/限价及次日可成交性UNKNOWN。没读OPEN或扣费；不能将巨大价格上行当可买到或账户收益。各股/各日相关，不作iid显著性、独立账户或年化结果；两日预先由用户固定且历史已消费，不是真正样本外。

完整表：[FULL5517_CANDIDATES.csv](FULL5517_CANDIDATES.csv)；[九组前20](TOP20_NINE_QUEUES.csv)；[全部i_buy含价格标签](FROZEN_RANKS_WITH_PRICE_LABELS.csv)。源码、名单及输出核对见[independent_review](independent_review/)。
'''
    (b/'READOUT.md').write_text(text)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--day',choices=['2022-01-24','2026-01-15'],required=True);main(p.parse_args().day)
