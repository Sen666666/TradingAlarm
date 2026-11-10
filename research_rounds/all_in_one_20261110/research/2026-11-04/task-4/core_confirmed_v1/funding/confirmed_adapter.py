"""One typed CORE confirmed fallback over the unchanged native No60 ledger.

Import only derives pure source functions. It does not load market histories,
construct accounts, or run a path. prepare_sources writes reviewable derivatives.
"""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import inspect
import json
import pickle
import sys
import textwrap
sys.dont_write_bytecode=True

O=Path(__file__).resolve().parent
ROOT=O.parent
POOL=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
sys.path.insert(0,str(POOL))
import native_adapter as A
N,J,L,S,IO=A.N,A.J,A.L,A.S,A.IO
LR=J.LR
POLICY='CORE_CONFIRMED_ZERO_PROBE_SAME_DAY_I_CP'
EXTRA_STREAMS=['core-proof','core-confirmed']
FALLBACK_FAILURES=frozenset({'probe_risk','sector_capital'})

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return J.W.canon(value)
def digest(value):
    return hashlib.sha256(json.dumps(canonical(value),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def replace_once(source,old,new):
    assert source.count(old)==1,('source needle not unique',old)
    return source.replace(old,new)

def dependency_hashes():
    """Bind inherited financial/market leaf sources without loading their inputs."""
    original=J.M.N;ledger=LR.L;market=J.M.E.FastMarket;facts=J.M.E.Facts
    methods=(LR.Account.reserve_quantity,LR.Account.fill_buy,LR.Account.fill_exit,
        LR.Account.split,LR.Account.accrue_dividend,original.HistoryRunner._actions,
        original.HistoryRunner._payments,market.__init__,market.window,market.latest_mark,
        market.marks,market.quote,market.quantity,market.fees,market.source_available,
        LR.preview,LR.protection_risk,LR.maximum_quantity,LR.fees,
        ledger.SectorAccount.__init__,ledger.SectorAccount.fill_buy,ledger.SectorAccount.fill_exit,
        ledger.SectorAccount.balance,ledger.SectorAccount.split,ledger.SectorAccount.accrue_dividend,
        ledger.SectorAccount.pay_dividend,ledger.QuantityRule,ledger.FeeSchedule,
        facts.row,facts.factor,facts.packet,facts.floor,original.checked_ref,original.read_raw,
        original.read_actions,original.eligible_prices,original.boolean_column,
        original.market_identity_on,original.version_on)
    files={Path(inspect.getsourcefile(method)).resolve()for method in methods}
    return {str(path):sha(path)for path in sorted(files)}

# Derive the effective No60 model, retaining original Order/Evidence classes in
# the runtime namespace. Only Contract.request is compiled for the subclass.
ORIGINAL_MODEL_SOURCE=A.P.NEW_MODEL
DERIVED_MODEL_SOURCE=ORIGINAL_MODEL_SOURCE
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 '                core_epoch_locked=False):',
 '                core_epoch_locked=False, typed_core_confirmed=False):')
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 "        assert role in ('core', 'mobile')\n",
 "        assert role in ('core', 'mobile')\n"
 "        if typed_core_confirmed and (probe_request or role != 'core'):\n"
 "            return 'typed_core_confirmed_role_required'\n")
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 '        self.stock_requests.add(oid)  # Failed request is not silently replayed every day.\n',
 '        if not typed_core_confirmed:\n'
 '            self.stock_requests.add(oid)  # Original request semantics.\n')
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 "        if probe_request and role == 'core' and core_epoch_locked: return 'core_epoch_locked'",
 "        if role == 'core' and core_epoch_locked and (probe_request or typed_core_confirmed): return 'core_epoch_locked'")
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 "        if not probe_request and role != 'mobile': return 'mobile_role_required'\n"
 "        if role == 'mobile':\n",
 "        if not probe_request and role != 'mobile' and not typed_core_confirmed: return 'mobile_role_required'\n"
 "        if typed_core_confirmed:\n"
 "            if not getattr(self, 'expand', False) or s.level < 1:\n"
 "                return 'typed_core_confirmed_industry_not_mature'\n"
 "            if any(o.sector == sector and o.attempt == s.attempt and o.pool == 'probe' and o.qty > 0\n"
 "                   and o.status in ('open', 'cancel_pending') for o in self.orders.values()):\n"
 "                return 'typed_core_confirmed_migration_blocked'\n"
 "        if role == 'mobile' or typed_core_confirmed:\n")
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 "            self.consumed.add(stock_token.event_id)\n"
 "        if pool == 'confirmed':\n",
 "            if not typed_core_confirmed:\n"
 "                self.consumed.add(stock_token.event_id)  # Original Mobile timing unchanged.\n"
 "        if pool == 'confirmed' and not typed_core_confirmed:\n")
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 "            if pool == 'confirmed': s.status = 'confirmed_unfunded'\n"
 "            return 'shared_loss_exhausted'",
 "            if pool == 'confirmed' and not typed_core_confirmed: s.status = 'confirmed_unfunded'\n"
 "            return 'shared_loss_exhausted'")
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 "        if failures:\n"
 "            if pool == 'confirmed': s.status = 'confirmed_unfunded'\n"
 "            return ','.join(failures)\n"
 "        self.prices.setdefault(stock, limit)",
 "        if failures:\n"
 "            if pool == 'confirmed' and not typed_core_confirmed: s.status = 'confirmed_unfunded'\n"
 "            return ','.join(failures)\n"
 "        if typed_core_confirmed:\n"
 "            # Read-only migration guards above make failure here an invariant error.\n"
 "            assert self.migrate(sector), 'typed CORE migration changed after validation'\n"
 "        self.prices.setdefault(stock, limit)")
