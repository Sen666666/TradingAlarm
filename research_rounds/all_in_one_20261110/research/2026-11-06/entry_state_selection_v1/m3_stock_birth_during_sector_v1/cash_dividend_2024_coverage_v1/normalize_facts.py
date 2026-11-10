"""Offline field normalization. No event admission or simulated portfolio actions."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,re,hashlib,collections,datetime
O=Path(__file__).resolve().parent;B=O.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
seal=json.loads((O/'SOURCE_SEAL.json').read_text());assert all(sha(Path(p))==h for p,h in seal['sources'].items())
rows=[];candidates=[];sources={};timings=[]
for t in seal['targets']:
 sid=t['sid'];p=B/'cash_dividend_source_feasibility_v1/raw'/(sid+'.json');origin='EXISTING_2022_ACQUISITION'
 if not p.exists():p=O/'raw'/(sid+'.json');origin='NEW_2024_ACQUISITION'
 o={**t,'fact_origin':origin,'source_path':str(p),'source_sha256':None,'candidate_count':0,'company_dates_complete':False,'pure_cash_reported':False,'amount_matches_source':False,'d_cash':None,'cash_delta':None,'amount_factor_residual':None,'record_date':None,'pay_date':None,'announcement_date':None,'fact_status':'NOT_ACQUIRED','archived_PIT_verified':False,'actual_individual_tax_verified':False,'coordinate_admitted':False,'entitlement_admitted':False}
 if not p.exists():rows.append(o);continue
 b=json.loads(p.read_text());assert b['sid']==sid and b['requested_code']==sid[:6] and b['params']=={'scode':sid[:6]} and b['endpoint']=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139'
 h=sha(p);sources[str(p)]=h;a=b['raw'];assert a['resultcode']==200 and a['count']==a['total']==len(a['records'])
 hits=[r for r in a['records'] if r.get('F020D')==t['ex_day']];o.update(source_sha256=h,retrieved_at_utc=b['retrieved_at_utc'],candidate_count=len(hits),api_identity_echo=False,identity_basis='request scode + frozen market-qualified sid + source terms; API omits identity')
 for r in hits:candidates.append({'sid':sid,'target_ex_day':t['ex_day'],**r})
 if origin=='NEW_2024_ACQUISITION':timings.append(b['transport']['elapsed_s'])
 if len(hits)!=1:o['fact_status']='EX_DATE_ABSENT' if not hits else 'MULTIPLE_ROWS_REQUIRES_NOTICE';rows.append(o);continue
 r=hits[0];ann,rec,ex,pay=[r.get(k) for k in ('F006D','F018D','F020D','F023D')]
 valid=lambda x:isinstance(x,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',x)
 clock=bool(all(valid(x) for x in [ann,rec,ex,pay]) and ann<=rec<ex<=pay)
 amt=D(str(r['F012N']))/10 if r['F012N'] is not None else None
 text=re.fullmatch(r'10派([0-9.]+)元\(含税\)',r.get('F007V') or '')
 pure=bool(text and r.get('F010N') in (None,0) and r.get('F011N') in (None,0) and D(text.group(1))/10==amt)
 same=bool(amt is not None and abs(amt-D(t['d_source']))<=D('1e-9'))
 residual=abs((D(t['factor_old'])*D(t['previous_raw_close'])/(D(t['previous_raw_close'])-amt))/D(t['factor_new'])-1) if amt is not None else None
 o.update(company_dates_complete=clock,pure_cash_reported=pure,amount_matches_source=same,d_cash=str(amt) if amt is not None else None,cash_delta=str(amt-D(t['d_source'])) if amt is not None else None,amount_factor_residual=str(residual) if residual is not None else None,amount_factor_residual_scope='PURE_CASH_SOURCE_COORDINATE_TEST' if D(t['split'])==1 else 'CASH_ONLY_DIAGNOSTIC_NOT_APPLICABLE_TO_SHARE_VALIDATION',record_date=rec,pay_date=pay,announcement_date=ann,plan=r.get('F007V'),bonus_per10=r.get('F010N'),capitalization_per10=r.get('F011N'),record_equals_prev=rec==t['previous_observation'],pay_equals_ex_fact=pay==ex,report_period=r.get('F001V'),dividend_type=r.get('F044V'))
 if D(t['split'])!=1:o['fact_status']='SHARE_ACTION_UNSUPPORTED'
 elif not clock or not pure:o['fact_status']='DATE_OR_TERMS_CONFLICT'
 elif same:o['fact_status']='STRICT_FIELD_MATCH_REVIEW_REQUIRED'
 else:o['fact_status']='CASH_PRECISION_NOTICE_REQUIRED'
 rows.append(o)
def writecsv(p,rs):
 cols=list(dict.fromkeys(k for r in rs for k in r))
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rs)
writecsv(O/'EVENT_FACT_COVERAGE.csv',rows);writecsv(O/'EXACT_DATE_CANDIDATES.csv',candidates)
summary={'target_events':len(rows),'target_pure_cash':sum(D(r['split'])==1 for r in rows),'target_share_events':sum(D(r['split'])!=1 for r in rows),'acquired_events':sum(r['source_sha256'] is not None for r in rows),'new_requests_successful':len(timings),'existing_cache_events':sum(r['source_sha256'] is not None and r['fact_origin']=='EXISTING_2022_ACQUISITION' for r in rows),'candidate_rows':len(candidates),'status_counts':dict(collections.Counter(r['fact_status'] for r in rows)),'unique_rows_date_complete':sum(r['company_dates_complete'] for r in rows),'date_complete_record_equals_prev':sum(r['company_dates_complete'] and r.get('record_equals_prev',False) for r in rows),'date_complete_pay_equals_ex':sum(r['company_dates_complete'] and r.get('pay_equals_ex_fact',False) for r in rows),'backtest_runs':0,'admitted_events':0,'current_historical_source_not_PIT':True,'sources_unchanged':all(sha(Path(p))==h for p,h in seal['sources'].items()),'source_hashes':sources}
(O/'COVERAGE_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='source_hashes'},ensure_ascii=False,indent=2))
