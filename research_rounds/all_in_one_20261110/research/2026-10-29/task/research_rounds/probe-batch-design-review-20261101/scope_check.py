"""Reservation-only mechanism scope. No allocator, account, or strategy replay.
The only quantity fold applies already recorded stock fills/splits to classify
whether a stock was held at the instant an ORIGINAL order was reserved.
"""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,hashlib,collections,time
import pandas as pd
import numpy as np

O=Path(__file__).resolve().parent; W=O.parent
sys.path.insert(0,str(W/'case-stage-ledger-20261031/v3'))
import joint_v3 as J
L=J.LR.L; Z=D(0)
RULEPATH=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
RULES=json.loads(RULEPATH.read_text())
SM={x['symbol']:x for x in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}; FACTORS={}
ROOTS={'2022':W/'2022-normal-reference-20261031/runs/B_diag/pair',
       '2025_07_2026_06':W/'q2-normal-continuation-20261031/runs/B_diag/pair'}
SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readbook(p):
    SOURCES[str(p.resolve())]=sha(p)
    with gzip.open(p,'rt') as f:return json.load(f)
def stream(p):
    SOURCES[str(p.resolve())]=sha(p)
    with gzip.open(p,'rt') as f:
        for s in f:yield json.loads(s)
def save(name,x):
    p=O/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)
def dated(rows,d):
    a=[x for x in rows if x['from']<=d and (not x.get('to') or d<x['to'])]
    if len(a)!=1:raise ValueError('dated quantity rule not uniquely available')
    return a[0]
def factor(sid,d):
    if sid not in FACTORS:
        r=SM[sid];p=Path(r['refs']['facts']);assert sha(p)==r['output_sha256'][str(p)]
        FACTORS[sid]=pd.read_parquet(p,columns=['factor']);SOURCES[str(p)]=sha(p)
    f=FACTORS[sid];date=pd.Timestamp(d)
    if date not in f.index:raise ValueError('no exact reservation-day fullwarm factor')
    return D(str(f.loc[date,'factor']))
def dist(a):
    if not a:return dict(n=0,min=None,p25=None,median=None,p75=None,p90=None,max=None)
    a=[float(x) for x in a]
    return dict(n=len(a),min=min(a),p25=float(np.quantile(a,.25)),median=float(np.median(a)),p75=float(np.quantile(a,.75)),p90=float(np.quantile(a,.9)),max=max(a))
def aggregate(rows):
    known=[x for x in rows if x['known']]
    return dict(reserved_orders=len(rows),distinct_stocks=len({x['sid'] for x in rows}),known_orders=len(known),unknown_orders=len(rows)-len(known),
        already_minimum_orders=sum(x['already_minimum'] for x in known),
        already_minimum_fraction_of_known=sum(x['already_minimum'] for x in known)/len(known) if known else None,
        shrinkable_orders=sum(not x['already_minimum'] for x in known),
        original_gross=sum((x['original_gross'] for x in known),Z),original_nominal_risk=sum((x['original_nominal_risk'] for x in known),Z),
        reduction_gross_upper_sum=sum((x['reduction_gross'] for x in known),Z),reduction_nominal_risk_upper_sum=sum((x['reduction_nominal_risk'] for x in known),Z),
        original_fee_reserve=sum((x['original_fee'] for x in known),Z),minimum_fee_reserve=sum((x['minimum_fee'] for x in known),Z),
        reduction_cash_upper_sum=sum((x['reduction_gross']+x['reduction_fee'] for x in known),Z),
        shrinkable_with_later_probe_risk_rejection=sum((not x['already_minimum']) and x['later_probe_risk_rejection_rows']>0 for x in known),
        reduction_risk_with_later_rejection_upper_sum=sum((x['reduction_nominal_risk'] for x in known if x['later_probe_risk_rejection_rows']>0),Z),
        sums_across_orders_are_not_simultaneous_account_space=True)

