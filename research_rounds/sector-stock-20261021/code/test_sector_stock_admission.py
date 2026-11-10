"""Synthetic boundary tests for a pure adapter; no account simulation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import itertools
import math
import unittest

from sector_stock_admission import (Clock, Fact, Rank, Sector, Security, Occupancy,
                                    Memory, ExitCompletion, decide, eligibility, rs_score)

UTC = timezone.utc
D = datetime(2020, 1, 2, 9, tzinfo=UTC)
C = Clock(D, D + timedelta(hours=23), D.date())


def fact(value, **kw):
    return Fact(value, D-timedelta(days=10), D-timedelta(days=10), source_id='synthetic', **kw)


def rank(value, at=D):
    return Rank(value, at, at)


def sector(sid, up=True, rs=0.5):
    return Sector(sid, fact(up), rank(rs))


def stock(sid, group='G1', issuer=None, rs=.5, up=True, buy=True, cap=20e9, ready=True):
    return Security(sid, fact(issuer or sid), fact(group), fact(ready), fact(buy),
                    fact(cap), fact(up), rank(rs))


def occ(sid, group='G1', issuer=None, **flags):
    return Occupancy(sid, issuer or sid, group, D, **(flags or {'has_position': True}))


def run(stocks, groups=None, variant='S0', **kw):
    return decide(clock=kw.pop('clock', C), variant=variant, securities=stocks,
                  sectors=groups or [sector('G1')], bootstrap=kw.pop('bootstrap', True), **kw)


class AdmissionTests(unittest.TestCase):
    def test_three_variant_gate(self):
        s=[stock('A')];g=[sector('G1', up=False)]
        self.assertEqual(run(s,g,'T0').selected, ('A',))
        self.assertEqual(run(s,g,'T1').selected, ())
        self.assertEqual(run(s,g,'S0').selected, ())

    def test_common_coverage_no_T0_expansion(self):
        for v in ('T0','T1','S0'):
            self.assertEqual(run([stock('A',ready=False)],variant=v).selected, ())
            self.assertIsNone(run([stock('A',ready=None)],variant=v).eligibility[0].q)

    def test_cap_strict_threshold_not_float_cap(self):
        self.assertFalse(run([stock('A',cap=10e9)]).eligibility[0].q)
        self.assertTrue(run([stock('A',cap=10e9+1)]).eligibility[0].q)
        self.assertIsNone(run([stock('A',cap=None)]).eligibility[0].q)

    def test_future_information_not_read(self):
        s=replace(stock('A'), company_cap_cny=replace(fact(20e9),known_at=D+timedelta(seconds=1)))
        self.assertIsNone(run([s]).eligibility[0].q)

    def test_announced_future_buy_change_execution_clock(self):
        s=replace(stock('A'),buy_allowed=replace(fact(False),valid_from=C.earliest_execution_at))
        self.assertFalse(run([s]).eligibility[0].q)
        s=replace(s,buy_allowed=replace(s.buy_allowed,known_at=D+timedelta(seconds=1)))
        self.assertIsNone(run([s]).eligibility[0].q)

    def test_snapshot_not_historical_membership(self):
        s=replace(stock('A'),sector_id=replace(fact('G1'),basis='snapshot',observed_at=D+timedelta(days=365)))
        self.assertIsNone(run([s]).eligibility[0].q)

    def test_snapshot_observed_after_decision_is_not_known_for_next_open(self):
        s=replace(stock('A'),sector_id=replace(fact('G1'),basis='snapshot',observed_at=D+timedelta(hours=1)))
        self.assertIsNone(run([s]).eligibility[0].q)
        self.assertEqual(run([s]).selected,())

    def test_unknown_not_forced_false(self):
        self.assertIsNone(run([stock('A',up=False,cap=None)]).eligibility[0].q)

    def test_current_RS_reorders_waiting(self):
        prev=(Memory('A',True,True,D-timedelta(days=5),'eligibility_rising_edge',as_of=D),
              Memory('B',True,True,D-timedelta(days=1),'eligibility_rising_edge',as_of=D))
        busy=[occ('X','G1'),occ('Y','G2'),occ('Z','G2'),occ('V','G3'),occ('W','G3')]
        result=run([stock('A',rs=.1),stock('B',rs=.9)],previous=prev,occupied=busy,bootstrap=False)
        self.assertEqual(result.selected,('B',))
        self.assertIn('A',result.waiting)

    def test_unknown_restore_keeps_candidate_identity(self):
        first=run([stock('A')]);prior=first.memories
        gap=run([stock('A',cap=None)],previous=prior,bootstrap=False)
        restored=run([stock('A')],previous=gap.memories,bootstrap=False,
                     clock=Clock(D+timedelta(days=1),D+timedelta(days=2),D.date()+timedelta(days=1)))
        self.assertEqual(restored.memories[0].created_at,prior[0].created_at)
        self.assertEqual(restored.memories[0].origin,'initial_carry_in')

    def test_unknown_then_true_without_prior_false_is_not_event(self):
        gap=run([stock('A',cap=None)],bootstrap=False)
        r=run([stock('A')],previous=gap.memories,bootstrap=False)
        self.assertEqual(r.selected,())
        self.assertFalse(r.memories[0].waiting)

    def test_false_unknown_true_is_real_eligibility_edge(self):
        a=run([stock('A',up=False)],bootstrap=False)
        b=run([stock('A',cap=None)],previous=a.memories,bootstrap=False)
        c=run([stock('A')],previous=b.memories,bootstrap=False)
        self.assertEqual(c.selected,('A',))
        self.assertEqual(c.memories[0].origin,'eligibility_rising_edge')

    def test_explicit_exit_reentry(self):
        r=run([stock('A')],previous=(Memory('A',True,False,as_of=D),),bootstrap=False,completed_exits=(ExitCompletion('A','exit-1',D),))
        self.assertEqual(r.selected,('A',))
        self.assertEqual(r.memories[0].origin,'completed_exit_reentry')
        with self.assertRaises(ValueError):
            run([stock('A')],occupied=[occ('A')],completed_exits=(ExitCompletion('A','exit-1',D),))

    def test_partial_priority_and_reserved_capacity(self):
        a=occ('A',partial_fill=True,pending_buy=True,has_position=True)
        b=occ('B',pending_buy=True)
        r=run([stock('A',rs=.01),stock('B',rs=.5),stock('C',rs=1)],occupied=[a,b])
        self.assertEqual(r.continue_buys,('A','B'))
        self.assertEqual(r.selected,())
        self.assertIn(('C','sector_issuer_slots_full'),r.rejected)

    def test_pending_before_first_fill_reranks_without_cancelling(self):
        r=run([stock('A',rs=.1),stock('B',rs=.9)],occupied=[occ('A',pending_buy=True),occ('B',pending_buy=True)])
        self.assertEqual(r.continue_buys,('B','A'))
        self.assertEqual(r.cancel_buys,())

    def test_sector_failure_cancels_remainder_not_holding(self):
        r=run([stock('A')],[sector('G1',up=False)],occupied=[occ('A',has_position=True,pending_buy=True,partial_fill=True)])
        self.assertEqual(r.cancel_buys,('A',))
        self.assertEqual(r.exit_requests,())
        self.assertEqual(r.continue_buys,())

    def test_unknown_pauses_pending_and_reserves_issuer(self):
        r=run([stock('A',cap=None),stock('H',issuer='A')],occupied=[occ('A',pending_buy=True)])
        self.assertEqual(r.pause_buys,('A',))
        self.assertEqual(r.selected,())
        self.assertIn(('H','issuer_already_occupied'),r.rejected)

    def test_missing_observation_pauses_not_cancel(self):
        r=run([],occupied=[occ('A',pending_buy=True)],previous=[Memory('A',True,True,D,'edge',as_of=D)],bootstrap=False)
        self.assertEqual(r.pause_buys,('A',));self.assertEqual(r.cancel_buys,())

    def test_stock_failure_latches_exit_and_recovery_does_not_release(self):
        o=occ('A',has_position=True,pending_buy=True,partial_fill=True)
        r=run([stock('A',up=False)],occupied=[o])
        self.assertEqual(r.exit_requests,('A',));self.assertEqual(r.cancel_buys,('A',))
        r=run([stock('A'),stock('H',issuer='A')],occupied=[replace(o,exit_latched=True,pending_buy=False,partial_fill=False)])
        self.assertEqual(r.exit_requests,('A',));self.assertEqual(r.selected,())

    def test_slot_limits_and_round_robin(self):
        gs=[sector('G'+str(i),rs=1/i) for i in range(1,5)]
        ss=[stock(f'{i}{j}',group='G'+str(i),rs=1/j) for i in range(1,5) for j in range(1,4)]
        r=run(ss,gs)
        self.assertEqual(r.selected,('11','21','31','12','22','32'))

    def test_T0_T1_global_priority_S0_sector_round_robin(self):
        gs=[sector('G1',rs=.9),sector('G2',rs=.1)]
        ss=[stock('A','G1',rs=.1),stock('B','G1',rs=.2),stock('C','G2',rs=.9)]
        self.assertEqual(run(ss,gs,'T0').selected,('C','B','A'))
        self.assertEqual(run(ss,gs,'T1').selected,('C','B','A'))
        self.assertEqual(run(ss,gs,'S0').selected,('B','C','A'))

    def test_AH_dedup_takes_current_policy_priority(self):
        gs=[sector('G1',rs=.9),sector('G2',rs=.1)]
        ss=[stock('A','G1',issuer='issuer',rs=.1),stock('H','G2',issuer='issuer',rs=.9)]
        self.assertEqual(run(ss,gs,'S0').selected,('A',))
        self.assertEqual(run(ss,gs,'T0').selected,('H',))

    def test_duplicate_line_does_not_consume_sector_first_pass(self):
        gs=[sector('G1',rs=.9),sector('G2',rs=.1)]
        ss=[stock('A','G1',issuer='same',rs=.9),stock('B','G1',rs=.1),
            stock('H','G2',issuer='same',rs=.9),stock('C','G2',rs=.1)]
        self.assertEqual(run(ss,gs).selected,('A','C','B'))

    def test_existing_migration_excess_does_not_force_sale(self):
        gs=[sector('G'+str(i)) for i in range(1,5)]
        busy=[occ('A','G1'),occ('B','G1'),occ('C','G1'),occ('D','G2')]
        r=run([stock('E','G1'),stock('F','G2'),stock('G','G3')],gs,occupied=busy)
        self.assertNotIn('E',r.selected);self.assertEqual(r.exit_requests,())
        self.assertEqual(set(r.selected),{'F','G'})

    def test_four_existing_sectors_cannot_add_fifth_but_can_fill_existing(self):
        gs=[sector('G'+str(i)) for i in range(1,6)]
        busy=[occ(str(i),'G'+str(i)) for i in range(1,5)]
        r=run([stock('X','G5',rs=1),stock('Y','G1',rs=.1)],gs,occupied=busy)
        self.assertEqual(r.selected,('Y',))

    def test_missing_sector_RS_degrades_whole_batch(self):
        gs=[sector('G1',rs=.1),sector('G2',rs=.9),sector('G3',rs=None)]
        r=run([stock('A','G1'),stock('B','G2'),stock('C','G3')],gs)
        self.assertEqual(r.selected,('A','B','C'));self.assertIn('waiting:sectors',r.ranking_fallbacks)

    def test_missing_stock_RS_only_affects_its_sector(self):
        gs=[sector('G1',rs=1),sector('G2',rs=.1)]
        ss=[stock('A','G1',rs=None),stock('B','G1',rs=.9),stock('C','G2',rs=.1),stock('D','G2',rs=.9)]
        r=run(ss,gs)
        self.assertEqual(r.selected,('A','D','B','C'))
        self.assertEqual(r.ranking_fallbacks,('waiting:stocks:G1',))

    def test_missing_global_RS_degrades_T0_T1_entire_batch(self):
        for v in ('T0','T1'):
            r=run([stock('A',rs=None),stock('B',rs=.9)],variant=v)
            self.assertEqual(r.selected,('A','B'));self.assertEqual(r.ranking_fallbacks,('waiting:stocks',))

    def test_holiday_RS_is_unavailable_not_fresh(self):
        a=replace(stock('A',rs=.1),rank=rank(.1,D-timedelta(days=1)))
        r=run([a,stock('B',rs=.9)],variant='T0')
        self.assertEqual(r.selected,('A','B'));self.assertTrue(r.ranking_fallbacks)

    def test_twelve_digit_tie_stable_id(self):
        r=run([stock('B',rs=.10000000000001),stock('A',rs=.1)],variant='T0')
        self.assertEqual(r.selected,('A','B'))

    def test_RS_253_boundary_and_formula(self):
        values=[float(i+1) for i in range(253)]
        self.assertIsNone(rs_score(values[:252]))
        expected=.4*(253/190-1)+.2*(190/127-1)+.2*(127/64-1)+.2*(64/1-1)
        self.assertAlmostEqual(rs_score(values),expected)
        with self.assertRaises(ValueError):rs_score([1,0,2])

    def test_permutation_invariance(self):
        ss=[stock('A','G1'),stock('B','G2'),stock('C','G1',issuer='B')]
        gs=[sector('G1'),sector('G2')]
        expect=run(ss,gs)
        for perm in itertools.permutations(ss):
            self.assertEqual(run(perm,list(reversed(gs))),expect)

    def test_future_facts_cannot_change_current_selection(self):
        ss=[stock('A')]
        future=replace(stock('Z'),company_cap_cny=replace(fact(20e9),known_at=D+timedelta(days=1)))
        self.assertEqual(run(ss).selected,run(ss+[future]).selected)

    def test_cancel_unfilled_reservation_frees_slot_but_partial_does_not(self):
        ss=[stock('A',buy=False),stock('B'),stock('C')]
        r=run(ss,occupied=[occ('A',pending_buy=True),occ('B')])
        self.assertEqual(r.cancel_buys,('A',));self.assertEqual(r.selected,('C',))
        r=run(ss,occupied=[occ('A',pending_buy=True,has_position=True,partial_fill=True),occ('B')])
        self.assertEqual(r.selected,());self.assertEqual(r.exit_requests,())

    def test_partial_unknown_pauses_before_completion_priority(self):
        r=run([stock('A',cap=None),stock('B')],occupied=[occ('A',pending_buy=True,has_position=True,partial_fill=True)])
        self.assertEqual(r.pause_buys,('A',));self.assertNotIn('A',r.continue_buys)

    def test_real_false_cancels_then_restoration_creates_new_event(self):
        initial=run([stock('A')])
        failed=run([stock('A',up=False)],previous=initial.memories,bootstrap=False)
        later=Clock(D+timedelta(days=2),D+timedelta(days=3),D.date()+timedelta(days=2))
        restored=run([stock('A')],previous=failed.memories,bootstrap=False,clock=later)
        self.assertEqual(restored.memories[0].origin,'eligibility_rising_edge')
        self.assertGreater(restored.memories[0].created_at,initial.memories[0].created_at)

    def test_fact_interval_end_is_exclusive(self):
        s=replace(stock('A'),buy_allowed=replace(fact(True),valid_to=C.earliest_execution_at))
        self.assertIsNone(run([s]).eligibility[0].q)

    def test_synthetic_prefix_replay_is_identical(self):
        snapshots=[[stock('A',up=False)],[stock('A')],[stock('A',cap=None)],[stock('A')],[stock('A',up=False)]]
        def replay(seq):
            outputs=[];memory=()
            for day, securities in enumerate(seq):
                clock=Clock(D+timedelta(days=day),D+timedelta(days=day+1),D.date()+timedelta(days=day))
                out=run(securities,previous=memory,bootstrap=False,clock=clock)
                outputs.append(out);memory=out.memories
            return outputs
        full=replay(snapshots)
        for end in range(1,len(snapshots)+1):
            self.assertEqual(replay(snapshots[:end]),full[:end])

    def test_commit_consumes_candidate_no_unacknowledged_reentry(self):
        first=run([stock('A')])
        committed=run([stock('A')],previous=first.memories,occupied=[occ('A')],bootstrap=False)
        self.assertFalse(committed.memories[0].waiting)
        absent=run([stock('A')],previous=committed.memories,bootstrap=False)
        self.assertEqual(absent.selected,())

    def test_exit_completion_survives_unknown_and_is_idempotent(self):
        ack=ExitCompletion('A','exit-1',D)
        initial=run([stock('A',cap=None)],previous=[Memory('A',True,False,as_of=D)],bootstrap=False,completed_exits=[ack])
        self.assertTrue(initial.memories[0].pending_reentry)
        restored=run([stock('A')],previous=initial.memories,bootstrap=False)
        self.assertEqual(restored.selected,('A',));self.assertFalse(restored.memories[0].pending_reentry)
        committed=run([stock('A')],previous=restored.memories,occupied=[occ('A')],bootstrap=False)
        duplicated=run([stock('A')],previous=committed.memories,bootstrap=False,completed_exits=[ack])
        self.assertEqual(duplicated.selected,())
        with self.assertRaises(ValueError):
            run([stock('A')],completed_exits=[ExitCompletion('A','future',D+timedelta(seconds=1))])

    def test_exit_event_old_replay_and_identity_timestamp_mismatch_rejected(self):
        first=run([stock('A')],bootstrap=False,completed_exits=[ExitCompletion('A','E1',D)])
        later=Clock(D+timedelta(days=3),D+timedelta(days=4),D.date()+timedelta(days=3))
        second=run([stock('A')],previous=first.memories,bootstrap=False,clock=later,
                   completed_exits=[ExitCompletion('A','E2',D+timedelta(days=2))])
        with self.assertRaises(ValueError):
            run([stock('A')],previous=second.memories,bootstrap=False,clock=later,
                completed_exits=[ExitCompletion('A','E1',D)])
        with self.assertRaises(ValueError):
            run([stock('A')],previous=second.memories,bootstrap=False,clock=later,
                completed_exits=[ExitCompletion('A','E2',D+timedelta(days=1))])

    def test_stale_occupancy_classification_is_rejected(self):
        with self.assertRaises(ValueError):
            run([stock('A','G2')],[sector('G1'),sector('G2')],occupied=[occ('A','G1')])
        with self.assertRaises(ValueError):
            run([stock('A',issuer='new')],occupied=[occ('A',issuer='old')])

    def test_input_integrity_and_no_mutation(self):
        ss=[stock('A')];gs=[sector('G1')];before=repr((ss,gs))
        run(ss,gs);self.assertEqual(repr((ss,gs)),before)
        with self.assertRaises(ValueError):run(ss+ss,gs)
        with self.assertRaises(ValueError):run(ss,gs,occupied=[occ('A'),occ('H',issuer='A')])
        with self.assertRaises(ValueError):Clock(D,D,D.date())
        with self.assertRaises(ValueError):
            run(ss,gs,previous=[Memory('A',False,False,as_of=D+timedelta(days=1))],bootstrap=False)
        with self.assertRaises(ValueError):
            run(ss,gs,previous=[Memory('A',False,False)],bootstrap=False)
        with self.assertRaises(ValueError):run(ss,gs,occupied=[replace(occ('A'),known_at=D+timedelta(days=1))])


if __name__ == '__main__':
    unittest.main(verbosity=2)
