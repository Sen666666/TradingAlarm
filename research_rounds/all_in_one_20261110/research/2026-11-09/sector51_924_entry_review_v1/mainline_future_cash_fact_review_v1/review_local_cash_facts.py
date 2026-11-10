"""Offline independent fact preparation only. Never constructs Data, runs history or admits events."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import hashlib,json,subprocess,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;P=ROOT/'october_remaining_cash_evidence_v1'
CODES='600079 688248 601619 688686 300573 600027 688188 688507 300394 300718 300855 301603 000338 000937 002353 601238 000905 688375 600236 601096 688097 688692 600248 600835 688535 000951 002552 600795 600821 601801'.split()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
save=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
before={str(p):sha(p) for p in P.iterdir() if p.is_file()}
frozen=read(ROOT/'mainline_candidate_v12_winner_funding_competition/FROZEN_INPUTS.json')['hashes']
results=[]
for code in CODES:
 f=read(P/f'{code}_FACT_REVIEW.json');e=f['event'];c=read(P/f'{code}_NOTICE_REVIEW_INPUT.json');checks=[];errors=[]
 def check(name,value):
  (checks if bool(value) else errors).append(name)
 check('exact_exchange_sid',e['sid']==code+('.SH' if code.startswith('6') else '.SZ'))
 check('single_adapter_exact',read(f['adapter_path'])==[e])
 check('adapter_sha256',sha(f['adapter_path'])==f['adapter_sha256'])
 for path,h in e['evidence_hashes'].items():check('source_hash_'+Path(path).name,sha(path)==h)
 check('exact_six_evidence_sources',len(e['evidence_hashes'])==6)
 pdf=Path(e['notice']['pdf_path']);check('genuine_pdf_header',pdf.read_bytes().startswith(b'%PDF'))
 js='ObjC.import("PDFKit"); var p=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(pdf))+')); JSON.stringify({pages:Number(p.pageCount),text:ObjC.unwrap(p.string)});'
 raw=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',js],text=True,capture_output=True,check=True)
 x=json.loads(raw.stdout);text=x['text'];compact=''.join(text.split());(O/f'{code}_independent_fulltext.txt').write_text(text)
 check('fresh_original_pdf_text_equals_existing_text',text==(P/f'{code}_official.pdf.txt').read_text())
 for i,s in enumerate(c['assert_fragments']):check(f'prior_assert_fragment_{i}_only_corrob_not_independent', ''.join(s.split()) in compact)
 pub=[a for a in read(P/f'{code}_CNINFO_SEARCH.json')['announcements'] if 'https://static.cninfo.com.cn/'+a['adjunctUrl']==e['notice_url']]
 check('unique_publication_record',len(pub)==1)
 if len(pub)==1:
  pub=pub[0];pubdate=datetime.fromtimestamp(pub['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
  check('publication_code_date_url',pub['secCode']==code and pubdate==e['notice_date'] and pub['adjunctUrl'].split('/')[1]==e['notice_date'])
 else:pubdate=None
 signature=e['notice_signature_date'];y,m,d=map(int,signature.split('-'))
 cn_signature={'000937':'二〇二四年十月十二日','000951':'二○二四年十月二十二日'}.get(code)
 check('pdf_signature_date',f'{y}年{m}月{d}日' in compact[-100:] or bool(cn_signature and cn_signature in compact[-100:]))
 check('publication_before_record_before_ex_and_pay',e['notice_date']<e['record_date']<e['ex_date']==e['pay_date'])
 a=read(e['local_action_path']);terms=[(i+1,t) for i,t in enumerate(a['events']) if t['effective_date']==e['ex_date']]
 check('local_sid_exact',a['series_id']==e['sid']);check('single_exact_local_event',len(terms)==1 and terms[0][0]==e['local_action_ordinal'])
 term=terms[0][1];check('local_action_pure_cash',D(term['split_ratio'])==1 and D(term['cash_per_old_share'])==D(e['d_source']) and D(e['d_source'])>0)
 z=pd.read_parquet(e['signal_path']);dt=pd.Timestamp(e['ex_date']);old=z[z.index<dt].iloc[-1];new=z.loc[dt]
 check('previous_day_is_record',str(old.name.date())==e['record_date']);check('single_ex_row',getattr(new,'ndim',0)==1)
 lineage=lambda r:tuple(str(r[k]) for k in ['source_kind','source_path','segment_id'])
 check('same_lineage',lineage(old)==lineage(new))
 for lab,row in [('old',old),('new',new)]:check('source_valid_'+lab,bool(row.price_eligible) and bool(row.volume_eligible) and bool(row.observed_bar) and not bool(row.source_invalid) and not bool(row.synthetic_event_bar))
 fo,fn,pc=map(lambda v:D(str(v)),[old.adjustment_factor,new.adjustment_factor,old.raw_close]);ds=D(e['d_source']);res=fo*pc/(pc-ds)/fn-1
 check('old_new_close_exact',list(map(str,[fo,fn,pc]))==[e['factor_old'],e['factor_new'],e['previous_close']])
 check('source_bridge_original_1e_11',abs(res)<D('1e-11') and res==D(e['source_coordinate_residual']))
 check('same_inputs_as_frozen_experiment',all(frozen.get(p)==e['evidence_hashes'][p] for p in [e['signal_path'],e['local_action_path']]))
 check('separate_net80_research_convention',D(e['net80_per_registered_share'])==D(e['d_cash'])*D('.8'))
 ref_res=str(fo*pc/(pc-D(e['d_ref']))/fn-1) if e['d_ref'] else None
 if e['d_ref']:check('reference_residual_exact',D(ref_res)==D(e['official_reference_coordinate_residual']))
 rowdict=lambda row:{k:(v.item() if hasattr(v,'item') else str(v) if not isinstance(v,(str,int,float,bool,type(None))) else v) for k,v in row.items()}
 result={'code':code,'sid':e['sid'],'status':'INTEGRITY_PASS_PENDING_INDEPENDENT_FACT_REVIEW' if not errors else 'FAIL','checks':checks,'failed_checks':errors,'event':e,'candidate_adapter_sha256':f['adapter_sha256'],'candidate_adapter_path':f['adapter_path'],'fact_file_sha256':sha(P/f'{code}_FACT_REVIEW.json'),'pdf_pages':x['pages'],'fresh_fulltext_sha256':hashlib.sha256(text.encode()).hexdigest(),'publication_record':pub,'publication_date_Asia_Shanghai':pubdate,'source_residual':str(res),'reference_residual':ref_res,'source_rows':{'old_day':str(old.name.date()),'old':rowdict(old),'new_day':str(new.name.date()),'new':rowdict(new)},'local_action':term,'actual_admission_performed':False,'history_run':False,'real_Data_constructed':False}
 results.append(result);save(O/f'{code}_INTEGRITY_QA.json',result)
 print(code,result['status'],e['record_date'],e['ex_date'],e['d_cash'],e['d_ref'],'res',res,'pages',x['pages'],'errors',errors,flush=True)
checkall={str(p):sha(p) for p in P.iterdir() if p.is_file()}
assert before==checkall,'ORIGINAL_EVIDENCE_CHANGED_DURING_REVIEW'
save(O/'SOURCE_DIRECTORY_HASHES.json',before)
save(O/'INTEGRITY_SUMMARY.json',{'events':len(results),'failures':[(r['sid'],r['failed_checks']) for r in results if r['failed_checks']],'max_abs_source_residual':str(max(abs(D(r['source_residual'])) for r in results)),'original_evidence_unchanged':True,'actual_admission_performed':False,'history_run':False,'real_Data_constructed':False,'source_directory_hashes_path':str(O/'SOURCE_DIRECTORY_HASHES.json')})
