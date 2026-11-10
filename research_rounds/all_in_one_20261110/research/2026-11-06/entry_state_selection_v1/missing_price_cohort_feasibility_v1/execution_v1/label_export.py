"""Posterior-only strict ordinary and separately settled NET80 scenario labels."""
from collections import defaultdict
from decimal import Decimal as D
import json,math
import pandas as pd
from cohort_config import TEMPLATE_ID
from gates import PROTOCOL_SHA256

def report(joint,dest,window):
    from report_adapter import financial_coverage
    from run_extension import save
    now=str(pd.Timestamp.now(tz='UTC'));s=joint.s;claimby=defaultdict(list);actionby=defaultdict(list)
    for c in s.claims.values():claimby[c['owner_round_id']].append(c)
    for a in s.actions:actionby[a['round_id']].append(a)
    touched=set(claimby)|{x.get('round_id') for x in s.bridges}|{x.get('round_id') for x in s.claim_ledger}|{x.get('owner_round_id') for x in s.registrations}
    qas={x['round_id']:x for x in s.ledger_qa()};rows=[]
    def zero(v):
        try:return D(str(v))==0
        except Exception:return False
    def close(a,b):
        try:return abs(float(a)-float(b))<1e-7
        except Exception:return False
    for rd in s.rounds:
        rid=rd['round_id'];st=s.archives[rid];cs=claimby[rid];aa=actionby[rid];qa=qas[rid];cov=financial_coverage(s,rd,cs)
        closed=rd['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND';pending=any(not c.get('recognized') or not c.get('settled') for c in cs)
        cash=sum(((-D(a['q'])*D(str(a['price']))-D(str(a['fee']))) if a['side'].startswith('buy') else D(a['q'])*D(str(a['price']))-D(str(a['fee'])) for a in aa),D(0))
        qty=sum((int(a['q']) if a['side'].startswith('buy') else -int(a['q']) for a in aa));fees=sum((D(str(a['fee'])) for a in aa),D(0))
        entered=any(a['side']=='buy_core' and a['q']>0 for a in aa)
        finite=rd.get('net_pnl') is not None and math.isfinite(float(rd['net_pnl']))
        fin=bool(closed and cov['financial_covered'] and qa['reconciled'] is True and zero(rd.get('core_qty')) and zero(rd.get('add_qty')) and finite)
        reconciled_settled=bool(fin and not pending and zero(qa.get('receivable')))
        paid_days=[];settlement_clock_verified=True
        for c in cs:
            matches=[x for x in s.claim_ledger if x.get('round_id')==rid and x.get('economic_event_id')==c['economic_event_id'] and x.get('event')=='PAY_CLOSE_TRANSFER']
            good=c.get('settled') is True and len(matches)==1
            if good:
                x=matches[0];dd=pd.Timestamp(x['day'])
                good=dd in s.cal and dd>=pd.Timestamp(c['pay_date']) and close(x['cash_delta'],c['amount']) and close(x['receivable_delta'],-c['amount'])
                if good:paid_days.append(dd)
            settlement_clock_verified &= good
        settled=bool(reconciled_settled and settlement_clock_verified)
        ordinary=bool(entered and fin and cov['reason']=='LOCAL_NO_ACTION_EVIDENCE' and rid not in touched)
        ordinary=ordinary and all(zero(rd.get(k)) for k in ['core_qty','add_qty','dividend_at_termination','receivable_at_termination','receivable_after_payouts','dividend_net80_total','dividend_net80_paid'])
        ordinary=ordinary and qty==0 and zero(qa.get('qty')) and zero(qa.get('paid')) and zero(qa.get('receivable'))
        ordinary=ordinary and bool(aa) and min(pd.Timestamp(a['day']) for a in aa)==pd.Timestamp(rd.get('entry_day')) and max(pd.Timestamp(a['day']) for a in aa)==pd.Timestamp(rd.get('exit_day'))
        ordinary=ordinary and all(close(cash,rd.get(k)) for k in ['net_pnl','cashflow_to_date','cash_after_payouts']) and close(cash,qa.get('trade_cash')) and close(fees,qa.get('fees'))
        ordinary=bool(ordinary);assert not ordinary or settled
        dates=[pd.Timestamp(rd['exit_day'])] if closed else []
        dates += paid_days
        exitclock=(pd.Timestamp(rd['exit_day'])+pd.Timedelta(hours=15)).isoformat() if ordinary else None
        settlementclock=(max(dates)+pd.Timedelta(hours=15)).isoformat() if settled else None
        status='STRICT_ORDINARY_MATURE_PROXY' if ordinary else 'FINANCIAL_SETTLED_NONORDINARY_SCENARIO' if settled else 'RIGHTS_PENDING' if closed and pending else 'SETTLEMENT_CLOCK_UNKNOWN' if reconciled_settled and not settlement_clock_verified else 'RECONCILIATION_FAILED' if closed and cov['financial_covered'] and not fin else 'SETTLEMENT_UNKNOWN' if fin and not settled else 'FINANCIAL_COVERAGE_UNKNOWN' if closed and not cov['financial_covered'] else rd['status']
        signal=str(pd.Timestamp(rd['signal_day']).date());key=(rd['sid'],signal,TEMPLATE_ID);root=rd.get('price_root',st.get('price_root'));group=(rd['sid'],repr(root)) if root else (rd['sid'],'AB')
        rows.append(dict(rd,cohort_id=window,template_id=TEMPLATE_ID,original_contract_sha256='94965590a1d5ba5fd28e88a6cf6c09188f747663590d2ffa0e3f7858e2265687',extension_protocol_sha256=PROTOCOL_SHA256,
            owner_lane=st.get('owner_lane',rd.get('owner_lane','AB')),signal_close=signal,decision_dedup_key=json.dumps(key),dependence_group=json.dumps(group),sid_cluster=rd['sid'],
            entered=entered,financial_covered=cov['financial_covered'],financial_coverage_reason=cov['reason'],rights_pending=pending,rights_touched=rid in touched,has_claim=bool(cs),has_bridge=rid in {x.get('round_id') for x in s.bridges},label_status=status,
            ordinary_label_mature=ordinary,financial_settled_label_mature=settled,financial_settled_nonordinary=settled and not ordinary,financial_reconciled_closed=fin,reconciled_settled=reconciled_settled,settlement_clock_verified=settlement_clock_verified,nominal_claim_pay_dates=json.dumps([str(c.get('pay_date')) for c in cs]),actual_payment_ledger_days=json.dumps([str(d.date()) for d in paid_days]),
            label_net_cny=float(rd['net_pnl']) if ordinary else None,label_R=float(rd['net_pnl'])/3000 if ordinary else None,
            financial_scenario_net_cny=float(rd['net_pnl']) if settled else None,financial_scenario_R=float(rd['net_pnl'])/3000 if settled else None,
            economic_close_at=str(pd.Timestamp(rd['exit_day']).date()) if closed else None,label_usable_proxy_at=exitclock,financial_settlement_proxy_at=settlementclock,
            proxy_clock_timezone='Asia/Shanghai',source_available_at=None,source_evidence_domain='HISTORICAL_VERSION_UNVERIFIED_NON_PIT_PROXY',artifact_generated_at=now,
            row_weight=1.0 if ordinary else None,overlap_weight_status='NO_MODEL_FIT; dedup identical decisions and cluster shared sid/root before later fitting'))
    z=pd.DataFrame(rows);assert not z.duplicated(['cohort_id','round_id']).any();assert not z.duplicated(['decision_dedup_key']).any()
    z.to_csv(dest/'ALL_LANE_LABELS.csv',index=False);price=z[z.owner_lane.eq('PRICE')].copy();price.to_csv(dest/'PRICE_LABELS.csv',index=False)
    cuts=['2023-12-31','2024-08-31','2024-12-31','2025-12-31','2026-06-30'];cutrows=[]
    for cut in cuts:
        end=pd.Timestamp(cut)+pd.Timedelta(days=1)
        for scope,flag,clock,value in [('STRICT_ORDINARY','ordinary_label_mature','label_usable_proxy_at','label_R'),('FINANCIAL_SETTLED_ALL','financial_settled_label_mature','financial_settlement_proxy_at','financial_scenario_R'),('FINANCIAL_SETTLED_NONORDINARY','financial_settled_nonordinary','financial_settlement_proxy_at','financial_scenario_R')]:
            zz=price[price[flag]&pd.to_datetime(price[clock],errors='coerce').lt(end)]
            cutrows.append(dict(cohort_id=window,cut=cut,scope=scope,mature_price_labels=len(zz),unique_sids=zz.sid.nunique(),tail_gt_3R=int(zz[value].gt(3).sum()),tail_gt_1R=int(zz[value].gt(1).sum()),nonpositive=int(zz[value].le(0).sum()),source_domain='NON_PIT_PROXY'))
    pd.DataFrame(cutrows).to_csv(dest/'PRICE_MATURITY_BY_CUT.csv',index=False)
    summary=dict(cohort=window,template_id=TEMPLATE_ID,all_rounds=len(z),price_rounds=len(price),all_status_counts=z.status.value_counts().to_dict(),price_label_status_counts=price.label_status.value_counts().to_dict(),strict_ordinary_price_labels=int(price.ordinary_label_mature.sum()),strict_ordinary_price_sids=price[price.ordinary_label_mature].sid.nunique(),financial_settled_price_labels=int(price.financial_settled_label_mature.sum()),financial_settled_nonordinary_price_labels=int(price.financial_settled_nonordinary.sum()),price_unknown=int(price.status.str.contains('UNKNOWN').sum()),rights_pending=int(price.rights_pending.sum()),financially_uncovered_closed=int((price.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')&~price.financial_covered).sum()),cut_counts=cutrows,independent_start_flat=True,not_continuous_account=True,not_full_PIT=True,no_tail_support_improvement_assumed=True,actual_orders=0,actual_fills=0)
    save(dest/'SUMMARY.json',summary);return summary
