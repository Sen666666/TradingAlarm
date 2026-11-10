"""Six preselected first-entry OHLC mechanism cases. No accounts, rankings or strategy tests."""
from pathlib import Path
import hashlib,json,math
import numpy as np,pandas as pd
OUT=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/first_signal_ohlc_mechanism_v1")
MF=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
RM=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json")
EF=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv")
MODEL=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py")
CASES=[("600056.SH","2022-03-03","existing_CORE_big_winner"),("600056.SH","2022-03-30","existing_MOBILE_failure"),("300182.SZ","2022-01-04","existing_MOBILE_failure"),("002385.SZ","2022-03-04","existing_MOBILE_failure"),("600606.SH","2022-03-22","existing_MOBILE_winner"),("688582.SH","2024-07-29","existing_MOBILE_winner")]
mf={r["symbol"]:r for r in json.loads(MF.read_text())}
rm={r["series_id"]:r for r in json.loads(RM.read_text())["series"]}
entries=pd.read_csv(EF)
sources={MF,RM,EF,MODEL}
daily=[];summary=[];contexts=[];checks=[]
for sid,ds,label in CASES:
    t=pd.Timestamp(ds);ref=mf[sid]["refs"]
    f=pd.read_parquet(ref["facts"]);c=pd.read_parquet(ref["CP1"]);inp=pd.read_parquet(ref["CP1_input"])
    raw=pd.read_parquet(rm[sid]["raw"]["path"]).set_index("trade_date");raw.index=pd.to_datetime(raw.index)
    sources.update(map(Path,[ref["facts"],ref["CP1"],ref["CP1_input"],rm[sid]["raw"]["path"]]))
    anchor=float(c.loc[t,"anchor"])
    eligible=c.loc[:t]
    ad=eligible.loc[(eligible.next_anchor-anchor).abs().lt(1e-12)&eligible.reset_reason.notna()].index[-1]
    q=raw[["open","high","low","close"]].mul(f.factor,axis=0).reindex(f.index)
    close_error=float((q.close-f.close).abs().max())
    assert np.allclose(q.close.reindex(inp.index),f.close.reindex(inp.index),rtol=1e-12,atol=1e-12)
    missing_outside_cp=[str(x.date()) for x in q.index[q.close.isna()] if x not in inp.index]
    assert np.allclose(raw.amount.reindex(inp.index),inp.amount,rtol=0,atol=0)
    q["p_log"]=np.log(q.close)
    q["amount"]=inp.amount;q["factor"]=f.factor
    for k in ["open","high","low","close"]:q["raw_"+k]=raw[k].reindex(q.index)
    q["gap_log"]=np.log(q.open/q.close.shift())
    q["intraday_log"]=np.log(q.close/q.open)
    q["upper_rejection_log"]=np.log(q.high/q.close)
    q["range_log"]=np.log(q.high/q.low)
    assert np.allclose((q.gap_log+q.intraday_log).dropna(),np.log(q.close).diff().dropna(),rtol=1e-9,atol=1e-12)
    q=q.join(c.add_prefix("cp_"))
    q["i_buy"]=f.i_buy;q["i_target"]=f.i_target;q["g_acute_down"]=f.g_acute_down
    w=q.loc[ad:t].copy()
    F=anchor;Kcredit=0.;max_dd=0.;max_low_dd=0.;cum_rejection=0.
    for ix,(d,r) in enumerate(w.iterrows()):
        p=math.log(r.close)
        if ix==0:
            before=anchor;fresh=0.;dd=low_dd=0.;D=0.
            cum_rejection=0.
        else:
            before=F;fresh=max(p-before,0.)
            dd=max(before-p,0.);low_dd=max(before-math.log(r.low),0.)
            F=max(F,p);Kcredit=math.fsum((Kcredit,fresh*float(r.cp_m)));D=F-anchor
            max_dd=max(max_dd,dd);max_low_dd=max(max_low_dd,low_dd);cum_rejection+=r.upper_rejection_log
        w.loc[d,"window_priorfrontier_log"]=before
        w.loc[d,"window_delta_frontier_log"]=fresh
        w.loc[d,"window_D_log"]=D
        w.loc[d,"window_daily_credit_log"]=fresh*float(r.cp_m)
        w.loc[d,"window_Kcredit_log"]=Kcredit
        w.loc[d,"window_close_drawdown_log"]=dd
        w.loc[d,"window_low_drawdown_log"]=low_dd
        w.loc[d,"window_max_close_drawdown_log"]=max_dd
        w.loc[d,"window_max_low_drawdown_log"]=max_low_dd
        w.loc[d,"window_cumulative_upper_rejection_log"]=cum_rejection
        w.loc[d,"anchor_basis_row"]=ix==0
    assert math.isclose(float(w.iloc[-1].window_D_log),float(c.loc[t,"displacement"]),rel_tol=1e-11,abs_tol=1e-12)
    assert math.isclose(Kcredit,float(c.loc[t,"credit"]),rel_tol=1e-11,abs_tol=1e-12)
    assert bool(c.loc[t,"receipt"])
    w.insert(0,"date",w.index.strftime("%Y-%m-%d"));w.insert(0,"case_signal_day",ds);w.insert(0,"sid",sid)
    daily.append(w.reset_index(drop=True))
    z=w.iloc[-1];a=float(c.loc[t,"scale"]);threshold=math.sqrt(5)*a
    old=entries.loc[(entries.sid==sid)&(entries.signal_day==ds)&(entries.account=="PVR")].iloc[0]
    Fprev=z.window_priorfrontier_log;delta=z.window_delta_frontier_log
    gap_extension=max(math.log(z.open)-Fprev,0.)
    retained_gap=min(delta,gap_extension)
    local={
      "sid":sid,"signal_day":ds,"label_source":"PVR original first-entry row; not new outcome computation","case_label":label,
      "first_kind":old.first_kind,"first_reason":old.first_reason,"entry_day":old.entry_day,"original_round_pnl":old.round_pnl,
      "original_market_regime":old.market_regime,"original_market_breadth20":old.market_breadth20,"original_industry_breadth20":old.industry_breadth20,
      "anchor_day":str(ad.date()),"anchor_reason":str(c.loc[ad,"reset_reason"]),"anchor_log":anchor,"anchor_native_close":math.exp(anchor),
      "anchor_raw_close":float(raw.loc[ad,"close"]),"frozen_scale":a,"threshold_sqrt5_scale":threshold,"bars_after_anchor":len(w)-1,
      "phase":str(c.loc[t,"phase"]),"i_buy":bool(f.loc[t,"i_buy"]),"receipt":True,
      "D":float(c.loc[t,"displacement"]),"Kcredit":float(c.loc[t,"credit"]),
      "D_over_threshold":float(c.loc[t,"displacement"])/threshold,"Kcredit_over_threshold":float(c.loc[t,"credit"])/threshold,
      "r_over_s":float(c.loc[t,"r"])/float(c.loc[t,"s"]),"amount_over_B":float(inp.loc[t,"amount"])/float(c.loc[t,"B"]),
      "current_close_drawdown_log":float(z.window_close_drawdown_log),"max_close_drawdown_since_anchor_log":float(z.window_max_close_drawdown_log),
      "current_low_drawdown_log":float(z.window_low_drawdown_log),"max_low_drawdown_since_anchor_log":float(z.window_max_low_drawdown_log),
      "retained_open_frontier_extension_log":retained_gap,"retained_intraday_frontier_extension_log":delta-retained_gap,
      "retained_open_share_of_fresh":retained_gap/delta,"upper_rejection_over_fresh":float(z.upper_rejection_log)/delta,
      "upper_rejection_over_s":float(z.upper_rejection_log)/float(z.cp_s)}
    for k in ["open","high","low","close","raw_open","raw_high","raw_low","raw_close","factor","amount","gap_log","intraday_log","upper_rejection_log","range_log","cp_r","cp_s","cp_z","cp_m"]:
      local[k]=float(z[k])
    summary.append(local)
    ctx=q.loc[:t].tail(12).copy();ctx.insert(0,"date",ctx.index.strftime("%Y-%m-%d"));ctx.insert(0,"case_signal_day",ds);ctx.insert(0,"sid",sid)
    contexts.append(ctx.reset_index(drop=True))
    checks.append({"sid":sid,"signal_day":ds,"native_close_max_abs_error":close_error,"coordinate_check_scope":"all original CP1_input indexed observations","facts_missing_raw_outside_CP_input":missing_outside_cp,"amount_exact":True,"OHLC_valid":bool((w.high>=w[["open","close","low"]].max(axis=1)).all() and (w.low<=w[["open","close","high"]].min(axis=1)).all()),"gap_plus_intraday_equals_r":True,"manual_D_equals_original":True,"manual_Kcredit_equals_original":True,"local_signal_close_drawdown_zero":float(z.window_close_drawdown_log)==0.0})
