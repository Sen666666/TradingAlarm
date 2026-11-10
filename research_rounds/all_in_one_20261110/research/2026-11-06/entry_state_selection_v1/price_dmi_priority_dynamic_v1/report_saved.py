"""Read-only posterior OLD JOINT vs NEW JOINT report. No strategy/run/reset calls."""
import argparse,json,math
from pathlib import Path
from types import SimpleNamespace as NS
from collections import Counter,defaultdict
import numpy as np,pandas as pd
from runtime import O,R,SOURCE,sha,read
from run_economic import save
from recover_saved_report import snapshot,SavedBook,normalized_record,verify_manifest,independent_retained_check
from report_adapter import adapt_engine,_permits
from reporting import build_report


def saved_consumer(directory,evidence):
    s=snapshot(directory/'joint',evidence,'A_UNION_B_PLUS_PRICE')
    return NS(s=s,arm='A_UNION_B_PLUS_PRICE',states={},
        price_audit=[normalized_record(r) for r in read(directory/'PRICE_AUDIT.json')],
        offer_audit=[normalized_record(r) for r in read(directory/'OFFER_AUDIT.json')],
        ab_decision_audit=[normalized_record(r) for r in read(directory/'AB_DECISION_AUDIT.json')],
        books={rid:SavedBook(v) for rid,v in read(directory/'EXECUTION_BOOKS.json').items()})


def distribution(values):
    v=np.asarray(values,dtype=float);win=v[v>0];loss=v[v<0]
    return dict(known_count=len(v),wins=len(win),losses=len(loss),zeros=int((v==0).sum()),
        win_rate=float(len(win)/len(v)) if len(v) else None,
        net=float(v.sum()),net_per_known_unit=float(v.mean()) if len(v) else None,
        mean_win=float(win.mean()) if len(win) else None,mean_loss=float(loss.mean()) if len(loss) else None,
        payoff_mean_win_over_abs_mean_loss=float(win.mean()/abs(loss.mean())) if len(win) and len(loss) else None,
        profit_factor=float(win.sum()/abs(loss.sum())) if len(loss) else None,
        quantiles={str(q):float(np.quantile(v,q)) for q in [0,.01,.05,.5,.9,.95,.99,1]} if len(v) else {})


def make_rounds(adapted,arm):
    act=defaultdict(list)
    for a in adapted['actions']:act[a['round_id']].append(a)
    cash={r['round_id']:r['cash_plus_receivable'] for r in adapted['closed_cash_checks']}
    probe={r['round_id']:r for r in adapted['core_diagnostics']}
    cov={r['round_id']:r for r in adapted['round_coverage']}
    result=[]
    for r in adapted['rounds']:
        rid=r['round_id'];p=probe.get(rid,{})
        result.append(dict(sid=r['sid'],arm=arm,owner_lane=r['owner_lane'],round_id=rid,event_id=r.get('event_id'),signal_day=r.get('signal_day'),entry_day=r.get('entry_day'),status=r['status'],entered=any(a['side']=='BUY' for a in act[rid]),full_closed_net=cash.get(rid),probe_closed_net=p.get('closed_net'),probe_open_net=p.get('open_total_net'),financial_covered=cov[rid]['financial_covered'],coverage_reason=cov[rid]['reason'],net80=r.get('dividend_net80_total'),unknown='UNKNOWN' in r['status'] or 'PENDING' in r['status'] or bool(r.get('_unresolved_book')),book_derived_unresolved=bool(r.get('_unresolved_book')),open_censored='CENSORED' in r['status'],independent_probe_fee_basis=p.get('fee_basis')))
    return result


