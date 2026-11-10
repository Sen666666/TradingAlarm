import time
START=time.monotonic()
import delay_patch as P
from pathlib import Path
import json,csv,gzip,hashlib,datetime,signal
import run_stage as OLD
I=P.I;O=Path(__file__).resolve().parent;old=P.OLD
budget=json.loads((O/'COMPUTE_TIME.json').read_text());remaining=180-budget['seconds']-(time.monotonic()-START);assert remaining>0
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('180 total repair compute exhausted')));signal.setitimer(signal.ITIMER_REAL,remaining)
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
techprefix=OLD.identity(O/'TECH/short2',O/'TECH/full/accounts-v2',['I__B_S0_delay1'],'2024-10-30',False);save(O/'TECH/PREFIX_IDENTITY.json',techprefix)
assert json.loads((O/'DRUG/prefix/IDENTITY.json').read_text())['passed']
base=list(csv.DictReader((old/'SUMMARY_18.csv').open()));lookup={(r['sector'],r['policy'],r['scenario']):r for r in base};changes=[]
for sector,mode in [('TECH','I'),('DRUG','ACT')]:
 root=O/sector/'full';aid=f'{mode}__B_S0_delay1';obj=json.loads((root/'accounts-v2'/f'{aid}.json').read_text());data=list(csv.DictReader((root/'analysis/summary.csv').open()))[0];daily=rows(root/'accounts-v2/daily.jsonl.gz');audit=obj['audit_log'];oldobj=json.loads((old/sector/'on/accounts-v2'/f'{aid}.json').read_text());g=json.loads((root/'GATE.json').read_text());accounting=json.loads((root/'analysis/accounting.json').read_text());assert accounting['passed'] and accounting['max_nav_difference']=='0';assert json.loads((root/'analysis/funding.json').read_text())['passed']
 def counts(a):
  orders={r['order_id'] for r in a if r['kind']=='reserve' and r['purpose']=='risk_restore'};fills=[r for r in a if r['kind']=='fill' and r['order_id'] in orders];expired=[r for r in a if r['kind']=='buy_day_expiry' and r['order_id'] in orders];return dict(applications=sum(r['kind']=='partial_event' and r['detail']['kind']=='restore_application' for r in a),orders=len(orders),expired=len(expired),zero_fill_expired=sum(not r['filled_shares'] for r in expired),fills=len(fills),fill_shares=sum(r['receipt']['shares'] for r in fills),credit_created=sum(r['kind']=='role_delay_credit_created' for r in a),credit_consumed=sum(r['kind']=='role_delay_credit_consumed' for r in a))
 previous=lookup[sector,'B','delay1'];cc=counts(audit);change=dict(sector=sector,old={k:previous[k] for k in ['net_return','net_profit','max_drawdown','fees','mean_exposure']},new={k:data[k] for k in ['net_return','net_profit','max_drawdown','fees','mean_exposure']},old_operations=counts(oldobj['audit_log']),new_operations=cc,accounting=accounting,first_consumed=next(r for r in audit if r['kind']=='role_delay_credit_consumed'));changes.append(change)
 newrow=dict(data,sector=sector,policy='B',scenario='delay1',account=aid,reference_reused=False,restore_applications=cc['applications'],restore_orders=cc['orders'],restore_buy_fill_count=cc['fills'],restore_buy_shares=cc['fill_shares'],restore_expired_orders=cc['expired'],restore_expired_zero_fill=cc['zero_fill_expired'],credit_created=cc['credit_created'],credit_consumed=cc['credit_consumed'],turnover_gross_cny=sum(float(f['gross_cny']) for f in obj['fills']),minimum_cash=str(min(I.D(d['available']) for d in daily)),result_status='repaired_role_delay_execution_validated_conditional_on_original_data',source=str(root/'analysis/summary.csv'))
 lookup[sector,'B','delay1']=newrow
save(O/'BEFORE_AFTER.json',changes)
oldf=json.loads((old/'ECONOMIC_FREEZE.json').read_text());origunchanged=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in oldf['sha256'].items());assert origunchanged
f=json.loads((O/'REPAIR_FREEZE.json').read_text());assert hashlib.sha256((O/'delay_patch.py').read_bytes()).hexdigest()==next(h for n,h in f['sha256'].items() if Path(n).resolve()==(O/'delay_patch.py').resolve())
h=json.loads((O/'HARNESS_FREEZE.json').read_text());assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==v for n,v in h['sha256'].items())
updated=[]
for r in base:
 k=r['sector'],r['policy'],r['scenario'];x=dict(lookup[k]);x.setdefault('result_status','unchanged_original_six_off_verified_and_financially_audited');x.setdefault('source',str(old/'SUMMARY_18.csv'));updated.append(x)
