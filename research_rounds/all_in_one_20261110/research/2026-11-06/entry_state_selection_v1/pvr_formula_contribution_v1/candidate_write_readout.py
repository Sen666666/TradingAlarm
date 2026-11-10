"""Report arithmetic from sealed candidate outputs; no new formula calculations."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent
p=pd.read_csv(O/"candidate_FIXED_CASES_WITH_CONTEXT.csv")
d=pd.read_csv(O/"candidate_DAILY_CONTRIBUTIONS.csv")
d["weighted_delta"]=d.weighted_new-d.weighted_old
d["g_log_open_prev_close"]=d.n
def table(frame):
 cols=list(frame.columns);out=["| "+" | ".join(cols)+" |","|"+"|".join(["---"]*len(cols))+"|"]
 for row in frame.itertuples(index=False,name=None):
  out.append("| "+" | ".join(f"{x:.6f}" if isinstance(x,(float,np.floating)) and np.isfinite(x) else str(x) for x in row)+" |")
 return "\n".join(out)
intro="""# 唯一冻结候选：有界日内压力核，同22例一次计算

## 结论先行

只做了一种冻结公式、同22点/19股。18严格已知和4复权UNKNOWN不变。21点分下降、1点微升，主要来自量信用被纳入tanh后的压缩；这既不等于预测改善，也不等于少了买单。没有新资格、阈值、排序consumer、账户、影子PnL或新胜率。

同方82.016→76.872、南网82.000→77.015仍近同分；华电88.228→83.131仍高于海能达83.661→79.484。目前这批固定病例不提供稳定辨别亏赢的证据。量归属经济假设已有全样本负结果，不能用数学非等价把旧失败洗成新alpha。

## 精确冻结公式和范围

原r、前63|r|中位尺度s、前21成交额中位Aref、b=tanh(log(A/Aref))、有效观察/segment与预热都不改。
g或n=log(O/Cprev)，d=log(C/O)，q=r/s，v=tanh(d/s)。
唯一新日核 e†=tanh(q+0.5*b*v)；E†=Σ原21项归一0.9权重 e†；PVR†=50+50*tanh(2E†)。
同源O来自原signal，未造价、未再次复权。22例85日均有正有限O；r=n+d最大误差8.984e−16。因子变化四例保留UNKNOWN，机械算出新分不是同源认证升级。

归因桥仅定义 e_link=tanh(q+0.5*b*tanh(q))：
E†−E旧=Σw(e_link−e旧)+Σw(e†−e_link)。
第一项包括量作用移入压缩器及其函数形式变化，第二项才是相同边界下的body信息差。桥不是第二候选，不给它排名、consumer或绩效。最终score非线性，不能直接把E贡献加到分数上。

## 必须并列的既有负结果

来源：../intraday_overnight_attribution_v1/PROTOCOL.json 与 READOUT.md。
旧核 e*=k[m_t*d_t+m_(t−1)*n_t]，m=1+0.5|u|b，k=tanh(r/s)/r，r=0连续值1/s；沿用原21/.9聚合。
范围是2022至2026-05-15原PVR账户已有53,121条合法空仓MOBILE机会，796日、每臂14,185槽，637槽变化（4.49%）。不是新账户。
同日共同完整支持上的5/20/60日次开盘价格路径增量为+0.0058/−0.0703/−0.0693个百分点；20日2022–2025完整年份全部负。原1993个后验大根的早捕获715→711，既定162对中把赢家排更高仍86对。旧核预热历史还出现e*=−183989.45，失去有界性。
因此旧量归属假设未有预测增量。新式修复了有界性、固定前史/O/A下当前C单调性，却未凭此继承正面经济结论。旧式无界也不是其全部负经济结果的解释，因为极端预热值没有进入2022后评价窗。

标签不可串账：旧53121研究另列原PVR实际2026-01-15江丰/珂玛完整回合−1405.27/−1475.64元；本22例继承的是另一个original PRICE条件尺寸合同，1/15三股q0。本表继续原q0，不把不同账户/合同的实际局悄悄拼成当前标签，更不把前期涨幅当新交易赢家。

## 全22点，不按结果删选

原条件已结回合的盈亏只是既有身份背景，不是新式结果。2026 q0以及无exact原PRICE回合保持原标签。

"""
compact=p[["name","day","strict_known","original_score","new_score","E_compression_delta","E_body_delta","context_class"]].copy()
text=intro+table(compact)+"""

## 同方与南网：改变哪天、有没有可辨别差异

以下固定展示每个既定病例21日 |w*(e†−e旧)| 最大的3天，加最后3个观察日；是事后贡献排序，不是挑新病例或策略。重合日不重复。e旧/e†/e_link为日核，压缩ΔE和bodyΔE已经乘该日原权重；g/d是对数收益，b是金额映射。

