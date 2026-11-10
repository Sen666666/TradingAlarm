from pathlib import Path
from collections import Counter
from decimal import Decimal
import json,csv,hashlib,math
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
O=R/'mainline_daily_industry_robotics_appendix_v1';OLD=R/'mainline_daily_industry_evidence_v1';B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
oldseal=read(O/'ORIGINAL_OUTPUT_SEAL.json')
assert oldseal==read(OLD/'OUTPUT_SEAL.json')
assert all(sha(OLD/n)==h for n,h in oldseal.items())
expected=(OLD/'build_evidence.py').read_text().replace("O=R/'mainline_daily_industry_evidence_v1'","O=R/'mainline_daily_industry_robotics_appendix_v1'")
a=expected.index('windows=[');b=expected.index('targetsecs=',a)
expected=expected[:a]+"windows=[('ROBOTICS_DECEMBER','自动化与机器人','2024-12-03','2024-12-13')]\n"+expected[b:]
assert (O/'build_appendix.py').read_text()==expected
daily=read(O/'DAILY_EVIDENCE.json');atom=read(O/'MEMBER_DAILY.json');members=read(O/'EVENT_MEMBERS.json');entry=read(O/'FIXED_WINDOW_ENTRY_CLASSIFICATION.json')
p=[x for x in daily if x['cohort']=='BIRTH_PRICE_KNOWN']
hashes=read(O/'SOURCE_HASHES.json');seal=read(B/'OUTPUT_HASHES.json')
def base(n):
 path=B/n;h=sha(path);assert h==seal.get(n,seal.get(str(path))),('BASELINE_DRIFT',n);hashes[str(path)]=h;return read(path)
info=base('INFORMATION_CONFIRMATIONS.json');cp=base('CP_EVENTS.json');orders=base('ORDERS.json');sd=base('SECTOR_DAILY.json')
filled=read(R/'mainline_seed_entry_diagnostic_v1/FILLED_SEED_CLASSIFICATION.json')
ten=[x for x in filled if x['sector51']=='自动化与机器人' and x['seed_day']=='2024-12-05']
assert len(ten)==10 and all(x['phase']=='MATURE' and x['signal_day']=='2024-12-03' and x['plan_day']=='2024-12-04' for x in ten)
rid={x['round_id'] for x in ten};byrid={x['round_id']:x for x in ten}
seedorders=[x for x in orders if x.get('round_id') in rid and x['side']=='BUY_SEED']
assert len(seedorders)==10 and all(x['event_id']=='自动化与机器人|2024-12-03' for x in seedorders)
allrounds={x['round_id'] for x in orders if x.get('event_id')=='自动化与机器人|2024-12-03'}
# Broader sector info includes all previously born positions, not only the 10 new ones.
sector_sids={x['sid'] for x in members}
def first(rows,pred):
 found=[x for x in rows if pred(x)]
 return min((x['day'] for x in found),default=None)
identity=[]
for x in ten:
 r=x['round_id'];i=[z for z in info if z['round_id']==r];c=[z for z in cp if z['round_id']==r]
 market=next(z for z in atom if z['sid']==x['sid'] and z['close_day']=='2024-12-04')
 adds=[z for z in orders if z.get('round_id')==r and z['side']=='BUY_ADD']
 identity.append({k:x[k] for k in ['round_id','sid','name','signal_day','plan_day','seed_day','phase','seed_cost','net','exit_day','exit_reason']}|dict(event_id='自动化与机器人|2024-12-03',G_at_plan=0,CP_market_receipt_at_plan=market['CP_receipt'],CP_market_frontier_at_plan=market['CP_frontier_advance'],
  first_original_post_SEED_CP=first(c,lambda z:z['event']=='CREATED_AFTER_SEED'),
  first_original_CLOSE_pass=first(i,lambda z:z['phase']=='CLOSE' and z['decision']=='INFORMATION_CLOSE_PASS'),
  first_original_OPEN_confirmed=first(i,lambda z:z['phase']=='OPEN' and z['decision']=='INFORMATION_CONFIRMED'),
  original_ADD_count=len(adds),original_ADD_days=[z['day'] for z in adds]))
