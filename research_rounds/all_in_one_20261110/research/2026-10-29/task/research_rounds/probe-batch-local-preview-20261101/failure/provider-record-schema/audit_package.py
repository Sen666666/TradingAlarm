"""Bounded input/lineage checks and compact readout; no new allocation policy."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,inspect,collections,math
import pandas as pd
import planner as P
O=P.O;W=P.W
def read(n):return json.loads((O/n).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
    p=O/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
def pool_resources(r,pool):
    s=r['final_state'];orders=[x for x in s['orders'].values() if x['pool']==pool and x['qty']>0 and x['status'] in ['open','cancel_pending']];lots=[x for x in s['lots'] if x['pool']==pool]
    return dict(capital=sum(x['qty']*x['limit'] for x in orders)+sum(x['qty']*s['prices'][x['stock']] for x in lots),risk=sum(x['qty']*max(0,x['limit']-x['floor']) for x in orders)+sum(x['qty']*max(0,s['prices'][x['stock']]-x['floor']) for x in lots))

assert read('SYNTHETIC_RESULTS.json')['passed'] and read('HARD_LIMIT_RESULTS.json')['passed'] and read('REAL_PREVIEW_SUMMARY.json')['passed']
assert all(sha(p)==h for p,h in read('CODE_FREEZE.json')['sha256'].items())
views={d:read(d+'_INPUT_VIEW.json') for d in ['2023-01-20','2022-06-29']}
ids=sorted({i['sid'] for v in views.values() for i in v['intents']})
# Price-only check against original native raw inputs, not another allocation run.
_,m,_=P.J.M.context('2023-01-20',ids=ids);checks=[];native_sources={}
for day,v in views.items():
    for i in v['intents']:
        f=m.raw[i['sid']];d=pd.Timestamp(day);exists=d in f.index and math.isfinite(float(f.loc[d,'open'])) and float(f.loc[d,'open'])>0
        if i['preview']:
            assert exists and D(str(f.loc[d,'open']))==D(i['preview']['known_open'])
            checks.append(dict(day=day,sid=i['sid'],role=i['role'],native_raw_open=str(f.loc[d,'open']),passed=True))
        elif i['preview_failure']=='missing_open':assert not exists
        rec=m.bundle.series[i['sid']].record;sig=rec['files']['signal'];native_sources[i['sid']]=dict(recorded_signal=sig)
save('NATIVE_OPEN_PRICE_CHECK.json',dict(passed=True,role_intents_checked=len(checks),missing_opens_preserved=2,native_context_only=True,no_account_or_planner_progression=True,checks=checks,source_records=native_sources,provider_manifest=dict(path=str(P.J.M.P/'manifest.json'),sha256=sha(P.J.M.P/'manifest.json'))))
floorchecks=[];data=[]
roots={'2023-01-20':W/'recovery-2023-readiness-20261101/runs/Bdiag/pair','2022-06-29':W/'2022-normal-reference-20261031/runs/B_diag/pair'}
meta=json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text())
for day in views:
    old=read(day+'_BASELINE_IDENTITY.json')['baseline'];new=read(day+'_TWO_PASS.json');comparison=read(day+'_COMPARISON.json')
    with gzip.open(roots[day]/'B.json.gz','rt') as f:book=json.load(f)
    for o in old['orders']:
        actual=book['budget']['orders'][o['key']]
        assert abs(float(o['floor'])-actual['floor'])<1e-9 and abs(float(o['price'])-actual['limit'])<1e-9
        floorchecks.append(dict(day=day,key=o['key'],original_raw_floor=actual['floor'],planning_raw_floor=o['floor'],passed=True))
    extra=[]
    for x in comparison['changes']:
        sid=x['sid'];extra.append(dict(**x,name=meta[sid]['name'],sector=meta[sid]['sector_id'],two_pass_blocked_roles=[r for r in new['rejected'] if r['sid']==sid]))
    data.append(dict(day=day,comparison=comparison,change_details=extra,pool_resources={name:{p:pool_resources(r,p) for p in ['probe','confirmed']} for name,r in [('baseline',old),('two_pass',new)]},
        no_order_migration_attempts={name:sum(e['candidate'] not in {x['key'] for x in r['orders']} for e in r['migrations']) for name,r in [('baseline',old),('two_pass',new)]},
        rejection_counts={name:dict(collections.Counter(x['reason'] for x in r['rejected'])) for name,r in [('baseline',old),('two_pass',new)]},
        original_named_frozen_intent_membership={sid:[dict(role=i['role'],rank=i['rank']) for i in views[day]['intents'] if i['sid']==sid] for sid in ['300308.SZ','300502.SZ']}))
save('PLANNED_FLOOR_IDENTITY.json',dict(passed=True,original_orders=len(floorchecks),checks=floorchecks))
save('MECHANISM_DETAILS.json',data)
(O/'derived_full_target_evaluation.py').write_text(P.EVAL_SOURCE)
(O/'derived_fixed_pool_predicate.py').write_text(P.PRED_SOURCE)
(O/'FROZEN_NATIVE_BDIAG_ROUTE.py').write_text(P.ROUTE_SOURCE)
save('SOURCE_DERIVATION.json',dict(native_route_path=str(P.ROUTE_PATH),native_route_SHA=sha(P.ROUTE_PATH),oracle_body_unmodified=True,eval_only_admission_tail_removed=True,predicate_body_exact_slice=True,derived_sources={p.name:sha(p) for p in [O/'derived_full_target_evaluation.py',O/'derived_fixed_pool_predicate.py',O/'FROZEN_NATIVE_BDIAG_ROUTE.py']},native_methods={n:dict(path=inspect.getsourcefile(fn),file_SHA=sha(inspect.getsourcefile(fn))) for n,fn in [('resources',P.N.Contract.resources),('valid',P.N.Contract.valid),('migrate',P.N.Contract.migrate),('request',P.N.Contract.request),('maximum_quantity',P.LR.maximum_quantity),('preview',P.LR.preview)]}))

lines=['两固定开盘：纯分配规划器局部工程验证；无新财务路径／成交／PnL','',
'真实机制结论：1/20没有扩大整体股票覆盖，36单→34单，新增4股、失去6股，中际未解锁。保留core优先后，新的core最小预留还能阻止同行业后续迁池，挤掉confirmed mobile；这已在真实固定输入发生，不只是合成反例。6/29仍0→0，为不变负对照。不能由18项测试通过就认定这项政策值得上账户。', '',
'工程门：审查八组合成＋两项原单遍恒等共10/10；另8/8原硬约束／读集核验。真实Jan20原36单顺序、role/pool/q/价格/费用全同，并核36个原raw floor；Jun29原0单及全部原缺open/目标/资源拒因同。真实最终两视图＋本地方案计算6.42秒，原账户未运行。所有真实输入fingerprint前后同，原source hashes未变。', '',
'S0为分配函数最低充分投影，不是完整Account/runner恢复：冻结原planning资格／目标／clock／rank。现金、应收、当前lot、最后决策保护、原native open mark、历史stock receipt消费／order IDs及资金池资源来自原账。ACT峰/global_watch等不被这次分配函数读取，不重新计算；core锁未锁布尔由原合法pending且无隔夜buy fill证明。已失效/filled的0数量订单不重造，但其request IDs保留防重复。',
'行业过去confirmed/unfunded status没有逐route日志可完整回填，保留None而不猜。源码AST证明被调用的native valid/request/migrate不读取旧sector.status；migrate会按当前真实资源写入，另做None扰动结果同测试。该未知不影响数量／pool判定；本包不声称整个Python策略状态逐字段恢复。全部会被准入读取的active/level/episode/attempt/start由全暖机原行业trace和原financial事件核同。',
'6/29原分红应收449.912→452.952，差3.04为600010原dividend_accrual，ex_at当日00:00、paid_at未知；仅加应收而现金不变。持仓缺当日factor时直接复用原Facts.row/factor的last-known语义，记录真实source_day，不补新行情或新信号；2个新候选缺open保持原拒绝。原日线成交／权息代理限制不消失。', '',
'1/20 局部分配总量（都是计划预留，不是成交）',
'                    原单遍              两遍',
'股票/订单             36                  34',
'core/probe            4                   7',
'mobile/confirmed      32                  27',
'总承诺资本          409205.40           349654.64',
'名义risk             28791.33            23372.12',
'现金预留含费         409417.60           349852.16',
'预留后可用现金       256637.12           316202.57',
'计划费用               212.20              197.52',
'probe risk            3325.324            3334.699',
'confirmed资本       386546.08           326245.94',
'不是收益；风险与资本少参与也可能错失有效趋势，当前不评价后续市场结果。', '',
'1/20 全部变化（其余原订单量/pool/role未变）']
for x in data[0]['change_details']:
    def desc(o):return '无' if o is None else f"{o['role']}/{o['pool']}/{o['quantity']}股"
    lines.append(x['sid']+' '+x['name']+'：'+desc(x['old'])+' → '+desc(x['new']))
lines+=['',
'具体耦合：梅花原mobile confirmed1200→core probe100，core预留即跳mobile；化学制品同attempt probe待单阻止后续迁池，卫星/昊华因此没有原confirmed订单。铜陵新增core probe后，工业金属的中孚/新疆众和/洛钼也无法走原confirmed路径。儒意原probe100失去，而同传媒行业的光线因此可得confirmed1400。这是双向role/pool反馈；不是历史confirmed保持不变，也没有最终重跑argmax把pool改回去。完整每个失败候选的原序raw原因及每次迁池（含无单）均保存。',
'中际仍在原冻结rank1294的core意图，原单遍及两遍均probe_risk拒；新易不在1/19这批合法冻结意图，不能记作该开盘被分配器拒。', '',
'6/29：0单→0单，资本/风险/现金完全同；0新增/丢失/角色pool变化。原拒因517 probe_risk、164 probe_risk+sector_capital、7再含sector_risk、1原冻结目标开盘minimum失败、2 missing_open。所有234次无订单迁池尝试也被保留，不能因没有买单就跳掉状态转换。', '',
'边界：仅两个固定开盘；每股最终聚合一次不等于已有全批atomic transaction。私有模型里的orders/consumed只是拟议预留，用于排除重复；原输入和原ledger的order IDs、logs、consumed均未变化。不提供真实提交API，不推进开盘后的库存／费用／退出／账户NAV，不计算PnL，不跑全批或新日期。',
'失败证据保留：首次June29因应收3.04增量未桥接而断言，第二次因强制exact-day factor与原last-known规则不同而断言；均为只读局部构造失败，未推进账户。修为逐项原已发生权益及直接调用原Facts.row/factor，最终冻结版本通过。不是为了改结果放松风险或源模型。']
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
assert all(sha(p)==h for p,h in read('CODE_FREEZE.json')['sha256'].items())
assert all(sha(p)==h for p,h in read('SOURCE_INPUT_HASHES.json').items())
save('FINAL_STATUS.json',dict(status='bounded_allocation_preview_complete',synthetic_tests=10,hard_limit_tests=8,original_order_identity_passed=True,original_floor_identity_passed=True,native_open_prices_checked=len(checks),only_fixed_dates=list(views),new_financial_paths=0,real_submissions=0,real_fills=0,no_after_open_account_progression=True,no_all_batch=True,no_PnL=True,full_account_object_restore_not_claimed=True,current_unused_sector_status_explicitly_unknown=True,readset_and_invariance_test_passed=True))
hashes={str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file() and 'failure' not in p.parts and p.name!='ARTIFACT_SHA256.json'};save('ARTIFACT_SHA256.json',hashes)
print('AUDIT_PACKAGE_READY',len(checks),'native price inputs',len(floorchecks),'native archived floors',len(hashes),'artifacts')
