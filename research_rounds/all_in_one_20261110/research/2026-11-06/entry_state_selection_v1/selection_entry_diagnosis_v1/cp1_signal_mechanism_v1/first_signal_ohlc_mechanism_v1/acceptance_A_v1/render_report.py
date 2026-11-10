from pathlib import Path
import pandas as pd, json, hashlib, math
O=Path(__file__).resolve().parent
s=pd.read_csv(O/'SIGNAL_SUMMARY.csv');d=pd.read_csv(O/'DAILY_23_ROWS.csv');e=pd.read_csv(O/'FIXED_ANCHOR_EXTENSION.csv');q=pd.read_csv(O/'TOP_CONTRIBUTORS.csv');diag=pd.read_csv(O/'SOURCE_DIAGNOSTICS.csv')
# Overlap examples prioritize actual nonzero current contributions, not inert old ranges.
co=pd.read_csv(O/'ALL_ORIGINAL_WINDOW_COHORTS.csv'); overlaps=[]
for _,sig in s.iterrows():
    hs=co[(co.case_id==sig.case_id)&(co.date==sig.date)]
    for metric in ['positive','negative']:
        cs=hs[hs[metric]>0].sort_values(metric,ascending=False).head(10).reset_index(drop=True)
        pairs=[]
        for j in range(len(cs)):
            for k in range(j):
                a=cs.iloc[k];b=cs.iloc[j];lo=max(a.low,b.low);hi=min(a.high,b.high)
                if hi>lo:pairs.append((float(a[metric]+b[metric]),k,j,lo,hi))
        if not pairs:continue
        score,k,j,lo,hi=max(pairs);a=cs.iloc[k];b=cs.iloc[j]
        overlaps.append(dict(case_id=sig.case_id,metric=metric,date_a=a.cohort_date,date_b=b.cohort_date,native_low_a=a.low,native_high_a=a.high,native_low_b=b.low,native_high_b=b.high,raw_low_a=a.raw_low,raw_high_a=a.raw_high,raw_low_b=b.raw_low,raw_high_b=b.raw_high,intersection_low=lo,intersection_high=hi,intersection_over_union=(hi-lo)/(max(a.high,b.high)-min(a.low,b.low)),q_a=a.q,q_b=b.q,wq_a=a.wq,wq_b=b.wq,contribution_a=a[metric],contribution_b=b[metric],combined_contribution=score,selection='Largest combined nonzero same-sign contribution among overlapping pairs in that sign top 10; diagnostic only'))
pd.DataFrame(overlaps).to_csv(O/'OVERLAPPING_INTERVAL_EXAMPLES.csv',index=False,float_format='%.16g')
def fmt(v):
    if pd.isna(v):return '—'
    if isinstance(v,(bool,)):return '是' if v else '否'
    if isinstance(v,(int,float)):
        if v==0:return '0'
        return f'{v:.8g}'
    return str(v)
def tab(df,cols,headers=None):
    out=['| '+' | '.join(headers or cols)+' |','| '+' | '.join('---' for _ in cols)+' |']
    for _,r in df.iterrows():out.append('| '+' | '.join(fmt(r[k]) for k in cols)+' |')
    return '\n'.join(out)
