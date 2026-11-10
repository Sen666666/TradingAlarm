"""Post-result descriptive money/risk denominators, original saved books only.
No account/strategy import and no execution. No label enters any policy.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import importlib.util,json,gzip,hashlib
import pandas as pd

HERE=Path(__file__).resolve().parent;OUT=HERE/'no60_capital_deployment'
ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=ROOT/'pvr-slot1-native-readiness-20261101';NEW=HERE.parent/'pvr_pool_feasibility'
P=ROOT/'c1-drawdown-capacity-20261101/analyze_saved.py'
sp=importlib.util.spec_from_file_location('saved_capital_money_math',P);A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)
Z=D(0);EPS=D('.02');SRC={};FACTS={};CATS=['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def n(x):return D(str(x))
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def day(x):return str(x)[:10]
def facts(sid):
    if sid not in FACTS:
        p=Path(A.SM[sid]['refs']['facts']);assert sha(p)==A.SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p)
        FACTS[sid]=pd.read_parquet(p,columns=['raw_close','factor'])
    return FACTS[sid]
def entry_actions(a):
    # Same audited original actual stock-quantity definition, not signal labels.
    q=defaultdict(int);ever=set();events=[];result={}
    for ix,t in enumerate(a['book']['trades']):events.append((str(t['at']),1,ix,'trade',t))
    for ix,s in enumerate(a['book']['audit']):
        if s['kind']=='split':events.append((str(s['at']),0,ix,'split',s))
    for _,_,_,kind,t in sorted(events,key=lambda e:e[:3]):
        sid=t.get('security_id',t.get('sid'))
        if kind=='split':q[sid]=int(D(q[sid])*n(t['ratio']));continue
        if t['side']=='sell':q[sid]-=t['shares'];assert q[sid]>=0;continue
        cat=CATS[1] if q[sid] else CATS[2] if sid in ever else CATS[0]
        result[t['layer']]=dict(layer=t['layer'],sid=sid,at=t['at'],action=cat,quantity_before=q[sid],gross=n(t['gross_cny']),buy_fee=n(t['fees_cny']))
        q[sid]+=t['shares'];ever.add(sid)
    return result
def aggregate(a,actions,ids):
    ll=[x for x in a['layers'] if x['layer'] in ids];closed=[x for x in ll if not x['qty']];opened=[x for x in ll if x['qty']]
    negative=[x for x in closed if x['net']<0];positive=[x for x in closed if x['net']>=0]
    gross=sum((actions[x['layer']]['gross'] for x in ll),Z);buyfee=sum((actions[x['layer']]['buy_fee'] for x in ll),Z)
    sellfee=sum((n(p['fee_cny']) for t in a['book']['trades'] if t['side']=='sell' for p in t['parts'] if p['layer'] in ids),Z)
    cost=sum((x['cost'] for x in ll),Z);net=sum((x['net'] for x in ll),Z)
    assert abs(cost-gross-buyfee)<D('.00000001')
    def ratio(x,y):return x/y if y else None
    return dict(layers=len(ll),stocks=len({x['sid'] for x in ll}),actual_cumulative_buy_gross=gross,
        actual_buy_fee=buyfee,actual_sell_fee=sellfee,total_actual_fee=buyfee+sellfee,cumulative_buy_cash=cost,
        whole_life_net_contribution=net,net_per_cumulative_buy_cash=ratio(net,cost),
        equity_closed_layers=len(closed),equity_closed_buy_cash=sum((x['cost'] for x in closed),Z),
        equity_closed_net=sum((x['net'] for x in closed),Z),
        equity_closed_net_per_its_buy_cash=ratio(sum((x['net'] for x in closed),Z),sum((x['cost'] for x in closed),Z)),
        equity_closed_negative_net=sum((x['net'] for x in negative),Z),equity_closed_negative_buy_cash=sum((x['cost'] for x in negative),Z),
        loss_per_negative_closed_buy_cash=ratio(-sum((x['net'] for x in negative),Z),sum((x['cost'] for x in negative),Z)),
        equity_closed_positive_net=sum((x['net'] for x in positive),Z),
        open_layers=len(opened),open_original_buy_cash=sum((x['cost'] for x in opened),Z),
        open_layer_lifecycle_net=sum((x['net'] for x in opened),Z),open_terminal_market_value=sum((x['value'] for x in opened),Z),
        net_contains_costs_and_recognized_dividend_once=True,
        classification='equity qty==0 is layer-closed; unpaid dividend can remain; not cash-closed campaign')
def deployment(a,actions):
    bycat={c:defaultdict(lambda:Z) for c in CATS};unknown=[];daily=[]
    for r in a['daily']:
        d=day(r['at']);nav=n(r['nav']);parts={c:defaultdict(lambda:Z) for c in CATS};unknown_cap=Z;knownrisk=Z
        for x in r['layers']:
            cat=actions[x['id']]['action'];q=D(x['qty']);mark=A.price(x['sid'],d);value=q*mark
            parts[cat]['market_value']+=value;parts[cat]['gross_cost_basis']+=q*n(x['unit_cost'])
            f=facts(x['sid']);t=pd.Timestamp(d);floor_coord=x['last_core_line'] if x['role']=='core' else x['floor']
            if t not in f.index or floor_coord is None:
                unknown.append(dict(day=d,layer=x['id'],sid=x['sid'],action=cat,capital=value,reason='no exact source factor observation or original effective line; not imputed'))
                unknown_cap+=value;parts[cat]['unknown_risk_capital']+=value;continue
            z=f.loc[t];assert pd.notna(z.factor) and n(z.factor)>0
            floor=n(floor_coord)/n(z.factor);risk=q*max(Z,n(z.raw_close)-floor)
            parts[cat]['known_line_risk']+=risk;knownrisk+=risk
        actualrisk=n(r['pool_probe'][1])+n(r['pool_confirmed'][1]);residual=actualrisk-knownrisk
        assert residual>=-EPS,(d,'negative unallocated risk',residual)
        if not unknown_cap:assert abs(residual)<EPS,(d,'unexplained risk without source unknown',residual)
        assert abs(sum((v['market_value'] for v in parts.values()),Z)-n(r['inventory']))<EPS
        assert n(r['order_reserved'])==0,'new pending-order risk needs separate explicit attribution'
        for cat,v in parts.items():
            for k in ('market_value','gross_cost_basis','known_line_risk','unknown_risk_capital'):bycat[cat][k]+=v[k]
            bycat[cat]['exposure_fraction_sum']+=v['market_value']/nav
            bycat[cat]['known_line_risk_NAV_fraction_sum']+=v['known_line_risk']/nav
        daily.append(dict(day=d,NAV=nav,recorded_total_nominal_risk=actualrisk,known_line_risk=knownrisk,
            unallocated_risk_due_to_source_unknown=max(Z,residual),unknown_capital=unknown_cap,action_parts={k:dict(v) for k,v in parts.items()}))
    count=len(daily);totalrisk=sum((x['recorded_total_nominal_risk'] for x in daily),Z)
    summary={}
    for cat,v in bycat.items():
        summary[cat]=dict(mean_actual_market_value=v['market_value']/count,mean_held_gross_cost_basis=v['gross_cost_basis']/count,
            actual_market_value_yuan_close_sum=v['market_value'],held_gross_cost_basis_yuan_close_sum=v['gross_cost_basis'],
            mean_exposure_pct=v['exposure_fraction_sum']/count*100,known_nominal_risk_yuan_close_sum=v['known_line_risk'],
            mean_known_nominal_risk=v['known_line_risk']/count,mean_known_risk_NAV_pct=v['known_line_risk_NAV_fraction_sum']/count*100,
            known_share_of_recorded_nominal_risk=v['known_line_risk']/totalrisk,mean_source_unknown_capital=v['unknown_risk_capital']/count)
    return dict(close_observations=count,by_action=summary,daily=daily,source_unknown_lot_days=len(unknown),source_unknowns=unknown,
        recorded_nominal_risk_yuan_close_sum=totalrisk,mean_recorded_nominal_risk=totalrisk/count,
        unallocated_risk_yuan_close_sum=sum((x['unallocated_risk_due_to_source_unknown'] for x in daily),Z),
        unallocated_share_of_recorded_risk=sum((x['unallocated_risk_due_to_source_unknown'] for x in daily),Z)/totalrisk,
        no_pending_order_reserved_at_all_closes=True)

def main():
    OUT.mkdir(exist_ok=False);A.O=OUT;reports={}
    for win in ['2022','2025_26']:
        roots={'PVR_SLOT1':OLD/'runs'/win,'PVR_NO_CONFIRMED60':NEW/'runs'/win};data={};summaries={};acts={}
        for ref,root in roots.items():
            for name in ['B.json.gz','daily.jsonl.gz','balances.jsonl.gz']:SRC[str(root/'pair'/name)]=sha(root/'pair'/name)
            a=A.account(win,ref,root);data[ref]=a;actions=entry_actions(a);acts[ref]=actions
            assert set(actions)=={x['layer'] for x in a['layers']}
            dep=deployment(a,actions);groups={cat:aggregate(a,actions,{lid for lid,v in actions.items() if v['action']==cat}) for cat in CATS}
            overall=aggregate(a,actions,set(actions));assert abs(sum((v['whole_life_net_contribution'] for v in groups.values()),Z)-(n(a['book']['ending_NAV'])-D(1000000)))<D('.00000001')
            assert abs(sum((v['total_actual_fee'] for v in groups.values()),Z)-a['metrics']['fees'])<D('.00000001')
            save(OUT/(win+'_'+ref+'_DEPLOYMENT.json'),dep);save(OUT/(win+'_'+ref+'_ENTRY_ACTIONS.json'),list(actions.values()))
            summaries[ref]=dict(metrics=a['metrics'],overall=overall,by_action=groups,
                deployment_summary={k:v for k,v in dep.items() if k not in ['daily','source_unknowns']})
        old=data['PVR_SLOT1'];new=data['PVR_NO_CONFIRMED60'];os=set(old['stock']);ns=set(new['stock'])
        sets={'common_funded_stock':os&ns,'new_funded_stock':ns-os,'lost_original_stock':os-ns};bridge={};stockrows=[]
        for cohort,ids in sets.items():
            g={}
            for ref,a in data.items():g[ref]=aggregate(a,acts[ref],{x['layer'] for x in a['layers'] if x['sid'] in ids})
            bridge[cohort]=dict(stocks=len(ids),**g,net_difference=g['PVR_NO_CONFIRMED60']['whole_life_net_contribution']-g['PVR_SLOT1']['whole_life_net_contribution'])
            for sid in sorted(ids):stockrows.append(dict(sid=sid,name=A.META[sid]['name'],cohort=cohort,
                old=aggregate(old,acts['PVR_SLOT1'],{x['layer'] for x in old['layers'] if x['sid']==sid}),
                new=aggregate(new,acts['PVR_NO_CONFIRMED60'],{x['layer'] for x in new['layers'] if x['sid']==sid})))
        navdelta=n(new['book']['ending_NAV'])-n(old['book']['ending_NAV']);assert abs(sum((v['net_difference'] for v in bridge.values()),Z)-navdelta)<D('.00000001')
        fixedfile=OLD/'analysis'/win/'PVR_SLOT1/TOP10_WORST3_AND_FIXED_PATHS.json';fixed=read(fixedfile)
        fixedrows=[]
        for ix,z in enumerate(fixed):
            sid=z['sid'];fixedrows.append(dict(sid=sid,name=A.META[sid]['name'],original_preserved_index=ix,
                origin='original PVR prior saved first10=top10 whole-stock net, then original worst3 and fixed names; no new-result selection',
                old=aggregate(old,acts['PVR_SLOT1'],{x['layer'] for x in old['layers'] if x['sid']==sid}),
                new=aggregate(new,acts['PVR_NO_CONFIRMED60'],{x['layer'] for x in new['layers'] if x['sid']==sid})))
        save(OUT/(win+'_ALL_STOCK_COHORT_BRIDGE.json'),dict(delta_NAV=navdelta,cohorts=bridge,all_stocks=stockrows))
        save(OUT/(win+'_ORIGINAL_FIXED_WINNERS_AND_CONTROLS.json'),fixedrows)
        reports[win]=dict(accounts=summaries,delta_NAV=navdelta,cohort_bridge=bridge,
            action_net_differences={c:summaries['PVR_NO_CONFIRMED60']['by_action'][c]['whole_life_net_contribution']-summaries['PVR_SLOT1']['by_action'][c]['whole_life_net_contribution'] for c in CATS})
    for p in [Path(__file__),P]:SRC[str(p)]=sha(p)
    save(OUT/'SUMMARY.json',reports);save(OUT/'SOURCE_MANIFEST.json',dict(sources=SRC,financial_events=0,
        analysis='post-result descriptive decomposition, no future labels or group result enters policy',
        denominator='cumulative actual buy gross+buy fee is recycled transaction cash, not distinct initial capital; cost basis and risk sums are yuan-close observations',
        ratios='net/cumulative buy cash is descriptive full-life cost-normalized contribution including open layers, not annualized return, prediction, alpha, or a counterfactual leverage-normalized account'))
    print('PVR_NO60_CAPITAL_DEPLOYMENT_DONE',list(reports),flush=True)
if __name__=='__main__':main()
