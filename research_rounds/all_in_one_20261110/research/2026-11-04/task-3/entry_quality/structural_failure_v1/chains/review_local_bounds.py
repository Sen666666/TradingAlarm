"""Independent thin join/price/cash audit of sibling local bounds (no Market)."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
O=Path(__file__).resolve().parent;B=O.parent/'executable_bounds/SIMPLE_LOCAL_CASH_RESULTS.json'
xs=json.loads((O/'COMPLETE_ORIGINAL_CHAINS.json').read_text());bounds=json.loads(B.read_text());byid={x['campaign']['campaign_id']:x for x in xs};out=[]
def eq(a,b,k):assert abs(D(str(a))-D(str(b)))<D('.000001'),(k,a,b)
for r in bounds['cases']:
 c=byid[r['campaign_id']];t=c['local_diagnostic_trigger'];assert r['trigger_at'][:10]==t['first_negative_native_event_after_actual_first_fill'];assert r['T_layer_ids']==t['T_inventory_layer_ids']
 a=r['A'];b=r['B'];v=dict(sid=r['sid'],trigger=r['trigger_at'],A=a,B=b,independent_checks=[])
 if a['status'].startswith('EXACT_SIMPLE'):
  o=next(o for o in c['observations'] if o['day']==a['at'][:10]);bar=o['original_raw_and_adjusted_bar'];eq(D(str(bar['raw_open']))*D('.9995'),a['price'],r['sid']+' original raw OPEN minus 5bps')
  eq(D(a['shares'])*D(a['price'])-D(a['fee']),a['exit_net'],r['sid']+' A net')
  control=r['isolated_T_inventory_control'];eq(D(a['exit_net'])-D(control['later_exit_net']),a['local_delta'],r['sid']+' A delta')
  eq(sum((D(p['shares'])*D(p['price'])-D(p['fee']) for p in control['parts']),D(0)),control['later_exit_net'],r['sid']+' original isolated control')
  old_actual_parts_net=sum((D(p['net_cash']) for e in c['entries'] if e['layer'] in r['T_layer_ids'] for p in e['actual_layer_accounting']['actual_sale_parts']),D(0))
  v['original_allocated_old_layer_net_cash']=str(old_actual_parts_net);v['native_logical_order_repricing_fee_bridge']=str(old_actual_parts_net-D(control['later_exit_net']));v['independent_checks']+=['original raw OPEN less 5bps exact','A net and delta exact','isolated control logical-order cash exact']
 if b['status'].startswith('EXACT_SIMPLE'):
  eq(D(b['retained_old_units_exit_net'])-D(b['original_post_T_cash']),b['local_delta'],r['sid']+' B delta')
  removed=sum((D(e['actual_layer_accounting']['cost']) for e in c['entries'] if e['layer'] in r['removed_post_T_mobile_ids']),D(0));eq(removed,b['avoided_mobile_actual_buycash'],r['sid']+' B original buycash');v['independent_checks']+=['B original buycash exact','B cash difference exact']
 out.append(v)
result=dict(status='PASS_THIN_ORIGINAL_PRICE_AND_CASH_REVIEW',source=str(B),source_sha256=hashlib.sha256(B.read_bytes()).hexdigest(),rows=out,new_accounts=0,independent_market_or_fee_engine_calls=0,limitations=['Native fee schedules, eligible-window and capacity lookup are sibling implementation scope; this thin review checks original extracted rawOPEN and logical cash arithmetic, not a second full execution engine.','Mixed preexisting pending cases remain uncomputed, never zero.','A and B are alternative diagnostics and cannot be summed; B persists beyond future +1 and is broader than the separate -1-to-next-+1 candidate.','Native-context local cash differences are not account returns or reusable proceeds.'])
(O/'LOCAL_BOUND_THIN_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# 局部执行边界补充（非账户收益）','','原13链全部保留。A是T时原库存隔离子账的提前退出；B是首负T以后原周期内拒绝新增mobile合同的宽诊断。两者不可相加、不能按个例挑选；B不会在下一+1恢复，故不是精确负leg候选的绩效。','','|股票|A 局部差额|B 局部差额|原约束说明|','|---|---:|---:|---|']
for v in out:
 a=v['A'];b=v['B'];fmt=lambda z:'未计算' if z['local_delta'] is None else f'{D(z["local_delta"]):,.2f}'
 note=[]
 if a['status']=='NO_INCREMENT_ALL_T_UNITS_ALREADY_LATCHED':note.append('T库存已全部被原卖单锁定，A增量0')
 if a.get('prior_ineligible_windows'):note.append('更早OPEN代理不可卖：'+', '.join(s[:10] for s in a['prior_ineligible_windows']))
 if a['local_delta'] is None or b['local_delta'] is None:note.append('既有部分mobile pending，需要订单状态重建，保持未定')
 lines.append('|'+v['sid']+'|'+fmt(a)+'|'+fmt(b)+'|'+'；'.join(note)+'|')
lines += ['', '盈新宽B少亏10701.83，略小于删去两层终局亏10706.78，因为原whole-stock逻辑卖单费用要重算；不能直接加减原层allocated fee。其两次新买发生在01-20已有正event之后，精确“-1暂停、+1恢复”并不拒绝它们。', '', '供销12-09事件到首个合法12-14 OPEN已失去图上提前量，A仅+0.97；众生A−24080.11、太保A−5305.48和B−2481.60保留为真实赢家反例。初步正向局部界限不支持跳过全分母和尾部检查直接建新规则。', '', '本薄核直接用原链的原始OPEN独立核对5bps代理价，并复核A/B现金与原买款；未另调用市场构造器或费用引擎。完整原窗口/容量/费率责任仍在 executable_bounds 的源协议与计算。']
(O/'LOCAL_BOUNDS_READOUT.md').write_text('\n'.join(lines)+'\n')
print('PASS:',len(out),'original triggers,',sum(v['A']['status'].startswith('EXACT_SIMPLE') for v in out),'exact A prices/cash,',sum(v['B']['status'].startswith('EXACT_SIMPLE') for v in out),'exact B cash pairs, unknown retained')