report='''# 独立成交接受度 A：六例逐日条件算术

## 先给结论与边界

**A≥1 只是一项研究候选确认，不拦截原 MOBILE 首试。A<1 不等于走势是假，A≥1 也不证明走势成真。** 本文没有账户、仓位、下单、全池检验、排序或参数搜索。

六例首证中，只有既有亏例 300182 当日满足 A≥1；两个明确赢家 600606、688582 当时 A 显著为负。这是本定义的重要反例，不应包装成“成功过滤”。两条 600056 单观察窗口都因锚后没有任何已完成历史 bar 而 P=0：3/3 的 N 仅 0.0000850801，主要是尚无正证据，不能解释为强烈负质量；3/30 的 N 严格为 0。

**所有计算都给定原 CP 真实形成锚。若先前原 receipt 被另一个完整系统改变，后续 alpha 会变。因此这里既不是新 CP 状态机，也不确定新系统的真实买入日。** 下面的延迟只是“固定原锚并且不消费正证据”的条件成熟时间。原首试保持不变；原 CORE 新 I 试仓旁路仅理论保留，未据此证明保留所有大行情。

## 冻结定义

先保存 FROZEN_DEFINITION.json、28 个来源 SHA-256 和六例清单，之后才计算。公式冻结文件 SHA-256：de85515a8e6ebaa097ece4380f0b39d5bb5deb98b644f15e68ad784432724a01。SCOPE_ADDENDUM.json 仅将解释限为候选确认，并定义条件延迟范围，未改公式。

- native O/H/L/C = 指定 raw OHLC × 原 facts.factor；amount 使用原输入金额。所有历史比较用 native 坐标，绝不混 canonical5517。
- B_i = 严格 i 日之前 21 个同 source 原有效观察的 amount 中位数。z_i 直接读原 CP.z，并核对它等于严格在 i 日之前的 63 个绝对对数收益中位数 ×1.4826，依原实现先截底 1e−8、再截底 log(1.001)。
- q_i=amount_i/B_i，**q 无上限**；p_t=log(C_t)，h_i=log(H_i)，l_i=log(L_i)。
- w_it=exp(−age_it/21)，age 是同 source 原有效观察序号差，不是日历天数。b_it=clip((p_t−h_i)/z_i,0,1)；d_it=clip((l_i−p_t)/z_i,0,1)。
- P_t=Σ[alpha<i<t] w_it q_i b_it；N_t=Σ[同 source 全部合格 i<t] w_it q_i d_it；A_t=P_t−N_t。
- 价格门：原形成窗 D_t≥sqrt(5)×原锚冻结 scale，且 fresh_t>0。候选确认门：A_t≥1。每行当日 cohort 贡献严格为 0。
- 区间内未判明质量 U_t=Σ[l_i≤p_t≤h_i] w_it q_i。另列 U_post（锚后子集）和 Σwq(1−b−d)（包含区间外未满一个 z 的部分），后者不是同一个 U。它们不应混为 P/N 的第三个互斥总账，因为旧锚前正项根本不进入 P。

amount 与 B 同为人民币金额观察，q、P、N、A 的量纲是“基准日金额当量”；A=1 是净 1 个基准日金额当量。21 只是沿用成交额基准记忆的**未验证设计假设**，不称最优。O 保留诊断，不进入 A。不能把这些历史日成交额当成仍在持有的筹码、主动资金或真实挂单承接。

正证据仅原锚后可用：receipt/lower_anchor 后重置正历史资格。负 cohort 不随 I 失效或 CP reset 清空，只有 source 不可比时断开，或价格恢复使 d=0、年龄自然衰减。历史指数尾全部保留，不以 12 bar 截断。

## 六例首证

'''
report+=tab(s,['sid','original_signal_day','P','N','A','candidate_A_ge_1','D_over_T','unknown_interval_mass_all'],['股票','原首证','P','N','A','候选A≥1','D/T','U全历史'])
report+='''

300182 在 12/31 已 A=1.0430229，但 D/T=0.885521；到 1/4 价格门与 A 才同时满足。它仍是既有亏例，说明这套承接接受度不是“避免亏损”的充分条件。原未来盈亏仅作为事先指定病例名称，不用于系数、阈值或等待规则。

600056 3/3 的 P=0 源自 alpha=3/2、t=3/3，集合 alpha<i<t 为空，不是成交不足；当天 q=30.5954268 也被严格排除。3/30 同理。**一个原锚后的第一根观察，无论涨多大、当日成交多大，本 A 都不可能当日满足 1。** 对这类窗口，它内生带有至少再观察一根的限制。这是数学结构，不是识别真假的证据。

## 原锚至首证的全部 23 行

D 和 fresh 都从该原锚日收盘后从零开始。若锚日是 receipt，其原 CP 行还带上个周期的位移，因此这里不误用该原行的旧周期 D。

'''
report+=tab(d,['case_id','date','P','N','A','D','T','D_over_T','fresh','candidate_A_ge_1','unknown_interval_mass_all'],['病例','日期','P','N','A','D','T','D/T','fresh','A≥1','U'])
report+='''

每行最大正/负贡献者、最大 q、U_post、完整精度见 DAILY_23_ROWS.csv。每行前三个非零负贡献者的 native O/H/L/C、amount、B、z、年龄、q、d 和贡献见 TOP_NEGATIVE_BY_DAY.md；TOP_CONTRIBUTORS.csv 同时列前三个非零正贡献者与前三 q。不存在非零正/负项时，明确写无，不用任意零贡献日期充当贡献者。

## 条件成熟时间与可见价格代价

只在原首证日及之后查看：固定原形成锚、原锚冻结尺度、不消费正证据。以 source 改变、原 I.target 失效、原 E0 失效、原 E0_down 或原 CP lower_anchor/E0_down_reset 为自然截止，不加固定最大等待天数；截止行本身不计入旧尝试，也不让后来的新 CP 复活旧证。

**原 receipt 实际已经消费并改锚，本诊断有意不沿用这个消费动作。原实际状态与固定锚诊断已不同，因此这里不是真实策略等待天数。** 同时列首次 A≥1 和首次 A≥1 且固定锚价格门/fresh 成立。六例这两类“首证之后的首次确认”恰好同日，不意味着一般都相同。

'''
s2=s.copy();s2['price_cost_pct']=s2.conditional_A_close_vs_signal_simple_return*100
s2['conditional_result']=s2.first_conditional_A_confirmation.fillna('自然失效前未确认')
s2['subsequent_original_receipts']=s2.original_receipts_ignored_count-1
report+=tab(s2,['sid','original_signal_day','conditional_result','conditional_A_delay_observations','price_cost_pct','first_A_confirmation_fresh','extension_stop_date','max_A_until_natural_stop','subsequent_original_receipts'],['股票','原首证','条件A确认','延后观察数','确认收盘相对首证%','确认fresh','自然截止','截至截止前maxA','期间后续原receipt数'])
report+='''

- 600056 3/3：3/4 条件确认，原未复权收盘 13.43→14.77，+9.9777%。3/3 自身的 q=30.5954 在翌日成为历史 cohort，P 一次跳到 29.172647；这不是多日广泛承接，而是**单日巨额 cohort 支配全部 P**。
- 600056 3/30：下一观察 3/31 原 E0_down_reset，自然截止前没有任何延伸行，max A=0。写“未确认”，不是“无限延后”。
- 300182：1/4 当日确认，价格代价 0；仍是预指定亏例。1/10 原 E0_down_reset 截止。
- 002385：3/7 仍未确认，3/8 原 I/E0 失效且 native down，max A=−7.603561。阴性结果不能推广为“以后不会走强”。
- 600606：3/23 条件确认，4.32→4.75，+9.9537%；P=4.467556，N=0.010312，A=4.457244。原首证 N=6.895682，次日几乎消失，主要因为价格收复历史区间，而非一夜年龄衰减。
- 688582：7/30 A=−5.132444，7/31 条件确认，29.05→30.59，+5.3012%；P=4.011200，N=1.034273，A=2.976927。7/30、7/31 原 i_buy=True，说明新 I 旁路与候选 A 的事件可能交错，不能说整个原系统等到 A 才第一次参与。

上述比例为同坐标收盘比较，不是成交价、滑点或损益。所有首次确认日原 I 均有效。FIXED_ANCHOR_EXTENSION.csv 提供 56 行完整延伸、原 receipt、原实际 anchor 和固定 anchor 的区别；源头首证本身也消费了一次 receipt，表内“期间后续原 receipt 数”不含这一次。

## 与短暂等待/冻结的关系

A 不是固定等 N 天：相同经过天数可因不同历史区间与成交额而得出相反结果；N 可因价格恢复快速归零，也可能一直延续至自然失效。P/N 都会随着当前收盘变化重新估值，不是不可撤销的“信用余额”。若价格不动且没有新增合格正项，已有 P 与 N 一起指数衰减，A 的符号不会被单纯等待翻转；纯负 A 只会趋近 0，不能单凭时间变成 ≥1。

但它与“先观察再确认”**有实质重叠**：严格禁止当前 bar 自证，且正项只取锚后，所以单根冲高必定尚未确认。本次 +1/+1/+2 观察的条件成熟恰好对应约 +10%/+10%/+5.3% 的收盘价差。若把它直接当作 MOBILE 首试闸门，就会重新引入用户不希望的等待和追高问题。当前只将其保留为可量化研究状态，不默认拦截首试，也不因为这些病例结果去改阈值放行。

## 巨额 q、最大贡献与重复成交暴露

q 不封顶，而 b/d 只封顶 1：单批最大绝对贡献可到 w×q，不受 1 限制。历史最大 q 不等于当前最大贡献，必须同时看年龄、位置、b/d 与锚前/后。

'''
for _,r in s.iterrows():
    v=q[(q.case_id==r.case_id)&(q.date==r.date)]
    report+=f"\n### {r.case_id}\n\n"
    report+=tab(v,['metric','rank','cohort_date','q','age','wq','b','d','positive','negative'],['排行','序','历史日','q','age','wq','b','d','P贡献','N贡献'])
    if not len(v[v.metric=='positive']):report+='\n\n无非零正贡献者。'
    if not len(v[v.metric=='negative']):report+='\n\n无非零负贡献者。'
    report+='\n'
