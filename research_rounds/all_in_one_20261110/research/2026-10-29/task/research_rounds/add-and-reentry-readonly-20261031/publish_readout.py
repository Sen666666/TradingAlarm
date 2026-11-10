"""Concise report from saved read-only outputs, no new market calculations."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,csv,hashlib
O=Path(__file__).resolve().parent;W=O.parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def m(v):return f'{float(v)/10000:.4f}'
def f(v):return f'{float(v):.2f}' if v is not None else 'N/A'
def stream(p):
 with gzip.open(p,'rt') as h:return [json.loads(x) for x in h]
def main():
 matches=read(O/'FIRST_LATER_MATCHED.json');checks=read(O/'VERIFICATION.json');summaries=read(O/'SUMMARY.json');coverage=[];extra=[];sources=read(O/'SOURCE_HASHES.json')
 for w in ['2022','2025_26']:
  es=read(O/w/'ENTRIES.json');original=W/'stage-progress-R-diagnostic-20261031'/w/'B_diag/ENTRIES.json';orig={r['layer']:r for r in read(original)};sources[str(original)]=sha(original)
  rs=stream(W/'opportunity-quality-ranking-20261031'/w/'CANDIDATES.jsonl.gz')
  for name in ['CANDIDATES.jsonl.gz','PRICE_LABELS.jsonl.gz']:
   p=W/'opportunity-quality-ranking-20261031'/w/name;sources[str(p)]=sha(p)
  for scope in ['all_including_inherited','complete_attempts_only']:
   use=[r for r in rs if scope=='all_including_inherited' or not r['attempt_inherited']]
   coverage.append(dict(window=w,scope=scope,events=len(use),stocks=len({x['sid'] for x in use}),dates=len({x['day'] for x in use}),first_events=sum(x['first_stock_attempt_in_window'] for x in use),later_events=sum(not x['first_stock_attempt_in_window'] for x in use)))
  for e in es:
   c=e['last_actual_buy_comparison'];extra.append(dict(window=w,layer=e['layer'],sid=e['sid'],name=e['name'],signal_day=e['signal_day'],fill_at=e['fill_at'],action=e['actual_action'],industry_stage=orig[e['layer']]['decision_known_stage'],snapshot_day=e['known_snapshot_day'],old_economic_sign=e['old_live_economic_sign'],old_economic_net=e['old_live_layer_economic_net'],new_buy_cash=e['actual_buy_cash'],new_buy_qty=e['actual_buy_qty'],open_below_previous_actual_buy=c['open_below_previous'] if c else None,fill_below_previous_actual_buy=c['fill_below_previous'] if c else None,previous_actual_buy_at=c['previous_at'] if c else None,previous_raw_fill=c['previous_raw_fill'] if c else None,current_raw_open=c['current_raw_open'] if c else None,current_raw_fill=c['current_raw_fill'] if c else None,prior_complete_exit_sign=e['reentry_previous_cycle_sign'],reentry_same_stock_E0=e['reentry_same_stock_E0'],reentry_same_industry_attempt=e['reentry_same_industry_attempt'],closed=e['closed'],new_layer_net=e['net_contribution'],terminal_quantity=e['terminal_quantity']))
 save(O/'MATCHING_COVERAGE.json',coverage)
 p=O/'ENTRY_SUMMARY.csv'
 with p.open('w') as h:
  writer=csv.DictWriter(h,fieldnames=list(extra[0]));writer.writeheader();writer.writerows(extra)
 t=['追加／重入与首后候选：原轨迹只读诊断｜2026-10-31',
    '0新账户回放、0新指标缓存、0交易规则变更。固定完整2022和2025-07-01至2026-06-30，仅B_diag真实confirmed mobile新买576/602层。',
    '', '一、已有股追加的直接事实',
    '“首次”=此前本账户从未实际持有该股；“追加”=真实本次fill前该股仍有core或mobile；“重入”=此前真实持有且整股实卖至0后再实际买入。所有角色／pool均参与判断，未成交意图不算持有，core迁池不算新投入。真实交易及拆股数量逐日重建仅作账目分类，未调用策略或成交引擎；两窗各242日日末数量与原快照完全一致。',
    '旧仓经济浮盈按入场前最近账户收盘的所有该股存量层计算：Σ(原层累计买卖现金净流 + 已归属分红权益 + 剩余股数×同源raw mark)。买费已在cash，分红沿原应收/到账代理，不视为可花现金；不混入此前已全清周期损益。核得追加样本的存量层此前部分卖出为0，因此这里没有用已实现部分利润充作浮盈。旧core/mobile数量、成本与原保护逐层保留；不把旧core换成新mobile近线。',
    '该分组是上一收盘已知状态，不冒充精确开盘前盈亏；隔夜跳空仍可能改变实际浮盈符号。所有追加样本前一收盘持仓层与实际prefill层及数量一致，拆股/同开盘卖出没有改变本批追加持仓身份。',
    '窗口 | 真实追加层 | 旧仓正/负/零/未知 | 负旧仓新买款占比 | 正旧仓新层闭合负 / 负旧仓新层闭合负（万元）']
 for s in summaries:
  a=s['adds_prior_close_sign'];t.append(f"{s['window']} | {s['action']['add']['layers']} | {a['positive']['layers']}/{a['negative']['layers']}/{a['zero']['layers']}/{a['unknown']['layers']} | {100*float(a['negative']['buy_cash'])/float(s['action']['add']['buy_cash']):.2f}% | {m(a['positive']['closed_negative'])} / {m(a['negative']['closed_negative'])}")
 t+=['2022追加负贡献的93.58%来自上一收盘旧仓经济浮盈为正的追加；负旧仓追加只占追加负贡献6.42%。但追加只占本批全部confirmed新层负贡献30.82%，首次参与51.46%、重入17.72%，不能把整年失败都归因于追加。',
     '2025—26相应追加负贡献89.82%来自正旧仓、10.18%来自负旧仓；正旧仓追加层合计闭合净+3.9258万元、未平贡献+2.0847万元，负旧仓追加层闭合净-1.3345万元。',
     '结论：本分母否定“主要不断给整体亏仓摊低成本”这一解释；真实风险是大量已有盈利的仓位追加后反转。但这不证明追加因果有害或原退出应改变，未模拟不追加反事实。',
     '', '二、各类新增层损益（万元；只归新增层，旧仓后续损益不挪入）',
     '窗口 | 类别 | 层/股 | 实际新买款含费 | 闭合正 | 闭合负 | 未平贡献']
 for s in summaries:
  for key,a in s['action'].items():t.append(f"{s['window']} | {key} | {a['layers']}/{a['stocks']} | {m(a['buy_cash'])} | {m(a['closed_positive'])} | {m(a['closed_negative'])} | {m(a['open_contribution'])}")
 t+=['上述三个行为类别互斥，股票数可跨类别重复；完整新增层数量、买款和净贡献逐项与原ENTRIES对齐，不能当独立胜率。closed依据原终点实际qty=0；open是剩余估值及原现金/权益的层净贡献，不冒充已平利润。',
     '', '三、当时价格相对上次真实买入',
     '比较使用原同源factor将上次实际fill与本次开盘/实际fill转换到同一价格域，跨权息不生拼raw价；仅作描述，不改变保护线。',
     '2022追加141层：开盘价低于上次实际买价18层；含5bps滑点的实际fill低于上次fill为16层，其中旧仓正8、负8。2025—26追加178层：两口径均22层，其中旧仓正13、负9。开盘与fill口径差异保留，不择好。',
     '', '四、两条完整真实链（案例不是市场总体因果证明）',
     '浙文互联600986：按日期最早的负旧仓追加。1/5 fresh CP1实际mobile100股@8.974485，含费902.53元；1/10旧层收盘100股×8.71，经济净-31.53元，原mobile raw保护8.02。行业expanded，1/10新canonical CP1，1/11买2200股@8.454225、含费18605.94元；1/12原I退出，2300股@8.19590，新增2200股层分配净卖款18006.57元、独立净亏599.38元；旧100股层净亏84.05元另列。',
     '000620（当前snapshot名称盈新发展）：按正旧仓追加中新层最大亏损选例，不冒充随机样本。1/12首次mobile6200股@3.08154；1/20全部卖@2.948525，前周期净-856.29元。1/21原I core实际重入4400股@3.28164；当日收盘3.62，旧core经济浮盈1482.50元、raw保护2.99。行业confirmed，1/21 fresh CP1使1/24追加5100股@3.72186（18988.17元），新mobile初始raw保护约3.1204，未替换core2.99；1/25再加3300股@4.002。2/8原I退出，12800股@2.768615；5100股新层独立亏4886.43元，3300股新层亏4088.12元，旧core亏2279.29元分别记账。',
     '全量原交易、逐层旧仓快照和原保护见EXAMPLE_CHAINS.json；案例链的时间线不回填未来信息到入场分组。',
     '', '五、真正全清后重入',
     '最近一次“完整退出”净贡献=该连续持有周期内所有原层最终cash+dividend；仅该周期真实全部实卖0后才确定。不得把每个亏损层卖出或先前未获资当完成试错。',
     '窗口 | 重入层 | 前完整周期正/负/零/未知 | 同原股E0 / 同原行业attempt / 两者同时']
 for s in summaries:
  w=s['window'];es=read(O/w/'ENTRIES.json');re=[e for e in es if e['actual_action']=='reentry'];a=s['reentry_prior_full_exit_sign'];both=sum(e['reentry_same_stock_E0'] and e['reentry_same_industry_attempt'] for e in re)
  t.append(f"{w} | {len(re)} | {a['positive']['layers']}/{a['negative']['layers']}/{a['zero']['layers']}/{a['unknown']['layers']} | {s['reentry_same_stock_E0'].get('True',0)} / {s['reentry_same_industry_attempt'].get('True',0)} / {both}")
 t+=['同E0／attempt比较新层与前一完整退出最后实卖批次所含原层身份；混合身份集合完整保存，不把换attempt清洗为首次。重入仍使用真正fresh receipt。',
     '窗口 | 前完整周期符号 | 层 | 新买款 | 新层闭合正 / 闭合负 / 未平贡献（万元）']
 for s in summaries:
  for sg in ['positive','negative']:
   a=s['reentry_prior_full_exit_sign'][sg];t.append(f"{s['window']} | {sg} | {a['layers']} | {m(a['buy_cash'])} | {m(a['closed_positive'])} / {m(a['closed_negative'])} / {m(a['open_contribution'])}")
 t+=['2022负周期后重入106/125层，但并非全部继续亏：新增层也有闭合正4.4535万元；正样本负周期后重入还贡献未平4.6094万元。这里只描述原轨迹，未授权亏后禁入、缩金额或降低重入预算。',
     '', '六、首候选/后续候选同日可比价格标签',
     'fresh/Q/stage候选、21/63观察同源复权close及删失定义完全复用上一轮，不重算信号。每股×行业attempt窗内首候选与后续候选比较。主要版本仅窗内新建attempt（2022首3098个、正样本首3546个）；继承暖机attempt的窗内首并非真实首次，另有完整含继承版本，不混称。字段complete_attempts_only/first_complete_attempt仅表示attempt起点在评价窗内，绝不表示attempt已经结束。',
     '粗配：day×stage；强配：day×同一原industry attempt，后者同时固定行业、stage与attempt年龄。每组先算首/后候选各自等权均值，再在同日对组等权、最后日期等权。只保留两组都存在的组；不是不同日期总均值之差。股票本身与证据出现顺序仍非随机，不作重复信号因果判断。',
     '完整新attempt版本 | 配对 | horizon | 可比/总组 | 日期 | 首/后事件 | 首/后同日均值% | 后−首百分点']
 for r in matches:
  if r['scope']=='complete_attempts_only' and r['stage']=='all':t.append(f"{r['window']} | {r['matching']} | {r['horizon']} | {r['comparable_groups']}/{r['total_groups']} | {r['comparable_dates']} | {r['first']['events']}/{r['later']['events']} | {f(r['date_equal_first'])}/{f(r['date_equal_later'])} | {f(r['date_equal_later_minus_first'])}")
 t+=['2022粗同日同阶段21观察后续反而+0.48个百分点，固定同一行业attempt后为-2.12；63为-2.69。正样本同attempt21为+0.24、63为-2.18。故首候选去重均值转正本身不能证明后续CP1无效；不同可比分母与尺度的结果全部报告，不择21/63结论。',
     '完整first/later人数、股票数、有效日期、MAE/MFE、confirmed/expanded分层及含继承敏感性见FIRST_LATER_MATCHED.csv/json；不可比组及完整机会分母见MATCHING_COVERAGE.json。删失0依赖评价窗后的实际归档价格：2022标签21最晚2023-02-07、63最晚2023-04-07；正样本21最晚2026-08-07、63最晚2026-10-16。未来仅作标签，非政策利润/真实胜率。',
     '', '七、核验与研究边界',
     '两窗各242日交易/拆股数量逐日匹配原日终；上一收盘原cash/dividend/quantity/core或mobile保护逐值保留。99/113个所用日的全部库存以同源raw close复算与原inventory差0；这验证价格单位，不自称另一独立完整NAV模型。样本旧层此前partial exit为0，3/4笔追加的旧仓含已归属分红权益。',
     '主要分析实际4.99秒，验证与导出为秒级；无账户策略重跑、无原始I/CP1重算。当前无数据/连接/权限阻塞，精确开盘前旧仓盈亏未重建，统一用最近收盘并保留隔夜限制。',
     '今日snapshot成员/行业映射非PIT，全部历史已消费；事件及未来窗口高度重叠，前向均值不是可实现收益。保持现合同冻结，不实施亏仓不加、不禁亏后重入、不改原退出、不选新阈值。此诊断不构成实盘认证。']
 p=O/'READOUT.txt';p.write_text('\n'.join(t)+'\n');save(O/'INPUT_PROVENANCE.json',sources)
 manifest={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.name!='FINAL_EVIDENCE.json'}
 save(O/'FINAL_EVIDENCE.json',dict(readonly=True,new_account_paths=0,new_policy_changes=0,outputs_SHA256=manifest))
 print('READOUT_SHA256',sha(O/'READOUT.txt'),'files',len(manifest))
if __name__=='__main__':main()
