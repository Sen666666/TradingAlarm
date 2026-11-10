"""Fixed synthetic + two independent real-daily conditional fixtures ONLY."""
from pathlib import Path
from decimal import Decimal as D
import sys,copy,json,traceback,time,re,hashlib
import candidate_bridge_v1 as E
import test_candidate_v1 as T
HERE=Path(__file__).resolve().parent;R=HERE.parent.parent
SID='600403.SH'
def save(out,name,x):
    with (out/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def real_fixture(s,which,catalog):
    halt=E.HaltEvidence(catalog['halts'])
    b=E.ExecutionBridge(s,evidence_domain='REAL_DAILY_CONDITIONAL_FIXTURE',halt_evidence=halt,candidates=catalog['distributions'])
    b.groups={};s.load(SID)
    a=json.loads((R/'known_halt_600403_daily_audit_v1/ACCOUNT_EXTRACT.json').read_text());st=copy.deepcopy(a['archive']);st.pop('_output_index',None)
    for k,v in list(st.items()):
        if isinstance(v,str) and re.fullmatch(r'\d{4}-\d\d-\d\d(?: 00:00:00)?',v):st[k]=s.pd.Timestamp(v)
        elif isinstance(v,str):
            try:st[k]=D(v)
            except Exception:pass
    st['origin']=tuple(st['origin']);rid=st['round_id'];s.archives={rid:st};b.states={SID:st};s.actions=copy.deepcopy(a['actions'])
    b.action_ids={x['execution_action_id'] for x in s.actions};b.caps[rid]=D(a['round_report'][0]['Nd']);b.pools[rid]='confirmed'
    b.layers=[E.Layer(rid+'|CORE',rid,SID,'core',700,s.pd.Timestamp('2022-03-03'),D('3591.1100597504'),s.actions[0]['execution_action_id']),E.Layer(rid+'|ADD_CLOSED',rid,SID,'add',0,s.pd.Timestamp('2022-03-04'),D('23688.9355787645'),s.actions[1]['execution_action_id'])]
    assert st['core']==700 and st['add']==0 and st['added'] is True and st['addpending'] is None and not st['exitpending']
    if which=='APRIL':
        seed=s.pd.Timestamp('2022-04-14');b.last_close=seed;b.last_valid_close[rid]=seed;b._stage(seed,'CLOSE');b.daily_nav=b.snapshot(seed,'CLOSE').nav
        initial=b.reconcile(seed,'CLOSE');days=[s.pd.Timestamp(x) for x in ['2022-04-15','2022-04-18']]
    else:
        # Independent conditional state assumed at May10. No April->May loop.
        seed=s.pd.Timestamp('2022-05-10');b.last_close=s.pd.Timestamp('2022-05-09');b.last_valid_close[rid]=b.last_close
        initial=b.close_phase(seed);days=[s.pd.Timestamp(x) for x in ['2022-05-11','2022-05-12','2022-05-13']]
    rows=[dict(day=seed,phase='SEEDED_CLOSE' if which=='APRIL' else 'CONDITIONAL_SEED_CLOSE',reconciliation=initial,state=copy.deepcopy(b.states.get(SID)))]
    start_action_count=len(s.actions);cash=b.cash();daily_source=[]
    for day in days:
        rr=s.raw[SID].get(day,{});daily_source.append(dict(day=day,raw={k:rr.get(k) for k in ('raw_open','raw_close','adjustment_factor','source_kind','source_path','segment_id')},facts=s.facts[SID].get(day,{}),cp=s.cp[SID].get(day,{})))
        op=b.open_phase(day);rows.append(dict(day=day,phase='OPEN',result=copy.deepcopy(op),state=copy.deepcopy(b.states.get(SID)),claims=copy.deepcopy(list(s.claims.values()))))
        if which=='MAY' and str(day.date())=='2022-05-12':
            assert b.cash()==cash and b.receivable()==D('196');assert len(s.bridges)==1 and s.bridges[0]['record_q']==700 and s.bridges[0]['core_record_q']==700
            assert st['core']==700 and st['add']==0 and st['added'] and not st['addpending']
        cl=b.close_phase(day);rows.append(dict(day=day,phase='CLOSE',result=copy.deepcopy(cl),state=copy.deepcopy(b.states.get(SID)),claims=copy.deepcopy(list(s.claims.values()))))
    assert len(s.actions)==start_action_count and not any(x['type']=='PROMOTED' for x in b.audit)
    if which=='APRIL':
        assert rows[1]['state']['state']==E.HALT and rows[1]['result']['reconciliation']['NAV'] is None
        assert rows[2]['result']['NAV'] is None and not rows[3]['result']['reconciliation']['certified']
        assert rows[-1]['result']['certified'] and not b.risk_recovery_pending
        assert st['core']==700 and st['add']==0 and st['added'] and not s.claims
    else:
        assert len(s.claims)==1 and b.cash()==cash+D('196') and b.receivable()==0
        c=next(iter(s.claims.values()));assert c['record_q']==c['core_record_q']==700 and c['amount']==c['core_amount']==D('196') and c['settled']
        assert s.claim_ledger[-1]['available_from']==s.pd.Timestamp('2022-05-13')
        for row in rows:
            state=row.get('state') or {};assert state.get('add',0)==0 and state.get('added',True)
    return dict(name=which,status='AUTHOR_PASS_CONDITIONAL_FIXTURE_ONLY',not_real_account_path=True,seed_cash_assumption='1200000 standalone fixture wallet, not recovered shared cash',seed_share_assumption='CORE700 ADD0, old ADD4500 closed; assumed May ownership not realized recovery',seed_round_cash='copied labeled historical single-round ledger',preexisting_actions_not_executed_here=start_action_count,new_actions=len(s.actions)-start_action_count,rows=rows,source_daily=daily_source,claims=list(s.claims.values()),registrations=s.registrations,claim_ledger=s.claim_ledger,equity_bridges=s.bridges,adapter_audit=b.candidate_tape.audit,execution_audit=b.audit,source_hashes=dict(s.hashes,**b.source_hashes))

def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'qa_attempt_01'
    if not re.fullmatch(r'qa_attempt_\d\d',label):raise ValueError('Only a new QA attempt directory label is accepted, never dates/range/cohort')
    out=HERE/label;out.mkdir(exist_ok=False);start=time.monotonic()
    save(out,'START.json',dict(scope='SYNTHETIC_PLUS_TWO_INDEPENDENT_CONDITIONAL_DAILY_FIXTURES',no_full_window=True,no_account_recovery=True,no_minute_data=True,code_hashes={str(p):E.sha(p) for p in HERE.glob('*.py')}))
    try:
        s=E.bridge.load_original('2022');assert len(s.EVENTS)==436 and E.EID not in s.EVENT_BY_ID
        original_events_hash=E.digest(s.EVENTS);original_ids=[e['economic_event_id'] for e in s.EVENTS]
        # Baseline source-definition regression, unchanged imported test code.
        sys.path.insert(0,str(E.HERE.parent/'known_halt_contract_v1'));import test_known_halt_v1 as legacy
        a=legacy.suite(s);save(out,'BASELINE_HALT_REGRESSION.json',a)
        b=T.suite(s);save(out,'CANDIDATE_SYNTHETIC.json',b)
        del s
        catalog=json.loads((HERE/'CANDIDATES_V1.json').read_text())
        s=E.bridge.load_original('2022');s.load(SID)
        tape=E.CandidateTape(s,catalog['distributions']);c=catalog['distributions'][0]
        may5=tape.announcement(c,s.pd.Timestamp('2022-05-05'));may6=tape.announcement(c,s.pd.Timestamp('2022-05-06'))
        assert may5 is None and may6 is not None and 'factor_new' not in may6
        # No coordinate data are included in the public May6 announcement.
        gate=dict(May5=may5,May6=may6,original_event_count=len(original_ids),candidate_union_count=len(original_ids)+1,original_catalog_hash=original_events_hash,original_event_ids=original_ids,candidate_id=E.EID,not_PIT=True)
        save(out,'CANDIDATE_GATE_AND_CATALOG.json',gate)
        april=real_fixture(s,'APRIL',catalog);save(out,'APRIL_14_18_CONDITIONAL_FIXTURE.json',april)
        may=real_fixture(s,'MAY',catalog);save(out,'MAY_10_13_CONDITIONAL_FIXTURE.json',may)
        assert E.digest(s.EVENTS)==original_events_hash
        expected=D('2.184501833556971')*D('5.13')/(D('5.13')-D('.35'));actual=D(str(s.raw[SID].get(s.pd.Timestamp('2022-05-12'),{})['adjustment_factor']))
        assert abs(expected/actual-1)<=D('1e-11')
        save(out,'FACTOR_RECONCILIATION.json',dict(known_only_at='2022-05-12 OPEN native coordinate check, not May6 public eligibility',factor_old='2.184501833556971',previous_close='5.13',d_source='.35',predicted_factor=expected,native_factor=actual,relative_gap=abs(expected/actual-1),tolerance='1e-11',conditional_registered_q=700,gross_if_q700=D(700)*D('.35'),NET80_if_q700=D(700)*D('.35')*D('.8')))
        # Artifact tampering is rejected before use (no on-disk tampering).
        bad=copy.deepcopy(catalog['halts']);bad[0]['clock']['artifacts'][0]['sha256']='0'*64
        try:E.HaltEvidence(bad)
        except ValueError:pass
        else:raise AssertionError('changed evidence hash accepted')
        protected=json.loads((HERE/'PROTECTED_INPUT_HASHES_BEFORE.json').read_text());after={p:E.sha(p) for p in protected};assert after==protected
        for p,h in dict(april['source_hashes'],**may['source_hashes']).items():assert E.sha(p)==h
        save(out,'PROTECTED_INPUTS_UNCHANGED.json',dict(unchanged=True,count=len(protected),before=protected,after=after))
        save(out,'RESULT.json',dict(status='AUTHOR_PASS_INDEPENDENT_REVIEW_PENDING',baseline_halt_tests=len(a),candidate_synthetic_tests=len(b),real_daily_fixture_windows=2,new_account_runs=0,new_account_recovery_paths=0,new_real_actions=0,no_full_window=True,source_hashes_unchanged=True,seconds=time.monotonic()-start))
        print('PASS',out,flush=True)
    except BaseException:
        save(out,'FAILURE.json',dict(error=traceback.format_exc(),seconds=time.monotonic()-start));raise
    finally:save(out,'OUTPUT_HASHES.json',{p.name:E.sha(p) for p in out.iterdir() if p.is_file()})
if __name__=='__main__':main()
