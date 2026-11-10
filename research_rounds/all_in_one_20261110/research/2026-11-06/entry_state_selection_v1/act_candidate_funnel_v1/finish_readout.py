"""Summarize derived candidate traces; no account replay or return simulation."""
from pathlib import Path
from collections import Counter
import pandas as pd
import json, hashlib
O=Path(__file__).resolve().parent
def csv(n,x):pd.DataFrame(x).to_csv(O/n,index=False)
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
periods=json.loads((O/'CONTRACT.json').read_text())['periods']
df=pd.read_parquet(O/'ROLE_CANDIDATE_TRACE.parquet')
sf=pd.read_csv(O/'STOCKDAY_FUNNEL.csv');sf['stage']=sf.stage.replace({'01b_NATIVE_STRUCTURE_KNOWN':'01b_ACTIVE_NATIVE_STRUCTURE_PRESENT'});sf.to_csv(O/'STOCKDAY_FUNNEL.csv',index=False)
c=pd.read_csv(O/'CONSUMER_COVERAGE.csv').rename(columns={'within_sector_competitive_candidate_stockdays':'within_sector_coexisting_candidate_stockdays','within_sector_competitive_day_sectors':'within_sector_coexisting_day_sectors'})
c['interpretation']='Same-day same-sector coexisting candidates only. Not evidence of shared-budget competition, rank-caused rejection, or feasible swaps.'
c.to_csv(O/'CONSUMER_COVERAGE.csv',index=False)
f=pd.read_csv(O/'ROLE_FUNNEL.csv')
if 'fresh_CP1_events' in f:
 f=f.rename(columns={'fresh_CP1_events':'coincident_CP1_observations'});f['mobile_fresh_CP1_events']=f.coincident_CP1_observations.where(f.role.eq('mobile'))
f.to_csv(O/'ROLE_FUNNEL.csv',index=False)
previews={'missing_open','open_at_or_below_protection','open_minimum_exceeds_frozen_contract'}
df['open_results']=df.open_result.map(lambda v:[q for q in v.split(';') if q])
df['route_entered']=df.open_results.map(lambda v:bool(v) and not any(x in previews for x in v))
df['positive_reserve']=df.open_results.map(lambda v:'reserved' in v)
df['budget_rejected']=df.open_results.map(lambda v:any(any(x in y.split(',') for x in ['cash_or_original_reserve','pool_capital','probe_risk','sector_capital','sector_risk','stock_capital','minimum_unit_not_funded']) for y in v))
df['right_censored_pending']=df.original_pending & df.signal_day.eq('2026-05-15') & df.open_result.eq('')
routes=[];why=[];opendays=[]
for period,(lo,hi) in periods.items():
 q=df[df.signal_day.between(lo,hi)]
 for (arm,role,held),g in q.groupby(['account','role','held_at_signal']):
  for scope,z in [('ALL_OBSERVED_ROLES',g),('LEGAL_ACTIVE_RANKED',g[g.legal_ranked])]:
   routes.append(dict(account=arm,period=period,role=role,held_at_signal=held,scope=scope,role_rows=len(z),native_pending=int(z.original_pending.sum()),logged_open_attempts=int(z.open_result.ne('').sum()),entered_original_route=int(z.route_entered.sum()),industry_invalidated=int(z.open_results.map(lambda v:'industry_invalidated' in v).sum()),budget_rejected=int(z.budget_rejected.sum()),positive_reserve=int(z.positive_reserve.sum()),actual_buy_orders=int(z.actual_buy.sum()),actual_first_entry_orders=int(z.actual_first_entry.sum()),same_stock_other_role_reserved=int(z.exclusive_role_stage.eq('SAME_STOCK_OTHER_ROLE_RESERVED').sum()),right_censored=int(z.right_censored_pending.sum())))
   last=routes[-1]
   assert last['native_pending']==last['logged_open_attempts']+last['same_stock_other_role_reserved']+last['right_censored'],last
   assert last['entered_original_route']==last['industry_invalidated']+last['budget_rejected']+last['positive_reserve'],last
   cnt=Counter(x for results in z.open_results for result in results for x in result.split(','))
   for reason,n in cnt.items():why.append(dict(account=arm,period=period,role=role,held_at_signal=held,scope=scope,reason=reason,role_rows=n,overlap=True))
 for (arm,day),g in q[q.original_pending].groupby(['account','signal_day']):
  opendays.append(dict(account=arm,period=period,signal_day=day,pending_stockdays=g.sid.nunique(),pending_role_intents=len(g),flat_pending_stockdays=g.loc[~g.held_at_signal,'sid'].nunique(),held_add_intents=int(g.held_at_signal.sum()),entered_route_roles=int(g.route_entered.sum()),positive_reserve_orders=int(g.positive_reserve.sum()),actual_first_entry_orders=int(g.actual_first_entry.sum()),budget_rejected_roles=int(g.budget_rejected.sum()),industry_invalidated_roles=int(g.open_results.map(lambda v:'industry_invalidated' in v).sum())))
