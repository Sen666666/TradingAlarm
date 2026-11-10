"""Pure price-event table over frozen TR/MA; no project account imports."""
from pathlib import Path
from decimal import Decimal as D
from collections import deque
import argparse,csv,hashlib,json,time
O=Path(__file__).resolve().parent;ROOT=O.parent
H=ROOT/'benchmark_2022_2023/inputs/510300_history.csv'
F=ROOT/'benchmark_2022_2023/INPUT_FREEZE.json'
C=ROOT/'ar6_native_feasibility/ma63_recovery_chain_v1/DAILY.csv'
E=ROOT/'ar6_native_feasibility/ma63_recovery_chain_v1/ALL_EPISODES.json'
P=ROOT/'pvr_pool_feasibility/ma63_incremental_rights_card_v1/H_RECOVERY_MA63_NEW20_NECESSARY_CARD.txt'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def write(name,rows):
    with (O/name).open('w',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def dec(v):
    try:x=D(v);return x if x.is_finite() and x>0 else None
    except:return None
def freeze():
    assert sha(H)==read(F)['inputs'][str(H)],'frozen TR source drift'
    value=dict(scope='pure potential necessary price certificates only',before_event_extraction=True,
        sources={str(p):sha(p)for p in (H,F,C,E,P,Path(__file__),O/'CARD.txt')},
        account_or_riskledger_or_H_calendar_inputs=False,TR_or_MA_recomputed=False)
    if(O/'SOURCE_FREEZE.json').exists():assert read(O/'SOURCE_FREEZE.json')==value
    else:save('SOURCE_FREEZE.json',value)
    return value
def main(execute=False):
    z=freeze()
    if not execute:print('SOURCE_FROZEN_NO_EVENTS',sha(O/'SOURCE_FREEZE.json'),flush=True);return
    assert not(O/'STATISTICS.json').exists(),'single event extraction only'
    started=time.monotonic();history=list(csv.DictReader(H.open()));clock=list(csv.DictReader(C.open()));episodes=read(E)
    assert len(clock)==484 and len(episodes)==22
    byday={r['day']:r for r in clock};assert len(byday)==484
    prior=deque(maxlen=20);full={};output=[]
    for r in history:
        day=r['date'];x=dec(r['signal_close']);ma=dec(r['ma63']);known20=len(prior)==20 and all(v is not None for _,v in prior)
        hi=max(v for _,v in prior)if known20 else None;known=x is not None and ma is not None and known20
        on=x>ma if x is not None and ma is not None else None
        new20=x>hi if x is not None and hi is not None else None
        event=bool(known and on and new20);full[day]=dict(X=x,MA63=ma,event=event)
        if day in byday:
            c=byday[day];assert on==(c['on']=='True')==(r['on']=='True')
            assert prior[-1][0]<day
            output.append(dict(day=day,decision_close=c['decision_close'],X=x,MA63=ma,prior20_close_high=hi,
                prior20_first_day=prior[0][0]if known20 else'',prior20_last_day=prior[-1][0]if known20 else'',
                all_required_known=known,on=on,strict_new20close_high=new20,potential_certificate=event,
                episode_id=c['episode_id'],episode_type=c['episode_type'],cross_event=c['cross_event'],
                next_benchmark_market_OPEN=c['benchmark_next_market_OPEN'],actual_H_flat_ACK_available=False,P_granted=False))
        prior.append((day,x))
    assert [r['day']for r in output]==[r['day']for r in clock]
    outby={r['day']:r for r in output};events=[r for r in output if r['potential_certificate']]
    summaries=[];up=[]
    for e in episodes:
        rows=[outby[d]for d in e['signal_days']];es=[r for r in rows if r['potential_certificate']]
        assert all(r['episode_id']==e['episode_id']for r in rows)
        q=dict(episode_id=e['episode_id'],type=e['type'],start_kind=e['start_kind'],start_day=e['start_day'],last_same_state_day=e['last_same_state_day'],
            next_cross_day=e['next_cross_day'],observations=len(rows),left_censored=e['initial_left_censored'],right_censored=e['right_censored'],
            start_day_certificate=rows[0]['potential_certificate'],certificate_count=len(es),first_potential_certificate=es[0]['day']if es else'',
            last_potential_certificate=es[-1]['day']if es else'',all_potential_certificate_days=[r['day']for r in es],
            first_cert_delay_observations=next(i for i,r in enumerate(rows)if r['potential_certificate'])if es else None,
            next_down_close_price_change_from_start_pct=None,nonpositive_start_to_next_down_price_proxy=None,
            next_down_close_price_change_from_first_cert_pct=None,nonpositive_firstcert_to_next_down_price_proxy=None,
            retrospective_price_diagnostic_only=True,actual_H_recovery_computed=False)
        # Future outcomes are annotations AFTER every pure event has been fixed.
        if e['type']=='ON' and e['start_kind']=='UP_CROSS' and e['next_cross_day'] in full:
            end=full[e['next_cross_day']]['X'];begin=full[e['start_day']]['X']
            if end is not None and begin is not None:
                q['next_down_close_price_change_from_start_pct']=(end/begin-1)*100;q['nonpositive_start_to_next_down_price_proxy']=end<=begin
            if es and end is not None:
                first=es[0]['X'];q['next_down_close_price_change_from_first_cert_pct']=(end/first-1)*100;q['nonpositive_firstcert_to_next_down_price_proxy']=end<=first
        summaries.append(q)
        if e['type']=='ON' and e['start_kind']=='UP_CROSS':up.append(q)
    assert len(up)==10 and sum(q['start_kind']=='START_ON'for q in summaries)==1
    write('DAILY_ALL_484.csv',output);write('ALL_POTENTIAL_EVENTS.csv',events)
    save('ALL_22_EPISODES.json',summaries)
    csvsumm=[dict(q,all_potential_certificate_days='|'.join(q['all_potential_certificate_days']))for q in summaries]
    write('ALL_22_EPISODES.csv',csvsumm);write('TRUE_UP_10_PRICE_DIAGNOSTICS.csv',[q for q in csvsumm if q['start_kind']=='UP_CROSS'])
    for p,h in z['sources'].items():assert sha(p)==h,('source changed',p)
    elapsed=time.monotonic()-started
    stats=dict(passed=True,source_rows=len(history),daily_rows=len(output),episodes=22,true_UP_episodes=10,START_ON_episodes=1,
        known_daily_rows=sum(r['all_required_known']for r in output),potential_certificate_days=len(events),
        true_UP_with_any_certificate=sum(q['certificate_count']>0for q in up),true_UP_cert_on_cross=sum(q['start_day_certificate']for q in up),
        true_UP_first_certificate_later_than_cross=sum(q['certificate_count']>0 and not q['start_day_certificate']for q in up),
        observed_nonpositive_UP_to_nextDOWN_price_episodes=sum(q['nonpositive_start_to_next_down_price_proxy']is True for q in up),
        those_with_any_certificate=sum(q['nonpositive_start_to_next_down_price_proxy']is True and q['certificate_count']>0for q in up),
        first_certificate_then_nonpositive_nextDOWN_price_episodes=sum(q['nonpositive_firstcert_to_next_down_price_proxy']is True for q in up),
        seconds=elapsed,Account_or_strategy_or_riskledger_events=0,no_old_H_or_future_flat_calendar_inputs=True,
        permission_scope='potential necessary price evidence only; no actual H->P/fullrisk permission',
        actual_H_to_P_financial_implementation='NOT_AUTHORIZED_NOT_IMPLEMENTED',P_renew_and_C_feedback='STILL_BLOCKED',
        future_price_annotations_never_used_in_certificate=True)
    save('STATISTICS.json',stats);print(json.dumps(stats,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args();main(a.execute)
