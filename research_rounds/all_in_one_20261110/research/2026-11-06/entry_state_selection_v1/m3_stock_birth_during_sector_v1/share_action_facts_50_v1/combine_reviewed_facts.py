"""Combine reviewed official facts with first-interruption eligibility only. Never simulate."""
from pathlib import Path
from decimal import Decimal as D
import pandas as pd,json,hashlib,datetime,re
O=Path(__file__).resolve().parent;B=O.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
seal=json.loads((O/'PRE_RUN_SEAL.json').read_text());assert all(sha(Path(p))==h for p,h in seal['source_hashes'].items())
reviews={}
for name in ['REVIEW_SZ_22.json','REVIEW_SH_28.json']:
 for r in json.loads((O/name).read_text())['records']:
  assert r['sid'] not in reviews;reviews[r['sid']]=r
assert len(reviews)==50
audit=pd.read_csv(B/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv')
audit=audit[(audit.status=='FACTOR_PATH_UNKNOWN')&(audit.split_ratio!=1)].sort_values(['status_day','sid'])
acts=pd.read_csv(B/'lifecycle_v1/ACTIONS.csv')
cp=B.parent/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
calendar=sorted(pd.to_datetime(pd.read_parquet(cp,columns=['day']).day.unique()))
rows=[];candidates=[];facts=[];evidence_count=0
for t in audit.itertuples():
 x=reviews[t.sid]
 api=json.loads((O/'raw'/(t.sid+'.json')).read_text())
 hits=[r for r in api['raw']['records'] if r.get('F020D')==t.status_day];assert len(hits)==1;r=hits[0]
 assert api['requested_code']==t.sid[:6] and api['params']=={'scode':t.sid[:6]}
 assert all(x[k]==r[f] for k,f in [('record_date','F018D'),('ex_date','F020D'),('pay_date','F023D')])
 b=D(str(x['bonus_per_old_share']));c=D(str(x['transfer_per_old_share']));d=D(str(x['cash_per_old_share']))
 assert b==D(str(r.get('F010N') or 0))/10 and c==D(str(r.get('F011N') or 0))/10 and d==D(str(r.get('F012N') or 0))/10
 meta=json.loads((O/'notice_pdf'/(t.sid+'.json')).read_text());assert meta['metadata']['secCode']==t.sid[:6]
 assert sha(O/'notice_pdf'/(t.sid+'.pdf'))==meta['sha256']
 prev=calendar[calendar.index(pd.Timestamp(t.status_day))-1].strftime('%Y-%m-%d')
 core=D(str(t.core_qty));add=D(str(t.add_qty));q=core+add
 a=acts[(acts.round_id==t.round_id)&(acts.day<=x['record_date'])]
 aq=sum((D(str(z.q)) if str(z.side).startswith('buy') else -D(str(z.q))) for z in a.itertuples())
 # Integer tests are component and strategy-layer specific; these are not global floor rules.
 ci=(core*b)%1==0 and (core*c)%1==0
 ai=(add*b)%1==0 and (add*c)%1==0
 qi=(q*b)%1==0 and (q*c)%1==0
 flags={'capital_premium_explicit':x['capital_premium_explicit'] is True,'transfer_tax_exempt_explicit':x['transfer_tax_exempt_explicit'] is True,'no_bonus':b==0,'listing_same_ex':x['listing_date']==x['ex_date'],'record_previous_common_day':x['record_date']==prev,'core_new_integer':ci,'add_new_integer':ai,'aggregate_new_integer':qi,'register_reconstruction_matches':aq==q,'cash_pay_date_known_or_not_applicable':d==0 or x['pay_date'] is not None}
 reasons=[]
 reason_names={'capital_premium_explicit':'CAPITAL_PREMIUM_ORIGIN_NOT_EXPLICIT','transfer_tax_exempt_explicit':'TRANSFER_TAX_EXEMPTION_NOT_EXPLICIT','no_bonus':'BONUS_OUTSIDE_FIRST_PILOT_CONTRACT','listing_same_ex':'LISTING_DATE_MISSING_OR_NOT_EX_DATE','record_previous_common_day':'REGISTER_NOT_PREVIOUS_COMMON_DAY','core_new_integer':'CORE_NEW_SHARES_NOT_INTEGER','add_new_integer':'ADD_NEW_SHARES_NOT_INTEGER','aggregate_new_integer':'ACCOUNT_NEW_SHARES_NOT_INTEGER','register_reconstruction_matches':'ORIGINAL_REGISTER_QTY_MISMATCH','cash_pay_date_known_or_not_applicable':'PAY_DATE_MISSING'}
 for k,v in flags.items():
  if not v:reasons.append(reason_names[k])
 ent_multiplier=1+b+c
 refcash=x.get('official_reference_cash');refchange=x.get('official_reference_share_change')
 ev=x['evidence']
 def evs(key,alternative=None):
  value=ev.get(key)
  if value is None and alternative:value=ev.get(alternative)
  return json.dumps(value,ensure_ascii=False) if value is not None else ''
 out={'round_id':t.round_id,'sid':t.sid,'name_in_old_audit':t.name,'notice_sec_name':meta['metadata']['secName'],'security_class':'A','target_ex_date':t.status_day,'announcement_date':r['F006D'],'notice_index_datetime':str(pd.Timestamp(meta['metadata']['announcementTime'],unit='ms',tz='UTC').tz_convert('Asia/Shanghai')),'record_date':x['record_date'],'ex_date':x['ex_date'],'listing_date':x['listing_date'],'pay_date':x['pay_date'],'pay_date_status':'NOT_APPLICABLE_NO_CASH' if d==0 else 'DOCUMENTED','api_share_credit_date_not_listing_proof':r['F025D'],'cash_per_old_share':str(d),'bonus_per_old_share':str(b),'transfer_per_old_share':str(c),'actual_entitlement_split':str(ent_multiplier),'source_cash':str(t.cash_per_old_share),'source_split':str(t.split_ratio),'source_factor_previous':str(t.factor_previous),'source_factor_current':str(t.factor_current),'cash_delta_entitlement_minus_source':str(d-D(str(t.cash_per_old_share))),'split_delta_entitlement_minus_source':str(ent_multiplier-D(str(t.split_ratio))),'official_reference_cash':refcash,'official_reference_share_change':refchange,'official_reference_split_derived_one_plus_change':str(1+D(str(refchange))) if refchange is not None else None,'old_core_qty':str(core),'old_add_qty':str(add),'old_total_qty':str(q),'register_qty_reconstructed':str(aq),'previous_common_day':prev,'core_new_bonus_theoretical':str(core*b),'core_new_transfer_theoretical':str(core*c),'add_new_bonus_theoretical':str(add*b),'add_new_transfer_theoretical':str(add*c),'aggregate_new_bonus_theoretical':str(q*b),'aggregate_new_transfer_theoretical':str(q*c),'actual_fractional_allocation':None,'fractional_allocation_status':'NOT_NEEDED_FOR_THIS_FIXED_INITIAL_QTY' if qi else 'UNKNOWN_ACCOUNT_AWARD','capital_source_text':x.get('capital_source_text'),'capital_related_mention':x.get('capital_source_related_mention'),'tax_basis_text':x.get('tax_basis_text'),'bonus_face_value_tax_basis_per_bonus_share':x.get('bonus_face_value_tax_basis_per_bonus_share',x.get('bonus_tax_base_per_bonus_share')),'fractional_rule_text':x.get('fractional_rule_text'),'notice_url':meta['url'],'pdf_sha256':meta['sha256'],**flags,'first_pilot_gate_pass':all(flags.values()),'first_pilot_block_reasons':'|'.join(reasons),'evidence_record_date':evs('record_date'),'evidence_ex_date':evs('ex_date'),'evidence_listing_date':evs('listing_date'),'evidence_pay_date':evs('pay_date'),'evidence_cash':evs('cash','cash_per_old_share'),'evidence_bonus':evs('bonus','bonus_per_old_share'),'evidence_transfer':evs('transfer','transfer_per_old_share'),'evidence_capital_tax':evs('capital_source_and_tax','capital_source_text'),'evidence_tax_basis':evs('tax_schedule','tax_basis_text'),'evidence_fractional':evs('fractional','fractional_rule_text'),'evidence_official_reference':evs('official_reference','official_reference_formula'),'no_strategy_execution':True}
 if t.sid=='002881.SZ':out['official_reference_formula_caveat']='Printed final formula omits division operator; parameters are separately explicit. No repaired official formula inferred.'
 if t.sid=='600570.SH':out['official_reference_formula_caveat']='Displayed four-decimal parameters; retain original formula and unrounded arithmetic separately in review JSON.'
 rows.append(out);facts.append({'sid':t.sid,'review':x,'eligibility':out})
 if out['first_pilot_gate_pass']:candidates.append(out)
frame=pd.DataFrame(rows);frame.to_csv(O/'FIRST_ELIGIBILITY_COVERAGE.csv',index=False)
pd.DataFrame(candidates,columns=frame.columns).to_csv(O/'PILOT_CANDIDATES.csv',index=False)
frame[~frame.aggregate_new_integer].to_csv(O/'FRACTIONAL_ALLOCATION_UNKNOWN.csv',index=False)
frame[(frame.cash_delta_entitlement_minus_source.map(D)!=0)|(frame.split_delta_entitlement_minus_source.map(D)!=0)].to_csv(O/'PRECISION_CONFLICTS.csv',index=False)
frame[frame.official_reference_cash.notna()].to_csv(O/'OFFICIAL_REFERENCE_PARAMETERS.csv',index=False)
save(O/'ALL_FACTS_AND_EVIDENCE.json',facts)
assert [x['sid'] for x in candidates]==['002738.SZ']
summary={'scope':'50 fixed 2022 first share-action interruptions, facts only','target_count':50,'api_target_matches':50,'official_notice_pdfs':50,'record_dates_documented':50,'ex_dates_documented':50,'cash_events':int((frame.cash_per_old_share.map(D)>0).sum()),'cash_pay_dates_documented':int(frame.pay_date.notna().sum()),'no_cash_pay_date_not_applicable':int((frame.cash_per_old_share.map(D)==0).sum()),'new_unrestricted_listing_dates_documented':int(frame.listing_date.notna().sum()),'listing_same_ex':int(frame.listing_same_ex.sum()),'listing_after_ex':int(((frame.listing_date.fillna('')>frame.ex_date)&frame.listing_date.notna()).sum()),'listing_unknown':frame.loc[frame.listing_date.isna(),'sid'].tolist(),'explicit_premium_and_transfer_exemption':int((frame.capital_premium_explicit&frame.transfer_tax_exempt_explicit).sum()),'transfer_events':int((frame.transfer_per_old_share.map(D)>0).sum()),'bonus_events':int((frame.bonus_per_old_share.map(D)>0).sum()),'explicit_bonus_face_value':int(frame.bonus_face_value_tax_basis_per_bonus_share.notna().sum()),'aggregate_integer_initial_quantities':int(frame.aggregate_new_integer.sum()),'core_add_each_integer_initial_quantities':int((frame.core_new_integer&frame.add_new_integer).sum()),'fractional_allocation_unknown':frame.loc[~frame.aggregate_new_integer,'sid'].tolist(),'record_previous_common_day':int(frame.record_previous_common_day.sum()),'register_reconstructed_matches_old_qty':int(frame.register_reconstruction_matches.sum()),'fractional_rule_in_notice_count':int(frame.fractional_rule_text.notna().sum()),'official_reference_parameter_pairs':int(frame.official_reference_cash.notna().sum()),'source_precision_conflicts':frame.loc[(frame.cash_delta_entitlement_minus_source.map(D)!=0)|(frame.split_delta_entitlement_minus_source.map(D)!=0),'sid'].tolist(),'first_pilot_candidates':[x['sid'] for x in candidates],'qualified_original_add_cases':[x['sid'] for x in candidates if D(x['old_add_qty'])>0],'source_hashes_unchanged':all(sha(Path(p))==h for p,h in seal['source_hashes'].items()),'calendar_sha256':sha(cp),'strategy_runs':0,'old_status_changes':0,'candidate_does_not_authorize_execution':True,'warning':'Absence of explicit capital-premium/exemption proof is evidence insufficiency, not proof of taxation. These quantities are initial eligibility only; every strategy arm must independently satisfy the causal contract.'}
save(O/'COVERAGE_SUMMARY.json',summary)
save(O/'REVIEW_INPUT_HASHES.json',{str(p):sha(p) for p in [cp,O/'REVIEW_SH_28.json',O/'REVIEW_SZ_22.json',O/'review_sz_notices.py',Path(__file__)]})
print(json.dumps(summary,ensure_ascii=False,indent=2))
