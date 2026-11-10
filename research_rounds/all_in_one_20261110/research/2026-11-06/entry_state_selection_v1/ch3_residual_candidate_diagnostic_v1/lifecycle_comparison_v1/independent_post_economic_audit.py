"""Read-only audit of the one completed run. No engine import or lifecycle replay."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
import argparse, collections, hashlib, json
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
E=O.parent.parent/'m3_stock_birth_during_sector_v1'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
ARMS=['A_UNION_B','RAW_MOM11','CH3_RM']
CLOSED='COMPLETE_CONDITIONAL_STOCK_ROUND'
OLD={'2022':E/'relative_priority_equity_run_2022_v1','2024_924':E/'cash_equity_baseline_2024_v1'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def csv(p):return pd.read_csv(p,float_precision='round_trip',low_memory=False)
def close(a,b,tol=1e-7):assert abs(float(a)-float(b))<=tol,(a,b)
parser=argparse.ArgumentParser()
parser.add_argument('--partial-window',choices=['2022','2024_924'])
args=parser.parse_args()
if not args.partial_window:assert (O/'COMPLETION.json').exists(),'Run must finish before the full audit'
audit=read(O/'PRE_ECONOMIC_AUDIT.json')
assert audit['result']=='PASS_PRE_ECONOMIC_IMPLEMENTATION'
for p,h in audit['implementation_hashes'].items():assert sha(O/p)==h
rules=read(B/'inputs-v2/market-rules.json')
approved=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
manifest={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')}
price_cache={}
with np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False) as h:
    common_calendar=pd.DatetimeIndex(h['dates'])
common_calendar=common_calendar[common_calendar<=pd.Timestamp('2026-06-30')]
def prices(sid):
    if sid not in price_cache:
        p=next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet'))
        assert sha(p)==manifest[sid]['source_sha256'][p]
        price_cache[sid]=pd.read_parquet(p,columns=['raw_open'])
    return price_cache[sid]
def version(rows,day):
    rows=[r for r in rows if r['from']<=day and (not r.get('to') or day<r['to'])]
    assert len(rows)==1
    r=rows[0]
    assert r['basis']=='official_rule' and r['verification_status']=='verified' or r['basis']=='explicit_research_proxy' and r.get('proxy_id') in approved
    return r
fee_cache={}
def independent_fee(sid,day,q,px,side):
    key=(sid,day)
    if key not in fee_cache:
        venue=version(rules['venue_versions'][sid],day)['venue']
        fee_cache[key]=version(rules['fee_versions'][venue],day)['schedule']['components']
    total=D(0)
    for c in fee_cache[key]:
        if c.get('side','both') not in ('both',side):continue
        basis=c.get('amount_basis','notional')
        base=D(q)*px if basis=='notional' else D(q) if basis=='shares' else D(q)*D(str(rules['security_metadata'][sid]['par_value']))
        amount=max(D(str(c.get('minimum_local',0))),base*D(str(c['rate'])))
        if c.get('maximum_local') is not None:amount=min(amount,D(str(c['maximum_local'])))
        if c.get('rounding_unit') is not None:
            unit=D(str(c['rounding_unit']))
            amount=(amount/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*unit
        total+=amount
    return total

per_arm=[];baseline_checks={};all_rounds=[];all_actions=[];all_claims=[]
for window in ([args.partial_window] if args.partial_window else ['2022','2024_924']):
    original=OLD[window]/('dynamic' if window=='2022' else 'economic')
    registry={e['economic_event_id']:e for e in read(OLD[window]/'ECONOMIC_EVENTS.json')}
    assert len(registry)==(436 if window=='2022' else 165)
    for arm in ARMS:
        root=O/window/arm
        for name,h in read(root/'COMPLETE_OUTPUT_HASHES.json').items():assert sha(root/name)==h,(window,arm,name)
        z=csv(root/'CORE_AND_FULL_ROUNDS.csv');a=csv(root/'ACTIONS.csv');dec=csv(root/'DECISIONS.csv')
        regs=csv(root/'REGISTRATIONS.csv');ledger=csv(root/'CLAIM_LEDGER.csv');claims=read(root/'CLAIMS.json');bridges=read(root/'BRIDGES.json')
        assert z.arm.eq(arm).all() and a.arm.eq(arm).all() and dec.arm.eq(arm).all()
        assert z.round_id.is_unique and z.event_id.is_unique
        assert len(dec)==(12917 if window=='2022' else 6878)
        assert set(z.round_id)==set(dec.loc[dec.selected,'round_id'])
        assert dec.groupby(['day','sector']).selected.sum().le(2).all()
        if arm=='A_UNION_B':
            checks={}
            for name in ['ROUNDS','ACTIONS','DECISIONS','RANKING_AUDIT','END_STATES','REGISTRATIONS','CLAIM_LEDGER','PROFIT_GATES']:
                actual=csv(root/(name+'.csv'));expected=csv(original/(name+'.csv'));expected=expected[expected.arm.eq(arm)].reset_index(drop=True)
                for col in expected:
                    if col not in actual:assert expected[col].isna().all();actual[col]=np.nan
                pd.testing.assert_frame_equal(actual[expected.columns].reset_index(drop=True),expected,check_dtype=False,check_exact=False,atol=1e-7,rtol=1e-12)
                checks[name]=len(expected)
            for name in ['CLAIMS','BRIDGES']:
                expected=[r for r in read(original/(name+'.json')) if r['arm']==arm]
                assert read(root/(name+'.json'))==expected
                checks[name]=len(expected)
            baseline_checks[window]=checks
        else:
            qa=csv(root/'CH3_QUEUE_AUDIT.csv')
            assert len(qa)==len(dec) and qa.event_id.is_unique and set(qa.event_id)==set(dec.event_id)
            dd=dec.set_index('event_id')
            assert set(qa.loc[qa.feasible,'event_id'])==set(dec.loc[dec.decision.isin(['SELECTED_PENDING','PASS_NOT_TOP2']),'event_id'])
            for _,g in qa.groupby(['day','sector']):
                g=g[g.feasible].sort_values(['PVR_score','sid'],ascending=[False,True])
                K=min(2,len(g));assert g.K.eq(K).all()
                known=g[g.known];score='RM' if arm=='CH3_RM' else 'RAW_MOM11'
                order=known.sort_values([score,'PVR_score','sid'],ascending=[False,False,True])
                mapping=dict(zip(order.event_id,known.old_feasible_rank))
                expected=np.array([mapping.get(r.event_id,r.old_feasible_rank) for r in g.itertuples()])
                assert np.array_equal(expected,g.new_feasible_rank)
                assert np.array_equal(expected<=K,dd.loc[g.event_id,'selected'])
        by_round={rid:g for rid,g in a.groupby('round_id',sort=False)}
        # Trade prices and dated fees are reconstructed independently from raw opens and rule records.
        for r in a.itertuples():
            side='buy' if r.side.startswith('buy') else 'sell';q=int(r.q);px=D(str(r.price))
            assert q>0
            raw=D(str(prices(r.sid).loc[pd.Timestamp(r.day),'raw_open']))
            close(px,raw*(1+D('.0005') if side=='buy' else 1-D('.0005')),1e-9)
            close(r.fee,independent_fee(r.sid,r.day,q,px,side),1e-8)
        # Registration snapshots use actual confirmed core/add inventory at record CLOSE.
        by_stock={sid:g for sid,g in a.groupby('sid',sort=False)}
        for r in regs.itertuples():
            if r.state=='UNKNOWN':
                assert pd.isna(r.record_q) and pd.isna(r.core_record_q)
                continue
            prior=by_stock.get(r.sid,pd.DataFrame(columns=a.columns))
            prior=prior[prior.day<=str(r.inventory_snapshot_day)[:10]]
            inv=sum((int(t.q) if t.side.startswith('buy') else -int(t.q)) for t in prior.itertuples())
            assert inv==int(r.record_q)
            if r.state=='HELD':
                own=by_round[r.owner_round_id];own=own[own.day<=str(r.inventory_snapshot_day)[:10]]
                core=sum(int(t.q) for t in own.itertuples() if t.side=='buy_core')
                assert not own.side.eq('sell_all').any() and core==int(r.core_record_q)
            else:assert inv==int(r.core_record_q)==0
        owners=collections.defaultdict(list)
        for c in claims:
            assert c['arm']==arm and c['owner_round_id'] in set(z.round_id)
            event=registry[c['economic_event_id']];assert event['entitlement_verified']
            assert c['sid']==event['sid'] and c['key'][:3]==[window,arm,c['sid']]
            assert c['record_date']==event['record_date'] and c['ex_date']==event['ex_date'] and c['pay_date']==event['pay_date']
            close(c['amount'],D(c['record_q'])*D(event['d_cash'])*D('.8'),1e-9)
            close(c['core_amount'],D(c['core_record_q'])*D(event['d_cash'])*D('.8'),1e-9)
            registration=regs[(regs.economic_event_id==c['economic_event_id']) & (regs.owner_round_id==c['owner_round_id'])]
            assert len(registration)==1 and registration.iloc[0].record_q==c['record_q'] and registration.iloc[0].core_record_q==c['core_record_q']
            events=ledger[(ledger.round_id==c['owner_round_id']) & (ledger.economic_event_id==c['economic_event_id'])]
            assert events.event.eq('ACCRUE_NET80').sum()==int(c['recognized'])
            assert events.event.eq('PAY_CLOSE_TRANSFER').sum()==int(c['settled'])
            for row in events.itertuples():
                expected=event['ex_date'] if row.event=='ACCRUE_NET80' else event['pay_date']
                assert str(row.day)[:10]==str(expected)[:10];close(row.amount,c['amount'])
                if row.event=='ACCRUE_NET80':close(row.cash_delta,0);close(row.receivable_delta,c['amount'])
                else:close(row.cash_delta,c['amount']);close(row.receivable_delta,-D(c['amount']))
            owners[c['owner_round_id']].append(c)
        for r in z.itertuples():
            trades=by_round.get(r.round_id,pd.DataFrame(columns=a.columns))
            cc=owners[r.round_id]
            qty=0;cash=D(0);spent=D(0);fees=D(0);bought=collections.defaultdict(int)
            for t in trades.itertuples():
                q=int(t.q);px=D(str(t.price));fee=D(str(t.fee));buy=t.side.startswith('buy')
                if t.side=='buy_add':
                    raw=D(str(prices(r.sid).loc[pd.Timestamp(t.day),'raw_open']));sell_px=raw*(1-D('.0005'))
                    accrued=sum((D(c['amount']) for c in cc if c['recognized'] and str(c['ex_date'])[:10]<=t.day),D(0))
                    prior_net=cash+accrued+D(qty)*sell_px-independent_fee(r.sid,t.day,qty,sell_px,'sell')
                    close(t.prior_round_net,prior_net)
                    assert prior_net>0
                if buy:qty+=q;bought[t.day]+=q;cash-=q*px+fee;spent+=q*px+fee
                else:assert q<=qty-bought[t.day];qty-=q;cash+=q*px-fee
                fees+=fee
                assert qty>=0
            recognized=sum((D(c['amount']) for c in cc if c['recognized']),D(0))
            paid=sum((D(c['amount']) for c in cc if c['settled']),D(0))
            corediv=sum((D(c['core_amount']) for c in cc if c['recognized']),D(0))
            close(r.dividend_net80_total,recognized);close(r.dividend_net80_paid,paid)
            close(r.cash_after_payouts,cash+paid);close(r.receivable_after_payouts,recognized-paid)
            if len(trades):
                assert qty==int(r.core_qty+r.add_qty);close(r.total_buy_cash,spent);close(r.all_fees,fees)
                assert trades.side.eq('buy_core').sum()==1 and trades.side.eq('buy_add').sum()<=1
                assert trades[trades.side.eq('buy_add')].prior_round_net.gt(0).all()
                assert pd.Timestamp(r.entry_day)==common_calendar[common_calendar>pd.Timestamp(r.signal_day)][0]
                assert r.entry_q>0 and r.entry_risk<=3000+1e-7 and r.entry_q*r.entry_price+r.entry_fee<=24000+1e-7
            if r.status==CLOSED:
                assert qty==0 and r.exit_reason=='I_STRUCTURE_EXIT'
                close(r.net_pnl,cash+recognized);close(r.net_return_on_buy_cash,D(str(r.net_pnl))/spent,1e-12)
                bf=independent_fee(r.sid,r.entry_day,int(r.entry_q),D(str(r.entry_price)),'buy')
                sf=independent_fee(r.sid,r.exit_day,int(r.entry_q),D(str(r.exit_price)),'sell')
                close(r.core_buy_fee,bf);close(r.core_sell_fee,sf);close(r.core_dividend_net80,corediv)
                cost=D(int(r.entry_q))*D(str(r.entry_price))+bf
                net=D(int(r.entry_q))*D(str(r.exit_price))-sf-cost+corediv
                close(r.core_net,net);close(r.core_buy_cash,cost);close(r.core_return,net/cost,1e-12)
                assert r.evidence_usable_closed==(r.financial_coverage_status in ['VERIFIED_ACTIONS_SCENARIO','LOCAL_NO_ACTION_EVIDENCE'])
            else:assert not r.evidence_usable_closed and pd.isna(r.core_net) and pd.isna(r.core_return)
        for sid,g in z[z.entry_day.notna()].groupby('sid'):
            g=g.sort_values('entry_day');previous=None
            for r in g.itertuples():
                if previous is not None:assert r.entry_day>previous
                previous=r.exit_day if r.status==CLOSED else '2026-06-30'
        for b in bridges:
            assert b['arm']==arm and b['economic_event_id'] in registry and b['round_id'] in set(z.round_id)
            if b['kind']=='PENDING_COORDINATE_Q0':assert b['record_q']==0 and b['dividend']==0
        per_arm.append(dict(window=window,arm=arm,rounds=len(z),actions=len(a),claims=len(claims),registrations=len(regs),bridges=len(bridges),closed=int(z.status.eq(CLOSED).sum()),usable=int(z.evidence_usable_closed.sum()),execution_unknown=int(z.status.str.contains('UNKNOWN').sum()),nofill=int(z.status.str.contains('NOFILL').sum()),censored=int(z.status.str.contains('CENSORED').sum())))
        all_rounds.append(z);all_actions.append(a);all_claims+=claims

if args.partial_window:
    partial=dict(status='PASS_PARTIAL_WINDOW_LEDGER_AUDIT',window=args.partial_window,per_arm=per_arm,baseline_exact_tables=baseline_checks,new_lifecycle_runs_by_auditor=0,aggregate_report_not_yet_audited=True)
    (O/('POST_ECONOMIC_'+args.partial_window+'_PARTIAL_AUDIT.json')).write_text(json.dumps(partial,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(partial,ensure_ascii=False,indent=2))
    raise SystemExit(0)

z=pd.concat(all_rounds,ignore_index=True);z['window']=z.window.astype(str)
published=csv(O/'report/CORE_AND_FULL_ROUNDS.csv')
assert set(z.round_id)==set(published.round_id) and z.round_id.is_unique
performance=csv(O/'report/PERFORMANCE.csv')
for r in performance.itertuples():
    g=z[z.window.eq(str(r.window))&z.arm.eq(r.arm)]
    if r.scope=='EVIDENCE_USABLE_CLOSED':g=g[g.evidence_usable_closed]
    elif r.scope=='CLOSED_FINANCIAL_UNKNOWN':g=g[g.status.eq(CLOSED)&g.financial_coverage_status.eq('COVERAGE_UNKNOWN')]
    c=g[g.status.eq(CLOSED)];p='core_net' if r.layer=='core' else 'net_pnl';ret='core_return' if r.layer=='core' else 'net_return_on_buy_cash'
    win=c[c[p]>0];loss=c[c[p]<0];zero=c[c[p]==0]
    assert r.admitted==len(g) and r.closed==len(c) and r.wins==len(win) and r.losses==len(loss) and r.zeros==len(zero)
    assert r.execution_unknown==g.status.str.contains('UNKNOWN').sum() and r.financial_unknown_closed==c.financial_coverage_status.eq('COVERAGE_UNKNOWN').sum()
    assert r.nofill==g.status.str.contains('NOFILL').sum() and r.censored==g.status.str.contains('CENSORED').sum()
    if len(c):
        close(r.net_win_rate,len(win)/len(c),1e-12);close(r.mean_net_cny,c[p].mean());close(r.mean_return,c[ret].mean(),1e-12)
    else:assert pd.isna(r.net_win_rate) and pd.isna(r.mean_net_cny)
    close(r.independent_net_sum,c[p].sum());close(r.winner_total_cny,win[p].sum());close(r.loser_total_cny,loss[p].sum())
    if len(win):close(r.winner_mean_cny,win[p].mean())
    if len(loss):close(r.loser_mean_cny,loss[p].mean())
    if len(win) and len(loss):close(r.payoff_cny,win[p].mean()/abs(loss[p].mean()),1e-12)
    assert r.tail_ge50==c[ret].ge(.5).sum()
    div='core_dividend_net80' if r.layer=='core' else 'full_dividend_net80'
    for col,actual in [('gross_raw_open_sum',c[r.layer+'_gross_raw_open_pnl'].sum()),('slippage_drag_sum',c[r.layer+'_slippage_drag'].sum()),('gross_after_slippage_sum',c[r.layer+'_gross_after_slippage_pnl'].sum()),('fees_sum',c[r.layer+'_fees'].sum()),('dividend_net80_sum',c[div].sum())]:close(getattr(r,col),actual)
    close(r.gross_raw_open_sum-r.slippage_drag_sum-r.fees_sum+r.dividend_net80_sum,r.independent_net_sum,1e-6)

participation=csv(O/'report/BASELINE_SAME_STOCK_PARTICIPATION.csv')
pairs=csv(O/'report/BASELINE_SAME_STOCK_ROUND_PAIRS.csv')
index=z.set_index('round_id')
for r in participation.itertuples():
    baseline=index.loc[r.baseline_round_id]
    same=z[z.window.eq(str(r.window))&z.arm.eq(r.arm)&z.sid.eq(r.sid)]
    entries=same[same.entry_day.notna()];event=same[same.event_id.eq(r.baseline_event_id)]
    assert r.any_same_stock_actual_entry==bool(len(entries)) and r.same_stock_actual_entry_rounds==len(entries)
    assert r.same_event_retained==bool(len(event)) and r.same_event_entry_confirmed==bool(len(event) and event.entry_day.notna().any())
    assert r.baseline_core_tail50==bool(baseline.evidence_usable_closed and baseline.core_return>=.5)
    assert r.baseline_full_tail50==bool(baseline.evidence_usable_closed and baseline.net_return_on_buy_cash>=.5)
    matching=pairs[pairs.baseline_round_id.eq(r.baseline_round_id)&pairs.arm.eq(r.arm)]
    assert set(matching.alternative_round_id)==set(entries.round_id)
    assert r.confirmed_overlap_rounds==int(matching.overlap_confirmed.sum())
    assert r.confirmed_full_cover_rounds==int(matching.full_cover_confirmed.sum())
for r in pairs.itertuples():
    alt=index.loc[r.alternative_round_id]
    base=index.loc[r.baseline_round_id]
    assert alt.sid==r.sid and alt.arm==r.arm and str(alt.window)==str(r.window)
    left=pd.Timestamp(alt.entry_day)
    right=pd.Timestamp(alt.exit_day) if alt.status==CLOSED else pd.Timestamp(alt.last_known_mark_day) if pd.notna(alt.last_known_mark_day) else left
    base_left=pd.Timestamp(base.entry_day) if pd.notna(base.entry_day) else None
    base_right=pd.Timestamp(base.exit_day) if base.status==CLOSED else pd.Timestamp(base.last_known_mark_day) if pd.notna(base.last_known_mark_day) else None
    overlap=base_left is not None and base_right is not None and max(left,base_left)<min(right,base_right)
    assert r.overlap_confirmed==overlap
    assert r.full_cover_confirmed==bool(overlap and left<=base_left and right>=base_right)
    assert pd.Timestamp(r.alternative_confirmed_prefix_end)==right
    for name,target in [('alternative_core_return','core_return'),('alternative_full_return','net_return_on_buy_cash'),('alternative_core_gross','core_gross_after_slippage_pnl'),('alternative_core_net','core_net'),('alternative_full_gross','full_gross_after_slippage_pnl'),('alternative_full_net','net_pnl')]:
        a,b=getattr(r,name),alt[target]
        if pd.isna(a):assert pd.isna(b)
        else:close(a,b)
actual2024=csv(O/'report/2024_ACTUAL_SAME_STOCK_GROSS_NET.csv')
pd.testing.assert_frame_equal(actual2024.reset_index(drop=True),pairs[pairs.window.eq('2024_924')].reset_index(drop=True),check_dtype=False)
unknown=z[z.status.str.contains('UNKNOWN')|z.financial_coverage_status.eq('COVERAGE_UNKNOWN')]
breakdown=csv(O/'report/UNKNOWN_REASON_BREAKDOWN.csv')
assert breakdown['rounds'].sum()==len(unknown)
for (window,arm),g in unknown.groupby(['window','arm']):assert breakdown[breakdown.window.astype(str).eq(window)&breakdown.arm.eq(arm)]['rounds'].sum()==len(g)
report=dict(status='PASS_POST_ECONOMIC_READ_ONLY_AUDIT',baseline_exact_tables=baseline_checks,per_arm=per_arm,
            total_rounds=len(z),total_actions=sum(len(x) for x in all_actions),total_claims=len(all_claims),metrics_rows=len(performance),
            independent_raw_open_and_dated_fee_reconstruction=True,independent_T1_inventory_cash_receivable_and_NET80=True,
            dynamic_rank_and_unknown_slot_reconstruction=True,core_full_denominators_and_all_metrics_recomputed=True,
            same_stock_participation_rows=len(participation),same_stock_actual_round_pairs=len(pairs),actual_2024_rows=len(actual2024),
            new_lifecycle_runs_by_auditor=0,original_sources_changed=0,implementation_hashes=audit['implementation_hashes'],
            output_summary_sha256=sha(O/'report/SUMMARY.json'),limitations=['Finite current-revision non-PIT per-stock conditional results, not shared-account or tradable historical returns.','UNKNOWN and incomplete financial coverage remain nonrandom; no payoff imputation.'])
(O/'POST_ECONOMIC_INDEPENDENT_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
