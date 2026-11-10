"""Post-audit reporting correction only. Never reruns selection or simulation."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib,datetime
O=Path(__file__).resolve().parent;V=O.parent;src=V/'rounds_clockfixed/ALL_SHADOW_ROUNDS.csv'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source_hash=sha(src)
with src.open(newline='') as f:
 reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
assert len(rows)==5490
out=O/'ALL_SHADOW_ROUNDS_REPORTING_CORRECTED.csv';assert not out.exists(),'Never overwrite prior corrected view'
extra=['fees_to_date_original_reported','fee_total_from_trade_ledger','fee_field_correction','fee_state_as_of_day','conditional_liquidation_value_clock']
closed=0;changed=[];maxgap=D(0);validation=[]
for r in rows:
 old=r['fees_to_date'];r['fees_to_date_original_reported']=old;r['fee_total_from_trade_ledger']='';r['fee_field_correction']='NONE';r['fee_state_as_of_day']=r['last_known_mark_day'];r['conditional_liquidation_value_clock']='LAST_KNOWN_MARK_DAY_CLOSE_NOT_FINAL_EXIT' if r['last_known_mark_day'] else 'NO_MARK_AVAILABLE'
 if r['entry_status']!='CONDITIONAL_OPEN_PROXY':continue
 acts=json.loads(r['actions']) if r['actions'] else [];ledgerfee=D(r['entry_fee'])+sum((D(a['fee']) for a in acts),D(0));r['fee_total_from_trade_ledger']=str(ledgerfee)
 isclosed=r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND'
 if isclosed:
  closed+=1;assert r['all_fees'] and r['exit_day'] and r['net_pnl'];assert acts and acts[-1]['side']=='sell_all';total=D(r['all_fees']);gap=abs(total-ledgerfee);assert gap<D('1e-8'),(r['event_id'],r['sid'],'all_fees_not_ledger',gap)
  omitted=total-D(old);lastsell=D(acts[-1]['fee']);assert abs(omitted-lastsell)<D('1e-8'),(r['event_id'],r['sid'],'missing_fee_not_final_sell',omitted,lastsell)
  r['fees_to_date']=r['all_fees'];r['fee_field_correction']='CLOSED_TOTAL_INCLUDES_FINAL_SELL_FEE';r['fee_state_as_of_day']=r['exit_day'];changed.append(dict(event_id=r['event_id'],sid=r['sid'],status=r['status'],fees_to_date_original=old,fees_to_date_corrected=r['fees_to_date'],final_sell_fee=str(lastsell),all_fees_unchanged=r['all_fees'],net_pnl_unchanged=r['net_pnl']))
 else:
  gap=abs(D(old)-ledgerfee);assert gap<D('1e-8'),(r['event_id'],r['sid'],'open_or_unknown_fee_not_ledger',gap)
 maxgap=max(maxgap,gap)
 validation.append(dict(event_id=r['event_id'],sid=r['sid'],status=r['status'],ledger_total_fee=str(ledgerfee),report_total_fee=r['fees_to_date'],difference=str(gap)))
assert closed==4567 and len(changed)==4567
with out.open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields+extra);w.writeheader();w.writerows(rows)
with (O/'CLOSED_FEE_FIELD_CORRECTIONS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(changed[0]));w.writeheader();w.writerows(changed)
with (O/'LEDGER_FEE_VERIFICATION.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(validation[0]));w.writeheader();w.writerows(validation)
# Original textual fields, not floating point approximations, must remain exact.
with src.open(newline='') as f:oldrows=list(csv.DictReader(f))
with out.open(newline='') as f:newrows=list(csv.DictReader(f))
assert len(oldrows)==len(newrows)
for a,b in zip(oldrows,newrows):
 for k in fields:
  if k!='fees_to_date':assert a[k]==b[k],(a['event_id'],a['sid'],'unexpected_reporting_change',k)
 if a['status']!='COMPLETE_CONDITIONAL_STOCK_ROUND':assert a['fees_to_date']==b['fees_to_date']
assert sha(src)==source_hash,'Frozen original changed'
meta=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='Post-audit reporting view, not a new strategy run',frozen_source=str(src),frozen_source_sha256=source_hash,frozen_source_unchanged=True,rows=len(rows),closed_fee_fields_corrected=closed,all_original_fields_except_closed_fees_to_date_textually_unchanged=True,ledger_fee_rows_verified=len(validation),maximum_absolute_ledger_fee_rounding_difference=str(maxgap),no_selection_or_strategy_or_pnl_rerun=True,bug='On closed rows fees_to_date retained pre-final-sale snapshot, while all_fees/net_pnl/cashflow_to_date were already correct.',correction='Only closed fees_to_date becomes all_fees; preserve original value and mark fee clock. Keep conditional_liquidation fields as last_known_mark_day historical snapshot, never as closed realized P&L.',trusted_economic_fields=['net_pnl','net_return_on_buy_cash','all_fees','cashflow_to_date','actions'],historical_snapshot_fields=['conditional_liquidation_net_pnl','conditional_liquidation_net_fraction','last_known_mark_day','last_raw_close'],new_view=str(out))
(O/'CORRECTION_AND_QA.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
(O/'README.md').write_text('''# 审计后费用字段更正视图\n\n原封存结果未改，也未重新选股或运行策略。\n\n原CSV的4567个闭合行中，`fees_to_date`还是最终卖出之前的累计费用；`all_fees`、`net_pnl`、收益率和交易流水本已正确。此视图只把闭合行`fees_to_date`改为`all_fees`，原值另存于`fees_to_date_original_reported`，并新增费用时钟和逐笔费用校验字段。非闭合行该字段保持不变。\n\n`conditional_liquidation_net_pnl`及其比例仍是`last_known_mark_day`收盘的历史条件清算估值，不是闭合实现盈亏。闭合盈亏请用`net_pnl`，完整闭合费用请用`all_fees`；更正视图中的`fees_to_date`也已完整。\n\n所有其他原始字段逐字符一致，5454个条件入场轮次按初仓费加actions费用核验；最终卖费漏记金额逐行与最后sell_all费相等（仅浮点呈现差异容差1e-8）。没有改变任何绩效汇总或已冻结经济结果。\n''')
(O/'OUTPUT_HASHES.json').write_text(json.dumps({str(p):sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'},indent=2)+'\n')
print(json.dumps(meta,ensure_ascii=False,indent=2))