OUT.mkdir(parents=True,exist_ok=True)
pd.concat(daily,ignore_index=True).to_csv(OUT/"ANCHOR_TO_SIGNAL_DAILY.csv",index=False,float_format="%.15g")
pd.DataFrame(summary).to_csv(OUT/"SIX_SIGNAL_SUMMARY.csv",index=False,float_format="%.15g")
pd.concat(contexts,ignore_index=True).to_csv(OUT/"PRE_SIGNAL_CONTEXT.csv",index=False,float_format="%.15g")
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
hashes={str(p):digest(p) for p in sorted(sources)}
(OUT/"SOURCE_SHA256.json").write_text(json.dumps(hashes,indent=2,ensure_ascii=False)+"\n")
(OUT/"CHECKS.json").write_text(json.dumps({"cases":checks,"all_checks_pass":all(all(v for k,v in x.items() if isinstance(v,bool)) for x in checks),"new_accounts":0,"account_backtests":0,"ranking_tests":0,"parameter_grid":0,"original_writes":0,"cases_preselected_by_parent":True},indent=2,ensure_ascii=False)+"\n")
report="""# 首次建仓信号 OHLC：六个预指定病例的机制核对

## 结论先行

这六个病例说明原 CP1 确实不读取同日开高低价，遗漏可以精确定义；但不说明 OHLC 足以把失败与赢家分开。六例是事前指定的既有病例，不是样本总体，不做胜率、覆盖率、排序或账户结论。

- 300182 的失败信号由高开贡献全部新收盘前沿，盘中反而回落；002385 的失败信号有明显上影。这些是原 CP1 不可见的直接信息。
- 600056 3/30 失败却低开后大涨且收最高价，上影为零；3/3 大赢家也收最高价。不存在“所有失败都是跳空／冲高回落”。
- 所有 fresh CP1 发证日必须创新收盘前沿，故相对“当前 CP 的前收盘 frontier”的信号收盘回撤必为零。这个指标在这些信号上没有横截面区分力，必须使用历史最大回撤、当日低点或更早未清空的参照。
- 688582 赢家和 300182 失败都经过 native-down 降锚，均 i_buy=False；前者发证时仍未收复旧 CP frontier。不能把反弹、弱市或未收复旧高等同失败。
- 002385 失败和 688582 赢家的信号上影/fresh推进分别约 1.596 与 1.521，几乎一样。只换成某个单比值也没有得到有效规则。

## 原算法与单位

p=log(native adjusted close)，r=p-p_prev。s=1.4826×前63个绝对对数收益的中位数，原实现先shift，且截底1e-8。z=max(s,log(1.001))。B=前21个amount中位数。m=1+0.5×abs(tanh(r/s))×tanh(log(amount/B))。

CP 在锚点冻结 scale。每日 fresh=max(p-frontier_prev,0)，frontier=max(frontier_prev,p)；D=frontier-anchor；Kcredit=sum(fresh×m)。fresh>0 且 D、Kcredit 均≥sqrt(5)×scale 时发证，随后锚点、frontier、credit、scale重置。这里 Kcredit 指累计信用，避免与原源码保护距离常数 K=sqrt(21) 混淆。

原程序的输入中没有 open/high/low。保持 close、amount、E0事实、source segment 不变而改变合法 OHLC，所有 CP 状态严格不变。这是信息盲区的数学事实，不是预测优势的证明。

OHLC 均使用该行原 facts.factor×指定 raw manifest 的同日未复权价格。原 CP1_input 全部日期的重建收盘与 native facts 最大误差≤2.85e-14，amount逐行精确一致。688582 的 facts 另有 2026-10-23/26/27 三行，原 raw manifest 未覆盖且不在 CP1_input；这些日期未参与坐标验证或本次2024病例。未使用 canonical5517 的价格。原旧市场状态标签从 ALL_FIRST_ENTRIES 只读引用，没有把该文件中的其它价格混入计算。所有log量无量纲，下表百分数是100×log，不是普通简单收益率。

当日 gap=log(O/Cprev)，intraday=log(C/O)，upper_rejection=log(H/C)，range=log(H/L)，恒有gap+intraday=r。
close_drawdown=max(prior close frontier-log(C),0)；low_drawdown=max(prior close frontier-log(L),0)。最大回撤只在真实CP锚日收盘之后累计，锚日盘中低点不能算入“锚后”。后者是“已知先前收盘峰值到当日低点”的损伤，不是日内高低先后已知的真实最大回撤；日线OHLC不能确定H和L顺序。

## 六例信号对照

"""
rows=[]
header="| 股票与信号日 | 原角色/结果 | gap | 日内 | 上影 | 振幅 | 锚后最大收盘DD | 锚后最大低点DD | D/阈值 | 信用/阈值 |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
rows.append(header)
for x in summary:
    vals=[x["sid"]+" "+x["signal_day"],x["first_kind"]+"/"+("赢家" if "winner" in x["case_label"] else "失败")]
    vals += [f'{100*x[k]:.4f}%' for k in ["gap_log","intraday_log","upper_rejection_log","range_log","max_close_drawdown_since_anchor_log","max_low_drawdown_since_anchor_log"]]
    vals += [f'{x["D_over_threshold"]:.6f}',f'{x["Kcredit_over_threshold"]:.6f}']
    rows.append("| "+" | ".join(vals)+" |")
