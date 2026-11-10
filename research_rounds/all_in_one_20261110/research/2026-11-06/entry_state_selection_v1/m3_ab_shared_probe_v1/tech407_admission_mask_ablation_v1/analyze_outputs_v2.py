"""Read-only outcome analysis. Does not instantiate or advance an account."""
from pathlib import Path
from decimal import Decimal as D
import collections,json,sys
import mask_bridge as M
from runner import save,read
HERE=Path(__file__).resolve().parent;ZERO=D(0);CLOSED='EXECUTION_AND_SETTLEMENT_CLOSED'
SEMANTIC=['ACTIONS','DECISIONS','RANKING_AUDIT','AUDIT','DAY_LEDGER','ARCHIVES','STATES','LAYERS','CLAIMS','REGISTRATIONS','CLAIM_LEDGER','EQUITY_BRIDGES','PROFIT_GATES','ROUND_ND','SOURCE_ROUNDS','SOURCE_HASHES','INTENTIONS','ORDER_STATUS','ROUND_REPORT','LAYER_REPORT','EXACT_TRADE_JOURNAL']
def normalized(name,data):
    if name=='DAY_LEDGER':return [{k:v for k,v in x.items() if k not in ('seconds','peak_rss_bytes')} for x in data]
    return data
def canonical(x):return json.dumps(x,sort_keys=True,default=str,allow_nan=True)
def validate(out):
    assert not (out/'FAILURE.json').exists() and not (out/'POST_STATUS_FAILURE.json').exists()
    status=read(out/'RUN_STATUS.json');assert status['status']=='COMPLETED_RESOURCE_PASS'
    qa=read(out/'FINAL_RESOURCE_QA.json');assert qa['resource_pass'] and qa['elapsed_seconds']<900 and qa['peak_rss_bytes']<6442450944
    assert status['elapsed_seconds']<900 and status['peak_rss_bytes']<6442450944
    assert status['output_seal_sha256']==M.E.bridge.sha(out/'OUTPUT_SEAL.json')
    assert status['final_resource_sha256']==M.E.bridge.sha(out/'FINAL_RESOURCE_QA.json')
    for name,h in read(out/'OUTPUT_SEAL.json').items():assert M.E.bridge.sha(out/name)==h,(out,name)
    return status

def baseline():
    new=HERE/'run_all1709_once';validate(new);old=M.BASE/'cohort_2024_924';checks={}
    for name in SEMANTIC:
        a=normalized(name,read(new/(name+'.json')));b=normalized(name,read(old/(name+'.json')))
        checks[name]=dict(match=canonical(a)==canonical(b),new_rows=len(a),old_rows=len(b))
    all_match=all(x['match'] for x in checks.values())
    result=dict(all_match=all_match,baseline_output_seal_sha256=M.E.bridge.sha(new/'OUTPUT_SEAL.json'),baseline_final_resource_sha256=M.E.bridge.sha(new/'FINAL_RESOURCE_QA.json'),baseline_run_status_sha256=M.E.bridge.sha(new/'RUN_STATUS.json'),semantic_outputs=checks,exclusions=['elapsed_seconds','seconds','peak_rss_bytes','run packaging/status and additional mask-only logs'],original_reference=str(old))
    save(HERE/'BASELINE_EXACT_EQUIVALENCE.json',result);assert all_match
    print('BASELINE_EXACT_PASS',len(checks))

def describe(rows,status_field,net_field,return_field):
    closed=[x for x in rows if x[status_field]==CLOSED]
    values=[D(str(x[net_field])) for x in closed];wins=[v for v in values if v>0];losses=[v for v in values if v<0]
    tail=[x for x in closed if D(str(x[return_field]))>=D('.30')]
    ordinary=[x for x in closed if D(str(x[return_field]))<D('.30')]
    summ=lambda xs:sum(xs,ZERO)
    mean_win=summ(wins)/len(wins) if wins else None;mean_loss=-summ(losses)/len(losses) if losses else None
    tailnet=summ([D(str(x[net_field])) for x in tail]);total=summ(values)
    return dict(total=len(rows),statuses=dict(collections.Counter(x[status_field] for x in rows)),closed=len(closed),wins=len(wins),losses=len(losses),flat=sum(v==0 for v in values),
        win_rate=None if not closed else D(len(wins))/D(len(closed)),net=total,mean_net=None if not closed else total/len(closed),
        mean_win=mean_win,mean_loss_abs=mean_loss,payoff_amount_ratio=None if not mean_win or not mean_loss else mean_win/mean_loss,
        tail_threshold_fee_net_return=D('.30'),tails=len(tail),tail_rate=None if not closed else D(len(tail))/D(len(closed)),tail_net=tailnet,
        tail_net_share=None if total==0 else tailnet/total,ordinary_count=len(ordinary),ordinary_wins=sum(D(str(x[net_field]))>0 for x in ordinary),ordinary_net=total-tailnet,
        closed_ids=[x['round_id'] for x in closed],tail_ids=[x['round_id'] for x in tail])
