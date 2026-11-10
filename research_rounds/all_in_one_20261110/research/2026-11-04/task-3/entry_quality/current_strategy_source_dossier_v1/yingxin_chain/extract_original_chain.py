"""Original six-layer Yingxin transaction evidence; no candidate/risk simulation."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,csv
O=Path(__file__).resolve().parent;Q=O.parents[1];SRC={};ids={68,69,75,78,113,122};sid='000620.SZ'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def m(x):return '—' if x is None else f'{D(str(x)):,.6f}'
base=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair';book=read(base/'B.json.gz',True);daily=read(base/'daily.jsonl.gz',True,True)
case=read(Q/'structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json');days={x['day']:x for x in case['days']};enriched={x['native']['id']:x for x in case['selected_actual_layers']};buys={x['layer']:x for x in book['trades'] if x['side']=='buy' and x['layer'] in ids};sales=[x for x in book['trades'] if x['side']=='sell' and any(p['layer'] in ids for p in x['parts'])]
# Only actual ledger cash events, not a new account/strategy loop.
available=D(1000000);cash_before={};cash_after_reserve={};cash_at_day={}
for a in book['audit']:
 kind=a['kind'];at=a.get('at',a.get('receipt',{}).get('at'))
 if kind=='reserve':
  cash_before[a['order_id']]=available;available-=D(a['gross_budget_cny'])+D(a['fee_reserved_cny']);cash_after_reserve[a['order_id']]=available
 elif kind=='release_buy':available+=D(a['gross_released'])+D(a['fee_released'])
 elif kind=='settle' and not a['settlement']['debit']:available+=D(a['settlement']['cny_amount'])
 elif kind=='fill' and a['receipt']['side']=='sell' and D(a['receipt']['gross_cny'])<D(a['receipt']['fees_cny']):available+=D(a['receipt']['gross_cny'])-D(a['receipt']['fees_cny'])
 if at:cash_at_day[at[:10]]=available
assert all(abs(cash_at_day[d['at'][:10]]-D(d['available']))<D('.000001') for d in daily)
signal_intents={d['at'][:10]:[i for i in d['intents'] if i['sid']==sid] for d in book['decisions']};signal_NAV={d['at'][:10]:d['nav'] for d in book['decisions']};actual=[]
industry_events=[r for r in read(base/'industry.jsonl.gz',True,True) if r['sector']=='URFI881153' and r.get('account')=='B']
for lid in sorted(ids):
 t=buys[lid];day=t['signal_at'][:10];od=t['at'][:10];e=enriched[lid];d=days[day];s=e['original_entry_state'];fi=next(i for i in signal_intents[day] if i['role']==s['role']);assert fi==s['frozen_intent']
 fill=next(a for a in book['audit'] if a['kind']=='fill' and a['receipt']['receipt_id']==t['receipt_id']);reserve=next(a for a in book['audit'] if a['kind']=='reserve' and a['order_id']==fill['order_id']);assert reserve['target_shares']==t['shares'];factor=D(str(days[od]['original_stock_facts']['factor']));floorraw=D(t['floor'])/factor
 prev=next(daily[j-1] for j,d0 in enumerate(daily) if d0['at'][:10]==od);same_before=[x for x in prev['layers'] if x['sid']==sid];assert not any(z['at'][:10]==od for z in sales)
 first_requests=[]
 for a in book['audit']:
  if a['kind']=='pilot_layer_exit' and a.get('sid')==sid and lid in a['layers']:first_requests.append(a)
 actual_parts=[dict(whole_actual_sell=t0,part=p) for t0 in sales for p in t0['parts'] if p['layer']==lid]
 opportunity=next((x for x in d['original_opportunities'] if x.get('account')=='B'),None);ranking=next((x for x in d['original_ranking'] if x.get('account')=='B'),None);financial=next((x for x in reversed(industry_events) if x['day']<=day),None)
 r=dict(layer=lid,security_id=sid,role=s['role'],signal_at=t['signal_at'],signal_facts=d['original_stock_facts'],signal_original_G1=d['original_G1'],signal_original_native_event=d['original_native_event'],signal_CP_cache=d['original_CP_cache'],signal_CP_canonical_receipt=d['original_CP_canonical_receipt'],
  signal_CLOSE_original_NAV=signal_NAV[day],signal_CLOSE_original_available_cash=d['original_account']['available_cash'],signal_CLOSE_original_account_components={k:v for k,v in d['original_account'].items() if k not in ['native_reported_account_mark_risk']},original_signal_opportunity=opportunity,original_signal_rank_policy=ranking,original_latest_industry_financial_event=financial,original_OPEN_funding=[x for x in days[od]['original_funding'] if x.get('account')=='B'],
  signal_industry_state=s['industry_state'],signal_industry_stage=s['industry_stage'],signal_industry_attempt=s['industry_attempt'],signal_industry_auth=s['industry_auth_id'],
  PVR_priority_score=fi['PVR_score'],PVR_ready=fi['PVR_ready'],priority_rank=fi['priority_rank'],original_H1_rank=fi['original_H1_rank'],original_H1_intent_score=fi['score'],legacy_trade_field_named_pvr=t['pvr'],original_frozen_intent=fi,
  original_OPEN_before_reserve_available_cash=cash_before[reserve['order_id']],original_OPEN_after_actual_reserve_available_cash=cash_after_reserve[reserve['order_id']],original_actual_reserve=reserve,original_fill_audit=fill,actual_buy=t,
  original_intent_max_shares=fi['cap'],actual_order_target_shares=reserve['target_shares'],actual_filled_shares=t['shares'],actual_initial_floor_adjusted=t['floor'],actual_fill_factor=factor,actual_initial_floor_raw=floorraw,
  same_stock_at_signal_CLOSE=[x['saved_native_layer'] for x in d['original_live_layers']],same_stock_at_OPEN_before_reserve=same_before,same_stock_before_reserve_qty=sum(x['qty'] for x in same_before),
  first_specific_exit_request=None if not first_requests else first_requests[0],all_actual_specific_exit_request_extensions=first_requests,actual_sell_parts=actual_parts,final_native_layer=e['native'],
  missing=['Exact per-quantity route/probe/sector/account constraint evaluation reducing frozen cap to reserved target is not saved; do not infer insufficient cash from target<cap.','Selected original book/audit does not save an explicit per-OPEN exit-window rejection reason for Jan28 or Feb7; pending/no actual fill is observable, actual exchange limit-down/halt is not inferred.'],
  scope='Original actual facts only; risk_budget is original individual CORE intent field, never v3 shared B/D/kappa.')
 actual.append(r)
save('ORIGINAL_SIX_LAYER_CHAIN.json',actual);save('ORIGINAL_TWO_SELL_ORDERS.json',sales)
buyrows=[];signalrows=[];exitrows=[]
for r in actual:
 t=r['actual_buy'];f=r['original_frozen_intent'];cp=r['signal_CP_canonical_receipt'];q=r['signal_facts'];g=r['signal_original_G1']
 buyrows.append(dict(layer=r['layer'],role=r['role'],signal_at=r['signal_at'],actual_OPEN=t['at'],signal_CLOSE_NAV=r['signal_CLOSE_original_NAV'],signal_CLOSE_available=r['signal_CLOSE_original_available_cash'],intent_cap=f['cap'],intent_gross_budget=f['budget'],intent_risk_budget=f.get('risk_budget'),actual_order_target=r['actual_order_target_shares'],actual_filled=t['shares'],raw_OPEN=t['raw_open'],execution_price=t['price'],buy_gross=t['gross_cny'],buy_fee=t['fees_cny'],before_reserve_available=r['original_OPEN_before_reserve_available_cash'],same_stock_qty_before=r['same_stock_before_reserve_qty'],initial_floor_adjusted=t['floor'],initial_floor_raw=r['actual_initial_floor_raw']))
 opp=r['original_signal_opportunity'];rank=r['original_signal_rank_policy'];fin=r['original_latest_industry_financial_event']
 signalrows.append(dict(layer=r['layer'],signal=r['signal_at'],E0_target=q['e0_target'],I_target=q['i_target'],i_buy=q['i_buy'],grade=q['g_grade'],up_reasons=g['up_reasons'],core_Q=None if opp is None else opp['core_Q'],mobile_Q=None if opp is None else opp['mobile_Q'],market_CP_id=None if cp is None else cp['receipt_id'],market_CP_candidate=r['signal_CP_cache'].get('candidate'),actual_intent_CP_id=f.get('CP1_id'),PVR_priority_score=r['PVR_priority_score'],original_H1_score=r['original_H1_intent_score'],trade_pvr=r['legacy_trade_field_named_pvr'],priority_rank=r['priority_rank'],original_slot=None if rank is None else rank['original_slot'],final_PVR_slot=None if rank is None else rank['final_slot'],industry_stage=r['signal_industry_stage'],industry_financial_level=None if fin is None else fin['financial_level']))
 for p in r['actual_sell_parts']:
  req=r['first_specific_exit_request'];t0=p['whole_actual_sell'];a=p['part'];exitrows.append(dict(layer=r['layer'],first_request_at=req['at'],first_request_reason=req['reason'],actual_sell_at=t0['at'],actual_shares=a['shares'],raw_OPEN=t0['raw_open'],execution_price=t0['price'],allocated_sell_fee=D(a['shares'])*D(t0['price'])-D(a['net_cash']),net_cash=a['net_cash'],final_part_reason=a['reason'],native_closed_layer_cash=r['final_native_layer']['cash']))
for name,rr in [('SIX_BUYS.csv',buyrows),('SIX_SIGNAL_STATES.csv',signalrows),('SIX_LAYER_EXIT_PARTS.csv',exitrows)]:
 with (O/name).open('w') as fh:
  wr=csv.DictWriter(fh,fieldnames=list(rr[0]));wr.writeheader();wr.writerows(rr)
# Source-only daily index, deliberately exclude every old paper/candidate field.
timeline=[{k:d[k] for k in ['day','original_CLOSE_clock','source_days','original_bar','original_stock_facts','original_G1','original_native_event','original_CP_cache','original_CP_canonical_receipt','original_OPEN_buys','original_OPEN_sells','original_CLOSE_specific_exit_requests','original_audit_today','original_journal_today','original_intents','original_opportunities','original_funding','original_ranking']} for d in case['days'] if d['day']>='2022-01-10'];save('ORIGINAL_DAILY_SOURCE_INDEX.json',timeline)
sourcefiles={
 'native_planning_opening':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py'),
 'native_rank':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py'),
 'rank_behavior_fields':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/behavior_evidence.py'),
 'known_OPEN_reserve':Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py'),
 'original_I':Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py'),
 'original_G1':Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py'),
 'layer_exit_union':Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py')}
for p in sourcefiles.values():SRC[str(p)]=sha(p)
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,code_references={k:str(v) for k,v in sourcefiles.items()},script_sha256=sha(__file__),all_read_only=True,new_accounts=0,new_models=0,new_candidate_quantities=0))
lines=['# 盈新发展：原策略六层真实交易证据','',
'范围仅000620.SZ的68、69、75、78、113、122层，2022-01-10信号至2022-02-08实际清仓。只原源码/原账，不含v3共享预算、候选数量、风险假说或新回测。金额单位人民币，信号15:10，实际成交09:30；表内cap、真实reserve target、实际filled是三个字段。','',
'## 六笔真实买入','',
'|层/角色|信号→实际OPEN|intent cap→下单target/filled|OPEN预留前available|实际价格|买费|原gross budget / CORE risk_budget|同股原股数|初始floor 调整/原始|','|---|---|---:|---:|---:|---:|---:|---:|---|']
for r in buyrows:lines.append(f'|{r["layer"]}/{r["role"]}|{r["signal_at"][:10]}→{r["actual_OPEN"][:10]}|{r["intent_cap"]}→{r["actual_order_target"]}/{r["actual_filled"]}|{m(r["before_reserve_available"])}|{r["execution_price"]}|{m(r["buy_fee"])}|{m(r["intent_gross_budget"])} / {m(r["intent_risk_budget"])}|{r["same_stock_qty_before"]}|{r["initial_floor_adjusted"]} / {r["initial_floor_raw"]}|')
lines+=['','3200是层68原intent的最大股数，真正提交的target就是100，实际也成交100；不是已下3200股只成交100。六笔均target=filled，实际before-reserve available按原audit现金事件逐项重建，并与全部726个原CLOSE available闭合。该现金是轮到该原reserve槽位时的余额，已反映此前其它原reserve，不是昨收现金，也没有借款。','','## 原信号CLOSE与实际OPEN现金分列','','|层|信号CLOSE NAV|信号CLOSE available|OPEN该笔reserve前available|原gross budget|原单笔CORE risk_budget|core_Q/mobile_Q|行业financial level|原slot→最终PVR slot / priority_rank|','|---|---:|---:|---:|---:|---:|---|---:|---|']
for a,b in zip(buyrows,signalrows):lines.append(f'|{a["layer"]}|{m(a["signal_CLOSE_NAV"])}|{m(a["signal_CLOSE_available"])}|{m(a["before_reserve_available"])}|{m(a["intent_gross_budget"])}|{m(a["intent_risk_budget"])}|{b["core_Q"]}/{b["mobile_Q"]}|{b["industry_financial_level"]}|{b["original_slot"]}→{b["final_PVR_slot"]} / {b["priority_rank"]}|')
lines+=['','signal_CLOSE_available、OPEN_before_reserve_available来自不同时钟，不互相代替；mobile risk_budget原字段缺失记None，不填原CORE值。financial level是截至信号日最后一条原industry金融事件，不以未来期末level回填。原slot/最终PVR slot/priority_rank均保原字段，不把名次当预算。',
'','## 每笔信号当时的原状态','',
'|层|E0 / I / i_buy / grade|原G1 up_reasons|当日市场CP candidate|实际intent CP id|PVR排序分|行业stage|','|---|---|---|---:|---|---:|---|']
for r in signalrows:lines.append(f'|{r["layer"]}|{r["E0_target"]}/{r["I_target"]}/{r["i_buy"]}/{r["grade"]}|{r["up_reasons"]}|{r["market_CP_candidate"]}|{r["actual_intent_CP_id"] or "None：CORE未使用CP"}|{r["PVR_priority_score"]}|{r["industry_stage"]}|')
lines+=['','全部CP完整ID及canonical形成字段在SIX_SIGNAL_STATES.csv/ORIGINAL_SIX_LAYER_CHAIN.json。层68当天市场存在CP，但CORE intent CP1_id=None，实际初始线取原I；不能将市场CP标记写成CORE使用了CP。',
'','PVR字段名称需分开：native_rank.py只新增`PVR_score/PVR_ready/priority_rank`并覆盖`rank`，保留原`score`；behavior_evidence.py把这个旧score明确称original_H1_score。成交字段名`pvr`承接旧intent score，和真正本轮PVR排序分不是同一字段。结构化文件同时保留PVR_priority_score、original_H1_intent_score、legacy_trade_field_named_pvr，不混为一个值。','',
'## 六层实际退出part','',
'|层|首次specific请求/原因|实际卖出|股数/价格|分摊卖费|net_cash|最终part reason|','|---|---|---|---:|---:|---:|---|']
for r in exitrows:lines.append(f'|{r["layer"]}|{r["first_request_at"][:10]} / {r["first_request_reason"]}|{r["actual_sell_at"][:10]}|{r["actual_shares"]} / {r["execution_price"]}|{m(r["allocated_sell_fee"])}|{m(r["net_cash"])}|{r["final_part_reason"]}|')
lines+=['','原逻辑卖单只有两次真实fill：1/20共16200股，raw OPEN2.95、价2.948525、全单费61.5561795135；2/8共9900股，raw OPEN2.77、价2.768615、全单费35.32235008995。表中按原parts反算各层分摊费用，合计与全单费一致，没有每层重复最低佣金。',
'','1/27 I仍on，首次卖单锁113/122是CP1_add_protection；2/7 Ioff才将CORE68并入已存在卖单。2/8所有parts最终reason写成I_structure_exit，不应倒填成1/27已经I退出。1/28与2/7未记录实际sell fill；所选原book/audit没有逐OPEN明确的窗口拒绝原因，保留“原pending/无实际fill，原因字段缺失”，不推断真实交易所跌停/停牌，也不假设未成交日可以成交。','',
'## 源码入口与未保存字段','',
f'- [原planning/旧线检查→ratchet→新申请]({sourcefiles["native_planning_opening"]}:213)：ACT/I优先退出，mobile先检查已有floor，未触才max原I/新CP；原CORE继续用I。',
f'- [原opening]({sourcefiles["native_planning_opening"]}:302)：先原退出和结算，再按rank/role顺序preview、route、reserve，之后检查执行窗口与fill。',
f'- [真实known-OPEN reserve]({sourcefiles["known_OPEN_reserve"]}:94)：target=q、锁gross与费用，assert q<=intent.cap；audit分别保存target与frozen cap。',
f'- [PVR排序字段绑定]({sourcefiles["native_rank"]}:78)、[旧H1 score字段命名]({sourcefiles["rank_behavior_fields"]}:36)、[trade.pvr=meta.score]({sourcefiles["layer_exit_union"]}:71)：结构化保留两类分数。',
f'- [原I事件/持有状态]({sourcefiles["original_I"]}:20)、[原G1 fresh_up来源]({sourcefiles["original_G1"]}:24)。',
f'- [同股退出层合并]({sourcefiles["layer_exit_union"]}:104)：后续请求会扩展已有单及reason，原created_at仍保留。',
'','缺失：原账没有逐个被尝试股数的route/probe/sector/account约束完整评估日志，不能仅凭cap与target差异断言是哪一道门、也不能直接说现金不足。已保存的frozen intent、原reserve、funding、实际fill都原样保留。mobile原risk_budget字段不存在，记None，不能填入任何共享预算。',
'','字段索引：ORIGINAL_SIX_LAYER_CHAIN.json是逐层完整原对象；SIX_BUYS.csv/SIX_SIGNAL_STATES.csv/SIX_LAYER_EXIT_PARTS.csv供对照；ORIGINAL_TWO_SELL_ORDERS.json保whole order+parts；ORIGINAL_DAILY_SOURCE_INDEX.json保1/10—2/8逐日原字段，已排除旧paper/v3字段。SOURCE_MANIFEST.json绑定原书、daily、源码和脚本。']
(O/'EVIDENCE.md').write_text('\n'.join(lines)+'\n')
save('VALIDATION.json',dict(status='PASS_ORIGINAL_SOURCE_EXTRACTION',six_layers=sorted(ids),real_buy_orders=6,real_buy_fills=6,real_sell_orders=2,all_target_equals_actual_fill=True,original_CLOSE_cash_points_reconciled=726,source_files=len(SRC),new_accounts=0,new_models=0,new_risk_schemes=0,new_candidate_quantities=0,missing_size_route_trace=True))
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
print('6 actual buys, 2 actual sell orders; source dossier saved; no candidate quantity or budget computed')
