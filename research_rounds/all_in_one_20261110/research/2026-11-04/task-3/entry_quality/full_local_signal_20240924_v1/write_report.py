"""Render the completed single-date evidence, never calls signal algorithms."""
from pathlib import Path
import json
import pandas as pd

HERE=Path(__file__).resolve().parent


def fmt(v,digits=0):
    if pd.isna(v):return '未知/未就绪'
    if isinstance(v,bool):return str(v)
    return f'{float(v):,.{digits}f}'


def rankfmt(v):return '—' if pd.isna(v) else fmt(v)


def main():
    a=json.loads((HERE/'ASSEMBLY_RECEIPT.json').read_text())
    s=json.loads((HERE/'signals/COMPLETION.json').read_text())
    q=pd.read_csv(HERE/'QUEUE_COUNTS.csv');n=pd.read_csv(HERE/'NAMED15_SIGNAL_RANKS.csv')
    x=pd.read_parquet(HERE/'FULL5517_CANDIDATES.parquet')
    rows=['|范围|裸PVR可评分|PVR且I有效|PVR且当日i_buy|','|---|---:|---:|---:|']
    labels={'ALL_LOCAL':'全部本地母体','OLD1709_STATIC_REFERENCE':'旧1709静态名单交集','OUTSIDE_OLD1709':'旧名单之外'}
    for scope,label in labels.items():
        z=q.loc[q.scope.eq(scope)].set_index('queue').N
        rows.append(f'|{label}|{int(z.PVR)}|{int(z.I_HOLD)}|{int(z.I_BUY)}|')
    named=['|代码/静态名称注释|PVR|全池裸PVR序|E0 ready|原I_target|原i_buy|解释后i_buy|成交额历史分位|全池i_buy队列序|',
           '|---|---:|---:|---:|---:|---|---|---:|---:|']
    for _,r in n.sort_values(['rank_ALL_LOCAL_PVR','sid'],na_position='last').iterrows():
        p=fmt(r.amount_history252_percentile*100,2)+'%'if pd.notna(r.amount_history252_percentile)else'未知'
        named.append(f'|{r.sid} {r.current_name}|{fmt(r.score,4)}|{rankfmt(r.rank_ALL_LOCAL_PVR)}|{fmt(r.e0_ready)}|{fmt(r.i_target)}|{r.i_buy}|{r.i_buy_research if pd.notna(r.i_buy_research) else "未知"}|{p}|{rankfmt(r.rank_ALL_LOCAL_I_BUY)}|')
    text=f'''# 2024-09-24完整本地可观察池：原E0/G1/I信号

已完成5517条本地标准化序列的单日表，不用2026市值、当前名单或当前行业授予历史候选资格。**这是完整本地母体的个股信号研究，不是历史全A股/PIT、全S0资格、可交易许可或账户策略。**

当日有行情{a['exact_target_bar']}只、缺行{a['missing_target_bar']}只；原PVR可评分{a['PVR_known']}只。E0就绪{a['E0_ready']}只，E0/G1均就绪{a['G1_and_E0_ready']}只；按已就绪原个股状态，I有效{a['I_hold_true']}只、当日i_buy {a['i_buy_true']}只。I解释未知{a['hold_unknown']}只、i_buy解释未知{a['i_buy_unknown']}只，原始默认0/False仍保留在原字段中，未拿它们替代未知判断。

## 接线与时钟

每只正式调用物理读取`symbol==sid AND trade_date<=2024-09-24`，保留全部已有历史，不为速度截短预热。110只旧同源结果、14只新pilot结果复用，正式批次剩余逐股持久化；控制样本重复仅用于核同，不重复计算已完成正式结果。

原管线为`eligible_prices → event_frame_numeric(joint=True,event_exit=False) → participation_frame(mode=volume) → e0_policy(decline_candidate=False) → B5/B4 evidence → G1 classify → project(G1_I)`，19个原信号字段完整保留。输入源码与canonical SHA冻结；未采用旧native缓存的不同价格坐标。

三股各两物理前缀的因果小测通过：追加至10/8的5个后续观察后，共同历史的全部原信号及numeric事件精确不变。扩展输入仅在隔离诊断文件，未作为9/24正式信号。小测不能代替所有分支/PIT认证；全量正式始终只传<=t行。

`I_hold_research`只在exact且原E0 ready时读I_target；`i_buy_research`还须G1 ready，否则NA。`i_buy`是当日原机会，可在已存在I周期再次出现，不等于首次建仓、原账户获资或成交。持有I与当日暖度/新机会不能互相代替。

## 三种队列、三个范围

PVR分数复用同一canonical原公式；降序排列，精确同分按代码升序。历史成交额分位不筛选、不加权。队列分别为裸PVR、PVR且I有效、PVR且原当日i_buy；不把它们冒充行业/H1/CP/账户资格。

{chr(10).join(rows)}

旧1709的精确代码在本地母体中只有{int(x.in_old1709_exact.sum())}只，另28只无同一标准化序列，不猜别名混入。池外是另外{int((~x.in_old1709_exact).sum())}只。这一静态分组只用于报告，不决定新母体或信号。

九份前20及各自分母见[TOP20_NINE_QUEUES.csv](TOP20_NINE_QUEUES.csv)，总表保留所有缺行/未就绪项：[FULL5517_CANDIDATES.parquet](FULL5517_CANDIDATES.parquet) / [CSV](FULL5517_CANDIDATES.csv)。

## 预先指定代表股

{chr(10).join(named)}

这些是事先固定的15只讨论股，不用后续收益筛样。裸PVR排名与i_buy队列排名使用不同分母；序号“—”只表示未进入该队列，已就绪False与未就绪未知由解释列区分。无i_buy序不表示不能走原MOBILE continuing+CP路径，本研究未生成CP或读取持仓状态。完整原保护线、G1和I字段见[NAMED15_SIGNAL_RANKS.csv](NAMED15_SIGNAL_RANKS.csv)。

## 成交额分位与可用边界

固定描述量：`p252=(此前252个同有效块观察中A<A_t的个数 + .5×A=A_t的个数)/252`。排除t；须完整252，否则未知。此前20观察成交额中位数另列，原PVR的prior21参考不改名。已知分位{a['amount252_known']}只；208只缺当日行，130只此前历史不足。金额保持原源单位，20/252均为个股有效观察，不是经认证的市场交易日；缺日不填。

海能达9/24分位1.59%、银之杰100%，没有据此加减授权。分位不等于市值、可成交性、可下单金额或参与率上限；4股原raw窗口计数/中位数独立核同。

历史证券身份、ST、停牌、涨跌停、数据真实发布时间及可执行资格明确UNKNOWN。缺当日行不能推断IPO/退市/停牌；`current_name`只是继承的本地静态名称注释，既不保证历史当日名称，也未认证为今天的最新名称；其中ST/*ST/DR字样不可当历史ST或企业行为状态。239份退市档案另外列覆盖，9/24有33份原行，未在复权/单位不同情况下混入5517榜单。5517本身仍有供应商/幸存、历史6000行截断和别名局限。

价格使用现存canonical qfq，参考日往往晚于t；终端常数缩放对PVR收益率可抵消，不认证历史复权因子版本、企业行为发布日期或E0/I的实际历史版本。所有正式输入行<=t是算法因果要求，与真正PIT数据是两件事。没有真实交易报价、ST/halt/limit状态和完整S0/H1/CP/持仓状态时，此表不可直接作为下单许可，更不能拼成账户收益。

12worker pilot16用时7.81秒、2控制全字段核同；正式批次实际墙钟{s.get('full_batch_wall_seconds',0)/60:.2f}分钟。每股JSONL fsync保存，进度记录、恢复清单、输入SHA及逐块收据均保留。未运行账户、订单、前瞻收益标签或参数搜索。

源码/因果和最终输出审查见[independent_review](independent_review/)。
'''
    (HERE/'READOUT.md').write_text(text)


if __name__=='__main__':main()