csv('EXACT_ROUTE_AND_ORDER_COUNTS.csv',routes);csv('OVERLAPPING_OPEN_REASONS_BY_ROLE.csv',why);csv('CLOSE_TO_OPEN_PENDING_COUNTS.csv',opendays)
e=pd.read_parquet(O/'NATIVE_BIRTH_STAGE_MEMBERSHIP.parquet');out=pd.read_csv(O/'ACTUAL_NATIVE_BIRTH_OUTCOMES.csv');roster=[]
for (period,scope,stage),g in e[e.holding_scope.eq('FLAT')&e.stage.isin(['POSITIVE_SIZE_RANKED','ACTUAL_FIRST_ENTRY'])].groupby(['period','holding_scope','stage']):
 p=set(g[g.account.eq('PVR')].native_birth);n=set(g[g.account.eq('NOACT')].native_birth)
 for b in p|n:roster.append(dict(period=period,holding_scope=scope,stage=stage,native_birth=b,membership='COMMON' if b in p&n else 'PVR_ONLY' if b in p else 'NOACT_ONLY'))
roster=pd.DataFrame(roster)
for arm in ['PVR','NOACT']:
 a=out[out.account.eq(arm)].drop(columns=['account']).rename(columns={k:arm+'_'+k for k in out.columns if k not in ['account','native_birth']})
 roster=roster.merge(a,on='native_birth',how='left',validate='many_to_one')
roster.to_parquet(O/'NATIVE_BIRTH_CROSS_ARM_ROSTER.parquet',index=False)
dump('STAGE_DEFINITIONS_AND_UNKNOWNS.json',{
 'stockday':'one arm + signal day + stock; CORE and MOBILE may coexist but stock counts once',
 'role_stockday':'one arm + signal day + stock + CORE/MOBILE; CORE is always flat; MOBILE may be flat or held',
 'order':'a real positive reservation, not a pending intent; all 7868 reservations filled in these frozen outputs',
 'first_entry':'real layer marked initial_layer in audited 0->0/open round ledger; includes open rounds, unlike completed-round count',
 'native_birth':'stock plus native E0 structure birth from segment on transition, not original-I big60, not CP1 id, not round_id; one birth may support several CP1 and actual rounds',
 'native_structure_absence':'E0 off has no active native structure. The full-universe 01b count means active structure present, not missing-data coverage. Every observed role and actual buy has a known matching native birth',
 'full_universe':'fixed future 1709-stock sample x 1054 account dates, not the entire contemporaneous Chinese market',
 'market_layer':'original ACT on/off is the only market admission layer counted. No new breadth gate is introduced',
 'sector_signal':'original eligibility sector_up; false/unknown reconstructed from complete original rejection reasons. Continuing MOBILE changes buy_allowed only, never sector eligibility',
 'industry_active':'original frozen E0_valid, nonnull attempt_id, stage>0. Original code checks this at OPEN route, not before sorting. The analytical funnel moves this known close state earlier only to partition potential consumers, not to claim native execution order changed',
 'exclusive_stockday':'first-failed hierarchy ACT -> sector signal -> industry active -> stock fresh Q -> role/epoch -> pending -> close size -> open checks -> budget -> fill. Failure causes overlap and hierarchy is accounting, not independent causal attribution',
 'signal_vs_execution':'period funnels use signal day including next open outside period. First_entry_two_clocks explicitly reports both. 2024 signal count558/703 differs from execution553/698; 2026Jan signal57/58 differs execution51/59',
 'raw_rank_consumer':'all native positive-size pending stock slots, including inactive industries that later fail route. Legal active flat subset is a research comparison domain, not a newly imposed prefilter',
 'rank_cutoff':'none. All pending slots retained. Rank-only no new names, no K20, no role change, no standalone rank rejection reason',
 'same_sector_coexistence':'at least two legal flat stocks coexist on same day in same sector. This is comparison coverage only, not observed binding budget competition. Cash competes across sectors and both pool routes also matter',
 'swap_feasibility':'UNKNOWN: whether exchanging two candidates or changing order yields a different fill, quantity, future holdings or return needs a fixed dynamic counterfactual; not performed in this task',
 'no_signal':'not cash rejected. Cash/risk reason counts only from original open funding records and remain overlapping',
 'untraded_returns':'UNKNOWN. Outcome columns remain absent if this arm never has an actual round at that native birth. Later actual winner at same birth is descriptive event coverage, not a candidate-specific counterfactual return',
 'win_definition':'completed actual round net >0 including all ADD and fees; 30pct denominator total actual BUY cost including fees and all ADD. Birth winner means every actual round at that birth closed and aggregate net>0; not every round wins',
 'other_unknowns':['fixed future universe and current industry membership NON-PIT','external historical execution/queueing/tradability UNKNOWN','new score effectiveness UNKNOWN; no fit, new signal gate or account rerun','last close has no following in-sample OPEN and remains right-censored'],
 'old_queue':'old PVR empty-MOBILE53121 exact key/CP1/rank/PVR identity; old E31 is excluded. NOACT67305 rebuilt separately. The old M3 limited-K shadow queue and its 78.71% statistic are different domains and not reused'})
