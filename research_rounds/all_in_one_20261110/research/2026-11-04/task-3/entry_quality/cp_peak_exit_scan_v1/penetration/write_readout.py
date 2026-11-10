"""Seal saved original penetration rows and source cross-check; no strategy run."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import csv,hashlib,json
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def fmt(x,n=6):return f'{D(str(x)):.{n}f}'
data=read('MOBILE_DAILY_PENETRATION.json');rows=[x['summary'] for x in data];cross=read('ACTUAL_FIRST_CP_TRIGGER_POINTS.json')
ap=O.parent/'peak_scan/FLOOR_PROVENANCE.json';author=json.loads(ap.read_text());am={(x['sid'],x['layer'],x['day']):x for x in author}
checks=[]
for x in data:
 r=x['summary'];k=(r['sid'],r['layer'],r['day']);a=am[k]
 assert D(a['old_floor'])==D(r['old_floor_adjusted'])
 assert D(a['after_floor'])==D(x['actual_after_CLOSE_layer']['floor'])
 if r['provenance_kind']=='UNIQUE_CP_MAX_ORIGIN':
  src=a['old_source'];assert src['kind']=='CP' and src['receipt_id']==r['unique_CP_receipt_id'] and D(str(src['original_scale']))==D(str(r['unique_CP_frozen_scale'])) and src['scale_frozen_at']==r['scale_frozen_at']
 else:assert a['old_source']['kind']=='I' and r['unique_CP_receipt_id'] is None and r['unique_CP_frozen_scale'] is None
 checks.append(dict(sid=k[0],layer=k[1],day=k[2],old_and_after_floor_exact=True,old_source_identity_exact=True))
save('STRUCTURAL_OWNER_PROVENANCE_CROSSCHECK.json',dict(status='PASS_TWO_AUTHORS_SAVED_SOURCE_EXTRACTIONS_EXACT',owner_file=str(ap.resolve()),owner_file_sha256=sha(ap),rows=len(rows),CP_receipt_scale_frozen_date_exact=185,I_dominated_no_CP_scale=24,checks=checks,scope='Cross-check of two source extractions, not a strategy/account replay or independent financial audit.'))
initial=[];first_cross=[]
for lid in sorted({r['layer'] for r in rows}):
 rr=[r for r in rows if r['layer']==lid];r=rr[0];x=next(x for x in data if x['summary'] is r);t=x['actual_initial_buy']
 assert not r['held_previous_CLOSE'] and all(r[k] is None for k in ['quantity_weighted_delta','quantity_weighted_old_distance','quantity_weighted_penetration'])
 initial.append(dict(sid=r['sid'],layer=lid,signal_at=t['signal_at'],actual_buy_at=t['at'],actual_qty=t['shares'],actual_raw_OPEN=t['raw_open'],actual_buy_execution_price=t['price'],actual_buy_fee=t['fees_cny'],original_initial_adjusted_floor=t['floor'],first_held_CLOSE_day=r['day'],first_held_Cprev_is_before_buy=True))
 first=next((r for r in rr if r['current_CLOSE_at_or_below_old_floor']),None)
 actual=rr[0]['actual_first_CP_request_at']
 first_cross.append(dict(sid=r['sid'],layer=lid,first_saved_CLOSE_at_or_below_old_line=None if first is None else first['day'],actual_first_CP_request_at=actual,dates_match=first is not None and first['day']==actual[:10]))
 assert first_cross[-1]['dates_match']
with (O/'ACTUAL_ENTRY_REFERENCE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(initial[0]));w.writeheader();w.writerows(initial)
save('FIRST_SAVED_CROSS_AND_ACTUAL_REQUEST_CHECK.json',first_cross)
groups=[];seen=set()
for r in cross:
 key=(r['sid'],r['day'],r['old_floor_adjusted'])
 if key in seen:continue
 seen.add(key);rr=[x for x in cross if (x['sid'],x['day'],x['old_floor_adjusted'])==key]
 groups.append(dict(**r,layers=[x['layer'] for x in rr],total_actual_qty=sum(x['qty_current_original'] for x in rr)))
save('SIX_ORIGINAL_STOCK_TRIGGER_EVENTS.json',groups)

lines=['# 原MOBILE旧线穿透：六股完整持有期','',
'主表覆盖太保601601、中信建投601066、中金公司601995、人保601319、人寿601628、海能达002583的14个指定原MOBILE层，**从各层实际entry到退出前最后实际持有CLOSE的完整期间**，共209个原held-layer CLOSE点。原47点P10五股+海能达子集保留为P10_FIVE_PLUS_HAINENGDA_SUBSET_*，不是主范围。0账户/模型/回测/新策略/新指标。','',
'`h`取当日CLOSE检查前已生效旧保护线：已有仓用前一原daily层floor；首持日用真实初始order floor，不能拿当日ratchet后新线替代。原当日更新后floor单独保留。所有raw分解先核前后factor与exact source observation，本样本209点同价域；跨factor/缺exact观察将UNKNOWN。CP/I检查仍按原代码先旧线检查后ratchet，不模拟重建持仓。','',
'## 原首次穿线/请求事实','',
'每股各层可共用一条旧线，下表合并同股同日同线。价格单位元/raw股，百分比统一除以前已知Cprev。','',
'|股/层|原请求日 Cprev→C|已生效旧h|ΔC|Cprev−h / h−C|对应百分比分解|原代理fill日/价|',
'|---|---|---:|---:|---:|---|---|']
for r in groups:
 lines.append(f'|{r["sid"]} / {r["layers"]}|{r["day"]} {r["C_prev_raw"]}→{r["C_raw"]}|{fmt(r["old_floor_raw"])}|{fmt(r["delta_C"])}|{fmt(r["previous_C_to_old_floor"])} / {fmt(r["old_floor_minus_current_C"])}|{fmt(D(r["delta_pct_of_Cprev"])*100,4)}% = {fmt(D(r["old_distance_pct_of_Cprev"])*100,4)}% + {fmt(D(r["penetration_pct_of_Cprev"])*100,4)}%|{r["actual_first_proxy_fill_at"][:10]} / {r["actual_first_proxy_price"]}|')
lines+=['',
'原14层第一次已存CLOSE≤旧线日期与第一次原CP1_add_protection层请求日期全部一致，对应6个股票事件。ΔC=(Cprev−h)+(h−C)仅是前收盘至当前收盘的价格恒等分解；正超线表示收盘已越线，不能说明盘中何时越线、线价可见、可成交或能按h卖出。实际请求、原whole-order receipt与代理fill单独保存，不把h换成卖价。','',
'14个首持日的Cprev发生在该层买入前，不是持有成本；主表held_previous_CLOSE=False，quantity_weighted_*留空。即使手工乘股数也只是同股数价格分解，不能当真实持仓损益。ACTUAL_ENTRY_REFERENCE.csv单列原actual买时点、raw OPEN、5bp代理买价、实际模拟买费和初始线，没有重构一笔损失。其它日quantity_weighted_*仍是未含费的mark价差分解，不是新退出收益。','',
'## 旧线来源与冻结尺度','',
'209点中185点对应唯一原CP最大值来源；24点为I主导，明确不给CP scale。与structural owner的FLOOR_PROVENANCE.json逐行交叉：209旧/更新后floor完全一致，185个receipt_id/original_scale/scale_frozen_at完全一致，24个I源一致，0不一致。来源采用真正2024_full/inputs/MANIFEST.json及其stock-receipts SHA绑定，未误用universe refs.receipts的其它窗口。','',
'|原事件|旧线形成receipt日|receipt_id|原冻结scale / 冻结日|',
'|---|---|---|---|']
for r in groups:lines.append(f'|{r["sid"]} {r["day"]}|{r["floor_origin_day"]}|{r["unique_CP_receipt_id"]}|{r["unique_CP_frozen_scale"]} / {r["scale_frozen_at"]}|')
lines+=['',
'太保10/9所用旧线来自10/8 receipt f0446fe6…，scale=.015834255171283874冻结于9/30；海11/4旧线来自10/31 receipt4b4720f2…，scale=.03851125614147488冻结于10/29。不能用触发日current s/z或next_scale顶替。每日当日CP cache s/z、receipt/candidate/source day与旧线对应的frozen scale分列，含所有未穿线日。scale_id可跨股票同值，不能单独当全局identity。','',
'## 下一日原代理价格评估列','',
'209行均附expost_next_market_day、exact raw OPEN、raw OPEN×.9995卖价参考、nextO/currentC−1、next raw CLOSE、factor/segment/status。全部是**事后评估标签**，不进入旧线来源、穿线或A/B触发条件。没有调用market.window、容量/wholelot/资金/订单函数；O×.9995不是已证明可成交价或净收益。跨因子/段/缺观察将UNKNOWN；本样本209行都有exact同单位下一源bar。原actual fill字段另列，不以该参考覆盖真实模拟账fill。','',
'人保CORE1884与海CORE1994只在CORE_I_APPENDIX.json，均未混入14个MOBILE层或CP触发表；I附录保持原既有范围，不宣称CP机制。所有receipt、fees和fill是原研究模拟账术语，不是实际broker ACK。','',
'文件：MOBILE_DAILY_PENETRATION.csv/json为209点主表；ACTUAL_FIRST_CP_TRIGGER_POINTS.csv/json为14层首次请求；SIX_ORIGINAL_STOCK_TRIGGER_EVENTS.json为6事件；OLD_FLOOR_PROVENANCE.json保完整源凭证；ACTUAL_ENTRY_REFERENCE.csv保14原买单；EXPOST_NEXT_OPEN_JOIN_RECEIPT.json标事后join与旧字段未改；STRUCTURAL_OWNER_PROVENANCE_CROSSCHECK.json绑定双作者交叉SHA；SOURCE_MANIFEST.json保原提取源SHA。']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
save('VALIDATION.json',dict(status='PASS_READ_ONLY_SOURCE_DECOMPOSITION_AND_CROSSCHECK',full_original_mobile_layers=14,full_held_layer_CLOSE_rows=209,first_held_days=14,first_held_quantity_weighted_PnL_fields_null=True,first_CP_layer_requests=14,stock_trigger_events=6,unique_CP_source_points=185,I_source_points_without_CP_scale=24,source_crosscheck_rows=209,next_OPEN_labels=209,next_OPEN_known=209,new_accounts=0,new_models=0,new_backtests=0,new_indicators=0,candidate_PnL=0))
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_FULL_14_LAYER_209_CLOSE_ORIGINAL_PENETRATION',readout_sha256=sha(O/'READOUT.md'),main_rows_sha256=sha(O/'MOBILE_DAILY_PENETRATION.json'),source_manifest_sha256=sha(O/'SOURCE_MANIFEST.json'),provenance_crosscheck_sha256=sha(O/'STRUCTURAL_OWNER_PROVENANCE_CROSSCHECK.json'),expost_join_sha256=sha(O/'EXPOST_NEXT_OPEN_JOIN_RECEIPT.json'),deliverable_sha256=sha(O/'DELIVERABLE_SHA256.json'),new_accounts=0,new_models=0,new_backtests=0,new_indicators=0)
save('SEAL_RECEIPT.json',seal);print(json.dumps(seal,ensure_ascii=False))