align=[]
for ds,phase in [('2024-12-04','CLOSE'),('2024-12-05','OPEN'),('2024-12-05','CLOSE'),('2024-12-06','OPEN')]:
 ii=[z for z in info if z['sid'] in sector_sids and z['day']==ds and z['phase']==phase]
 cc=[z for z in cp if z['sid'] in sector_sids and z['day']==ds and z['phase']==phase]
 z=next(x for x in sd if x['sector51']=='自动化与机器人' and x['day']==ds)
 align.append(dict(day=ds,phase=phase,sector_information_events=ii,sector_CP_account_events=cc,
  new_ten_information_events=[x for x in ii if x['round_id'] in rid],
  exported_day_CLOSE_confirmed_stocks=z['information_confirmed_stocks'],
  exported_day_CLOSE_confirmed_not_substituted_for_OPEN=True))
assert not align[0]['sector_information_events'] and not align[1]['sector_information_events']
assert align[0]['exported_day_CLOSE_confirmed_stocks']==align[1]['exported_day_CLOSE_confirmed_stocks']==0
# Explicit atom-to-aggregate and frozen membership checks.
for row in daily:
 scope={x['sid'] for x in members if row['cohort']=='ALL_FIXED' or x['in_'+row['cohort']]}
 aa=[x for x in atom if x['close_day']==row['close_day'] and x['sid'] in scope]
 assert len(aa)==len(scope)==row['N_fixed']
 for field in ['positive','advance','decline','profitable_advance','new_event_high','CP_receipt','CP_frontier_advance']:
  k=sum(x[field]==1 for x in aa);u=sum(x[field]==-1 for x in aa)
  assert (k,u)==(row[field+'_n'],row[field+'_unknown'])
  g=-1 if not len(aa) else 1 if 2*k>len(aa) else 0 if 2*(k+u)<=len(aa) else -1
  assert g==row[field+'_majority']
 assert row['G']==row['profitable_advance_majority']
 if row['event_return_known']==row['N_fixed']:
  assert math.isclose(float(np.median([x['event_return'] for x in aa])),row['event_return_median_exact'],rel_tol=1e-12,abs_tol=1e-12)
assert all(x['birth_day']=='2024-12-03' for x in members)
key=next(x for x in p if x['close_day']=='2024-12-04')
assert (key['N_fixed'],key['profitable_advance_n'],key['G'],key['CP_receipt_n'],key['CP_frontier_advance_n'])==(28,10,0,2,6)
assert first(p,lambda x:x['G']==1)=='2024-12-10' if False else True
recovery=min(x['close_day'] for x in p if x['G']==1)
assert recovery=='2024-12-10'
summary=dict(sector51='自动化与机器人',event_id='自动化与机器人|2024-12-03',birth_day='2024-12-03',
 all_frozen_N=31,birth_price_known_N=28,birth_qualified_N=sum(x['in_BIRTH_QUALIFIED'] for x in members),
 close_1204_G=0,close_1204_profitable_advance=10,close_1204_CP_receipts=2,close_1204_CP_frontier=6,
 market_receipt_names=[x['name'] for x in atom if x['close_day']=='2024-12-04' and x['CP_receipt']==1],
 original_1205_MATURE_count=10,all_ten_WAIT=True,first_industry_G_recovery_CLOSE=recovery,earliest_industry_only_next_OPEN='2024-12-11',
 original_ten_SEED_cost=str(sum((Decimal(x['seed_cost']) for x in ten),Decimal(0))),
 original_ten_full_round_net=str(sum((Decimal(x['net']) for x in ten),Decimal(0))),
 original_ten_ADD_count=sum(x['original_ADD_count'] for x in identity),
 original_path_PnL_not_claimed_as_saving=True)
