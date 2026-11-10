#!/usr/bin/env python3
import csv,json
from decimal import Decimal as D, getcontext
from pathlib import Path
import analyze_fixed as m
import verify_conditions as v
getcontext().prec=80
O=m.OUT
def put(name,text):
    with (O/name).open("x") as f:f.write(text)
def fmt(x,n=2):
    return "—" if x is None or x=="" else f"{D(str(x)):.{n}f}"
def main():
    rr=m.load(O/"FIXED_CASE_RESULTS.json");bs=m.load(O/"PER_BAR.json");qa=m.load(O/"SOURCE_QA.json")
    lookup={(b["sid"],b["day"],b["clock"]):b for b in bs}
    lowerrows=[]
    for b in bs:
        low=D(b["lower_limit_proxy"]);upper=D(b["upper_limit_proxy"])
        lowerrows.append(dict(sid=b["sid"],day=b["day"],clock=b["clock"],
            lower_limit_proxy=low,upper_limit_proxy=upper,close_at_lower_proxy=D(b["close"])==low,
            flat_at_lower_proxy=D(b["open"])==D(b["high"])==D(b["low"])==D(b["close"])==low,
            source_clock_status="UNVERIFIED_INTERVAL_END_INTERPRETATION",
            source_first_bar_auction_coverage="UNKNOWN",
            source_bar_complete_at_label="UNVERIFIED",source_available_at="UNKNOWN",
            prices_and_limits="SOURCE_CONDITIONAL_AUDIT_ONLY"))
    m.write_csv("SUPPLEMENT_BAR_LIMIT_CLOCK_AUDIT.csv",lowerrows)
    ev=[]
    for c in rr:
        b=lookup.get((c["sid"],c["entry_day"],c["quality_tau"]))
        ev.append(dict(case_id=c["case_id"],quality_tau=c["quality_tau"],
            tau_at_lower_limit_proxy=(D(b["close"])==D(b["lower_limit_proxy"])) if b else None,
            tau_entire_prefix_same_price=b["same_price_entire_prefix"] if b else None,
            tau_close_below_previous_close=b["close_below_previous_close"] if b else None,
            time_is_source_label_not_available_at=True,
            next_bar_interval_start_is_assumed_label_mapping_not_fill_time=True))
    m.write_json("SUPPLEMENT_EVENT_LIMIT_CLOCK_AUDIT.json",ev)
    # A limit-down flat path is algebraically indistinguishable from other exact flat prefixes.
    s,series=v.summary(v.make([("9","9","9","9","1","9")]*4))
    assert s["quality"]==("SIGNAL","09:50")
    tiny=[b for b in bs if b["bar_quality_reasons"] and max(D(b["low"])-D(b["incremental_average"]),D(b["incremental_average"])-D(b["high"]))<=D(".00001")]
    assert len(tiny)==1 and (tiny[0]["sid"],tiny[0]["day"],tiny[0]["clock"])==("688660.SH","2024-09-26","14:05")
    m.write_json("SUPPLEMENTAL_CHECKS.json",dict(flat_lower_proxy_test=dict(input_price="9",hypothetical_preclose="10",hypothetical_lower_limit="9",observed=s,passed=True,not_an_extra_stock_case=True),
        strict_without_tolerance_extra_bar=tiny[0],note="Earlier rough tolerance 1e-5 would miss this bar. Frozen strict Decimal has no tolerance.",
        synthetic_tests_added=1,new_economics=0,source_clock_and_auction_coverage="UNKNOWN",
        next_open_5bp_illegal_proxy_events=sum(bool(c.get("quality_next_open_plus_5bp_above_upper_illegal_proxy")) for c in rr),
        original_open_5bp_illegal_proxy_events=sum(c["old_open_plus_5bp_above_upper_illegal_proxy"] for c in rr)))
    dictionary=dict(
        numeric_storage="原raw OHLCVA原字符串保留；计算Decimal80结果以字符串落JSON，比较使用精确交叉乘积，Fraction另核。显示比值末位不参与决策。",
        provider_nominal_Q="逐bar固定数学式，未因质量抹掉；eligible另列09:50..14:50窗，非窗内不取tau。",
        quality_available_Q="窗内COMPATIBLE时与名义Q一致；第一个坏bar及以后UNKNOWN，不重置累计量额、不忽略坏bar。窗外NOT_EVALUATED。",
        prefix_quality="只表示已见供方bar内部约束相容，不认证实际成交全覆盖、集合竞价覆盖、数据完成、available_at或成交可执行性。",
        quality_status="有更早相容首tau则SIGNAL且不受未来坏bar撤回；此前无tau且评估窗遇坏则UNKNOWN；完整相容窗无tau才NO_SIGNAL。",
        W="供方当日首bar起累计amount/volume，不是全体持仓成本，不识别主动买入或卖出。",
        next_bar_interval_start="按源标签被解释为5分钟期末所做的减5分钟映射；非供方认证定义，不是实际最早可买时点。",
        old_pnl="完整保留原NOACT冻结首层标签，只用于识别原病例，不计算其相加、节约亏损或新收益。",
        PRICE_label="只按原冻结tag识别7盈利/7失败；海能达和4个江丰点均未标经济结果，不借旧O>J报告补标签。",
        old_O_gt_J_mapping="仅PRICE合同sid+signal_day+entry_day精确映射旧19点；NOACT14无同合同映射，一律UNKNOWN。",
        limits="供方配套日线preclose/isST与一般规则代理，未认证历史逐票特殊上下限。不输入Q。",
        SOURCE_QA="全日与日线/native聚合审计，不作前缀门。",
        order_lifecycle="只算首tau，没有真实报价、订单、撤单、部分成交、重审或新经济模型。")
    m.write_json("FIELD_DICTIONARY.json",dictionary)
    text="""# 供方成交重心接受：固定病例条件预检
研究日期：2026-11-09。**不晋升，不跑账户，不更换公式。** 本次把ORB“必须突破开盘高点”换成唯一冻结的供方累计均价条件，解决了涨停高点天花板，却没有分开固定失败和赢家。

## 1. 关键结果
- 10/8福莱11:25许可，下一bar open14.10，相对原open14.69为−4.02%；歌尔09:55也许可，下一bar24.57，相对24.94为−1.48%。两例名义与点时质量版一致。福莱恢复许可不等于识别成功，因为歌尔失败也恢复且更早。
- NOACT七个快失败只对岩山无许可，天山、华东、三花、新集、格力、烽火六个均许可。六个原赢家有五个许可，润泽仍无许可。另江丰原亏损控制点14:20也许可。不把这些病例计数称新拒错率、胜率或省亏损。
- **烽火2026-01-15全48bar O=H=L=C=43.07，量正、A=43.07V；对应preclose47.86、跌停代理43.07，09:50因两项等号许可。** 平价涨停、普通横盘和平价跌停都可以自动通过。该式不识别主动承接、放量或净需求。
- PRICE十九点中十八许可，唯一无许可是华电辽能。七个明确旧失败仍有六个许可，七个明确旧盈利全部许可；海能达和四个江丰点仅时钟/纯输入对照，经济标签未知。
- 四股日41根bar有严格额量/区间不相容，后续共89根前缀UNKNOWN。四例的首许可都发生在首坏bar之前，因此不追溯撤回，最终首tau与名义版恰好一致。逐barUNKNOWN仍完整保留。

所有价格差仅描述源价格路径；**没有新成交、收益、费用、节约亏损、仓位或退出重算。**

## 2. 唯一规则、数学边界和时钟
完整协议hash：e8be017794c1c36f0d8c6b3ec256428defcb53bfc60d9666ec632c438839643e。协议先于本候选病例计算冻结，但原标签、旧ORB/O>J及粗质量结果已知，不是盲法、预注册样本外或独立测试。

W_k=Σamount/Σvolume，从供方当日首bar起累积。源标签09:50..14:50窗口内，Q=[W_k≥W_(k−1)]∧[C_k≥W_k]∧[v_k>0]，取首次真。没有高点突破、涨停特例、参数扫描或新样本。

当v_k>0且此前累计量正：
(A_k V_(k−1)−A_(k−1)V_k) = (a_k V_(k−1)−A_(k−1)v_k)。
所以第一式等价于本bar成交均价不低于此前W；第二式要求当前收盘不低于累计W。两条件不重复，但也非独立概率证据。判断只用交叉乘积符号，不以四舍五入后的W判断等号。物理前缀和未来扰动只证明程序依赖源前缀。

**供方time只被核实为17位行情时间，未认证是5分钟期末、已完整发布时点，亦未认证首09:35bar是否含集合竞价。** 因此tau是源标签下的条件时钟；W是“供方当日首bar起累计均价”，不是认证的全市场开盘起累计成本。next_bar_interval_start是按期末标签解释减5分钟的映射，不是实际最早买入时刻。真实实施仍必须认证已完成bar并取得available_at，实际下单严格晚于数据收到。

## 3. 原合同对照
NOACT14：旧ORB5许可/9无许可；本式12许可/2无许可。旧O>J没有同合同逐事件映射，14个全部UNKNOWN。不得把PRICE同股日借过来补齐。
PRICE19：旧ORB10许可/9无许可；本式18许可/1无许可。旧O>J原表精确映射18许可/1不许可，但旧不许可是浪潮，本式不许可是华电辽能，两组虽同为18并非同一集合。
旧O>J身份核验来自price_next_open_receipt_preflight_v1/FIXED19_INPUT_RESULT.json，按PRICE合同、sid、signal_day、entry_day和原open核实。原表若另有“8赢家”叙述，本次不借它给海能达增经济标签。

### NOACT固定14事件
旧净额只保留原首层标签。保护关系是下一bar描述open相对原冻结首层保护线，不能保证T+1保护或实际成交。其余未通过的病例无下一bar代理。

|病例/原买日|原首层净额|旧ORB tau|本式tau|下一bar open|相对原open|原保护关系|
|---|---:|---|---|---:|---:|---|
"""
    for c in rr:
        if c["contract"]=="NOACT_ORIGINAL_MOBILE":
            text+="|"+"/".join([c["name"],c["entry_day"]])+"|"+fmt(c["old_pnl"])+"|"+(c["original_ORB_signal_time"] or "无")+"|"+(c["quality_tau"] or "无")+"|"+fmt(c.get("quality_next_bar_raw_open"))+"|"+(fmt(c.get("quality_next_open_vs_old_open_pct"))+"%" if c.get("quality_tau") else "—")+"|"+c.get("quality_next_open_vs_original_floor","—")+"|\n"
    text+="""
### PRICE固定19事件
PRICE原冻结资料未提供该合同的初始保护线，因此保护关系UNKNOWN，不借NOACT线补齐。下表“盈利/失败”完全来自原tag，未给新候选贴经济标签。

|原病例|信号日→入场日|旧O>J|旧ORB tau|本式tau|下一bar open|相对原open|
|---|---|---|---|---|---:|---:|
"""
    for c in rr:
        if c["contract"]=="PRICE_FIXED_INPUT":
            text+="|"+c["name"]+"|"+c["signal_day"]+"→"+c["entry_day"]+"|"+c["old_O_gt_J_status"]+"|"+(c["original_ORB_signal_time"] or "无")+"|"+(c["quality_tau"] or "无")+"|"+fmt(c.get("quality_next_bar_raw_open"))+"|"+(fmt(c.get("quality_next_open_vs_old_open_pct"))+"%" if c.get("quality_tau") else "—")+"|\n"
    text+="""
## 4. 924、早根、重入及价格代价
- 924窗口固定点是9/25信号对应9/26，不新增9/24病例。电气风电09:50许可、3.24，较原open+1.25%；海能达09:50许可、6.04、+4.86%。海能达旧ORB10:00下一bar6.16、+6.94%，本式较早但仍追价，不能拿整段行情涨幅奖励这个价格。
- 江丰2025-12-15早根次日09:55、89.72、−0.32%；12/17确认点次日09:50、93.10、+2.26%；2026-01-05点次日09:50、106.39、+7.58%；1/15点次日14:20、128.16、+0.64%。前置根无需等E0/I，但不同点时仍有明显等待和价格代价，纯PRICE点无新收益标签。
- 永和重入10:45、28.24、+0.21%，游族重入10:25、8.25、−1.08%，杭钢重入09:50、4.45、−1.11%，银轮09:50、18.74、+0.75%。保留这些条件许可不代表已复现旧重入盈利。
- NOACT钢研下一bar较原open+3.65%，湖南白银+6.84%、银河+2.75%。有更便宜的路径也有更贵的路径，均不等于新收益增减。
- 固定病例共有五个首tau收盘低于前一bar收盘（新集、钢研、中国动力、浪潮、江丰2026-01-06）。全32股日评估窗647根名义Q为真，其中204根收盘低于前一bar。该式不是逐bar价格上升门，不据此补一项新条件。

## 5. 严格质量、UNKNOWN与涨跌停代理
每根raw以Decimal检查L×v≤a≤H×v，无容差、截断、平滑或量额修补。v=0且a=0是NO_NEW_FLOW；v=0而a≠0、缺bar、负量、无累计量、非法OHLC或额量越界均使当时起前缀UNKNOWN。更早许可保留，后续新Q仍UNKNOWN，不把UNKNOWN算失败。

|股日|首tau|首不相容标签|坏bar数|首tau保留|
|---|---|---|---:|---|
"""
    for q in qa:
        if q["incompatible_bar_count"]:
            c=next(c for c in rr if c["sid"]==q["sid"] and c["entry_day"]==q["day"])
            text+=f"|{c['name']}/{q['day']}|{c['quality_tau']}|{q['first_bad_time']}|{q['incompatible_bar_count']}|是，先信号后坏bar|\n"
    text+="""
严格41而非冻结前粗查40，多出电气风电2024-09-26 14:05：L=H=3.26，A/V=3.2600060277275467…，越高0.0000060277275…，不能用1e−5容差放过。该日11:15已首次坏、09:50已许可，多出的bar不改变首tau。所有不相容bar与吸收式UNKNOWN均在PER_BAR，未抹掉源名义结果。

全日分钟/日线OHLC、量额与原native不守恒仍只是事后审计。原供方聚合OHLC有14/32日不一致；即使某日全日相容，也不能补证完整逐笔、源发布时间或排队成交。程序没有把全日QA作为早盘门。

涨跌停只按原供方日线preclose/isST和一般规则计算，未认证逐票历史例外。福莱/歌尔原open恰等上限代理，原open×1.0005分别14.697345、24.95247，均越代理上限，因此原“开盘+5bp”是非法价格代理；不削回上限冒充成交。本式有首tau的30事件，下一bar open+5bp均未越上限代理，但“未越代理上限”仍不认证合法订单、卖盘或本人实际成交。原始下一bar open与所有标记均保留。

烽火平价跌停代理的事实尤其说明：OHLCVA内部完全相容并不意味着安全入口。其43.07与下限代理吻合，等号自动通过，不能解释为放量接受。新增SUPPLEMENT_BAR_LIMIT_CLOCK_AUDIT保存逐bar下限及时间认证未知，不改原核心输出。

## 6. 验证与未实施消费者
完成1536个物理截断前缀、1536个未来价格/量额/日期/复权标记扰动截点；每段已见输出一致，早许可不被未来坏bar撤回。另从raw逐次独立求和，以Decimal与Fraction精确有理数比较1536bar，核第一式交叉乘积恒等及两条件布尔完全一致。81个直接输入/协议hash及29个原native源hash均未变，原ORB78项旧封存hash全部相符。

14项初始合成测试加1项平价跌停代理测试，共15项：涨停/普通横盘/跌停平价等号可过、开板先降后恢复可在上限下方许可、极小正量可过、收盘低于前bar也可过、两条件互不蕴含、前坏UNKNOWN、后坏不撤早许可、0量0额无新增成交、0量正额UNKNOWN、无累计量UNKNOWN、缺bar前后时点。合成只验证既定式，不增加股票样本、不扫参数。

**本次仅计算首tau，不是完整盘中订单消费者。** 未来tau时若封板无可执行卖盘，必须用随后最新已完成bar重新核Q，不能把09:50许可永久挂到午后开板。新bar失效时需处理未成交单撤回和回报，部分成交保留同一首探身份，T+1不回转。这些生命周期均未模拟。
实际下单还须核真实现金、原保护、行业/单股预算、最小单位、dated费用、当时卖价/数量/时戳及官方价格范围；q只能缩小，不超过原冻结首探目标。ADD、持有退出、T+1不改。没有新经济运行。

## 7. 裁决和产物
不晋升。这一式恢复了不少ORB漏掉的旧赢家，却同时恢复更多旧失败；既能许可跌停平价，也能在极小新量下通过，没有证明新需求或首仓失败风险已分离。固定已看标签不能用于声称可泛化效果；数据和订单时钟亦不足。按冻结协议停在这里，不改窗、不加涨停特例、不再换一式补救。

- PROTOCOL.md：唯一冻结规则，未修改。
- analyze_fixed.py、PER_BAR.csv/json、FIXED_CASE_RESULTS.csv/json：固定33事件/32股日/1536bar，名义和质量两列。
- SOURCE_QA.csv/json、SOURCE_HASHES.json、SUMMARY.json：逐源质量与输入封存。
- verify_conditions.py、PREFIX_POISON_TESTS.json、SYNTHETIC_TESTS.json、INTERNAL_VERIFICATION.json：实现验证。
- SUPPLEMENT_BAR_LIMIT_CLOCK_AUDIT.csv、SUPPLEMENT_EVENT_LIMIT_CLOCK_AUDIT.json、SUPPLEMENTAL_CHECKS.json：下限退化、41/40严格差异及未认证时钟说明。
- FIELD_DICTIONARY.json：字段边界。SETUP_ERRORS.txt保留开始阶段未执行成功的命令错误；不存在覆盖原结果。
- 独立审计如有另见INDEPENDENT_*，最终文件hash由最终封存清单记录。

网络新抓取0，账户运行0，新经济计算0，参数搜索0，原文件改写0。
"""
    put("READOUT.md",text)
    print("READOUT and supplements written once.")
if __name__=="__main__":main()
