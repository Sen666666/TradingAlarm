"""Pure OPEN proposal only. No Account/Runner construction or order callbacks.

Uses the frozen native buy preview, quantity, fee and exit-lock formula. Parent
CLOSE authority and all real commitments are immutable inputs. Conditional
sales are NOT cancellations, real releases or spendable money.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace as NS
from dataclasses import asdict
import copy, hashlib, json, sys

HERE=Path(__file__).resolve().parent
RR=HERE.parent
sys.path.insert(0,str(RR/'g-s-C-native-synthetic-v3-20261102'))
import native_c as N
from policy import ExitLock
Z=D(0); ONE=D(1)
EXCHANGE_TIMEZONE='Asia/Shanghai'  # Explicit fixed A-share exchange-day clock.

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def instant(x):
    t=datetime.fromisoformat(x)
    if t.utcoffset() is None: raise ValueError('aware clock required')
    return t
def exchange_session_day(x):
    return instant(x).astimezone(ZoneInfo(EXCHANGE_TIMEZONE)).date().isoformat()
def require(v,why):
    if not v: raise ValueError(why)
def sealed(out):
    out=json.loads(json.dumps(out,default=str))
    out['proposal_id']=digest(out)
    return out
def schedule(s):
    return N.T.FeeSchedule(s['schedule_id'],tuple(N.T.FeeComponent(**c) for c in s['components']))
def fee(q,p,s,side,paid=None,accrued=None):
    return sum(schedule(s).incremental(side,D(q)*p,{k:D(v) for k,v in (paid or {}).items()},
        {k:D(v) for k,v in (accrued or {}).items()},ONE,shares=q,par_value=ONE).values(),Z) if q else Z

def authority_remaining(parent,sid,state):
    """Pending is a subset of remaining authority, never subtracted twice."""
    q=parent['Q'][sid]
    for k in ('filled','permanent_reduction','pending'):
        require(type(state[k]) is int and state[k]>=0,'invalid authorization quantity')
    total=q-state['filled']-state['permanent_reduction']
    require(total>=state['pending'],'pending exceeds total remaining authority')
    return dict(total_remaining=total,pending_commitment=state['pending'],new_quantity_cap=total-state['pending'])

def verified(x,expected_sha256):
    require(digest(x)==expected_sha256,'trusted input body changed')
    p=x['parent'];body={k:v for k,v in p.items() if k!='certificate_id'}
    require(digest(body)==p['certificate_id']==x['trusted_parent_id'],'untrusted parent certificate')
    t=instant(x['at']);c=instant(p['known_at'])
    require(c<t<=instant(p['deadline']),'original parent execution interval')
    require(x['decision_nav']==x['state']['decision_nav'],'decision NAV identity')
    for d in x['demands']:
        sid=d['sid'];require(sid in p['Q'] and p['Q'][sid]>0,'new receiver outside parent Q')
        b=d['receipt'];require(b==p['receipt_bindings'][sid],'receipt replaced')
        require(b['sid']==sid and instant(b['start'])<=instant(b['end'])<=instant(b['confirmed'])==c,'original receipt clock')
        require(b['deadline']==p['deadline']==d['deadline'],'receipt deadline changed')
        require(d['role']=='mobile' and d['pool']=='confirmed','new role/pool outside C authority')
        require(d['use'] in ('G','S'),'new use outside C authority')
        require(d['priority']==x['frozen_priority'][sid],'OPEN reranking forbidden')
        authority_remaining(p,sid,d['authority'])
        require(type(d['authority']['order_bound']) is bool,'missing original order binding state')
        pending=x['state']['pending_orders'].get(sid)
        require(d['authority']['pending']==(pending['remaining_shares'] if pending else 0),'pending authority/native quantity mismatch')
        if pending:
            require(pending['parent_id']==p['certificate_id'] and pending['receipt_id']==b['event_id'],'pending order parent/receipt mismatch')
            require(sum(r['qty'] for r in x['state']['pending_rows'] if r['id']==pending['order_id'])==pending['remaining_shares'],'pending resource row quantity mismatch')
    require(len({d['sid'] for d in x['demands']})==len(x['demands']),'duplicate receiver')
    require({d['sid'] for d in x['demands']}=={s for s,q in p['Q'].items() if q},'parent receiver omitted')
    sums={}
    for d in x['donors']:
        require(d['layer'] in x['parent_D_layers'],'new donor layer')
        require(d['original_cap']==x['parent_D_layers'][d['layer']],'donor layer cap changed')
        require(0<=d['max_remaining']<=d['original_cap'],'D quantity above original')
        sums[d['sid']]=sums.get(d['sid'],0)+d['original_cap']
        require(d['role']=='mobile','core cannot be opportunity donor')
    require(all(q<=p['D'].get(s,0) for s,q in sums.items()),'stock D above parent')
    return t

def quote_unknown(x):
    need={r['sid'] for r in x['state']['lots']}|{d['sid'] for d in x['demands']}|{d['sid'] for d in x['donors']}
    out=[]
    if x['quote_session']!=exchange_session_day(x['at']):
        return ['proposal:declared_exchange_session_mismatch']
    for sid in sorted(need):
        q=x['quotes'].get(sid)
        if not q:out.append(sid+':missing');continue
        # Deliberately no full-day validity, volume, H/L/C or fill-window field.
        fields={'price','known_at','session','source','kind'}
        if set(q)-fields:raise ValueError('quote schema contains non-quote fields')
        if fields-set(q):out.append(sid+':unknown_quote_fields');continue
        if q['kind']!='current_open_print' or q['session']!=x['quote_session']:out.append(sid+':stale_or_nonquote');continue
        try:
            known=instant(q['known_at'])
        except (TypeError,ValueError):
            out.append(sid+':unknown_quote_clock');continue
        if known>instant(x['at']):out.append(sid+':future');continue
        if exchange_session_day(q['known_at'])!=x['quote_session']:
            out.append(sid+':quote_timestamp_exchange_session_mismatch');continue
        if q['price'] is None or not D(q['price']).is_finite() or D(q['price'])<=0 or not q['source']:out.append(sid+':invalid')
    for z in x['state']['lots']:
        if z['floor'] is None:out.append(str(z['id'])+':unknown_held_floor')
        for e in z['locks']:
            if e['q0'] is None or e['e0'] is None or not e['h']:out.append(e['eid']+':unknown_exit_lock')
    for d in x['demands']:
        if d['floor'] is None:out.append(d['sid']+':unknown_receiver_floor')
        for k in ('i_valid','stock_q','permission_valid'):
            if type(d[k]) is not bool:out.append(d['sid']+':unknown_'+k)
    return out

def actual_rows(x):
    rows=[]
    for z in x['state']['lots']:
        m=D(x['quotes'][z['sid']]['price']);f=D(z['floor']);locked=sum(e['remaining'] for e in z['locks'])
        require(locked<=z['qty'],'overlapping real exit locks')
        parts={}
        for e in z['locks']:
            args=copy.deepcopy(e)
            for k in ('q0','e0','ratio'):args[k]=None if args[k] is None else D(args[k])
            parts[e['eid']]=ExitLock(**args).charge(m,f)
        risk=D(z['qty']-locked)*max(Z,m-f)+sum(parts.values(),Z)
        rows.append(dict(id=z['id'],sid=z['sid'],sector=z['sector'],pool=z['pool'],role=z['role'],qty=z['qty'],
            mark=m,floor=f,capital=z['qty']*m,risk=risk,reserve=Z,lock_charges=parts))
    for r in x['state']['pending_rows']:rows.append({k:(D(v) if k in ('capital','risk','reserve') else v) for k,v in r.items()})
    return rows

def donor_plan(x,amounts):
    """Only conditional fills of specified old layers; no shadow cancellation."""
    require(donor_prefix_ok(x,amounts),'D violates original same-stock layer prefix')
    ds={d['layer']:d for d in x['donors']};lots={z['id']:z for z in x['state']['lots']};groups={};parts=[]
    for lid,q in amounts.items():
        d=ds[lid];require(type(q) is int and 0<=q<=min(d['max_remaining'],d['sellable_qty']),'D outside remaining/sellable original layer')
        if not q:continue
        z=lots[lid];require(not d['mixed_mandatory'],'UNSUPPORTED_MIXED_PARTIAL_COORDINATION')
        require(q<=sum(e['remaining'] for e in z['locks'] if e['eid'] in d['lock_ids']),'D exceeds original live opportunity locks')
        groups.setdefault(d['sid'],[]).append((lid,q,d))
    charges={r['id']:r for r in actual_rows(x)}
    for sid,gs in groups.items():
        n=sum(q for _,q,_ in gs);d=gs[0][2];p=D(x['quotes'][sid]['price'])*(ONE-N.LR.SLIP)
        ff=fee(n,p,d['fees'],'sell',d['paid'],d['accrued']);allocated=Z
        for ix,(lid,q,dd) in enumerate(gs):
            z=lots[lid];left=q;release=Z
            for e in z['locks']:
                if e['eid'] not in dd['lock_ids']:continue
                k=min(left,e['remaining']);left-=k
                release+=charges[lid]['lock_charges'][e['eid']]*D(k)/e['remaining']
            require(left==0,'missing original lock tranche')
            f=ff-allocated if ix==len(gs)-1 else ff*D(q)/n;allocated+=f
            parts.append(dict(layer=lid,sid=sid,q=q,risk_release=release,capital=D(q)*D(x['quotes'][sid]['price']),net=D(q)*p-f,fee=f))
    return parts

def donor_prefix_ok(x,amounts):
    ds={d['layer']:d for d in x['donors']};seen={}
    if any(lid not in ds for lid in amounts):return False
    for lid in x['frozen_donor_order']:
        d=ds[lid];q=amounts.get(lid,0)
        if q and any(amounts.get(old,0)<min(ds[old]['max_remaining'],ds[old]['sellable_qty']) for old in seen.get(d['sid'],[])):return False
        seen.setdefault(d['sid'],[]).append(lid)
    return True

class QuoteView:
    """Read-only arguments for audited native _preview; not a financial ledger."""
    _preview=N.Account._preview
    def __init__(self,x,Dmap):
        self.x=x;self.rows=actual_rows(x);by={r['id']:r for r in self.rows};self.parts=donor_plan(x,Dmap)
        self.available=D(x['state']['available'])-D(x['state']['other_goal_cash_encumbrance'])
        self.equity=D(x['state']['non_inventory_equity'])+sum((r['capital'] for r in self.rows if isinstance(r['id'],int)),Z)
        for p in self.parts:
            r=by[p['layer']];r['qty']-=p['q'];r['capital']-=p['capital'];r['risk']-=p['risk_release']
            self.available+=p['net'];self.equity+=p['net']-p['capital']
        self.policy=NS(nd=D(x['decision_nav']),consumed=set(x['state']['consumed_receipts']),locks={e['eid']:NS(**e) for z in x['state']['lots'] for e in z['locks'] if e['remaining']},
            allowed=lambda scope,use,holding=False:x['permissions'].get(scope,{}).get(('holding_' if holding else '')+use,False),
            targets=lambda sec:D(x['industry_targets'].get(sec,0)))
        self.market=NS(prices={s:D(q['price']) for s,q in x['quotes'].items()},
            quantity=lambda sid,at:N.T.QuantityRule(**x['specs'][sid]['quantity']),fees=lambda sid,at:schedule(x['specs'][sid]['fees']))
        self.facts=NS(factor=lambda sid,at:ONE)
        self.buys={k:NS(**{**v,'fee_reserved_cny':D(v['fee_reserved_cny'])}) for k,v in x['state']['pending_orders'].items()}
        self.exits={s:True for s in x['state']['receiver_responsibilities']};self.core_epoch={};self.supports={};self.retained={}
        self.pendingfees=sum((o.fee_reserved_cny for o in self.buys.values()),Z);self.new=[]
    def resources(self,**kw):return copy.deepcopy(self.rows)
    def totals(self,rows):return {k:sum((r[k] for r in rows),Z) for k in ('capital','risk','reserve')}
    def nav(self,at):return self.equity
    def receipt_verified(self,c):return c.event_id in {d['receipt']['event_id'] for d in self.x['demands']}
    def quantity(self,sid):return sum(r.get('qty',0) for r in self.rows if r['sid']==sid and isinstance(r['id'],int))
    def intent(self,d):
        b=d['receipt'];c=N.HistoricalReceipt(b['event_id'],d['sid'],instant(b['start']),instant(b['end']),instant(b['confirmed']),tuple(b['structure']),source=b['source'],payload_json='{}',payload_sha256=b['payload_sha256'],source_binding=b['source_binding'],scale=b['scale'])
        return dict(sid=d['sid'],sector=d['sector'],i_valid=d['i_valid'],stock_q=d['stock_q'],core=False,receipt=c,
            I_floor=D(d['floor']),cp_floor=D(d['floor']),epoch=c.structure,clock=NS(decision_at=instant(self.x['parent']['known_at'])))
    def preview(self,d,cap):
        if not d['permission_valid']:return dict(q=0,why=['original_permission_ended'])
        if d['authority']['pending']:return dict(q=0,why=['existing_pending_order_kept_separately'])
        if d['authority']['order_bound']:return dict(q=0,why=['original_certificate_already_bound_no_second_order'])
        return self._preview(self.intent(d),d['use'],'mobile',instant(self.x['at']),cap=cap)
    def reserve_shadow(self,d,q):
        if not q:return
        p=self.market.prices[d['sid']]*(ONE+N.LR.SLIP);f=fee(q,p,d['fees'],'buy');gross=D(q)*p
        self.available-=gross+f;self.pendingfees+=f
        self.buys[d['sid']]=NS(order_id='PROPOSAL|'+d['sid'],fee_reserved_cny=f)
        self.rows.append(dict(id='PROPOSAL|'+d['sid'],sid=d['sid'],sector=d['sector'],pool='confirmed',role='mobile',qty=q,capital=gross,risk=D(q)*max(Z,p-D(d['floor'])),reserve=gross+f))
        self.new.append((d,q,p,f))
    def residuals(self):
        # Same resource constraints at final reservation boundary; no simulated fill.
        bn=self.equity-self.pendingfees;nd=D(self.x['decision_nav']);tot=self.totals(self.rows)
        out={'cash_reserve10':self.available-nd*D('.1'),'account_capital90':bn*D('.9')-tot['capital'],'account_risk6':bn*D('.06')-tot['risk']}
        for d,q,p,f in self.new:
            sec=[r for r in self.rows if r['sector']==d['sector']];stk=[r for r in self.rows if r['sid']==d['sid']]
            out[d['sid']+':industry_target']=D(d['industry_target'])-sum((r['capital'] for r in sec),Z)
            out[d['sid']+':sector_risk5']=bn*D('.05')-sum((r['risk'] for r in sec),Z)
            out[d['sid']+':stock10']=nd*D('.1')-sum((r['capital'] for r in stk),Z)
        return out

def proposal(x,*,expected_sha256,enabled=True,max_checks=250000):
    before=digest(x);verified(x,expected_sha256);unknown=quote_unknown(x)
    common=dict(schema='QUOTE_ONLY_OPEN_PROPOSAL_V1',parent=x['parent']['certificate_id'],at=x['at'],input_sha256=before,
        enabled=enabled,financial_events=0,submit_allowed=False,order_mutations=0,receipt_consumed=False,
        actual_releases=dict(cash='0',risk='0'),mandatory_exit_action='CONTINUE_ORIGINAL_OBLIGATIONS',retained_pending=copy.deepcopy(x['state']['pending_orders']))
    common['Q_semantics']='NEW_QUANTITY_ONLY; existing pending commitments retained separately'
    common['mandatory_exit_obligations']=[copy.deepcopy(e) for z in x['state']['lots'] for e in z['locks'] if e['reason']!='actionable_S_funding' and e['remaining']]
    if unknown:return sealed(dict(common,state='UNKNOWN',unknown=unknown,Q=None,D=None,freeze_quantity_caps=False))
    caps={d['sid']:authority_remaining(x['parent'],d['sid'],d['authority']) for d in x['demands']}
    common['authority_remaining']=caps
    if any(d['mixed_mandatory'] for d in x['donors']):return sealed(dict(common,state='UNSUPPORTED_MIXED_PARTIAL_COORDINATION',Q=None,D=None,freeze_quantity_caps=False))
    ds=sorted(x['demands'],key=lambda d:(d['priority'],d['sid']));donors={d['layer']:d for d in x['donors']};order=x['frozen_donor_order']
    require(set(order)==set(donors),'frozen donor order mismatch')
    Q={d['sid']:0 for d in ds};Dmap={};checks=0;trace=[]
    if enabled and not x['state']['pending_orders']:
        full={lid:min(d['max_remaining'],d['sellable_qty']) for lid,d in donors.items()}
        vv=QuoteView(x,full);minimum_old_risk=sum((r['risk'] for r in vv.rows),Z)
        maximum_equity=D(x['state']['non_inventory_equity'])+sum((r['capital'] for r in actual_rows(x) if isinstance(r['id'],int)),Z)
        if minimum_old_risk>maximum_equity*D('.06'):
            out=dict(common,state='NO_LEGAL_RECIPIENTS',Q=Q,D={},freeze_quantity_caps=True,
                bound=dict(minimum_old_risk=minimum_old_risk,frictionless_upper_risk_capacity=maximum_equity*D('.06')),
                checks=0,actual_resource_totals={k:sum((r[k] for r in actual_rows(x)),Z) for k in ('capital','risk','reserve')},
                cancel_ack_required={d['layer']:d['submitted_unacked'] for d in x['donors'] if d['submitted_unacked']},
                conditional_projection_is_not_cancellation=True,other_goal_commitments_preserved=True)
            return sealed(out)
    def test(qmap,dm):
        nonlocal checks
        checks+=1
        if checks>max_checks:raise RuntimeError('technical quote-check bound; no approximate proposal')
        if not donor_prefix_ok(x,dm):return False,None,{'why':['original_same_stock_layer_prefix']}
        v=QuoteView(x,dm)
        for d in ds:
            q=qmap.get(d['sid'],0)
            if q:
                z=v.preview(d,q)
                if z['q']<q:return False,v,z
                v.reserve_shadow(d,q)
        ok=not any(z<0 for z in v.residuals().values()) if any(qmap.values()) else True
        return ok,v,None
    if not enabled:
        Dmap={lid:d['max_remaining'] for lid,d in donors.items() if d['max_remaining']}
        v=QuoteView(x,Dmap);previews={}
        for d in ds:
            z=v.preview(d,caps[d['sid']]['new_quantity_cap']);Q[d['sid']]=z['q'];previews[d['sid']]={k:z[k] for k in ('q','why')}
            v.reserve_shadow(d,z['q'])
        return sealed(dict(common,state='OFF_ORIGINAL_D_AND_NATIVE_BUY_PREVIEW',Q=Q,D=Dmap,previews=previews,residuals=v.residuals(),conditional_parts=v.parts,checks=0,freeze_quantity_caps=False))
    # Original priority and weaker-donor prefix search, strictly within parent Q/D.
    # No unlimited selector and no future fill/window function is called.
    for d in ds:
        sid=d['sid'];best=0;bestD=dict(Dmap);last=None
        def attempt(dm):
            nonlocal best,bestD,last
            # Prior quantities are fixed; native preview gives a necessary upper.
            ok,v,why=test(Q,dm)
            if not ok:return
            z=v.preview(d,caps[sid]['new_quantity_cap']);q=z['q'];last={k:z.get(k) for k in ('q','why')}
            rule=N.T.QuantityRule(**d['quantity'])
            while q>best:
                qq=dict(Q);qq[sid]=q;good,_,_=test(qq,dm)
                if good:best=q;bestD=dict(dm);return
                q=rule.buy_floor(q-rule.buy_step)
        attempt(Dmap)
        prefix=dict(Dmap)
        for lid in order:
            if best==caps[sid]['new_quantity_cap']:break
            old=donors[lid]
            if old['sid']==sid or any(q and s==old['sid'] for s,q in Q.items()):continue
            step=N.T.QuantityRule(**old['quantity']).sell_step;top=min(old['max_remaining'],old['sellable_qty'])
            values=range((prefix.get(lid,0)//step+1)*step,top+1,step)
            for n in values:
                trial=dict(prefix);trial[lid]=n;attempt(trial)
                if best==caps[sid]['new_quantity_cap']:break
            prefix[lid]=top
        Q[sid]=best;Dmap=bestD
        # Restore original stronger donor first, unit by unit, for fixed Q.
        for lid in reversed(order):
            step=N.T.QuantityRule(**donors[lid]['quantity']).sell_step
            while Dmap.get(lid,0):
                previous=Dmap[lid];trial=dict(Dmap);trial[lid]=max(0,previous-step)
                if not test(Q,trial)[0]:break
                Dmap=trial
        trace.append(dict(sid=sid,q=best,D=dict(Dmap),native_preview=last))
    Dmap={lid:q for lid,q in Dmap.items() if q} if any(Q.values()) else {}
    ok,v,_=test(Q,Dmap);require(ok,'final joint proposal invalid')
    sent={d['layer']:d['submitted_unacked'] for d in x['donors'] if d['submitted_unacked']}
    pending_cancel={lid:sent[lid]-Dmap.get(lid,0) for lid in sent if sent[lid]>Dmap.get(lid,0)}
    out=dict(common,state='CONDITIONAL_LEGAL_PROPOSAL' if any(Q.values()) else 'NO_LEGAL_RECIPIENTS',Q=Q,D=Dmap,
        conditional_parts=v.parts,residuals=v.residuals(),checks=checks,trace=trace,freeze_quantity_caps=True,
        cancel_ack_required=pending_cancel,actual_submitted_unacked=sent,
        actual_resource_totals={k:sum((r[k] for r in actual_rows(x)),Z) for k in ('capital','risk','reserve')},
        conditional_projection_is_not_cancellation=True,other_goal_commitments_preserved=True)
    require(digest(x)==before,'quote prototype mutated actual input')
    return sealed(out)