"""
selected=[]
for sid,day in [("600100.SH","2022-01-04"),("688248.SH","2022-05-12"),("002583.SZ","2024-09-25"),("300666.SZ","2026-01-05")]:
 z=d[(d.sid==sid)&(d.signal_day==day)].copy()
 top=z.assign(abs_delta=z.weighted_delta.abs()).nlargest(3,"abs_delta").bar_day.tolist()
 last=z.sort_values("bar_day").tail(3).bar_day.tolist()
 show=z[z.bar_day.isin(top+last)].sort_values("bar_day").copy()
 show["display_reason"]=show.bar_day.map(lambda x:"TOP3+LAST3" if x in top and x in last else "TOP3" if x in top else "LAST3")
 selected.append(show)
 name=p[(p.sid==sid)&(p.day==day)].name.iloc[0]
 text+=f"### {name} {day}\n\n"
 v=show[["bar_day","display_reason","g_log_open_prev_close","d","b","e","e_new","e_link","weighted_compression_delta","weighted_body_delta"]].rename(columns={"g_log_open_prev_close":"g","e":"e旧","e_new":"e†","weighted_compression_delta":"压缩ΔE","weighted_body_delta":"bodyΔE"})
 text+=table(v)+"\n\n"
 if sid=="600100.SH":
  text+="同方前三变化日恰好末三日，g全0，因此新body信息相对桥基本为0。旧放量上涨日核大于1被压回1内，三天ΔE约−.018098/−.032398/−.022285，主要是函数压缩而非识别到额外失败事实。\n\n"
 elif sid=="688248.SH":
  text+="南网前三变化日也恰好末三日，三天均低开高收。body差分分别只加+.000122/+.000097/+.000816的E，远小于压缩扣减。全21日南网减同方：原E差−.000274280，新E差+.002016786；压缩差+.004600350，body差反而−.002309283。分差由−.016188变+.143116，仍几乎相同；轻微翻序主要来自压缩，不能声称新增body成功识别了亏赢。南网5/6低开反弹但缩量，body差分−.005657，解释了全窗body并非统一加分。\n\n"
 elif sid=="002583.SZ":
  text+="海能达9/20、23、24、25的O=C，day body为0；这种一字/无日内位移观察仍保留全部价格u，但金额不再给额外信用。9/25即使金额22.944倍，e由1.496259降至.999076、ΔE−.055827；9/23和9/24因去掉缩量扣减反而加+.012260/+.019143。21日净变化−.069730，其中压缩−.066937、body−.002793。最近5日E .526504→.459494，旧16日−.118191→−.120912。并未修复它排在华电以下，且明确减少原条件盈利例的强上行动量信用。日线O=C不证明实际能成交或纯粹无交易。\n\n"
 else:
  text+="江丰1/5真实低开? 本日g=+.009950，实际是高开且大阳body+.076427，不是低开。r/s=3.513511、b=.702301、v=.996020，old e1.348132→new .999118，ΔE−.039189几乎全是压缩；本日body修正约−1.53e−7，不能把降分说成日内承接失败。21日压缩−.055501、body+.005580；最近5日E从+.008207转−.028471，旧16日仍+.134569，最终E .106098、score60.453。新式没改旧记忆，反而在这次重启日削掉了爆发额信用；没有对应原PRICE完整局，不推断未来收益。\n\n"
text=text.replace("江丰1/5真实低开? 本日g=+.009950，实际是高开且大阳body+.076427，不是低开。","江丰1/5本日g=+.009950，是高开且大阳body+.076427。")
text+="""## 其他必须保留的方向与代价

- 浪潮70.130→68.668、游族72.048→71.316，原相对顺序未变。浪潮全窗压缩/body ΔE=−.016758/−.000464；游族+.000859/−.009866。不能把每个降低都称更准。
- 华电88.228→83.131，仍高于海能达79.484；华电10/28 r=.094642、g=.032553、body=.062089，e1.458911→.999950，单日ΔE约−.051535。是真上涨的额信用被压缩，不是新发现未来会亏。
- 江丰12/15是唯一升分点65.790→65.905，12/17几乎不变69.819→69.761。12/15 g=−.011748、body+.025244，old e .550790→.624949，当日bodyΔE+.005102；低开收复在这个核中确可区别，但这两点都无exact原PRICE完整回合。
- 江丰1/15 q0：91.771→88.027。1/13 g=−.010206、body+.008903、r=−.001303，old e−.065877→new+.020967，单日bodyΔE+.009031；小负收盘可被已发生的低开日内收复翻正，符合事前接受的语义。全窗body+.020514仍不能抵掉压缩−.124656。
- 珂玛1/15 q0：87.619→79.737。1/15 g=−.028477、body+.142645，old e1.220981→.999961，单日压缩ΔE−.024818、body几乎0；强上行已饱和。全窗压缩/body−.133407/−.013314。
- 金海通1/15 q0：93.159→87.447；全窗压缩/body−.107882/−.059702。1/15 g=+.028782、body−.020318、r仍+.008464，old e .374925→.086319，单日bodyΔE−.039755；1/12高开回落另给bodyΔE−.021198。新信息确实区别了开盘后回落，但q0不是新买入亏赢，不能把降分当择时成功。
- 原4复权UNKNOWN仍分列：歌尔87.190→80.999、永和72.950→64.279、力鼎74.483→69.487、福莱80.001→76.418。只机械归因，不拿它们解除同源限制或计算新胜率。

