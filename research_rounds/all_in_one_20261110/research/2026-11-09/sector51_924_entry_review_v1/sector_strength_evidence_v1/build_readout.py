from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
p=O/'build_strength.py';s=p.read_text();s=s.replace('half_saturated=(n.eq(N)&K.eq(N))','full_pool_saturated=(n.eq(N)&K.eq(N)),known_saturated=(K.gt(0)&n.eq(K))');p.write_text(s)
for f in ['ALL50_DAILY_EVIDENCE.csv','TARGET50_EVIDENCE.csv']:
 a=pd.read_csv(O/f)
 if 'm3_half_saturated' in a:a=a.rename(columns={'m3_half_saturated':'m3_full_pool_saturated'})
 a['m3_known_saturated']=a.m3_K.gt(0)&a.m3_n.eq(a.m3_K)
 a.to_csv(O/f,index=False,float_format='%.12g')
a=pd.read_csv(O/'ALL50_DAILY_EVIDENCE.csv').sort_values(['sector51','day']);t=pd.read_csv(O/'TARGET50_EVIDENCE.csv');targetdays=t.day.unique()
a['rs5_previous_day_pp']=a.groupby('sector51').rs5_median_pp.shift();a['rs5_change_1day_pp']=a.rs5_median_pp-a.rs5_previous_day_pp
a['candidate_common_Q']=a.m3_state.eq(1)&a.m3_half_streak.ge(2)
a['candidate_fast_promotion_F']=a.candidate_common_Q&a.rs5_median_pp.gt(0)&a.rs5_change_1day_pp.gt(0)&a.return5_median.gt(0)&(2*a.breakout20_count>=a.m3_N)
a['candidate_slow_support_S']=a.candidate_common_Q&a.rs10_median_pp.gt(0)&a.rs20_median_pp.gt(0)&a.return10_median.gt(0)
a['candidate_relative_cooling']=a.rs5_and10_negative_streak.ge(2)
a['no_new_add_if_M3_unknown']=a.m3_state.eq(-1)
cols=['day','sector51','m3_N','m3_K','m3_n','m3_U','m3_state','m3_true_streak','m3_half_streak','m3_diff','m3_known_saturated','rs5_median_pp','rs5_previous_day_pp','rs5_change_1day_pp','rs10_median_pp','rs20_median_pp','rs10_and20_positive_streak','rs5_and10_negative_streak','return5_median','return10_median','breakout20_K','breakout20_count','candidate_common_Q','candidate_fast_promotion_F','candidate_slow_support_S','candidate_relative_cooling','no_new_add_if_M3_unknown']
a[a.day.isin(targetdays)][cols].sort_values(['day','sector51']).to_csv(O/'CANDIDATE_DIAGNOSTICS_NOT_STRATEGY.csv',index=False,float_format='%.12g')
focus=['证券保险','银行','软件与IT服务','半导体','电子元件材料','动力电池']
def table(df):
 cols=list(df.columns);out=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
 for row in df.itertuples(index=False,name=None):out.append('| '+' | '.join(str(x) for x in row)+' |')
 return '\n'.join(out)
