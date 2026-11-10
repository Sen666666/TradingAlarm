from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,gzip,hashlib
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task');P=ROOT/'research_rounds/pvr-slot1-native-readiness-20261101';O=P/'semiconductor-2026H1-readonly';W=P.parent
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
summary=read('SUMMARY.json');sectors=read('INDUSTRY_SUMMARY.json');curve=read('DAILY_ALIGNED_CAPITAL.json');snaps=read('REPRESENTATIVE_CLOSE_RESOURCE_STATES.json');paths=read('FIXED_TOP_RETURN_AND_FUNDED_CONTROLS.json');funnel=read('SEMICONDUCTOR_OPPORTUNITY_FUNNEL.json')
sources={}
cap=[
 dict(name='original_cash_reserve',value='10% decision NAV',formula='new gross+fee <= available - .10*last decision NAV, and mirrored unreserved cash',meaning='not a forced daily cash weight; current real resources also checked'),
 dict(name='probe_capital',value='10% fee-adjusted current budget NAV',formula='existing probe marked lots + live/cancel-pending buys + new gross <= .10*(real NAV-pending buy fees-new buy fee)'),
 dict(name='confirmed_capital',value='60% same budget NAV',formula='existing confirmed marked lots + pending + new gross <= .60*budget NAV'),
 dict(name='sum_of_pools',value='10%+60%',meaning='active construction ceiling from cash around70%; NOT a separate daily total70% risk rule. Passive growth can exceed caps without forced sale; one pool over cap does not magically empty another'),
 dict(name='industry_capital',value='probe route2%; confirmed route industry stage10%/20%',formula='ALL sector commitments, across pools/attempts/roles, counted; a probe request always uses2% even when its industry stage is higher'),
 dict(name='industry_nominal_risk',value='1% same budget NAV',formula='sum quantity*max(current mark or pending limit - ACTUAL role floor,0); no phantom CP1 floor on core'),
 dict(name='probe_nominal_risk',value='0.5% same budget NAV',formula='all probe lot/pending mark-to-floor risk, including passive winner giveback'),
 dict(name='stock_capital',value='10% original decision NAV at new admission',formula='held at known open + new gross <= .10*last decision NAV; passive growth above10% does not force sale'),
 dict(name='core_order_risk',value='0.25% decision NAV',formula='modeled buy gross+buy fee - own I/E0-floor sell proceeds + modeled sell fee <= .0025*decision NAV; frozen maximum shares/gross; stock10% cap'),
 dict(name='mobile_order_target',value='2% decision NAV',formula='min(.02*decision NAV, remaining stock10% gross headroom), frozen legal quantity; no R1 round-up'),
 dict(name='account_total_3pct_check',value='ABSENT',meaning='current PVR_SLOT1 inherits Bdiag singlepass; does not mean no sector/probe/cash risk limits'),
 dict(name='ACT',value='original ACT20_BREAK',meaning='phase DD pause/exit and original market recovery; 0 paused closes in2026H1'),
 dict(name='non_numeric_admission',value='original Q/I, fresh canonical mobile CP1, active industry, legal lots, one stock order, core-first reservation',meaning='successful core reservation suppresses same-open mobile even with zero fill; first/ADD/reentry cannot reuse receipt'),
 dict(name='migration_coupling',value='ORIGINAL SC COUPLED',meaning='new mobile confirmed route/request still needs successful whole-current-industry-attempt probe migration. Pending same-attempt probe blocks it; no pending release before acknowledgement. Original industry invalidation cancels pending new orders but does not force stock exits')]
