"""Pure synthetic admission tests and a fixed seven-session prefix; never a full run."""
from pathlib import Path
import ast,copy,json,sys,time,types
import numpy as np
import pandas as pd
import mask_bridge as M
from runner import save,semantic_payloads
E=M.E;HERE=Path(__file__).resolve().parent
CUTOFF=pd.Timestamp('2024-09-10')

def canonical(x):return json.dumps(x,sort_keys=True,default=str,allow_nan=True)
def nan_equal(a,b):return canonical(a)==canonical(b)
def synth():
    checks=[]
    source=E.bridge.EVENT_ROOT/'relative_priority_v1/simulate.py'
    tree=ast.parse(source.read_text());qnode=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='queue')
    priority=E.bridge.EVENT_ROOT/'relative_priority_v1/priority.py'
    def fixture(mask):
        s=types.ModuleType('SYNTHETIC_MASK');s.SOURCE=source;s.pd=pd;s.np=np
        s.true=lambda x:pd.notna(x) and x in (True,1)
        s.finite=lambda x:bool(np.isfinite(x))
        d=pd.Timestamp('2024-09-02')
        rows=[]
        for sid,score in [('N1',10.),('N2',9.),('T1',8.),('T2',7.),('T3',6.),('T4',5.)]:
            rows.append(dict(event_id='SYN|'+sid,window='2024_924',day=d,sid=sid,name=sid,industry='S',sector='S',event_type='A_SECTOR_BIRTH',PVR_score=score,I_qualified=True,PVR_known=True,relative_known=True,relative_event=0,i_floor=1.))
        s.ev=pd.DataFrame(rows)
        def reset(*args):
            for key in ('actions','decisions','ranking_audit','rounds','registrations','claim_ledger','bridges','marks'):setattr(s,key,[])
            s.archives={};s.claims={}
        s.reset=reset
        def new_state(r,arm,rid,check):
            st=dict(r,state='BUY_PENDING',arm=arm,round_id=rid,signal_day=r['day'],**check);s.archives[rid]=st;return st
        s.new_state=new_state
        exec(compile(priority.read_text(),str(priority),'exec'),s.__dict__)
        exec(compile(ast.Module(body=[qnode],type_ignores=[]),str(source)+':queue_only','exec'),s.__dict__)
        b=M.AdmissionMaskBridge(s,admission_members={'T1','T2','T3','T4'}) if mask else E.ExecutionBridge(s)
        b.close_nd=E.D(1200000)
        b._checkclose=lambda r:dict(close_check='PASS',close_q=100,prior20_capacity=1000)
        return s,b,d
    s,b,d=fixture(True);original=s.ev.copy(deep=True);groups={k:v.copy(deep=True) for k,v in b.groups.items()};b._select_close(d)
    assert set(b.states)=={'T1','T2'}
    assert [x['sid'] for x in s.decisions if x['decision']=='PASS_NOT_TOP2']==['T3','T4']
    assert [x['sid'] for x in b.mask_audit[0]['excluded']]==['N1','N2']
    pd.testing.assert_frame_equal(s.ev,original)
    for k in groups:pd.testing.assert_frame_equal(b.groups[k],groups[k])
    assert s.ev.PVR_score.tolist()==[10.,9.,8.,7.,6.,5.]
    checks.append('MASK_BEFORE_TOP2_SELECTS_TECH_3RD_4TH_IN_ORIGINAL_QUEUE_WITH_UNCHANGED_SOURCE_AND_PVR')
    s,b,d=fixture(True);b.states['N1']=dict(state='HELD',round_id='OLD_NONMEMBER')
    b._select_close(d)
    assert s.decisions[0]['sid']=='N1' and s.decisions[0]['decision']=='BLOCKED_HELD'
    assert b.states['N1']==dict(state='HELD',round_id='OLD_NONMEMBER')
    assert b.mask_audit[0]['retained_existing_nonmembers']==['N1']
    checks.append('EXISTING_NONMEMBER_STATE_NOT_REMOVED_OR_RERANKED_AS_FRESH_ENTRY')
    s,b,d=fixture(False);b._select_close(d);assert set(b.states)=={'N1','N2'}
    checks.append('BASELINE_USES_ORIGINAL_CLASS_NO_MASK_NO_DERIVED_SELECTION')
    s,b,d=fixture(True)
    try:b._entry_proposal(dict(sid='N1',round_id='BAD'),d)
    except AssertionError as e:assert e.args[0][0]=='NONMEMBER_INIT_AT_OPEN'
    else:raise AssertionError('OPEN assertion did not fire')
    checks.append('OPEN_NONMEMBER_INIT_FAIL_CLOSED')
    s,b,d=fixture(True);b._checkclose=lambda r:dict(close_check='KNOWN_REJECT') if r['sid']=='T1' else dict(close_check='PASS',close_q=100,prior20_capacity=1000)
    b._select_close(d);assert set(b.states)=={'T2','T3'}
    checks.append('ORIGINAL_CLOSE_LEGAL_CANDIDATE_REPLACEMENT_WITHIN_MASK_NOT_POST_TOP2_FILTER')
    for method in ('open_phase','close_phase','open_exits','_add_proposal','commit','reserve_proposal','snapshot','reconcile','prepare_promotions','commit_promotions'):
        assert getattr(M.AdmissionMaskBridge,method) is getattr(E.ExecutionBridge,method)
    checks.append('OPEN_GLOBAL_RANK_NO_BACKFILL_AND_ALL_ASSET_ADD_EXIT_UNKNOWN_METHODS_IDENTICAL')
    # Nonempty REAL dependency overlap: prior full source hashes + original code map.
    sources=json.loads((M.BASE/'cohort_2024_924/SOURCE_HASHES.json').read_text())
    deps=json.loads((M.BASE/'COHORT_EXECUTION_CONTRACT_V3.json').read_text())['code_hashes']
    source_engine=E.bridge.EVENT_ROOT/'cash_equity_baseline_2024_v1/engine.py'
    deps[str(source_engine)]=E.bridge.sha(source_engine)
    overlap=set(sources)&set(deps);assert overlap
    merged=M.merge_hashes(sources,deps,sources)
    assert len(merged)==len(set(sources)|set(deps)) and all(merged[p]==sources[p]==deps[p] for p in overlap)
    key=sorted(overlap)[0]
    try:M.merge_hashes(sources,{key:'0'*64})
    except AssertionError as e:assert e.args[0][0]=='HASH_KEY_CONFLICT'
    else:raise AssertionError('hash conflict accepted')
    checks.append('REAL_NONEMPTY_DEPENDENCY_HASH_OVERLAP_MERGES_IDENTICAL_AND_FAILS_CONFLICT')
    out=HERE/'qa_synthetic_attempt_01';out.mkdir(exist_ok=False)
    save(out/'RESULT.json',dict(status='PASS',tests=checks,real_dependency_overlap=sorted(overlap),real_source_count=len(sources),merged_count=len(merged),derivation=M.DERIVATION))
    print('PASS_SYNTHETIC',len(checks))

