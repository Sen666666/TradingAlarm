"""Exact event interface and export tests. Never constructs real Data or runs history."""
from pathlib import Path
from types import SimpleNamespace
import copy
import gzip
import hashlib
import importlib.util
import json
import os
import sys
import time
import tracemalloc
sys.dont_write_bytecode=True
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('cash688200_test',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
f=e.frozen;D=e.D;pd=e.pd;np=f.np
CHECKS=[]
def check(name,truth=True):
    assert truth,name
    CHECKS.append(name)
def rejects(name,call):
    try:call()
    except (AssertionError,KeyError,ValueError,FileExistsError):check(name)
    else:raise AssertionError(name)

def main():
    out=P/'qa_runs'/str(time.time_ns());out.mkdir(parents=True)
    static=e.self_check();check('all_Engine_methods_except_export_identical',static['result']=='PASS')
    check('Data_default_unchanged',e.Data.__init__.__defaults__==('2026-06-30',))
    check('native_admit_function_identical',e.native_admit_cash is f.base.v.b.v6.admit_cash)
    seen={}
    def checked(p,h):
        assert e.stream.file_sha(p)==h,('HASH_DRIFT',p);seen[p]=h
    ev=e.validated_event(checked);check('independent_PASS_hash_scope_gate')
    for p,h in ev['evidence_hashes'].items():checked(p,h)
    check('exact_six_evidence_hashes',len(ev['evidence_hashes'])==6)
    sid=ev['sid'];dt=pd.Timestamp(ev['ex_date']);record=pd.Timestamp(ev['record_date'])
    # Only two source rows, no Data() constructor and no historical account prefix.
    source=pd.read_parquet(ev['signal_path']).loc[[record,dt]].copy()
    actions=e.read(Path(ev['local_action_path']))
    def fixture():
        data=SimpleNamespace(end=dt,raw={sid:source.copy(deep=True)},actions={sid:copy.deepcopy(actions)},events={},admission=[],sid_sector={sid:'半导体'},hashes={})
        data.z=lambda s,d:data.raw[s].loc[d]
        data.action=lambda s,d:[v for v in data.actions[s]['events'] if v['effective_date']==e.day(d)]
        return data
    data=fixture();e.admit_exact(data,ev,checked)
    check('exact_source_loader_admission',set(data.events)=={(sid,dt)} and len(data.admission)==1)
    check('separate_source_cash_and_reference',data.events[(sid,dt)]['d_source']=='0.23' and data.events[(sid,dt)]['d_cash']=='0.23' and data.events[(sid,dt)]['d_ref']=='0.2297')
    for label,key,value in [('sid','sid','688248.SH'),('date','ex_date','2024-10-14'),('id','economic_event_id_candidate','688200.SH|OTHER'),('record','record_date','2024-10-09'),('pay','pay_date','2024-10-14'),('cash','d_cash','0.2297'),('source','d_source','0.2297'),('reference','d_ref','0.23'),('type','event_type','SPLIT'),('source_path','signal_path','memory://wrong')]:
        changed=copy.deepcopy(ev);changed[key]=value
        rejects('reject_'+label,lambda v=changed:e.admit_exact(fixture(),v,checked))
    rejects('reject_duplicate',lambda:e.admit_exact(data,ev,checked))
    for name,mutate in [('factor',lambda d:d.raw[sid].loc.__setitem__((dt,'adjustment_factor'),9.0)),('lineage',lambda d:d.raw[sid].loc.__setitem__((dt,'source_path'),'wrong')),('split',lambda d:next(v for v in d.actions[sid]['events'] if v['effective_date']==e.day(dt)).update(split_ratio='2')),('action_cash',lambda d:next(v for v in d.actions[sid]['events'] if v['effective_date']==e.day(dt)).update(cash_per_old_share='0.2297'))]:
        d=fixture();mutate(d);rejects('reject_native_'+name,lambda d=d:e.admit_exact(d,ev,checked))
    d=fixture();d.end=record;e.admit_exact(d,ev,checked);check('no_event_before_loaded_end',not d.events and not d.admission)
    # Q0 native retained ticket bridge only. No fabricated equity entitlement.
    x=e.Engine(data);origin=f.lineage(data.z(sid,record))
    x.tickets={sid:dict(sid=sid,ticket_id='synthetic_688200',ever_seeded=False,status='RETAINED',origin=origin,current_factor=D(ev['factor_old']),original_factor=D(ev['factor_old']),nav0=D('1297938.1769722432405'),budget=D('25958.763539444864810'),original_ifloor=D('169.9110006633611'),ifloor=D('169.9110006633611'),signal_day='2024-09-26',plan=None,last_verified_day='2024-10-10')}
    pending=[dict(sid=sid,origin=origin,factor=D(ev['factor_old']),ticket_id='synthetic_688200')]
    x.register_pay(record);before=copy.deepcopy(x.tickets[sid]);balances=(x.cash,x.receivable,copy.deepcopy(x.claims))
    x.economic_preflight(dt,pending);x.accrue(dt);x.register_pay(dt)
    check('Q0_zero_cash_receivable_claims',balances==(x.cash,x.receivable,x.claims))
    check('Q0_no_position_order_round',not x.active and not x.archive and not x.orders)
    check('Q0_native_factor_bridge_only',x.tickets[sid]['current_factor']==D(ev['factor_new']) and x.tickets[sid]['last_verified_day']=='2024-10-11')
    check('Q0_ticket_identity_budget_I_phase_unchanged',all(x.tickets[sid][k]==v for k,v in before.items() if k not in ('current_factor','last_verified_day')))
    check('Q0_no_information_CP_priority_consumption',not x.confirmations and not x.cp_log and not x.events)
    check('Q0_equity_only_zero_bridge',len(x.equity)==1 and x.equity[0]['event']=='FACTOR_BRIDGE' and x.equity[0]['record_qty']==0 and x.equity[0]['cash_delta']=='0')
    # Nonzero entitlement still uses exactly original NET80 accrual/pay methods.
    y=e.Engine(data);a=dict(id='fixture_round',sid=sid,dividend=D(0),lots=[dict(q=200)])
    y.active[sid]=a;y.archive[a['id']]=a;y.register_pay(record);cash=y.cash
    y.accrue(dt);check('registered_NET80_unchanged',y.receivable==D('36.800') and a['dividend']==D('36.800'))
    y.register_pay(dt);check('pay_close_unchanged',y.cash==cash+D('36.800') and y.receivable==0)
    # Prior-day causal boundary: only the native zero snapshot differs, not balances.
    without=e.Engine(fixture());with_event=e.Engine(data)
    for engine in (without,with_event):engine.accrue(record);engine.register_pay(record)
    za={k:v for k,v in vars(without).items() if k not in ('d','snapshots')};zb={k:v for k,v in vars(with_event).items() if k not in ('d','snapshots')}
    check('before_effective_date_economic_state_identical',f.digest(za)==f.digest(zb))
    check('only_native_zero_record_snapshot_added',with_event.snapshots=={(sid,'2024-10-10'):{'q':0,'round':None}} and not without.snapshots)
    # Mixed types, collisions, sets and nonfinite scalar bytes follow the old clean/save.
    shared={'中文':D('0.2300'),'bool':np.bool_(True),'int':np.int64(7),'float':np.float32(1.25)}
    value=[shared,shared,{'a':{('x',1),('a',2)},'empty':[],'tuple':(None,True,False,{},set()),'time':pd.Timestamp('2024-10-11'),'q':[float('nan'),float('inf'),-0.0],1:'first','1':'last'}]
    expected=(json.dumps(f.clean(value),ensure_ascii=False,indent=2,default=str)+'\n').encode()
    meta=e.stream.save_gzip(out/'types.json.gz',value);raw=gzip.decompress((out/'types.json.gz').read_bytes())
    check('stream_exact_old_bytes_all_types',raw==expected)
    check('stream_both_hashes_and_sizes',meta['uncompressed_sha256']==hashlib.sha256(raw).hexdigest() and meta['gzip_sha256']==e.stream.file_sha(out/'types.json.gz') and meta['uncompressed_bytes']==len(raw))
    e.stream.save_gzip(out/'types2.json.gz',value);check('gzip_deterministic',e.stream.file_sha(out/'types.json.gz')==e.stream.file_sha(out/'types2.json.gz'))
    rejects('exclusive_output_no_overwrite',lambda:e.stream.save_gzip(out/'types.json.gz',value))
    # Genuine frozen native M12 fixture; full export before/after account and aliases.
    t=f.module('cash688200_frozen_fixture',e.FROZEN/'synthetic_tests.py')
    x=t.setup(cls=e.Engine);t.hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[('old',t.dt)]={'M':0,'E':0,'W':True}
    rows=t.planned(x);decision=x.select_open(t.nxt,rows);x.execute_selected(t.nxt,rows,decision)
    x.pending=rows;x.ledger=[dict(day=e.day(t.nxt))]
    state=f.digest({k:v for k,v in vars(x).items() if k!='d'});data_state=f.digest(vars(x.d))
    aliases={s:id(a) for s,a in x.active.items()};before_method=f.Engine.export
    # Test-only output-root variable redirection. Frozen function and source are unchanged.
    old_root=f.O
    try:
        f.O=out;f.Engine.export(x,out/'reference_export')
    finally:f.O=old_root
    check('original_export_function_unchanged',f.Engine.export is before_method)
    check('original_export_state_unchanged',state==f.digest({k:v for k,v in vars(x).items() if k!='d'}))
    x.export(out/'gzip_export')
    check('new_export_state_and_data_unchanged',state==f.digest({k:v for k,v in vars(x).items() if k!='d'}) and data_state==f.digest(vars(x.d)))
    check('active_archive_aliases_unchanged',all(id(x.active[s])==v and x.archive[x.active[s]['id']] is x.active[s] for s,v in aliases.items()))
    old=out/'reference_export';new=out/'gzip_export'
    oldnames={p.name for p in old.iterdir()};newnames={p.name for p in new.iterdir()}
    check('only_expected_output_family_change',newnames==(oldnames-{'FUNDING_BRANCH_BOOKS.json'})|{'FUNDING_BRANCH_BOOKS.json.gz','COMPRESSED_OUTPUTS.json'})
    matched=[]
    for p in old.iterdir():
        if p.name=='OUTPUT_HASHES.json':continue
        if p.name=='FUNDING_BRANCH_BOOKS.json':same=gzip.decompress((new/(p.name+'.gz')).read_bytes())==p.read_bytes()
        else:same=(new/p.name).read_bytes()==p.read_bytes()
        check('export_byte_identical_'+p.name,same);matched.append(p.name)
    inventory=e.read(new/'OUTPUT_HASHES.json')
    check('complete_actual_output_hashes',set(inventory)==newnames-{'OUTPUT_HASHES.json'} and all(e.stream.file_sha(new/n)==h for n,h in inventory.items()))
    metadata=e.read(new/'COMPRESSED_OUTPUTS.json')['files'][0]
    check('book_decompressed_hash_matches_original',metadata['uncompressed_sha256']==e.stream.file_sha(old/'FUNDING_BRANCH_BOOKS.json'))
    # Large repeated synthetic rows show encoder working memory does not scale with tree size.
    large=[{'payload':'x'*4096,'i':i} for i in range(4096)]
    tracemalloc.start();start=time.perf_counter();scale=e.stream.save_gzip(out/'scale.json.gz',large);peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
    scale.update(peak_traced_bytes=peak,seconds=time.perf_counter()-start,synthetic_only=True)
    check('stream_16MB_peak_under_5MB',scale['uncompressed_bytes']>16*1024*1024 and peak<5*1024*1024)
    result=dict(result='PASS',assertions=len(CHECKS),checks=CHECKS,history_run=False,real_Data_constructed=False,output_directory=str(out),static=static,exact_source_hashes=seen,export_matched_files=matched,scale=scale,
                engine_sha256=e.sha(P/'engine.py'),stream_sha256=e.sha(P/'stream_output.py'),tests_sha256=e.sha(P/'synthetic_tests.py'),admission_lock_sha256=e.LOCK_SHA)
    e.save(Path(os.environ.get('QA_RESULT_PATH',P/'SYNTHETIC_QA.json')),result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