for p,lo,hi in [(W/'account-risk-ablation-20261031/route_without_account_check.py',1,38),(W/'account-risk-ablation-20261031/model_without_account_check.py',187,260),(W/'case-stage-ledger-20261031/v3/joint_v3.py',244,260),(W/'case-stage-ledger-20261031/v3/joint_v3.py',301,319),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py'),42,66)]:
 a=p.read_text().splitlines();sources[str(p)]=dict(sha256=h(p),first=lo,last=min(hi,len(a)),excerpt='\n'.join(f'{i+1}: {a[i]}' for i in range(lo-1,min(hi,len(a)))))
save('HARD_CAP_SOURCE_INVENTORY.json',dict(all_limits_are_research_choices_not_user_limits=True,no_limit_changed=True,limits=cap,source=sources))
# Exact old known lines at two deterministic controls' actual exit requests.
root=P/'runs/2025_26/pair';b=gz(root/'B.json.gz')
with gzip.open(root/'daily.jsonl.gz','rt') as f:ds=[json.loads(t) for t in f]
dd={x['at'][:10]:x for x in ds};days=list(dd);sm={x['symbol']:x for x in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())};controls=[]
for sid in ['603061.SH','688107.SH']:
 x=next(x for x in paths if x['stock']['sid']==sid);f=pd.read_parquet(sm[sid]['refs']['facts'])
 for e in x['actual_exit_requests_and_fills']:
  d=e['request_at'][:10];prior=days[days.index(d)-1];z=next(z for z in dd[prior]['layers'] if z['id']==e['layer']);line=D(z['floor'] if z['role']=='mobile' else z['last_core_line']);r=f.loc[d]
  t=next(t for t in b['trades'] if t['side']=='sell' and any(a['layer']==e['layer'] for a in t['parts']))
  controls.append(dict(sid=sid,layer=e['layer'],known_line_at_prior_close=prior,actual_known_line_adjusted=str(line),trigger_close_day=d,trigger_close_adjusted=str(r.close),I_still_valid_at_trigger=bool(r.i_target),G1_grade_known_at_trigger=float(r.g_grade),request=e['request_at'],reason=e['reason'],first_legal_proxy_fill=t['at'],actual_raw_open=t['raw_open'],actual_sell_price=t['price'],layer_net=e['net'],does_not_claim_an_earlier_executable_fill=True))
save('CONTROL_EXIT_PRIOR_LINES.json',controls)
# Confirm old financial objects equal previously audited financial artifact capture.
fm=json.loads((P/'FINANCIAL_ARTIFACT_SHA256.json').read_text());verified={}
for n,v in fm.items():
 if n.startswith('runs/2025_26/') and (n.endswith('pair/B.json.gz') or n.endswith('pair/daily.jsonl.gz') or n.endswith('pair/funding.jsonl.gz') or n.endswith('checkpoint.pkl')):
  assert h(P/n)==v;verified[n]=v
assert len(verified)>=3
# Compact ROOT-readable report.
def f(x,n=2):return f'{float(x):,.{n}f}'
lines=['2026H1 PVR_SLOT1｜原行业半导体参与与真实容量（只读）',
'结论：严格半导体未达大仓参与目标；总体盈利不能替代这项行为验收。只读原账/缓存，无新账户、指标、限额或T1-L实现。7—10月经济参与未验证。',
'时间窗为原账户2025-12-31收盘承接到2026-06-30，共116个原市场钟收盘。H1账户收益+54.1743%，平均曝险64.6996%，ACT暂停0日。',
'', '原行业｜指数H1涨幅｜平均/峰值/末权重｜H1贡献｜闭合交易PnL｜未实现价差变化｜确认股息（金额万元）']
for x in sectors:
 lines.append(f"{x['industry']}｜{f(x['price_return_H1_pct'])}%｜{f(x['mean_weight_pct'])}/{f(x['peak_weight'])}/{f(x['end_weight'])}%｜{f(float(x['interval_net_contribution'])/1e4)}｜{f(float(x['closed_trading_PnL_excluding_dividends'])/1e4)}｜{f(float(x['unrealized_price_PnL_change'])/1e4)}｜{f(float(x['recognized_H1_dividends'])/1e4,4)}")