## 数学非等价与纯因果QA

- C/O同倍单位、A同倍单位：22例最大误差3.659e−12。全史与物理截t完全一致；污染未来C/O/A不影响t前输出，22例全部通过。
- 镜像C′=10000/C、O′=10000/O、A不变，score′=100−score，最大误差2.885e−12；不是对价格单位倒数的经济解释，只是对称性测试。
- b=0精确e†=u；无gap n=0不等于旧含量核。固定toy无gap old e−.740422、新−.732393。
- 同C/A/H/L而仅改变合法O的合成反例：原PVR两者都44.455866，新49.603988/43.960661。证明非原PVR函数，且H/L/close型方法输入保持相同；未重算DMI数值，不把输入同一冒充已跑DMI验证。
- 固定前史、O、A时，令x=log C：de†/dx=sech²(q+.5bv)*(1+.5*b*sech²(d/s))/s>0；对C的导数另除以C也>0。9组固定输入控制的所有当前C递增步均使新分递增。它避免“更高收盘反而降分”，但不是预测检验。
- |e†|<1，|E†|<1，score界为(1.798621,98.201379)，旧界约(.247262,99.752738)。分数尺度变了，不允许沿用旧阈值偷偷生成新准入。
- |q|>.5时量压力≤.5不能翻价格方向；强正冲击趋+1。无gap小q时new e/q→1+.5b、old→1：b=.882353、q=1e−6的比值为1.441176/1.000000，量影响由二阶变一阶。
- q=0且body非0可以有证据；低量阴body可给正调整。日金额含开盘集合竞价，不能称纯日内资金流或真实主动买卖方。
- O=C时body0，新核精确只有u；零amount、缺O、segment重置均新分UNKNOWN。缺O未偷偷重写原r/s/Aref观察钟。
- 21项bridge恒等式最大误差7.46e−17。s、每日tanh、21/.9记忆均沿旧制，前文的标准化丢失绝对幅度、上行饱和和旧信用滞后仍存在。
- 外加body与Sharpe备选只因数学性质在本轮病例计算前弃用，从未算病例新分。当前公式未据22点结果调参、重选或补门。

## 交付和结论

candidate_PROTOCOL.json、candidate_score_function.py先冻结；candidate_SOURCE_FREEZE.json在任何病例新分前记录代码和输入hash。一次计算后封存特征，再join原固定上下文。
核心CSV：candidate_POINT_FEATURES.csv、candidate_DAILY_CONTRIBUTIONS.csv、candidate_RAW_TRAJECTORIES.csv、candidate_FIXED_CASES_WITH_CONTEXT.csv、candidate_TARGETED_DAY_ATTRIBUTION.csv。
candidate_CAUSAL_QA.json、candidate_SYNTHETIC_QA.json与candidate_RESULT_SUMMARY.json保留精确验证。全部源未改，固定名单/UNKNOWN/q0/费后回合身份未改。

数学上有界、单调且非等价，只是一个解释清楚的公式改动；它没有解决同方/南网近同分，也没有倒转华电/海能达的原排序，且显著压缩海能达/江丰强上行额信用。与旧全53121量归属负结果并列，本轮没有足够证据支持预测增量或策略晋升。止于固定病例机制结论，不扩样、不运行经济、不追加新候选。
"""
pd.concat(selected,ignore_index=True).to_csv(O/"candidate_TARGETED_DAY_ATTRIBUTION.csv",index=False,float_format="%.17g")
with (O/"candidate_READOUT.md").open("x") as f:f.write(text)
hist=[R/"intraday_overnight_attribution_v1/PROTOCOL.json",R/"intraday_overnight_attribution_v1/READOUT.md"]
with (O/"candidate_HISTORY_CONTEXT_HASHES.json").open("x") as f:json.dump({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in hist},f,indent=2)
with (O/"candidate_FINAL_OUTPUT_HASHES.json").open("x") as f:json.dump({x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in O.glob("candidate_*") if x.is_file() and x.name!="candidate_FINAL_OUTPUT_HASHES.json"},f,indent=2)
print("Readout and targeted attribution saved.")
