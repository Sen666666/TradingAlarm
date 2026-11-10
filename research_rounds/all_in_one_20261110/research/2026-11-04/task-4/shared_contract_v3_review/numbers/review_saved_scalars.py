"""Read peer saved scalar witnesses only. No finance/model/price imports."""
from pathlib import Path
from decimal import Decimal as D
import hashlib
import json
import time

OUT=Path(__file__).resolve().parent
PEER=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structure_risk_position_contract_v3')
SOURCES={};Z=D(0);EPS=D('1e-18')
def bind(p):
    p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(n):return json.loads(bind(PEER/n).read_text())
def equal(a,b):return abs(D(str(a))-D(str(b)))<=EPS
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')

def main():
    start=time.monotonic();bind(__file__)
    bridge=read('open_prefix/SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json')
    seal=read('open_prefix/SEAL_RECEIPT.json')
    audit=read('independent_numbers/SEVEN_ACTUAL_OPEN_BRIDGE_AUDIT.json')
    local_audit=read('independent_numbers/FINAL_SEVEN_LOCAL_AUDIT.json')
    decisions=read('cases/FINAL_SEVEN_PAPER_DECISIONS.json')
    read('independent_numbers/ACTUAL_PREFIX_D_ARITHMETIC.json')
    bind(PEER/'open_prefix/READOUT.md');bind(PEER/'cases/READOUT.txt')
    bind(PEER/'designer/MINIMUM_MATH_CONTRACT.md')
    rows=[]
    for r in bridge['results']:
        p=D(r['ACT_peak']);domains=[]
        for label,ik,nk,ak,lk in [
            ('native_known_mark','native_known_mark_inventory_after_sells','native_known_mark_NAV_prefix','A_native_domain','G2_lower_native_mark_domain'),
            ('exact_raw_OPEN_valuation','exact_raw_OPEN_inventory_after_sells','raw_OPEN_valued_NAV_prefix','A_OPEN_valuation_domain','G2_lower_OPEN_valuation_domain')]:
            inventory=D(r[ik]);nav=D(r[nk]);a=max(Z,nav-D('.8')*p);lower=D('.36')*inventory
            assert equal(a,r[ak]) and equal(lower,r[lk])
            assert lower>a
            domains.append(dict(domain=label,inventory=inventory,NAV=nav,ACTpeak=p,
                recomputed_A=a,recomputed_36pct_inventory=lower,lower_excess_over_A=lower-a,
                lower_gt_A=True))
        rows.append(dict(next_OPEN=r['next_OPEN'],prefix=r['prefix'],
            original_actual_sells=len(r['actual_sells']),original_settlements=len(r['actual_settlements']),
            domains=domains,final_additional_grant_on_this_prefix=0))
    assert len(rows)==7
    decision_checks=[]
    fee_checks=[]
    for r in decisions:
        b=D('.0025')*D(r['origin_signal_NAV']);dc=r['D_components']
        d=max(Z,D(dc['gross_loss'])+D(dc['actual_paid_fees'])-D(dc['gross_profit'])-D(dc['paid_rights']))
        paid=sum((D(x['buyfee'])for x in dc['buyfee_parts']),Z)+sum((D(x['sellfee'])for x in dc['sell_parts']),Z)
        assert equal(b,r['B']) and equal(d,r['D_before']) and equal(paid,dc['actual_paid_fees'])
        assert r['q_final_grant']==0 and r['single_prefix_only'] and r['counterfactual_account_gain']=='NOT_COMPUTED_NOT_IDENTIFIED'
        c=r['local_cost_at_q'];k=sum((D(x['kappa'])for x in c['parts']),Z);buyfee=D(c['unpaid_candidate_buyfee'])
        assert equal(k,c['kappa_sum']) and equal(d+buyfee+k,c['total'])
        for x in c['parts']:
            assert equal(max(Z,D(x['gross_basis'])-D(x['plan_net_before_fee'])+D(x['allocated_sellfee'])),x['kappa'])
        assert equal(sum((D(x['allocated_sellfee'])for x in c['parts']),Z),c['sell_group_fee'])
        cost=D(c['total']);q=r['q_local_after_source_and_frozen_caps']
        decision_checks.append(dict(sid=r['sid'],decision=r['decision'],source=r['source'],
            B_once=b,D_before=d,local_q_only=q,local_total=cost,D_exceeds_B=d>b,
            local_q_is_not_final_grant=True,final_grant=0,
            local_minimum_total=r.get('local_minimum_unit_cost',{}).get('total')))
        # All seven saved prefixes have zero realized profit/equity buffer. For
        # this limited set, moving candidate fee once into projected D is exact.
        assert D(dc['gross_profit'])==0 and D(dc['paid_rights'])==0
        dproj=d+buyfee
        assert equal(dproj+k,cost)
        f=dict(sid=r['sid'],decision=r['decision'],existing_paid_fees_once=paid,
            new_unpaid_buyfee_once=buyfee,D_postfill_for_these_no_profit_buffer_examples=dproj,
            kappa_excludes_already_paid_buyfee=True,prefill_vs_postfill_same_k_total_equal=True)
        if q:
            x=next(x for x in c['parts']if x['layer']=='candidate')
            basis=D(x['gross_basis']);m=D(r['next_rawOPEN']);p_buy=D(r['next_buy_price'])
            assert equal(basis,D(q)*p_buy)
            proceeds=D(x['plan_net_before_fee']);sf=D(x['allocated_sellfee'])
            pending=D(q)*p_buy-proceeds+sf+buyfee
            live=D(q)*m-proceeds+sf
            nav_cost=D(q)*(p_buy-m)+buyfee
            assert equal(pending,live+nav_cost)
            f['saved_positive_local_q']=q
            f['pending_pressure_candidate_component']=pending
            f['postfill_live_pressure_candidate_component']=live
            f['projected_NAV_entry_cost_once']=nav_cost
            f['candidate_pending_phi_equals_postfill_phi_plus_NAV_cost']=True
        fee_checks.append(f)
    # Scalar demonstration of the new-wide-I whole-sid G2 step. P/kappa local
    # totals remain per-layer; they do not compute this common-sid scenario.
    steps=[]
    for r in decisions:
        if r['source']!='HELD_I_INCREMENT':continue
        factor=D(r['holding_floor_adjusted'])/D(r['holding_floor_raw_OPEN'])
        z=min(D(r['signal_rawclose']),D(r['next_rawOPEN']))
        old_lines=[D(x['floor_adjusted'])/factor for x in r['existing_original_layers']]
        b0=min([z]+old_lines);b1=min(b0,D(r['holding_floor_raw_OPEN']))
        qold=sum(x['q']for x in r['existing_original_layers'])
        oldstep=D(qold)*D('.64')*D('.9995')*(b0-b1)
        steps.append(dict(sid=r['sid'],decision=r['decision'],existing_real_shares=qold,
            known_Z=z,b_before_positive_proposal=b0,b_after_any_positive_wide_I=b1,
            existing_shares_only_G2_extra_before_fees=oldstep,
            step_occurs_if_positive_proposal=oldstep>0,
            q_zero_does_not_install_proposed_I=True,
            scope='Only saved scalar common-b illustration; not full Phi/Lambda/T/capacity or a new grant. No proposed quantity enumerated.'))
    assert all(x.get('pass',True)for x in audit['checks'])
    assert all(x.get('pass',True)for x in local_audit['checks'])
    current_bridge_sha=SOURCES[str((PEER/'open_prefix/SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json').resolve())]
    assert all(r['original_OPEN_pressure_necessary_condition']['source_sha256']==current_bridge_sha for r in decisions)
    res=dict(status='PASS_SEVEN_SAVED_ORIGINAL_PREFIX_NECESSARY_DENIALS_ONLY',
        reviewer='/root/audit_924',prefix_lower_bound_rows=rows,shared_B_D_local_checks=decision_checks,
        buyfee_postfill_checks=fee_checks,wide_I_common_sid_step_examples=steps,
        peer_prior_audit=dict(open_bridge_status=audit['status'],open_bridge_checks=len(audit['checks']),
            local_status=local_audit['status'],local_checks=len(local_audit['checks']),
            reliance='Peer prior audits cover original raw quantities, quotes, receipts and settlements. This review does not reopen market/source data or rerun their audit scripts.'),
        necessary_denial_argument='At fixed original prefix, G2 b<=Z<=M implies existing loss>=.36*existing inventory before fees/exit locks. Existing lower>A in both separately reconciled domains. Positive buys cannot increase A after entry costs or reduce the existing common-b pressure; thus additional grant0 follows without full scenario implementation.',
        scope=['Seven independent ORIGINAL account prefixes after actual exits/settlements before first new reserve; Apr23 uses equivalent after-settlement point because original no new reserve.',
            'Not from-flat replacement strategy, not a sequential path, not an actual new order/fill, not return or drawdown improvement.',
            'A uses original current ACT episode peak, not immutable initial capital or assumed .2NAV.',
            '36% is frozen two-step .8^2 stress lower bound, not legal daily limit, probability or worst actual loss.',
            'Positive local caps476/369/2300 consume only P/kappa/B/source caps and are not final; new wideI can raise common-b liability on all old same-sid shares.',
            'Current postfill no-double-fee and common-b card amendments are formula-audited here, not claimed an implemented full scenario/postfill engine.'],
        new_accounts=0,new_models=0,new_backtests=0,new_parameter_tests=0,new_prices=0,new_quantity_searches=0,
        scalar_review_seconds=time.monotonic()-start,source_sha256=SOURCES)
    save('SEVEN_PREFIX_SAVED_SCALAR_REVIEW.json',res)
    print(json.dumps(dict(status=res['status'],prefixes=7,all_final_zero_on_original_prefix=True,
        wideI_steps=steps,seconds=res['scalar_review_seconds']),ensure_ascii=False,default=str))

if __name__=='__main__':main()
