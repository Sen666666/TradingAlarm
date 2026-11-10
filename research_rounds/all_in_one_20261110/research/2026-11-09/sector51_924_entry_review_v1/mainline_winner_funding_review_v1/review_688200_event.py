"""Independent 688200 one-event evidence review. No strategy Data or history."""
from pathlib import Path
from decimal import Decimal as D
import json, hashlib, subprocess, copy, importlib.util, sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
O=Path(__file__).resolve().parent
P=ROOT/'october_remaining_cash_evidence_v1'
RUN=ROOT/'mainline_candidate_v12_winner_funding_competition'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
checks=[]
def ok(name,value):
    assert value,name
    checks.append(name)
fact=read(P/'688200_FACT_REVIEW.json');ev=fact['event']
ok('single_exact_adapter',read(fact['adapter_path'])==[ev])
ok('adapter_seal',sha(fact['adapter_path'])==fact['adapter_sha256']=='af9b6319597e47ea858c0125bf0e43d31c270da056e06db8d470d76bdc025686')
hashes={}
for p,h in ev['evidence_hashes'].items():
    ok('source_hash_'+Path(p).name,sha(p)==h);hashes[p]=h
ok('exact_six_sources',len(hashes)==6)
pdf=Path(ev['notice']['pdf_path'])
ok('genuine_pdf_header',pdf.read_bytes().startswith(b'%PDF'))
js='ObjC.import("PDFKit"); var p = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(pdf))+')); JSON.stringify({pages:Number(p.pageCount),text:ObjC.unwrap(p.string)});'
raw=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',js],check=True,text=True,capture_output=True)
extracted=json.loads(raw.stdout)
text=extracted['text']
ok('five_original_pdf_pages',extracted['pages']==5)
ok('original_pdf_text_exact_sealed_text',text==(P/'688200_official.pdf.txt').read_text())
compact=''.join(text.split())
for label,s in [
 ('issuer','证券代码：688200证券简称：华峰测控公告编号：2024-044'),
 ('pure_cash','本次不进行资本公积转增股本，不送红股'),
 ('cash','每股现金红利0.23元'),
 ('dates','股权登记日除权（息）日现金红利发放日2024/10/102024/10/112024/10/11'),
 ('ordinary_holder_scope','公司回购专用证券账户中的股份不参与利润分配'),
 ('no_self_distribution','自行发放对象无。'),
 ('differential_reference','即公司除权（息）参考价格=前收盘价格-0.2297元/股。'),
 ('signature','2024年9月27日'),
 ('tax_not_universal_net80','本次分红派息公司暂不扣缴个人所得税')]:
    ok('pdf_'+label,''.join(s.split()) in compact)
notice=[x for x in read(P/'688200_CNINFO_SEARCH.json')['announcements'] if x['announcementId']=='1221306527']
ok('unique_publication_record',len(notice)==1)
ok('notice_publication_20240927',notice[0]['secCode']=='688200' and notice[0]['adjunctUrl']=='finalpage/2024-09-27/1221306527.PDF' and notice[0]['announcementTime']==1727366400000)
ok('prior_publication_calendar_not_intraday_PIT',ev['notice_date']==ev['notice_signature_date']=='2024-09-27' and ev['notice_date']<ev['record_date']<ev['ex_date']==ev['pay_date']=='2024-10-11')
terms=read(ev['local_action_path'])
matches=[(i+1,a) for i,a in enumerate(terms['events']) if a['effective_date']=='2024-10-11']
ok('unique_exact_event',terms['series_id']=='688200.SH' and len(matches)==1 and matches[0][0]==7)
a=matches[0][1]
ok('pure_cash_local_source',D(a['split_ratio'])==1 and D(a['cash_per_old_share'])==D('.23'))
z=pd.read_parquet(ev['signal_path']);dt=pd.Timestamp(ev['ex_date'])
before=z[z.index<dt].iloc[-1];after=z.loc[dt]
lineage=lambda r:tuple(str(r[k]) for k in ('source_kind','source_path','segment_id'))
ok('source_dates',str(before.name.date())=='2024-10-10' and str(after.name.date())=='2024-10-11')
ok('same_lineage',lineage(before)==lineage(after))
for label,r in [('before',before),('after',after)]:
    ok('source_valid_'+label,bool(r.price_eligible) and bool(r.volume_eligible) and bool(r.observed_bar) and not bool(r.source_invalid) and not bool(r.synthetic_event_bar))