def prefix(arm):
    start=time.monotonic();out=HERE/('qa_prefix_'+arm+'_attempt_01');out.mkdir(exist_ok=False)
    s=E.bridge.load_original('2024_924');b=M.make_bridge(s,arm);before=s.ev.copy(deep=True);groups={d:tuple(g.event_id) for d,g in b.groups.items()};daily=[]
    days=s.cal[(s.cal>=pd.Timestamp('2024-09-01'))&(s.cal<=CUTOFF)];assert len(days)==7
    for n,day in enumerate(days):
        o=b.open_phase(day)['reconciliation'] if n else None;c=b.close_phase(day)
        daily.append(dict(day=day,OPEN=o,CLOSE=c,actions=len(s.actions),archives=len(s.archives),audit_rows=len(b.audit)))
    pd.testing.assert_frame_equal(s.ev,before);assert {d:tuple(g.event_id) for d,g in b.groups.items()}==groups
    payloads=semantic_payloads(s,b,daily)
    for name,value in payloads.items():save(out/(name+'.json'),value)
    save(out/'MASK_AUDIT.json',getattr(b,'mask_audit',[]));save(out/'OPEN_MASK_AUDIT.json',getattr(b,'open_mask_audit',[]))
    checks={'seven_session_prefix_only':True,'source_ev_and_groups_unchanged':True,'all_init_within_membership':all(a['sid'] in M.members() for a in s.actions if a['side']=='buy_core') if arm=='tech407' else True}
    if arm=='all1709':
        for name in ('ACTIONS','DECISIONS','RANKING_AUDIT','AUDIT','DAY_LEDGER','REGISTRATIONS','CLAIM_LEDGER','EQUITY_BRIDGES','PROFIT_GATES'):
            old=json.loads((M.BASE/'cohort_2024_924'/(name+'.json')).read_text())
            datekey='inventory_snapshot_day' if name=='REGISTRATIONS' else 'day'
            old=[x for x in old if x.get(datekey) is not None and pd.Timestamp(x[datekey])<=CUTOFF]
            if name=='DAY_LEDGER':old=[{k:v for k,v in x.items() if k not in ('seconds','peak_rss_bytes')} for x in old]
            checks['exact_'+name]=nan_equal(payloads[name],old)
            assert checks['exact_'+name],name
    assert all(checks.values())
    save(out/'RESULT.json',dict(status='PASS',arm=arm,cutoff=str(CUTOFF.date()),days=len(days),checks=checks,actions=len(s.actions),elapsed_seconds=time.monotonic()-start))
    print('PASS_PREFIX',arm,len(days),len(s.actions))
if __name__=='__main__':
    if sys.argv[1]=='synthetic':synth()
    else:prefix(sys.argv[1])
