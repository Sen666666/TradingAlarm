"""Import-safe joint consumer. Historical PRICE runs require separate root G2 evidence.

No module-level market loading, source reads, engine import, accounting or runner.
The only historical execution model is the explicitly conditional full-fill proxy.
Partial/zero/latefill behavior is tested in execution_book, never fabricated here.
"""
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path
import json
import pandas as pd

from joint_policy import (PriceSizing, OpenView, finite, truth, known_pvr, industry_gate,
                          ab_legal, rank_key, price_protection_close, add_market_permission,
                          INIT, SLOT, RISK, NAV, SLIP)
from execution_book import ExecutionBook, EvidenceDomain, Clock, Receipt, OpenPermission
from gates import PROTOCOL_SHA256, require_economic_authorization, claim_run_once
from cohort_config import CONFIG

O = Path(__file__).resolve().parent


def daystr(day):
    return str(pd.Timestamp(day).date())


def clock(day, phase):
    return Clock(daystr(day), phase)


class JointConsumer:
    def __init__(self, engine, market, window):
        self.s, self.market = engine, market
        self.window = window
        assert window in CONFIG
        self.start = pd.Timestamp(CONFIG[window][0])
        self.birth_end = pd.Timestamp(CONFIG[window][1])
        self.arm = 'A_UNION_B_PLUS_PRICE'
        self.states, self.seq, self.books = {}, {}, {}
        self.sizing = PriceSizing(engine)
        self.price_audit, self.offer_audit, self.frozen_responsibilities = [], [], []
        self.ab_decision_audit = []
        self._cal_next = {d: engine.cal[i + 1] for i, d in enumerate(engine.cal[:-1])}
        assert all(e['event_type']=='PURE_CASH' for e in getattr(engine,'EVENTS',[])), 'QUANTITY_ACTIONS_NOT_ADMITTED'

    def _record(self, st, status, day, **extra):
        self.s.record(st, status, day, **extra)
        self.s.rounds[-1].update(owner_lane=st.get('owner_lane', 'AB'),
                                price_root=st.get('price_root'),
                                actual_order='NOT_PROVIDED', actual_ack='NOT_PROVIDED',
                                actual_fill='NOT_PROVIDED', historical_tradability='UNKNOWN')

    def _unknown(self, sid, st, reason, day):
        self.frozen_responsibilities.append(dict(round_id=st['round_id'], sid=sid, day=day,
            reason=reason, owner_lane=st.get('owner_lane'), core=st.get('core'), add=st.get('add'),
            exitpending=st.get('exitpending'), last_known_mark_day=st.get('last_known_mark_day'),
            book=self.books[st['round_id']].responsibility() if st['round_id'] in self.books else None))
        self.s.freeze_unknown(self.states, sid, st, reason, day)
        self.states[sid]['owner_lane'] = st.get('owner_lane')
        book = self.books.get(st['round_id'])
        if book is not None:
            book.freeze_unknown(reason, clock(day, 10 if self.s.CURRENT_PHASE == 'OPEN' else 100))
        self.s.rounds[-1].update(owner_lane=st.get('owner_lane'), price_root=st.get('price_root'))

    def _unadmitted_action(self, sid, day):
        # PRICE cannot treat a known unreviewed corporate action as no action.
        if hasattr(self.s,'unadmitted_action_at') and self.s.unadmitted_action_at(sid,day):
            return True
        actions = self.s.local_actions(sid)
        if actions.get('_source_integrity_ok') is False:
            return True
        return any(pd.Timestamp(e['effective_date']) == day for e in actions.get('events', [])) and (sid, day) not in self.s.EVENT_AT

    def _view(self, sid, day):
        return OpenView.from_mapping(self.market.open(sid, day))

    def _validate_open(self, sid, st, day, *, pending):
        """No current market.close/phase/failed/root access is permitted here."""
        view = self._view(sid, day)
        if not finite(view.raw_open) or D(str(view.raw_open)) <= 0:
            self._unknown(sid, st, 'MISSING_NEXT_OPEN_UNKNOWN' if pending else 'MISSING_OPEN_PATH_UNKNOWN', day)
            return None
        prev = self.s.raw[sid].get(st['signal_day'], {}) if pending else None
        origin = self.s.lineage(prev) if pending else st['origin']
        if view.lineage != origin:
            self._unknown(sid, st, 'SOURCE_CHANGED_AT_ENTRY_UNKNOWN' if pending else 'SOURCE_CHANGE_PATH_UNKNOWN', day)
            return None
        if self._unadmitted_action(sid, day):
            self._unknown(sid, st, 'UNADMITTED_ACTION_AT_ENTRY_UNKNOWN' if pending else 'UNADMITTED_ACTION_PATH_UNKNOWN', day)
            return None
        if pending:
            z = self.s.raw[sid].get(day, {})
            if self.s.pending_bridge(st, day, z, prev):
                expected = D(str(view.adjustment_factor))
            else:
                expected = D(str(prev['adjustment_factor']))
        else:
            # Original admitted equity bridge updates fac/addfloor/addpending and claims.
            # It preserves S in the canonical source coordinate.
            if not self.s.before_held(self.states, sid, st, day):
                self.states[sid]['owner_lane'] = 'PRICE'
                self.frozen_responsibilities.append(dict(round_id=st['round_id'], sid=sid,
                    day=day, reason=self.states[sid].get('unknown_reason'),
                    core=st.get('core'), add=st.get('add'), owner_lane='PRICE'))
                self.books[st['round_id']].freeze_unknown(self.states[sid].get('unknown_reason', 'EQUITY_UNKNOWN'), clock(day, 10))
                return None
            expected = st['fac']
        if not finite(view.adjustment_factor) or D(str(view.adjustment_factor)) <= 0 or abs(D(str(view.adjustment_factor)) / expected - 1) > D('1e-11'):
            self._unknown(sid, st, 'FACTOR_AT_ENTRY_UNKNOWN' if pending else 'FACTOR_PATH_UNKNOWN', day)
            return None
        try:
            self.s.getmeta(sid, day)
        except (self.s.RuleUnavailable, KeyError, ValueError):
            self._unknown(sid, st, 'DATED_RULE_AT_ENTRY_UNKNOWN' if pending else 'DATED_RULE_PATH_UNKNOWN', day)
            return None
        return view

    def _receipt(self, fact):
        eligible = self._cal_next.get(pd.Timestamp(fact['day']))
        if eligible is None:
            return None
        return Receipt(tuple(fact['root_id']), daystr(fact['day']), clock(fact['day'], 100), daystr(eligible))

    def _proxy_buy(self, st, role, fact, day, sized, *, close_profitable=False):
        book = self.books.get(st['round_id'])
        if book is None:
            book = ExecutionBook(tuple(fact['root_id']), EvidenceDomain.PROXY)
            self.books[st['round_id']] = book
        receipt = self._receipt(fact)
        permission = OpenPermission(receipt, daystr(day), clock(day, 20),
            float(sized['raw_open']), float(sized['floor']), int(sized['q']),
            float(sized['budget']), PROTOCOL_SHA256, True,
            confirmed=fact.get('phase') == 'CONFIRMED',
            close_net_positive=close_profitable, open_net_positive=close_profitable)
        order = book.open_target(role, permission)
        if order is None:
            raise AssertionError('VALIDATED_POSITIVE_PROXY_TARGET_REJECTED')
        parent = book.proxy_full_fill(order.order_id, fill_known_at=clock(day, 30),
             complete_known_at=clock(day, 40), price=float(sized['price']), fee=float(sized['fee']))
        self.price_audit.append(dict(round_id=st['round_id'], sid=st['sid'], day=day,
            role=role, event='PROXY_FULL_FILL_NOT_ACTUAL', target_Q=parent.target_Q,
            filled_F=parent.filled_F, complete_known_at=str(parent.complete_known_at),
            receipt_id=str(receipt.receipt_id), root_id=str(book.root_id),
            historical_tradability='UNKNOWN'))
        return book

    def price_entry_open(self, sid, st, day):
        self.s.CURRENT_PHASE = 'OPEN'
        view = self._validate_open(sid, st, day, pending=True)
        if view is None:
            return
        floor = D(str(st['price_s'])) / D(str(view.adjustment_factor))
        sized = self.sizing.initial_open(sid, day, view, floor=floor, capacity=st['prior20_capacity'])
        if sized['result'] != 'PASS':
            if 'UNKNOWN' in sized['result']:
                self._unknown(sid, st, sized['result'], day)
            else:
                self._record(st, sized['result'], day)
                self.states.pop(sid)
            self.price_audit.append(dict(round_id=st['round_id'], sid=sid, day=day,
                                        event=sized['result'], target_created=False))
            return
        q, px, bf = sized['q'], sized['price'], sized['fee']
        book = self._proxy_buy(st, 'PROBE', st['price_signal_fact'], day, sized)
        st.update(state='HELD', entry_status='CONDITIONAL_OPEN_PROXY', entry_day=day,
            entry_price=float(px), entry_open=float(sized['raw_open']), entry_q=q,
            entry_fee=float(bf), entry_risk=float(sized['risk']), entry_gross=float(D(q) * px),
            entry_floor_raw=float(floor), cash=-D(q)*px-bf, spent=D(q)*px+bf, fees=bf,
            core=q, add=0, addfloor=None, added=False, added_q=0, addpending=None,
            exitpending=None, addexitpending=False, origin=view.lineage,
            factor=float(view.adjustment_factor), fac=D(str(view.adjustment_factor)),
            initial_fee=bf, add_attempts=0, add_profit_floor_rejects=0, add_size_rejects=0,
            negative_CP_blocked=0, CP_unknown_days=0, post_birth_window_adds=0,
            profitable_close_days=0, first_profitable_close=None, first_fresh_CP=None,
            industry_first_not_true=None, max_inventory_reference_fraction=float(D(q)*px/NAV))
        self.s.act(st, day, 'buy_core', q, px, bf, 'PRICE_INITIAL_CONDITIONAL_PROXY',
                   signal_day=daystr(st['signal_day']), economic_role='PRICE_PROBE')
        assert book.held_qty == st['core'] + st['add']

    def price_held_open(self, sid, st, day):
        self.s.CURRENT_PHASE = 'OPEN'
        view = self._validate_open(sid, st, day, pending=False)
        if view is None:
            return
        _, fs, par = self.s.getmeta(sid, day)
        op = D(str(view.raw_open)); sp = op * (1-SLIP)
        book = self.books[st['round_id']]
        if st['exitpending']:
            q = st['core'] + st['add']
            sf = self.s.fee(q, sp, fs, 'sell', par)
            order = book.submit_exit(decision_open=daystr(day), known_at=clock(day, 20))
            assert order.quantity == q
            book.proxy_full_fill(order.order_id, fill_known_at=clock(day, 30),
                                  complete_known_at=clock(day, 40), price=float(sp), fee=float(sf))
            st['cash'] += D(q)*sp-sf; st['fees'] += sf
            self.s.act(st, day, 'sell_all', q, sp, sf, 'PRICE_OLD_S_EXIT', economic_role='PRICE_ALL')
            st['core'] = st['add'] = 0
            assert book.held_qty == 0
            self._record(st, 'COMPLETE_CONDITIONAL_STOCK_ROUND', day,
                         exit_price=float(sp), exit_reason='PRICE_OLD_S_EXIT')
            self.states.pop(sid)
            return
        fact = st.pop('price_add_fact', None)
        st['addpending'] = None
        if fact is None:
            return
        st['add_attempts'] += 1
        prior_net = self.s.mark(st, sp, day)
        floor = D(str(st['price_s'])) / st['fac']
        sized = self.sizing.add_open(sid, day, view, floor=floor,
            capacity=fact['capacity_shares'], held_qty=st['core']+st['add'],
            all_entry_fees=st['initial_fee'], prior_net=prior_net)
        if sized['result'] != 'PASS':
            if 'UNKNOWN' in sized['result']:
                self._unknown(sid, st, sized['result'], day)
            else:
                st['add_profit_floor_rejects' if 'PROFITABLE' in sized['result'] or 'BELOW' in sized['result'] else 'add_size_rejects'] += 1
            self.price_audit.append(dict(round_id=st['round_id'], sid=sid, day=day,
                                        role='ADD', event=sized['result'], target_created=False))
            return
        assert prior_net > 0 and not st['added']
        book = self._proxy_buy(st, 'ADD', fact, day, sized, close_profitable=True)
        q, px, bf = sized['q'], sized['price'], sized['fee']
        st.update(add=q, addfloor=floor, added=True, added_q=q)
        st['cash'] -= D(q)*px+bf; st['spent'] += D(q)*px+bf; st['fees'] += bf
        st['post_birth_window_adds'] += int(day > self.birth_end)
        self.s.act(st, day, 'buy_add', q, px, bf, 'PRICE_CONFIRMED_FRONTIER_ADD',
                   prior_round_net=float(prior_net), economic_role='PRICE_ADD')
        assert book.held_qty == st['core'] + st['add']

    def price_held_close(self, sid, st, day):
        self.s.CURRENT_PHASE = 'CLOSE'
        fact = self.market.close(sid, day)
        outcome, raised = price_protection_close(held_root=st['price_root'],
                                                prior_s=st['price_s'], fact=fact)
        if outcome == 'UNKNOWN':
            self._unknown(sid, st, 'PRICE_SOURCE_OR_ROOT_PATH_UNKNOWN', day)
            return
        cl = D(str(fact['raw_close']))
        try:
            net = self.s.mark(st, cl*(1-SLIP), day)
        except (self.s.RuleUnavailable, KeyError, ValueError):
            self._unknown(sid, st, 'DATED_RULE_CLOSE_UNKNOWN', day)
            return
        st.update(last_known_mark_day=day, last_raw_close=float(cl),
                  last_mark_net=float(net), last_mark_fraction=float(net/st['spent']))
        st['max_inventory_reference_fraction'] = max(st['max_inventory_reference_fraction'],
            float(D(st['core']+st['add'])*cl/NAV))
        st['profitable_close_days'] += int(net > 0)
        if net > 0 and st['first_profitable_close'] is None:
            st['first_profitable_close'] = day
        book = self.books[st['round_id']]
        if outcome == 'EXIT':
            book.retire_root(clock(day, 100), 'PRICE_FAILED_OLD_S')
            st.update(exitpending='PRICE_OLD_S_EXIT', addpending=None)
            st.pop('price_add_fact', None)
            return
        st['price_s'] = raised
        if st['add']:
            st['addfloor'] = raised/st['fac']
        if industry_gate(fact) != 'PASS' and st['industry_first_not_true'] is None:
            st['industry_first_not_true'] = day
        receipt = self._receipt(fact) if truth(fact.get('receipt')) is True else None
        if receipt and add_market_permission(fact=fact, healthy=not book.unknown and not st['exitpending'],
            probe_complete=book.complete('PROBE'), complete_known_at=book.parent('PROBE').complete_known_at,
            receipt_known_at=receipt.known_at, add_parent_exists=book.parent('ADD') is not None, net=net):
            st['price_add_fact'] = fact
            st['addpending'] = raised/st['fac']

    def _new_state(self, row, lane, check):
        sid = row['sid']; self.seq[sid] = self.seq.get(sid, 0) + 1
        rid = f'{self.window}|{self.arm}|{sid}|{self.seq[sid]}'
        st = self.s.new_state(row, self.arm, rid, check)
        st.update(owner_lane=lane, birth_end=self.birth_end)
        if lane == 'PRICE':
            st.update(price_root=tuple(row['root_id']), price_s=D(str(row['S_new'])),
                      price_signal_fact=dict(row))
        self.states[sid] = st
        return st

    def _offer(self, lane, row, result, **extra):
        self.offer_audit.append(dict(day=row['day'],sid=row['sid'],owner_lane=lane,
            event_id=row.get('event_id'),request_id=('PRICE|'+repr(row.get('receipt_id')) if lane=='PRICE' else row.get('event_id')),
            sector=row.get('sector'),receipt_id=repr(row.get('receipt_id')),
            PVR_known=known_pvr(row),PVR_score=row.get('PVR_score'),result=result,**extra))

    def select_close(self, day, ab_rows, price_rows):
        """One stock-level option, legal AB precedence, then shared known/unknown ranking."""
        by_ab = {r['sid']:dict(r) for r in ab_rows}
        by_price = {r['sid']:dict(r) for r in price_rows}
        native_ab_rank={}
        for sector in sorted({r['sector'] for r in ab_rows}):
            queue_rank=feasible_rank=0
            ordered=sorted([r for r in ab_rows if r['sector']==sector],
                key=lambda r:(0,-float(r['PVR_score']),r['sid']) if finite(r.get('PVR_score')) else (1,0,r['sid']))
            for r in ordered:
                sid=r['sid'];state=self.states.get(sid,{}).get('state','FLAT')
                z={k:r.get(k) for k in ['event_id','window','day','sid','sector','event_type','I_qualified','PVR_known','PVR_score']}
                z.update(stock_state_before=state,blocking_round_id=self.states.get(sid,{}).get('round_id'),
                         original_ab_queue_rank=None,original_ab_feasible_rank=None)
                if state!='FLAT':z['decision_before_joint']='BLOCKED_'+state
                elif truth(r.get('I_qualified')) is not True:z['decision_before_joint']='I_INELIGIBLE'
                elif not known_pvr(r):z['decision_before_joint']='PVR_UNKNOWN'
                else:
                    queue_rank+=1;z['original_ab_queue_rank']=queue_rank
                    check=self.s.checkclose(r);z.update(check)
                    if check['close_check']!='PASS':z['decision_before_joint']='CLOSE_'+check['close_check']
                    else:
                        feasible_rank+=1;z.update(original_ab_feasible_rank=feasible_rank,decision_before_joint='PASS_TO_JOINT_QUEUE')
                native_ab_rank[sid]=z
                self.ab_decision_audit.append(z)
        options = []
        for sid in sorted(set(by_ab)|set(by_price)):
            ab, pr = by_ab.get(sid), by_price.get(sid)
            if pr:self._offer('PRICE',pr,'APPLICATION',stage='RAW_MARKET_RECEIPT')
            state = self.states.get(sid, {}).get('state', 'FLAT')
            if state != 'FLAT':
                for lane, row in [('AB',ab),('PRICE',pr)]:
                    if row:
                        self._offer(lane,row,'BLOCKED_'+state,blocking_round_id=self.states[sid]['round_id'])
                continue
            abcheck = {}
            if ab and truth(ab.get('I_qualified')) is True and known_pvr(ab):
                abcheck = self.s.checkclose(ab)
            if ab_legal(ab, abcheck):
                row, lane, check = ab, 'AB', abcheck
                if pr:
                    self._offer('PRICE',pr,'SUPPRESSED_BY_AB_VALID_CLOSE')
            else:
                if ab:
                    self._offer('AB',ab,'AB_ORIGINAL_CLOSE_INELIGIBLE',I_qualified=ab.get('I_qualified'),
                                close_check=abcheck.get('close_check'))
                if pr is None:
                    continue
                if industry_gate(pr) != 'PASS':
                    self._offer('PRICE',pr,industry_gate(pr))
                    continue
                check = self.sizing.close_check(pr, window=self.window)
                if check['close_check'] != 'PASS':
                    self._offer('PRICE',pr,check['close_check'])
                    continue
                row, lane = pr, 'PRICE'
                row.update(event_id='PRICE|'+repr(pr['receipt_id']), event_type='PRICE_FRONTIER_INVITATION',
                           I_qualified=None, i_floor=pr['S_new'], window=self.window)
            row['owner_lane'] = lane
            options.append((row,check))
        sectors = sorted({r['sector'] for r,_ in options})
        for sector in sectors:
            ordered = sorted([(r,c) for r,c in options if r['sector']==sector], key=lambda rc:rank_key(rc[0]))
            for rank,(row,check) in enumerate(ordered,1):
                dec = {k:row.get(k) for k in ['event_id','window','day','sid','name','industry','sector',
                                              'event_type','PVR_score','I_qualified','PVR_known','owner_lane']}
                old_rank=native_ab_rank.get(row['sid'],{}) if row['owner_lane']=='AB' else {}
                dec.update(arm=self.arm, selected=rank<=2, queue_rank=old_rank.get('original_ab_queue_rank'),
                           original_ab_queue_rank=old_rank.get('original_ab_queue_rank'),
                           original_ab_feasible_rank=old_rank.get('original_ab_feasible_rank'),joint_feasible_rank=rank,
                           stock_state_before='FLAT', **check)
                if rank<=2:
                    st=self._new_state(row,row['owner_lane'],check)
                    dec.update(decision='SELECTED_PENDING',selected_rank=rank,round_id=st['round_id'])
                    self.s.load(row['sid'])
                else:
                    dec['decision']='PASS_NOT_TOP2'
                self.s.decisions.append(dec)
                self.s.ranking_audit.append(dict(dec))
                self._offer(row['owner_lane'],row,dec['decision'],rank=rank)

    def process_day(self, day, prevday, ab_rows, price_rows):
        """Daily scheduler shared by authorized history and fictitious G1 fixtures."""
        self.s.accrue_day(self.arm,day)
        for sid in list(self.states):
            st=self.states[sid]
            if st['state']=='BUY_PENDING':
                if st.get('owner_lane')=='PRICE':self.price_entry_open(sid,st,day)
                else:self.s.entry_open(self.states,sid,st,day)
            elif st['state']=='HELD':
                if st.get('owner_lane')=='PRICE':self.price_held_open(sid,st,day)
                else:self.s.held_open(self.states,sid,st,day,prevday)
        for sid in list(self.states):
            st=self.states[sid]
            if st['state']=='HELD':
                if st.get('owner_lane')=='PRICE':self.price_held_close(sid,st,day)
                else:self.s.held_close(self.states,sid,st,day)
        self.s.register(self.states,self.arm,day)
        if day<=self.birth_end:
            self.select_close(day,ab_rows,price_rows)
        self.s.pay_day(self.arm,day)

    def _candidate_frame(self):
        """Read only whitelisted causal fields; never old holdings/outcomes."""
        from market_adapter import canonical_root
        p=O/'PRICE_CANDIDATES.parquet'
        cols=['sid','day','name','industry','sector','window','root_day','identity','receipt_id',
              'valid','raw_close','adjustment_factor','S_new','phase','born','receipt',
              'old_PVR_known','old_PVR_score','old_sector_known','old_sector_observed_today',
              'old_sector_rs_ready_fresh','old_sector_up','volume_capacity_shares']
        x=pd.read_parquet(p,columns=cols,filters=[('window','==',self.window)])
        x=x.rename(columns={'valid':'price_valid','receipt_id':'legacy_receipt_id',
            'old_PVR_known':'PVR_known','old_PVR_score':'PVR_score',
            'volume_capacity_shares':'capacity_shares',
            **{'old_'+k:k for k in ('sector_known','sector_observed_today','sector_rs_ready_fresh','sector_up')}})
        x['root_id']=[canonical_root(sid,identity,birth) for sid,identity,birth in zip(x.sid,x.identity,x.root_day)]
        x['receipt_id']=[(root,daystr(day)) for root,day in zip(x.root_id,x.day)]
        self.candidate_source_sha256=__import__('hashlib').sha256(p.read_bytes()).hexdigest()
        return x

    def run_authorized(self, authorization):
        # Gate runs again immediately before any first PRICE iteration.
        win=self.window
        approved=require_economic_authorization(win,authorization)
        claim_run_once(win,approved)
        self.s.reset(True)
        groups_ab={d:g.to_dict('records') for d,g in self.s.ev.groupby('day')}
        prices=self._candidate_frame()
        groups_price={d:g.to_dict('records') for d,g in prices.groupby('day')}
        for k,day in enumerate(self.s.cal):
            if day<self.start or day>self.s.END:
                continue
            prevday=self.s.cal[k-1] if k else None
            self.process_day(day,prevday,groups_ab.get(day,[]),groups_price.get(day,[]))
            if k%50==0:print('COHORT_DAY',self.window,str(day.date()),'states',len(self.states),'rounds',len(self.s.rounds),flush=True)
        for sid,st in self.states.items():
            if st['state']=='HELD':
                self._record(st,'OPEN_CENSORED_AT_2026_06_30',self.s.END)
            elif st['state']=='BUY_PENDING':
                self._record(st,'BUY_PENDING_CENSORED_AT_DATA_END',self.s.END)
            self.s.blocks.append(dict(window=self.window,arm=self.arm,sid=sid,
                final_state=st['state'],round_id=st['round_id']))
        self.s.finalize()
        for row in self.s.rounds:
            st=self.s.archives[row['round_id']]
            row.update(owner_lane=st.get('owner_lane','AB'),price_root=st.get('price_root'),
                       actual_ack='NOT_PROVIDED',actual_fill='NOT_PROVIDED',historical_tradability='UNKNOWN')
        self.market_source_sha256=self.market.verify_sources()
        for path,digest in self.s.hashes.items():
            assert self.s.sha(path)==digest,('BASE_SOURCE_DRIFT_AT_END',path)
        if hasattr(self,'candidate_source_sha256'):
            path=O/'PRICE_CANDIDATES.parquet'
            assert self.s.sha(path)==self.candidate_source_sha256,'CANDIDATE_SOURCE_DRIFT_AT_END'
        return self


def run_price_off(window):
    """Identical original engine route, no joint policy or market state is instantiated."""
    from baseline_regression import run_price_off as original_route
    return original_route(window,price_enabled=False)


def run_joint(window, authorization=None):
    # Authorize before engine source loading as well as before the loop.
    approved=require_economic_authorization(window,authorization)
    from baseline_regression import load_engine
    from market_adapter import MarketAdapter
    return JointConsumer(load_engine(window),MarketAdapter(expected_sources=approved['input_sha256']),window).run_authorized(authorization)