qa=read(O/'QA.json')
qa.update(dict(original_18_artifacts_unchanged=True,original_OUTPUT_SEAL_unchanged=True,
 builder_diff_only_output_directory_and_requested_window=True,original_formula_and_cohort_unchanged=True,
 independent_aggregate_rows=27,new_market_daily_rows=9,all_ten_round_identity_verified=True,info_CLOSE_and_OPEN_explicitly_separated=True,
 current_real_account_information_not_inherited_into_hypothetical_wait=True,
 primary_event_or_daily_quote_unknown_rows=sum(x['positive_unknown'] or x['advance_unknown'] for x in p),
 W_audit_inherited_same_first_export_day_boundary_as_original=True,
 no_ticket_lifecycle_counterfactual=True,no_candidate_engine_run=True,no_savings_estimate=True))
for path,h in hashes.items():assert sha(path)==h
hashes[str(OLD/'build_evidence.py')]=sha(OLD/'build_evidence.py');hashes[str(OLD/'READOUT.md')]=sha(OLD/'READOUT.md');hashes[str(OLD/'OUTPUT_SEAL.json')]=sha(OLD/'OUTPUT_SEAL.json')
save('TEN_MATURE_IDENTITIES',identity);save('INFO_TIME_ALIGNMENT',align);save('SUMMARY',summary);save('QA',qa);save('SOURCE_HASHES',hashes)
def pc(v):return '未知' if v is None else f'{100*v:+.2f}%'
def n(v):return '无' if v is None else v
text=['# 自动化与机器人 12/5 新 MATURE 盲区：同公式独立附录','',
'## 首结论','',
'**已封存行业方向会等待此例，不会放行 12/5 的 10 个新 MATURE。** 12/4 CLOSE，事件出生可观察固定 28 股仅 10 股已有出生后正价差且当天继续涨，18 股下跌，中位数 −1.23%；G=F。当天确实有 2 个原市场 CP receipt、6 个 frontier 推进，不能说“没有 CP”。',
'',
'12/5 CLOSE 推进 14/28 恰好一半，按原严格多数仍 F。原公式第一次恢复是 12/10 CLOSE 的 22/28，最早只支持 12/11 OPEN 重新审查行业条件。未验证这 10 张原票各自是否届时仍存续、是否满足原 F/CP 与经济/资金/开盘约束，更没有新账户收益；不能把原合亏 4,180.03 元直接算作节省。',
'',
'## 1. 与已封存主研究的关系','',
'- 原 mainline_daily_industry_evidence_v1 的 18 份封存产物及 OUTPUT_SEAL 均逐字节未变。这里是独立目录、独立封条。',
'- build_appendix.py 与原 build_evidence.py 的文本差异只有输出目录及指定的单段 windows。固定集合、三值、严格多数、价格/CP 检查和公式不变，没有因结果改分母或天数。',
'- 仅本地冻结 93 日账户截至 2025-01-20，附录价格展示 2024-12-03 至 12-13 共 9 个 CLOSE。无联网、无新源、无 history、无候选账户重放。',
'- 行业当前分类、原股票总体及历史复权价格仍继承非 PIT 局限。出生可观察集合防止本次未来收益/未来持仓择样，不能补出缺失的历史成分档案。',
'',
'## 2. 固定公式与三个分母','',
'G_e(t)=严格多数 { i∈出生当日报价可知固定集合：C_i(t)>C_i(b_e) 且 C_i(t)>C_i(t−1) }。',
'',
'出生为 12/3 CLOSE。主集合固定 N_e=28；ALL_FIXED 原 N=31，出生缺报价 3 个始终作为未知保留在其对照分母；出生 stock/I/价线合格的固定子集 N_q=17，仅描述、不改用。缺失比例取 [k/N,(k+u)/N]：2k>N 为 T，2(k+u)≤N 为 F，否则 U。出生首日相对出生收益为 0。未知不补 false，平盘不当上涨。',
'',
'12/4 三种分母结果都为 F：主集合 10/28，原全集已知 10/31、未知3（即使全未知都真也只有13/31），出生合格集合 7/17。主集合当天价格覆盖完整，中位−1.228889%；原 N 的全体中位保守区间为[−1.388224%,−1.015228%]，不是把缺报价填零后求中位。','',
'## 3. 完整逐日市场证据','',
'正价差指相对12/3出生收盘为正；推进指同股正价差且当日上涨。所有主表分母均28。事件新高为超过出生以来此前最高收盘，不是20日新高。CP直接读取原市场CP1 receipt/frontier，未重算模型。G不取代行业状态/I/个股资格。',
'',
'| CLOSE → nextOPEN | state/M; S/F | 出生正 / 当日推进 | 出生收益中位 | 涨/跌/平 | 事件新高 | CP receipt/frontier | E / ΔE | G | 原次日EVENT/MATURE |',
'|---|---|---|---:|---|---:|---|---|---|---|']
for x in p:
 flat=x['advance_known']-x['advance_n']-x['decline_n']
 text.append(f"| {x['close_day']} → {x['next_OPEN']} | {x['state']}/{x['M']}; {x['S']}/{x['F']} | {x['positive_n']}/28 ; {x['profitable_advance_n']}/28 | {pc(x['event_return_median_exact'])} | {x['advance_n']}/{x['decline_n']}/{flat} | {x['new_event_high_n']} | {x['CP_receipt_n']}/{x['CP_frontier_advance_n']} | {x['E']:.6f} / {x['raw_delta_E']:+.6f} | { {1:'T',0:'F',-1:'U'}[x['G']] } | {x['next_OPEN_actual_EVENT']}/{x['next_OPEN_actual_MATURE']} |")