def summarize_rounds(rounds,common):
    results=[]
    for cohort in ('ALL_FIXED_1709','COMMON_COMPARABLE_STOCKS'):
        for arm in ('baseline','joint'):
            for lane in ('ALL','AB','PRICE'):
                rs=[r for r in rounds if r['arm']==arm and (cohort=='ALL_FIXED_1709' or r['sid'] in common) and (lane=='ALL' or r['owner_lane']==lane)]
                ent=[r for r in rs if r['entered']]
                for role,col in [('FULL_ROUND','full_closed_net'),('FIRST_PROBE_INDEPENDENT_DATED_FEES','probe_closed_net')]:
                    for coverage in ('ALL_CONDITIONAL_CLOSED','FINANCIALLY_COVERED_CLOSED'):
                        usable=[r for r in ent if r[col] is not None and not r['unknown'] and (coverage=='ALL_CONDITIONAL_CLOSED' or r['financial_covered'])]
                        results.append(dict(cohort=cohort,arm=arm,lane=lane,role=role,coverage_filter=coverage,selected_round_records=len(rs),entered_rounds=len(ent),unknown_entered_rounds=sum(r['unknown'] for r in ent),book_derived_unresolved_entered_rounds=sum(r['book_derived_unresolved'] for r in ent),open_censored_entered_rounds=sum(r['open_censored'] for r in ent),financial_uncovered_entered_rounds=sum(not r['financial_covered'] for r in ent),closed_net_denominator=len(usable),not_in_known_closed_denominator=len(ent)-len(usable),**distribution([r[col] for r in usable])))
    return results


def displacement(old,new):
    oo=defaultdict(list);nn=defaultdict(list)
    for x in old.offer_audit:oo[x['owner_lane'],str(x['request_id'])].append(x)
    for x in new.offer_audit:nn[x['owner_lane'],str(x['request_id'])].append(x)
    rd={r['round_id']:r for r in new.s.rounds};result=[]
    for key in sorted(set(oo)|set(nn)):
        a,b=oo[key],nn[key]
        selected=lambda xs:any(x['result']=='SELECTED_PENDING' for x in xs)
        sa,sb=selected(a),selected(b)
        if sa==sb:continue
        reason='NEWLY_SELECTED_DYNAMIC_PATH' if sb else 'NO_LONGER_SELECTED_DYNAMIC_PATH'
        if sa and not sb:
            reasons=[]
            for x in b:
                blocker=rd.get(x.get('blocking_round_id'),{})
                if x['result'].startswith('BLOCKED_'):reasons.append(x['result']+'_'+blocker.get('owner_lane','UNKNOWN_OWNER'))
                elif x['result']=='PASS_NOT_TOP2':reasons.append('SECTOR_SLOT_RANK')
                elif x['result']!='APPLICATION':reasons.append(x['result'])
            reason='|'.join(sorted(set(reasons))) or 'NO_NEW_OFFER'
        lead=(b or a)[0]
        result.append(dict(lane=key[0],request_id=key[1],sid=lead['sid'],day=lead['day'],sector=lead['sector'],old_selected=sa,new_selected=sb,reason=reason,old_offers=a,new_offers=b))
    return result