lines += ['电子化学品/元件严格另列，不事后合并为半导体。23.64%电子化学品峰值含被动涨价，不能当新买突破20%准入上限。',
'严格半导体H1无承接旧仓，13次新买=12 mobile/confirmed+1 mobile/probe，没有core成交；11只股票。累计实际新买含费25.7367万元不是同时仓位；净主动gross资金6.8818万，价格/权益库存变化0.9428万，末库存7.8246万。',
'严格半导体闭合正贡献9889.63、闭合负贡献-14360.84，净-4471.21；末未实现13663.17，合计9191.96元。没有将open-layer类别当未实现PnL。',
'', '算法状态→资金：以下均为当日收盘后状态，升级只能供下一合法开盘用，绝非同日开盘已知。']
for d in ['2026-01-05','2026-01-07','2026-03-23','2026-04-17','2026-04-30','2026-05-07','2026-06-24','2026-06-30']:
 x=next(x for x in curve if x['day']==d and x['sector']=='URFI881121');lines.append(f"{d} 行业{x['industry_stage']}，指数较2025末{f(x['index_return_since_2025end_pct'])}%，半导体权重{f(x['industry_weight_pct'])}%，组合{f(x['portfolio_exposure_pct'])}%")
lines += ['原行业3/3—4/7及5/29—6/10 E0失效撤新许可；4/17probe、4/30confirmed、5/7expanded；6/16probe、6/24confirmed、6/30expanded。未因行业失效强卖仍满足个股规则的旧股。',
'833个独立stock/day/canonical-CP1机会通过原mobile Q且行业confirmed/expanded：257未进入计划（原目标/尺寸），537开盘拒绝，13预留且成交，26已计划但下一开盘越过6/30终点。末日合格34中另8已归尺寸类，不能再重复加总。ACT不是这些机会的阻挡；原始拒因含多路由合并，不能全部叫风险独占。',
'', '真实反例/对照（以126原快照身份为分母；114个半年价可比、12边界或来源不足保留NA；涨幅只作后视镜）']
for x in paths[:5]:
 a=x['stock'];mb=x['original_mobile_target_minimum_blocks'];op=x['first_actual_opening_route_record']
 why=(f"全部{x['original_opportunity_counts']['CP1_Q']}个Q通过CP1均目标不足最低单位" if len(mb)==x['original_opportunity_counts']['CP1_Q'] and mb else f"首实际开盘记录{op['at'][:10]}:{op['result']}" if op else '见原始源头分层')
 lines.append(f"{a['name']} {a['sid']} H1价+{f(a['price_return_pct'])}%，最大实际权重{f(a['peak_H1_weight_pct'])}%，{why}")
lines += ['普冉1/7：原2%目标26239.04，200股×183=36600，差10360.96元；源杰1/9：26790.73对150400，差123609.27。原core另受.25%风险/股10%混合最小单位限制，不虚称全部风险独占。',
'金海通1/19及1/20各买100股，峰值4.5338%，2/11 CP1保护请求、2/12实卖，合计+7700.61；之后仍有新信号，9个Q通过CP1在目标/最低单位处受阻，另有原资源拒绝。不是从未识别，也没有持续持有完整+419%行情。',
'正贡献对照立昂微：1月即有原I/CP1/Q，早期资源拒；5/11真正全清后重入300股，最大1.2721%，末未平贡献+7822.29。',
'失败对照安路科技：5/20收盘G1=4、I有效、行业expanded，5/21 mobile/confirmed买662股32065.29元含费；5/29 CP1保护请求、6/1实卖，净-5050.15。实际旧线/触发价/下一合法代理成交在CONTROL_EXIT_PRIOR_LINES，不推算虚构早退。',
'', '结构上限与当时实际阻挡必须分开：',
'原现金预留10%；probe资本10%/风险.5%；confirmed资本60%；行业ALL承诺对probe新单总是2%，confirmed随stage10/20%；行业真实名义风险1%；股新承诺10%；core每单全成本保护风险.25%；mobile正常目标2%；无账户总3%检查。它们都是研究选择，不是用户上限。',
'两池60+10限制主动建仓能力，但不是每日总仓位70硬线；涨价可被动超限不强卖。严格单行业20%又阻止主动把近全仓压到一个原行业；用户全仓首先指组合/主线能力，不解释成单股100%或杠杆。',
'然而本例并未打满半导体20%，不能只提高行业上限就声称解决：']
for d in ['2026-04-30','2026-05-07']:
 x=next(x for x in snaps if x['day']==d);lines.append(f"{d} NAV{f(x['NAV'])}，半导体0；行业资本余量{f(x['semiconductor_capital_slack'])}；confirmed占用{f(x['confirmed_capital'])} / 参考上限{f(x['confirmed_capital_cap'])}；probe风险{f(x['probe_risk'])} / {f(x['probe_risk_cap'])}；可用现金{f(x['actual_available'])}，收盘10%预留{f(x['cash_reserve_reference_10pct'])}。")