DERIVED_MODEL_SOURCE=replace_once(DERIVED_MODEL_SOURCE,
 "        self.orders[oid].attempt = s.attempt\n"
 "        return 'reserved'",
 "        self.orders[oid].attempt = s.attempt\n"
 "        if typed_core_confirmed:\n"
 "            self.stock_requests.add(oid)\n"
 "            self.consumed.add(stock_token.event_id)  # Commit only after legal reservation.\n"
 "        return 'reserved'")

def request_source(source):
    tree=ast.parse(source)
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef)and x.name=='Contract')
    method=next(x for x in cls.body if isinstance(x,ast.FunctionDef)and x.name=='request')
    return textwrap.dedent(''.join(source.splitlines(True)[method.lineno-1:method.end_lineno]))

DERIVED_REQUEST_SOURCE=request_source(DERIVED_MODEL_SOURCE)
_request_env=dict(A.P.MOD.__dict__)
exec(compile(DERIVED_REQUEST_SOURCE,str(O/'derived_request_typed_core.py'),'exec'),_request_env)
TYPED_REQUEST=_request_env['request']
assert TYPED_REQUEST.__globals__['Order']is A.P.MOD.Order

ORIGINAL_ROUTE_SOURCE=A.P.NEW_ROUTE
ZERO_ROUTE_NEEDLE="  if not q:return None,','.join(sorted(set(sum(reasons.values(),[])))) or 'minimum_unit_not_funded'"
ZERO_ROUTE_HOOK="""  if not q:
   original_reason=','.join(sorted(set(sum(reasons.values(),[])))) or 'minimum_unit_not_funded'
   if role=='core' and original_reason and set(original_reason.split(','))<=FALLBACK_FAILURES:
    return self.core_confirmed_fallback(a,i,x,at,original_reason)
   return None,original_reason"""
DERIVED_ROUTE_SOURCE=replace_once(ORIGINAL_ROUTE_SOURCE,ZERO_ROUTE_NEEDLE,ZERO_ROUTE_HOOK)
_route_env=dict(J.__dict__);_route_env['FALLBACK_FAILURES']=FALLBACK_FAILURES
exec(compile(DERIVED_ROUTE_SOURCE,str(O/'derived_route_confirmed_fallback.py'),'exec'),_route_env)
CONFIRMED_ROUTE=_route_env['route']
assert DERIVED_ROUTE_SOURCE.replace(ZERO_ROUTE_HOOK,ZERO_ROUTE_NEEDLE)==ORIGINAL_ROUTE_SOURCE