sf=pd.read_csv(O/'STOCKDAY_FUNNEL.csv');over=pd.read_csv(O/'NATIVE_BIRTH_CROSS_ARM_OVERLAP.csv');co=pd.read_csv(O/'ACTUAL_FIRST_ENTRY_COHORT_OUTCOMES.csv');ex=pd.read_csv(O/'EXCLUSIVE_STOCKDAY_STAGES.csv');rr=pd.DataFrame(routes)
def s(arm,period,stage):return int(sf[(sf.account==arm)&(sf.period==period)&(sf.stage==stage)].stockdays.iloc[0])
def fmt(v):return f'{v:,}'
def mdtable(frame):
 cols=list(frame.columns);lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
 for row in frame.itertuples(index=False,name=None):lines.append('| '+' | '.join(str(x) for x in row)+' |')
 return '\n'.join(lines)
lines=['# 原PVR/NOACT初仓候选漏斗：只读原账诊断','',
 '## 结论','',
 '能直接研究首仓成员质量的消费者在“原角色与尺寸合格后、原PVR逐股票槽排序前”。全期行业active、空仓且正尺寸候选为PVR 116,831、NOACT 154,944个stock-day；实际首买2,693/3,131笔。它们不是独立样本，也不是已证明能够互换的成交名额。',
 '原PVR没有Top-K删选：所有原pending都保留，只改变OPEN处理顺序。CORE与MOBILE同股耦合、CORE先行；跨行业共用现金、probe/confirmed路线共同约束。此处没有“排名淘汰了多少”的独立日志，不能把预算拒绝全部归因于排名。',
 '同日同行至少2个合法空仓候选并存的覆盖为107,455/142,934个stock-day，约91.98%/92.25%。这支持有范围地研究同业成员质量，只是可比较覆盖；不证明每一次换序都会改变成交，也不是实际预算竞争比例。',
 '旧PVR独立合法empty-MOBILE队列53,121条与本次精确一致；NOACT独立重建67,305条，不能拿旧E31或旧影子M3/K20结果代替。两臂empty-MOBILE按day+sid共同51,741、PVR独有1,380、NOACT独有15,564。',
 '', '## 冻结与分母','',
 '原act_only_ablation_continuous_v1已完成的PVR/NOACT，2022年初120万元空仓到2026-05-15，1054共同交易日，固定1709股/90行业。唯一经济变化仍为NOACT去ACT强平/暂停；本分析account_runs=0、indicator_runs=0，不加载账户引擎，不改旧文件。原48项产物哈希与1799份出生/行业辅助源均核验。',
 '“全市场”以下只指固定1709研究池，不冒充历史全A股。stock-day是一臂×信号收盘日×股票；role-stockday再拆CORE/MOBILE。一个stock-day可有双角色。CP1是新证事件，nativebirth是股票+原E0 segment内0→1出生，实际round为真实0→0或仍未闭回合，四者不可相加或互换。',
 '主漏斗按信号日归窗；成交按对应实际signal_at匹配。另附实际执行日期口径，避免把12月31日信号后的1月首买放错年。完整回合结果截至2026-05-15，只归实际首买执行期，未成交不补收益。',
 '', '## 全期互斥stock-day漏斗','',
 '分桶优先级为ACT→行业G资格→行业active→个股fresh Q→角色/epoch→尺寸→OPEN检查→预算→实际买。它是首个失败阶段的会计分解，原行业active事实上到OPEN route才检查；不能当成原代码先行业预筛或互相独立的因果损失。无信号绝不记为现金拒单。']