def build(window):
    olddir=SOURCE/('economic_'+window);newdir=O/('dmi_'+window)
    assert (newdir/'COMPLETE_SAVED_SNAPSHOT.json').exists(),'REQUIRE_COMPLETE_SEALED_SNAPSHOT'
    complete=read(newdir/'COMPLETE_SAVED_SNAPSHOT.json')
    assert complete['output_seal_sha256']==sha(newdir/'OUTPUT_SEAL.json')
    for name,h in read(newdir/'OUTPUT_SEAL.json').items():assert sha(newdir/name)==h,('SNAPSHOT_DRIFT',name)
    dest=O/('report_'+window);dest.mkdir(exist_ok=False)
    protected={str(p):sha(p) for d in [olddir,newdir] for p in d.rglob('*') if p.is_file()}
    verify_manifest(olddir/'joint');verify_manifest(newdir/'joint')
    from baseline_regression import load_engine
    evidence=load_engine(window) # original read-only source/rights setup, no lifecycle
    old=saved_consumer(olddir,evidence);new=saved_consumer(newdir,evidence)
    retained_ab=independent_retained_check(NS(rounds=[r for r in old.s.rounds if r['owner_lane']=='AB'],actions=old.s.actions,claims=old.s.claims),NS(rounds=[r for r in new.s.rounds if r['owner_lane']=='AB'],actions=new.s.actions,claims=new.s.claims))
    roster=pd.read_csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').sid.astype(str).tolist()
    assert len(roster)==len(set(roster))==1709
    b=adapt_engine(old,roster,window,'baseline',baseline=False)
    j=adapt_engine(new,roster,window,'joint',baseline=False)
    args={name:b[name]+j[name] for name in ('actions','claims','states','terminal_marks','coverage','core_diagnostics','closed_cash_checks')}
    report=build_report(roster,['2022' if window=='2022' else '2024_924'],['baseline','joint'],['AB','PRICE'],expected_roster_size=1709,reference_permits=_permits(old.s.ev),candidate_permits=_permits(new.s.ev),**args)
    report.update(arm_definitions=dict(baseline='ORIGINAL_A_PLUS_B_PLUS_PRICE_PVR_PRIORITY',joint='SAME_JOINT_PRICE_ONLY_DMI_PRIORITY'),round_coverage=b['round_coverage']+j['round_coverage'],adapter_blockers=b['blockers']+j['blockers'],source='SAVED_LEDGER_ONLY_NO_NEW_CONSUMER_EXECUTION')
    assert report['permit_exact_verified']
    report['retained_ab_path_exact']=retained_ab
    if retained_ab['mismatch_count']:report['adapter_blockers'].append('RETAINED_AB_ECONOMIC_PATH_MISMATCH')
    # Original joint has PRICE on both sides; baseline=False above is mandatory.
    assert sum(r['owner_lane']=='PRICE' for r in b['rounds'])>0
    common=set(report['summary'][0]['common_covered_sids'])
    rounds=make_rounds(b,'baseline')+make_rounds(j,'joint')
    metrics=summarize_rounds(rounds,common)
    participation=[]
    for s in report['stock_rows']:
        rs=[r for r in rounds if r['sid']==s['sid'] and r['arm']==s['arm'] and r['entered']]
        participation.append(dict(s,common_comparable=s['sid'] in common,entered_rounds=len(rs),ab_rounds=sum(r['owner_lane']=='AB' for r in rs),price_rounds=sum(r['owner_lane']=='PRICE' for r in rs),unknown_rounds=sum(r['unknown'] for r in rs),conditional_closed_round_net=sum(r['full_closed_net'] for r in rs if r['full_closed_net'] is not None),conditional_closed_round_net_is_not_total_if_unknown=True))
    stocks=[]
    for cohort in ('ALL_FIXED_1709','COMMON_COMPARABLE_STOCKS'):
        for arm in ('baseline','joint'):
            allrows=[s for s in participation if s['arm']==arm and (cohort=='ALL_FIXED_1709' or s['sid'] in common)]
            ent=[s for s in allrows if s['entered_rounds']>0];known=[s for s in ent if s['known_total_pnl'] is not None]
            order=sorted(known,key=lambda x:x['known_total_pnl'])
            stocks.append(dict(cohort=cohort,arm=arm,fixed_stocks=len(allrows),entered_stocks=len(ent),never_entered_stocks=sum(s['never_entered'] for s in allrows),unknown_stocks=sum(s['unknown_liability'] for s in allrows),financial_uncovered_stocks=sum(not s['financial_covered'] for s in allrows),repeated_participation_stocks=sum(s['entered_rounds']>1 for s in allrows),known_participant_distribution=distribution([s['known_total_pnl'] for s in known]),bottom20=[dict(sid=s['sid'],net=s['known_total_pnl'],rounds=s['entered_rounds']) for s in order[:20]],top20=[dict(sid=s['sid'],net=s['known_total_pnl'],rounds=s['entered_rounds']) for s in order[-20:][::-1]]))
    changes=displacement(old,new)
    old_unknown={r['sid'] for r in rounds if r['arm']=='baseline' and r['unknown']};new_unknown={r['sid'] for r in rounds if r['arm']=='joint' and r['unknown']}
    stock_unknown={arm:{r['sid'] for r in report['stock_rows'] if r['arm']==arm and r['unknown_liability']} for arm in ['baseline','joint']}
    round_status_unknown={arm:{r['sid'] for r in rounds if r['arm']==arm and ('UNKNOWN' in r['status'] or 'PENDING' in r['status'])} for arm in ['baseline','joint']}
    unknown_round_stock_mismatch=dict(baseline=sorted(old_unknown^stock_unknown['baseline']),joint=sorted(new_unknown^stock_unknown['joint']))
    unknown_status_vs_stock={arm:[dict(sid=sid,raw_status_unknown=sid in round_status_unknown[arm],stock_unknown_liability=sid in stock_unknown[arm],rounds=[r for r in rounds if r['arm']==arm and r['sid']==sid],lanes=[r for r in report['lane_rows'] if r['arm']==arm and r['sid']==sid]) for sid in sorted(round_status_unknown[arm]^stock_unknown[arm])] for arm in ['baseline','joint']}
    old_unknown,new_unknown=stock_unknown['baseline'],stock_unknown['joint']
    if any(unknown_round_stock_mismatch.values()):report['adapter_blockers'].append('UNKNOWN_ROUND_STOCK_LIABILITY_RECONCILIATION_REVIEW')
    rank=read(newdir/'DMI_RANK_AUDIT.json')
    summary=dict(window=window,model='CONDITIONAL_PER_STOCK_PROXY_NOT_SHARED_CASH_ACCOUNT',fixed_stocks=1709,common_comparable_stocks=len(common),old_net_common=report['summary'][0]['common_covered_pnl'],new_net_common=report['summary'][1]['common_covered_pnl'],common_delta=report['summary'][1]['common_covered_pnl']-report['summary'][0]['common_covered_pnl'],common_lane_deltas={lane:sum(r['lane_contributions'][lane] for r in report['differences'] if r['common_covered']) for lane in ['AB','PRICE']},unknown=dict(old=len(old_unknown),new=len(new_unknown),newly_unknown=sorted(new_unknown-old_unknown),no_longer_unknown=sorted(old_unknown-new_unknown)),retained_ab_path_exact=retained_ab,unknown_round_stock_mismatch=unknown_round_stock_mismatch,unknown_status_vs_stock=unknown_status_vs_stock,changed_requests=len(changes),changed_request_reasons=dict(Counter(x['lane']+'|'+x['reason'] for x in changes)),same_day_dynamic_queue_rank_invariants=dict(rows=len(rank),locked_ab_moved=sum(x['rank_changed'] for x in rank if x['owner_lane']=='AB'),unknown_moved=sum(x['rank_changed'] for x in rank if not x['mutable']),dynamic_price_selected=sum(x['dmi_selected'] for x in rank if x['owner_lane']=='PRICE'),mutable_rank_changes=sum(x['rank_changed'] for x in rank if x['mutable'])),adapter_blockers=report['adapter_blockers'],new_economic_executions_by_this_report=0)
    assert summary['same_day_dynamic_queue_rank_invariants']['locked_ab_moved']==0
    assert summary['same_day_dynamic_queue_rank_invariants']['unknown_moved']==0
    assert math.isclose(summary['common_delta'],sum(summary['common_lane_deltas'].values()),abs_tol=1e-6)
    for p,h in protected.items():assert sha(p)==h,('SAVED_LEDGER_CHANGED',p)
    save(dest/'COMPARISON_REPORT.json',report);save(dest/'SUMMARY.json',summary)
    save(dest/'ROUND_METRICS.json',metrics);save(dest/'STOCK_METRICS.json',stocks)
    save(dest/'REQUEST_DISPLACEMENT.json',changes)
    pd.DataFrame(rounds).to_csv(dest/'ALL_ROUNDS.csv',index=False)
    pd.DataFrame(participation).to_csv(dest/'ALL_STOCK_PARTICIPATION.csv',index=False)
    save(dest/'REPORT_QA.json',dict(result='SAVED_JOINT_VS_JOINT_POSTERIOR_REPORT',full_roster_both_arms=True,price_lane_in_both=True,raw_ledgers_unchanged=True,common_scope_count=len(common),old_files_sha256=protected,unknown_not_zero=True,claim_cash_reconciled=True,report_code_sha256=sha(__file__),consumer_executions=0))
    save(dest/'OUTPUT_SHA256.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file()})
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);build(p.parse_args().window)