class ConfirmedCoreBudget(A.NoConfirmed60Budget):
    request=TYPED_REQUEST

def prepare_sources():
    """Write only finite source derivatives/diffs, without account/input loading."""
    O.mkdir(parents=True,exist_ok=True)
    sources={
        'derived_model_typed_core.py':DERIVED_MODEL_SOURCE,
        'derived_request_typed_core.py':DERIVED_REQUEST_SOURCE,
        'derived_route_confirmed_fallback.py':DERIVED_ROUTE_SOURCE,
    }
    for name,value in sources.items():
        path=O/name
        if path.exists():assert path.read_text()==value,('Existing derived source differs',str(path))
        else:path.write_text(value)
    diff=''.join(difflib.unified_diff(ORIGINAL_MODEL_SOURCE.splitlines(True),DERIVED_MODEL_SOURCE.splitlines(True),
                                   fromfile='effective_No60_model',tofile='typed_CORE_model'))
    diff+=''.join(difflib.unified_diff(ORIGINAL_ROUTE_SOURCE.splitlines(True),DERIVED_ROUTE_SOURCE.splitlines(True),
                                    fromfile='effective_No60_route',tofile='zero_probe_hook_route'))
    (O/'SOURCE_DIFF.patch').write_text(diff)
    value=dict(policy=POLICY,account_constructions=0,market_histories_loaded=0,adapter_sha256=sha(__file__),
               runtime_Order_is_original=True,probe_zero_hook_count=1,
               original_model_sha256=hashlib.sha256(ORIGINAL_MODEL_SOURCE.encode()).hexdigest(),
               original_route_sha256=hashlib.sha256(ORIGINAL_ROUTE_SOURCE.encode()).hexdigest(),
               derivatives={n:sha(O/n)for n in sources},inherited_dependency_sha256=dependency_hashes(),
               inherited_dependency_identity_scope='Current leaf SHA closure; prior full OFF leaf SHA agreement is not asserted by this adapter.')
    (O/'SOURCE_DERIVATION.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    return value

def _resource_view(a,sector,token_id=None):
    b=a.budget;s=b.sectors.get(sector)
    return canonical(dict(available=a.available,decision_NAV=a.current_nav,budget_cash=b.cash,budget_NAV=b.nav,
        global_resources=b.resources(),probe_resources=b.resources('probe'),confirmed_resources=b.resources('confirmed'),
        sector_resources=b.resources(sector=sector),pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values()if o.status in('open','cancel_pending')),
        sector_state=dict(active=s.active,level=s.level,status=s.status,episode=s.episode,attempt=s.attempt)if s else None,
        lots_quantity={str(l.batch):l.qty for l in b.lots},lots_pool={str(l.batch):l.pool for l in b.lots},
        live_order_quantity={oid:o.qty for oid,o in b.orders.items()if o.qty>0 and o.status in('open','cancel_pending')},
        token_consumed=token_id in b.consumed if token_id else None,stock_request_count=len(b.stock_requests)))