def pct(x):return f'{100*x:+.2f}%'
def pp(x):return f'{x:+.2f}'
lines=['# 板块持续主线：事前日线证据 v1','',
'## 先说结论','',
'1. 初次广度确认和持续主线增配应分层。9/18 只有证券保险 M3=TRUE；9/19 地产加入；9/23 已有 21 类 TRUE；9/26 所有 48 个 N≥3 的行业都 TRUE，继续把 TRUE 当等价配置许可证会失去相对强弱区分。社会服务 N=1、综合企业 N=2 永远达不到当前 M3 的 n≥3 条件，不能把其 FALSE 解释为价格弱。',
'2. 早期证券保险、地产、软件、计算机设备确有当时可见证据，不能为了后来科技赢家而删除这些早期候选。9/23 地产 RS10/20=+6.91/+7.72 pp，双正连续9日；软件 +4.26/+6.91 pp，双正13日；证券保险 +4.17/+5.07 pp，双正11日；计算机设备 +3.96/+5.17 pp，双正4日。',
'3. 快新主线不能被长窗唯一门槛挡住。半导体9/26首次 TRUE=94/126，但 RS5/10/20=-0.30/-2.62/-3.56 pp；9/27 RS5 已转 +1.94 pp，5日中位收益16.34%，20日收盘突破比例从39.42%升到87.50%，半数广度连续2日，短期转强已经可见。RS10/20仍为-0.84/-1.45 pp是过去弱势的残留，不等于仍未启动。9/30 RS5/10/20升到+10.66/+6.18/+3.19 pp。若硬等10/20双正连续2日，最快到10/8收盘，下一可执行时点更晚。',
'4. 动力电池9/27短期RS5=+6.72 pp、RS10/20=+0.42/+6.90 pp；元件9/27的RS5/10/20仍为-0.91/-2.77/-1.68 pp，9/30短期RS5才转+0.90 pp，10/8长窗双正第1日。它们不是同一天、同成熟度。',
'5. 银行与证券保险应分开：9/26银行39/39全TRUE，但RS20仍-4.04 pp；9/27 RS5转-2.15 pp，9/30 RS5/10/20=-9.85/-6.81/-9.45 pp。10/8证券保险已知51/51全TRUE，三日diff=0，RS10/20仍+13.86/+17.94 pp，属于已知广度饱和而非退潮。',
'6. 当时真实强者不限于上述六类。地产9/26 RS10/20=+12.67/+12.95 pp；医疗服务9/26首次半数确认、双正第1日，9/27继续扩散，10/8 RS10/20=+23.39/+20.73 pp。白酒、旅游、美容等也应如实保留，不按未来收益筛掉。',
'',
'## 样本、单位与可知边界','',
'- 固定现存池1692只、50类；17只未分类排除。池与行业映射均非 PIT，属于当前固定池内的历史可知价格诊断，不是完整历史可投资宇宙，也不能消除存活、上市和分类回填偏差。价格文件为后来收集/构造的缓存，不宣称已证明历史当日数据可得性。',
'- 行业 N 固定；M3_K 是 M3/common-known 的可知数，M3_U=N-K；每个收益窗口单列 returnh_K/U。两者不是同一知识集合，不可互换。例10/8软件M3_K=64/67，但价格完整窗口K=65/67；半导体M3_K=103/126，价格K=104/126。',
'- 所有 *_pp 列是真实百分点：2.2373表示2.2373个百分点。原始 return/mean/median/fraction/drawdown 列均为小数比例，0.10=10%。单位修订同步 builder、数据与 QA；不改变任何符号、排序或结论。',
'- h日收益=调整收盘价(t)/调整收盘价(t-h)-1，要求共同市场交易日 t-h…t 共h+1根全部存在、完整有效OHLCV、同source_kind/source_path/segment。禁止跳过缺报/停牌后取最后h个有效观察，缺失不填0。所有计算均在先截断到10/8的源数据上、仅用过去窗口完成。',
'- 采用同一完整窗口成员的终点收益中位数和算术均值，不构造不断换成员的行业指数，因此没有成员进出制造指数涨跌。市场基准是在全1692中采用完全相同窗口规则后留下的股票收益中位数/均值，不是行业等权，不是沪深指数。RSmedian=行业中位数-市场中位数；RSmean=行业均值-市场均值。每一行均给市场K/U。',
'- 目标日价格完整样本K为1599至1608，不把其余84至93只的收益猜为零；目标逐股未知均来自共同日期缺失。本研究未核实每一缺失是停牌、上市前还是源覆盖不全，不能一概称停牌。',
'- 5/10/20日是一周/两周/一月的诊断尺度，不是通过未来涨幅选择的最优参数。20日突破指当日收盘严格超过此前20日收盘最大值；回撤是当日收盘相对含当日共21日最大收盘的距离。二者仅在同一完整21根集合上算。',
'- M3持续天数从2022-01-04完整信号历史起算；RS持续天数从2024-01-02起算，开头可能左删失。本文9月目标的所述持续段均在观察区间内重新开始。T/F/U分别为1/0/-1；UNKNOWN不是FALSE。',
'',
'## 六类逐日证据','',
'RS列为5/10/20日中位收益相对市场的百分点；收益列为5/10/20日绝对中位收益。突破比例分母为完整20日窗口价格K，不是行业N。',
'']
for sec in focus:
 b=t[t.sector51.eq(sec)].copy();rows=[]
 for r in b.itertuples():
  rows.append({'日期':r.day,'M3 n/K/N':f'{r.m3_n}/{r.m3_K}/{r.m3_N}','状态/TRUE天/半数天':f'{r.m3_state}/{r.m3_true_streak}/{r.m3_half_streak}','三日净扩散':r.m3_diff,'收益5/10/20': '/'.join(pct(getattr(r,f'return{h}_median')) for h in [5,10,20]),'RS5/10/20 pp':'/'.join(pp(getattr(r,f'rs{h}_median_pp')) for h in [5,10,20]),'10&20双正天':r.rs10_and20_positive_streak,'价格K5/K10/K20':f'{r.return5_K}/{r.return10_K}/{r.return20_K}','20日突破':f'{r.breakout20_count}/{r.breakout20_K}'})
 lines+=['### '+sec,'',table(pd.DataFrame(rows)),'']
