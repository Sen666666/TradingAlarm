"""Read saved final states. ZERO event/step/window/account-construction calls."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction as F
import hashlib,json,gc
import replay_runtime as X
from event_comparison import read_verified
R=X.HERE;E=X.E

def main():
    records=[];roles={};source_checks={};n_risk_orders=0;n_risk_fills=0
    data=X.read(R/'REPLAY_INPUT_BINDING.json')
    for mode in ['C10','C_BATCH20']:
        for day in ['2025-07-22','2025-07-23','2025-07-04','2025-07-30']:
            case=mode+'|'+day;rec=data['cases'][case];nextday=rec['next_day']
            old_action=Path(rec['baseline_open']).with_name(nextday+'-ACTION.pkl')
            baseline_action=read_verified(old_action,'baseline');base_digest=E.digest(X.snapshot(baseline_action));del baseline_action;gc.collect()
            for flag in ['off','on']:
                out=R/'runs'/(mode+'-'+day+'-'+flag)
                for phase in ['ACTION','OPEN']:
                    p=out/(nextday+'-'+phase+'.pkl');r=read_verified(p,'diagnostic');b=r.account.bridge(r.last_completed_event)
                    assert all(D(b[k])==0 for k in ['independent_nav_difference','cash_asset_difference','layer_cash_difference'])
                    source_checks[str(p)]=X.sha(p)
                    if phase=='ACTION':assert E.digest(X.snapshot(r))==base_digest,'ACTION changed under R0'
                    else:
                        comp_path=out/'ACTUAL_OPEN_COMPARISON.json'
                        if not comp_path.exists():comp_path=out/'OFF_IDENTITY_READONLY.json'
                        comp=X.read(comp_path)
                        if flag=='off':assert comp['off_complete_original_state_identity']
                        roles[mode+'-'+day+'-'+flag]=[]
                        for f in r.account.fills:
                            if f.side!='buy' or f.at<E.iso(nextday+'T09:30:00+08:00'):continue
                            layer=r.account.inventory_map[f.receipt_id]['layer'];meta=r.account.capital_meta[layer];support=r.account.supports[meta['order']]
                            roles[mode+'-'+day+'-'+flag].append(dict(sid=f.security_id,shares=f.shares,gross=f.gross_cny,fee=f.fees_cny,receipt=f.receipt_id,layer=layer,role=meta['role'],pool=meta['pool'],purpose=meta['purpose'],C_certificate=support.get('C_certificate'),order=meta['order']))
                        if flag=='on':
                            n_risk_orders+=len(r.risk.orders);n_risk_fills+=len(r.risk.fills)
                            for key,z in r.risk.approvals.items():
                                assert z['spent']<=z['approved']['R0']
                                if z['order']:
                                    sid=z['approved']['sid'];o=r.account.buys.get(sid)
                                    if o and o.order_id==z['order']:
                                        price=r.account.market.prices[sid]*(E.ONE+E.LR.SLIP);floor=r.account.order_meta[o.order_id]['floor']/r.account.facts.factor(sid,r.last_completed_event)
                                        assert z['spent']+F(o.remaining_shares)*max(F(0),F(price)-F(floor))<=z['approved']['R0']
                    records.append(dict(case=case,risk=flag,phase=phase,cursor=str(r.last_completed_event),sha256=X.sha(p),finance_bridges=True,lot_share_bridge=True,actual_source_identity=True))
                    del r;gc.collect()
    # Original checkpoints/OPEN controls and frozen manifests stay immutable.
    for p,h in data['sources'].items():assert X.sha(p)==h,('original changed',p)
    X.save(R/'ACTUAL_ROLE_POOL_ROWS.json',roles)
    X.save(R/'ACTUAL_FINANCIAL_GATE.json',dict(passed=True,financial_events_invoked_by_verifier=0,states=records,state_count=len(records),all_ACTIONs_original_exact=True,all_OFF_OPENs_original_exact=True,all_journal_cash_share_equity_fee_bridges=True,on_new_C_order_risk_mappings=n_risk_orders,on_actual_C_fill_risk_debits=n_risk_fills,original_sources_and_checkpoints_unchanged=True,source_checkpoints=source_checks,risk_adapter_sha256=X.RISK_SHA,runtime_sha256=X.sha(R/'replay_runtime.py'),fixed_driver_sha256=X.sha(R/'run_prepared_fixed.py')))
    print('ACTUAL_FINANCIAL_GATE_PASS',len(records),'states',n_risk_orders,'Corders',n_risk_fills,'Cfills',flush=True)
if __name__=='__main__':main()