report+="\n".join(rows)
report+="""

全部当前信号close_drawdown=0。600056 3/3指PVR账本原CORE（signal 3/3、entry 3/4）；同日E31是MOBILE，不混为同一角色。所有结果只是旧局的既有标签；没有重做执行可行性核查，且各日期不是同日竞争集合。

## 可手算完整例：002385 2022-03-04

实际CP锚日为2/28的lower_anchor，不是2/21的start。原native因子5.080314101556109在该窗口不变。锚收盘42.065000760885，p0=3.739216059091080；冻结scale=0.026387348372480，阈值sqrt(5)×scale=0.059003904706833。

逐日D/K的0行定义为锚日收盘之后，所以锚日更早日内波动不进入本次信用。完整高精度数据在 ANCHOR_TO_SIGNAL_DAILY.csv。
"""
df=pd.concat(daily,ignore_index=True);w=df[(df.sid=="002385.SZ")&(df.case_signal_day=="2022-03-04")]
cols=["date","open","high","low","close","amount","cp_r","cp_s","cp_z","cp_m","window_delta_frontier_log","window_D_log","window_daily_credit_log","window_Kcredit_log","window_close_drawdown_log"]
report+="\n"+w[cols].to_csv(index=False,float_format="%.10f")
report+="""
3/1 fresh=log(8.46/8.28)=0.021506205221，乘m=1.0077360274得信用0.0216725778。
3/2 fresh=log(8.56/8.46)=0.0117510165，新增0.0123347711，累计D=0.0332572218、信用0.0340073489。
3/3收盘8.49低于原frontier8.56，fresh=0，D与信用完全不变；当日收盘回撤0.0082111898、低点相对priorfrontier回撤0.0200596697。原CP没有扣款。
3/4 close-to-close r=log(8.79/8.49)=0.0347257114，但fresh只有log(8.79/8.56)=0.0265145215，不重复给恢复旧高的0.0082111898记新信用。fresh×m=0.0330431701，累计信用0.0670505190；D=log(8.79/8.28)=0.0597717433。两者跨阈值，发证并消费。
因此原CP并非所有反弹都重复加分：它只给新frontier加分。但信用不扣普通回撤；同日高9.17到收8.79的上影log(9.17/8.79)=0.0423225746没有影响。信号日当日低8.34相对旧frontier8.56的损伤0.0260369738也没有影响。

## 其它真实路径与反例

- 300182：12/27 native-down从此前frontier 6.58重新锚在5.94，随后5个观察收盘5.98→6.04→6.30→6.33→6.54，累计D=0.0962280321、信用=0.1081489244。1/4 open6.60、high6.77、low6.36、close6.54；gap=0.0417694129、intraday=−0.0091324836。新收盘前沿0.0326369293全部由开盘已有的跃升保留，盘中没有新增前沿。但该日只比旧6.58低0.61%左右，随后涨跌不能改写原局已知亏损。
- 600606：3/17锚3.98，3/18到4.10，3/21回4.08，信用保持0.0324094237；3/22到4.32，fresh=log(4.32/4.10)=0.0522684285，新增信用0.0718295272，累计0.1042389508。它也有中途回撤，不能要求所有成功路径没有回撤。
- 688582：7/24 native-down锚27.38，之后28.30→28.79→29.05。7/26信用已0.0552618183，几乎过阈值但D仍不足；7/29信用0.0644230738、D0.0592056634才双过线。当前信号上影0.0136754268并非零，锚后最大priorclose-to-low回撤0.0246837787，接近002385失败的0.0260369738。旧frontier7/19的29.72仍未收复，但既有原局盈利。
- 600056大赢家：3/3实际CP锚是3/2上一张receipt消费后close12.21，不应把3/2上一周期的信用0.1522286704计入3/3。本周期只有一条fresh=log(13.43/12.21)=0.0952357224、m1.4989328477、信用0.1427519526。
- 600056终端失败：3/25 E0_invalid清账，3/29 start锚36.58；3/30 open35.98、high40.24、low35.48、close40.24，低开后收最高价。D0.0953598828、信用0.1019459592。它不只是“仍未越旧高”的反弹，收盘也超过了3/21旧峰36.59。仅保存旧高不足以识别这一失败。

## 可直接计算、尚未验证的研究接口

可以先把gap、intraday、上影、当日低点损伤、锚后历史最大回撤作为独立信息记录，不必先拍一个加权总分、阈值或换账户。

若要精确区分新的frontier来自开盘还是盘中，可按既有frontier F定义：
Delta=max(log(C)-F,0)
retained_open=min(Delta,max(log(O)-F,0))
retained_intraday=Delta-retained_open
rejected_extension=max(log(H)-max(log(C),F),0)
这些都是纯定义，没有调参；信号日rejected_extension=upper_rejection。注意retained_open是“开盘已具备且收盘仍保留的新前沿”，不是成交量、主动资金或因果归因。

该分解会暴露300182本日推进全部来自高开；却不会识别600056 3/30失败，因为后者全部来自盘中推进、上影为零。惩罚gap或奖励日内推进不能被这六例证明有效。若要修改信用，必须明确新增负项的状态何时清零，以及为什么不会因receipt、lower_anchor或E0_invalid抹去要保留的损伤；同时控制与已有r、fresh、s、m的重复计量。这里不冻结任何惩罚系数、不生成候选排名。

希望覆盖大量失败的可证伪路径应在全部预先定义首仓信号上先量化：有多少失败属于高开后回落/显著上影/低点损伤/重置遗忘这几类；同等市况及波动尺度的赢家是否也同样普遍；区分CORE与MOBILE、SEEK与UP、弱市/改善/支持阶段，并保留不能被这些信息解释的600056终端失败。没有总体分布证据前，不给出可提升胜率或可覆盖多少失败的数字。

## 文件与审计

- ANCHOR_TO_SIGNAL_DAILY.csv：23行，六个真实CP锚至信号日；原CP字段以cp_开头，手工本周期账本以window_开头。锚日可能属于前一张receipt，其cp_*仍忠实保留旧周期数据，window_D/window_Kcredit从0开始。
- SIX_SIGNAL_SUMMARY.csv：六例native OHLC、原r/s/z/m、冻结尺度、D/信用、分解及原市场标签。
- PRE_SIGNAL_CONTEXT.csv：每例最近12观察，仅帮助查看重置前背景，不把12定义成新参数。
- CHECKS.json、SOURCE_SHA256.json：价格与金额坐标、逐日分解、D/信用复算及只读来源哈希。

无新账户、无资金回测、无排序检验、无阈值/参数网格、不写原shared/cache/CE封存目录。
"""
(OUT/"REPORT.md").write_text(report)

