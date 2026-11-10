"""Fixed synthetic, two independent conditional slices, and <=71-session prefix QA.
No continuation after 2022-04-18, no full diagnostic economic run.
"""
from pathlib import Path
from decimal import Decimal as D
import sys,json,copy,time,types,traceback,pickle,tempfile
import union_bridge_v1 as U
import run_diagnostic_v1 as RUN
HERE=Path(__file__).resolve().parent;B=HERE.parent
C=U.C

def save(out,name,v):RUN.save(out,name,v)
def normalized(x):return json.loads(json.dumps(x,default=str))
def cat(s):return copy.deepcopy({k:getattr(s,k) for k in ('EVENTS','EVENT_BY_ID','EVENT_AT','BY_RECORD','BY_EX','BY_PAY','ALLOWED_EVENT_IDS')})
def restore(s,c):
    for k,v in copy.deepcopy(c).items():setattr(s,k,v)
def main():
    label=sys.argv[1]
    if not label.startswith('qa_attempt_') or not label[11:].isdigit():raise ValueError('Only new QA attempt label')
    out=HERE/label;out.mkdir(exist_ok=False);start=time.monotonic();results=[]
    save(out,'START.json',dict(start_utc=time.time(),fixed_prefix_end='2022-04-18',diagnostic_economic_runs=0))
    try:
        import test_known_halt_v1 as H
        import test_candidate_v1 as T
        s=U.bridge.load_original('2022');a=H.suite(s);save(out,'LEGACY_20.json',a)
        s=U.bridge.load_original('2022');a=T.suite(s);save(out,'CANDIDATE_26.json',a)
        s=U.bridge.load_original('2022');original=cat(s);catalog=json.loads(U.CATALOG.read_text());c=catalog['distributions'][0]
        def passed(name,detail=None):results.append(dict(name=name,status='PASS',detail=detail))
        tape=U.UnionTape(s,[c]);before=U.digest(original['EVENTS'])
        for day,expected in [('2022-05-05',436),('2022-05-06',437),('2022-05-11',437),('2022-05-12',437),('2022-05-13',437)]:
            tape.project(s.pd.Timestamp(day),'OPEN')
            assert len(s.EVENTS)==expected and len(s.EVENT_BY_ID)==expected
            assert U.digest(s.EVENTS[:436])==before
            for k in ('EVENT_BY_ID','EVENT_AT'):
                for key,v in original[k].items():assert getattr(s,k)[key]==v
            for k in ('BY_RECORD','BY_EX','BY_PAY'):
                for key,v in original[k].items():assert getattr(s,k)[key][:len(v)]==v
            assert {x['economic_event_id'] for x in original['EVENTS']}<=s.ALLOWED_EVENT_IDS
            if day<'2022-05-12':assert ('600403.SH',s.pd.Timestamp('2022-05-12')) not in s.EVENT_AT
        assert len(s.EVENT_AT)==437
        coordinate=[x for x in s.EVENTS if x['origin']=='ENTRY10_COORDINATE_ONLY']
        assert len(coordinate)==10 and all(not x['entitlement_verified'] and x['d_cash'] is None and x['pay_date'] is None for x in coordinate)
        passed('all_six_union_views_preserve_436_bytes_and_10_coordinate_only_permissions',dict(original_digest=before,event_count=437))
        restore(s,original);s.ALLOWED_EVENT_IDS={original['EVENTS'][0]['economic_event_id']};tape=U.UnionTape(s,[c]);tape.project(s.pd.Timestamp('2022-05-06'),'OPEN')
        assert s.ALLOWED_EVENT_IDS=={original['EVENTS'][0]['economic_event_id'],C.EID};passed('restricted_legacy_allowed_set_not_broadened')
        restore(s,original)
        cases=[[c,c],[dict(c,economic_event_id=original['EVENTS'][0]['economic_event_id'])],
            [dict(c,sid=original['EVENTS'][0]['sid'],ex_date=str(original['EVENTS'][0]['ex_date'].date()))],
            [c,dict(c,economic_event_id='OTHER')]]
        for bad in cases:
            try:U.UnionTape(s,bad)
            except ValueError:pass
            else:raise AssertionError('collision accepted')
        passed('duplicate_ID_and_same_sid_ex_collisions_rejected')
        class NoFuture:
            def get(self,*a,**k):raise AssertionError('pre-ex future coordinate read')
        raw=s.raw; s.raw={c['sid']:NoFuture()}
        try:
            tape=U.UnionTape(s,[c]);assert not tape.project(s.pd.Timestamp('2022-05-05'),'CLOSE')
            visible=tape.project(s.pd.Timestamp('2022-05-06'),'OPEN');assert len(visible)==1 and not any(k in visible[0] for k in ('factor_old','factor_new','previous_close','previous_day'))
        finally:s.raw=raw
        passed('May5_closed_gate_May6_announcement_has_no_future_market_fields')
        restore(s,original);h=U.UnionHalts()
        assert h.get('600595.SH',s.pd.Timestamp('2022-01-13')) and h.get('600403.SH',s.pd.Timestamp('2022-04-15'))
        for sid,day in [('600595.SH','2022-01-14'),('600403.SH','2022-04-18'),('000001.SZ','2022-04-15')]:assert h.get(sid,s.pd.Timestamp(day)) is None
        passed('two_exact_halt_sessions_coexist_no_extension')
        # Native fixture with actual union adapter, original full catalog and no new
        # synthetic candidate until explicitly installed. Old events remain present.
        import test_execution_indexed as F
        class TestBridge(U.ExecutionBridge):
            def __init__(self,*a,**kw):super().__init__(*a,candidates=[],synthetic_candidates=True,**kw)
        F.E=types.SimpleNamespace(**dict(U.native.__dict__,ExecutionBridge=TestBridge))
        def fixture():
            restore(s,original);b,st,ds=F.fixture(s);s.local_actions=lambda sid:{'events':[]};return b,st,ds
        b,st,ds=fixture();b.open_phase(ds[1]);b.close_phase(ds[1]);st['addpending']=None;b.pending_cp.clear()
        old_event=dict(s.EVENTS[0],sid=F.SID,economic_event_id='SYNTHETIC_OLD_CLAIM',record_date=ds[1],coordinate_snapshot_day=ds[1],ex_date=ds[2],pay_date=ds[3],d_cash=D(1),d_source=D(0),entitlement_verified=True)
        s.EVENTS=[old_event];s.EVENT_BY_ID={old_event['economic_event_id']:old_event};s.EVENT_AT={};s.BY_RECORD={ds[1]:[old_event]};s.BY_EX={ds[2]:[old_event]};s.BY_PAY={ds[3]:[old_event]};s.ALLOWED_EVENT_IDS=None
        b.union_tape=U.UnionTape(s,[],synthetic=True);b.union_tape.project(ds[1],'CLOSE');s.register(b.states,U.ARM,ds[1]);claim=next(iter(s.claims.values()));rid=st['round_id'];st['exitpending']='SYNTHETIC_OLD_EXIT'
        b.open_phase(ds[2]);assert st['core']==0 and st['receivable']==D(160) and F.SID not in b.states
        b.close_phase(ds[2]);b.open_phase(ds[3]);b.close_phase(ds[3]);assert claim['owner_round_id']==rid and claim['settled'] and st['dividend_paid']==D(160)
        passed('old_round_registered_claim_accrues_and_pays_after_execution_close')
        b,st,ds=fixture();s.raw[F.SID].pop(ds[1]);b.open_phase(ds[1]);assert b.states[F.SID]['state']=='UNKNOWN' and not U.blocking_unknowns(b,ds[1],'OPEN')
        passed('never_filled_zero_responsibility_UNKNOWN_exempt')
        st['receivable']=D(1);assert U.blocking_unknowns(b,ds[1],'OPEN');st['receivable']=D(0)
        s.claims['test']={'owner_round_id':st['round_id'],'settled':False};assert U.blocking_unknowns(b,ds[1],'OPEN');s.claims['test']['settled']=True;assert not U.blocking_unknowns(b,ds[1],'OPEN')
        st['exitpending']='PENDING';assert U.blocking_unknowns(b,ds[1],'OPEN');st['exitpending']=None
        passed('zero_qty_unsettled_claim_receivable_pending_sell_stop_but_settled_claim_alone_not')
        b,st,ds=fixture();b.open_phase(ds[1]);b.close_phase(ds[1]);s.raw[F.SID].pop(ds[2]);b.open_phase(ds[2]);assert U.blocking_unknowns(b,ds[2],'OPEN') and b.last_open==ds[2] and not b._live_orders()
        passed('ordinary_missing_price_stops_only_after_complete_OPEN')
        # Report must not observe stopping-day CLOSE after OPEN; full runtime retains
        # aliases and all orders, layer identities, CP cache and union maps.
        rpt=RUN.report_closed(b,ds[2],'OPEN');assert all(x['whole_round_NET80'] is None for x in rpt['rounds'] if x['terminal_qty'])
        rt=b.capture_runtime();rr=pickle.loads(pickle.dumps(rt));assert rr['own']['states'][F.SID]==b.states[F.SID] and rr['source']['archives'][st['round_id']]==st
        assert {'runtime_catalog','candidate_audit','cp_cache','meta','loaded_sids'}<=rr['union'].keys()
        passed('OPEN_report_no_future_CLOSE_and_lossless_full_runtime_roundtrip')
        checkdir=out/'checkpoint_fixture';checkdir.mkdir()
        RUN.checkpoint(b,checkdir,ds[2],'OPEN',[],U.blocking_unknowns(b,ds[2],'OPEN'),'SYNTHETIC_CHECKPOINT_TEST')
        assert (checkdir/'CHECKPOINT.pkl').exists() and json.loads((checkdir/'CHECKPOINT_INDEX.json').read_text())['checkpoint_roundtrip_identity_pass']
        passed('complete_checkpoint_writer_roundtrips_unknown_lightweight_state_and_dated_fees')
        b.states['SYNTH_MISSING']={'state':'UNKNOWN','round_id':'MISSING_ARCHIVE','unknown_reason':'SYNTHETIC'}
        try:U.blocking_unknowns(b,ds[2],'OPEN')
        except U.native.StateInvariantError:pass
        else:raise AssertionError('missing archive responsibility silently exempted')
        b.states.pop('SYNTH_MISSING')
        assert RUN.source_row_at_phase(dict(raw_open=10,adjustment_factor=1,raw_close=99,raw_volume=999,amount=888,all_day_status='FUTURE'),True,'OPEN')==dict(raw_open=10,adjustment_factor=1)
        passed('missing_archive_fails_closed_and_OPEN_source_evidence_whitelist_excludes_all_day_fields')

        # Gate and durable lock tests do not create a release for the real folder.
        gate=out/'gate_fixture';gate.mkdir();RUN.claim_once(gate)
        try:RUN.claim_once(gate)
        except FileExistsError:pass
        else:raise AssertionError('second execution lock accepted')
        try:RUN.load_release(gate)
        except FileNotFoundError:pass
        else:raise AssertionError('missing release accepted')
        passed('single_O_EXCL_lock_and_missing_release_fail_closed')
        # Fixed-byte gate rejects stage or dependency mutation, independently of lock.
        save(gate,'RUN_CONTRACT.json',{'dependencies':{}})
        save(gate,'PRE_RUN_STAGE_SEAL.json',{'RUN_CONTRACT.json':U.sha(gate/'RUN_CONTRACT.json')})
        save(gate,'INDEPENDENT_REVIEW_RELEASE.json',dict(status='PASS',scope=RUN.SCOPE,reviewed_stage_sha256=U.sha(gate/'PRE_RUN_STAGE_SEAL.json'),synthetic_gate_test_only=True))
        RUN.load_release(gate)
        with (gate/'RUN_CONTRACT.json').open('a') as f:f.write(' ')
        try:RUN.load_release(gate)
        except ValueError:pass
        else:raise AssertionError('changed reviewed bytes accepted')
        passed('reviewed_byte_gate_detects_contract_tamper')
        for cfg,expected in [({'wall_seconds':.15,'peak_rss_bytes':6*1024**3},'HARD_WALL_BUDGET'),({'wall_seconds':10,'peak_rss_bytes':1},'HARD_RSS_BUDGET')]:
            child=RUN.subprocess.Popen(['/bin/sleep','10'],start_new_session=True)
            reason,rss=RUN.supervise(child,cfg,time.monotonic());assert reason==expected and child.returncode==-9
        passed('supervisor_hard_wall_and_RSS_kill_dummy_process_not_economic_run')
        b,st,ds=fixture();b.open_phase(ds[1]);b.close_phase(ds[1]);syn=T.event(ds)
        b.union_tape=U.UnionTape(s,[syn],synthetic=True);b.open_phase(ds[2]);b.close_phase(ds[2]);s.raw[F.SID][ds[3]]['adjustment_factor']=float(D(112)/D(111))
        saved=b.capture_runtime();baseline=b.open_phase(ds[3]);ledger=copy.deepcopy((s.actions,s.claims,s.bridges))
        b.restore_runtime(saved);s.raw[F.SID][ds[3]].update(raw_close=1e8,raw_high=1e8,raw_low=.00001,raw_volume=1e15)
        s.facts[F.SID][ds[3]]=dict(i_target=False,i_floor=1e8);s.cp[F.SID][ds[3]]=dict(receipt=True,candidate=1e8);s.sector[st['sector']][ds[3]]=-1
        polluted=b.open_phase(ds[3]);assert polluted==baseline and (s.actions,s.claims,s.bridges)==ledger
        passed('union_ex_OPEN_future_HLCV_I_CP_M3_pollution_invariant')
        save(out,'UNION_SYNTHETIC.json',results)
        # Re-execute the two finite independent fixtures through the union adapter.
        import run_bounded_v1 as S
        S.E=types.SimpleNamespace(**dict(C.__dict__,ExecutionBridge=U.ExecutionBridge))
        s=U.bridge.load_original('2022');original=cat(s)
        april=S.real_fixture(s,'APRIL',catalog);save(out,'APRIL_UNION_SLICE.json',april)
        restore(s,original);may=S.real_fixture(s,'MAY',catalog);save(out,'MAY_UNION_SLICE.json',may)
        del s
        # Only the fixed original-data prefix through April18; compare against the
        # already sealed 2022 recovery run, never run the full follow window.
        s=U.bridge.load_original('2022');b=U.ExecutionBridge(s,halt_evidence=U.UnionHalts());rows=[]
        olddir=B/'known_halt_contract_v1/cohort_2022_recovery_v2'
        olddays={r['day'][:10]:r for r in json.loads((olddir/'DAY_LEDGER.json').read_text())}
        days=s.cal[(s.cal>=s.pd.Timestamp('2022-01-04'))&(s.cal<=s.pd.Timestamp('2022-04-18'))]
        assert len(days)<75
        for n,d in enumerate(days):
            for phase in (('CLOSE',) if n==0 else ('OPEN','CLOSE')):
                r=b.open_phase(d)['reconciliation'] if phase=='OPEN' else b.close_phase(d)
                assert not U.blocking_unknowns(b,d,phase)
                oldrow=olddays[str(d.date())][phase]
                if str(d.date())<'2022-04-15':assert normalized(r)==oldrow,(d,phase,'prefix reconciliation drift')
                else:
                    for k in ('cash','receivable','live_rounds','layers','live_orders','unique_actions','cash_and_qty_reconciled'):assert normalized(r[k])==oldrow[k],(d,phase,k)
                rows.append(dict(day=d,phase=phase,reconciliation=r))
        oldactions=json.loads((olddir/'ACTIONS.json').read_text());expected=[a for a in oldactions if a['day']<='2022-04-18']
        assert normalized(s.actions)==expected
        assert b.last_valid_close[next(r for r,st in s.archives.items() if st['sid']=='600403.SH' and st.get('core',0)>0)]==s.pd.Timestamp('2022-04-18')
        save(out,'PREFIX_PHASES.json',rows);save(out,'PREFIX_ACTIONS.json',s.actions)
        save(out,'PREFIX_COMPARISON.json',dict(status='PASS',days=len(days),phases=len(rows),actions=len(s.actions),before_Apr15_all_reconciliations_equal=True,through_Apr18_cash_qty_transactions_equal=True,
            permitted_changes='April15 known halt/stale mark, April18 OPEN recovery lock and valid CLOSE; no new cash announcement before May6',fixed_cutoff='2022-04-18',not_diagnostic_economic_run=True))
        save(out,'SOURCE_HASHES.json',dict(s.hashes,**b.source_hashes))
        for p,h in dict(s.hashes,**b.source_hashes).items():assert U.sha(p)==h
        save(out,'RESULT.json',dict(status='AUTHOR_PASS_PENDING_INDEPENDENT_REVIEW',old_groups=20,candidate_groups=26,union_groups=len(results),independent_slices=2,prefix_sessions=len(days),new_diagnostic_economic_runs=0,seconds=time.monotonic()-start))
    except BaseException:
        save(out,'FAILURE.json',dict(traceback=traceback.format_exc(),seconds=time.monotonic()-start));raise
    finally:save(out,'OUTPUT_SEAL.json',{p.name:U.sha(p) for p in out.iterdir() if p.is_file()})
if __name__=='__main__':main()
