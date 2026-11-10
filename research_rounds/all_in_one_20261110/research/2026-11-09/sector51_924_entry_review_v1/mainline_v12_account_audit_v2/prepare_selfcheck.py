"""Preparation-only parser/negative-case tests using existing synthetic bytes."""
from pathlib import Path
import ast,copy,gzip,hashlib,json,sys,time
sys.dont_write_bytecode=True
import accounting_core as au
import compression_integrity as ci
import prefix_independent as pi
import checkpoint_metadata as cm
import verify_saved_funding_semantics as sem
from stream_branch_books import iter_books
from audit_saved_outputs import certified_frontier
HOME=Path(__file__).resolve().parent;ROOT=HOME.parent;C=ROOT/'mainline_candidate_v12_winner_funding_cash_688200_v2'
checks=[]
def ok(name,test=True):assert test,name;checks.append(name)
def reject(name,fn):
    try:fn()
    except (AssertionError,EOFError,gzip.BadGzipFile,OSError):checks.append(name)
    else:raise AssertionError('not rejected: '+name)
def write(path,x):path.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    out=HOME/'synthetic_selfcheck'/str(time.time_ns());out.mkdir(parents=True,exist_ok=False)
    qa=au.read(C/'SYNTHETIC_QA.json');fixture=Path(qa['output_directory']);gzdir=fixture/'gzip_export';ref=fixture/'reference_export';manifest=au.read(gzdir/'COMPRESSED_OUTPUTS.json');p=gzdir/'FUNDING_BRANCH_BOOKS.json.gz'
    integrity=ci.verify(p,manifest,au.read(gzdir/'OUTPUT_HASHES.json'));ok('both_file_and_decompressed_hashes_and_lengths')
    ok('decompressed_exact_reference_bytes',integrity['uncompressed_sha256']==au.sha(ref/'FUNDING_BRANCH_BOOKS.json'))
    def callback(b,i,prefix,context):
        sem.reference(b);ok('synthetic_branch_'+str(i)+'_reference')
        ok('synthetic_branch_'+str(i)+'_identity',sem.digest({k:b[k] for k in ('retained','requests','plan','event_reserved','bar_q_C')})==b['branch_id'])
        return pi.digest(b)
    gb=list(iter_books(p,callback));rb=list(iter_books(ref/'FUNDING_BRANCH_BOOKS.json',pi.branch_digest))
    ok('gzip_and_plain_full_book_descriptors',all(pi.descriptor(a)==pi.descriptor(b) for a,b in zip(gb,rb)) and len(gb)==len(rb))
    m=copy.deepcopy(manifest);m['files'][0]['gzip_sha256']='0'*64;reject('reject_compressed_hash',lambda:ci.verify(p,m))
    m=copy.deepcopy(manifest);m['files'][0]['uncompressed_sha256']='0'*64;reject('reject_uncompressed_hash',lambda:ci.verify(p,m))
    m=copy.deepcopy(manifest);m['files'][0]['uncompressed_bytes']-=1;reject('reject_uncompressed_length',lambda:ci.verify(p,m))
    m=copy.deepcopy(manifest);m['files'][0]['ordered_lists_preserved']=False;reject('reject_false_format_contract',lambda:ci.verify(p,m))
    bad=out/'truncated';bad.mkdir();bp=bad/p.name;bp.write_bytes(p.read_bytes()[:-7]);m=copy.deepcopy(manifest);m['files'][0].update(gzip_sha256=ci.sha(bp),gzip_bytes=bp.stat().st_size)
    reject('reject_truncated_gzip_even_with_updated_outer_hash',lambda:ci.verify(bp,m))
    old={n:[{'day':'2024-10-09','n':1},{'day':'2024-10-10','n':2}] for n in pi.DAILY};new=copy.deepcopy(old)
    ok('all_25_daily_families_exact',len(pi.daily_equal(old,new,'2024-10-10'))==2)
    new['ORDERS'][1]['n']=3;reject('reject_one_economic_prefix_field',lambda:pi.daily_equal(old,new,'2024-10-10'))
    new=copy.deepcopy(old);new['EQUITY_EVENTS'][0].update(sid='688200.SH',cash_delta='1');reject('reject_nonzero_event_difference_before_effective_date',lambda:pi.daily_equal(old,new,'2024-10-10'))
    b=copy.deepcopy(gb[0]);b['close_day']='2024-10-10';b['book_id']='a'*64;b['_stream_content_sha256']='a'*64;b['scratch_integrity']={'before':'a','after':'a','passed':True}
    c=copy.deepcopy(b);c['book_id']='b'*64;c['_stream_content_sha256']='b'*64;c['scratch_integrity']={'before':'b','after':'b','passed':True}
    ok('only_Oct10_book_id_and_scratch_hash_exclusion',pi.descriptor(b)==pi.descriptor(c))
    c['_unexpected_top_level']=1;ok('unknown_top_level_field_not_silently_ignored',pi.descriptor(b)!=pi.descriptor(c));c.pop('_unexpected_top_level')
    c['branches'][0]='c'*64;ok('full_branch_content_change_is_detected',pi.descriptor(b)!=pi.descriptor(c))
    b['close_day']=c['close_day']='2024-10-09';ok('no_hash_exclusion_before_Oct10',pi.descriptor(b)!=pi.descriptor(c))
    ledger=[{'day':'2024-09-02','NAV':'1200000'},{'day':'2024-09-03','NAV':'1200001'}]
    status=dict(result='ATOMIC_BLOCK',days=2,last=ledger[-1],runtime_error=None,atomic_block=dict(day='2024-09-04',atomic_rollback=True))
    ok('arbitrary_2day_certified_frontier',certified_frontier(status,ledger,['2024-09-02','2024-09-03','2024-09-04'])=='2024-09-03')
    broken=copy.deepcopy(status);broken['result']='RUNTIME_ERROR';reject('reject_uncertified_runtime_error',lambda:certified_frontier(broken,ledger,['2024-09-02','2024-09-03']))
    broken=copy.deepcopy(status);broken['last']={'day':'2024-09-04'};reject('reject_status_ledger_mismatch',lambda:certified_frontier(broken,ledger,['2024-09-02','2024-09-03']))
    cp=out/'fake_checkpoint';cp.mkdir();body=cp/'STATE.pickle.gz';body.write_bytes(b'THIS IS NOT A PICKLE OR GZIP; HASH ONLY')
    bind=dict(schema=cm.SCHEMA,source_manifest_path=str(out/'SOURCE_HASHES.json'),source_manifest_sha256='0'*64,code_and_evidence_hashes={},data_identity={'source_hashes':{}},python=list(sys.version_info[:3]),cache_fields=['meta'],source_migration_allowed=False);bind['binding_id']=cm.digest(bind)
    receipt=dict(schema=cm.SCHEMA,status='CERTIFIED_COMMITTED',certified_day='2024-10-10',binding=bind,state_file=body.name,state_sha256=ci.sha(body),state_bytes=body.stat().st_size,history_authorization=False,continuation_requires_separate_run_approval=True)
    write(cp/'COMMIT.json',receipt);h=ci.sha(cp/'COMMIT.json')
    cq=cm.audit(cp,h,out,'2024-10-10',verify_sources=False);ok('opaque_non_pickle_bytes_not_deserialized',cq['pickle_opened'] is False)
    reject('reject_untrusted_receipt_hash',lambda:cm.audit(cp,'0'*64,out,'2024-10-10',False))
    reject('reject_checkpoint_after_certified_frontier',lambda:cm.audit(cp,h,out,'2024-10-09',False))
    body.write_bytes(body.read_bytes()+b'x');reject('reject_tampered_opaque_state',lambda:cm.audit(cp,h,out,'2024-10-10',False))
    source_scan=[]
    for f in HOME.glob('*.py'):
        tree=ast.parse(f.read_text());imports=[ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        assert not any('pickle' in n or 'checkpoint_tests' in n or n.startswith('import engine') or 'from engine' in n for n in imports)
        source_scan.append(dict(file=f.name,sha256=au.sha(f),imports=imports))
    ok('all_scripts_parse_no_engine_Data_pickle_import')
    seal=au.read(ROOT/'mainline_v12_account_audit_v1/FINAL_AUDIT_SEAL.json')
    ok('v1_69_sealed_files_unchanged',all(au.sha(ROOT/'mainline_v12_account_audit_v1'/n)==h for n,h in seal['files'].items()))
    result=dict(result='PASS_PREPARATION_SYNTHETIC_ONLY',assertions=len(checks),checks=checks,fixture_directory=str(fixture),compressed_integrity=integrity,source_scan=source_scan,current_candidate_engine_sha256_observation_only=au.sha(C/'engine.py'),candidate_freeze_not_asserted=True,new_real_run_read=False,strategy_imported=False,Data_constructed=False,history_executed=False,pickle_deserialized=False)
    write(HOME/'PREPARATION_QA.json',result)
    print(json.dumps(dict(result=result['result'],assertions=len(checks),fixture=str(fixture),engine_frozen=False)))
if __name__=='__main__':main()
