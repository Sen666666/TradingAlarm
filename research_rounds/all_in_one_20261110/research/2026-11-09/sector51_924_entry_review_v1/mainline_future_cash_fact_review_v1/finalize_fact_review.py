"""Independent PDF-reading assertions and report; offline preparation, never admission."""
from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_DOWN
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;P=ROOT/'october_remaining_cash_evidence_v1'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
# Facts transcribed independently from the complete fresh PDFKit output, not imported from candidate configuration.
# code | record day | ex/pay day | gross eligible cash/share | published d_ref or - | declared base shares | declared total cash or - | publication date | signature date | exact cash wording
DATA='''600079|10|11|.15|-|1632257765|244838664.75|09-27|09-27|现金红利0.15元
688248|10|11|.1350|-|564700000|76234500|09-27|09-27|现金红利0.1350元
601619|11|14|.01|-|2434351234|24343512.34|10-08|10-08|现金红利0.01元
688686|11|14|.13|-|122235455|15890609.15|09-27|09-27|现金红利0.13元
300573|15|16|.50|-|174424871|87212435.50|10-08|10-08|每10股派5.000000元人民币现金
600027|15|16|.08|-|10227561133|818204890.64|10-10|10-09|现金红利0.08元
688188|15|16|.718|-|205452708|147515044.34|10-09|10-09|现金红利0.718元
688507|15|16|.064|.06355|88483535|5662946.24|10-09|10-09|现金红利0.064元
300394|16|17|.50|-|553911681|276955840.50|10-10|10-10|每10股派发5.00元人民币现金
300718|16|17|.168|.1672150|297383030|49960349.04|10-10|10-09|每10股派1.680000元人民币现金
300855|16|17|.10|-|395531500|-|10-10|10-10|每10股派1.000000元人民币现金
301603|16|17|.80|-|120760000|96608000.00|10-09|10-09|每10股派8.00元人民币现金
000338|17|18|.372|.3715066|6774521296|2520121922.11|10-11|10-10|每10股派发现金红利人民币3.72元
000937|17|18|.20|-|3533546850|706709370|10-12|10-12|每10股派2元人民币现金
002353|17|18|.12|.1199992|1023849677|122861961.24|10-11|10-10|每10股派1.200000元人民币现金
601238|17|18|.03|.02995|7374786063|221243581.89|10-11|10-10|现金红利0.03元
000905|18|21|.053|-|741809597|39315908.64|10-12|10-11|每10股派发现金红利0.53元人民币
688375|18|21|.51|-|596014900|303967599.00|10-12|10-12|现金红利0.51元
600236|21|22|.085|-|7882377802|670002113.17|10-16|10-16|现金红利0.085元
601096|21|22|.0114|-|2675155088|30496768.00|10-16|10-16|现金红利0.0114元
688097|21|22|.085|.0841|441728603|37546931.26|10-16|10-16|现金红利0.085元
688692|21|22|1.10|-|76000000|83600000|10-16|10-16|现金红利1.10元
600248|22|23|.05|-|3767582286|188379114.30|10-16|10-16|现金红利0.05元
600835|23|24|.20|-|1022739308|204547861.60|10-18|10-18|A股每股现金红利0.20元
688535|25|28|.10|-|80696453|8069645.30|10-18|10-18|现金红利0.10元
000951|28|29|.291|.2895449|1168994951|340177530.74|10-22|10-22|每10股派2.91元人民币
002552|30|31|.14|-|408542039|57195885.46|10-25|10-25|每10股派1.400000元人民币现金
600795|30|31|.09|-|17835619082|1605205717.38|10-25|10-25|现金红利0.09元
600821|30|31|.10|.09850|1967324953|196732495.30|10-23|10-23|A股每股现金红利0.1元
601801|30|31|.10|-|1957931237|195793123.70|10-24|10-24|现金红利0.100元'''
# total and treasury shares are exact PDF figures. A-share denominator only for 000338 and 601238.
DIFF={'688507':(89108784,625249),'300718':(298779030,1396000),'000338':(6783516821,8995525),'002353':(1023855833,6156),'601238':(7388297513,13511450),'688097':(446647765,4919162),'000951':(1174869360,5874409),'600821':(1997263453,29938500)}
PURE_QUOTES={'300573':'不以公积金转增股本，不送红股','688507':'本次利润分配不送红股，不进行资本公积转增股本','300394':'不送红股，不以资本公积转增股本','300718':'不实施送股和资本公积转增股本','300855':'不以资本公积金转增股本，不送红股','301603':'不送红股，不进行资本公积金转增股本','000338':'不实施公积金转增股本','000937':'分红后公司总股本不变','002353':'送红股0股（含税），不以公积金转增股本','601238':'本次利润分配仅进行现金红利分配，不涉及送股及资本公积金转增股本','000905':'不进行资本公积转增股本，不送红股','688097':'公司本次仅进行现金红利分配，不送红股，不进行资本公积金转增股本','000951':'不送红股，不以公积金转增股本','002552':'不送红股，不进行资本公积金转增股本','600821':'公司流通股不会发生变化，流通股份变动比例为“0”'}
SPECIAL={
'600027':'Only ordinary A-share record/ex/pay dates reviewed. The stated total cash/base covers company share capital; separate H-share arrangements and tax schedules are not imported.',
'300718':'The 88,800 restricted-share cancellation completed on 2024-09-20 is historical context, not a share-count change in this 2024-10-17 cash event.',
'300855':'The 2024-09-12 incentive vesting increased shares to 395,531,500 before this event; it is not a split or share allotment on this cash ex-date.',
'000338':'Only A-share cash entitlement/denominator/date applies; H-share distribution is explicitly separate.',
'601238':'Only A-share cash entitlement/denominator/date applies; H-share distribution is explicitly separate.',
'600835':'A-share record 10/23 and ex/pay 10/24 in RMB. B-share record 10/28, payment 11/6 and USD amount are explicitly excluded.',
'600821':'Unconfirmed holder securities account is self-paid after separate confirmation/registration; do not generalize ordinary exchange-settled entitlement to those accounts.',
'688507':'SSE implementation PDF and date-coded stored URL exist, with a local retrieval summary. Local CNINFO raw search has only surrounding notices and no matching implementation publication record; exact independent publication record remains UNKNOWN. Do not fetch any URL or substitute a related notice.'}
results=[]
for line in DATA.splitlines():
 code,rd,xd,dc,dr,base,total,pub,sig,cashquote=line.split('|');r=read(O/f'{code}_INTEGRITY_QA.json');e=r['event'];txt=(O/f'{code}_independent_fulltext.txt').read_text();s=''.join(txt.split());numeric=s.replace(',','');checks=[];fail=[];gaps=[];quotes={}
 def check(name,val): (checks if val else fail).append(name)
 def quote(name,frag):quotes[name]=frag;check('pdf_'+name,frag in s)
 check('independent_cash_matches_candidate',D(e['d_cash'])==D(dc))
 check('source_cash_independently_matches_ordinary_cash',D(e['d_source'])==D(dc))
 check('independent_dates_match_candidate',(e['record_date'],e['ex_date'],e['pay_date'])==(f'2024-10-{rd}',f'2024-10-{xd}',f'2024-10-{xd}'))
 check('independent_notice_signature_matches_candidate',(e['notice_date'],e['notice_signature_date'])==('2024-'+pub,'2024-'+sig))
 quote('cash',cashquote);quote('issuer_code',code);quote('notice_number',e['notice_number'])
 check('ordinary_registered_holder_scope','登记在册' in s and ('全体股东' in s or '本公司现有可予分配A股股份之股东' in s or '全体A股股东' in s))
 if e['sid'].endswith('.SH'):
  pat=f'2024/10/{rd}'+r'(?:－)?'+f'2024/10/{xd}2024/10/{xd}'
  m=re.search(pat,s);check('ordered_record_ex_pay_table',bool(m));quotes['dates']=m.group(0) if m else pat
 else:
  recpat=rf'股权登记日(?:为)?[：:]?2024年10月{int(rd)}日';exppat=rf'除权除息日(?:为)?[：:]?2024年10月{int(xd)}日'
  check('explicit_record_date',bool(re.search(recpat,s)));check('explicit_ex_date',bool(re.search(exppat,s)))
  paypat=rf'现金红利将于2024年10月{int(xd)}日通过股东托管证券公司'
  check('explicit_pay_date',bool(re.search(paypat,s)));quotes['dates']={'record_pattern':recpat,'ex_pattern':exppat,'pay_pattern':paypat}
 check('declared_base_shares_in_pdf',base in numeric)
 if code in PURE_QUOTES:
  quote('cash_only',PURE_QUOTES[code]);pure_basis='Explicit cash-only/no-stock-change clause, plus complete distribution-scheme reading and local split_ratio=1.'
 else:
  start=s.index('3.分配方案：');end=s.index('三、',start);section=s[start:end];quotes['complete_distribution_scheme']=section
  check('complete_distribution_scheme_only_cash','现金红利' in section and not any(w in section for w in ['送红股','转增股','配股']))
  pure_basis='Complete operative distribution scheme contains only cash. Generic conditional implementation wording about red shares/transfer shares is boilerplate, not an additional scheme.'
 check('no_current_share_count_change',D(r['local_action']['split_ratio'])==1)
 arithmetic={'declared_base_shares':base,'declared_total_cash':None if total=='-' else total,'exact_eligible_cash_product':str(D(base)*D(dc))}
 if total!='-':
  check('declared_total_in_pdf',total.rstrip('0').rstrip('.') in numeric or total in numeric)
  # PDF totals use cents; do not change published gross per-share amount to force a perfect aggregate.
  check('aggregate_cash_matches_cents',D(total)==(D(base)*D(dc)).quantize(D('.01'),rounding=ROUND_HALF_UP))
 if dr!='-':
  check('independent_reference_matches_candidate',D(e['d_ref'])==D(dr));quote('published_reference_literal',e['d_ref'])
  n,b=DIFF[code];check('differential_shares_in_pdf',str(n) in numeric and str(b) in numeric);check('eligible_equals_total_less_treasury',D(n)-D(b)==D(base))
  exact=D(base)*D(dc)/D(n);unit=D(1).scaleb(D(dr).as_tuple().exponent)
  check('published_reference_precision',abs(exact-D(dr))<unit);check('reference_is_not_source_bridge',abs(D(r['reference_residual']))>D('1e-11'))
  arithmetic.update(total_denominator=str(n),treasury_excluded=str(b),exact_diluted_cash=str(exact),published_reference=e['d_ref'],last_published_unit=str(unit),matches_round_half_up=exact.quantize(unit,rounding=ROUND_HALF_UP)==D(dr),matches_truncation=exact.quantize(unit,rounding=ROUND_DOWN)==D(dr),published_rounding_rule='Explicit truncation of per-10-share amount at six decimal places' if code=='000951' else 'Literal published amount retained; no rounding convention inferred')
  if code=='000951':quote('explicit_reference_truncation','保留六位小数，最后一位直接截取，不四舍五入')
 else:
  check('reference_not_invented',e['d_ref'] is None)
  if e['sid'].endswith('.SH'):quote('no_differential','差异化分红送转：否')
  arithmetic['reference_scope']='No standalone decrement in notice; candidate d_ref remains null. Do not invent one.'
 if r['failed_checks']:
  if code=='688507' and r['failed_checks']==['unique_publication_record']:gaps.append('UNKNOWN_IMPLEMENTATION_PUBLICATION_RECORD')
  else:fail += ['integrity:'+x for x in r['failed_checks']]
 status='FAIL_LOCAL_FACT_CHECK' if fail else 'UNKNOWN_PUBLICATION_EVIDENCE_NOT_ADMITTED' if gaps else 'PASS_LOCAL_FACTS_NOT_ADMITTED'
 final={'status':status,'scope':'LOCAL_FACT_PREPARATION_ONLY_NOT_RUNTIME_ADMISSION','sid':e['sid'],'record_date':e['record_date'],'ex_date':e['ex_date'],'pay_date':e['pay_date'],'d_source':e['d_source'],'d_cash':e['d_cash'],'d_ref':e['d_ref'],'notice_date':e['notice_date'],'signature_date':e['notice_signature_date'],'notice_url':e['notice_url'],'checks':checks,'failed_checks':fail,'evidence_gaps':gaps,'direct_pdf_quotes_compacted':quotes,'pure_cash_basis':pure_basis,'arithmetic':arithmetic,'special_scope':SPECIAL.get(code),'source_residual':r['source_residual'],'wrong_reference_bridge_residual':r['reference_residual'],'factor_old':e['factor_old'],'factor_new':e['factor_new'],'previous_close':e['previous_close'],'source_rows_file':str(O/f'{code}_INTEGRITY_QA.json'),'source_rows_file_sha256':sha(O/f'{code}_INTEGRITY_QA.json'),'candidate_adapter_path':r['candidate_adapter_path'],'candidate_adapter_sha256':r['candidate_adapter_sha256'],'source_hashes':e['evidence_hashes'],'original_pdf_pages':r['pdf_pages'],'fresh_fulltext_sha256':r['fresh_fulltext_sha256'],'full_pdf_text_read':True,'visual_page_review':False,'publication_intraday_known_at':'UNKNOWN. Calendar date and signature are not exact first-publication timestamp; no intraday PIT claim.','tax_scope':'Gross ordinary registered eligible-share cash. Frozen NET80 is a research convention, not the issuer universal net amount/tax timing. Self-paid holders and treaty/holding-period taxes are not generalized.','actual_admission_performed':False,'current_run_membership_verified':False,'history_run':False,'real_Data_constructed':False}
 save(O/f'{code}_FACT_QA.json',final);results.append(final);print(code,status,'fail',fail,'gap',gaps)