lines += ['这证明资金/真实风险许可与识别不同。上述是已保存收盘资源，不是精确开盘前逐候选状态；本轮没有做移除单约束后可买多少的预览，没有恢复器或假成交。',
'4/30主要资本占用包括长飞光纤7.078万、东山精密3.735万等，原I有效且当时已盈利；不能因其占额就叫垃圾旧仓。probe风险前10真实层及角色/保护在REPRESENTATIVE_CLOSE_RESOURCE_STATES。',
'原confirmed路由还耦合整行业current-attempt迁池成功，原probe新股又受行业ALL2%限制。仅凭合并拒因无法精确判定某开盘是哪个pending挡住；该未知保留。',
'', '现成环境数据：复用原ACT1709/90外部breadth，4/30=58.84%、5/7=67.97%、6/30=32.91%；它是行业分组的原量价方向广度，不是半导体广度。原行业CP1 m/v也逐日给出；未新算板块横截面广度/金额指标。',
'全组合H1实际贡献前列中船特气18.8045万、唯特偶12.0926万（电子化学品）、长飞光纤8.5908万（通信设备），说明捕获了别的赢家；不能据此替严格半导体验收盖章。',
'支持的机制：实际信号→订单尺寸/共享池与迁池→角色保护/重入链存在可证断点；严格半导体未实现大仓参与。未证：放宽某一限额会改善可执行收益，或换序/更严证明可补全行情。',
'下一项预金融验收应把924旧版快速广泛确认正例与本例持续推进/失败对照一起审市场证据时钟和资金承接能力；T1-L只是待审假说，不能先作为统一等待五日否决。当前不实现新层级证明、不改任何上限。',
'', '核验：116日持股估值/交易流/NAV与三行业闭合交易+未实现变化+股息桥通过；原已审book/daily/funding/checkpoint哈希不变。只读分析首版OPEN上下文误用当日close，已改为前决策close并保留analysis-v0-open-clock；原交易账未动。当前快照非PIT、日线OHLCV执行代理与未知权息时点限制不变，不实盘认证。']
(O/'CORE_READOUT.txt').write_text('\n'.join(lines)+'\n')
save('AUDIT_READINESS.json',dict(scope='one compact readonly evidence packet, no account replay',new_indicators=0,new_account_paths=0,new_limits=0,exact_relaxed_order_previews=0,original_financial_hash_matches=verified,
 all_116_close_cashflow_stock_NAV_bridges=True,three_sector_realized_unrealized_dividend_bridges=True,opening_context_corrected_to_previous_decision_close=True,analysis_error_history='analysis-v0-open-clock',
 root_authorized_scope='Jan-Jun2026 original PVR_SLOT1 only; Jul-Oct economic behavior unvalidated; T1-L implementation/coverage paused',primary='CORE_READOUT.txt'))
save('ARTIFACT_SHA256.json',{p.name:h(p) for p in O.iterdir() if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
print('PACKET_READY',O,'source_SHA',h(O/'analyze_readonly.py'),'readout_SHA',h(O/'CORE_READOUT.txt'),'financial_files_verified',len(verified))
print('EXIT_CONTROLS',json.dumps(controls,ensure_ascii=False))
