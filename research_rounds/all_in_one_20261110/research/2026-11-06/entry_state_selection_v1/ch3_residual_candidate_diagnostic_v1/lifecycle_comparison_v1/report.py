"""Read-only outcome accounting. No economic path or parameter is rerun here."""
from pathlib import Path
from decimal import Decimal as D
import json, re, ast
import numpy as np
import pandas as pd
from adapter import O, ARMS, ENGINES, compare_table, save, sha
CLOSED='COMPLETE_CONDITIONAL_STOCK_ROUND'

def derive_original_report(s,window,source):
    # Reuse the frozen financial coverage and initial-lot fee attribution exactly.
    p=ENGINES[window].parent/'report.py';text=p.read_text()
    stop='metrics=[]' if window=='2022' else 'def metric(g,layer):'
    prefix=text[:text.index(stop)]
    prefix=prefix.replace('import engine as s\n','').replace('from engine import pd,np,D,Path\n','')
    line="O=s.O;dest=O/'report';assert not dest.exists();dest.mkdir()"
    assert prefix.count(line)==1;prefix=prefix.replace(line,'O=INPUT_ROOT')
    for name in ['ROUNDS.csv','ACTIONS.csv','DECISIONS.csv','CLAIMS.json','BRIDGES.json']:
        old="O/'"+('dynamic/' if window=='2022' else 'economic/')+name+"'"
        assert prefix.count(old)==1;prefix=prefix.replace(old,"O/'"+name+"'")
    # No output writes are admitted in the extracted attribution prefix.
    assert '.to_csv(' not in prefix and '.write_' not in prefix and '.mkdir(' not in prefix
    ns=dict(s=s,pd=pd,np=np,D=D,Path=Path,INPUT_ROOT=source)
    exec(compile(prefix,str(p)+':coverage_and_core_only','exec'),ns)
    if window=='2022':
        ns['z']['duration_bucket']=pd.cut(ns['z'].holding_calendar_days,[-1,5,20,60,120,365,99999],labels=['0-5','6-20','21-60','61-120','121-365','366+']).astype(str)
    return ns['z'],ns['coverage'] if window=='2022' else ns['cov']

def add_gross(z,a):
    z=z.copy()
    for i,r in z.iterrows():
        if r.status!=CLOSED: continue
        acts=a[a.round_id.eq(r.round_id)];gross=D(0);rawgross=D(0)
        for x in acts.to_dict('records'):
            buy=x['side'].startswith('buy');v=D(int(x['q']))*D(str(x['price']))
            gross+=(-v if buy else v)
            rawgross+=(-v/(1+D('.0005')) if buy else v/(1-D('.0005')))
        div=D(str(r.dividend_net80_total));fees=D(str(r.all_fees));net=gross-fees+div
        assert abs(float(net)-r.net_pnl)<1e-7
        q=D(int(r.entry_q));bp=D(str(r.entry_price));sp=D(str(r.exit_price));cg=q*(sp-bp)
        cr=q*(sp/(1-D('.0005'))-bp/(1+D('.0005')));cf=D(str(r.core_buy_fee))+D(str(r.core_sell_fee));cd=D(str(r.core_dividend_net80))
        assert abs(float(cg-cf+cd)-r.core_net)<1e-7
        vals=dict(full_gross_raw_open_pnl=float(rawgross),full_slippage_drag=float(rawgross-gross),full_gross_after_slippage_pnl=float(gross),full_fees=float(fees),full_dividend_net80=float(div),core_gross_raw_open_pnl=float(cr),core_slippage_drag=float(cr-cg),core_gross_after_slippage_pnl=float(cg),core_fees=float(cf))
        for k,v in vals.items(): z.loc[i,k]=v
    return z

