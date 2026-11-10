"""Evidence overlay and adapter candidates only. No event is admitted; no engine import."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,re,hashlib,collections
O=Path(__file__).resolve().parent;B=O.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def csvsave(p,rs):
 keys=list(dict.fromkeys(k for r in rs for k in r))
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rs)
rows=list(csv.DictReader((O/'EVENT_FACT_COVERAGE.csv').open()))
# Main issuer implementation notices manually reviewed, not broad search-title matches.
configs={
'301031.SZ':('1221245898','0.1003962','0.0999999','2024-09-20'),
'600056.SH':('1221255690','0.02174',None,'2024-09-21'),
'002831.SZ':('1221291906','0.3302356','0.3242375','2024-09-26'),
'600938.SH':('1221377976','0.67653',None,'2024-10-14'),
'601006.SH':('1221407353','0.12924',None,'2024-10-17'),
'000582.SZ':('1221742081','0.1510004',None,'2024-11-16'),
'600873.SH':('1221757503','0.17596','0.17500','2024-11-15'),
'600995.SH':('1221891250','0.03919',None,'2024-11-30'),
'600663.SH':('1221939752','0.06288',None,'2024-12-06'),
'301589.SZ':('1222048111','0.2109033','0.2100000','2024-12-17'),
'002352.SZ':('1221573964','1.4','1.3939620','2024-10-31'),
'688208.SH':('1221114934','0.4','0.3903','2024-09-03'),
'300866.SZ':('1221139410','0.6',None,'2024-09-04'),
'300638.SZ':('1224016755','0.35','0.3487983','2025-06-27')}
notices=[];overlay=[];adapters=[];follow=[];sourcehash={};fact_counts=collections.Counter()
for r in rows:
 sid=r['sid'];n=None;o=dict(r);o.update(d_ref=None,notice_url=None,company_fact_resolution='UNREVIEWED',production_admitted=False)
 if sid in configs:
  aid,dc,dr,signature=configs[sid];base=O/'notice_pdf'/(sid+'_'+aid+'.pdf');meta=json.loads(base.with_suffix('.json').read_text());txt=base.with_suffix('.txt').read_text();compact=re.sub(r'\s+','',txt)
  assert meta['metadata']['secCode']==sid[:6] and sha(base.with_suffix('.pdf'))==meta['sha256'] and '证券代码：'+sid[:6] in compact
  assert str(D(dc)*10).rstrip('0').rstrip('.') in compact or str(D(dc)) in compact
  if dr:assert dr in compact
  if sid=='002352.SZ':
   rec,ex,pay,ann='2024-11-06','2024-11-07','2024-11-07','2024-10-31'
   hits=[x for x in json.loads(Path(r['source_path']).read_text())['raw']['records'] if x.get('F020D')==ex]
   assert len(hits)==2 and sum(D(str(x['F012N']))/10 for x in hits)==D(dc)
   assert all((x['F018D'],x['F020D'],x['F023D'],x['F006D'])==(rec,ex,pay,ann) for x in hits)
   components=[{'kind':'2024中期','gross_cash_per_share':'0.4'},{'kind':'回报股东特别分红','gross_cash_per_share':'1.0'}]
   o.update(record_date=rec,pay_date=pay,announcement_date=ann,d_cash=dc,cash_delta='0',company_dates_complete=True,pure_cash_reported=True,amount_matches_source=True,record_equals_prev=rec==r['previous_observation'],pay_equals_ex_fact=True)
  else:
   assert D(dc)==D(r['d_cash']);rec,ex,pay,ann=r['record_date'],r['ex_day'],r['pay_date'],r['announcement_date'];components=[]
  n={'sid':sid,'ex_date':ex,'record_date':rec,'pay_date':pay,'implementation_announcement_api_date':ann,'notice_publication_path_date':meta['metadata']['adjunctUrl'].split('/')[1],'notice_signature_date':signature,'d_cash':dc,'d_ref':dr,'d_source':r['d_source'],'notice_url':meta['url'],'pdf_path':str(base.with_suffix('.pdf')),'pdf_sha256':meta['sha256'],'text_path':str(base.with_suffix('.txt')),'code_verified':True,'gross_A_share_RMB_context_verified':True,'record_ex_pay_context_verified':True,'pure_cash_verified':True,'components':components,'validation_scope':'Manual issuer-notice text context verification; separate independent audit required. No PIT, investor-specific tax or production admission.'}
  if sid=='600663.SH':n['market_note']='A-share RMB0.06288 and A record 12/11, ex/pay12/12. Do not use B-share USD0.008808, record12/16 or pay12/24.'
  if sid=='600938.SH':n['market_note']='A-share RMB0.67653; do not use HKD0.74 declaration as A cash.'
  if sid=='600873.SH':n['date_note']='Signature 2024-11-15 differs from official publication path/API 2024-11-18. Neither is intraday known-at.'
  if sid=='002352.SZ':n['component_note']='Only this expressly documented combined distribution is merged. No generic same-date aggregation.'
  notices.append(n);o.update(d_ref=dr,notice_url=meta['url'])
 if D(r['split'])!=1:o['company_fact_resolution']='UNSUPPORTED_SHARE_ACTION'
 elif n and sid=='002352.SZ':o['company_fact_resolution']='NOTICE_DOCUMENTED_COMPOSITE'
 elif n and r['fact_status']=='CASH_PRECISION_NOTICE_REQUIRED':o['company_fact_resolution']='NOTICE_CASH_PRECISION_RESOLVED'
 elif r['fact_status']=='STRICT_FIELD_MATCH_REVIEW_REQUIRED':o['company_fact_resolution']='STRICT_API_FIELD_MATCH'+('_NOTICE_SAMPLED' if n else '')
 else:o['company_fact_resolution']='UNRESOLVED'
 fact_counts[o['company_fact_resolution']]+=1;overlay.append(o)
 ap=Path(r['source_action_path']);a=json.loads(ap.read_text());sourcehash[str(ap)]=sha(ap);assert a['series_id']==sid
 inds=[i for i,x in enumerate(a['events']) if x['effective_date']==r['ex_day']];assert len(inds)==1
 i=inds[0];e=a['events'][i];assert D(e['cash_per_old_share'])==D(r['d_source']) and D(e['split_ratio'])==D(r['split'])
 eid=sid+'|LOCAL_DISTRIBUTION_'+str(i+1).zfill(3)
 if D(r['split'])==1:
  ds=D(r['d_source']);res=abs(D(r['factor_old'])*D(r['previous_raw_close'])/(D(r['previous_raw_close'])-ds)/D(r['factor_new'])-1);assert res<=D('1e-11')
  adapters.append({'sid':sid,'economic_event_id_candidate':eid,'event_type':'PURE_CASH','record_date':o['record_date'],'ex_date':r['ex_day'],'pay_date':o['pay_date'],'d_source':r['d_source'],'d_cash':o['d_cash'],'d_ref':o['d_ref'],'factor_old':r['factor_old'],'factor_new':r['factor_new'],'previous_close':r['previous_raw_close'],'previous_day':r['previous_observation'],'source_coordinate_residual':str(res),'coordinate_scope_candidate':'FROZEN_SOURCE_TRANSLATION_ONLY','entitlement_scope_candidate':'OWN_REGISTER_Q_NET80_NOT_ACTUAL_TAX','local_action_ordinal':i+1,'local_action_path':str(ap),'local_action_sha256':sha(ap),'source_fact_path':r['source_path'],'source_fact_sha256':r['source_sha256'],'notice':n,'coordinate_verified_for_production':False,'entitlement_verified_for_production':False,'runtime_gate':'BLOCKED_PENDING_EVENT_ADMISSION_AND_TECHNICAL_TESTS','evidence_version':hashlib.sha256(json.dumps(o,sort_keys=True).encode()).hexdigest()})
 raw=json.loads(Path(r['source_path']).read_text())['raw']['records']
 for j,e in enumerate(a['events']):
  if not r['ex_day']<e['effective_date']<='2026-06-30':continue
  h=[x for x in raw if x.get('F020D')==e['effective_date']]
  follow.append({'sid':sid,'first_event_date':r['ex_day'],'later_date':e['effective_date'],'local_ordinal':j+1,'split_ratio':e['split_ratio'],'d_source':e['cash_per_old_share'],'current_api_same_date_rows':len(h),'audit_status':'UNADJUDICATED_SCOPE_INVENTORY_ONLY','holding_exposure_known':False})
assert len(adapters)==165 and len({x['economic_event_id_candidate'] for x in adapters})==165
existing=json.loads((B/'relative_priority_equity_run_2022_v1/EVENT_REGISTRY.json').read_text())
# Registry format is kept untouched and no admission is inferred from this candidate file.
save(O/'NOTICE_ADJUDICATIONS.json',notices);csvsave(O/'ADJUDICATED_EVENT_FACTS.csv',overlay);save(O/'EVENT_ADAPTER_CANDIDATES.json',adapters);csvsave(O/'FOLLOW_ON_EVENT_INVENTORY.csv',follow)
precision=[r for r in rows if r['fact_status']=='CASH_PRECISION_NOTICE_REQUIRED']
sumry={'first_events':167,'pure_cash_events_with_current_company_dates_and_gross_amount':165,'pure_cash_dates_all_record_previous_observation':all(str(r['record_equals_prev'])=='True' for r in overlay if D(r['split'])==1),'pure_cash_dates_all_pay_equals_ex':all(str(r['pay_equals_ex_fact'])=='True' for r in overlay if D(r['split'])==1),'fact_resolution_counts':dict(fact_counts),'notice_reviewed_events':len(notices),'precision_absolute_cash_delta_min':str(min(abs(D(r['cash_delta'])) for r in precision)),'precision_absolute_cash_delta_max':str(max(abs(D(r['cash_delta'])) for r in precision)),'precision_using_cash_in_source_factor_residual_min':str(min(D(r['amount_factor_residual']) for r in precision)),'precision_using_cash_in_source_factor_residual_max':str(max(D(r['amount_factor_residual']) for r in precision)),'documented_d_ref_d_cash_distinct':sum(n['d_ref'] is not None and D(n['d_ref'])!=D(n['d_cash']) for n in notices),'follow_on_source_events':len(follow),'follow_on_unique_stocks':len({r['sid'] for r in follow}),'follow_on_pure_cash':sum(D(r['split_ratio'])==1 for r in follow),'follow_on_share_events':sum(D(r['split_ratio'])!=1 for r in follow),'follow_on_api_match_count_distribution':dict(collections.Counter(r['current_api_same_date_rows'] for r in follow)),'follow_on_events_admitted':0,'adapter_candidates':len(adapters),'production_admitted':0,'backtest_runs':0,'point_in_time_certified':False,'personal_tax_certified':False,'original_source_action_hashes':sourcehash}
save(O/'ADJUDICATION_SUMMARY.json',sumry);print(json.dumps({k:v for k,v in sumry.items() if k!='original_source_action_hashes'},ensure_ascii=False,indent=2))