# Optional arithmetic requested by parent: fixed original windows only, no new CP state.
arithmetic=[];arithmetic_summary=[]
for x in summary:
    w=df[(df.sid==x["sid"])&(df.case_signal_day==x["signal_day"])].copy()
    w["m_reconstructed"]=1+.5*np.abs(np.tanh(w.cp_r/w.cp_s))*np.tanh(np.log(w.amount/w.cp_B))
    assert np.allclose(w.m_reconstructed,w.cp_m,atol=1e-12,rtol=1e-12)
    w["m_body"]=1+.5*np.tanh(w.intraday_log/w.cp_s)*np.tanh(np.log(w.amount/w.cp_B))
    w["A_body_daily_credit"]=w.window_delta_frontier_log*w.m_body
    w["B_signed_daily_credit"]=w.cp_m*w.cp_r
    w.loc[w.anchor_basis_row.astype(bool),"B_signed_daily_credit"]=0.
    w["A_body_K"]=w.A_body_daily_credit.cumsum()
    w["B_signed_K"]=w.B_signed_daily_credit.cumsum()
    y=w.iloc[-1];th=x["threshold_sqrt5_scale"]
    arithmetic.append(w)
    arithmetic_summary.append({"sid":x["sid"],"signal_day":x["signal_day"],"anchor_day":x["anchor_day"],"original_D":x["D"],"threshold":th,"original_K":x["Kcredit"],"A_body_K":float(y.A_body_K),"A_ratio":float(y.A_body_K)/th,"B_signed_K":float(y.B_signed_K),"B_ratio":float(y.B_signed_K)/th,"original_D_pass":x["D"]>=th,"A_credit_pass":float(y.A_body_K)>=th,"B_credit_pass":float(y.B_signed_K)>=th,"original_window_only":True})