def metric(g,layer):
    p,ret=('core_net','core_return') if layer=='core' else ('net_pnl','net_return_on_buy_cash')
    c=g[g.status.eq(CLOSED)];win=c[c[p]>0];loss=c[c[p]<0];zero=c[c[p]==0]
    wavg=float(win[p].mean()) if len(win) else None;lavg=float(loss[p].mean()) if len(loss) else None
    return dict(admitted=len(g),filled=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),closed=len(c),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),financial_unknown_closed=int(c.financial_coverage_status.eq('COVERAGE_UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),censored=int(g.status.str.contains('CENSORED').sum()),wins=len(win),losses=len(loss),zeros=len(zero),net_win_rate=len(win)/len(c) if len(c) else None,mean_net_cny=float(c[p].mean()) if len(c) else None,mean_return=float(c[ret].mean()) if len(c) else None,winner_total_cny=float(win[p].sum()),winner_mean_cny=wavg,loser_total_cny=float(loss[p].sum()),loser_mean_cny=lavg,payoff_cny=wavg/abs(lavg) if wavg is not None and lavg else None,tail_ge50=int(c[ret].ge(.5).sum()),gross_raw_open_sum=float(c[layer+'_gross_raw_open_pnl'].sum()),slippage_drag_sum=float(c[layer+'_slippage_drag'].sum()),gross_after_slippage_sum=float(c[layer+'_gross_after_slippage_pnl'].sum()),fees_sum=float(c[layer+'_fees'].sum()),dividend_net80_sum=float(c['core_dividend_net80' if layer=='core' else 'full_dividend_net80'].sum()),independent_net_sum=float(c[p].sum()),not_account_return=True)

def report_arm(s,window,arm,source):
    z,cov=derive_original_report(s,window,source)
    a=pd.read_csv(source/'ACTIONS.csv',float_precision='round_trip',low_memory=False)
    z=add_gross(z,a)
    if arm=='A_UNION_B':
        expected=pd.read_csv(ENGINES[window].parent/'report/CORE_AND_FULL_ROUNDS.csv',float_precision='round_trip',low_memory=False)
        expected=expected[expected.arm.eq(arm)]
        qa=compare_table(z,expected,['round_id'])
        assert int(z.evidence_usable_closed.sum())==({'2022':2616,'2024_924':1312}[window])
        save(source/'BASELINE_REPORT_QA.json',qa)
    z.to_csv(source/'CORE_AND_FULL_ROUNDS.csv',index=False);cov.to_csv(source/'FINANCIAL_COVERAGE.csv',index=False)
    return z

def same_stock(z):
    records=[];pairs=[]
    for window,w in z.groupby('window'):
        b=w[w.arm.eq('A_UNION_B')]
        for arm in ARMS[1:]:
            alt=w[w.arm.eq(arm)]
            for r in b.to_dict('records'):
                same=alt[alt.sid.eq(r['sid'])];held=same[same.entry_day.notna()];events=same[same.event_id.eq(r['event_id'])]
                if len(events) and events.entry_day.notna().any():kind='SAME_EVENT_ACTUAL_ENTRY'
                elif len(held):kind='SAME_STOCK_OTHER_ENTRY'
                elif same.status.str.contains('UNKNOWN').any():kind='PARTICIPATION_UNKNOWN'
                else:kind='NO_CONFIRMED_PARTICIPATION'
                rb=pd.Timestamp(r['entry_day']) if pd.notna(r['entry_day']) else None
                re_=pd.Timestamp(r['exit_day']) if r['status']==CLOSED else pd.Timestamp(r['last_known_mark_day']) if pd.notna(r.get('last_known_mark_day')) else None
                overlaps=0;full=0
                for rr in held.to_dict('records'):
                    left=pd.Timestamp(rr['entry_day']);right=pd.Timestamp(rr['exit_day']) if rr['status']==CLOSED else pd.Timestamp(rr['last_known_mark_day']) if pd.notna(rr.get('last_known_mark_day')) else left
                    overlap=rb is not None and re_ is not None and max(rb,left)<min(re_,right)
                    cover=overlap and left<=rb and right>=re_;overlaps+=int(overlap);full+=int(cover)
                    pairs.append(dict(window=window,arm=arm,baseline_event_id=r['event_id'],baseline_round_id=r['round_id'],alternative_event_id=rr['event_id'],alternative_round_id=rr['round_id'],sid=r['sid'],name=r['name'],baseline_entry=r['entry_day'],baseline_exit=r['exit_day'],alternative_entry=rr['entry_day'],alternative_exit=rr['exit_day'],alternative_confirmed_prefix_end=str(right.date()),alternative_status=rr['status'],alternative_evidence_usable_closed=rr['evidence_usable_closed'],overlap_confirmed=overlap,full_cover_confirmed=cover,baseline_core_return=r.get('core_return'),baseline_full_return=r.get('net_return_on_buy_cash'),alternative_core_return=rr.get('core_return'),alternative_full_return=rr.get('net_return_on_buy_cash'),alternative_core_gross=rr.get('core_gross_after_slippage_pnl'),alternative_core_net=rr.get('core_net'),alternative_full_gross=rr.get('full_gross_after_slippage_pnl'),alternative_full_net=rr.get('net_pnl')))
                records.append(dict(window=window,arm=arm,baseline_event_id=r['event_id'],baseline_round_id=r['round_id'],sid=r['sid'],name=r['name'],baseline_status=r['status'],baseline_evidence_usable_closed=r['evidence_usable_closed'],baseline_core_return=r.get('core_return'),baseline_full_return=r.get('net_return_on_buy_cash'),baseline_core_tail50=bool(r['status']==CLOSED and r['evidence_usable_closed'] and r.get('core_return',-1)>=.5),baseline_full_tail50=bool(r['status']==CLOSED and r['evidence_usable_closed'] and r.get('net_return_on_buy_cash',-1)>=.5),conditional_core_tail50=bool(r['status']==CLOSED and r.get('core_return',-1)>=.5),conditional_full_tail50=bool(r['status']==CLOSED and r.get('net_return_on_buy_cash',-1)>=.5),participation=kind,same_event_retained=bool(len(events)),same_event_entry_confirmed=bool(len(events) and events.entry_day.notna().any()),any_same_stock_actual_entry=bool(len(held)),same_stock_rounds=len(same),same_stock_actual_entry_rounds=len(held),confirmed_overlap_rounds=overlaps,confirmed_full_cover_rounds=full,unknown_same_stock_rounds=int(same.status.str.contains('UNKNOWN').sum())))
    return pd.DataFrame(records),pd.DataFrame(pairs)

def aggregate():
    assert not (O/'report').exists();dest=O/'report';dest.mkdir()
    frames=[];decisions=[];acts=[];claims=[]
    for window in ['2022','2024_924']:
        for arm in ARMS:
            p=O/window/arm
            frames.append(pd.read_csv(p/'CORE_AND_FULL_ROUNDS.csv',float_precision='round_trip',low_memory=False))
            decisions.append(pd.read_csv(p/'DECISIONS.csv',float_precision='round_trip',low_memory=False))
            acts.append(pd.read_csv(p/'ACTIONS.csv',float_precision='round_trip',low_memory=False))
            claims+=json.loads((p/'CLAIMS.json').read_text())
    z=pd.concat(frames,ignore_index=True);z['window']=z.window.astype(str);d=pd.concat(decisions,ignore_index=True);a=pd.concat(acts,ignore_index=True)
    feat=pd.read_csv(O/'ALL_MARKET_STOCK_MONTH_FEATURES.csv');z['month']=z.signal_day.str[:7]
    z=z.merge(feat,on=['sid','month'],validate='many_to_one',suffixes=('','_feature'))
    assert z.status_feature.notna().all()
    metrics=[]
    for (window,arm),g in z.groupby(['window','arm']):
        for layer in ['core','full']:
            for scope,gg in [('ALL_CONDITIONAL_EXECUTION',g),('EVIDENCE_USABLE_CLOSED',g[g.evidence_usable_closed]),('CLOSED_FINANCIAL_UNKNOWN',g[g.status.eq(CLOSED)&g.financial_coverage_status.eq('COVERAGE_UNKNOWN')])]:
                metrics.append(dict(window=window,arm=arm,layer=layer,scope=scope,**metric(gg,layer)))
    coverage=z.groupby(['window','arm','status','financial_coverage_status','status_feature'],dropna=False).size().reset_index(name='rounds')
    unknown=z[z.status.str.contains('UNKNOWN')|z.financial_coverage_status.eq('COVERAGE_UNKNOWN')].groupby(['window','arm','status','failure_phase','financial_coverage_status','coverage_reasons'],dropna=False).size().reset_index(name='rounds')
    unknown.to_csv(dest/'UNKNOWN_REASON_BREAKDOWN.csv',index=False)
    common=[]
    for window,w in z.groupby('window'):
        base=w[w.arm.eq('A_UNION_B')].set_index('event_id')
        for arm in ARMS[1:]:
            alt=w[w.arm.eq(arm)].set_index('event_id')
            for eid in sorted(set(base.index)&set(alt.index)):
                b=base.loc[eid];r=alt.loc[eid]
                fields=['status','entry_day','entry_q','entry_price','exit_day','exit_price','net_pnl','core_net','dividend_net80_total','added_q','financial_coverage_status']
                compare_table(pd.DataFrame([r[fields]]).assign(id=1),pd.DataFrame([b[fields]]).assign(id=1),['id'])
                ba=a[a.round_id.eq(b.round_id)][['day','side','q','price','fee','reason']].reset_index(drop=True)
                aa=a[a.round_id.eq(r.round_id)][['day','side','q','price','fee','reason']].reset_index(drop=True)
                pd.testing.assert_frame_equal(ba,aa,check_exact=False,atol=1e-7,rtol=1e-12)
                keys=['economic_event_id','record_q','core_record_q','amount','core_amount','recognized','settled']
                bc=[{k:c[k] for k in keys} for c in claims if c['owner_round_id']==b.round_id]
                rc=[{k:c[k] for k in keys} for c in claims if c['owner_round_id']==r.round_id]
                assert bc==rc,(eid,'same-event claims')
                common.append(dict(window=window,arm=arm,event_id=eid,actions_claims_outcomes_identical=True))
    participation,pairs=same_stock(z)
    for name,frame in [('CORE_AND_FULL_ROUNDS',z),('PERFORMANCE',pd.DataFrame(metrics)),('FULL_STATUS_COVERAGE',coverage),('COMMON_EVENT_QA',pd.DataFrame(common)),('BASELINE_SAME_STOCK_PARTICIPATION',participation),('BASELINE_SAME_STOCK_ROUND_PAIRS',pairs)]:frame.to_csv(dest/(name+'.csv'),index=False)
    participation[participation.baseline_core_tail50|participation.baseline_full_tail50].to_csv(dest/'BASELINE_TAIL50_PARTICIPATION.csv',index=False)
    pairs[pairs.window.eq('2024_924')].to_csv(dest/'2024_ACTUAL_SAME_STOCK_GROSS_NET.csv',index=False)
    save(dest/'SUMMARY.json',dict(metrics=metrics,common_market_event_checks=len(common),status_counts={str(k):int(v) for k,v in z.groupby(['window','arm','status']).size().items()},limitations=['Not a shared account or strategy-effect estimate','Current revision CH3 factors, historical release UNKNOWN, not PIT','Native adjusted close is not certified total shareholder return','Static current pool and industry mapping','Window-specific finite admitted action sets preserved unchanged','Unknown execution and financial coverage are nonrandom; no unknown payoff imputation','Core is initial lot at the actual FULL entry/exit with standalone dated fees, not another lifecycle','FAST unchanged and not included','Gross-after-slippage uses actual conditional fill prices; raw-open gross/slippage/fees/NET80 shown separately']))
    save(dest/'OUTPUT_HASHES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file()})
    print(pd.DataFrame(metrics).to_string(index=False),flush=True)
if __name__=='__main__': aggregate()
