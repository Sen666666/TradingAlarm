"""Separate, explicitly sourced composite-event overlay. Never edit first-pass or old research."""
from pathlib import Path
from decimal import Decimal
import json,hashlib
import pandas as pd
R=Path(__file__).resolve().parent
seal=json.loads((R/'PRE_RUN_SEAL.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in seal['source_hashes'].items())
df=pd.read_csv(R/'EVENT_FACT_COVERAGE.csv')
actions=pd.read_csv(R.parent/'lifecycle_v1/ACTIONS.csv')
old=pd.read_csv(R.parent/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv').set_index('round_id')
for fn in ['COMPOSITE_NOTICE_ADJUDICATION.json','COMPOSITE_NOTICE_ADJUDICATION_600188.json']:
 j=json.loads((R/fn).read_text()); ix=df.index[df.sid==j['sid']]; assert len(ix)==1
 i=ix[0]; t=df.loc[i]; assert t.coverage_status=='DUPLICATE_EX_DATE_UNRESOLVED'
 raw=json.loads((R/'raw'/(j['sid']+'.json')).read_text())['raw']['records']
 h=[x for x in raw if x.get('F020D')==j['ex_date']]
 assert len(h)==2 and {x['F044V'] for x in h}=={'年度分红','特别分红'}
 assert all(x['F018D']==j['record_date'] and x['F023D']==j['pay_date'] and x['F010N'] in (None,0) and x['F011N'] in (None,0) for x in h)
 assert len({x['F006D'] for x in h})==1 and len({x['F001V'] for x in h})==1
 cash=sum(Decimal(str(x['F012N']))/10 for x in h)
 assert cash==Decimal(str(j['gross_cash_per_share']))==Decimal(str(t.cash_per_old_share))
 aa=actions[(actions.round_id==t.round_id)&(actions.day<=j['record_date'])]
 qty=sum(float(a.q)*(1 if a.side.startswith('buy') else -1) for a in aa.itertuples())
 oq=float(old.loc[t.round_id,'core_qty']+old.loc[t.round_id,'add_qty'])
 assert qty>0 and qty==oq and j['record_date']==old.loc[t.round_id,'previous_observation']
 values={'record_date':j['record_date'],'pay_date':j['pay_date'],'implementation_announcement_date':h[0]['F006D'],'report_period':h[0]['F001V'],'public_gross_cash_per_share':float(cash),'current_api_clock_consistent':True,'amount_matches_old_terms':True,'reported_pure_cash':True,'register_held_qty_in_original_simulation':qty,'original_qty_at_interruption':oq,'register_qty_matches_interruption_qty':True,'record_equals_previous_observed_trading_day':True,'coverage_status':'PUBLIC_NOTICE_DOCUMENTED_COMPOSITE_NOT_PIT_OR_TAX_CERTIFIED','source_plan':' + '.join(x['F007V'] for x in h),'adjudication_file':fn,'adjudication_source_url':j['source_url']}
 for key,val in values.items():df.loc[i,key]=val
# Dated company notices are sample evidence; source response identity and PIT remain separately labelled.
checks=json.loads((R/'PUBLIC_SOURCE_CHECKS.json').read_text())['checks']
for x in checks:
 idx=df.index[df.sid==x['sid']]
 df.loc[idx,'sample_notice_url']=x['url']
 df.loc[idx,'sample_notice_date']=x['notice_date']
df.to_csv(R/'EVENT_FACTS_WITH_DOCUMENTED_COMPOSITES.csv',index=False)
bad=df[df.coverage_status=='FACT_CONFLICT_OR_INCOMPLETE_REQUIRES_ADJUDICATION'].copy()
bad['absolute_gross_difference_at_original_register_qty']=bad.amount_delta_per_share.abs()*bad.register_held_qty_in_original_simulation
bad.to_csv(R/'PRECISION_DIFFERENCES.csv',index=False)
q={'retrieved_events':len(df),'unique_date_source_rows':424,'documented_composite_events':2,'company_register_ex_pay_dates_available':int(df.record_date.notna().sum()),'strict_amount_and_date_matches_plus_documented_composites':int((df.coverage_status!='FACT_CONFLICT_OR_INCOMPLETE_REQUIRES_ADJUDICATION').sum()),'unresolved_amount_differences':len(bad),'max_absolute_per_share_difference':float(bad.amount_delta_per_share.abs().max()),'max_gross_snapshot_difference':float(bad.absolute_gross_difference_at_original_register_qty.max()),'sum_absolute_gross_snapshot_differences':float(bad.absolute_gross_difference_at_original_register_qty.sum()),'snapshot_warning':'Only event-date gross-equity amount arithmetic at old simulated inventory, not PnL or a bound on subsequent state-dependent path effects.','positive_register_qty':int((df.register_held_qty_in_original_simulation>0).sum()),'register_equals_previous_observation':int(df.record_equals_previous_observed_trading_day.astype(bool).sum()),'register_qty_equals_original_interruption_qty':int(df.register_qty_matches_interruption_qty.astype(bool).sum()),'pay_date_equals_ex_date':int((df.pay_date==df.status_day).sum()),'old_formal_UNKNOWN_count_remains':508,'strategy_replays':0,'actual_tax_estimates':0,'source_dated_notices_sampled_not_universal':True,'source_returns_code_name':False,'historical_API_is_archived_PIT':False}
(R/'POST_ADJUDICATION_SUMMARY.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(q,ensure_ascii=False,indent=2))
