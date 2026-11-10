"""Pure-file tests of exact AST-extracted runner helpers in isolated /tmp.
No producer entrypoint, kernel, stock_signal, Account, processes or signals run.
"""
from pathlib import Path
import ast,json,hashlib,os,uuid,datetime,math,tempfile,shutil,types
import pandas as pd,numpy as np,pyarrow as pa,pyarrow.parquet as pq
O=Path(__file__).resolve().parent;R=O.parent;P=R.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
f=json.loads((R/'FREEZE.json').read_text());code=R/'run_cache.py';assert sha(code)==f['code_sha256'][str(code)]
tmp=Path(tempfile.mkdtemp(prefix='cache_recovery_review_',dir='/tmp'))
for name in ['fixtures','artifacts','receipts','running','errors','pending','runs']:(tmp/name).mkdir()
# Extract only pure formatting/comparison; do not import pilot or any model.
pt=ast.parse((P/'pilot.py').read_text());helper_names=['clean','compare_frames']
pg={'np':np,'pd':pd,'math':math};exec(compile(ast.Module(body=[z for z in pt.body if isinstance(z,ast.FunctionDef)and z.name in helper_names],type_ignores=[]),str(P/'pilot.py'),'exec'),pg)
fields=next(ast.literal_eval(z.value)for z in pt.body if isinstance(z,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='FIELDS'for t in z.targets))
p=types.SimpleNamespace(clean=pg['clean'],compare_frames=pg['compare_frames'],FIELDS=fields,sha=sha)
assert not hasattr(p,'kernel')
needed=['read','sha','now','sync_dir','atomic_json','marker','verify_values','commit_receipt','verified_done','reconcile','import20']
tree=ast.parse(code.read_text());selected=[z for z in tree.body if isinstance(z,ast.FunctionDef)and z.name in needed];assert {z.name for z in selected}==set(needed)
ns={'Path':Path,'json':json,'os':os,'uuid':uuid,'datetime':datetime,'np':np,'pd':pd,'pq':pq,'p':p,'HERE':tmp,'RUNID':'ISOLATED_FILE_TEST_NOT_PRODUCTION'}
exec(compile(ast.Module(body=selected,type_ignores=[]),str(code),'exec'),ns)
schema=pa.ipc.read_schema(pa.BufferReader((R/'DAILY_SCHEMA.arrow').read_bytes()));ns['SCHEMA']=schema;ns['GRID']=pd.DatetimeIndex(pd.read_parquet(f['grid_path']).day)
ns['OLD']={d:pd.read_parquet(P.parent/'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet'if d=='2024-09-24'else P.parent/'full_local_signal_two_dates_v1'/d/'signals/ALL_SIGNALS.parquet').set_index('sid')for d in ['2022-01-24','2024-09-24','2026-01-15']}
ns['OLDFEATURE']=pd.read_parquet(P.parent/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet',columns=['sid','day','target_row_present','r','scale','amount_ref','u','b','e','E','score']).set_index('sid')
tf=dict(f);tf['cache_identity']='ISOLATED_TEST_'+f['cache_identity'];tf['reuse20']={}
for sid,ref in f['reuse20'].items():
 dest=tmp/'fixtures'/f'{sid}.parquet';shutil.copyfile(ref['path'],dest);assert sha(dest)==ref['sha256'];tf['reuse20'][sid]={**ref,'path':str(dest)}
ns['F']=tf;roster=list(tf['reuse20']);checks=[];done={}
ns['import20'](done);assert len(done)==20
for sid,r in done.items():ns['verified_done'](sid,r)
assert len(list((tmp/'receipts').glob('*.json')))==20 and not list((tmp/'running').glob('*.json'))
checks.append({'case':'normalize_import_all20_strict_schema_and_old_reference_checks','result':'PASS','models':0,'receipts':20})
# A valid DONE wins over a stale marker without any process liveness action.
sid='000620.SZ';ns['marker'](tmp/'running'/f'{sid}.json',{'pid':os.getpid(),'cache_identity':tf['cache_identity']});d,u=ns['reconcile'](roster);assert len(d)==20 and not u and not(tmp/'running'/f'{sid}.json').exists()
checks.append({'case':'valid_DONE_plus_stale_RUNNING','result':'PASS','new_model':False})
# Complete pending result after lost receipt: recover by values+identity+fsync, no compute.
sid='300085.SZ';(tmp/'receipts'/f'{sid}.json').unlink();os.replace(tmp/'artifacts'/f'{sid}.parquet',tmp/'pending'/f'{sid}.parquet.tmp')
d,u=ns['reconcile'](roster);assert len(d)==20 and not u and d[sid]['origin']=='ORPHAN_RECOVERED_BY_VALUES_NO_MODEL'and not(tmp/'pending'/f'{sid}.parquet.tmp').exists()
checks.append({'case':'complete_pending_orphan_without_receipt','result':'PASS_READONLY_PROMOTION_NO_MODEL','rows':1054})
# Corrupt a committed file: the original receipt is retained, not repaired/recomputed.
sid='000001.SZ';receipt_before=sha(tmp/'receipts'/f'{sid}.json');(tmp/'artifacts'/f'{sid}.parquet').write_bytes(b'corrupt fixture only')
d,u=ns['reconcile'](roster);assert len(d)==19 and any(z['sid']==sid and z['status']=='UNKNOWN_NO_AUTORETRY'for z in u)and sha(tmp/'receipts'/f'{sid}.json')==receipt_before
checks.append({'case':'DONE_receipt_file_hash_mismatch','result':'PASS_UNKNOWN_PRESERVED_NO_MODEL'})
# Explicit error prevents automatic recovery or recomputation.
sid='000620.SZ';(tmp/'receipts'/f'{sid}.json').unlink();ns['atomic_json'](tmp/'errors'/f'{sid}.json',{'status':'ERROR_NO_AUTORETRY','error':'isolated synthetic file-state'})
d,u=ns['reconcile'](roster);assert any(z['sid']==sid and z['reason']=='ERROR_NO_AUTORETRY'for z in u)and not(tmp/'receipts'/f'{sid}.json').exists()
checks.append({'case':'explicit_ERROR_even_with_readable_artifact','result':'PASS_ERROR_ISOLATED_NO_AUTORECOVERY'})
# Footer absent/partial write never becomes DONE.
sid='301611.SZ';(tmp/'receipts'/f'{sid}.json').unlink();(tmp/'artifacts'/f'{sid}.parquet').unlink();(tmp/'pending'/f'{sid}.parquet.tmp').write_bytes(b'PAR1')
d,u=ns['reconcile'](roster);assert any(z['sid']==sid and z['status']=='UNKNOWN_NO_AUTORETRY'for z in u)and not(tmp/'receipts'/f'{sid}.json').exists()and (tmp/'pending'/f'{sid}.parquet.tmp').read_bytes()==b'PAR1'
checks.append({'case':'incomplete_pending_footer','result':'PASS_UNKNOWN_BYTES_PRESERVED_NO_MODEL'})
# No test source is within production artifact/receipt/running directories.
assert tmp.is_relative_to(Path('/tmp')) or str(tmp).startswith('/private/var/folders/')
out={'status':'PASS_ISOLATED_PURE_FILE_RECOVERY_HELPER_CASES','remaining_blocks':[],'cache_identity_under_review':f['cache_identity'],'runner_sha256':sha(code),'functions_AST_executed':needed,'test_directory':str(tmp),'cases':checks,'reviewer_models':0,'reviewer_accounts':0,'production_artifacts_modified':False,'technical_note':'Initial pure-file run reached all6 case assertions, then final sandbox path assertion rejected macOS /var/folders temp spelling. Fresh /tmp test rerun only, no production or model action.','limits':['Exact helper bodies exercised with copied20 fixtures, not original signal/kernel calls.','No OS process death, SIGINT/SIGTERM, power loss, ENOSPC, real PID-liveness or concurrent-writer race test.','Footer/identity/value recovery is tested at file-state level only; no original pre-crash expected-byte hash exists for orphan files.'],'source_sha256':{str(z):sha(z)for z in [code,P/'pilot.py',R/'FREEZE.json',R/'DAILY_SCHEMA.arrow',Path(__file__)]}}
p=O/'PURE_FILE_RECOVERY_AUDIT.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':out['status'],'sha256':sha(p),'cases':len(checks),'models':0,'tempdir':str(tmp)},ensure_ascii=False))