fo,fn,pc=map(lambda x:D(str(x)),[before.adjustment_factor,after.adjustment_factor,before.raw_close])
ok('source_values_exact',(fo,fn,pc)==(D('2.234495011354039'),D('2.2388548166866773'),D('118.11')))
res=fo*pc/(pc-D(ev['d_source']))/fn-1
wrong=fo*pc/(pc-D(ev['d_ref']))/fn-1
ok('source_bridge',abs(res)<D('1e-11') and res==D(ev['source_coordinate_residual']))
ok('separate_reference_from_source',abs(wrong)>D('1e-11') and ev['d_ref']=='0.2297' and ev['d_cash']==ev['d_source']=='0.23')
diluted=D(135263327)*D('.23')/D(135439427)
ok('differential_arithmetic',D(135439427)-D(176100)==D(135263327) and D(135263327)*D('.23')==D('31110565.21') and diluted.quantize(D('.0001'))==D('.2297'))
frozen=read(RUN/'FROZEN_INPUTS.json')['hashes']
ok('same_source_as_frozen_experiment',all(frozen[p]==hashes[p] for p in [ev['signal_path'],ev['local_action_path']]))
manifest=read(ROOT/'mainline_m7_downturn_cash_batch_v6/REVIEWED_BATCH_MANIFEST.json')
ok('not_previously_admitted',len(manifest['events'])==26 and not any(x['sid']=='688200.SH' for x in manifest['events']))
out=RUN/'once_20250120'; output_hash=read(out/'OUTPUT_HASHES.json')
for n in ['TICKET_STATE.json','PENDING_AT_END.json','HOLDINGS.json','ALL_TARGETS_BLOCKER_SCAN.json','RETRY_TICKETS.json','ORDERS.json']:
    ok('saved_output_hash_'+n,sha(out/n)==output_hash[n]);hashes[str(out/n)]=output_hash[n]