text+=['',
'12/3 出生当天 G=F 不改变 EVENT：原 12/4 OPEN 的均普智能、捷昌驱动、拓斯达 3 个试仓仍按原规则进行。12/4 原 M 首次为1、Q/S/F=1/1/0、n16/K28/U3，仍不能把已有股票结构宽度等同当天价格继续推进。12/6行业state未知、12/9 M未知，表保留，不用 G 推进未知原资格。12/13行业false，原取消/退出优先，G不重新出生事件。',
'',
'## 4. 原市场 CP 与真正 post-SEED 信息确认不是一件事','',
'12/4 CLOSE 的两个原市场 receipt 是：',
'- 机器人（300024.SZ）：相对12/3上涨14.54%，receipt真、frontier推进真；但这次新轮实际要到12/5 OPEN才SEED。',
'- 埃斯顿（002747.SZ）：相对12/3上涨4.21%，receipt真、frontier推进真；同样在12/5 OPEN才SEED。',
'',
'其余有 frontier 推进的是怡合达、固高科技、绿的谐波、均普智能。局部领先股可以真实推进，同时行业多数回吐。不能把两个 receipt 擦掉，也不能把它们叫本轮 SEED 之后的确认。',
'',
'严格时间对齐：',
'| 时点 | 当时实际可知的信息 |',
'|---|---|',
'| 12/4 CLOSE | 原行业 information_confirmed_stocks=0；此刻10个新MATURE轮尚未SEED。原INFO日志无本行业CLOSE信息通过，市场CP仍有机器人/埃斯顿两个receipt。 |',
'| 12/5 OPEN | 10个MATURE在原路径实际SEED；原INFO日志没有本行业OPEN确认。不能借12/4的pre-SEED receipt变成本轮post-SEED CP，也不能前读12/5 CLOSE。 |',
'| 12/5 CLOSE | 原雷赛智能新MATURE轮、均普智能先前EVENT轮各有CREATED_AFTER_SEED和INFORMATION_CLOSE_PASS。该日晚导出的confirmed仍0，因为还没到次OPEN确认。 |',
'| 12/6 OPEN | 上述两轮才出现INFORMATION_CONFIRMED，原各实际ADD。 |',
'',
'这里的 post-SEED 按原实现包含实际SEED当日收盘。以上都是原账户事实；如果新种子被WAIT而未实际SEED，其原雷赛12/5确认不能自动继承到假设路径。所有更晚信息也只能按当日可知使用。','',
'## 5. 10个原实际 MATURE 的身份与确认时间','',
'全体 event_id=自动化与机器人|2024-12-03，signal_day=12/3、计划CLOSE=12/4、SEED OPEN=12/5、phase=MATURE。身份及费用支出逐项对照基线ORDERS，无股票简称猜配。',
'',
'| 股票 / sid | 原 round_id | 12/4市场receipt | 原首次本轮CP | 原首次CLOSE信息通过 | 原首次OPEN确认 | 原ADD笔数 |',
'|---|---|---:|---|---|---|---:|']
for x in identity:
 text.append(f"| {x['name']} / {x['sid']} | {x['round_id'].replace('|',' / ')} | {x['CP_market_receipt_at_plan']} | {n(x['first_original_post_SEED_CP'])} | {n(x['first_original_CLOSE_pass'])} | {n(x['first_original_OPEN_confirmed'])} | {x['original_ADD_count']} |")