def liability_free_unknown_count(audit):
    return sum(x.get('type')=='UNKNOWN' and x.get('liability_free_initial') is True for x in audit)

def require_baseline_gate(root=HERE):
    out=root/'run_all1709_once';status=validate(out);exact=read(root/'BASELINE_EXACT_EQUIVALENCE.json')
    assert exact['all_match'] is True
    assert exact['baseline_output_seal_sha256']==M.E.bridge.sha(out/'OUTPUT_SEAL.json')
    assert exact['baseline_final_resource_sha256']==M.E.bridge.sha(out/'FINAL_RESOURCE_QA.json')
    assert exact['baseline_run_status_sha256']==M.E.bridge.sha(out/'RUN_STATUS.json')
    return status

def account(arm):
    out=HERE/('run_'+arm+'_once');status=validate(out);data={n:read(out/(n+'.json')) for n in SEMANTIC};result=read(out/'RESULT.json')
    layers=data['LAYER_REPORT'];rounds=data['ROUND_REPORT'];daily=data['DAY_LEDGER'];actions=data['ACTIONS'];decisions=data['DECISIONS'];orders=data['ORDER_STATUS'];tech=M.members()
    closed=describe(rounds,'status','whole_round_NET80','conditional_return_on_actual_buy_cash')
    core=describe([x for x in layers if x['layer']=='core'],'layer_status','NET80','return_on_layer_buy_cash')
    add=describe([x for x in layers if x['layer']=='add'],'layer_status','NET80','return_on_layer_buy_cash')
    navs=[D('1200000')];full_cert=result['complete_certified_NAV_path']
    for row in daily:
        if row['CLOSE']['certified']:navs.append(D(row['CLOSE']['NAV']))
        else:full_cert=False
        if row['OPEN'] is not None and not row['OPEN']['certified']:full_cert=False
    endnav=D(daily[-1]['CLOSE']['NAV']) if daily[-1]['CLOSE']['NAV'] is not None else None
    peak=navs[0];dd=ZERO;peakday='SEED';troughday=None;ddpeakday=None
    for row in daily:
        if not row['CLOSE']['certified']:continue
        nav=D(row['CLOSE']['NAV'])
        if nav>peak:peak=nav;peakday=row['day']
        draw=(peak-nav)/peak
        if draw>dd:dd=draw;troughday=row['day'];ddpeakday=peakday
    if not full_cert:dd=None;troughday=None;ddpeakday=None
    filled=[o for o in orders if o['status']=='filled' and o['kind']=='INIT']
    init_ids={a['round_id'] for a in actions if a['side']=='buy_core'}
    lifecycle=[]
    rr={x['round_id']:x for x in rounds}
    for rid in sorted(init_ids):
        st=data['ARCHIVES'][rid];r=rr[rid];a=next(x for x in actions if x['round_id']==rid and x['side']=='buy_core')
        lifecycle.append(dict(event_id=st['event_id'],sid=st['sid'],round_id=rid,signal_day=st['signal_day'],entry_day=a['day'],sector=st['sector'],member_tech407=st['sid'] in tech,initial_q=a['q'],initial_price=a['price'],PVR_score=st['PVR_score'],
            status=r['status'],NET80=r['whole_round_NET80'],return_on_actual_buy_cash=r['conditional_return_on_actual_buy_cash'],actual_buy_cash=r['whole_round_actual_buy_cash']))
    # Counts are decision-path stages, not independently recomputed alternative cohorts.
    funnel=dict(raw_AB_events=6878,raw_membership_events=1319 if arm=='tech407' else 6878,
        evaluated_decisions=len(decisions),decisions_by_label=dict(collections.Counter(x['decision'] for x in decisions)),
        current_state_blocked=sum(x['stock_state_before']!='FLAT' for x in decisions),
        flat_I_qualified=sum(x['stock_state_before']=='FLAT' and x['I_qualified'] in (True,1) for x in decisions),
        flat_I_PVR_known=sum(x['stock_state_before']=='FLAT' and x['I_qualified'] in (True,1) and x['PVR_known'] in (True,1) and x['queue_rank']==x['queue_rank'] for x in decisions),
        close_PASS=sum(x.get('close_check')=='PASS' for x in decisions),selected_top2=sum(x['selected'] for x in decisions),
        selected_initial_zero_liability_UNKNOWN=liability_free_unknown_count(data['AUDIT']),
        actual_initial_fills=len(init_ids),actual_ADD_fills=sum(a['side']=='buy_add' for a in actions),
        closed_whole_rounds=closed['closed'],closed_initial_layers=core['closed'],closed_ADD_layers=add['closed'])
    meanrisk=sum((D(o['risk']) for o in filled),ZERO)/len(filled) if filled else None
    initial_buy_cash=sum((D(x['buy_cash']) for x in layers if x['layer']=='core'),ZERO)
    source_hashes=data['SOURCE_HASHES']
    summary=dict(arm=arm,resources=status,initial_layers=core,ADD_layers=add,whole_rounds=closed,funnel=funnel,
        certified_full_NAV_path=full_cert,final_NAV=endnav,total_return=(endnav/D(1200000)-1) if full_cert and endnav is not None else None,
        close_to_close_max_drawdown=dd,drawdown_peak_day=ddpeakday,drawdown_trough_day=troughday,drawdown_definition='439 daily CLOSE NAV observations plus initial seed; OPEN certification also required; no intraday drawdown claim',
        first_uncertified=result['first_uncertified'],unknown_terminal_states=[{**st,'sid':sid} for sid,st in data['STATES'].items() if st['state']=='UNKNOWN'],
        first_INIT_mean_fee_inclusive_planned_risk=meanrisk,initial_total_buy_cash=initial_buy_cash,initial_mean_buy_cash=initial_buy_cash/len(filled) if filled else None,
        initial_total_shares=sum(a['q'] for a in actions if a['side']=='buy_core'),claims=len(data['CLAIMS']),claim_paid=sum((D(x['amount']) for x in data['CLAIMS'] if x['settled']),ZERO),used_source_count=len(source_hashes))
    return summary,lifecycle,data