ticket=read(out/'TICKET_STATE.json')['688200.SH']
pending=[x for x in read(out/'PENDING_AT_END.json') if x['sid']=='688200.SH']
scan=[x for x in read(out/'ALL_TARGETS_BLOCKER_SCAN.json') if x['sid']=='688200.SH']
ok('real_retained_and_original_pending',ticket['status']=='RETAINED' and ticket['ever_seeded'] is False and len(pending)==1 and pending[0]['ticket_id']==ticket['ticket_id'])
ok('zero_actual_record_holding',not any(x['sid']=='688200.SH' for x in read(out/'HOLDINGS.json')) and not any(x['sid']=='688200.SH' for x in read(out/'ORDERS.json')))
ok('real_guard_correct',scan[0]['held_qty']==0 and scan[0]['pending'] and scan[0]['retained_status']=='RETAINED' and scan[0]['issues']==['UNADMITTED_EQUITY_EVENT','UNADMITTED_FACTOR_CHANGE'])
# Pure original policy helper only. No strategy engine or Data imports.
rp=ROOT/'allocation_ablation_v1/allocation_rules.py'
spec=importlib.util.spec_from_file_location('single_event_rules_review',rp);rules=importlib.util.module_from_spec(spec);sys.modules[spec.name]=rules;spec.loader.exec_module(rules)
t=copy.deepcopy(ticket);t['origin']=tuple(t['origin']);t['current_factor']=D(t['current_factor']);old=copy.deepcopy(t)
try:rules.retained_ticket_preflight(t,date='2024-10-11',origin=t['origin'],factor=fn,action_present=True)
except rules.MissingBridge: ok('missing_event_block_is_native',True)
else:raise AssertionError('missing_event_must_block')
t=copy.deepcopy(old)
result=rules.retained_ticket_preflight(t,date='2024-10-11',origin=t['origin'],factor=fn,action_present=True,admitted_event=dict(reviewed=True,factor_old=fo,factor_new=fn))
ok('native_zero_quantity_bridge',result==dict(status='RETAINED',record_qty=0,dividend_accrual=D(0)))
ok('native_bridge_preserves_identity_budget_floor_phase',all(t[k]==old[k] for k in old if k not in ['current_factor','last_verified_day']))
ok('native_bridge_exact_factor_day',t['current_factor']==fn and t['last_verified_day']=='2024-10-11')
base=read(ROOT/'mainline_m7_cash_batch_design_v6/once_20260630/TICKET_STATE.json')['688200.SH']
ok('baseline_cancelled_not_guard_target',base['ticket_id']==ticket['ticket_id'] and base['status']=='CANCELLED' and base['reason']=='RETRY_NON_CAPITAL_OPEN_REJECTION' and base['last_verified_day']=='2024-10-08')
minimum_cost=D('25939.808894736')
ok('saved_budgets_straddle_builder_cost',D(base['budget'])<minimum_cost<D(ticket['budget']))
code_manifest=read(RUN/'SOURCE_HASHES.json')
for p,h in code_manifest['files'].items():ok('frozen_source_'+Path(p).parent.name+'_'+Path(p).name,sha(p)==h)
result=dict(result='PASS_EXACT_688200_20241011_LOCAL_RESEARCH_EVENT_ADMISSION',checks=checks,assertions=len(checks),
 exact_scope=dict(sid='688200.SH',ex_date='2024-10-11',economic_event_id_candidate='688200.SH|LOCAL_DISTRIBUTION_007',event_type='PURE_CASH',
 record_date='2024-10-10',pay_date='2024-10-11',d_source='0.23',d_cash='0.23',d_ref='0.2297',factor_old=str(fo),factor_new=str(fn)),
 adapter_path=fact['adapter_path'],adapter_sha256=fact['adapter_sha256'],evidence_hashes=ev['evidence_hashes'],additional_hashes=hashes,
 source_residual=str(res),wrong_reference_bridge_residual=str(wrong),diluted_reference_exact=str(diluted),
 pdf=dict(parser='installed macOS PDFKit via osascript JXA',pages=extracted['pages'],text_sha256=hashlib.sha256(text.encode()).hexdigest(),exact_sealed_text_match=True,visual_page_review=False),
 known_at='Notice date and stored publication record 2024-09-27; before record/ex-date, no intraday or general PIT claim; not known for 2024-09-26 signal.',
 state=dict(held_qty=0,pending=True,retained=True,zero_entitlement=True,original_guard_correct=True,branch_union_added_target=False,
 baseline_cancelled_day='2024-10-08',candidate_original_budget=ticket['budget'],baseline_original_budget=base['budget'],
 budget_cost_source='Builder supplied original 200-share all-in cost; this review compares saved budgets, not recomputes dated fees.'),
 restrictions=['Only this exact event tuple and six sealed sources; no generic admission or new action classes.',
 'Use d_source for source-coordinate factor bridge, d_cash for registered-share entitlement, d_ref only for official reference. Never substitute.',
 'Q0 retained ticket gets only native factor/day bridge; no shares, cash, dividend, attempt reset, new NAV, CP, priority or automatic fill.',
 'Original preflight/atomic and all existing limits remain. Resume/re-run requires separate newly sealed adapter/experiment approval; this review does not run or admit anything.',
 'Frozen NET80 remains research convention, not the issuer universal tax schedule; zero record holdings yield zero.',
 'No future price/factor enters CLOSE selection. Runtime source bridge verifies only effective day, notice dates previously published.',
 'not_PIT, not production, no external access, no actual trades.'],
 history_run=False,real_Data_constructed=False,strategy_code_changed=False,frozen_inputs_changed=False,actual_admission_performed=False,
 remaining_fact_blockers=[])
target=O/'V12_688200_EVENT_ADMISSION_QA.json'
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['result','assertions','source_residual','history_run','real_Data_constructed','remaining_fact_blockers']},ensure_ascii=False))
