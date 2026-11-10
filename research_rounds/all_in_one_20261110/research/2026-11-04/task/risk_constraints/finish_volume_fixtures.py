"""Explain existing paired pure-feature traces; no algorithm/account calls."""
from pathlib import Path
import json,hashlib,math
import pandas as pd

H=Path(__file__).resolve().parent;P=H/'volume_feature_fixtures_v1';V=P/'verification_fix_v2'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
    assert read(V/'COMPLETED.json')['passed'];first=read(P/'FAILED.json');done=read(V/'COMPLETED.json');total=first['wall_seconds']+done['wall_seconds'];assert total<180
    cases=[]
    choices=[('early_I_then_invalidation','000001.SZ','2022-01-05','real'),('neutral_I_then_invalidation','688001.SH','2022-01-17','neutral'),('same_anchor_low_amount_CP1','000001.SZ','2022-02-18',None),('same_continuing_I_same_CP1','688001.SH','2024-11-06',None),('strong_window_grade_is_not_holding_exit','300001.SZ','2025-10-15',None)]
    for kind,sid,date,which in choices:
        trace=pd.read_parquet(V/(sid+'_PAIRED_TRACE.parquet'));facts=pd.read_parquet(P/(sid+'_REAL/facts.parquet'));a=pd.read_parquet(P/(sid+'_REAL/CP1.parquet'));b=pd.read_parquet(V/(sid+'_NEUTRAL/CP1.parquet'))
        row=dict(kind=kind,sid=sid,decision_close=date,paired_saved_row=trace.loc[date].to_dict(),signal_close=facts.loc[date,'close'],raw_close=facts.loc[date,'raw_close'],factor=facts.loc[date,'factor'],
            REAL_CP1=a.loc[date,['anchor','scale','credit','displacement','m','receipt','candidate']].to_dict(),NEUTRAL_CP1=b.loc[date,['anchor','scale','credit','displacement','m','receipt','candidate','effective_amount_multiplier']].to_dict())
        if which:
            after=trace.loc[date:];off=after.index[after[which+'_i_target'].eq(0)]
            if len(off):row['first_subsequent_I_invalid']=dict(arm=which,day=str(off[0].date()),signal_close=facts.loc[off[0],'close'],raw_close=facts.loc[off[0],'raw_close'])
        if kind=='same_anchor_low_amount_CP1':
            assert row['REAL_CP1']['anchor']==row['NEUTRAL_CP1']['anchor'] and row['REAL_CP1']['scale']==row['NEUTRAL_CP1']['scale']
            row['same_frozen_displacement_credit_threshold']=math.sqrt(5)*float(row['REAL_CP1']['scale'])
        cases.append(row)
    save(V/'EXPLANATORY_SAVED_CASES.json',dict(cases=cases,selection='mechanism examples inside the three board/source-preselected fixtures, not PnL-selected, not a fourth fixture',
        future_price_context='later I invalid/close shown only as observed outcome context, never input to either signal; no trade/NAV/PnL calculated'))
    audit=H.parent/'independent_review/VOLUME_THREE_FIXTURE_COMPLETED_AUDIT.json';aa=read(audit)
    text=f'''# 三个量中性pure-feature样本收口

**薄装配可行，量确实会改变当前算法的转向、继续发证和PVR分数；但这轮没有证明量提高了信号质量或经济收益。** 只运行固定000001/300001/688001及其原银行/电网设备/专用设备行业，未加第四只、未全池导出、未构造Account/Runner，未生成PnL/NAV。累计计算{total:.3f}秒，低于180秒。

真量冷算使用原B5→G1→I及CP1/PVR函数，6序列全warm facts/I/CP1input/CP1逐值复现已有缓存。PVR逐值核原13/21/21个八字段点和每股968个已有策略日score；其余warm八字段没有旧表，未伪造控制。F1另由ar6用原函数独立冷算并与owner raw输出核同。F2行业保原eligible_prices，排除原3条坏几何，未把3034原行冒作3031有效观察。

第一轮在真量gate之后的比较器错误停下：NumPy标量断言不能直接比较pandas Series，不是行情或算法数值失配。原源码/freeze/FAILED保留。root另准v2仅把3处比较转严格array、SHA复用已落REAL、不重算真量门；没有tolerance或模型修改。中性6序列在2021Dec31/2024Sep23/2026Jun30物理截断与对应全表前缀一致；本轮**没有重算REAL物理前缀**。

## 量在具体判断中做了什么

1. **会把局部上冲更早认成I转上，但不保证是真趋势。** 平安银行2022Jan5，真量E0上event=1、中性=0，真量G1=2、中性=−3，I真量有效/有新买事件而中性未有效；双方S21仍下。真量I在Jan14失效，原因果信号close由53.028到50.493。它说明量会带来更积极的早期试错，不是“量总能排除假启动”。这些是信号价坐标与I状态，非交易盈亏。
2. **量也会阻止另一条后来失败的局部转上。** 华兴源创2022Jan17，中性S21向上、G1=3并新I，真量S21仍下/G1=−2且I无效；中性I于Jan25失效，信号close38.041→34.210。量在此保留了不同结构记忆，不能把所有差异都说成“放量早进”。这是相反方向的机制反例，仍不证明可实现避损。
3. **CP1金额抑制可以在相同价格、相同锚/尺度下延后继续发证。** 平安银行2022Feb18，双方anchor=3.918764864、scale=.012873598、价格displacement=.029654215；同一√5阈值约.028785。真量credit=.025719625而中性=.029654215，故仅中性发CP1候选。真量观测m=.85191，中性实际应用乘子1。这里能把金额信用作用与上游不同I重锚分开；尚不能说延后更好或更差。
4. **G1变化不等于成熟资金许可变化。** 华兴源创2024Nov6，真量G1=2/新I事件、中性G1=1/无新I事件，但两边I仍有效、CP1同日都发证，候选均29.623492888。真量m=1.24079使credit更大，但价格和信用门双方均足够，没改变这一保护候选。特锐德2025Oct15亦为真量G1=4、中性=−3，两边I仍有效且都没有新CP1；I-only模式并不以当前grade冷自动退出。这解释了为什么只数grade或信号日期改变不能回答持续趋势持有质量。

这些例子按已有paired trace解释路径，不是按新收益筛样本。不同历史重锚会产生“当日真量qeff更大，整条真量链却更晚转上”的情形；同anchor下的价格门性质不能扩成全路径先后保证。共同前缀在分叉前保持相同因果输出；后来的失效/价格只作展示上下文，不输入信号。

## 已验证与仍未回答

Neutral实际复用E0原numeric的EVENT_COLUMNS（不消费其旧target）、B4 joint=False后重建原grade/I、股票/行业原CP1 price_only=True、PVR纯函数内仅预测D归一使e=u。原真实价格/volume/amount文件、valid/source分段与执行量字段未改。CP1输出的原`m`仍是未消费的观测诊断，`effective_amount_multiplier=1`及逐前沿credit体现实际中性；不能读错为漏关量。PVR的归一D仅为纯函数信号输入，不是伪造实际成交额。

ACT仅核原纯hook与未来边界，**未计算3股票toy广度或完整1709中性recovery**，也没运行Q/排序资金竞争、账户或成本后效果。三个样本并非总体质量估计；未证明能降低L03/L04或Oct后303笔损耗，未证明保全原83/94赢家。现有证据仅说明必要对照可以不重写状态机地薄接，不能据此改纯价主线、调门或晋升策略。后续若需要完整量增量，仍须另定全母体特征/ACT及经济准入范围，本轮不自动延伸。

独审为PASS_WITH_SCOPE：`{audit}`核已保存中性CP1信用、qeff=q、e=u、共同价格/掩码及差异日期；18次中性物理prefix由owner实际计算，独审查其source/收据，不冒称又独立重算。独立PVR汇总公式的机器舍入边界亦保留，producer没有改数值。

证据：上层`TRUE_ALL_6_SERIES_GATE.json`和6组REAL；本目录`COMPLETED.json`、`TRUE_REFERENCE_REUSE.json`、`PHYSICAL_PREFIXES.json`、`DIFFERENCES.json`、`*_PAIRED_TRACE.parquet`、6组NEUTRAL及`EXPLANATORY_SAVED_CASES.json`。独立F1原函数结果在`ar6_native_feasibility/VOLUME_SOURCE_READINESS/F1_REAL_COLD/`。两版source/grant/freeze、失败和diff均保留。
'''
    (V/'READOUT.md').write_text(text)
    save(V/'FINAL_BINDING.json',dict(account_events=0,economic_outputs=0,first_run_seconds=first['wall_seconds'],verification_fix_seconds=done['wall_seconds'],total_compute_seconds=total,
        independent_audit_path=str(audit),independent_audit_sha256=sha(audit),readout_sha256=sha(V/'READOUT.md'),finisher_sha256=sha(Path(__file__)),
        references={str(p):sha(p) for p in [P/'EXECUTION_FREEZE.json',P/'FAILED.json',P/'TRUE_ALL_6_SERIES_GATE.json',V/'EXECUTION_FREEZE.json',V/'COMPLETED.json',V/'PHYSICAL_PREFIXES.json',V/'DIFFERENCES.json',V/'EXPLANATORY_SAVED_CASES.json']},
        limits='Only fixed3stock+3industry pure features; no ACTmacro rebuild/Q/funding/NAV/PnL or economicquality conclusion. REALfullwarm parity and NEUTRALphysicalprefix scopes separate.'))
    print('THREE_FIXTURE_READOUT_READY',total)
if __name__=='__main__':main()
