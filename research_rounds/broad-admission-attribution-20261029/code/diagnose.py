"""Read actual BSR-1 records; no account creation, orders, or return simulation."""
from pathlib import Path
import sys,json,gzip,collections,hashlib
from decimal import Decimal as D
from bisect import bisect_right
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1]
BASE=ROOT/'research_rounds/broad-stage-reentry-20261029'
sys.path.insert(0,str(BASE/'code'))
import study as B
ZERO,ONE=B.ZERO,B.ONE
def load(p):return json.loads(Path(p).read_text())
def save(p,obj):
    p=O/p;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(B.N.encoded(obj),f,ensure_ascii=False,indent=2,allow_nan=False,default=B.BP.date_default)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    (O/'data').mkdir(exist_ok=False)
    obj=load(BASE/'results/N1.json')
    with gzip.open(BASE/'results/daily.jsonl.gz','rt') as f:ds=[r for r in map(json.loads,f) if r['account']=='N1']
    decisions={r['at']:r for r in obj['decisions']};dmap={r['at']:r for r in ds}
    meta=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').to_dict('index')
    funds=pd.read_csv(BASE/'analysis/funding-causes.csv');records={(r.symbol,r.signal_at):r for r in funds.itertuples()}
    intents={(i['sid'],d['at']):i for d in obj['decisions'] for i in d['intents']}
    assert len(intents)==len(funds)==22871
    audits=collections.defaultdict(list);trades=collections.defaultdict(list)
    for a in obj['audit']:
        if a.get('at'):audits[a['at'][:10]].append(a)
    for t in obj['trades']:trades[t['at'][:10]].append(t)
    cash=[];cashmap={};funded=[]
    for previous,current in zip(ds,ds[1:]):
        day=current['at'][:10];events=audits[day]
        credits=sum((D(a['settlement']['cny_amount']) for a in events if a['kind']=='settle' and not a['settlement']['debit']),ZERO)
        opening_credits=sum((D(a['settlement']['cny_amount']) for a in events if a['kind']=='settle' and not a['settlement']['debit'] and pd.Timestamp(a['at']).time()<=pd.Timestamp('09:30').time()),ZERO)
        spent=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in trades[day] if t['side']=='buy'),ZERO)
        assert D(previous['available'])+credits-spent==D(current['available']),(day,'cash bridge')
        available=D(previous['available'])+opening_credits;buffer=D(previous['nav'])*D('.1');deploy=max(ZERO,available-buffer)
        allocated=[a for a in events if a['kind']=='lot_risk_funded'];group=collections.defaultdict(lambda:ZERO)
        roles=collections.defaultdict(lambda:ZERO)
        for a in allocated:
            i=intents[a['sid'],a['signal_at']];amount=D(a['gross'])+D(a['fees']);group[i['group']]+=amount;roles[i['kind']]+=amount
            funded.append(dict(open_day=day,signal_at=a['signal_at'],symbol=a['sid'],name=meta[a['sid']]['name'],
                kind=i['kind'],group=i['group'],score=i['score'],cash=amount,shares=a['shares'],reason=i['reason']))
        assert sum(group.values(),ZERO)<=deploy
        row=dict(signal_at=previous['at'],open_day=day,previous_nav=D(previous['nav']),previous_inventory=D(previous['inventory']),
             previous_available=D(previous['available']),sale_and_dividend_credits_before_open=opening_credits,
             open_available=available,cash_buffer=buffer,deployable=deploy,
             group0_allocated=group[0],group1_allocated=group[1],mobile_allocated=roles['mobile'],trial_allocated=roles['trial'],
             same_open_buy_actual=spent,close_available=D(current['available']))
        cash.append(row);cashmap[previous['at']]=row
    pd.DataFrame(B.N.encoded(cash)).to_csv(O/'data/daily-cash-bridge.csv',index=False)
    pd.DataFrame(B.N.encoded(funded)).to_csv(O/'data/actual-funded-orders.csv',index=False)
    print('Cash bridge verified',len(cash),flush=True)

    # Original market adapters and stored indicator values only; no account objects.
    B.BP.P.setup('RS');bundle,market=B.R.context(None);facts=B.E.Facts(bundle,market,None)
    cp={s:pd.read_parquet(B.CP/f'{s}.parquet') for s in market.lines}
    fine={s:pd.read_parquet(B.FINE/f'{s}.parquet') for s in market.lines}
    pv={s:pd.read_parquet(B.PV/f'{s}.parquet').score for s in market.lines}
    epochs={};watch=set();lastbuy={};lastflat={};bi=xi=0
    buys=sorted([t for t in obj['trades'] if t['side']=='buy'],key=lambda x:x['at'])
    campaigns=pd.read_csv(BASE/'analysis/campaigns.csv');exits=campaigns[campaigns.account.eq('N1')&campaigns.closed].sort_values('exit_at').to_dict('records')
    rejected=[];named_daily=[];candidate_matches=0
    named=['688498.SH','688256.SH','300308.SZ','300502.SZ','601869.SH','688048.SH']
    for d in ds:
        at=pd.Timestamp(d['at']).to_pydatetime();day=pd.Timestamp(at.date())
        while bi<len(buys) and pd.Timestamp(buys[bi]['at'])<=at:
            t=buys[bi];sid=t['security_id'];lastbuy[sid]=D(t['price'])*facts.factor(sid,pd.Timestamp(t['at']).to_pydatetime());bi+=1
        while xi<len(exits) and pd.Timestamp(exits[xi]['exit_at'])<=at:
            lastflat[exits[xi]['symbol']]=pd.Timestamp(exits[xi]['exit_at']);xi+=1
        clock,stocks,sectors=facts.packet(at,'I');ss={x.sector_id:x for x in sectors};buyable=market.market_buyable(at)
        for s in stocks:
            sid=s.security_id;r=facts.row(sid,at);key=(bool(r.i_target),int(r.segment_id)) if r is not None else (False,-1)
            if epochs.get(sid)!=key:watch.discard(sid);epochs[sid]=key
            event=B.A.eligibility(s,ss,clock,'S0').q is True
            continuing=B.A.eligibility(B.replace(s,buy_allowed=buyable[sid]),ss,clock,'S0').q is True
            if event:watch.add(sid)
            c=cp[sid].loc[day] if day in cp[sid].index else None
            f=fine[sid].loc[day] if day in fine[sid].index else None
            p=float(pv[sid].loc[day]) if day in pv[sid].index and np.isfinite(pv[sid].loc[day]) else None
            warm=bool(continuing and r.g_ready and r.g_grade>=2 and p is not None and p>50)
            confirm=bool(sid in watch and warm and c is not None and bool(c.receipt))
            held=bool(d['positions'].get(sid,0));previous_exit=lastflat.get(sid)
            fr=bool(not held and previous_exit is not None and sid in watch and warm and f is not None and f.event==1 and pd.Timestamp(f.pivot_date).date()>=previous_exit.date())
            trigger=False
            if d['on'] and sid not in d['pending_sells']:
                if held:trigger=bool(any(z['sid']==sid and z['kind']=='core' for z in d['layers']) and confirm and D(str(r.close))>lastbuy[sid])
                else:trigger=event or confirm or fr
            budget_reject=False
            if trigger:
                q=market.quote(sid,at);floor=facts.floor(sid,at,'I')
                if floor is not None and q is not None:
                    budget=min(max(D(d['nav'])*D('.02'),D(q.quantity.buy_minimum)*q.raw_price*D('1.0005')),
                               max(ZERO,D(d['nav'])*D('.1')-d['positions'].get(sid,0)*q.raw_price))
                    cap=q.quantity.buy_floor(int(budget/(q.raw_price*D('1.0005'))))
                    if not cap:
                        budget_reject=True;rejected.append(dict(symbol=sid,name=meta[sid]['name'],at=d['at'],kind='mobile' if held else 'trial',nav=D(d['nav']),
                            raw_price=q.raw_price,minimum_shares=q.quantity.buy_minimum,minimum_gross=D(q.quantity.buy_minimum)*q.raw_price*D('1.0005'),
                            minimum_nav_weight=D(q.quantity.buy_minimum)*q.raw_price*D('1.0005')/D(d['nav']),held_market_value=d['positions'].get(sid,0)*q.raw_price,
                            remaining_single_name_budget=max(ZERO,D(d['nav'])*D('.1')-d['positions'].get(sid,0)*q.raw_price)))
                    else:
                        i=intents[sid,d['at']];assert D(i['budget'])==budget and i['cap']==cap;candidate_matches+=1
            if sid in named:
                named_daily.append(dict(symbol=sid,date=str(day.date()),raw_i_buy=bool(r is not None and day in facts.f[sid].index and r.i_buy),
                     account_on=d['on'],event_s0=event,continuing_s0=continuing,held=held,
                     pending_exit=sid in d['pending_sells'],candidate_before_budget=trigger,
                     single_name_budget_rejected=budget_reject,intent=(sid,d['at']) in intents))
    assert len(rejected)==obj['counts']['minimum_exceeds_single_name_cap']==143
    assert candidate_matches==22871
    pd.DataFrame(B.N.encoded(rejected)).to_csv(O/'data/pre-intent-budget-rejections.csv',index=False)
    pd.DataFrame(named_daily).to_csv(O/'data/named-daily-gates.csv',index=False)
    print('Pre-intent candidates verified',candidate_matches,len(rejected),flush=True)

    # Trace actual allocation, not an alternative allocation or sale decision.
    allocations=collections.defaultdict(list)
    for a in obj['audit']:
        if a['kind']=='lot_allocation':allocations[a['at'][:10]].append(a)
    funding_by_day=collections.defaultdict(list)
    for a in funded:funding_by_day[a['open_day']].append(a)
    traces=[];ownership=[];competitors=[];case_summaries=[]
    chosen=[('688498.SH','2024-02-20'),('688498.SH','2024-03-19'),('688498.SH','2025-10-21'),
            ('688256.SH','2024-02-19'),('688256.SH','2024-11-06')]
    for sid,start in [('688048.SH','2025-11-17'),('300502.SZ','2026-01-12')]:
        z=funds[funds.symbol.eq(sid)&funds.signal_at.ge(start)&funds.reason.eq('cash_competition_for_whole_order')]
        if len(z):chosen.append((sid,z.iloc[0].signal_at[:10]))
    for k,i in intents.items():
        sid,signal_at=k;rec=records[k];day=pd.Timestamp(rec.next_open);at=pd.Timestamp(signal_at).to_pydatetime()
        if rec.reason not in ('cash_competition_for_whole_order','next_open_minimum_exceeds_frozen_amount_or_share_contract'):continue
        raw=market.raw[sid];op=D(str(raw.loc[day].open));q=market.quantity(sid,pd.Timestamp(str(day.date())+'T09:30:00+08:00').to_pydatetime());schedule=market.fees(sid,pd.Timestamp(str(day.date())+'T09:30:00+08:00').to_pydatetime())
        cost=D(q.buy_minimum)*op*D('1.0005')+B.LR.fees(q.buy_minimum,op*D('1.0005'),schedule,'buy',i.get('par_value'))
        b=cashmap[signal_at];g=i['group'];before=max(ZERO,b['deployable']-(b['group0_allocated'] if g==1 else ZERO))
        selected=[x for x in allocations[rec.next_open] if x['sid']==sid]
        row=dict(symbol=sid,name=meta[sid]['name'],signal_at=signal_at,open_day=rec.next_open,kind=i['kind'],group=g,score=i['score'],
            reason=rec.reason,signal_price=market.quote(sid,at).raw_price,open_price=op,open_gap=op/market.quote(sid,at).raw_price-ONE,
            minimum_shares=q.buy_minimum,minimum_cash=cost,frozen_gross_budget=D(i['budget']),
            previous_nav=b['previous_nav'],open_available=b['open_available'],buffer=b['cash_buffer'],deployable=b['deployable'],
            group0_allocated=b['group0_allocated'],group1_allocated=b['group1_allocated'],mobile_allocated=b['mobile_allocated'],
            group_start_cash=before,total_cash_can_pay=cost<=b['open_available'],deployable_can_pay=cost<=b['deployable'],
            group_start_can_pay=cost<=before,skip_same_day_mobile_cash_arithmetic=cost<=max(ZERO,b['deployable']-b['group0_allocated']-b['group1_allocated'])+b['mobile_allocated'],
            theoretical_cash=D(selected[0]['ideal_cash']) if selected else None,
            minimum_ratio=D(selected[0]['minimum_share_ratio']) if selected else None)
        traces.append(row)
        if (sid,signal_at[:10]) not in chosen:continue
        d=dmap[signal_at];marks=market.marks(at,d['positions']);total=ZERO;age_trials=ZERO;heldlist=[]
        layer_info={z['id']:z for z in obj['layers']}
        for held_sid,qty in d['positions'].items():
            value=D(qty)*marks[held_sid].cny_price(at);total+=value
            pv_now=float(pv[held_sid].loc[pd.Timestamp(signal_at[:10])]) if pd.Timestamp(signal_at[:10]) in pv[held_sid].index else None
            roles=collections.defaultdict(lambda:ZERO)
            for z in d['layers']:
                if z['sid']==held_sid:roles[z['kind']]+=D(z['qty'])*marks[held_sid].cny_price(at)
            heldlist.append(dict(target=sid,signal_at=signal_at,symbol=held_sid,name=meta[held_sid]['name'],industry=meta[held_sid]['industry'],
                market_value=value,nav_weight=value/D(d['nav']),pvr=pv_now,trial_value=roles['trial'],core_value=roles['core'],mobile_value=roles['mobile']))
        assert total==D(d['inventory'])
        heldlist.sort(key=lambda z:-z['market_value']);ownership+=heldlist
        opening_funds=funding_by_day[rec.next_open]
        for x in opening_funds:competitors.append(dict(target=sid,target_signal=signal_at,**x))
        case_summaries.append(dict(**row,previous_positions=len(d['positions']),previous_stock_value=total,
             held_trial_value=sum(z['trial_value'] for z in heldlist),held_core_value=sum(z['core_value'] for z in heldlist),
             held_mobile_value=sum(z['mobile_value'] for z in heldlist),actual_funded_names=len(opening_funds)))
    for name,data in [('miss-traces',traces),('case-ownership',ownership),('case-competing-orders',competitors),('case-summaries',case_summaries)]:
        pd.DataFrame(B.N.encoded(data)).to_csv(O/f'data/{name}.csv',index=False)
    rejected_groups=collections.Counter(x['symbol'] for x in rejected)
    save('SUMMARY.json',dict(cash_bridge_rows=len(cash),original_intents_reconciled=candidate_matches,
       pre_intent_budget_rejections=len(rejected),pre_intent_by_symbol=dict(rejected_groups),cases=case_summaries,
       new_account_paths=0,new_indicator_formula_computations=0,static_only=True))
    protected=load(BASE/'completion-sha256.json')['sha256'];assert all(sha(BASE/k)==v for k,v in protected.items())
    save('VERIFICATION.json',dict(passed=True,old_study_files_unchanged=len(protected),cash_bridge_exact_rows=len(cash),
         reconstructed_original_intents=22871,reconstructed_pre_intent_rejections=143,old_results_or_params_changed=0,
         new_account_paths=0,new_indicator_formula_computations=0,source_manifest_sha256=sha(BASE/'completion-sha256.json')))
    print('COMPLETE',len(traces),len(case_summaries),dict(rejected_groups),flush=True)
if __name__=='__main__':main()
