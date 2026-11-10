"""Prepare, but do not execute, one-window saved ON contract auditor."""
from pathlib import Path
import ast,difflib,hashlib,json
R=Path(__file__).resolve().parent;oldpath=R/'audit_native_technical_prefixes.py';old=oldpath.read_text()
helpers=old[:old.index("freeze=read(O/'SOURCE_FREEZE.json')")]
helpers=helpers.replace('import json,gzip,hashlib,sys,time','import json,gzip,hashlib,sys,time,argparse,traceback')
setup=old[old.index("freeze=read(O/'SOURCE_FREEZE.json')"):old.index('def fact(sid,day):')]
functions=old[old.index('def fact(sid,day):'):old.index('report={};total_success=0;')]
body=old[old.index('report={};total_success=0;'):]
body=body.replace("for w,cut in F.TECH_CUTS.items():","for w,cut in [(window,F.D.WINDOWS[window][1])]:",1)
a=body.index(" off=K/(w+'_OFF');");b=body.index(' for root in[off,full]:',a)
body=body[:a]+''' off=OLD/'runs'/(w+'_OFF');full=O/'runs'/(w+'_ON')
 offid={'reused_prior_full_OFF_native_identity':True};fullid={'common_window_and_input_identity':True};physicalid={'same_frozen_source_passed_technical_physical_prefix':True}
 assert read(full/'DONE.json')['completed']
'''+body[b:]
body=body.replace('for root in[off,full]:','for root in[full]:',1)
body=body.replace(" b=book(full/'pair/B.json.gz');dailys=rows(full/'pair/daily.jsonl.gz');",' b=b0;dailys=daily0;',1)
needle=" b=b0;dailys=daily0;dec="
body=body.replace(needle," b=b0;dailys=daily0;assert len(dailys)==({'long':726,'strong':242}[w]) and dailys[-1]['at'][:10]==cut;assert [x['at'][:10]for x in dailys]==[x['at'][:10]for x in rows(off/'pair/daily.jsonl.gz')];dec=",1)
# Replace quadratic prefix lookups by literal funding-row accumulation, no route/state recreation.
needle=' success=filled=partial=none=0;failures=Counter()\n'
replacement=''' wanted_logs={(x['at'],x['sid'],'core')for x in logs};original_front={};active_at=None;front=[]
 for x in fund:
  if '09:30:00'not in x['at']:continue
  if x['at']!=active_at:active_at=x['at'];front=[]
  key=(x['at'],x['sid'],x['role'])
  if key in wanted_logs:original_front[key]=tuple(front)
  if x.get('result')=='reserved':front.append(reserve_by[key])
 core_first={(x['security_id'],tuple(x['epoch'])):x['at']for x in corebuys}
 success=filled=partial=none=0;failures=Counter()
'''
assert body.count(needle)==1;body=body.replace(needle,replacement,1)
oldfront="ix=next(k for k,x in enumerate(fund)if x['at']==at and x['sid']==sid and x['role']=='core');front=[x for x in fund[:ix]if x['at']==at and x.get('result')=='reserved'];rr=[reserve_by[at,x['sid'],x['role']]for x in front]"
assert body.count(oldfront)==1;body=body.replace(oldfront,"rr=original_front[at,sid,'core']",1)
oldprior="for (d,sid),i in intents.items():assert not any(t['security_id']==sid and t['epoch']==i['epoch']and t['at']<d+' 23:59:59'for t in corebuys)"
assert body.count(oldprior)==1;body=body.replace(oldprior,"core_first={(t['security_id'],tuple(t['epoch'])):t['at']for t in corebuys}\n for (d,sid),i in intents.items():assert core_first.get((sid,tuple(i['epoch'])),'9999')>d+' 23:59:59'",1)
# Native allocation uses finite Decimal precision; preserve exact shares and sub-cent monetary tolerance.
oldsum="sum(x['shares']for x in t['parts'])==t['shares']and sum((D(x['net_cash'])for x in t['parts']),Z)==D(t['gross_cny'])-D(t['fees_cny'])"
assert body.count(oldsum)==1;body=body.replace(oldsum,"sum(x['shares']for x in t['parts'])==t['shares']and abs(sum((D(x['net_cash'])for x in t['parts']),Z)-(D(t['gross_cny'])-D(t['fees_cny'])))<D('.00000001')",1)
body=body.replace('assert total_success==108 and total_proofs==3684','assert total_success==sum(x[\'new_typed_reservations\']for x in report.values())',1)
a=body.index("out={'passed':True,")
body=body[:a]+'''out={'passed':True,'scope':'Complete saved one-window ON proof/reservation/real-fill, clocks/epoch/token, cashflow NAV and native mirror audit. No new financial or mark path.','window':window,'source_freeze_sha256':sha(O/'SOURCE_FREEZE.json'),'technical_gate_sha256':sha(K/'GATE.json'),'full_admission_sha256':sha(R/'FULL_ADMISSION.json'),'full_CLOSEs':{'long':726,'strong':242}[window],'proof_rows':total_proofs,'typed_reservations':total_success,'typed_with_real_fill':total_filled,'typed_no_fill':total_none,'typed_partial':total_partial,'saved_balance_rows_checked':total_balance,'windows':report,'not_economic_result':'Contract/clock and financial equations, not arm selection. Economic summary and ON-OFF contribution conservation require completed saved analysis.','review_limits':['Native inventory marks/certificates cashflow reconciled; completed financial reader independently values source prices later.','Epoch/T+1/FIFO/CA behavior and unchanged native sources, no checkpoint unpickling or new financial initialization.','Unobserved boundary cases remain source/pure-fixture scope, no invented actual partial/nonfill.','Current leaf closure frozen; absent historical OFF leaf hashes not claimed.'],'reviewer_new_native_accounts_or_marks':0,'sources_sha256':sources,'seconds':time.monotonic()-begun}
(R/(window.upper()+'_FULL_NATIVE_REVIEW.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\\n');print(json.dumps({k:v for k,v in out.items()if k not in['sources_sha256','windows']},ensure_ascii=False))
'''
prechecks='''
window=window.lower();assert window in ('long','strong')
full=O/'runs'/(window+'_ON')
# Hard completion guard is before any saved financial book/outcome read.
assert read(full/'DONE.json')['completed'], 'Target ON incomplete; do not read partial economics'
complete=read(O/'runs'/(window+'_COMPLETE.json'));assert complete['passed'] and complete['new_ON_accounts']==1 and complete['new_OFF_accounts']==0
admission=read(R/'FULL_ADMISSION.json');assert admission['approved'] and admission['scope']=='CORE_CONFIRMED_TWO_FULL_ON'
assert complete['source_freeze_sha256']==sha(O/'SOURCE_FREEZE.json')==admission['source_freeze_sha256']
timing=read(O/'runs'/(window+'_TIMING.json'));assert timing['used_seconds']<={'long':1600,'strong':800}[window]
fresh=read(O/'runs'/(window+'_FRESH.json'));assert fresh=={'cash':1000000,'positions':0,'orders':0,'imported_accounts':0}
oldidentity=read(OLD/'runs'/(window+'_INPUT_IDENTITY.json'));newidentity=read(O/'runs'/(window+'_INPUT_IDENTITY.json'))
assert {k:v for k,v in oldidentity.items()if k!='seconds'}=={k:v for k,v in newidentity.items()if k!='seconds'}, 'Actual immutable input identity differs'
'''
main='''def main(window):
 global begun,sources,rules,sm,canonical,facts,receiptcache
 begun=time.monotonic();sources={}
'''+''.join(' '+line+'\n'for line in prechecks.strip().splitlines())+''.join(' '+line+'\n'for line in setup.strip().splitlines())+''.join(' '+line+'\n'for line in body.strip().splitlines())
footer='''
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--execute',action='store_true');parser.add_argument('--window',choices=['long','strong']);args=parser.parse_args();assert args.prepare!=args.execute
 if args.prepare:
  paths=[Path(__file__),R/'audit_native_technical_prefixes.py',R/'FULL_ADMISSION.json',O/'SOURCE_FREEZE.json',P/'PROTOCOL.txt']
  value={'passed':True,'prepared_only':True,'source_sha256':{str(p.resolve()):sha(p)for p in paths},'windows':{'long':726,'strong':242},'hard_completion_guard_before_any_book_read':True,'full_ON_results_read':False,'new_Account_or_Market_or_route_runs':0,'new_marks':0,'differences_from_audited_prefix_reader':['One completed window, full input identity/count/date and scoped run budget checks.','Reuses prior full OFF identity and passed physical-prefix evidence; no duplicate full OFF path or financial re-audit.','Literal per-OPEN prefix lookup and epoch map replace quadratic scans.','Sub-cent finite Decimal allocation tolerance; exact shares.','No fixed108/3684 assertions; count actual full observations including nonfill and partial.']}
  (R/'FULL_READER_PREPARATION.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\\n');print('PREPARED_ONLY_NO_FULL_RESULTS_READ')
 else:
  assert args.window
  try:main(args.window)
  except BaseException as error:
   (R/(args.window.upper()+'_FULL_REVIEW_FAILURE.json')).write_text(json.dumps({'passed':False,'window':args.window,'error':str(error),'traceback':traceback.format_exc(),'new_native_accounts_or_marks':0},ensure_ascii=False,indent=2)+'\\n');raise
'''
new=helpers+functions+'\n'+main+footer
ast.parse(new)
f=R/'audit_full_completed_window.py';f.write_text(new)
(R/'FULL_READER_FROM_PREFIX.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=oldpath.name,tofile=f.name)))
(R/'FULL_READER_DERIVATION.json').write_text(json.dumps({'prepared_only':True,'prefix_source_sha256':hashlib.sha256(old.encode()).hexdigest(),'full_reader_sha256':hashlib.sha256(new.encode()).hexdigest(),'compile_only':True,'full_outputs_read':False,'native_accounts_or_paths':0},indent=2)+'\n')
print('WROTE',f)