def opportunity_identity(p):
    SOURCES[str(p.resolve())]=sha(p);raw=hashlib.sha256();counts=collections.Counter();seen=collections.defaultdict(set);duplicate=0;first=last=None
    with gzip.open(p,'rb') as f:
        for line in f:
            raw.update(line);x=json.loads(line);d=x['day'];counts[d]+=1;key=(x['account'],x['sid'])
            duplicate+=key in seen[d];seen[d].add(key);first=first or {k:x[k] for k in ['account','day','sid']};last={k:x[k] for k in ['account','day','sid']}
    st=p.stat()
    assert duplicate==0 and len(counts)==242 and set(counts.values())=={1709}
    return dict(path=str(p.resolve()),device=st.st_dev,inode=st.st_ino,compressed_bytes=st.st_size,compressed_sha256=sha(p),uncompressed_sha256=raw.hexdigest(),rows=sum(counts.values()),trading_dates=len(counts),rows_per_date=1709,first_date=min(counts),last_date=max(counts),first_record=first,last_record=last,duplicates=duplicate)

def main():
    started=time.monotonic();summaries={};opp={};all_rows=[]
    for window,root in ROOTS.items():
        b=readbook(root/'B.json.gz');daily={x['at'][:10]:x for x in stream(root/'daily.jsonl.gz')};fund=list(stream(root/'funding.jsonl.gz'))
        opens=collections.defaultdict(list)
        for seq,x in enumerate(fund):
            if '09:30:00' in x['at']:opens[x['at'][:10]].append(dict(x,source_funding_sequence=seq))
        funded={(x['at'][:10],x['sid'],x['role']):x for x in fund if x.get('result')=='reserved' and x.get('pool')=='probe'}
        assert len(funded)==sum(x.get('result')=='reserved' and x.get('pool')=='probe' for x in fund)
        fundseq={(x['at'][:10],x['sid'],x['role']):seq for seq,x in enumerate(fund) if x.get('result')=='reserved' and x.get('pool')=='probe'}
        intents={(i['sid'],d['at'][:10],i['role']):dict(i,decision_NAV=d['nav']) for d in b['decisions'] for i in d['intents']}
        audits={x['order_id']:x for x in b['audit'] if x['kind']=='reserve'}
        flogs={x['order_id']:x for x in b['audit'] if x['kind']=='lot_risk_funded'}
        inventory=collections.Counter();ever_filled=set();ever_reserved=set();rows=[];byday=collections.defaultdict(list)
        for e in b['journal']:byday[e['at'][:10]].append(e)
        feechecks=targetchecks=quantitychecks=0
        for d in sorted(set(byday)|set(daily)):
            seen_buy_fill=False
            for e in byday[d]:
                kind=e['kind'];sid=e.get('sid')
                if kind=='actual_split':inventory[sid]=int(D(inventory[sid])*D(e['ratio']))
                elif kind=='real_sell_fill':inventory[sid]-=e['shares'];assert inventory[sid]>=0
                elif kind=='real_buy_fill':inventory[sid]+=e['shares'];ever_filled.add(sid);seen_buy_fill=True
                elif kind=='real_reserve':
                    assert not seen_buy_fill,'original batch reserved after a buy fill'
                    if e['pool']=='probe':
                        oid=e['order'];r=dict(window=window,day=d,at=e['at'],sid=sid,role=e['role'],native_order=oid,budget_order=e['budget_order'],original_reservation_quantity=e['shares'],held_quantity_before_any_batch_buy=inventory[sid],ever_previously_filled=sid in ever_filled,ever_previously_reserved=sid in ever_reserved,
                            participation_class='add_to_existing_stock' if inventory[sid]>0 else 'flat_reentry_after_prior_fill' if sid in ever_filled else 'flat_first_foothold_attempt',known=False)
                        try:
                            a=audits[oid];f=flogs[oid];signal=a['decision_at'][:10];i=intents[(sid,signal,e['role'])]
                            assert a['at']==e['at'] and a['sid']==sid and a['target_shares']==e['shares']==f['shares']
                            q=e['shares'];p=D(e['price']);gross=D(a['gross_budget_cny']);assert gross==D(q)*p==D(f['gross'])
                            rule=L.QuantityRule(**dated(RULES['quantity_versions'][sid],d)['rule']);m=rule.buy_minimum
                            assert rule.buy_floor(q)==q and q>=m;quantitychecks+=1
                            adjusted=D(f['floor']);assert adjusted==D(i['floor']);fl=adjusted/factor(sid,d)
                            assert p>fl>0
                            schedules=[z['schedule'] for vs in RULES['fee_versions'].values() for z in vs if z['schedule']['schedule_id']==a['fee_schedule']]
                            assert schedules and all(z==schedules[0] for z in schedules)
                            sd=schedules[0];schedule=L.FeeSchedule(sd['schedule_id'],tuple(L.FeeComponent(**z) for z in sd['components']));par=RULES['security_metadata'][sid].get('par_value')
                            fq=J.LR.fees(q,p,schedule,'buy',par);fm=J.LR.fees(m,p,schedule,'buy',par)
                            assert fq==D(a['fee_reserved_cny'])==D(f['fees']) and fm<=fq;feechecks+=1
                            assert m<=i['cap'] and m<=a['frozen_max_shares'] and D(m)*p<=D(i['budget']) and D(m)*p<=D(a['frozen_max_gross'])
                            if e['role']=='core':assert J.LR.protection_risk(m,p,fl,schedule,par)<=D(i['risk_budget'])
                            targetchecks+=1
                            fs=fundseq[(d,sid,e['role'])];rejs=[x for x in opens[d] if x['source_funding_sequence']>fs and 'probe_risk' in x.get('result','')]
                            r.update(known=True,signal_day=signal,decision_NAV=D(i['decision_NAV']),original_priority_rank=i['rank'],minimum_legal_initial_order=m,subsequent_increment=rule.buy_step,rule_id=rule.rule_id,raw_reservation_price=p,adjusted_protection=adjusted,raw_protection=fl,
                                original_gross=gross,original_nominal_risk=D(q)*max(Z,p-fl),original_fee=fq,minimum_fee=fm,
                                minimum_gross=D(m)*p,minimum_nominal_risk=D(m)*max(Z,p-fl),already_minimum=q==m,
                                reduction_gross=D(q-m)*p,reduction_nominal_risk=D(q-m)*max(Z,p-fl),reduction_fee=fq-fm,
                                source_funding_sequence=fs,later_probe_risk_rejection_rows=len(rejs),later_probe_risk_rejected_stocks=len({x['sid'] for x in rejs}),
                                later_probe_risk_rejection_meaning='actual later original funding result contains probe_risk; may coexist with other route/sector reasons; not an independently feasible candidate',
                                before_any_fill_cancel=True,fee_recomputed_once_for_one_aggregate_order=True)
                        except (KeyError,ValueError) as exc:r['unknown_reason']=str(exc)
                        rows.append(r)
                    ever_reserved.add(sid)
            if d in daily:
                expected={s:int(q) for s,q in daily[d]['positions'].items() if int(q)};actual={s:q for s,q in inventory.items() if q}
                assert actual==expected,(window,d,'recorded quantity classification fold differs from saved daily')
        assert len(rows)==len(funded)
        batches=[]
        for d in sorted(daily):
            rs=[x for x in rows if x['day']==d];a=aggregate(rs);allrejs=[x for x in opens[d] if 'probe_risk' in x.get('result','')]
            batches.append(dict(day=d,**a,any_actual_probe_risk_rejection=bool(allrejs),actual_probe_risk_rejection_rows=len(allrejs),
                any_later_probe_risk_rejection=any(x.get('later_probe_risk_rejection_rows',0)>0 for x in rs),
                any_shrinkable_with_later_probe_risk_rejection=any(x.get('reduction_nominal_risk',0)>0 and x.get('later_probe_risk_rejection_rows',0)>0 for x in rs),
                risk_reduction_upper_pct_decision_NAV=100*float(a['reduction_nominal_risk_upper_sum'])/float(rs[0]['decision_NAV']) if rs and rs[0]['known'] else None))
        byrole={role:aggregate([x for x in rows if x['role']==role]) for role in ['core','mobile']}
        classes=['flat_first_foothold_attempt','add_to_existing_stock','flat_reentry_after_prior_fill']
        byclass={cl:aggregate([x for x in rows if x['participation_class']==cl]) for cl in classes}
        cross={role+'|'+cl:aggregate([x for x in rows if x['role']==role and x['participation_class']==cl]) for role in ['core','mobile'] for cl in classes}
        active=[x for x in batches if x['reserved_orders']];shrink=[x for x in batches if x['reduction_nominal_risk_upper_sum']>0]
        summaries[window]=dict(**aggregate(rows),market_opening_dates=len(batches),probe_reservation_batches=len(active),positive_reduction_batches=len(shrink),
            positive_reduction_and_later_probe_rejection_batches=sum(x['any_shrinkable_with_later_probe_risk_rejection'] for x in batches),
            batches_with_probe_rejection_but_no_original_probe_orders=sum(x['any_actual_probe_risk_rejection'] and not x['reserved_orders'] for x in batches),
            zero_reduction_market_batches=sum(x['reduction_nominal_risk_upper_sum']==0 for x in batches),
            distribution_all_market_openings={k:dist([x[k] for x in batches]) for k in ['reserved_orders','reduction_gross_upper_sum','reduction_nominal_risk_upper_sum']},
            distribution_probe_order_batches={k:dist([x[k] for x in active]) for k in ['reserved_orders','already_minimum_fraction_of_known','reduction_gross_upper_sum','reduction_nominal_risk_upper_sum','risk_reduction_upper_pct_decision_NAV']},
            distribution_positive_reduction_batches={k:dist([x[k] for x in shrink]) for k in ['reduction_gross_upper_sum','reduction_nominal_risk_upper_sum','risk_reduction_upper_pct_decision_NAV']},
            by_role=byrole,by_participation=byclass,cross_role_participation=cross,
            original_quantity_audit_checks=quantitychecks,original_fee_checks=feechecks,original_minimum_target_checks=targetchecks,daily_quantity_only_checks=len(daily),
            no_cash_or_strategy_state_reconstruction=True)
        save(window+'_ACTUAL_PROBE_ORDERS.json',rows);save(window+'_OPENING_BATCHES.json',batches)
        all_rows+=rows;opp[window]=opportunity_identity(root/'opportunities.jsonl.gz')
    assert opp['2022']['compressed_sha256']!=opp['2025_07_2026_06']['compressed_sha256'] and opp['2022']['uncompressed_sha256']!=opp['2025_07_2026_06']['uncompressed_sha256']
    assert opp['2022']['last_date']<opp['2025_07_2026_06']['first_date']
    save('OPPORTUNITY_FILE_IDENTITY_CHECK.json',dict(passed=True,reason_equal_counts='both are 242 saved decision days × fixed 1709 input identities; different files, hashes and nonoverlapping dates',files=opp))
    save('SCOPE_SUMMARY.json',dict(passed=True,windows=summaries,units='sums of reservation-time differences across original orders, not simultaneous freed portfolio capacity',
        no_new_allocator=True,no_new_account_or_economic_path=True,quantity_fold_only_recorded_fills_splits_for_classification=True,all_original_order_quantities_from_reservations=True,
        unknown_orders=[x for x in all_rows if not x['known']],seconds=time.monotonic()-started))
    SOURCES[str(RULEPATH)]=sha(RULEPATH)
    save('SCOPE_SOURCE_HASHES.json',SOURCES)
    print('RESERVATION_SCOPE_COMPLETE',round(time.monotonic()-started,3),'seconds',[(k,v['reserved_orders'],v['already_minimum_orders'],v['positive_reduction_and_later_probe_rejection_batches']) for k,v in summaries.items()],flush=True)

if __name__=='__main__':main()