report+='''

600056 3/30 所见历史最高 q 分别 82.7759、77.1266、53.2780；它们在当前锚前，所以正贡献为零，价格又在它们的高点之上，所以负贡献也为零。不能只看 q 很大就宣称它们支配该日 A。反之，3/4 的 3/3 cohort q=30.5954 确实单独占全部 P，随后固定锚不消费的诊断 max A 达 288.2209，显示这种总和可有极不均衡的尺度。原实际 CP 每张 receipt 会重锚，此巨大值尤其不能直接读作原实际状态。

**同价格区间的多日重复暴露可能多计同一批资金的周转。** 002385 3/2 与 3/3 原未复权 H/L 为 [8.41,8.72] 与 [8.39,8.69]，区间交并比 0.848485；3/4 对它们仍分别加正证据 0.353438 与 0.406268，合计 0.759707。688582 6/20 与 6/21 区间 [30.31,31.99] 与 [30.26,32.35] 明显重叠，7/29 分别加负证据 0.659171 与 0.679120，合计 1.338291。公式并未去重，也没有持仓流转信息来证明这代表两份独立未解套存量。因此它是“逐日成交暴露的加权记录”，不是可独立加总的筹码库存。

OVERLAPPING_INTERVAL_EXAMPLES.csv 另按当前非零 P/N 分开，从该方向贡献最大的十个 cohort 中找相互重叠、合计贡献最大的对；只作读数说明，不生成新门槛或策略。无非零重叠对就不造例。600056 3/3 和300182的负项重叠只是极小指数尾，仍按原数值列明，不能把它们渲染成实质支配。

## 全历史负项、warmup、missing 与 source

每个 source 的最前 64 条原观察还不能获得完整 B/z，明确记为不可用，不是零成交、零负债，也不把缺失前史伪造为 0。合格 cohort 从第一条 B、z、OHLC、amount 全部可知的观察开始。五只股票原输入各仅一个 source segment，本次没有实际 source 切换；代码仍明确只汇总当前同 source。合格历史不按 CP.ready、I.target 或 E0 有效性过滤。

'''
report+=tab(diag,['sid','segment_first_date','first_B_date','first_z_date','first_eligible_cohort_date','unavailable_warmup_B_or_z_rows','missing_or_invalid_OHLC_amount_rows','source_segment_resets'],['股票','输入开始','首B','首z','首合格cohort','warmup行','缺失/非法OHLC行','source重置数'])
report+='\n\n本次首证实际读取合格历史及旧 I 失效期间 cohort：\n\n'
report+=tab(s,['sid','original_signal_day','eligible_history_count','history_I_invalid_cohorts','N','N_age_over_12'],['股票','首证','合格历史数','其中I失效行','N全历史','age>12的N'])
report+='''

002385 与 600606 的首证负项全部来自超过 12 观察的历史；688582 N=6.612044 中 6.280211 来自 age>12。只读 PRE_SIGNAL_CONTEXT 的 12 bar 会彻底改变结论，因此该文件只用于固定原窗核对，不当 N 起点。300182 的 N=6.62×10⁻¹⁴ 仍保留精确正值，经济意义近于零，不渲染为实质负质量；600056 3/3 的小尾也按同样原则解释。

688582 原 CP parquet 比原 CP1_input 多 79 条 2026-07 至 2026-10 尾部记录。分析只用 CP1_input 的原观察索引，额外日期已记录在 SOURCE_DIAGNOSTICS.csv，不把缺少原 input 的尾部拼接成新增观察。全部六例及其自然截止均早于这段尾部，未受影响。最初严格要求两个全索引相等的验证被这个差异中止；只修正覆盖检查并记录 ATTEMPT_LOG.json，未改公式或原数据。

## 检验与文件

CHECKS.json：23/23 原形成窗 D/fresh 与已有逐日记录一致；79/79（23原窗+56延伸）完整前缀标量重算与向量算术一致；当日贡献均零；两条600056首证均 P=0 且 A≤0；B/z 均严格前置；native收盘与原facts/input匹配；amount精确匹配；全同源历史、I无效时期cohort保留；28个来源哈希与冻结定义哈希未变。没有重算原 CP 指标状态。

- FROZEN_DEFINITION.json、SCOPE_ADDENDUM.json、SOURCE_SHA256.json：冻结公式、边界与来源。
- DAILY_23_ROWS.csv：23 行完整逐日结果，含 P/N/A、D/T、未判明量、贡献最大值及日期。
- SIGNAL_SUMMARY.csv：6 例首证、条件延迟、可见价格代价、自然截止与 maxA。
- FIXED_ANCHOR_EXTENSION.csv：56 行固定锚条件延伸，明确保留原receipt/anchor对照。
- TOP_CONTRIBUTORS.csv、TOP_NEGATIVE_BY_DAY.md：逐日前三个非零正/负项和前三 q；附每批 OHLC/amount/B/z。
- ALL_ORIGINAL_WINDOW_COHORTS.csv：39,721 条原窗历史 cohort 明细，可逐项手工复核。
- SOURCE_DIAGNOSTICS.csv、OVERLAPPING_INTERVAL_EXAMPLES.csv、CHECKS.json、ATTEMPT_LOG.json、RUN_RESULT.json、OUTPUT_SHA256.json。
- analyze_acceptance.py、render_report.py：隔离、可复现脚本。

不把这六例当总体统计，不报告胜率或收益改善，不声称 A 发现了独立于价格的因果成交需求。它确实引入原CP没读的 H/L 与历史金额位置，但仍强烈依赖当前收盘，是否有额外信息价值尚未被这六例证明。
'''
(O/'REPORT.md').write_text(report)
appendix='# 每个原形成窗观察的前三个非零负贡献\n\n全部价格为原 native 坐标；金额为人民币。空集合明确写无。完整未复权价格也保留在 TOP_CONTRIBUTORS.csv。\n'
for _,r in d.iterrows():
    v=q[(q.case_id==r.case_id)&(q.date==r.date)&(q.metric=='negative')]
    appendix+=f"\n## {r.case_id} / {r.date}\n\nP={r.P:.16g}，N={r.N:.16g}，A={r.A:.16g}；U={r.unknown_interval_mass_all:.16g}。\n\n"
    if v.empty:appendix+='无非零负贡献。\n'
    else:appendix+=tab(v,['rank','cohort_date','open','high','low','close','amount','cp_B','cp_z','age','q','w','d','negative'])+'\n'
(O/'TOP_NEGATIVE_BY_DAY.md').write_text(appendix)
def dg(p):return hashlib.sha256(p.read_bytes()).hexdigest()
f=json.loads((O/'FROZEN_DEFINITION.json').read_text());assert all(dg(Path(p))==h for p,h in f['source_sha256'].items())
(O/'FINAL_SOURCE_CHECK.json').write_text(json.dumps({'all_28_source_hashes_unchanged':True,'frozen_definition_unchanged':dg(O/'FROZEN_DEFINITION.json')=='de85515a8e6ebaa097ece4380f0b39d5bb5deb98b644f15e68ad784432724a01','source_files_written':0},indent=2)+'\n')
(O/'OUTPUT_SHA256.json').write_text(json.dumps({p.name:dg(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_SHA256.json'},indent=2)+'\n')
print(json.dumps({'report':str(O/'REPORT.md'),'files':len(list(O.iterdir())),'source_check':'passed','report_characters':len(report),'appendix_characters':len(appendix)},ensure_ascii=False))