def both():
    assert read(HERE/'BASELINE_EXACT_EQUIVALENCE.json')['all_match']
    sa,la,da=account('all1709');st,lt,dt=account('tech407')
    key=lambda x:(x['event_id'],x['sid'])
    ka={key(x):x for x in la};kt={key(x):x for x in lt};assert len(ka)==len(la) and len(kt)==len(lt)
    differences=dict(common=[dict(all1709=ka[k],tech407=kt[k]) for k in sorted(set(ka)&set(kt))],
        all1709_only=[ka[k] for k in sorted(set(ka)-set(kt))],tech407_only=[kt[k] for k in sorted(set(kt)-set(ka))])
    sources_a=da['SOURCE_HASHES'];sources_t=dt['SOURCE_HASHES'];common=set(sources_a)&set(sources_t)
    assert all(sources_a[p]==sources_t[p] for p in common)
    result=dict(all1709=sa,tech407=st,comparison=dict(common_actual_births=len(differences['common']),all1709_only_actual_births=len(differences['all1709_only']),tech407_only_actual_births=len(differences['tech407_only']),
        source_shared_count=len(common),source_only_all1709=sorted(set(sources_a)-set(sources_t)),source_only_tech407=sorted(set(sources_t)-set(sources_a)),shared_source_hashes_equal=True),
        limits=['Fixed future membership and classification NON-PIT','September to December 2024 birth cohort; follow-up through June 30 2026, not continuous full-year admission','Original conditional daily OPEN +/-5bp proxy, original daily capacity/eligibility limitations unchanged','No inferred counterfactual PnL; each observed path retains own quantities fees claims and exits','This current M3 admission-mask result cannot explain the entire difference versus old S 48.44%'])
    save(HERE/'COMPARATIVE_SUMMARY.json',result);save(HERE/'ACTUAL_BIRTH_PATH_COMPARISON.json',differences)
    save(HERE/'FILLED_ROUND_IDENTITIES_ALL1709.json',la);save(HERE/'FILLED_ROUND_IDENTITIES_TECH407.json',lt)
    print(json.dumps({k:{m:v for m,v in s.items() if m in ('arm','initial_layers','ADD_layers','whole_rounds','certified_full_NAV_path','final_NAV','total_return','close_to_close_max_drawdown')} for k,s in [('all1709',sa),('tech407',st)]},ensure_ascii=False,default=str))
if __name__=='__main__':baseline() if sys.argv[1]=='baseline' else both()
