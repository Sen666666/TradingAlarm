"""M12 minimal-A funding selector. Offline review only; no history launcher.

Frozen native M7 plans and greedy execution are reused. Only the set of new
MATURE SEED requests changes. Conditional projection never reads full-day bars.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
import textwrap
import numpy as np
sys.dont_write_bytecode = True
O = Path(__file__).resolve().parent
ROOT = O.parent
BASE = ROOT / 'mainline_m7_cash_batch_design_v6'
DESIGN = ROOT / 'mainline_winner_funding_design_v1'
DESIGN_SHA = '3ffa6bd951e2377e65a83f9ee13bd3a2ed320970ed0f03fd277398e1b9856bd1'
BASE_SHA = 'ad0f77fb92d47af4046bf5ab7ef3b4f9b51451d4fe6a6b86a62163f35076a056'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(DESIGN / 'EXECUTION_FREEZE_ADDENDUM.md') == DESIGN_SHA
assert sha(BASE / 'engine.py') == BASE_SHA

def module(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m
base = module('funding_frozen_cash_v6', BASE / 'engine.py')
m4, m3 = base.v.m4, base.v.m3
m2, m5 = m3.m2, base.v.m7.m5
D, ZERO, SLIP = base.D, m4.ZERO, m4.SLIP
pd, dec, day, finite, valid, lineage = base.pd, base.dec, base.day, m4.finite, m4.valid, m4.lineage
Blocked, Data, rules = base.Blocked, base.Data, m4.rules
WAIT = 'FUNDING_NONDISPLACEMENT_WAIT'
PLAN_KEYS = ('reference', 'transfer_plan', '_donor_sectors', '_probe_receiver_sectors')
PLAN_LOGS = ('transfers', 'reference_log', 'capital_lots', 'reference_requests', 'event_plans')
AUDIT_KEYS = ('funding_book', 'funding_books', 'funding_decisions', 'funding_wait_log', 'funding_preflight', 'funding_actual')

def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in sorted(x.items(), key=lambda p: str(p[0]))}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if isinstance(x, set): return sorted((clean(v) for v in x), key=str)
    if isinstance(x, (bool, np.bool_)): return bool(x)
    if isinstance(x, (int, np.integer)): return int(x)
    if x is None or isinstance(x, (str, float)): return x
    return str(x)

def digest(value):
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def branch_hash_payload(branch):
    return {k:branch[k] for k in ('retained','requests','plan','event_reserved','bar_q_C')}


def boolean(x):
    return bool(x) if isinstance(x, (bool, np.bool_)) else None

def positive(x):
    return finite(x) and dec(x) > ZERO

def known_origin(z):
    return all(z.get(k) is not None and pd.notna(z.get(k)) and str(z.get(k)).strip().lower() not in ('', 'unknown', 'none', 'nan')
               for k in ('source_kind', 'source_path', 'segment_id'))

def request_id(r):
    ticket = (hashlib.sha256(json.dumps([r['sid'], r['birth_type'], r['signal_day'], tuple(r['origin'])]).encode()).hexdigest()[:24] if r['kind'] == 'SEED' else None)
    return digest([r['sid'], r['kind'], r['signal_day'], r.get('birth_type'), ticket,
                   r.get('round_id'), r.get('cp_id'), r.get('cp_date'), r.get('event_id'), r.get('origin')])[:24]

def new_seed(r):
    return r['kind'] == 'SEED' and r.get('allocation_phase') == 'MATURE'

def protected(r):
    return r['kind'] == 'ADD' or r.get('allocation_phase') == 'EVENT'

def once(s, a, b):
    assert s.count(a) == 1, ('HOOK_NOT_UNIQUE', a)
    return s.replace(a, b)

# Extract the ORIGINAL current M5 donor planner; only sync/prepare are separated
# so all branches start AFTER the exact same one-time CLOSE event update.
PLAN_ORIGINAL = textwrap.dedent(inspect.getsource(m4.Engine.plan_transfers))
PLAN_ROLE = once(PLAN_ORIGINAL, "tier=0 if r['kind']=='SEED' else 1 if r['donor_reason']=='WEAK_SECTOR_ADD_LAYER' else 2",
                 "tier=0 if r['capital_role']=='INITIAL' else 1 if r['M']==0 else 2")
PLAN_ROLE = once(PLAN_ROLE, "q=maxq if r['kind']=='SEED' and maxq==r['qty'] else 0 if r['kind']=='SEED' else self.sell_quantity(s,nxt,p,gap,maxq,self.quantity(a))",
                 "q=(maxq if maxq==r['qty'] else 0) if r['capital_role']=='INITIAL' else self.sell_quantity(s,nxt,p,gap,maxq,self.quantity(a))")
PLAN_HEAD = "self.sync_events(d);reqs=self.prepare_requests(d,[a['plan'] for a in self.active.values() if a.get('plan')]+pending)"
PLAN_SOURCE = once(PLAN_ROLE, PLAN_HEAD, 'reqs=pending')
ns = dict(vars(m5))
exec(compile(PLAN_SOURCE, 'M12_NATIVE_PLANNER_PREPARED_WORKING_SET_ONLY', 'exec'), ns)
native_plan_prepared = ns['plan_transfers']

class QuoteView:
    """Strict conditional execution facade: no current/future CLOSE or signals.

    CLOSE projection maps quotes from the observed CLOSE, but metadata/fees
    remain dated at next OPEN. OPEN projection exposes only current raw_open.
    Data metadata cache is private; shared price matrices are never modified.
    """
    def __init__(self, data, decision_day, close_day=None):
        self._data = copy.copy(data)
        if hasattr(data, 'meta'): self._data.meta = dict(data.meta)
        self._decision = decision_day
        self._close = close_day
    def __copy__(self):
        return QuoteView(self._data, self._decision, self._close)
    def __getattr__(self, key):
        if key in ('raw', 'facts', 'cp', 'stock', 'main', 'sectors', 'cap', 'f', 'c', 'm', 'evidence'):
            raise AssertionError('FORBIDDEN_PROJECTION_INPUT:' + key)
        return getattr(self._data, key)
    def z(self, s, d):
        assert d == self._decision, 'PROJECTION_DATE_ESCAPE'
        z = self._data.z(s, self._close if self._close is not None else d)
        fields = ('adjustment_factor', 'source_kind', 'source_path', 'segment_id')
        return {k: z.get(k) for k in fields} | {'raw_open': z.get('raw_close' if self._close is not None else 'raw_open')}
    def getmeta(self, *a): return self._data.getmeta(*a)
    def fee(self, *a): return self._data.fee(*a)
    def size(self, *a): return self._data.size(*a)


def scratch(engine, data=None):
    x = object.__new__(ConditionalEngine)
    # One deepcopy preserves active/archive aliases, including plans and proof.
    state = {k: v for k, v in vars(engine).items() if k != 'd' and k not in AUDIT_KEYS}
    vars(x).update(copy.deepcopy(state))
    x.d = copy.copy(engine.d) if data is None else data
    if data is None and hasattr(engine.d, 'meta'): x.d.meta = dict(engine.d.meta)
    for k in AUDIT_KEYS: setattr(x, k, None if k == 'funding_book' else [])
    return x


def state_fingerprint(engine):
    return digest({k:v for k,v in vars(engine).items() if k!='d' and k not in AUDIT_KEYS})

def compare(candidate, shadow, H, A):
    bad_y = [l for l, h in H.items() if h['H'] and candidate['y'].get(l, 0) > shadow['y'].get(l, 0)]
    bad_q = [r for r in A if candidate['q'].get(r, 0) < shadow['q'].get(r, 0)]
    return dict(passed=not bad_y and not bad_q, healthy_donor_increase=bad_y, add_event_reduction=bad_q)

class Engine(base.Engine):
    def __init__(self, data):
        super().__init__(data)
        self.funding_book = None
        self.funding_books = []
        self.funding_decisions = []
        self.funding_wait_log = []
        self.funding_preflight = []
        self.funding_actual = []
        self.funding_waits = {}
        self.funding_close_knowledge = {}

    def health(self, d, phase, *, pre_cashflows=None):
        out = {}
        for s, a in self.active.items():
            z = self.d.z(s, d)
            knowledge = self.funding_close_knowledge.get(s, {})
            source = (valid(z) if phase == 'CLOSE' else knowledge.get('close_quote_known', False)) and known_origin(z) and tuple(lineage(z)) == tuple(a['origin'])
            proof = next((c for c in reversed(self.confirmations) if c.get('round_id') == a['id'] and c.get('decision') == 'INFORMATION_CONFIRMED' and c.get('cp_id')), None)
            factor = positive(z.get('adjustment_factor')) and abs(dec(z['adjustment_factor']) / a['factor'] - 1) <= D('1e-11')
            net = self.net(a, d, 'raw_close' if phase == 'CLOSE' else 'raw_open')
            mark = dec(z['raw_close' if phase == 'CLOSE' else 'raw_open']) * a['factor']
            for lot in a['lots']:
                floor = max(a['ifloor'], lot['floor']) if lot['kind'] == 'ADD' else a['ifloor']
                components = dict(post_seed_information_confirmed=bool(a.get('confirmed_history', False) and proof),
                                  current_net_positive=net > ZERO,
                                  protection_unbroken=mark > floor and not a['exit'] and not lot.get('exit'),
                                  source_and_factor_known=bool(source and factor),
                                  close_I_CP_fields_known=bool(knowledge.get('I_known') and knowledge.get('CP_known')),
                                  original_donor_fields_known=bool(knowledge.get('native_fields_known')))
                previous = (pre_cashflows or {}).get(a['id'], a['cashflow'])
                out[lot['id']] = dict(sid=s, round_id=a['id'], lot_id=lot['id'], quantity=lot['q'],
                    capital_role=lot.get('capital_role'), H=all(components.values()), components=components,
                    net_liquidation=str(net), raw_mark=str(z['raw_close' if phase == 'CLOSE' else 'raw_open']),
                    current_factor=str(a['factor']), origin=a['origin'], effective_protection=str(floor),
                    confirmation_day=a.get('confirmed_day'), confirmation_proof=copy.deepcopy(proof), actual_cashflow_before_prefix=str(previous),
                    conditional_prefix_cashflow=str(a['cashflow']-previous), dividend=str(a['dividend']),
                    knowledge=knowledge, cp_id=lot.get('cp_id'), conditionally_predicted=phase == 'OPEN')
        return out

    def freeze_knowledge(self, d):
        self.funding_close_knowledge = {}
        for s, a in self.active.items():
            f, c, m, z = self.d.f(s, d), self.d.c(s, d), self.d.m(s,d), self.d.z(s,d)
            sec=int(self.d.sectors[self.d.sid_sector[s]].at[d,'state']); stock=int(self.d.stock.at[d,s])
            self.funding_close_knowledge[s] = dict(day=day(d),
                I_known=bool(m4.truth(f.get('i_target'))) and positive(f.get('i_floor')),
                native_fields_known=sec in (0,1) and stock in (0,1) and m.M in (0,1) and finite(m.E),
                sector_state=sec, stock_state=stock, M=int(m.M), E=str(m.E),
                close_quote_known=bool(valid(z) and known_origin(z) and tuple(lineage(z))==tuple(a['origin'])),
                CP_known=boolean(c.get('receipt')) is not None,
                i_target=1 if m4.truth(f.get('i_target')) else 0 if m4.false(f.get('i_target')) else None, i_floor=str(f.get('i_floor')),
                cp_receipt=boolean(c.get('receipt')), cp_candidate=str(c.get('candidate')))

    def plan_branch(self, d, anchor, reqs, retained, n_ids):
        x = scratch(anchor)
        rows = copy.deepcopy([r for r in reqs if not new_seed(r) or request_id(r) in retained])
        starts = {k: len(getattr(x, k)) for k in PLAN_LOGS}
        native_plan_prepared(x, d, rows)
        rows = x.request_key_groups(rows)
        result = dict(retained=list(retained), requests=rows,
                      plan={k: copy.deepcopy(getattr(x, k)) for k in PLAN_KEYS},
                      event_reserved={k: v['reserved'] for k, v in x.events.items()},
                      logs={k: copy.deepcopy(getattr(x, k)[starts[k]:]) for k in PLAN_LOGS})
        result['bar_q_C'] = {request_id(r): int(min(r['planned_q'], r['capacity'], r.get('_ref_q', 0), r.get('econ_q', r['planned_q']))) for r in rows}
        for r in reqs: result['bar_q_C'].setdefault(request_id(r), 0)
        result['branch_id'] = digest(branch_hash_payload(result))
        return result

    def install(self, branch, pending):
        """Install ONE complete CLOSE branch; never union/max/min fields.

        Identity intersection is essential: original Q0/preflight or forced
        exits may already have removed a request. No branch can restore it.
        """
        for k, value in copy.deepcopy(branch['plan']).items(): setattr(self, k, value)
        available = {request_id(r): r for r in branch['requests']}
        result = []
        for r in pending:
            rid = request_id(r)
            if rid in available: result.append(copy.deepcopy(available[rid]))
        for a in self.active.values():
            r = a.get('plan')
            if r:
                rid = request_id(r)
                a['plan'] = copy.deepcopy(available[rid]) if rid in available else None
        for eid, value in branch['event_reserved'].items():
            if eid in self.events: self.events[eid]['reserved'] = value
        return result

    def project(self, d, common, branch, pending, all_requests):
        x = scratch(common)
        pr = x.install(branch, pending)
        before_t, before_c = len(x.transfers), len(x.candidates)
        base.Engine.alloc_open(x, d, pr)
        q = {request_id(r): 0 for r in all_requests}
        # q_hat is original reservation/submittable quantity, not demand desired.
        lookup = {(r['sid'], r['kind'], r['signal_day'], r.get('cp_id')): request_id(r) for r in all_requests}
        for row in x.candidates[before_c:]:
            key = (row['sid'], row.get('event'), row.get('signal_day'), row.get('cp_id'))
            if key in lookup: q[lookup[key]] = int(row['executed_q'])
        y = {}
        for row in x.transfers[before_t:]:
            if row.get('event') == 'DONOR_EXECUTION': y[row['lot_id']] = int(row['executed_q'])
        for rid, amount in q.items(): assert amount <= branch['bar_q_C'].get(rid, 0), ('NATIVE_BRANCH_BOUND', rid, amount)
        return dict(q=q, y=y, cash_after=str(x.cash),
                    reservation_rows=copy.deepcopy(x.candidates[before_c:]),
                    transfer_rows=copy.deepcopy(x.transfers[before_t:]))

    def conditional_prefix(self, d, close_day=None):
        view = QuoteView(self.d, d, close_day)
        x = scratch(self, view)
        before = {a['id']: a['cashflow'] for a in x.archive.values()}
        order_start = len(x.orders)
        base.Engine.exit_open(x, d)
        base.Engine.info_open(x, d)
        prefix = dict(actual_cash_before=str(self.cash), predicted_cash_after=str(x.cash),
                      predicted_prefix_orders=copy.deepcopy(x.orders[order_start:]),
                      actual_receivable=str(self.receivable), actual_cashflows={k: str(v) for k, v in before.items()},
                      conditional_inventory={s: {l['id']: l['q'] for l in a['lots']} for s, a in x.active.items()},
                      conditional_confirmations=copy.deepcopy(x.confirmations[len(self.confirmations):]))
        return x, before, prefix

    def plan_transfers(self, d, pending):
        self.sync_events(d)
        reqs = self.prepare_requests(d, [a['plan'] for a in self.active.values() if a.get('plan')] + pending)
        self.freeze_knowledge(d)
        for r in reqs:
            if r['kind']=='ADD':r['round_id']=self.active[r['sid']]['id']
        H = self.health(d, 'CLOSE')
        hs = digest([day(d), 'CLOSE', self.cash, self.receivable, H])
        state_before_projection=state_fingerprint(self)
        anchor = scratch(self)
        full = self.plan_branch(d, anchor, reqs, [request_id(r) for r in reqs if new_seed(r)], [])
        priority = [request_id(r) for r in full['requests'] if new_seed(r)]
        full['retained'] = priority
        full['branch_id'] = digest(branch_hash_payload(full))
        branches = [full]
        for k in range(1, len(priority)+1):
            branches.append(self.plan_branch(d, anchor, reqs, priority[:-k], priority))
        common, _, prefix = self.conditional_prefix(self.next_day(d), close_day=d)
        for branch in branches:
            branch['close_projection'] = self.project(self.next_day(d), common, branch, pending, reqs)
        A = [request_id(r) for r in reqs if protected(r)]
        shadow = branches[-1]
        for i, branch in enumerate(branches):
            branch['deletion_index'] = i
            branch['close_comparison'] = compare(branch['close_projection'], shadow['close_projection'], H, A)
        selected = next(i for i, branch in enumerate(branches) if branch['close_comparison']['passed'])
        state_after_projection=state_fingerprint(self)
        assert state_before_projection==state_after_projection,'CLOSE_SCRATCH_SIDE_EFFECT'
        book = dict(scratch_integrity=dict(before=state_before_projection,after=state_after_projection,passed=True),close_day=day(d), next_day=day(self.next_day(d)), health_snapshot_id=hs,
                    H=H, close_conditional_prefix=prefix, original_requests=copy.deepcopy(reqs),
                    N_priority=priority, A=A, branches=branches, selected_close_index=selected,
                    preflight_original_targets=sorted(set(self.active)|{r['sid'] for r in pending}|set(self.live_tickets())))
        book['hash_contract']='digest(clean(all book fields except book_id)); branch_id=digest(clean(retained,requests,plan,event_reserved,bar_q_C))'
        book['book_id'] = digest(book)
        self.funding_book = book
        self.funding_books.append(book)
        # Adopt native selected CLOSE diagnostics, not scratch execution effects.
        for k in PLAN_LOGS: getattr(self, k).extend(copy.deepcopy(branches[selected]['logs'][k]))
        original_by_id = {request_id(r): r for r in reqs}
        for branch in (full, branches[selected]):
            for r in branch['requests']:
                original_by_id[request_id(r)].update(copy.deepcopy(r))
        self.install(branches[selected], pending)
        # The real pending still contains ALL original requests for preflight.
        assert {r['sid'] for r in pending} <= set(book['preflight_original_targets'])

    def select_open(self, d, pending):
        book = self.funding_book
        if book is None:
            assert not pending and not self.transfer_plan
            return None
        assert book['next_day'] == day(d), 'STALE_BRANCH_BOOK'
        state_before_projection=state_fingerprint(self)
        common, before, prefix = self.conditional_prefix(d)
        H = common.health(d, 'OPEN', pre_cashflows=before)
        hs = digest([day(d), 'OPEN', prefix, H])
        branch_projections = {}
        branches = book['branches']
        shadow_i = len(branches)-1
        p0 = self.project(d, common, branches[-1], pending, book['original_requests'])
        branch_projections[shadow_i] = p0
        evaluated = []
        selected = None
        for i in range(book['selected_close_index'], len(branches)):
            b = branches[i]
            if not b['close_comparison']['passed']: continue
            p = branch_projections.get(i)
            if p is None: p = self.project(d, common, b, pending, book['original_requests']); branch_projections[i] = p
            result = compare(p, p0, H, book['A'])
            evaluated.append(dict(index=i, branch_id=b['branch_id'], health_snapshot_id=hs, projection=p, comparison=result))
            if result['passed']: selected=i; break
        assert selected is not None
        state_after_projection=state_fingerprint(self)
        assert state_before_projection==state_after_projection,'OPEN_SCRATCH_SIDE_EFFECT'
        decision = dict(scratch_integrity=dict(before=state_before_projection,after=state_after_projection,passed=True),day=day(d), book_id=book['book_id'], health_snapshot_id=hs, H=H,
                        common_conditional_prefix=prefix, shadow_projection=p0,
                        evaluated=evaluated, selected_index=selected, selected_branch_id=branches[selected]['branch_id'],
                        chosen_projection=branch_projections[selected], selection_before_actual_orders=len(self.orders))
        self.funding_decisions.append(decision)
        return decision

    def wait_ticket(self, r, d, decision, x):
        s = r['sid']
        t = self.live_tickets().get(s)
        if x['reason'] != 'PASS':
            # Native attempt-budget/stock/structural failures are NOT a new
            # capital wait permission. Retain or cancel exactly as original.
            rawq=r.get('econ_q',0);rawcost=rawq*x['p']+self.d.fee(s,d,rawq,x['p'],'buy') if rawq else ZERO
            if t:
                rules.retry_open_outcome(t,filled=False,structural_pass=x['structural'],all_in_cost=rawcost,caps=x['caps'])
                self.ticket_event(t,d,'ORIGINAL_OPEN_REJECTION_WHILE_FUNDING_WITHDRAWN',decision=x['reason'])
            self.funding_wait_log.append(dict(day=day(d),request_id=request_id(r),ticket_id=t['ticket_id'] if t else None,
                original_request=copy.deepcopy(r),status=t['status'] if t else 'ORIGINAL_REJECT_NO_TICKET',
                reason=x['reason'],selected_branch_id=decision['selected_branch_id'],new_round_created=False,actual_quantity=0))
            return
        if t is None:
            ident = hashlib.sha256(json.dumps([s,r['birth_type'],r['signal_day'],tuple(r['origin'])]).encode()).hexdigest()[:24]
            t = dict(ticket_id=ident, sid=s, birth_type=r['birth_type'], signal_day=r['signal_day'],
                     nav0=r['nav0'], budget=r['budget'], origin=tuple(r['origin']),
                     original_factor=r['factor'], current_factor=dec(self.d.z(s,d)['adjustment_factor']),
                     original_ifloor=r['ifloor'], ifloor=r['ifloor'], status='RETAINED', ever_seeded=False,
                     plan=None, first_reject_caps=['funding_nondisplacement'], last_verified_day=day(d), event_id=r.get('event_id'))
            self.tickets[s] = t
        assert t['signal_day']==r['signal_day'] and t['nav0']==r['nav0'] and t['budget']==r['budget']
        t['plan'] = None
        if not x['structural']:
            rules.cancel(t, 'RETRY_OPEN_STRUCTURE_FAILED')
            t['funding_original_reason'] = x['reason']
        else:
            t['status']='RETAINED';t['reason']=WAIT
        row = dict(day=day(d), request_id=request_id(r), ticket_id=t['ticket_id'], original_request=copy.deepcopy(r),
                   original_rank=r.get('_ref_rank'), status=t['status'], reason=t['reason'],
                   original_open_check=x['reason'], selected_branch_id=decision['selected_branch_id'],
                   comparisons=[dict(branch_id=e['branch_id'],comparison=e['comparison']) for e in decision['evaluated']],
                   has_lot=False, actual_quantity=0, new_round_created=False)
        self.funding_waits[t['ticket_id']] = row
        self.funding_wait_log.append(row)
        self.ticket_event(t,d,'FUNDING_NONDISPLACEMENT_OUTCOME',decision=t['reason'],original_open_check=x['reason'])

    def execute_selected(self, d, pending, decision):
        if decision is None:
            base.Engine.exit_open(self,d)
            return base.Engine.alloc_open(self,d,pending)
        branch = self.funding_book['branches'][decision['selected_index']]
        selected_pending = self.install(branch, pending)
        included = {request_id(r) for r in selected_pending}
        wait = [r for r in pending if new_seed(r) and request_id(r) not in included]
        before_t, before_o, before_b = len(self.transfers), len(self.orders), len(self.execution_boundary_log)
        base.Engine.exit_open(self,d)
        actual_prefix_cash = str(self.cash)
        actual_prefix_inventory = {s:{l['id']:l['q'] for l in a['lots']} for s,a in self.active.items()}
        actual_prefix_orders = copy.deepcopy(self.orders[before_o:])
        diagnostic=scratch(self,QuoteView(self.d,d));base.Engine.info_open(diagnostic,d)
        actual_prefix_H=diagnostic.health(d,'OPEN',pre_cashflows={k:dec(v) for k,v in decision['common_conditional_prefix']['actual_cashflows'].items()})
        # Lifecycle checks are actual OPEN-known checks, not day CLOSE signals.
        nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()}
        for r in wait:
            x=base.Engine.noncash(self,r,d,'raw_open',nav,sv)
            self.wait_ticket(r,d,decision,x)
        base.Engine.alloc_open(self,d,selected_pending)
        actual_y={r['lot_id']:int(r['executed_q']) for r in self.transfers[before_t:] if r.get('event')=='DONOR_EXECUTION'}
        actual_q={request_id(r):0 for r in self.funding_book['original_requests']}
        lookup={(r['sid'],r['kind'],r['signal_day'],r.get('cp_id')):request_id(r) for r in self.funding_book['original_requests']}
        for order in self.orders[before_o:]:
            if order['side'].startswith('BUY'):
                key=(order['sid'],order['side'][4:],order['signal_day'],order.get('cp_id'))
                if key in lookup:actual_q[lookup[key]]+=int(order['qty'])
        projected=decision['chosen_projection']
        self.funding_actual.append(dict(day=day(d),selected_branch_id=decision['selected_branch_id'],
             diagnostic_only=True,reselected=False,actual_q=actual_q,actual_y=actual_y,
             q_deviation={k:actual_q.get(k,0)-projected['q'].get(k,0) for k in set(actual_q)|set(projected['q']) if actual_q.get(k,0)!=projected['q'].get(k,0)},
             y_deviation={k:actual_y.get(k,0)-projected['y'].get(k,0) for k in set(actual_y)|set(projected['y']) if actual_y.get(k,0)!=projected['y'].get(k,0)},
             actual_prefix_cash=actual_prefix_cash, actual_prefix_inventory=actual_prefix_inventory,
             actual_prefix_H_diagnostic_only=actual_prefix_H,
             actual_prefix_orders=actual_prefix_orders,
             prefix_cash_deviation=str(dec(actual_prefix_cash)-dec(decision['common_conditional_prefix']['predicted_cash_after'])),
             deviation_reasons=(['ORIGINAL_PREFIX_NO_FILL'] if any(v.get('event')=='SELL_NO_FILL' for v in self.execution_boundary_log[before_b:]) else [])
                +(['ORIGINAL_OPTIONAL_NO_FILL'] if any(v.get('event') in ('DONOR_NO_FILL','BUY_NO_FILL') for v in self.execution_boundary_log[before_b:]) else []),
             actual_orders=copy.deepcopy(self.orders[before_o:]),no_fill_events=copy.deepcopy(self.execution_boundary_log[before_b:]),
             actual_cash_after=str(self.cash)))

    def atomic_step(self,d,pending,prev):
        snapshot=copy.deepcopy({k:v for k,v in vars(self).items() if k!='d'})
        p0=copy.deepcopy(pending)
        try:
            targets=sorted(set(self.active)|{r['sid'] for r in pending}|set(self.live_tickets()))
            self.economic_preflight(d,pending)
            self.funding_preflight.append(dict(day=day(d),original_targets=targets,
                original_pending=[dict(sid=r['sid'],request_id=request_id(r)) for r in p0],
                after_native_pending=[dict(sid=r['sid'],request_id=request_id(r)) for r in pending],native_target_diagnostics=copy.deepcopy(self.last_targets)))
            self.accrue(d)
            decision=self.select_open(d,pending)
            self.execute_selected(d,pending,decision)
            return self.close(d,prev)
        except BaseException:
            for k in list(vars(self)):
                if k!='d':delattr(self,k)
            vars(self).update(snapshot)
            pending[:]=p0
            raise

    def run(self,*a,**kw):
        raise RuntimeError('REVIEW_ONLY_NO_HISTORICAL_LAUNCH_APPROVAL')

    def export(self,path):
        path=Path(path).resolve();assert path.is_relative_to(O),'CANDIDATE_OUTPUT_ONLY'
        super().export(path)
        for name,value in [('FUNDING_BRANCH_BOOKS',self.funding_books),('FUNDING_OPEN_DECISIONS',self.funding_decisions),
                ('FUNDING_WAIT_LOG',self.funding_wait_log),('FUNDING_WAIT_STATE',self.funding_waits),
                ('FUNDING_PREFLIGHT',self.funding_preflight),('FUNDING_ACTUAL_DIAGNOSTICS',self.funding_actual)]:
            base.save(path/(name+'.json'),clean(value))
        base.save(path/'OUTPUT_HASHES.json',{p.name:sha(p) for p in path.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})

class ConditionalEngine(Engine):
    def no_fill(self,*a,**kw): return False
    def buy_nofill(self,*a,**kw): return False


def self_check():
    unchanged=['close','exit_open','alloc_open','execute_transfers','noncash','demand','plan_requests','classify_reference',
               'finalize_reference','independent_mature_demand','request_key_groups','order','economic_preflight','info_open',
               'info_close','net','cpvalid','no_fill','buy_nofill','accrue','register_pay','refresh_tickets']
    assert all(getattr(Engine,k) is getattr(base.Engine,k) for k in unchanged)
    assert PLAN_SOURCE.replace('reqs=pending',PLAN_HEAD)==PLAN_ROLE
    assert boolean(np.bool_(True)) is True and boolean(np.bool_(False)) is False
    assert boolean(1) is None and boolean('False') is None
    assert Data is base.Data
    return dict(result='PASS',history_run=False,real_Data_constructed=False,baseline_sha256=BASE_SHA,
                design_sha256=DESIGN_SHA,unchanged_methods=unchanged,projection_no_OHLC=True,
                historical_launcher=False,not_PIT=True)

if __name__=='__main__':print(json.dumps(self_check(),ensure_ascii=False))
