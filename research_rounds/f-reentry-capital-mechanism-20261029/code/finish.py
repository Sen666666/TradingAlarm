from pathlib import Path
import json,gzip,collections,time,importlib.util,sys,datetime
from decimal import Decimal as D
import pandas as pd
R=Path('/Users/bytedance/Documents/ChatGPT/money');O=R/'research_rounds/f-reentry-capital-mechanism-20261029';E1=R/'research_rounds/s-entry-mechanism-audit-20261029'
sp=importlib.util.spec_from_file_location('f_finish_h',O/'code/study.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S)
t=time.monotonic();ident=S.H.read(O/'input-identity.json')['sha256'];assert all(S.H.sha(p)==h for p,h in ident.items())
summary=S.H.read(O/'results/summary.json');checks=collections.Counter();examples={};active_idle=collections.Counter();cycle_frames=pd.read_csv(O/'results/roundtrips.csv');failures=[]
with gzip.open(O/'results/audit.jsonl.gz','rt') as f:
 for line in f:
  a=json.loads(line)
  if a['cost']!=1:continue
  q=0;lastsale=None;entry=None;ns=collections.Counter();prior_exit=None
  for x in a['audit']:
   k=x['kind']
   if k=='fill':
    z=x['receipt'];tm=pd.Timestamp(z['at']);qty=int(z['shares'])
    if z['side']=='buy':
     if q==0:
      entry=tm
      if lastsale is not None:
       assert tm>lastsale;checks['repurchase_after_full_sale']+=1
     q+=qty;ns['buys']+=1
    else:
     assert tm.date()>entry.date();checks['sale_after_buy_date']+=1;q-=qty;ns['sales']+=1
     if not q:lastsale=tm
   elif k in ['split','split_fraction_floor_proxy']:q=int(D(q)*D(x['ratio']));ns[k]+=1
   elif k=='dividend_accrual':ns[k]+=1
   if k=='exit_request':prior_exit=pd.Timestamp(x['at'])
  for x in a['decisions']:
   if x['kind']=='raise' and x['pivot_eligible']:
    assert str(x['pivot_date'])>=pd.Timestamp(x['entry']).date().isoformat();checks['F_pivot_at_or_after_actual_cycle_buy']+=1
   if x['kind']=='exit' and x['reason']=='old_protection':assert D(x['close'])<=D(x['old']);checks['old_line_break_before_new_candidate']+=1
  sales=[pd.Timestamp(x['receipt']['at']) for x in a['audit'] if x['kind']=='fill' and x['receipt']['side']=='sell']
  for x in a['attempts']:
   st=pd.Timestamp(x['signal_at'])
   if any(y.date()==st.date() and y<st for y in sales):checks['same_day_close_reentry_after_open_sale']+=1;examples.setdefault('sale_cash_same_day',dict(event_id=a['event_id'],attempt=x))
  if ns['buys']>=4:examples.setdefault('multiple_retries',dict(event_id=a['event_id'],counts=dict(ns)))
  if ns['split']:examples.setdefault('split',dict(event_id=a['event_id'],counts=dict(ns)))
  if ns['split_fraction_floor_proxy']:examples.setdefault('fraction_proxy',dict(event_id=a['event_id'],counts=dict(ns)))
  if ns['dividend_accrual']:examples.setdefault('dividend_claim',dict(event_id=a['event_id'],counts=dict(ns)))
u=pd.read_parquet(O/'results/units.parquet');base=u[u.cost.eq(1)]
for row in base.to_dict('records'):
 if row['stats'].get('exit_unavailable_open'):examples.setdefault('exit_unavailable',dict(event_id=row['event_id'],stats=row['stats']))
 if row['stats'].get('buy_unavailable_open'):examples.setdefault('buy_unavailable',dict(event_id=row['event_id'],stats=row['stats']))
 if row['shares']>0:examples.setdefault('terminal_open',dict(event_id=row['event_id'],shares=row['shares'],market_value=row['market_value'],mark_known_at=row['mark_known_at']))
d=pd.read_parquet(O/'results/daily-paired.parquet');e=pd.read_parquet(E1/'opportunities.parquet');d=d.merge(e[['event_id','end_signal']],on='event_id');di=d[(d.cost==1)&(d.F_cycle>0)&d.F_shares.eq(0)];within=di.end_signal.isna()|pd.to_datetime(di.date).lt(pd.to_datetime(di.end_signal))
idle=dict(total_flat_close_sessions=len(di),inside_original_E0=int(within.sum()),after_original_E0=len(di)-int(within.sum()),meaning='Cash is idle at these closes; after-E0 includes entitlement waiting, not new valid retry opportunities. 0 interest and no imagined other-stock return.')
failed=O/'full-v1-serialization-failed/audit.jsonl.gz'
with gzip.open(failed,'rt') as f:failedrows=sum(1 for _ in f)
S.save(O/'FAILURES.json',dict(technical_only=True,error='JSON TypeError NAType not serializable in F pivot metadata',complete_audit_units_before_failure=failedrows,elapsed_first_failed_run_not_instrumented=True,preserved_dir=str(failed.parent),fix='Map pd.NA/NaT metadata to JSON null only; no financial/state/parameter change',report_scope_note='407 frozen stocks, 396 with E0 epochs, 11 without E0 epoch. Conditional396 and fixed407 stock-equal scales both reported; no unmatched outcome invented.',report_type_fix='finish v1 string date vs datetime idle-scope comparison, explicitly convert both to datetime; v1 retained, financial results unchanged',economic_reruns_after_results=0))
S.save(O/'results/supplementary-verification.json',dict(passed=True,readonly_inputs_sha_unchanged=len(ident),checks=dict(checks),examples=examples,idle_scope=idle,no_new_strategy_computation=True,seconds=time.monotonic()-t))
def money(x):return f'{D(str(x))/10000:,.2f}'
b=summary['1'];c=summary['2'];bucket=b['daily_accounting']
report=f'''实验三：F快保护＋合法同股买回，完成收口

结论：本轮不支持替代原I/E0持有。F确实省普通损耗、买回也追回可观收益，但尾部损失更大。此结论只针对冻结F与原I新事件买回；不能外推为所有快退出/再参与均无效，也没有检验跨股轮换。

同407科技冻结池、5349共同E0事件、基础/双成本。396股有E0事件，11股无事件，不补造零收益机会。各事件初始独立100万元，两臂第一实际成交精确一致。I控制只读引用实验一；以下合计是独立影子账求和，绝非单个可交易账户收益。

基础成本：F−I合计 {money(b['delta'])} 万元，平均每百万元事件 {D(b['per_1m_event_delta']):,.2f} 元（−1.0392个百分点）。省负损耗 {money(b['loss_saved'])} 万元，少正收益 {money(b['positive_pnl_foregone'])} 万元；普通事件差额 +{money(b['ordinary_delta'])} 万元，原I>=30%尾部差额 {money(b['tail_delta'])} 万元。原I尾部596事件中592已无股票、4仍期末估值；F在同一集合保留81.46%贡献。30%只是既有评价标签，不代表抓住数倍行情，更不是交易门槛。
双成本：平均 {D(c['per_1m_event_delta']):,.2f} 元；普通 +{money(c['ordinary_delta'])}、尾部 {money(c['tail_delta'])} 万元，尾部保留81.10%。固定407股票等权口径基础 {D(b['stock_equal_delta_per_1m_frozen_pool407']):,.2f} 元；只在396有事件股条件归一为 {D(b['stock_equal_conditional_event_stocks396']):,.2f} 元，方向一致。

买回不能省略，也不能重置本金：基础有1222事件买回，共1677次，单事件最多7次入场。1669次闭合买回中1015次亏损，负轮次合计 {money(b['retry_closed_loss_amount'])} 万元；全部买回（含未平仓）净贡献 +{money(b['retry_all_pnl'])} 万元。精确分解：F首轮相对完整I差额 {money(b['first_F_cycle_vs_full_I'])} 万元，加全部买回 +{money(b['retry_all_pnl'])}，等于最终 {money(b['delta'])} 万元。买回恢复约57.8%的首轮差额，仍未补齐。不能用1015次失败就否定买回：其净贡献仍为正。
F/I平均盈利额比平均亏损额为3.23/3.54；胜率仅描述，不作为通过条件。F省普通成本而损肥尾的取舍，和低胜率、高盈亏比目标不匹配。

会计拆分（每日两臂NAV变动差，万元）：共同首次持有 {money(bucket['initial_hold'])}；完全空仓等待 {money(bucket['idle'])}；再次持有 {money(bucket['repurchased_hold'])}；已申请退出但仍持有 {money(bucket['pending_exit'])}；交易/部分成交/权息边界 {money(bucket['mixed_trade_action'])}。五项精确合计主差额。这是路径会计，不能当作唯一因果归因；再次持有差额也含前次损失导致股数变化。{idle['inside_original_E0']}个平仓收盘在原段内，{idle['after_original_E0']}个在原段后（含等待权益），无利息、无假定其他股再投资收益。
额外显式费用 {money(b['all_extra_fees'])} 万元，额外原开盘滑点 {money(b['all_extra_slippage'])} 万元，仅备忘，已经计入净账，不能再扣一次；即便在相同实际路径加回也未补足主差额，这不等于零成本策略重跑。

正确性：111事件/222账样例1.483秒，8股物理截断前缀通过。全量5349事件/10698新F账52.953秒（含加载/身份检查/落盘），低于300秒；样例全量一致。独立现金、股数、分项费率、权息和NAV，原I终值重建，所有初次成交精确；最大现金和NAV残差0。逐轮Pnl、逐日差额、尾部/普通、省损耗−少正收益均核对。原418输入SHA不变。真实路径包含不可成交开盘、部分退出、跳空实际开盘、拆股/分数股代理、股息待收和期末未平仓；补充核验给出例子。{checks['same_day_close_reentry_after_open_sale']}次卖出当日收盘的新I事件允许再申请，无额外空等一天；买入当日股票不可卖与此分开。
输入冻结1.189秒，结果聚合约1.64秒。开发/阅读/工具交互未预设独立秒表，父线程本轮检查点约16分钟，不能把它伪写成精确CPU耗时；协议至样例文件时间约16秒，代码首次落盘至样例约49秒，均不覆盖之前阅读/设计。首次全量仅日志pd.NA序列化错误，失败目录及旧代码保留，修复不改规则；首次失败耗时未单独捕获。报告后没有经济重跑或调参。

原F对照与本轮边界：RULES.txt第6行和study.py第17–40行定义半阈值、63/21原股数量口径、旧线先检、买后低点、max上抬，均沿用；F观察器连续、不因交易重建。每次买回重置为当次原I支持，不继承已失败旧F线。为了共同首次参与，初始保护从冻结原I入场支持开始；原实现私人fast_floor在首个持有收盘初始化，边界已事前列明。部分退出期间仍是同一持有周期；源/E0段终止不再买回，已有退出按实际可成交完成。本轮移除ACT、整户名额/行业配额/排序/共享现金和15%整户预算；保留原Q的市场/行业/准备/G1门槛。每事件100万元隔离仅作机制诊断，非原INTENT-SUPPORT整户复现。

期末两臂104/51个持股事件及所有待收权益均进入主账。既有日线开盘+历史容量/当日HLV校验代理、分数股向下取整、股息支付字段未知等限制继续存在，不冒称逐笔可成交或真实税务。估计清算费另列summary，不伪装已成交；现有开发历史不是样本外。

交付：PROTOCOL.json、input-identity.json；code/study.py、report.py；results/units.parquet、daily-paired.parquet、paired-events-cost*.csv、roundtrips.csv、attempts.csv、fee-components.csv、continuous-contributions.csv、top-I-events-cost*.csv、summary.json及三份verification。下一步：本轮收口，不自动接跨股票轮换、调F线或改产品。无权限阻塞、无账户访问、无交易。
'''
(O/'FINAL_REPORT.txt').write_text(report)
S.save(O/'COMPLETION.json',dict(status='completed',verdict='Do not replace I with this F+legal same-stock reentry rule in the frozen sample; ordinary improvement is outweighed by tail damage.',events=5349,frozen_stocks=407,event_stocks=396,sample_seconds=1.4830206669867039,full_seconds=52.9528888752684,main=summary,inputs_unchanged=len(ident),product_changes=0,account_access=0,trades=0,new_routes=0,blockers=[],report=str(O/'FINAL_REPORT.txt')))
print(json.dumps(dict(completed=True,extra_checks=dict(checks),idle=idle,seconds=time.monotonic()-t),ensure_ascii=False))
