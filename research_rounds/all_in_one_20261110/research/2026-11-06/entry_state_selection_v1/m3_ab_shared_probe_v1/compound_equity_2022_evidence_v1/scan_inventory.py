"""Read frozen research inputs, write only this new evidence directory. No account imports/runs."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib,collections,time,datetime,shutil
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent;E=R/'m3_stock_birth_during_sector_v1'
A=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')
S=E/'share_action_facts_50_v1'; hashes={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):hashes[str(p)]=sha(p);return json.loads(p.read_text())
def rows(p):hashes[str(p)]=sha(p);return list(csv.DictReader(p.open()))
def dump(n,o): (O/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def csvout(n,rr):
 if not rr:return
 keys=list(dict.fromkeys(k for r in rr for k in r));f=(O/n).open('w',newline='');w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rr);f.close()
start=time.monotonic();all_births=rows(E/'SEALED_ALL_BIRTH_EVENTS.csv');births=[r for r in all_births if r['window']=='2022' and r['event_type'] in ('A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR')]
sids=sorted({r['sid'] for r in births});assert len(births)==12917 and len(sids)==1458
names={r['sid']:r['name'] for r in births};counts=collections.Counter(r['sid'] for r in births)
inv=read(B/'annual_2022_marked_nav_v1/economic_run_2022_annual_once/YEAR_END_OR_STOP_INVENTORY.json');held=collections.defaultdict(int)
for r in inv['active_layers']:held[r['sid']]+=r['qty']
facts={(r['sid'],r['review'].get('ex_date')):r for r in read(S/'ALL_FACTS_AND_EVIDENCE.json')}
perm=[]
for origin,path,condition in [('CASH402',E/'cash_dividend_source_feasibility_v1/EVENT_FACTS_WITH_DOCUMENTED_COMPOSITES.csv',lambda r:r['coverage_status'] in ['CURRENT_PUBLIC_FACTS_MATCHED_NOT_PIT_OR_TAX_CERTIFIED','PUBLIC_NOTICE_DOCUMENTED_COMPOSITE_NOT_PIT_OR_TAX_CERTIFIED']),('PRECISION24',E/'cash_dividend_precision_24_v1/ADJUDICATED_24.csv',lambda r:True),('ENTRY10_COORDINATE_ONLY',E/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv',lambda r:r['status']=='FACTOR_AT_ENTRY_UNKNOWN')]:
 for r in rows(path):
  if condition(r):perm.append({'sid':r['sid'],'ex_date':r['status_day'],'origin':origin,'entitlement_permitted':origin!='ENTRY10_COORDINATE_ONLY'})
assert len(perm)==436
for r in read(B/'known_halt_dividend_candidate_v1/CANDIDATES_V1.json')['distributions']:perm.append({'sid':r['sid'],'ex_date':r['ex_date'],'origin':'LIMITED_CANDIDATE_600403','entitlement_permitted':True})
assert len(perm)==437;permat={(r['sid'],r['ex_date']):r for r in perm};assert len(permat)==437
all_events=[];coverage=[];missing=[];local_cache={}
for sid in sids:
 p=A/(sid+'.json')
 if not p.exists():missing.append(sid);continue
 a=read(p);local_cache[sid]=a
 for ev in a.get('coverage_evidence',[]):
  ep=Path(ev['path']);actual=sha(ep);assert actual==ev['sha256'],str(ep);hashes[str(ep)]=actual
 coverage.append({'sid':sid,'name_current_frozen_label':names[sid],'original_2022_birth_count':counts[sid],'local_action_count':len(a['events']),'local_action_path':str(p),'local_action_sha256':sha(p),'held_qty_at_stop':held.get(sid,0)})
 for i,e in enumerate(a['events']):
  d=e['effective_date']
  if not '2022-06-23'<=d<='2022-12-30':continue
  typ=e.get('classification');cash=D(e.get('cash_per_old_share','0'));split=D(e.get('split_ratio','1'));compound=(split!=1 or typ!='ordinary_cash_and_pro_rata_bonus');text=e.get('raw_text','')
  subtype='RIGHTS_SUBSCRIPTION_REQUIRED' if typ=='rights_issue_no_subscription' else 'TARGETED_NON_PRO_RATA' if typ=='targeted_non_pro_rata_issuance' else ('CASH_PLUS_BONUS' if '送' in text else 'CASH_PLUS_CAPITALIZATION') if cash>0 and split!=1 else 'CAPITALIZATION_OR_SPLIT_ONLY' if split!=1 else 'PURE_CASH'
  f=facts.get((sid,d));r=f['review'] if f else {};pr=permat.get((sid,d));known=r.get('announcement_date');clock_missing=[k for k in ['announcement_date','record_date','ex_date','listing_date'] if compound and not r.get(k)]
  if cash>0 and not r.get('pay_date'):clock_missing+=['pay_date']
  all_events.append({'sid':sid,'name_current_frozen_label':names[sid],'economic_event_id':sid+'|LOCAL_DISTRIBUTION_'+str(i+1).zfill(3),'effective_date_local':d,'local_classification':typ,'type':subtype,'complex':compound,'cash_per_old_share_local':str(cash),'split_ratio_local':str(split),'local_paid_at':e.get('paid_at'),'local_new_shares_sellable_at':e.get('new_shares_sellable_at'),'raw_text':text,'original_437_permitted':bool(pr),'original_437_origin':pr['origin'] if pr else None,'original_437_entitlement_permitted':pr['entitlement_permitted'] if pr else False,'local_50_official_evidence':bool(f),'official_announcement_date':known,'official_known_upper_bound':known+'T23:59:59.999999+08:00' if known else None,'record_date':r.get('record_date'),'official_ex_date':r.get('ex_date'),'pay_date':r.get('pay_date'),'listing_date':r.get('listing_date'),'missing_official_date_fields':clock_missing,'same_day_cash_available_before_open_proven':False,'existing_fact_review_block_reasons':r.get('block_reasons',[]),'notice_url':r.get('notice_url'),'pdf_sha256':r.get('source_pdf_sha256'),'held_qty_at_stop':held.get(sid,0),'priority_at_current_stop':0 if sid=='000987.SZ' and d=='2022-06-23' else 1 if sid in held else 2,'evidence_domain':'CURRENT_HISTORICAL_RECORDS_NOT_PIT','strategy_future_injection_allowed':False})
assert not missing
all_events.sort(key=lambda x:(x['effective_date_local'],x['sid']));complex_events=[r for r in all_events if r['complex']];held_events=[r for r in all_events if r['held_qty_at_stop']>0]
selected=complex_events[:5];assert [r['sid'] for r in selected]==['000987.SZ','600850.SH','300762.SZ','600056.SH','000625.SZ']
(O/'sources').mkdir(exist_ok=True);reuse=[]
for r in selected:
 sid=r['sid']
 if r['local_50_official_evidence']:
  for folder,ext in [('notice_pdf','.pdf'),('notice_pdf','.text.json'),('notice_pdf','.json'),('notices','.json')]:
   src=S/folder/(sid+ext);dst=O/'sources'/(sid+('_index' if folder=='notices' else '')+ext);hashes[str(src)]=sha(src);shutil.copyfile(src,dst);assert sha(src)==sha(dst)
  pdf=O/'sources'/(sid+'.pdf');assert sha(pdf)==r['pdf_sha256'];reuse.append(sid)
summary={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'universe':'Original frozen 2022 A_SECTOR_BIRTH and B_STOCK_BIRTH_DURING_SECTOR only, no holding pruning','birth_rows':len(births),'sids':len(sids),'local_action_files':len(coverage),'missing_local_actions':missing,'scan_start':'2022-06-23','scan_end':'2022-12-30','all_events':len(all_events),'complex_events':len(complex_events),'complex_type_counts':dict(collections.Counter(r['type'] for r in complex_events)),'complex_original_437_permitted':sum(r['original_437_permitted'] for r in complex_events),'complex_existing_official50_evidence':sum(r['local_50_official_evidence'] for r in complex_events),'all_events_original_437_permitted':sum(r['original_437_permitted'] for r in all_events),'current_held_sids':len(held),'held_future_events':len(held_events),'held_future_complex_events':sum(r['complex'] for r in held_events),'selected_max5':[r['sid'] for r in selected],'reused_original_official_pdf_sids':reuse,'new_official_acquisition_candidates':[r['sid'] for r in selected if not r['local_50_official_evidence']],'acquisition_limit':'At most five compound events including reused sources; missing two may each use one official index query and one PDF download; no retries after access denial, no registration; 20 second request timeout.','offline_scan_elapsed_seconds':time.monotonic()-start,'no_account_import_or_run':True,'no_old_input_write':True,'no_event_dates_fed_to_strategy':True,'source_limit':'Local actions are declared research proxy, not exhaustive official corporate-action history. Only original action-list coverage is inventoried.','future_note':'Current holdings are triage only, not prediction of ownership at future record date. Unknown future announcement dates remain unknown.'}
csvout('ORIGINAL_2022_UNIVERSE.csv',coverage);csvout('ORIGINAL_437_PERMITS.csv',perm);csvout('ALL_LOCAL_EVENTS_20220623_20221230.csv',all_events);csvout('COMPLEX_EVENTS.csv',complex_events);csvout('CURRENT_HOLDINGS_FUTURE_EVENTS.csv',held_events);dump('SELECTED_MAX5.json',selected);dump('INVENTORY_SUMMARY.json',summary);dump('PROTECTED_SOURCE_HASHES.json',hashes);print(json.dumps(summary,ensure_ascii=False,indent=2))