class Runner(A.Runner):
    def __init__(self,*args,core_confirmed_mode='OFF',**kwargs):
        assert core_confirmed_mode in('OFF','ON')
        self.core_confirmed_mode=core_confirmed_mode
        self._core_confirmed_bootstrap=True
        self.core_proof_log=[];self.core_confirmed_log=[]
        super().__init__(*args,**kwargs)
        if core_confirmed_mode=='ON':
            for a in self.accounts.values():a.budget.__class__=ConfirmedCoreBudget
        self._core_confirmed_bootstrap=False
        self.integration_policy=POLICY+':'+self.rank_mode+':'+self.core_confirmed_mode
        self.assert_native_wiring()

    def assert_native_wiring(self):
        cap_bootstrap=getattr(self,'_cap_bootstrap',False)
        own_bootstrap=getattr(self,'_core_confirmed_bootstrap',False)
        expected=(N.POLICY if cap_bootstrap else A.POLICY)+':'+self.rank_mode if own_bootstrap else POLICY+':'+self.rank_mode+':'+self.core_confirmed_mode
        assert self.integration_policy==expected
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is Runner.planning
        assert self.route.__func__ is Runner.route
        for a in self.accounts.values():
            expected_budget=N.BASE.NoAccountBudget if cap_bootstrap else A.NoConfirmed60Budget if own_bootstrap or self.core_confirmed_mode=='OFF'else ConfirmedCoreBudget
            assert type(a)is J.Account and type(a.budget)is expected_budget
            if not cap_bootstrap:
                assert a.budget.request.__func__ is (TYPED_REQUEST if not own_bootstrap and self.core_confirmed_mode=='ON'else A.P.MOD.Contract.request)
                assert a.budget.migrate.__func__ is A.NoConfirmed60Budget.migrate
            for name in('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)

    def planning(self,at):
        N.Runner.planning(self,at)
        if self.core_confirmed_mode=='OFF':return
        day=str(at.date())
        for a in self.accounts.values():
            for i in a.pending:
                if i['role']!='core':continue
                assert i['kind']=='core'and i['clock'].decision_at==at
                sid=i['sid'];row=self.facts.row(sid,at)
                sector=self.sector_by_sid[sid];industry=a.budget.sectors.get(sector)
                cp=self.receipts.get(sid,{}).get(day)
                frozen=dict(policy=POLICY,account=a.label,sid=sid,signal_day=day,epoch=list(i['epoch']),
                    sector=sector,industry_episode=industry.episode if industry else None,
                    industry_attempt=industry.attempt if industry else None,
                    industry_level=industry.level if industry else None,
                    source_segment=int(row.segment_id),i_target=bool(row.i_target),i_buy=bool(row.i_buy),
                    e0_target=bool(row.e0_target),G1_ready=bool(row.g_ready),G1_grade=float(row.g_grade),
                    ACT_on=bool(a.risk_state['on']),canonical_receipt=copy.deepcopy(cp))
                frozen['receipt_sha256']=digest(cp)if cp is not None else None
                frozen['proof_sha256']=digest(frozen)
                i['_confirmed_core_cp']=frozen
                self.core_proof_log.append(canonical(dict(account=a.label,at=at,sid=sid,role='core',
                    signal_day=day,epoch=i['epoch'],source_segment=frozen['source_segment'],
                    sector=sector,industry_episode=frozen['industry_episode'],industry_attempt=frozen['industry_attempt'],
                    industry_level=frozen['industry_level'],
                    receipt_id=cp.get('receipt_id')if cp else None,receipt_sha256=frozen['receipt_sha256'],
                    proof_sha256=frozen['proof_sha256'],CP_present=cp is not None)))

    def route(self,a,i,x,at):
        if self.core_confirmed_mode=='OFF':return A.P.ROUTES[True](self,a,i,x,at)
        return CONFIRMED_ROUTE(self,a,i,x,at)

    def core_confirmed_fallback(self,a,i,x,at,original_reason):
        """One read-only eligibility/quantity pass, then one typed reservation."""
        b=a.budget;sid=i['sid'];sector=self.sector_by_sid[sid];s=b.sectors.get(sector)
        frozen=i.get('_confirmed_core_cp');cp=frozen.get('canonical_receipt')if isinstance(frozen,dict)else None
        token_id=cp.get('receipt_id')if isinstance(cp,dict)else None
        before=_resource_view(a,sector,token_id)
        log=dict(account=a.label,at=at,signal_day=str(i['clock'].decision_at.date()),sid=sid,role='core',
                 probe_result=original_reason,probe_failures=original_reason.split(','),before=before,
                 original_frozen_cap=i['cap'],original_frozen_budget=i['budget'],original_risk_budget=i['risk_budget'],
                 preview_maxq=x['maxq'],I_floor_adjusted=i['floor'],I_floor_raw=x['floor'],known_OPEN=x.get('known_open'),
                 receipt_id=token_id,proof_sha256=frozen.get('proof_sha256')if isinstance(frozen,dict)else None)
        def reject(reason):
            log.update(result='not_reserved',fallback_reason=reason,after=_resource_view(a,sector,token_id))
            assert log['before']==log['after'],('Failed typed fallback changed resource prefix',sid,reason)
            self.core_confirmed_log.append(canonical(log))
            return None,original_reason
        if not original_reason or not set(original_reason.split(','))<=FALLBACK_FAILURES:return reject('probe_failure_set_not_eligible')
        if i['role']!='core'or i['kind']!='core':return reject('original_CORE_required')
        if a.quantity(sid)or sid in a.buys or sid in a.exits:return reject('original_flat_or_pending_conflict')
        if a.core_epoch.get(sid)==i['epoch']:return reject('core_epoch_locked')
        if not s or not s.active or not b.expand or s.level<1:return reject('industry_not_confirmed')
        if any(o.sector==sector and o.attempt==s.attempt and o.pool=='probe'and o.qty>0 and o.status in('open','cancel_pending')for o in b.orders.values()):
            return reject('same_attempt_probe_order_blocks_migration')
        if not isinstance(frozen,dict)or not isinstance(cp,dict):return reject('no_frozen_signal_CP')
        unhashed={k:v for k,v in frozen.items()if k!='proof_sha256'}
        if frozen.get('proof_sha256')!=digest(unhashed)or frozen.get('receipt_sha256')!=digest(cp):return reject('frozen_CP_hash_mismatch')
        signal_day=str(i['clock'].decision_at.date());bar=J.ordinal(signal_day)
        if frozen.get('sid')!=sid or frozen.get('signal_day')!=signal_day or tuple(frozen.get('epoch',()))!=tuple(i['epoch']):return reject('frozen_CORE_clock_or_epoch_mismatch')
        if frozen.get('sector')!=sector or frozen.get('industry_episode')!=s.episode or frozen.get('industry_attempt')!=s.attempt:
            return reject('frozen_industry_episode_or_attempt_mismatch')
        if not all(frozen.get(k)is True for k in('i_target','i_buy','e0_target','G1_ready','ACT_on'))or frozen.get('G1_grade',float('-inf'))<2:return reject('original_CORE_qualification_not_frozen')
        if str(frozen.get('source_segment'))!=str(i['epoch'][0]):return reject('CORE_source_epoch_mismatch')
        if cp.get('canonical_series')!=sid or cp.get('confirmed_day')!=signal_day or cp.get('trace_unknown')!=[]:return reject('canonical_CP_identity_or_unknown')
        if str(cp.get('source_segment'))!=str(frozen['source_segment'])or not str(cp.get('scale_id','')).startswith('CP1-original:'):return reject('CP_source_or_scale_mismatch')
        if not cp.get('receipt_id')or not cp.get('original_E0_episode_id'):return reject('canonical_CP_fields_missing')
        try:
            start=J.ordinal(cp['formation_start_exclusive']);end=J.ordinal(cp['formation_end_inclusive'])
        except (KeyError,TypeError,ValueError):return reject('CP_formation_clock_unknown')
        if not start<=end<=bar:return reject('CP_formation_after_signal')
        token=J.V.Evidence(token_id,sector,'stock_cp1','21',start,end,bar,s.episode,sid,s.attempt)
        if not b.valid(token,'stock_cp1',bar)or token_id in b.consumed:return reject('CP_invalid_or_consumed')
        assert not getattr(a,'_budget_sync_pending',False),'cannot admit during unacknowledged ledger callback'
        assert i['cap']>=x['maxq']>0 and i['budget']>=J.D(x['maxq'])*x['price']
        assert LR.protection_risk(x['maxq'],x['price'],x['floor'],x['schedule'],i['quote'].par_value)<=i['risk_budget']
        _,_,reserve=b.resources();sc,sr,_=b.resources(sector=sector)
        pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values()if o.status in('open','cancel_pending'))
        p=float(x['price']);floor=float(x['floor']);frac=(.02,.1,.2)[s.level]
        known_open=x.get('known_open',x['price']/(J.D(1)+LR.SLIP));held_at_open=float(a.quantity(sid))*float(known_open)
        def detail(q):
            fee=float(LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value));nav=b.nav-pending_fees-fee
            cap=q*p;risk=q*max(0.,p-floor);fails=[]
            if cap+fee>min(float(a.available-a.current_nav*J.D('.1')),b.cash-reserve)+1e-9:fails.append('cash_or_original_reserve')
            if sc+cap>frac*nav+1e-9:fails.append('sector_capital')
            if sr+risk>.01*nav+1e-9:fails.append('sector_risk')
            if held_at_open+cap>.10*float(a.current_nav)+1e-9:fails.append('stock_capital')
            return dict(quantity=q,fee=fee,budget_NAV=nav,capital=cap,nominal_risk=risk,
                        industry_capital_limit=frac*nav,industry_risk_limit=.01*nav,
                        cash_after_original_reserve=min(float(a.available-a.current_nav*J.D('.1')),b.cash-reserve),failures=fails)
        min_detail=detail(x['rule'].buy_minimum)
        q=LR.maximum_quantity(x['rule'],x['maxq'],lambda n:not detail(n)['failures'])
        log.update(minimum=min_detail,confirmed_quantity=q,confirmed_detail=detail(q)if q else None,
                   CP_token=canonical(token),receipt_sha256=frozen['receipt_sha256'])
        if not q:return reject('confirmed_minimum_not_funded')
        fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value)
        bid=f"{a.label}|{i['clock'].decision_at.isoformat()}|{sid}|core"
        result=b.request(bid,sid,sector,q,p,floor,token,bar,float(fee/J.D(q)),probe_request=False,role='core',
                         order_expiry_bar=J.ordinal(at.date()),core_epoch_locked=a.core_epoch.get(sid)==i['epoch'],typed_core_confirmed=True)
        assert result=='reserved',('Typed CORE request failed after pure eligibility/quantity validation',bid,result)
        a.pools_from_model()
        # Only this successfully reserved new branch binds the actual CP proof
        # to native journal callbacks. Kind/role/I floor/epoch remain CORE.
        i.update(budget_order=bid,pool='confirmed',_confirmed_core_receipt_id=token_id,
                 CP1_id=token_id,CP1_trace=copy.deepcopy(cp))
        log.update(result='reserved',fallback_reason=None,budget_order=bid,pool='confirmed',shares=q,price=x['price'],fees=fee,
                   after=_resource_view(a,sector,token_id))
        self.core_confirmed_log.append(canonical(log))
        return(q,'confirmed'),None

    def restore(self,path):
        saved=pickle.loads(Path(path).read_bytes())
        assert saved['runner']['core_confirmed_mode']==self.core_confirmed_mode
        return super().restore(path)

    def dump_joint(self,path):
        super().dump_joint(path)
        IO.write_gzip_jsonl(Path(path)/'core-proof.jsonl.gz',self.core_proof_log)
        IO.write_gzip_jsonl(Path(path)/'core-confirmed.jsonl.gz',self.core_confirmed_log)

def source_freeze():
    result=A.source_freeze()
    result.update(dependency_hashes())
    for path in [Path(__file__),ROOT/'PROTOCOL.txt',O/'derived_model_typed_core.py',O/'derived_request_typed_core.py',
                 O/'derived_route_confirmed_fallback.py',O/'SOURCE_DIFF.patch',O/'SOURCE_DERIVATION.json']:
        result[str(path.resolve())]=sha(path)
    return result

if __name__=='__main__':raise SystemExit('Adapter only. Use reviewed run_confirmed staged entrypoints.')