lines+=['## 可解释的候选状态机，不是已冻结策略','',
'以下规则是在查看本证据后提出的研究假设，未用未来收益选窗口/阈值，也未做账户收益回测；不能称预注册、最优或已验证。正式下一阶段必须先冻结逻辑、风控和执行口径，再走盲样本。候选诊断文件仅是把公式施加于全部50类的证据标签，不是新账户，不是目标仓位清单。',
'',
'### 1. 初次确认：有限试错，而不是全行业播种','',
'保留M3首次TRUE作为获得小试资格的事件；行业UNKNOWN暂停新增，已持成熟仓仍按自身保护位和独立风险约束管理。M3 TRUE本身不决定必须买入、行业资本配额或立即成熟。本轮不设共享试错风险额度或共享试错风险池，坚持小仓试错。实际规模应由当时可知的主线证据、真实可用资金、法定交易数量、费用、流动性以及另行冻结的资金分配规则决定，不按50个行业均分。逐股保护距离与可能保护损失单独展示，不据此加回共享池。',
'',
'### 2. 持续转强晋级：快证据与慢证据分开','',
'共同Q：M3=TRUE，且n/N≥1/2连续两个交易日。两个交易日是“出现过一次”和“继续成立”的最小区分，仅是候选，不声称最优。',
'',
'快证据F：Q成立、RS5>0、RS5较上日改善、5日中位绝对收益>0，且20日收盘突破股票数≥N/2。这里用突破数/N的下界，未知股不被假定为突破；它不是把未知收益填0。经济含义是持续广度、当下跑赢、绝对上涨与多数价格突破共同支持“允许考虑晋级”。10/20日不设成这条快通道的否决门。',
'',
'慢证据S：Q成立、RS10>0且RS20>0，且10日中位绝对收益>0。双正持续天数作为成熟度/信心证据另列，不强制统一等两天才允许任何加码。它支持已持续较久的主线，不能要求所有新主线先补齐整月弱势。',
'',
'F或S只给晋级候选资格，不等于所有通过者都应等权获配。例半导体F从9/27可见，S从9/30可见；若再把S强制连续两天，会拖到10/8。动力电池F从9/27可见，元件F从9/30可见。F在9/27会放行19类，故它绝不能替代资金优先级或被包装成已经精准识别单一主线。',
'',
'### 3. 资金向强处转，不靠固定行业个数','',
'新增资本按可知主线证据与另行冻结的资金分配规则逐笔决定，不先给50类预留等额资本，也不设置共享试错额度。可解释的初步优先量可以用E=max(RS5,0)×(n/N)：只衡量当前正超额收益乘可知广度，用于已取得资格的边际新增请求排序，不能独立触发开仓、清仓或代替长期成熟度。F/S、RS连续天数、价格窗口K/N都应在账中并列可见，不用未来标签。E不是优化出的最优评分。',
'',
'真正把小试放大还需要该已持股票自身盈利、保护位/CP等原有交易逻辑支持。逐笔新增保护损失可按新增股数乘以每股可执行价到保护位的非负距离展示，交易费用另列；这只是保护风险的说明，不是共享风险池，也不是已冻结的反推股数公式。实际股数仍须由可知主线证据、真实可用资金、法定交易数量、费用、流动性、T+1和另行冻结的资金分配规则决定。行业与单股资本上限均为待检验参数，不是不可更改的既定目标。确认且持续走强的主线应获得更有意义的资本，而非按50类均分。本研究尚未形成完整可运行的仓位策略，不能由这段行情倒推仓位数值。',
'',
'已持盈利证据只能用于决定同一已有仓是否具备继续放大的条件，不能把没分到种子的半导体等行业判为“无盈利所以弱”。既有账户收益受先前选股、先后顺序、现金耗尽影响，这里不把它混进行业价格强弱评分。',
'',
'### 4. 退潮与腾挪：先识别失去相对优势，不把饱和当失败','',
'相对降温候选W：RS5<0且RS10<0连续两个交易日。W意味着新增优先级下降；可在之后另行冻结的腾挪规则下减少较弱或未确认方向的资本投入，把实际可释放资本转向证据更强的主线。不设共享试错额度，也不等价于价格已下跌，更不意味着必须全卖。扩散为负、半数上界(n+U)/N<1/2、价格失守和实际持仓亏损可提供独立退潮证据；单股保护规则独立生效。',
'',
'若M3 UNKNOWN，冻结该行业新增/晋级而非清空成熟仓。若diff=0而n=K且RS仍强，是“已知成员饱和”；例如10/8券保51/51已知成员全部TRUE、U=1，不能因没有更多新增TRUE就撤走。全池饱和n=N与已知饱和n=K分别列字段。',
'',
'强候选需要资金时，先用可用现金和按另行冻结的腾挪规则从较弱方向实际释放的资金；不能为补齐行业覆盖而卖强买弱。没有合规腾挪来源时必须如实拒绝或等待，不改现金约束，也不能拿未来强弱选卖谁。换入的机会损失和滑点是必要成本，需后续冻结后审计，本文不声称已改善收益。',
'',
'## 全50类无删选快照','',
'下表每格为“状态 n/N；RS5/10/20 pp”。其余指定日期、K/U、均值、持续天数、扩散与突破均在TARGET50_EVIDENCE.csv的550行完整保留。',
'']
rows=[]
for sec in sorted(t.sector51.unique()):
 row={'行业':sec}
 for d in ['2024-09-23','2024-09-26','2024-09-27','2024-09-30','2024-10-08']:
  x=t[(t.sector51==sec)&(t.day==d)].iloc[0];row[d]=f'{int(x.m3_state)} {int(x.m3_n)}/{int(x.m3_N)}; '+ '/'.join(pp(x[f'rs{h}_median_pp']) for h in [5,10,20])
 rows.append(row)