ardf=pd.concat(arithmetic,ignore_index=True)
ardf.to_csv(OUT/"ARITHMETIC_DAILY.csv",index=False,float_format="%.15g")
ars=pd.DataFrame(arithmetic_summary)
ars.to_csv(OUT/"ARITHMETIC_SUMMARY.csv",index=False,float_format="%.15g")
report+="\n\n## 追加：仅在原形成窗的A/B算术，不是新策略\n\nA沿用原fresh，只改信用乘子：m_body=1+0.5×tanh(log(C/O)/s)×tanh(log(amount/B))，A_K=Σfresh×m_body。\nB沿用原m，B_K=Σm×r，逐日带符号且不截断。二者都从原锚日收盘以后开始，使用原冻结阈值；没有重新计算发证日、降锚、reset或后续状态。因此这里只比较原信号日固定窗口的账面数值，不能当作新CP实际事件。\n\n"+ars.to_csv(index=False,float_format="%.12f")
report+="\n六例A、B仍全部通过原门槛。300182锚后五个收盘逐日创新高，所以B与原K完全相同；600056两例仅一个观察，B也完全相同。B并不保证小于原信用：002385、600606反而增加，因为恢复旧高当天的m大于回撤当天的m，形成正的加权往返差。m恒为1时，B按望远镜求和等于p_t−p_anchor；在fresh发证日等于D，所以不凭空处罚一次下跌再等幅恢复。\n\nm_body也不是始终降低信用：若成交额低于B且body为负，两个tanh都负，其乘积为正，m_body反而高于1。该符号结构应明确解释，不能笼统称为“阴线扣分”。\n\n### 300182逐日完整手算数据\n\n原native因子10.090791938232751，本窗不变；真实锚为2021-12-27收盘5.94（native59.939304113103），冻结scale=0.032115335128约，阈值0.071812072465895。锚日的r/m/O/C仅展示背景，不进入当前窗累计。amount和B均人民币元。\n\n"
aw=ardf[(ardf.sid=="300182.SZ")&(ardf.case_signal_day=="2022-01-04")]
acols=["date","p_log","raw_open","raw_high","raw_low","raw_close","open","close","amount","cp_B","cp_r","cp_s","cp_z","cp_m","window_delta_frontier_log","window_daily_credit_log","window_D_log","window_Kcredit_log","intraday_log","m_body","A_body_daily_credit","A_body_K","B_signed_daily_credit","B_signed_K"]
report+=aw[acols].to_csv(index=False,float_format="%.12f")
report+="\n1/4单日原m=1.155139142326、m_body=0.942915017525，新增信用从0.037700194535降为0.030773850775，但A累计0.101554362780仍是阈值1.414168倍；原/B累计0.108148924382是1.505999倍。这证明当前有界乘子修改对这一失败例不会改变原窗口通过结果，并未验证新事件或后续收益。\n"
(OUT/"REPORT.md").write_text(report)
(OUT/"ATTEMPT_LOG.json").write_text(json.dumps({"initial_validation_attempt":"Assertion failed when requiring raw OHLC for all facts dates; 688582 has three trailing facts dates outside original raw and CP1_input coverage.","resolution":"Validate all original CP1_input indexed observations and explicitly disclose three excluded 2026 facts dates; all six historical case windows remain complete.","excluded_dates":["2026-10-23","2026-10-26","2026-10-27"],"denied_actions":0},indent=2)+"\n")

(OUT/"OUTPUT_SHA256.json").write_text(json.dumps({p.name:digest(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="OUTPUT_SHA256.json"},indent=2)+"\n")
print(json.dumps({"output_dir":str(OUT),"daily_rows":len(df),"summary_rows":len(summary),"checks":checks,"files":[p.name for p in sorted(OUT.iterdir())]},ensure_ascii=False))