x=ex[ex.period.eq('ALL')].pivot(index='exclusive_stage',columns='account',values='stockdays').fillna(0).astype(int).reset_index();lines+=['',mdtable(x),'', '每臂各阶段合计1,801,286 stock-day，精确等于1709×1054。最后一日未执行pending保留右截尾；没有无日志的planned/no-plan残差。']
main=[]
for p in periods:
 for a in ['PVR','NOACT']:
  row=c[(c.account==a)&(c.period==p)].iloc[0]
  main.append(dict(窗口=p,账户=a,固定池stockday=s(a,p,'01_FIXED_UNIVERSE'),ACT开=s(a,p,'02_ACT_ON'),再过行业G=s(a,p,'03_ACT_ON_SECTOR_SIGNAL_PASS'),再过行业active=s(a,p,'04_ACT_ON_SECTOR_SIGNAL_AND_ACTIVE'),再有freshQ=s(a,p,'05_ALL_ABOVE_FRESH_SIGNAL_Q'),合法正尺寸股票日=s(a,p,'07_LEGAL_POSITIVE_SIZE_RANKED'),其中flat=int(row.flat_legal_ranked_stockdays),实际首买信号归窗=int(row.actual_first_entries)))
lines+=['','## 指定五个窗口','',mdtable(pd.DataFrame(main)),'','上表“合法正尺寸”含已有持仓MOBILE；其中flat单独作为首仓消费者。ACT暂停外的原Q可以仍true，但不能形成该臂的待买。原stock Q独立于ACT，全期两臂均214,286个fresh-signal-Q股票日。']
lines+=['','## CORE、空仓MOBILE、已有持仓ADD','',mdtable(f[f.period.eq('ALL')&f.stage.isin(['ROLE_OBSERVED','POSITIVE_SIZE_RANKED','ACTUAL_BUY'])][['account','role','held_at_signal','stage','role_stockdays','native_birth_events']]),'',
 '全期实际初买PVR CORE879+空仓MOBILE1814=2693；NOACT CORE1075+空仓MOBILE2056=3131。另有已有持仓MOBILE ADD937/1107，不能加进初仓数。闭合初买回合只有2626/3064，另各67仍未闭，因此不能把首买2693/3131写成完整回合数。',
 '同股双角色flat stock-day42,908/54,613，故CORE106,618+MOBILE53,121不能直接相加作PVR股票数。CORE没有CP1角色事件要求，表中的偶遇CP1只作观察；MOBILE独立CP1事件数与其role-stockday相同。']
rview=rr[rr.period.eq('ALL')&rr.scope.eq('ALL_OBSERVED_ROLES')][['account','role','held_at_signal','native_pending','logged_open_attempts','entered_original_route','industry_invalidated','budget_rejected','positive_reserve','actual_first_entry_orders','same_stock_other_role_reserved']]
lines+=['','## 可精确核的排序后OPEN路径','',mdtable(rview),'',
 '原全部pending unique-stock日数PVR144,926/NOACT194,978，包含当时行业inactive、到OPEN才被route拒绝的股票。只研究合法active子集时相应121,938/161,328；不能把子集误称原完整排序队列。两臂452,208条pending角色均精确对应原rank-policy，排名自身删减0条。',
 'entered_original_route从OPEN原日志及preview顺序核定，不把missing_open或开盘价格/尺寸preview拒绝算已过route。positive_reserve与实际BUY全期均7,868笔；一股同日CORE先保留时MOBILE被跳过另列，不能叫资金拒绝。OVERLAPPING_OPEN_REASONS_BY_ROLE.csv分别列现金、probe风险、行业资本/风险等可同时出现的原拒因，不把原因行数相加当拒单笔数。',
 'CLOSE_TO_OPEN_PENDING_COUNTS.csv给每个信号日的原完整pending股票数/角色数、实际route进入、reserve、初买与拒绝数。可核的是这些原账事实。换序是否可行、是否改成交量或未来状态均UNKNOWN，需另做固定动态反事实，本任务未执行。']
ov=over[over.holding_scope.eq('FLAT')&over.stage.isin(['POSITIVE_SIZE_RANKED','ACTUAL_FIRST_ENTRY'])]
lines+=['','## 同一nativebirth的覆盖','',mdtable(ov.drop(columns='holding_scope')),'',
 '全期原有flat角色的nativebirth两臂均28,229；行业active及尺寸后的可排序事件19,225/23,824，实际首买事件2,575/2,999。共同实际首买事件2038，PVR独有537、NOACT独有961。一出生可多次重入，故事件数小于初买笔数。局部窗口只表示该窗口有相应候选/首买，不按birth年份归窗。',
 'NATIVE_BIRTH_CROSS_ARM_ROSTER.parquet提供每个出生、阶段及单臂/共同成员清单。不是原I big60事件；没有重用4359 big60分母，也不跨臂按round_id匹配。']
