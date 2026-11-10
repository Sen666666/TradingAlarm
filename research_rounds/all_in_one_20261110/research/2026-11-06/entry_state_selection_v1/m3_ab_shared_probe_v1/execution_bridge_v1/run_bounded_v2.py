"""Strictly fixed 2022 Jan6/7/10 engineering proxy path; never a full backtest."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,copy,hashlib,time,contextlib,traceback
import engine_v2 as E
HERE=Path(__file__).resolve().parent
def dump(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,default=str,ensure_ascii=False);f.write('\n')
def canonical(x):return json.dumps(x,sort_keys=True,default=str,allow_nan=True)
def hybrid_source_equivalence(s):
    # Mechanically first original Jan7 ADD by sid, not chosen for return.
    path=E.bridge.EVENT_ROOT/'relative_priority_equity_run_2022_v1/dynamic/ACTIONS.csv'
    sealed=s.pd.read_csv(path)
    subset=sealed[sealed.arm.eq('A_UNION_B')&sealed.side.eq('buy_add')&sealed.day.eq('2022-01-07')].sort_values('sid')
    row=subset.iloc[0];rid=row.round_id;sid=row.sid
    initial=sealed[sealed.round_id.eq(rid)&sealed.side.eq('buy_core')].iloc[0]
    signal=s.pd.Timestamp(initial.signal_day);fill=s.pd.Timestamp(initial.day);testday=s.pd.Timestamp(row.day)
    assert (str(signal.date()),str(fill.date()),str(testday.date()))==('2022-01-05','2022-01-06','2022-01-07')
    b=E.ExecutionBridge(s);r=s.ev[s.ev.sid.eq(sid)&s.ev.day.eq(signal)].iloc[0].to_dict()
    check=s.checkclose(r);st=s.new_state(r,'A_UNION_B',rid,check);b.states[sid]=st
    s.entry_open(b.states,sid,st,fill);s.held_close(b.states,sid,st,fill)
    assert st['entry_q']==int(initial.q) and st['addpending'] is not None
    b.last_close=fill;before=copy.deepcopy(st);saved=b.capture_runtime()
    s.held_open(b.states,sid,st,testday,fill);whole=copy.deepcopy(dict(state=st,actions=s.actions))
    b.restore_runtime(saved);st=s.archives[rid]
    assert s.before_held(b.states,sid,st,testday)
    b._callback('source_exit_only')(b.states,sid,st,testday,fill)
    p=b._callback('source_prepare_add',INIT=s.INIT,SLOT=s.SLOT,RISK=s.RISK)(b.states,sid,st,testday,fill,s.raw[sid].get(testday))
    assert p is not None
    b._callback('source_commit_add')(st,testday,p['q'],p['fee'],p['price'],p['floor'],p['prior_net'])
    assert canonical(whole)==canonical(dict(state=st,actions=s.actions))
    assert st['add']==int(row.q)
    return dict(status='PASS_SOURCE_SNAPSHOT_HYBRID_ONLY',sid=sid,round_id=rid,signal=signal,entry=fill,test_open=testday,
        original_ADD_q=int(row.q),before=before,after=whole,source_action_hash=E.bridge.sha(path),
        explanation='Exact old fixed-budget consumer source snapshot. This stock is not claimed held by the shared three-OPEN wallet.',
        equality='Full original state and all source actions exact; original whole held_open versus split validation/exits/ADD prep/commit.')
def poison_open(b,day,baseline,pre,post):
    s=b.s;maps=('raw','facts','cp','capacity','sector');original={k:getattr(s,k) for k in maps}
    count={}
    try:
        b.restore_runtime(pre)
        for name in ('raw','facts','cp'):
            cloned=dict(original[name]);n=0
            for sid,obj in original[name].items():
                frame=obj.frame.copy(deep=True);mask=frame.index>=day;n+=int(mask.sum())
                if name=='raw':
                    for col in ('raw_high','raw_low','raw_close','raw_volume'):
                        frame.loc[mask,col]=-987654321.
                elif name=='facts':
                    frame['i_target']=frame['i_target'].astype(object);frame.loc[mask,'i_target']=False;frame.loc[mask,'i_floor']=987654321.
                else:
                    frame['receipt']=frame['receipt'].astype(object);frame.loc[mask,'receipt']=True;frame.loc[mask,'candidate']=987654321.
                cloned[sid]=s.DayFrame(frame)
            setattr(s,name,cloned);count[name]=n
        s.capacity={sid:{d:(-987654321 if d>=day else value) for d,value in rows.items()} for sid,rows in original['capacity'].items()}
        s.sector={sec:{d:(0 if d>=day else value) for d,value in rows.items()} for sec,rows in original['sector'].items()}
        got=b.open_phase(day)
        assert canonical(got)==canonical(baseline),'OPEN polluted by current/future CLOSE-only inputs'
        return dict(day=day,status='PASS',held_before=sum(x.qty>0 for x in pre['own']['layers']),rows_poisoned=count,
                    compared='All OPEN actions, reservation trials, promotion/profit proofs, and reconciliation',
                    preserved='raw OPEN, factor, source lineage, previous CLOSE inputs, lawful equity metadata, dated rules',
                    limitation='No claim about future days after a legitimately different CLOSE, or real same-OPEN executability.')
    finally:
        for k,v in original.items():setattr(s,k,v)
        b.restore_runtime(post)
def run():
    output=HERE/sys.argv[1];output.mkdir(exist_ok=False)
    sources=[HERE/x for x in ('engine_v2.py','source_split_v2.py','run_bounded_v2.py','API_AND_TEST_PLAN.md','EXECUTION_BOUNDARIES_V2.md','test_execution_v2.py')]
    sources += [HERE.parent/'shared_feasibility_v1/limits_v3.py',HERE.parent/'source_bridge_v1/bridge.py']
    hashes={str(p):E.bridge.sha(p) for p in sources}
    frozen=dict(stage='FIXED_THREE_OPEN_ENGINEERING_NOT_RETURN_VALIDATION',window='2022',real_opens=E.REAL_OPENS,
                initialization=['2022-01-04','2022-01-05'],close_through='2022-01-10',code_hashes=hashes,
                historical_execution_proxy='Observe OPEN then compute quantity and book OPEN +/- 5bp, not an executability proof',started_utc=time.time())
    dump(output/'STARTED.json',frozen);begin=time.monotonic()
    try:
        with (output/'execution.log').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            s=E.bridge.load_original('2022');dump(output/'SOURCE_MANIFEST_AT_START.json',E.bridge.verified_manifest())
            hybrid=hybrid_source_equivalence(s);dump(output/'HYBRID_SOURCE_SPLIT_EQUIVALENCE.json',hybrid)
            b=E.ExecutionBridge(s);dump(output/'AST_DERIVATION.json',b.split['provenance'])
            init=[]
            for d in frozen['initialization']:init.append(b.close_phase(s.pd.Timestamp(d)))
            expected=json.loads((HERE.parent/'shared_feasibility_v1/first_open_2022_v3/PLANS.json').read_text())
            chosen=sorted([st['sid'] for st in b.states.values() if st['state']=='BUY_PENDING'])
            assert chosen==sorted(x['sid'] for x in expected) and len(chosen)==30
            assert not any(x['day']==s.pd.Timestamp('2022-01-04') and x['selected'] for x in s.decisions)
            opens=[];closes=[];perturbations=[]
            for day_str in E.REAL_OPENS:
                day=s.pd.Timestamp(day_str);pre=b.capture_runtime();result=b.open_phase(day);post=b.capture_runtime()
                opens.append(result);print('OPEN',day_str,result['reconciliation'],flush=True)
                if day_str!='2022-01-06':perturbations.append(poison_open(b,day,result,pre,post))
                closes.append(b.close_phase(day))
            assert tuple(b.completed_opens)==E.REAL_OPENS
            first=[a for a in opens[0]['audit'] if a['type'] in ('RESERVED','BUDGET_REJECTED')]
            comparison=[]
            assert len(first)==len(expected)==30
            for actual,old in zip(first,expected):
                sid=b.s.archives[actual['round_id']]['sid']
                fields=dict(sid=sid,source_formula_q=actual['original_formula_q']==old['original_single_q'],
                    initial_close_cap=actual['before_shared_q']==old['before_shared_caps_q'],shared_q=actual['shared_q']==old['shared_q'])
                assert sid==old['sid'] and all(fields[k] for k in fields if k!='sid')
                comparison.append(fields)
            dump(output/'FIRST30_V3_RESERVATION_COMPARISON.json',comparison)
            dump(output/'INITIALIZATION.json',init);dump(output/'OPEN_PHASES.json',opens);dump(output/'CLOSE_PHASES.json',closes)
            dump(output/'HELD_OPEN_FUTURE_POLLUTION_QA.json',perturbations)
            dump(output/'ACTIONS.json',s.actions);dump(output/'DECISIONS.json',s.decisions);dump(output/'RANKING_AUDIT.json',s.ranking_audit)
            dump(output/'ROUND_ARCHIVES.json',s.archives);dump(output/'FINAL_STATES.json',b.states);dump(output/'LAYERS.json',[E.asdict(x) for x in b.layers])
            dump(output/'REGISTRATIONS.json',s.registrations);dump(output/'CLAIMS.json',list(s.claims.values()));dump(output/'CLAIM_LEDGER.json',s.claim_ledger)
            dump(output/'EQUITY_BRIDGES.json',s.bridges);dump(output/'AUDIT.json',b.audit);dump(output/'ROUND_ND.json',b.caps)
            dump(output/'PROFIT_GATES.json',s.marks)
            dump(output/'ACTUAL_CONSUMED_SOURCE_HASHES.json',dict(s.hashes,**b.source_hashes))
            for path,h in dict(s.hashes,**b.source_hashes).items():assert E.bridge.sha(path)==h
            for path,h in hashes.items():assert E.bridge.sha(path)==h
            summary=dict(status='AUTHOR_PASS_FIXED_ENGINEERING_PROXY_ONLY',real_opens=E.REAL_OPENS,elapsed=time.monotonic()-begin,
                actions=len(s.actions),buy_core=sum(x['side']=='buy_core' for x in s.actions),buy_add=sum(x['side']=='buy_add' for x in s.actions),
                sells=sum(x['side'].startswith('sell') for x in s.actions),promotions=sum(x['type']=='PROMOTED' for x in b.audit),
                registrations=len(s.registrations),claims=len(s.claims),equity_bridges=len(s.bridges),
                first30_reservations_equal_sealed_v3=True,held_OPEN_pollution_tests=len(perturbations),
                source_split_original_snapshot='600820.SH Jan7 first original ADD, exact state/actions',
                final_reconciliation=closes[-1],no_performance_validation=True,not_executability_proof=True,code_hashes=hashes)
            dump(output/'RESULT.json',summary)
        output_hashes={str(p.relative_to(output)):E.bridge.sha(p) for p in output.iterdir() if p.is_file()}
        dump(output/'OUTPUT_SEAL.json',output_hashes);print('PASS',output,summary['actions'])
    except BaseException as err:
        if not (output/'RESULT.json').exists():dump(output/'RESULT.json',dict(status='FAILED',error=repr(err),traceback=traceback.format_exc(),elapsed=time.monotonic()-begin))
        print(traceback.format_exc());raise
if __name__=='__main__':run()