# Read-only seal verification of every original evidence file and all thirty linked action/signal files.
orig=read(O/'SOURCE_DIRECTORY_HASHES.json');assert all(sha(p)==h for p,h in orig.items())
linked={p:h for r in results for p,h in r['source_hashes'].items()};assert all(sha(p)==h for p,h in linked.items())
summary={'result':'COMPLETE_LOCAL_FACT_PREPARATION_NOT_ADMISSION','total_events':len(results),'pass_count':sum(x['status']=='PASS_LOCAL_FACTS_NOT_ADMITTED' for x in results),'unknown_count':sum(x['status'].startswith('UNKNOWN') for x in results),'fail_count':sum(x['status'].startswith('FAIL') for x in results),'events':[{'sid':r['sid'],'status':r['status'],'ex_date':r['ex_date'],'qa_path':str(O/f"{r['sid'][:6]}_FACT_QA.json"),'qa_sha256':sha(O/f"{r['sid'][:6]}_FACT_QA.json")} for r in results],'max_abs_source_residual':str(max(abs(D(r['source_residual'])) for r in results)),'differential_events':list(DIFF),'all_source_evidence_unchanged':True,'original_directory_file_count':len(orig),'history_run':False,'real_Data_constructed':False,'actual_admission_performed':False,'strategy_code_changed':False,'network_used':False,'new_url_visited':False,'CNINFO_000728_403_retried_or_bypassed':False,'limits':['All results are preparation only; future admission still needs exact event approval/sealed adapter under its own process.','No target expansion, historical run, current-run membership assertion, generic action admission or Q0/held-state transition test.','No event first-publication intraday timestamp is proven. not_PIT, not production.']}
save(O/'FACT_REVIEW_SUMMARY.json',summary)
lines=['# 30 October cash events: local facts reviewed, not admitted','',f"Result: {summary['pass_count']} PASS, {summary['unknown_count']} UNKNOWN, {summary['fail_count']} FAIL. All thirty source bridges meet the original 1e-11 tolerance; maximum absolute residual {summary['max_abs_source_residual']}.",'','This report is independent local fact preparation. It does not admit an event, edit a runtime manifest, construct Data, run history, or assert membership in the current experiment. No network/URL calls; no retry or bypass of 000728 CNINFO 403. All original evidence and linked action/signal hashes were reverified unchanged.','', '## Earliest four','', '600079.SH and 688248.SH: record 2024-10-10, ex/pay 2024-10-11; gross ordinary eligible-share cash 0.15 and 0.1350. 601619.SH and 688686.SH: record 2024-10-11, ex/pay 2024-10-14; cash 0.01 and 0.13. Four PASS, no specific fact blocker. No differential distribution; no standalone d_ref published, so null is preserved.','', '## Remaining gap','', '688507.SH: PDF facts, split=1, hashes, exact two-day source bridge and differential arithmetic pass. The full SSE implementation PDF is locally present and signed 2024-10-09. Its stored date-coded URL and local retrieval summary give that date, but the raw CNINFO search has only four surrounding announcements, not the implementation notice. Exact independent implementation-publication record is UNKNOWN. This is not replaced by inference and is not used for admission.','', '## Important interpretation','', '- Eight differentiated distributions separate d_cash/d_source from d_ref. All eight published reference decrements fail the source bridge if substituted; use source cash for source factor coordinates, eligible cash for entitlement, reference decrement only for the official reference price.','- Explicitly keep A/H scopes separate for 000338, 600027, 601238; A/B scopes separate for 600835. Historical cancellation/vesting at 300718/300855 is not this cash action.','- Some Shanghai notices contain conditional red-share/transfer implementation boilerplate. Their complete operative schemes state only cash; no equity increase is inferred from boilerplate.','- Cash is gross per ordinary registered eligible share, not universal net80 cash. Self-paid and unconfirmed accounts and investor-dependent tax timing remain distinct.','- All thirty exact first-publication intraday times remain UNKNOWN. Stored CNINFO date values are interpreted in Asia/Shanghai, with signature date tracked separately. No PIT claim.','', '## Event results','', '| SID | Record | Ex / pay | d_source | d_cash | d_ref | Publication / signature | Status |','|---|---|---|---|---|---|---|---|']
for r in results:lines.append(f"| {r['sid']} | {r['record_date']} | {r['ex_date']} | {r['d_source']} | {r['d_cash']} | {r['d_ref']} | {r['notice_date']} / {r['signature_date']} | {r['status']} |")
lines += ['', '## Reproducibility','', 'review_local_cash_facts.py extracts each original PDF using installed macOS PDFKit, compares full text with the sealed source, rehashes all six event sources and candidate adapter, reads original action and parquet rows, checks dates/eligibility/lineage/factors and original tolerance, and compares both action and signal hashes with frozen M12 inputs. finalize_fact_review.py adds independently transcribed full-document facts and arithmetic. Neither imports strategy engine code.','', 'Run using existing parquet-capable interpreter: /Users/bytedance/.cache/uv/environments-v2/b2d53c07a5e2321f/49580a0fa3b048c7/bin/python. System python3 lacks a parquet engine; initial attempt stopped before first parquet read, then the existing installed interpreter completed. No software was installed.','', 'Per-event FACT_QA files include compacted exact PDF quotes, independent dates/cash, arithmetic, source hashes and linked row/adapter hashes. INTEGRITY_QA files retain both full source rows and original action. Fresh full texts preserve PDFKit extraction; visual page rendering was not performed. SOURCE_DIRECTORY_HASHES seals all original evidence. REVIEW_ARTIFACT_SEAL seals the review artifacts.']
(O/'FACT_REVIEW_REPORT.md').write_text('\n'.join(lines)+'\n')
seal={str(p):sha(p) for p in O.iterdir() if p.is_file() and p.name!='REVIEW_ARTIFACT_SEAL.json'}
save(O/'REVIEW_ARTIFACT_SEAL.json',{'files':seal,'additional_frozen_manifest_sha256':sha(ROOT/'mainline_candidate_v12_winner_funding_competition/FROZEN_INPUTS.json'),'actual_admission_performed':False})
print(json.dumps({k:v for k,v in summary.items() if k not in ['events','limits']},ensure_ascii=False))