cv=co[co.period.eq('ALL')][['account','initial_role','first_entries','complete_rounds','open_rounds','complete_winners','complete_win_rate','complete_30pct_rounds','complete_round_net']].copy();cv['complete_win_rate']=cv.complete_win_rate.map(lambda x:f'{x:.2%}');cv['complete_round_net']=cv.complete_round_net.round(2)
lines+=['','## 实际后来赢家与30%完整净回合，只作事后描述','',mdtable(cv),'',
 'PVR 73、NOACT104个≥30%实际完整回合来自所有实际BUY含费本金分母，包含ADD。初买MOBILE分别贡献52/76个，CORE21/28个。它们不能转成未入选候选的获利标签，不能以“后来赢过”反选当时候选。',
 'POSTHOC_ACTUAL_WINNER_COVERAGE.csv列各层nativebirth后来在同臂是否确有闭合总净赢家/≥30%实际回合，以及该臂完全无实际回合的数量。无回合只写缺失、不标输也不标赢；某个birth另日后来成交获利只说明事件覆盖，不意味着此前任一未成交stock-day按当时买入也获利。',
 'ACTUAL_FIRST_ENTRY_COHORT_OUTCOMES.csv给五窗口按实际首买执行日归组的闭合/未闭/胜率/右尾。2024实际首买553/698与信号归窗558/703不同；2026Jan为执行51/59、信号57/58。不得混用。这是同开发样本已见历史，不是新成员质量alpha检验。',
 '', '## 下一层可改什么，不能据此声称什么','',
 '1. 市场层ACT只控制能否继续候选/持有；取消ACT扩大合法首仓覆盖，但全账户与CORE胜率并未普遍提升。本漏斗不另建议新的全市场硬门。',
 '2. 行业层有原G资格与active授权两道不同约束；行业公共特征可改变行业间优先级，却不能自行区分同业个股成员。',
 '3. 个股层最直接的首仓质量消费者，是合法空仓CORE/MOBILE的逐股票优先级；同业并存覆盖大，值得在同一原合法域内比较事前个股推进/风险，而非扩张资格后把新增交易视为提升。',
 '4. 收盘资格、角色和尺寸先于预算实现；真正改排序会改变同股CORE/MOBILE竞争、现金/池分配及后续空仓状态，所以旧独立MOBILE K20只能作诊断，不可直接当作只改一个键的账户因果证明。',
 '5. 此处只定位消费者和覆盖，不新增评分、不扫描参数、不做新账户大回测。固定未来池/当前行业NON-PIT、外部历史可交易性UNKNOWN等限制保持。',
 '', '## 文件与复验','',
 'analyze_readonly.py重建原trace及主表；finish_readout.py只读新trace生成route补充与本报告。QA.json和INPUT_SHA256.json保存检验与原源hash。旧数据未改、经济账户运行0。',
 '- STOCKDAY_FUNNEL.csv / EXCLUSIVE_STOCKDAY_STAGES.csv：股票日累计与互斥漏斗。',
 '- ROLE_FUNNEL.csv / EXCLUSIVE_ROLE_STAGES.csv / ROLE_CANDIDATE_TRACE.parquet：角色、空仓/持仓、nativebirth及逐条原结果。',
 '- EXACT_ROUTE_AND_ORDER_COUNTS.csv / OVERLAPPING_OPEN_REASONS_BY_ROLE.csv / CLOSE_TO_OPEN_PENDING_COUNTS.csv：原route、订单与重叠拒因。',
 '- CONSUMER_COVERAGE.csv / FIRST_ENTRY_TWO_CLOCKS.csv：首仓研究域、同业并存和双日期口径。',
 '- NATIVE_BIRTH_CROSS_ARM_OVERLAP.csv / NATIVE_BIRTH_CROSS_ARM_ROSTER.parquet：统一出生事件两臂共同/单臂。',
 '- ACTUAL_NATIVE_BIRTH_OUTCOMES.csv / POSTHOC_ACTUAL_WINNER_COVERAGE.csv / ACTUAL_FIRST_ENTRY_COHORT_OUTCOMES.csv：仅实际交易的事后结果。',
 '- OLD_EMPTY_MOBILE_QUEUE_IDENTITY.json：旧PVR空仓MOBILE的精确同源验证。',
 '- STAGE_DEFINITIONS_AND_UNKNOWNS.json：定义、优先级、字段边界与UNKNOWN。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
dump('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print(pd.DataFrame(routes)[lambda f:f.period.eq('ALL')].to_string(index=False))
print('READOUT_READY')
