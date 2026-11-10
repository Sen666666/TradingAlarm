"""Bounded original June22 prefix and one fixed June23 entitlement fixture.
Not an annual economic run or lock claim. Every fixture restores the saved prefix.
"""
from pathlib import Path
from decimal import Decimal as D
import copy,json,sys,time,traceback,resource,types
import compound_bridge_v1 as E
import report_compound_halt_v1 as REPORT
HERE=Path(__file__).resolve().parent;B=HERE.parent
OLD=B/'annual_2022_marked_nav_v1/economic_run_2022_annual_once'
def save(out,name,obj):
    p=out/name
    with p.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def norm(x):return json.loads(json.dumps(x,default=str))
def main():
    label=sys.argv[1]
    if not label.startswith('qa_attempt_') or not label[11:].isdigit():raise ValueError('Fresh QA label required')
    out=HERE/label;out.mkdir(exist_ok=False);start=time.monotonic();checks=[]
    def passed(name,detail=None):
        checks.append(dict(name=name,status='PASS',detail=detail));print('PASS',name,flush=True)
    protected=json.loads((B/'annual_2022_marked_nav_v1/PROTECTED_OLD_INPUTS.json').read_text())
    oldoutputs={str(p):E.sha(p) for p in OLD.iterdir() if p.is_file()}
    try:
        bundle,policy,hashes=E.verify_fixed_facts()
        assert bundle['maximum_distinct_economic_events']==442
        for c in bundle['new_pure_cash']+bundle['new_compound']:
            assert not any(k in c for k in ('factor_old','factor_new','previous_close','previous_day'))
        passed('independent_fact_release_exact_hashes_policy_and_437_plus_5_domain')
        gate=out/'sealed_member_gate';gate.mkdir();member=gate/'facts.json';member.write_text('{"fact":1}\\n')
        sealed=gate/'FINAL_SEAL.json';sealed.write_text(json.dumps({'file_sha256':{'facts.json':E.sha(member)}}))
        old_seal_hash=E.sha(sealed)
        assert len(E.verify_sealed_members(sealed,old_seal_hash))==1
        member.write_text('{"fact":2}\\n');assert E.sha(sealed)==old_seal_hash
        try:E.verify_sealed_members(sealed,old_seal_hash)
        except ValueError as error:assert 'member drift' in str(error)
        else:raise AssertionError('Untouched seal accepted changed fact member')
        passed('unchanged_seal_changed_one_member_byte_rejected_before_account_build')
        import pandas as pd
        typed={pd.Timestamp('2022-06-22'):'timestamp', '2022-06-22 00:00:00':'text', ('x',1):D('1.00')}
        assert E.structural_digest(typed)==E.structural_digest(copy.deepcopy(typed))
        assert E.structural_digest({pd.Timestamp('2022-06-22'):1})!=E.structural_digest({'2022-06-22 00:00:00':1})
        assert E.structural_digest({('x',1):1})!=E.structural_digest({str(('x',1)):1})
        assert E.structural_digest({1,2,3})==E.structural_digest({3,2,1})
        assert E.structural_digest(D('1.00'))!=E.structural_digest(D('1'))
        assert E.structural_digest({'a':1,'b':2})!=E.structural_digest({'b':2,'a':1})
        passed('typed_timestamp_string_tuple_set_decimal_keys_no_collision_dictionary_order_preserved')


        s=E.bridge.load_original('2022');b=E.ExecutionBridge(s,halt_evidence=E.AnnualHalts())
        oldrows=json.loads((OLD/'PHASE_LEDGER.json').read_text())
        oldactions=json.loads((OLD/'ACTIONS.json').read_text())
        prefix=[r for r in oldrows if r['day'][:10]<='2022-06-22']
        expected_actions=[a for a in oldactions if a['day']<='2022-06-22']
        assert len(prefix)==221 and len(expected_actions)==253
        days=s.cal[(s.cal>=s.pd.Timestamp('2022-01-04'))&(s.cal<=s.pd.Timestamp('2022-06-22'))];rows=[]
        for n,day in enumerate(days):
            for phase in (('CLOSE',) if n==0 else ('OPEN','CLOSE')):
                rec=b.open_phase(day)['reconciliation'] if phase=='OPEN' else b.close_phase(day)
                old=prefix[len(rows)]
                assert norm(rec)==old['reconciliation'],(str(day),phase,'economic reconciliation mismatch',norm(rec),old['reconciliation'])
                assert len(s.actions)==old['actions'] and len(s.archives)==old['archives']
                assert not E.blocking_unknowns(b,day,phase)
                rows.append(dict(day=day,phase=phase,reconciliation=rec,actions=len(s.actions),archives=len(s.archives)))
        assert norm(s.actions)==expected_actions and len(rows)==221 and len(s.actions)==253
        assert b.research_tax_total()==0 and not b.share_ledger and not b.research_tax_ledger
        save(out,'PREFIX_PHASES.json',rows);save(out,'PREFIX_ACTIONS.json',s.actions)
        passed('221_original_economic_phases_and_253_actions_exact_through_June22',
               dict(phases=221,actions=253,resource_fields_excluded=True,extra_fact_registration_separate=True))
        sid='000987.SZ';st=b.states[sid];rid=st['round_id'];day=s.pd.Timestamp('2022-06-23')
        assert rid=='2022|A_UNION_B_SHARED_ENGINEERING_V1|000987.SZ|2'
        assert st['core']==300 and st['add']==0 and st['spent']==D('2796.614682786500')
        saved=b.capture_runtime();snapshot_signature=E.structural_digest(saved)
        import pickle
        with (out/'PREFIX_CHECKPOINT.pkl').open('xb') as f:pickle.dump(saved,f,protocol=5)
        with (out/'PREFIX_CHECKPOINT.pkl').open('rb') as f:loaded=pickle.load(f)
        assert E.structural_digest(loaded)==snapshot_signature
        for key,state in loaded['own']['states'].items():
            if b.states[key] is s.archives[state['round_id']]:
                assert state is loaded['source']['archives'][state['round_id']]
        passed('ex_before_pickle_actual_round_archive_shared_identity_preserved')

        def restore():
            b.restore_runtime(saved)
            assert E.structural_digest(b.capture_runtime())==snapshot_signature
            return b.states[sid]
        original_layers=[(x.layer_id,x.qty,x.cost,x.opened,x.first_fill_id) for x in b.layers if x.round_id==rid]
        original_cp=copy.deepcopy((b.pending_cp,b.cp_attempts,b.promotion_seen))
        original_identity={k:copy.deepcopy(st.get(k)) for k in ('spent','fees','initial_fee','added','added_q','add_attempts','entry_day','exitpending','addexitpending','addpending','addfloor')}
        cash_before=b.cash()
        b._stage(day,'OPEN')
        raw=s.raw[sid].get(day);prior=s.raw[sid].get(s.pd.Timestamp('2022-06-22'))
        assert D(str(raw['raw_open']))==D('6.7') and D(str(prior['raw_close']))==D('9.39')
        p=b._prepare_compound(st,day)
        assert p['stock_reserve_total']==D(21) and p['updates'][0]['new_q']==105
        assert p['cash_claim']['amount']==D(48)
        pure_arithmetic=D(405)*D('6.7')+D(48)-D('2796.614682786500')-D(21)
        assert pure_arithmetic==D('-56.114682786500')
        b._compound_open_preamble(day)
        assert st['core']==405 and st['add']==0 and st['receivable']==48
        assert b.cash()==cash_before-21 and st['cash']==-D('2796.614682786500')-21
        assert b.research_tax_total()==21 and len(b.research_tax_ledger)==1 and len(b.share_ledger)==1
        assert original_cp==(b.pending_cp,b.cp_attempts,b.promotion_seen)
        for k in ('spent','fees','initial_fee','added','added_q','add_attempts','entry_day','exitpending','addexitpending'):
            assert st.get(k)==original_identity[k],k
        _,fs,pa=s.getmeta(sid,day)
        at_raw=s.mark(st,D('6.7'),day);sell_fee=s.fee(405,D('6.7'),fs,'sell',pa)
        assert at_raw==pure_arithmetic-sell_fee and at_raw<0
        proxy_price=D('6.7')*(1-s.SLIP);proxy_fee=s.fee(405,proxy_price,fs,'sell',pa)
        assert s.mark(st,proxy_price,day)==st['cash']+st['receivable']+D(405)*proxy_price-proxy_fee
        actual_layer=next(x for x in b.layers if x.round_id==rid and x.kind=='core')
        assert actual_layer.cost==D('2796.614682786500') and actual_layer.opened==s.pd.Timestamp('2022-06-17')
        for k in ('addfloor','addpending'):
            if original_identity[k] is not None:
                assert st[k]==D(str(original_identity[k]))*D(str(prior['adjustment_factor']))/D(str(raw['adjustment_factor']))
        fixture=dict(round_id=rid,record_q=300,new_q=105,current_q=405,prior_raw_close=prior['raw_close'],
          actual_raw_open=raw['raw_open'],buy_cost=st['spent'],research_stock_haircut=21,cash_NET80_receivable=48,
          before_hypothetical_sell_fee=pure_arithmetic,native_raw_mark=at_raw,native_raw_sell_fee=sell_fee,
          native_5bp_sell_mark=s.mark(st,proxy_price,day),native_5bp_sell_fee=proxy_fee,
          global_cash_delta=b.cash()-cash_before,CP_identity_and_ADD_state_preserved=True,not_account_run_result=True)
        save(out,'FIXED_000987_EX_OPEN.json',fixture)
        passed('fixed_000987_actual_record_source_and_nonrefundable21_once_no_phantom_profit',fixture)
        # Force a synthetic exit intent on the same fixed position. Never run selection or a new annual phase.
        before_action=len(s.actions);st['exitpending']='FIXTURE_ONLY_ORIGINAL_I_EXIT'
        b._callback('source_exit_only')(b.states,sid,st,day,b.last_close)
        b._record_new_actions(before_action,day)
        assert len(s.actions)==before_action+1 and s.actions[-1]['q']==405
        assert s.actions[-1]['side']=='sell_all' and st['core']==0
        assert st['cash']==-D('2796.614682786500')-21+D(405)*proxy_price-proxy_fee
        assert st['fees']==original_identity['fees']+proxy_fee and st['spent']==original_identity['spent']
        # Original pay CLOSE, not same-day OPEN spend, then isolate the one-round report.
        before_pay=b.cash();s.pay_day(E.ARM,day);s.finalize()
        assert b.cash()==before_pay+48 and st['receivable']==0 and st['dividend_paid']==48
        target_actions=[x for x in s.actions if x['round_id']==rid]
        target_shares=copy.deepcopy(b.share_ledger)
        for x in target_shares:
            x['action_index']=sum(a['round_id']==rid for a in s.actions[:x['action_index']])
        proxy=copy.copy(b);source=types.SimpleNamespace(**s.__dict__)
        source.actions=target_actions;source.archives={rid:st};source.claims={k:v for k,v in s.claims.items() if v['owner_round_id']==rid}
        proxy.s=source;proxy.share_ledger=target_shares
        rep=REPORT.reports(proxy,day)
        assert len(rep['rounds'])==1 and rep['rounds'][0]['status']=='EXECUTION_AND_SETTLEMENT_CLOSED'
        assert rep['rounds'][0]['whole_round_NET80']==st['cash'] and rep['rounds'][0]['research_stock_tax_total']==21
        assert rep['layers'][0]['research_stock_tax']==21
        assert sum(x['exact_whole_order_fee'] for x in rep['exact_trade_journal'])==st['fees']
        assert rep['exact_trade_journal'][0]['q']==300 and rep['exact_trade_journal'][1]['q']==405
        assert rep['layers'][0]['buy_cash']==D('2796.614682786500')
        save(out,'FIXED_000987_EXIT_REPORT.json',rep)
        passed('same_fixed_405_full_odd_exit_actual_dated_fee_once_and_report_cash_qty_tax_closure')
        restore();st=b.states[sid];b._stage(day,'OPEN')
        # Prove pending receivable cannot fund tax: retain actual settled cash 20, add huge receivable.
        b.seed_cash-=b.cash()-D(20);st['receivable']+=D(1000000)
        before=(st['core'],st['add'],st['cash'],len(b.share_ledger),b.research_tax_total())
        b._compound_open_preamble(day)
        assert b.states[sid]['state']=='UNKNOWN' and b.states[sid]['unknown_reason']=='INSUFFICIENT_SETTLED_CASH_FOR_RESEARCH_HAIRCUT'
        assert before==(st['core'],st['add'],st['cash'],len(b.share_ledger),b.research_tax_total())
        assert not s.claims[('2022',E.ARM,sid,E.COMPOUND_ID)]['recognized']
        passed('insufficient_settled_cash_no_receivable_funding_no_half_share_or_tax_or_cash_claim')
        restore();st=b.states[sid];b._stage(day,'OPEN');before=E.structural_digest(b.capture_runtime())
        accrue=b._native_accrue_day
        def fail_after_accrual(*args):
            accrue(*args);raise RuntimeError('SYNTHETIC_FAILURE_AFTER_NATIVE_ACCRUAL')
        b._native_accrue_day=fail_after_accrual
        try:
            try:b._compound_open_preamble(day)
            except RuntimeError as error:assert str(error)=='SYNTHETIC_FAILURE_AFTER_NATIVE_ACCRUAL'
            else:raise AssertionError('Expected synthetic transaction failure')
        finally:b._native_accrue_day=accrue
        assert E.structural_digest(b.capture_runtime())==before
        passed('unexpected_post_accrual_failure_rolls_back_cash_qty_claims_tax_and_identity')
        restore()
        assert E.structural_digest(b.capture_runtime())==snapshot_signature and b.research_tax_total()==0
        save(out,'SOURCE_HASHES.json',E.merge_hashes(s.hashes,b.source_hashes))
        # Real dependency intersections, not empty dictionaries.
        deps=json.loads((B/'annual_2022_marked_nav_v1/RUN_CONTRACT.json').read_text())['dependencies']
        merged=E.merge_hashes(s.hashes,b.source_hashes,deps)
        overlap=set(b.source_hashes)&set(deps);assert overlap
        key=next(iter(overlap))
        try:E.merge_hashes(b.source_hashes,{key:'0'*64})
        except ValueError:pass
        else:raise AssertionError('Conflicting duplicate hash accepted')
        for path,h in merged.items():assert E.sha(path)==h,path
        save(out,'ACTUAL_MERGE_CHECK.json',dict(merged_count=len(merged),intersection_count=len(overlap),conflicting_hash_rejected=True))
        passed('actual_source_contract_merge_same_value_and_conflict_rejection')
        for p,h in protected.items():assert E.sha(p)==h,p
        for p,h in oldoutputs.items():assert E.sha(p)==h,p
        save(out,'CHECKS.json',checks)
        save(out,'RESULT.json',dict(status='AUTHOR_QA_PASS_PENDING_INDEPENDENT_REVIEW',checks=len(checks),
             prefix_phases=221,prefix_actions=253,fixture_scope='One fixed 000987 registration/ex/forced-synthetic-intent exit/report; restored exactly.',
             real_annual_runs=0,old_protected=len(protected),old_output_files=len(oldoutputs),old_bytes_unchanged=True,
             elapsed_seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        print('PREPARATION_DONE',flush=True)
    except BaseException:
        save(out,'FAILURE.json',dict(traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-start))
        raise
    finally:save(out,'OUTPUT_SEAL.json',{p.name:E.sha(p) for p in out.iterdir() if p.is_file()})
if __name__=='__main__':main()
