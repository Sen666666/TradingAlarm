"""Join independent saved OPEN bridge to local caps; no new risk simulation."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,csv
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def money(x):return f'{D(str(x)):,.2f}'
localpath=O/'SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json';bridgepath=O.parent/'open_prefix/SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json';card=O.parent/'designer/MINIMUM_MATH_CONTRACT.md';manifest=read(O/'LOCAL_SOURCE_MANIFEST.json');oldsha=manifest['sources'][str(card)]
reconcile=dict(recorded_contract_sha256=oldsha,current_contract_sha256=sha(card),version_changed=oldsha!=sha(card),consumed_sections='B origin, D, positive-per-layer kappa, one same-sid prospective sell group, source/CLOSE freeze, dated fees and units',not_consumed='No full G1/G2/sector scenario engine or old per-layer shock was run. CLOSE .36inventory lower bound does not depend on old Z-vs-minh/per-sid choice.',current_common_sid_min_h_only_tightens_necessary_lower_bound=True,local_numeric_recompute_unnecessary='P/kappa and local caps unchanged by G-base amendment; firstthree old fee-group scope was already explicitly superseded.')
(O/'CONTRACT_VERSION_RECONCILIATION.json').write_text(json.dumps(reconcile,ensure_ascii=False,indent=2)+'\n')
local=read(localpath);bs=read(bridgepath);byopen={(r['window'],r['next_OPEN'][:10]):r for r in bs['results']};final=[];compact=[]
for r in local:
 b=byopen[r['window'],r['nextOPEN']];assert b['status']=='EXACT_ORIGINAL_PREFIX_ARITHMETIC'
 for domain in ['native_mark','OPEN_valuation']:
  invkey='native_known_mark_inventory_after_sells' if domain=='native_mark' else 'exact_raw_OPEN_inventory_after_sells';navkey='native_known_mark_NAV_prefix' if domain=='native_mark' else 'raw_OPEN_valued_NAV_prefix';Akey='A_native_domain' if domain=='native_mark' else 'A_OPEN_valuation_domain';lowkey='G2_lower_native_mark_domain' if domain=='native_mark' else 'G2_lower_OPEN_valuation_domain'
  assert abs(D(b[lowkey])-D('.36')*D(b[invkey]))<D('.000001')
  assert abs(D(b[Akey])-max(D(0),D(b[navkey])-D('.8')*D(b['ACT_peak'])))<D('.000001')
  assert D(b[lowkey])>D(b[Akey])
 rf=dict(r);rf['local_disposition']=rf.pop('final_disposition');rf['scope_note']='local_disposition is the preserved risk/source-cap preview only, not the final grant. In this joined file use final_status and q_final_grant; all seven final grants are zero. The original local JSON remains unchanged.';rf['original_OPEN_pressure_necessary_condition']=dict(source=str(bridgepath),source_sha256=sha(bridgepath),prefix=b['prefix'],next_OPEN=b['next_OPEN'],cash_after_actual_exits_and_settles=b['cash_after_original_settles'],ACTpeak=b['ACT_peak'],native_mark_NAV=b['native_known_mark_NAV_prefix'],native_mark_inventory=b['native_known_mark_inventory_after_sells'],A_native=b['A_native_domain'],G2_lower_native=b['G2_lower_native_mark_domain'],exact_raw_OPEN_NAV=b['raw_OPEN_valued_NAV_prefix'],exact_raw_OPEN_inventory=b['exact_raw_OPEN_inventory_after_sells'],A_OPEN=b['A_OPEN_valuation_domain'],G2_lower_OPEN=b['G2_lower_OPEN_valuation_domain'],both_necessary_inequalities_fail=True,not_signal_CLOSE_substitution=True,full_Phi_T_engine_not_needed_for_deny=True)
  # Existing inventory alone violates a necessary condition. No positive new
  # position can turn this independent original prefix into a valid grant.
 rf['q_final_grant']=0;rf['final_status']='FINAL_DENY_ZERO_ON_THIS_INDEPENDENT_ORIGINAL_PREFIX';rf['primary_reason']='D_ALREADY_EXCEEDS_SHARED_B' if D(r['D_before'])>D(r['B']) else 'LOCAL_NO_LEGAL_MINIMUM_UNIT' if r['q_local_after_source_and_frozen_caps']==0 else 'ORIGINAL_OPEN_EXISTING_G2_NECESSARY_LOWER_EXCEEDS_A';rf['additional_known_denial']='ORIGINAL_OPEN_EXISTING_G2_NECESSARY_LOWER_EXCEEDS_A';rf['counterfactual_account_gain']='NOT_COMPUTED_NOT_IDENTIFIED';rf['single_prefix_only']=True
 rf['OPEN_full_portfolio_pressure']='Necessary lower bound verified in two valuation domains; full Phi/scenario allocation not computed and not required for this rejection.'
 final.append(rf);compact.append(dict(stock=r['sid'],signal=r['decision'],OPEN=r['nextOPEN'],source=r['source'],B=r['B'],D=r['D_before'],q_CLOSE_risk=r['q_CLOSE_risk_only'],source_cap=r['original_frozen_source_cap'],frozen_cap=r['frozen_local_cap'],q_OPEN_risk=r['q_OPEN_risk_only'],q_local=r['q_local_after_source_and_frozen_caps'],OPEN_A_native=b['A_native_domain'],OPEN_G2_lower_native=b['G2_lower_native_mark_domain'],OPEN_A_raw=b['A_OPEN_valuation_domain'],OPEN_G2_lower_raw=b['G2_lower_OPEN_valuation_domain'],FINAL_GRANT=0,reason=rf['primary_reason']))
(O/'FINAL_SEVEN_PAPER_DECISIONS.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
with (O/'FINAL_SEVEN_PAPER_TABLE.csv').open('w') as f:
 wr=csv.DictWriter(f,fieldnames=list(compact[0]));wr.writeheader();wr.writerows(compact)
lines=['七个独立原前缀的v3纸算：局部有正cap，原OPEN最终grant全部为0。','',
'这是待检初值的一次纸面授信核查，不是替代账户、连续路径或收益预测。原v2两案例封版未改；没有新loader/模型/账户/参数搜索。每行重新站在该原真实prefix，不把不同q拼成交易历史。','',
'信号→OPEN | 来源 | 固定B / 已损D | CLOSE-risk / 原sourcecap / frozen | OPEN-risk / 最终localcap | 原OPEN A / G2必要下界(native) | 最终grant / 先触发原因']
for r in compact:lines.append(f'{r["stock"]} {r["signal"]}→{r["OPEN"]} | {r["source"]} | {money(r["B"])} / {money(r["D"])} | {r["q_CLOSE_risk"]} / {r["source_cap"] if r["source_cap"] is not None else "新typed臂无原intent"} / {r["frozen_cap"]} | {r["q_OPEN_risk"]} / {r["q_local"]} | {money(r["OPEN_A_native"])} / {money(r["OPEN_G2_lower_native"])} | 0 / {r["reason"]}')
lines+=['','局部q的精确含义：中船495只是B/D/κ风险上界，原CLOSE sourcecap476后是476；4/30 CLOSE risk433/source422，5/6 OPEN变价后risk369，所以local369。盈新seed原intent signal_price2.74/reference2.741370、cap3200，OPEN风险收为2300，没有开盘增q。旧firstthree risk-only及sameguard fee-group版本保留并显式superseded；正式同sid一prospective组可有不同计划线，按合计notional只收一次最低佣金再按shares分摊。',
'',
'盈新1/20不是新E0开启：原states.entered=0、IX e0_entered=0，持续原1/6 canonical E0段；B仍沿1/10首成功reserve对应signalNAV995688.148105514冻结2489.220370264，1/21和1/24已损D分别7118.724008357与7125.407666165，均大于B，可直接拒0，不需要等待Ω。已付买/卖费一次进D，未实现浮盈不抵D，旧层负成本缺口不抵新风险。',
'',
'两个HELD_I_INCREMENT是额外选定的“真实持仓后首个CP已知False+i_buyTrue且无退出观察”：中船4/22→23、盈新1/14→17。原core_Q均True，现有原层均confirmed；i_buy/up_reasons为原真实事件字段，身份/typed proof未实现，不伪造真实订单。I线而非紧CP线定量：中船最小200股D+κ+费8731.03>B4126.47；盈新最小100股3477.55>B2489.22，local均0。无须为凑最小手加钱。',
'',
'原OPEN桥由open_prefix owner只读原audit、settlement、持股和原报价重建，在原实际退出/结算后、首个新reserve之前取存量。其native原mark域与真实rawOPEN估值域两种下界都已超过各自A；表不是用signal CLOSE暴露替OPEN拒绝。因为plan_exit<=mark，忽略费/线外缺口时G2仍>=.36×存量市值；真正同sid最低计划线、费用、待退锁、容量只会更紧。现有库存已违反必要条件即可拒新增，完整Φ/T/全组合新引擎无需搭建。',
'',
'本例最终0不意味着新策略从空仓开始永不买，也不证明能获利或不伤赢家；它表明在这七个已高度投资的原真实prefix上，这组候选压力初值不允许新增。中船局部能申请但全户已占用过高；盈新多笔还先被共享预算/最小手拒绝。不能由这些单次结果拼新账户收益，不能因看见赢家就调压力折扣救单。',
'',
'原退出锁另外保留：盈新1/27 CP锁mobile113/122，2/7 Ioff把CORE并入，2/8才真实卖。mark风险夹0时实物/退出责任仍在，不能释放现金或新B；没有虚构当时不存在的买事件。',
'',
'源索引：FINAL_SEVEN_PAPER_DECISIONS.json含完整local、B origin、D逐笔、fee/units、原quote及OPEN必要条件；OPPORTUNITY_KEY_ORIGIN_PROOF.json钉真E0根；EXACT_ORIGINAL_OPEN_CASH_BRIDGE.json重建968个CLOSE可用现金完全闭合，并列五个原reserve槽位前可用现金（两个新I无原槽位不造）；原OPEN组合桥见../open_prefix/SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json。卡版本更正见CONTRACT_VERSION_RECONCILIATION.json：局部只消费P/κ/B/sourcecap，Ω更正未被旧版本数值冒充。']
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
bindings=dict(local_file=str(localpath),local_sha256=sha(localpath),OPEN_bridge_file=str(bridgepath),OPEN_bridge_sha256=sha(bridgepath),current_contract_sha256=sha(card),all_seven_final_grant_zero=True,full_risk_engine_not_run=True,new_accounts=0,new_model_calls=0,script_sha256=sha(__file__))
(O/'FINAL_BINDING.json').write_text(json.dumps(bindings,indent=2)+'\n')
# complete_saved_inputs read its local input before adding the cash annotation.
# Preserve that historical hash as an attempt input; do not claim it unchanged.
add=read(O/'ADDITIONAL_SOURCE_BINDING.json');p=str(localpath)
if p in add['sources'] and add['sources'][p]!=sha(localpath):
 (O/'OWN_DERIVED_INPUT_HASH_RECONCILIATION.json').write_text(json.dumps(dict(file=p,before_cash_annotation=add['sources'][p],after_cash_annotation=sha(localpath),reason='same local numeric rows, only exact original cash annotations appended; original external sources unchanged'),indent=2)+'\n')
manifest={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json' and p.suffix!='.log'};(O/'DELIVERABLE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(compact,ensure_ascii=False,default=str))