keys=['sector','policy','scenario','net_return','net_profit','final_nav','max_drawdown','mean_exposure','fees','tail_profit','all_closed_losses','maximum_stock_weight','maximum_sector_weight','restore_applications','restore_orders','restore_buy_fill_count','restore_buy_shares','restore_expired_orders','restore_expired_zero_fill','credit_created','credit_consumed','result_status','source']
with (O/'SUMMARY_18_UPDATED.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(updated)
lines=['部分行动delay1恢复链修复与唯一两格复验：完成，候选不晋升。','',
'本轮只改模拟执行适配：risk_restore零成交且实际消耗过一次合法执行等待后，按同股票/原E0来源结构/风险角色/原持仓cycle/最近实际risk_flat_at建立当次收盘信用。只有当次新I+Q及原排序/资源接纳的新单可消费；不续旧信号，不延长信用，不保证成交。原initial、normal/cost2、A/L分支原样。',
'日单仍在earliest session收盘到期；无合法窗口不产生信用，部分成交单不获得零成交信用。全退/换结构/无缺口不得继承。新模块源码delay_patch.py，原已冻结8文件未改。',
'先9项真实ledger/admission合成全部通过：旧bug复现；新I/Q实际成交；无新I/陈旧I不复活；Q不通过；无窗口；部分实际恢复后的余额不继承零成交信用；全退/换结构；normal/cost2及关闭角色A/L delay精确流水一致。',
'首次短段截止10/18无恢复成交，失败日志及ERROR保留。查既有订单时间，不读取未来收益，确认TECH29、DRUG30次到期当天重新获准下单；技术短段纠正到10/30并预先冻结。该段实际10/30恢复300085 1200股，独立核账通过。此纠正只改技术覆盖终点，不改策略或完整经济窗口。', '',
'修复前后两格（累计收益% / 最大DD%；初始100万元）：']
for c in changes:
 oldr=c['old'];newr=c['new'];lines.append(f"{c['sector']}：{float(oldr['net_return'])*100:.4f}/{float(oldr['max_drawdown'])*100:.4f} → {float(newr['net_return'])*100:.4f}/{float(newr['max_drawdown'])*100:.4f}；净利润差{(float(newr['net_profit'])-float(oldr['net_profit']))/10000:.4f}万元；费用{float(oldr['fees']):.2f}→{float(newr['fees']):.2f}元。")
 lines.append('  恢复申请/订单/到期/零成交到期/成交笔数/实际股数：'+str([c['old_operations'][k] for k in ['applications','orders','expired','zero_fill_expired','fills','fill_shares']])+' → '+str([c['new_operations'][k] for k in ['applications','orders','expired','zero_fill_expired','fills','fill_shares']])+f"；新信用建立/消费={c['new_operations']['credit_created']}/{c['new_operations']['credit_consumed']}。")
lines+=['', '当前18格（收益% / 最大DD%）：','行业/压力 | A原ACT | B部分行动 | L固定名义现金保留额']
for sector in ['TECH','DRUG']:
 for stress in ['base','cost2','delay1']:
  cells=[]
  for policy in ['A','B','L']:
   r=lookup[sector,policy,stress];cells.append(f"{100*float(r['net_return']):.2f}/{100*float(r['max_drawdown']):.2f}")
  lines.append(f'{sector}/{stress} | '+' | '.join(cells))
lines += ['',
'有效性：A六格、L六格、B正常/双成本四格完全沿用原结果；修后仅替换当前汇总的B delay1两格，并保留原两格为“未覆盖恢复链”的旧版本。新两格是修复后的同一冻结策略，不能将修复前后收益差称为新信号价值。两个行业均已有真实延迟恢复成交，恢复也仍会合理到期失败。',
'会计：两新账户各681日，1362日独立股数/NAV/费用/权息/资金预留核验，最大NAV差0。TECH物理截断10/30短段与完整新轨迹逐事件一致；DRUG物理截断2025-12-31前缀一致。原normal/cost2及A/L源码/输入与原六off逐事件恒等证据保持。',
'数据边界未消失：缺原生事件/价格时保留unknown、沿原保护，日线HL执行代理含后验可成交信息，冻结行业样本及已见历史不属OOS。未重跑其余16格，没有新参数或经济变体。',
'综合取舍：科技B正常/双成本收益与DD仍优于A；创新药B正常/双成本仍逊A；修后delay1需按上表评价，不能靠修复消除跨行业及成本/时点差异。L现金保留额是防御用途，科技少赚、创新药正常/双成本较好，但会改变ACT暂停路径，不能包装成信号成功。当前仍不足以批准两池通用实操策略。',
'完成后停止；没有自动新策略/新历史窗口/尺度切换/产品修改/交易。正式计算含失败短段、修正短段、两全量、DRUG固定前缀及汇总核验，详见COMPUTE_TIME。']
(O/'FINAL_REPORT.txt').write_text('\n'.join(lines)+'\n')
elapsed=time.monotonic()-START;budget['seconds']+=elapsed;budget['stages'].append(dict(stage='prefix_identity_and_final_read_only_report',status='complete',seconds=elapsed));save(O/'COMPUTE_TIME.json',budget);assert budget['seconds']<=180
save(O/'VERIFICATION.json',dict(passed=True,real_synthetic_cases=9,affected_new_economic_paths=2,other_original_16_unchanged=True,original_frozen8_unchanged=True,new_patch_frozen_unchanged=True,technical_harness_freeze_unchanged=True,independent_daily_rows=1362,max_nav_difference='0',prefix_tech_oct30=techprefix['passed'],prefix_drug_dec31=True,delay_restore_exposed_both_sectors=True,budget_seconds=180,actual_seconds=budget['seconds'],candidate_promoted=False))
save(O/'COMPLETION.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='approved_two_delay_paths_repaired_revalidated_complete',candidate_promoted=False,remaining_execution_blocker=None,remaining_economic_limit='No common dominance across sectors/stresses; original snapshot/missing-data execution assumptions remain',old_two_cells_preserved=True,additional_experiments_started=False,product_modified=False))
signal.setitimer(signal.ITIMER_REAL,0);print(json.dumps(changes,ensure_ascii=False)[:1800]);print('COMPLETE seconds',budget['seconds'])