lines+=[table(pd.DataFrame(rows)),'','## 文件与核验','','- TARGET50_EVIDENCE.csv：11个重点日期×50类=550行。','- ALL50_DAILY_EVIDENCE.csv：2024-01-02到10/8，9100行，给连续性上下文。','- TARGET_STOCK_WINDOW_AUDIT.csv：55836个逐股窗口单元，列起点、所需根数、known/unknown理由及收益。','- MARKET_BENCHMARK.csv：546个日期-窗口基准行，每行N/K/U。','- CANDIDATE_DIAGNOSTICS_NOT_STRATEGY.csv：上述候选Q/F/S/W对全部50类的透明诊断，不是交易账。','- QA.json、SOURCE_HASHES.json：1692原始价格源SHA256全部匹配；目标55836个窗口逐一用连续截取方式核验；旧M3逐字段完全匹配。','- build_strength.py、build_readout.py：可复现计算与说明。','- 未跑账户、未计算未来收益排名、未修改输入源。所有新增内容仅在本目录。','']
(O/'READOUT.md').write_text('\n'.join(lines))
# Audit output aggregates independently against per-stock target windows.
w=pd.read_csv(O/'TARGET_STOCK_WINDOW_AUDIT.csv');assert len(w)==55836;checks=0
for row in t.itertuples():
 for h in [5,10,20]:
  z=w[(w.day==row.day)&(w.window==h)];v=z[(z.sector51==row.sector51)&z.known].return_value;m=z[z.known].return_value
  assert len(v)==getattr(row,f'return{h}_K');assert len(v)+getattr(row,f'return{h}_U')==row.m3_N
  for f,expected in [(f'return{h}_median',v.median()),(f'return{h}_mean',v.mean()),(f'rs{h}_median_pp',100*(v.median()-m.median())),(f'rs{h}_mean_pp',100*(v.mean()-m.mean()))]:assert np.isclose(getattr(row,f),expected,rtol=1e-9,atol=1e-9,equal_nan=True),(row.day,row.sector51,f)
  checks+=1
q=json.loads((O/'QA.json').read_text());q['aggregate_audit_sector_windows']=checks;q['unit_revision']='All *_pp fields now store actual percentage points; raw return and fraction columns store fractional values. Builder synchronized.';q['candidate_rules']='Transparent hypotheses only, not a frozen, validated, or executed strategy.';(O/'QA.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n')
seal={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_SEAL.json'};(O/'OUTPUT_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
print('READOUT + candidate diagnostics written; aggregate audit PASS',checks,'sector-windows; outputs sealed.')