text += ['',
f"原10笔SEED现金支出 {Decimal(summary['original_ten_SEED_cost']):,.2f} 元；后续原10轮共 {summary['original_ten_ADD_count']} 个 ADD，原完整轮合计净 {Decimal(summary['original_ten_full_round_net']):,.2f} 元。这是原路径规模与结果，不是G能节省的金额。未做资金回流、替代持仓、重新入场、ADD或NAV闭环。",
'',
'## 6. 这一附录增加了什么、没有增加什么','',
'它证明原已提出的行业进展方向能触及“没有赢家供资、没有ADD竞争、现金富余却批量新MATURE”的这一实际输入盲区。这个例子不是靠新的风险池、利润覆盖要求或强制多等天数解决，而是在12/4已知收盘价格上发现多数尚未推进。',
'',
'但它不推翻主报告的证券11/7等反例，也不证明该方向总体更优。12/10行业G恢复，真票可能恢复、降级或已按原条件取消，均须完整状态机验证。没有把10轮永久删除，没有叠加资金约束，没有发起候选或history。',
'',
'## 7. 交付与验证','',
'- DAILY_EVIDENCE：9日×3固定集合=27行完整指标；MEMBER_DAILY：31股×9日=279条原子证据；EVENT_MEMBERS：出生固定名单及未知。',
'- TEN_MATURE_IDENTITIES：10轮身份、市场CP与原post-SEED确认逐笔对齐；INFO_TIME_ALIGNMENT：原CLOSE/OPEN日志及边界；SUMMARY/QA：结论与检验。',
'- 27行按成员原子值独立聚合重验；原公式文本仅输出目录/窗口差异验证；原18份封存产物与原封条、消费源哈希、基线关键导出均复核未变。',
'- 原全集缺失保持三值，出生可观察主集合本窗价格完整；这不删除未来可能出现的未知分支。原E审计继承主报告“首导出日1行W缺前日数值”的披露。',
'- SOURCE_HASHES与独立OUTPUT_SEAL提供追溯；没有修改主报告或策略。','']
(O/'READOUT.md').write_text('\n'.join(text))
assert all(sha(OLD/n)==h for n,h in oldseal.items()) and oldseal==read(OLD/'OUTPUT_SEAL.json')
save('OUTPUT_SEAL',{f.name:sha(f) for f in O.iterdir() if f.is_file() and f.name!='OUTPUT_SEAL.json'})
print(json.dumps(dict(summary=summary,qa=qa,report_sha256=sha(O/'READOUT.md')),ensure_ascii=False))
