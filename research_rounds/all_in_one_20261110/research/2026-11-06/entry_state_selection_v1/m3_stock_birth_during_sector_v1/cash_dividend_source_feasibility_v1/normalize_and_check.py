"""Offline, frozen-list field checks only. Does not simulate or change official UNKNOWN rows."""
from pathlib import Path
import json,hashlib,re,statistics,datetime
from decimal import Decimal
import pandas as pd
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
seal=json.loads((ROOT/'PRE_RUN_SEAL.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in seal['source_hashes'].items()),'frozen input changed; halt normalization'
targets=seal['targets']
actions=pd.read_csv(BASE/'lifecycle_v1/ACTIONS.csv')
audit=pd.read_csv(BASE/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv').set_index('round_id')
results=[]; timing=[]; all_hist=0; candidates=[]
for t in targets:
 sid=t['sid']; p=ROOT/'raw'/(sid+'.json')
 o={**t,'record_date':None,'pay_date':None,'implementation_announcement_date':None,'report_period':None,'public_gross_cash_per_share':None,'source_record_count':0,'exact_ex_date_candidates':0,'current_api_clock_consistent':False,'amount_matches_old_terms':False,'reported_pure_cash':False,'register_held_qty_in_original_simulation':None,'record_equals_previous_observed_trading_day':None,'tax_rate':None,'actual_tax_cash_date':None,'archived_point_in_time_verified':False,'source_returns_security_identity':False,'coverage_status':'NOT_RETRIEVED'}
 if not p.exists():results.append(o);continue
 d=json.loads(p.read_text());raw=d['raw'];rows=raw['records'];all_hist+=len(rows)
 assert d['sid']==sid and d['requested_code']==sid[:6] and d['params']=={'scode':sid[:6]}
 assert d['endpoint']=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139'
 timing.append(d['transport']['elapsed_s'])
 o.update({'source_path':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'retrieved_at_utc':d['retrieved_at_utc'],'source_record_count':len(rows),'source_resultcode':raw.get('resultcode'),'declared_count_matches':raw.get('count')==len(rows),'declared_total_matches':raw.get('total')==len(rows),'identity_basis':'requested scode + presealed universe; raw records omit security code/name'})
 hits=[r for r in rows if r.get('F020D')==t['status_day']]
 o['exact_ex_date_candidates']=len(hits)
 candidates.extend([{'sid':sid,'round_id':t['round_id'],'target_ex_date':t['status_day'],'old_cash_per_share':t['cash_per_old_share'],**r} for r in hits])
 if len(hits)!=1:
  o['coverage_status']='EX_DATE_ABSENT' if not hits else 'DUPLICATE_EX_DATE_UNRESOLVED';results.append(o);continue
 r=hits[0]
 ann,rec,ex,pay=[r.get(k) for k in ('F006D','F018D','F020D','F023D')]
 o.update({'record_date':rec,'pay_date':pay,'implementation_announcement_date':ann,'report_period':r.get('F001V'),'dividend_type':r.get('F044V'),'source_plan':r.get('F007V'),'source_bonus_per10':r.get('F010N'),'source_capitalization_per10':r.get('F011N')})
 if r.get('F012N') is not None:
  amount=Decimal(str(r['F012N']))/10
  o['public_gross_cash_per_share']=float(amount)
  o['amount_delta_per_share']=float(amount-Decimal(str(t['cash_per_old_share'])))
  o['amount_matches_old_terms']=abs(o['amount_delta_per_share'])<=1e-9
 pure=re.fullmatch(r'10派([0-9.]+)元\(含税\)',r.get('F007V') or '')
 o['reported_pure_cash']=bool(pure and r.get('F010N') in (None,0) and r.get('F011N') in (None,0) and abs(Decimal(pure.group(1))/10-Decimal(str(t['cash_per_old_share'])))<=Decimal('1e-9'))
 valid=lambda s: isinstance(s,str) and bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',s))
 clock=all(valid(s) for s in [ann,rec,ex,pay]) and ann<=rec<ex<=pay
 o['current_api_clock_consistent']=clock
 if clock:
  o['announcement_to_record_calendar_days']=(datetime.date.fromisoformat(rec)-datetime.date.fromisoformat(ann)).days
  o['record_to_ex_calendar_days']=(datetime.date.fromisoformat(ex)-datetime.date.fromisoformat(rec)).days
  o['ex_to_pay_calendar_days']=(datetime.date.fromisoformat(pay)-datetime.date.fromisoformat(ex)).days
  aa=actions[actions.round_id==t['round_id']].copy()
  aa['signed_q']=aa.apply(lambda a:a.q if str(a.side).startswith('buy') else -a.q,axis=1)
  before=aa[aa.day<=rec]
  o['register_held_qty_in_original_simulation']=float(before.signed_q.sum())
  o['entry_on_or_before_record']=str(audit.loc[t['round_id'],'entry_day'])<=rec
  o['actions_record_exclusive_to_ex_exclusive']=int(((aa.day>rec)&(aa.day<ex)).sum())
  o['record_equals_previous_observed_trading_day']=rec==audit.loc[t['round_id'],'previous_observation']
  o['original_qty_at_interruption']=float(audit.loc[t['round_id'],'core_qty']+audit.loc[t['round_id'],'add_qty'])
  o['register_qty_matches_interruption_qty']=o['register_held_qty_in_original_simulation']==o['original_qty_at_interruption']
 checks=[clock,o['amount_matches_old_terms'],o['reported_pure_cash'],o['declared_count_matches'],o['declared_total_matches'],raw.get('resultcode')==200]
 o['coverage_status']='CURRENT_PUBLIC_FACTS_MATCHED_NOT_PIT_OR_TAX_CERTIFIED' if all(checks) else 'FACT_CONFLICT_OR_INCOMPLETE_REQUIRES_ADJUDICATION'
 results.append(o)
pd.DataFrame(candidates).to_csv(ROOT/'EXACT_DATE_CANDIDATES.csv',index=False)
frame=pd.DataFrame(results); frame.to_csv(ROOT/'EVENT_FACT_COVERAGE.csv',index=False)
known=frame[frame.coverage_status=='CURRENT_PUBLIC_FACTS_MATCHED_NOT_PIT_OR_TAX_CERTIFIED']
sumry={'target_events':len(targets),'retrieved_symbols':len(timing),'historical_records_returned':all_hist,'coverage_status_counts':frame.coverage_status.value_counts().to_dict(),'qualified_date_and_gross_term_matches':len(known),'field_present_counts':{k:int(frame[k].notna().sum()) for k in ['record_date','pay_date','implementation_announcement_date','public_gross_cash_per_share']},'identity_echo_present':int(frame.source_returns_security_identity.sum()),'archived_point_in_time_verified':0,'actual_individual_tax_verified':0,'eligible_quantities_in_original_simulation':int((pd.to_numeric(frame.register_held_qty_in_original_simulation,errors='coerce')>0).sum()),'record_equals_previous_observed_trading_day':int(frame.record_equals_previous_observed_trading_day.fillna(False).sum()),'pay_date_equals_ex_date':int((frame.pay_date==frame.status_day).sum()),'http_request_timing_s':{'mean':statistics.mean(timing),'median':statistics.median(timing),'max':max(timing),'total':sum(timing)} if timing else None,'stop_files':[p.name for p in ROOT.glob('STOP_*.json')],'frozen_inputs_unchanged':all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in seal['source_hashes'].items()),'scope':'Company public-fact retrieval only. Old UNKNOWN statuses unchanged; no strategy replay or actual tax inference.'}
assert sumry['frozen_inputs_unchanged'],'frozen input changed; halt'
sumry['qualified_rows_with_positive_original_register_qty']=int((pd.to_numeric(known.register_held_qty_in_original_simulation,errors='coerce')>0).sum())
sumry['qualified_rows_register_qty_matches_interruption_qty']=int(known.register_qty_matches_interruption_qty.fillna(False).sum()) if 'register_qty_matches_interruption_qty' in known else 0
(ROOT/'COVERAGE_SUMMARY.json').write_text(json.dumps(sumry,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(sumry,ensure_ascii=False,indent=2))
