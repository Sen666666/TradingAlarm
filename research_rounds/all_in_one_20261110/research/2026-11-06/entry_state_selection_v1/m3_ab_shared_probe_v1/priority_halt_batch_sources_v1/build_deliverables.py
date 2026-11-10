import pathlib,json,csv,re,hashlib,collections,datetime,shutil
from bs4 import BeautifulSoup
O=pathlib.Path(__file__).parent;B=O.parent
J=lambda p:json.loads(pathlib.Path(p).read_text())
H=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def out(name,x): (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def csvout(name,rows):
 with (O/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
plan=J(O/'PLAN.json');ledger=[json.loads(s) for s in (O/'REQUEST_LEDGER.jsonl').read_text().splitlines()]
p=list(csv.DictReader((O/'TARGET_RUNS.csv').open()));assert len(p)==55
E=[r for r in csv.DictReader((B/'daily_gap_inventory_v1/UNUSABLE_QUOTE_EPISODES.csv').open()) if r['I_exit_priority']=='True'];assert len(E)==54
emap={gid:e for e in E for gid in e['component_missing_run_ids'].split(';')}
daily=list(csv.DictReader((B/'daily_gap_inventory_v1/DAILY_ISSUES_V2.csv').open()))
invalid=list(csv.DictReader((B/'daily_gap_inventory_v1/INVALID_EXISTING_ROW_DETAILS.csv').open()))
prior=list(csv.DictReader((B/'priority_halt_evidence_batch12_v1/FINAL_CLASSIFICATION.csv').open(encoding='utf-8-sig')))
prior_map={(r['sid'],r['episode_start'],r['episode_end']):r for r in prior}
source_reuse=[]
for month,rel,url in [('2022-03','priority_halt_evidence_batch12_v1/raw/47_SZSE_2022_03_monthly.html','https://docs.static.szse.cn/www/market/periodical/month/W020220408565950756780.html'),('2022-04','halt_evidence_batch_v1/raw/szse_2022_04_suspensions.html','https://docs.static.szse.cn/www/market/periodical/month/W020220511397986494671.html')]:
 dest=O/'raw'/('szse_'+month.replace('-','_')+'_reused.html');shutil.copyfile(B/rel,dest)
 source_reuse.append({'month':month,'source_path':str(B/rel),'path':str(dest),'url':url,'sha256':H(dest),'network_requests':0})
for rel in ['halt_evidence_batch_v1/raw/sse_suspension_page.html','halt_evidence_batch_v1/raw/sse_table_config.js','priority_halt_evidence_batch12_v1/FINAL_CLASSIFICATION.csv']:
 source_reuse.append({'source_path':str(B/rel),'sha256':H(B/rel),'network_requests':0,'used_for':'route discovery or inherited evidence overlay only'})
out('LOCAL_SOURCE_REUSE.json',source_reuse)
urlmap={r['path']:r.get('url') for r in ledger if r.get('url')};urlmap.update({r['path']:r['url'] for r in source_reuse if r.get('path')})
monthly=[];monthstats=[]
for f in sorted(O.glob('raw/szse_*.html')):
 soup=BeautifulSoup(f.read_bytes().decode('gb18030'),'html.parser');cap=soup.caption.get_text(' ',strip=True);m=re.search(r'(20\d{2})\.(\d{2})',cap);assert m
 month='-'.join(m.groups());assert month in plan['SZ_months_fixed'];n=0
 for tr in soup.select('tr'):
  x=[td.get_text(' ',strip=True) for td in tr.select('td')]
  if len(x)!=5 or not re.fullmatch(r'\d{6}',x[0]):continue
  n+=1;monthly.append({'source_family':'SZSE_MONTHLY','source_file':str(f.relative_to(O)),'source_url':urlmap[str(f)],'source_sha256':H(f),'report_month':month,'sid':x[0]+'.SZ','historical_name':x[1],'reason':x[2],'start':x[3].replace('/','-'),'resume':None if x[4].startswith('9999') else x[4].replace('/','-'),'resume_raw':x[4],'public_known_at':None,'row_id':f'SZ_{month}_{n:03}'})
 monthstats.append({'month':month,'caption':cap,'rows':n,'path':str(f),'url':urlmap[str(f)],'sha256':H(f)})
out('SZ_MONTHLY_ROWS.json',monthly);out('SZ_MONTH_COVERAGE.json',{'required':plan['SZ_months_fixed'],'fetched_or_reused':monthstats,'missing_months':sorted(set(plan['SZ_months_fixed'])-{r['month'] for r in monthstats}),'caption_verified_not_url_inferred':True})
sse=[];pagination=[]
for page in range(1,7):
 f=O/'raw'/('sse_halt_range.json' if page==1 else f'sse_halt_range_p{page}.json');j=J(f);ph=j['pageHelp'];assert ph['pageNo']==page and ph['total']==521 and ph['pageCount']==6
 pagination.append({'page':page,'rows':len(j['result']),'total':ph['total'],'page_count':ph['pageCount'],'path':str(f),'sha256':H(f)})
 for i,r in enumerate(j['result'],1):
  s=dict(r);s.update(source_family='SSE_HISTORY_API',source_file=str(f.relative_to(O)),source_url=urlmap[str(f)],source_sha256=H(f),row_id=f'SSE_P{page}_R{i:03}',public_known_at=None);sse.append(s)
uniquekeys={json.dumps({k:r[k] for k in ['startStopDate','stopReason','productCode','endStopReason','controlType','endStopDate','stopTime','type','productName']},sort_keys=True) for r in sse};assert len(sse)==len(uniquekeys)==521
out('SSE_HISTORY_ROWS.json',sse);out('SSE_PAGINATION_QA.json',{'pages':pagination,'rows':len(sse),'unique_rows':len(uniquekeys),'all_pages_same_total':True,'duplicates':0,'complete_for_exact_returned_query':True,'historical_database_completeness_not_proven':True,'range':['2022-01-13','2023-04-17'],'not_a_resume_publication_feed':True})
def datefmt(s):return s[:4]+'-'+s[4:6]+'-'+s[6:8] if s and len(s)==8 else s

def matched_rows(sid,start,end):
 if sid.endswith('SH'):
  return [r for r in sse if r['productCode']==sid[:6] and r['controlType']=='TR' and datefmt(r['startStopDate'])<=end and r['endStopDate'] and not r['endStopDate'].startswith('9999') and datefmt(r['endStopDate'])>=start]
 return [r for r in monthly if r['sid']==sid and ((r['resume'] is not None and r['start'][:10]<=end and r['resume'][:10]>start) or start<=r['start'][:10]<=end)]
def classify(sid,day,rows):
 bound=[];point=[]
 for r in rows:
  if sid.endswith('SH'):
   if datefmt(r['startStopDate'])<=day<=datefmt(r['endStopDate']) and (r['type']=='LXTP' or (r['type']=='LSTP' and r['stopTime']=='WH')):bound.append(r['row_id'])
  else:
   if r['resume'] is not None and r['start']<=day+' 09:30' and r['resume']>=day+' 15:00':bound.append(r['row_id'])
   elif r['start']==day+' 09:30':point.append(r['row_id'])
 if bound:return 'OFFICIAL_RETROSPECTIVE_BOUNDED_HALT_INTERVAL',';'.join(bound)
 if point:return 'OFFICIAL_START_POINT_ONLY_END_UNKNOWN',';'.join(point)
 return 'UNKNOWN_NO_BOUNDED_DAILY_SUPPORT',''
runrows=[];sessions=[]
for r in p:
 e=emap[r['gap_id']];m=matched_rows(r['sid'],e['episode_start'],e['episode_end']);days=sorted({z['day'] for z in daily if z['sid']==r['sid'] and z['issue']=='MISSING_ROW' and r['gap_start']<=z['day']<=r['gap_end']});assert len(days)==int(r['missing_common_sessions'])
 old=prior_map.get((e['sid'],e['episode_start'],e['episode_end']),{})
 sc=[]
 for day in days:
  cl,ids=classify(r['sid'],day,m);sc.append(cl)
  sessions.append({'gap_id':r['gap_id'],'episode_id':e['episode_id'],'sid':r['sid'],'day':day,'row_type':'MISSING_ROW','official_daily_fact_status':cl,'source_row_ids':ids,'public_known_at':'UNKNOWN','preopen_status':'EXISTING_REGISTRY_UNCHANGED' if r['registry_covered_sessions']!='0' else 'NOT_ADMITTED_UNKNOWN_OR_REVIEW_ONLY','prior_batch_grade':old.get('grade',''),'prior_batch_review_candidate':day in old.get('review_candidate_sessions','').split(';'),'new_admitted':False,'source_price_modified':False})
 nbound=sc.count('OFFICIAL_RETROSPECTIVE_BOUNDED_HALT_INTERVAL');npoint=sc.count('OFFICIAL_START_POINT_ONLY_END_UNKNOWN')
 status='FULL_BOUNDED_DAILY_INTERVAL_MATCH' if nbound==len(days) else 'PARTIAL_BOUNDED_DAILY_INTERVAL_MATCH' if nbound else 'START_ANCHOR_ONLY_NO_COMPLETE_INTERVAL' if m else 'NO_MATCH_WITHIN_COLLECTED_SOURCES'
 reasons=';'.join(sorted({z.get('reason',z.get('stopReason','')) for z in m}))
 if r['sid']=='000528.SZ':typ='CASH_ELECTION';basis='prior official fulltext and this batch direct original'
 elif r['sid']=='000970.SZ' or '配股' in reasons:typ='RIGHTS_ISSUE';basis='official reason or direct original'
 elif r['sid']=='600403.SH' or (r['sid']=='600595.SH' and r['gap_start']=='2022-01-13') or '风险警示' in reasons or (r['sid']=='600515.SH' and r['gap_start']=='2022-05-18'):typ='RISK_STATUS_CHANGE';basis='official reason or prior reviewed case; not itself share-count change'
 elif '重大资产重组' in reasons or r['sid'] in ['002092.SZ','002060.SZ']:typ='PROPOSED_MA_OR_REORGANIZATION';basis='official reason or prior reviewed case; no executed equity bridge'
 elif '重组委审核' in reasons or r['sid'] in ['600009.SH','600461.SH']:typ='MA_REVIEW';basis='official reason or prior reviewed case'
 else:typ='UNKNOWN_SPECIFIC_EQUITY_EFFECT';basis='generic halt reason or source not collected; no inference from price/factor'
 runrows.append({'gap_id':r['gap_id'],'episode_id':e['episode_id'],'sid':r['sid'],'historical_current_name_input':r['name'],'gap_start':r['gap_start'],'gap_end':r['gap_end'],'missing_sessions':len(days),'official_match_status':status,'bounded_interval_sessions':nbound,'start_point_only_sessions':npoint,'no_bounded_support_sessions':len(days)-nbound,'matched_row_count':len(m),'matched_row_ids':';'.join(z['row_id'] for z in m),'reasons':reasons,'event_type':typ,'event_type_basis':basis,'official_known_at':'UNKNOWN','new_admitted_sessions':0,'existing_registry_sessions':int(r['registry_covered_sessions']),'prior_batch_grade':old.get('grade',''),'prior_batch_review_candidate_sessions':len([d for d in days if d in old.get('review_candidate_sessions','').split(';')]),'unknown_corporate_action_bridge':'PRESERVED'})
for e in E:
 for z in invalid:
  if z['sid']==e['sid'] and e['episode_start']<=z['day']<=e['episode_end']:
   cl,ids=classify(z['sid'],z['day'],matched_rows(z['sid'],e['episode_start'],e['episode_end']));old=prior_map.get((e['sid'],e['episode_start'],e['episode_end']),{})
   sessions.append({'gap_id':'SYNTHETIC_NONQUOTE_IN_EPISODE','episode_id':e['episode_id'],'sid':z['sid'],'day':z['day'],'row_type':'EXPLICIT_SYNTHETIC_EVENT_BAR_NOT_OBSERVED_QUOTE','official_daily_fact_status':cl,'source_row_ids':ids,'public_known_at':'UNKNOWN','preopen_status':'NOT_ADMITTED_UNKNOWN_OR_REVIEW_ONLY','prior_batch_grade':old.get('grade',''),'prior_batch_review_candidate':z['day'] in old.get('review_candidate_sessions','').split(';'),'new_admitted':False,'source_price_modified':False})
assert len(sessions)==311
for r in runrows:
 r['match_layer']='BATCH_HALT_LIST_ONLY; separate direct-original overlay below'
 r['direct_original_overlay']='FIXED_DAILY_INTERVAL_CONFIRMED; prior-date announcement candidate' if r['sid']=='000970.SZ' else 'CONDITIONAL_CONTINUOUS_START; no certified final stop/resume; prior-date announcement candidate' if r['sid']=='000528.SZ' else 'ORIGINAL_NOT_OBTAINED_THIS_BATCH' if r['sid'] in ['600595.SH','601377.SH'] else 'NOT_SAMPLED_THIS_BATCH'
 r['direct_original_bounded_sessions']=6 if r['sid']=='000970.SZ' else 0
 r['direct_original_date_end_candidate']='2022-02-11T23:59:59+08:00' if r['sid']=='000970.SZ' else '2022-01-06T23:59:59+08:00' if r['sid']=='000528.SZ' else ''
for r in sessions:
 r['match_layer']='BATCH_HALT_LIST_ONLY; separate direct-original overlay below'
 r['direct_original_fixed_daily_interval_support']=r['sid']=='000970.SZ'
 r['direct_original_conditional_continuous_review_candidate']=r['sid']=='000528.SZ'
 r['direct_original_date_end_candidate']='2022-02-11T23:59:59+08:00' if r['sid']=='000970.SZ' else '2022-01-06T23:59:59+08:00' if r['sid']=='000528.SZ' else ''
csvout('TARGET_RUN_MATCHES.csv',runrows);csvout('TARGET_SESSION_MATCHES.csv',sorted(sessions,key=lambda r:(r['sid'],r['day'])))
notices=[];notice_summary=[]
for sid in ['000528','000970','600595','601377']:
 sz=sid.startswith('0');f=O/'raw'/('sz_notice_' if sz else 'sse_notice_');f=f.with_name(f.name+sid+'.json');j=J(f)
 if sz:rows=j['data'];reported=j['announceCount'];allpages=len(rows)>=reported
 else:rows=[r for g in j['result'] for r in (g if isinstance(g,list) else [g])];reported=j['pageHelp']['total'];allpages=j['pageHelp']['pageCount']==1
 for r in rows:
  title=r['title'] if sz else r['TITLE'];date=r['publishTime'] if sz else r['SSEDATE'];url='https://disc.static.szse.cn/download'+r['attachPath'] if sz else 'https://www.sse.com.cn'+r['URL']
  notices.append({'sid':sid+('.SZ' if sz else '.SH'),'title':title,'raw_date_field':date,'date_field_name':'publishTime' if sz else 'SSEDATE','field_semantics':'official UI labels announcement time; only daily precision observed','exact_publication_timestamp_verified':False,'earlier_date_end_upper_bound_candidate':date[:10]+'T23:59:59+08:00','same_session_preopen_inference_allowed':False,'original_url':url,'index_source':str(f.relative_to(O)),'source_sha256':H(f),'title_category':'CASH_ELECTION' if '现金选择权' in title else 'RIGHTS_ISSUE' if '配股' in title else 'DIVIDEND_DISTRIBUTION' if '分派' in title or '分红' in title else 'HALT' if '停牌' in title or '停复牌' in title else 'OTHER'})
 notice_summary.append({'sid':sid+('.SZ' if sz else '.SH'),'returned_flat_announcements':len(rows),'api_total_groups_or_announcements':reported,'one_page_complete_for_sample':allpages,'historical_index_obtained':True,'original_pdf_obtained':sz,'actual_publication_clock_verified':False,'date_precision':'day (all 00:00:00)' if sz else 'day only','not_evidence_of_49_name_availability':True})
csvout('HISTORICAL_ANNOUNCEMENT_INDEX.csv',notices)
out('ANNOUNCEMENT_CAPABILITY.json',{'sample_size':4,'target_sids':49,'sample_coverage_of_sids':4/49,'index_success':4,'index_success_rate_within_fixed_sample':1.0,'original_bytes_success':2,'original_bytes_success_rate_within_fixed_sample':0.5,'original_failures':'Two official SSE 301 targets returned identical gzip-compressed HTML script challenge, not PDF. Preserved; no challenge execution, cookie construction or alternate host bypass.','originals_max_four_notices':True,'flat_announcement_rows':len(notices),'non_midnight_sz_timestamp_rows':sum(' ' in r['raw_date_field'] and not r['raw_date_field'].endswith('00:00:00') for r in notices),'actual_publication_clock_verified':0,'samples':notice_summary,'title_categories':dict(collections.Counter(r['title_category'] for r in notices)),'limitations':['Sample 4/49, not 49/49 index verification.','SSE total counts grouped results; flat sibling documents produce 31 rows from 27 result groups.','Official UI labels 公告时间. Date precision can be reviewed as historical announced date; no original publication-hour proof or historical crawl timestamp.','Prior-date conservative day-end candidates require shared rule adjudication. Same-day date labels cannot establish preOPEN.','Dividend distribution keyword category is available as title search/string, but no such event returned in these 4 windows; actual dividend index coverage remains untested.']})
clock={'status':'RESEARCH_CANDIDATES_ONLY_NO_REGISTRATION','SSE_halt':{'route_source':'raw/sse_trade_tip.js lines 118-127, 274-305','columns':['productCode','productName','controlType','startStopDate','endStopDate','stopTime','stopReason','endStopReason','type'],'meaning':'Official UI: 停牌起始日/停牌终止日. End date inclusive halt date, not a resume date. TR selects equity trading; exclude convert/putback rows. WH explicitly 全天; LXTP date interval with empty stopTime retained as retrospective continuous-date range. No actual publication field.','new_known_at':0},'SZ_monthly':{'columns':['代码','证券简称','停牌原因','停牌时间','复牌时间'],'meaning':'Effective start and resume boundary, not publication clock. 9999/12/31 means endpoint UNKNOWN; no indefinite forward fill.','new_known_at':0},'SZ_index':{'route_source':['raw/sz_concatversion.js: disc_path /api/disc','raw/sz_listedAnnoun_min.js: historyUrl /announcement/annList and cols ggsj 公告时间','raw/sz_concatDisc_min.js: historical POST JSON, publishTimeFormat hides 00:00 clock'],'observed':'87/87 publishTime values exactly 00:00:00; official announcement date precision only.','potential_date_only_upper_bound':'For date strictly before target day, daily close-of-day +08:00 upper bound may be reviewed, never assumed midnight.'},'SSE_index':{'route_source':'raw/sse_announcements.js lines 8-20 and historical list rendering SSEDATE','observed':'31/31 flat document rows have SSEDATE YYYY-MM-DD and no actual clock field.'},'direct_original_pairs':[{'sid':'000528.SZ','index_date':'2022-01-06','evidence':'notice_original_000528.pdf + text: announcement2022-03; explicitly says current notice刊登日 follows Jan5 trading day and Jan6 publication, signature Jan5 differs. Jan14 open continuous halt until conditions.','date_end_review_candidate':'2022-01-06T23:59:59+08:00','no_equity_execution':True,'overlaps_prior_batch_candidate':True},{'sid':'000970.SZ','index_date':'2022-02-11','evidence':'notice_original_000970.pdf + schedule: Feb11 刊登配股发行公告; Feb16-Feb23 全天停牌; Feb24 conditional successful ex-right or failed resumption.','date_end_review_candidate':'2022-02-11T23:59:59+08:00','no_equity_execution':True,'overlaps_prior_batch_candidate':True},{'sid':'600595.SH','index_date':'2022-01-13','evidence':'Same target-session date; PDF challenge. Existing registered evidence unchanged.','date_end_review_candidate':None},{'sid':'601377.SH','index_date':'2022-08-12','evidence':'Prior-date index + official halt interval Aug17-Aug24; original PDF challenge. Title alone is not complete rights/halt terms.','date_end_review_candidate':None}]}
out('EVENT_DATE_VS_KNOWN_AT.json',clock)
# Only read protected files; hash checks do not import engines.
checks=[]
for rel,h in plan['input_hashes'].items():checks.append({'path':str(B/rel),'expected':h,'observed':H(B/rel),'ok':H(B/rel)==h,'group':'plan_input'})
for path,h in J(B/'daily_gap_inventory_v1/PROTECTED_LEDGER_HASHES.json').items():checks.append({'path':path,'expected':h,'observed':H(path),'ok':H(path)==h,'group':'old_ledger'})
for rel,h in J(B/'priority_halt_evidence_batch12_v1/FINAL_SEAL.json')['files'].items():checks.append({'path':str(B/'priority_halt_evidence_batch12_v1'/rel),'expected':h,'observed':H(B/'priority_halt_evidence_batch12_v1'/rel),'ok':H(B/'priority_halt_evidence_batch12_v1'/rel)==h,'group':'prior_batch_seal'})
out('PROTECTED_INPUT_CHECK.json',checks);assert all(r['ok'] for r in checks)
missing=[r for r in sessions if r['row_type']=='MISSING_ROW'];synth=[r for r in sessions if r['row_type']!='MISSING_ROW']
summary={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'target_runs':55,'target_sids':49,'priority_episodes':54,'missing_sessions':309,'synthetic_nonquote_sessions':2,'all_unusable_sessions':311,'target_exchange_run_counts':dict(collections.Counter(r['sid'][-2:] for r in runrows)),'target_start_range':[min(r['gap_start'] for r in p),max(r['gap_start'] for r in p)],'target_end_max':max(r['gap_end'] for r in p),'exchange_missing_sessions':{ex:sum(r['missing_sessions'] for r in runrows if r['sid'].endswith(ex)) for ex in ['SH','SZ']},'run_status_counts':dict(collections.Counter(r['official_match_status'] for r in runrows)),'runs_with_any_official_row_match':sum(r['matched_row_count']>0 for r in runrows),'bounded_interval_missing_sessions_list_only':sum(r['official_daily_fact_status']=='OFFICIAL_RETROSPECTIVE_BOUNDED_HALT_INTERVAL' for r in missing),'start_point_only_missing_sessions':sum(r['official_daily_fact_status']=='OFFICIAL_START_POINT_ONLY_END_UNKNOWN' for r in missing),'missing_sessions_without_bounded_interval_in_lists':sum(r['official_daily_fact_status']!='OFFICIAL_RETROSPECTIVE_BOUNDED_HALT_INTERVAL' for r in missing),'synthetic_session_statuses':synth,'event_type_counts':dict(collections.Counter(r['event_type'] for r in runrows)),'SZ_required_months':14,'SZ_obtained_months':len(monthstats),'SZ_obtained_rows':len(monthly),'SSE_total_history_rows':521,'SSE_unique_history_rows':521,'SSE_pages_complete':6,'SSE_target_bounded_runs':sum(r['sid'].endswith('SH') and r['official_match_status']=='FULL_BOUNDED_DAILY_INTERVAL_MATCH' for r in runrows),'SSE_target_missing_days_bounded':sum(r['bounded_interval_sessions'] for r in runrows if r['sid'].endswith('SH')),'unique_bounded_missing_sessions_lists_plus_direct_originals':sum(r['official_daily_fact_status']=='OFFICIAL_RETROSPECTIVE_BOUNDED_HALT_INTERVAL' or r['direct_original_fixed_daily_interval_support'] for r in missing),'direct_original_only_fixed_interval_missing_sessions':6,'direct_original_conditional_continuous_review_missing_sessions':10,'new_admitted_sessions':0,'existing_registry_sessions_unchanged':sum(r['existing_registry_sessions'] for r in runrows),'new_economic_accounts':0,'engine_imported':False,'minute_data_used':False,'OHLC_or_factor_modified':False,'search_index_api_requests':sum(r['category']=='search_index_api' for r in ledger),'document_read_attempts':sum(r['category']=='document' for r in ledger),'actual_network_calls':len(ledger),'curl_network_seconds':round(sum(r.get('elapsed_seconds',0) for r in ledger),3),'paid_accounts_or_tokens_used':False,'original_request_cap':20,'amended_request_cap':21,'document_cap':24,'elapsed_seconds_from_plan':round((datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(plan['created_at'])).total_seconds(),3),'direct_fetch_raw_bytes':sum(r.get('bytes',0) for r in ledger),'search_result_bytes':sum((O/'raw'/f).stat().st_size for f in ['search1.json','search2.json','sz_notice_search.json']),'protected_checks':dict(collections.Counter(r['group'] for r in checks)),'all_protected_checks_pass':True,'all_results_retrospective_nonPIT':True,'network_closed':True}
assert summary['search_index_api_requests']==21 and summary['document_read_attempts']==22
out('COVERAGE_AND_COST.json',summary)
out('FINAL_QA.json',{'target_count_matches':True,'episode_count_matches':True,'session_count_matches':True,'SSE_page_sequence_and_unique_rows_verified':True,'monthly_caption_verified':True,'all_protected_inputs_unchanged':True,'budgets_with_authorized_amendment_satisfied':True,'unknown_not_forward_filled':True,'original_600595_registry_unchanged':True,'no_equity_execution_or_simulation':True,'SSE_original_pdf_failures_not_misclassified':True})
print(json.dumps(summary,ensure_ascii=False,indent=2))
