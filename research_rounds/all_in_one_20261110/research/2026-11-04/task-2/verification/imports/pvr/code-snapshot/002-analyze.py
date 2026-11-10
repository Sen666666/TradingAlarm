"""Accounting decomposition only: no additional policies or market replay."""
from pathlib import Path
import json,gzip,time,signal,hashlib,collections
from decimal import Decimal as D
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-local-finite-capital-20261029');PV=O.parent/'pvr-incremental-order-20261029'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str))
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def frame(path):return pd.read_csv(path,dtype=str).fillna('')
def export(name,rs):pd.DataFrame(rs).to_csv(O/(name+'.csv'),index=False)
started=time.monotonic();budget=read(O/'COMPUTE_BUDGET.json');remaining=300-budget['used_seconds'];assert remaining>0
def timeout(*_):raise TimeoutError('Frozen cumulative300s calculation budget exhausted')
signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,remaining)
status='failed';error=None
try:
    assert read(O/'BASELINE_VERIFICATION.json')['passed'] and read(O/'LOCAL_VERIFICATION.json')['passed']
    trace=rows(O/'admission-trace.jsonl.gz');risk=pd.read_parquet(PV/'risk-set.parquet');events={(str(r.date.date()),r.symbol):r.e0_epoch for r in risk.itertuples()}
    data={};summary=[];orders_out=[];fills_out=[];daily_out=[];risk_out=[];stock_out=[];event_out=[];displace=[];flows=[];curves=[];details={}
    for policy in ['baseline','local']:
        p=O/policy;d=rows(p/'accounts-v2/daily.jsonl.gz');de=rows(p/'accounts-v2/decisions.jsonl.gz');s=frame(p/'analysis/summary.csv');c=frame(p/'analysis/campaigns.csv');con=frame(p/'analysis/contributions.csv')
        data[policy]=dict(daily={sc:{r['at']:r for r in d if r['account']=='I__S0_'+sc} for sc in ['base','cost2','delay1']},decisions={sc:{r['at']:r for r in de if r['account']=='I__S0_'+sc} for sc in ['base','cost2','delay1']},summary=s,campaigns=c,contributions=con)
    for sc in ['base','cost2','delay1']:
        aid='I__S0_'+sc;objects={v:read(O/v/'accounts-v2'/f'{aid}.json') for v in data};counts={};cycle_events={};pnl={};stock={}
        for v in data:
            obj=objects[v];ds=data[v]['daily'][sc];su=data[v]['summary'].set_index('scenario').loc[sc].to_dict();su.update(policy=v);summary.append(su)
            intents={r['order_id']:r for r in obj['audit_log'] if r['kind']=='entry_contract'}
            buy_decision={(r['receipt']['security_id'],r['receipt']['at']):intents[r['order_id']]['decision_at'] for r in obj['audit_log'] if r['kind']=='fill' and r['receipt']['side']=='buy'}
            cs=data[v]['campaigns'];cs=cs[cs.scenario.eq(sc)];ee={};ss=collections.defaultdict(lambda:D(0));event_missing=0
            for r in cs.to_dict('records'):
                day=buy_decision[(r['symbol'],r['first_buy_at'])][:10];key=events.get((day,r['symbol']))
                if key is None:event_missing+=1;key='unmapped|'+r['symbol']+'|'+r['first_buy_at']
                z=ee.setdefault(key,dict(event=key,symbol=r['symbol'],name=r['name'],industry=r['industry'],pnl=D(0),basis=D(0),fees=D(0),cycles=0,open_cycles=0,entries=[]))
                z['pnl']+=D(r['net_pnl']);z['basis']+=D(r['buy_gross'])+D(r['buy_fees']);z['fees']+=D(r['buy_fees'])+D(r['sell_fees']);z['cycles']+=1;z['open_cycles']+=int(r['closed']!='True');z['entries'].append(r['first_buy_at']);ss[r['symbol']]+=D(r['net_pnl'])
            assert event_missing==0,(v,sc,event_missing)
            final=list(ds.values())[-1];total=sum((z['pnl'] for z in ee.values()),D(0));assert total==D(final['nav'])-D(1000000),(v,sc,total,final['nav'])
            cycle_events[v]=ee;stock[v]=ss;pnl[v]=total
            neg=sum((-D(r['net_pnl']) for r in cs.to_dict('records') if D(r['net_pnl'])<0),D(0))
            counts[v]=dict(cycles=len(cs),negative_cycles=sum(D(x)<0 for x in cs.net_pnl),all_negative_pnl=neg,open_cycles=sum(cs.closed.ne('True')),repeated_event_extra_cycles=sum(max(0,z['cycles']-1) for z in ee.values()),event_missing=event_missing,final_equity_components={k:final[k] for k in ['available','order_reserved','sale_receivable','dividend_receivable','inventory','nav']},held_stock_sessions=sum(sum(int(n)>0 for n in r['positions'].values()) for r in ds.values()),market_value_sessions=sum((D(r['inventory']) for r in ds.values()),D(0)),available_cash_sessions=sum((D(r['available']) for r in ds.values()),D(0)),order_reserved_sessions=sum((D(r['order_reserved']) for r in ds.values()),D(0)))
            values=sorted([z['pnl'] for z in ee.values()],reverse=True)
            for n,x in enumerate(values):curves.append(dict(policy=v,scenario=sc,event_rank=n+1,event_count=len(values),pnl=x,cumulative=sum(values[:n+1],D(0))))
        delta=pnl['local']-pnl['baseline'];ee0=cycle_events['baseline'];ee1=cycle_events['local'];tail_delta=D(0);ordinary_delta=D(0);baseline_tail=D(0);local_baseline_tail=D(0);categories=collections.defaultdict(lambda:D(0))
        for key in sorted(set(ee0)|set(ee1)):
            b=ee0.get(key);l=ee1.get(key);bp=b['pnl'] if b else D(0);lp=l['pnl'] if l else D(0);bt=bool(b and b['basis']>0 and bp/b['basis']>=D('.30'));lt=bool(l and l['basis']>0 and lp/l['basis']>=D('.30'));cat='shared_funded_E0' if b and l else 'only_baseline_funded_E0' if b else 'only_local_funded_E0';categories[cat]+=lp-bp
            if bt or lt:tail_delta+=lp-bp
            else:ordinary_delta+=lp-bp
            if bt:baseline_tail+=bp;local_baseline_tail+=lp
            z=b or l;event_out.append(dict(scenario=sc,event=key,symbol=z['symbol'],name=z['name'],category=cat,baseline_pnl=bp,local_pnl=lp,delta=lp-bp,baseline_basis=b['basis'] if b else 0,local_basis=l['basis'] if l else 0,baseline_tail=bt,local_tail=lt,baseline_entries='|'.join(b['entries']) if b else '',local_entries='|'.join(l['entries']) if l else '',baseline_fees=b['fees'] if b else 0,local_fees=l['fees'] if l else 0))
        assert tail_delta+ordinary_delta==delta and sum(categories.values(),D(0))==delta
        for sid in sorted(set(stock['baseline'])|set(stock['local'])):
            b=stock['baseline'].get(sid,D(0));l=stock['local'].get(sid,D(0));stock_out.append(dict(scenario=sc,symbol=sid,baseline_pnl=b,local_pnl=l,delta=l-b))
        o={v:{(r['decision_at'],r['sid']):r for r in objects[v]['audit_log'] if r['kind']=='entry_contract'} for v in data};order_changed=[]
        for key in sorted(set(o['baseline'])|set(o['local'])):
            b=o['baseline'].get(key);l=o['local'].get(key);kind='only_local' if b is None else 'only_baseline' if l is None else 'common_budget_changed' if D(b['budget'])!=D(l['budget']) else 'identical'
            if kind!='identical':order_changed.append(dict(scenario=sc,at=key[0],symbol=key[1],kind=kind,baseline_budget=b['budget'] if b else 0,local_budget=l['budget'] if l else 0))
        orders_out.extend(order_changed)
        f={v:{(r['at'],r['security_id'],r['side']):r for r in objects[v]['fills']} for v in data};fc=[]
        for key in sorted(set(f['baseline'])|set(f['local'])):
            b=f['baseline'].get(key);l=f['local'].get(key);fields=['shares','gross_cny','fees_cny'];same=b is not None and l is not None and all(b[k]==l[k] for k in fields)
            if not same:fc.append(dict(scenario=sc,at=key[0],symbol=key[1],side=key[2],baseline_shares=b['shares'] if b else 0,local_shares=l['shares'] if l else 0,baseline_gross=b['gross_cny'] if b else 0,local_gross=l['gross_cny'] if l else 0))
        fills_out.extend(fc)
        checkpoints={v:{r['at']:r for r in objects[v]['audit_log'] if r['kind']=='risk_checkpoint'} for v in data};phase=collections.defaultdict(lambda:D(0));phase_days=collections.Counter();prev=D(0);dc=[]
        for at,b in data['baseline']['daily'][sc].items():
            l=data['local']['daily'][sc][at];rb=checkpoints['baseline'][at];rl=checkpoints['local'][at];state='both_active' if rb['on'] and rl['on'] else 'both_paused' if not rb['on'] and not rl['on'] else 'only_local_active' if rl['on'] else 'only_baseline_active';dd=D(l['nav'])-D(b['nav']);increment=dd-prev;prev=dd;phase[state]+=increment;phase_days[state]+=1
            bd=data['baseline']['decisions'][sc][at];ld=data['local']['decisions'][sc][at];changed=bd['accepted']!=ld['accepted'];dc.append(changed)
            daily_out.append(dict(scenario=sc,at=at,phase=state,baseline_nav=b['nav'],local_nav=l['nav'],delta_nav=dd,delta_increment=increment,baseline_accepted='|'.join(bd['accepted']),local_accepted='|'.join(ld['accepted']),accepted_list_changed=changed,accepted_set_changed=set(bd['accepted'])!=set(ld['accepted']),baseline_positions=json.dumps(b['positions']),local_positions=json.dumps(l['positions']),baseline_inventory=b['inventory'],local_inventory=l['inventory'],baseline_available=b['available'],local_available=l['available']))
            if rb['event'] or rl['event'] or rb['on']!=rl['on']:risk_out.append(dict(scenario=sc,at=at,baseline_event=rb['event'],local_event=rl['event'],baseline_on=rb['on'],local_on=rl['on'],baseline_nav=rb['nav'],local_nav=rl['nav'],baseline_episode=rb['episode'],local_episode=rl['episode'],baseline_drawdown=rb['episode_drawdown'],local_drawdown=rl['episode_drawdown']))
        assert sum(phase.values(),D(0))==delta
        tt=[r for r in trace if r['account']==aid];rec=[(c,r) for c in tt for r in c['recommendations'] if r['changed']]
        for c,r in rec:
            gains=sorted(set(r['local'])-set(r['original']));lost=sorted(set(r['original'])-set(r['local']));accepted=set(c['accepted']);contracts=c['entry_contracts'];fill_by_order=collections.defaultdict(list)
            for row in objects['local']['audit_log']:
                if row['kind']=='fill' and row['receipt']['side']=='buy':fill_by_order[row['order_id']].append(row['receipt'])
            for new in gains:
                ic=next((x for x in contracts if x['sid']==new),None);ff=fill_by_order.get(ic['order_id'],[]) if ic else [];event=events.get((c['at'][:10],new));z=ee1.get(event)
                displace.append(dict(scenario=sc,at=c['at'],local_new=new,original_shadow_selected='|'.join(lost),actually_accepted=new in accepted,actual_budget=ic['budget'] if ic else 0,buy_fill_count=len(ff),gross_used=sum((D(x['gross_cny'])+D(x['fees_cny']) for x in ff),D(0)),event=event,event_final_pnl=z['pnl'] if z else 0,available_before=c['available_before'],note='same-state recommendation contrast; displaced shadow not necessarily affordable. Repeated commit recommendations are not independent trades; event PnL must not be summed over repeated rows'))
        flow=dict(scenario=sc,cutoffs=len(tt),cutoffs_changed_priority=sum(bool(c['priority_changes']) for c in tt),same_state_selected_list_change_calls=len(rec),same_state_selected_set_change_calls=sum(set(r['local'])!=set(r['original']) for _,r in rec),same_state_selected_set_change_dates=len({c['at'] for c,r in rec if set(r['local'])!=set(r['original'])}),actual_accepted_list_change_dates=sum(dc),actual_order_identity_changes=sum(r['kind'] in ['only_local','only_baseline'] for r in order_changed),actual_order_budget_change=len(order_changed),actual_fill_rows_changed=len(fc),first_order_changes=order_changed[:5],first_fill_changes=fc[:5]);flows.append(flow)
        details[sc]=dict(delta_NAV=delta,paired_funded_E0_tail_delta=tail_delta,paired_funded_E0_ordinary_delta=ordinary_delta,baseline_fixed_tail_profit=baseline_tail,local_profit_on_baseline_tail=local_baseline_tail,baseline_tail_retention=local_baseline_tail/baseline_tail if baseline_tail else None,funded_E0_category_delta=dict(categories),phase_NAV_increment=dict(phase),phase_days=dict(phase_days),policy_counts=counts,identification=flow)
    for name,rs in [('summary',summary),('order-differences',orders_out),('fill-differences',fills_out),('daily-transmission',daily_out),('ACT-transmission',risk_out),('stock-differences',stock_out),('event-contributions',event_out),('capital-displacement',displace),('identification-funnel',flows),('continuous-contributions',curves)]:export(name,rs)
    for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():assert sha(p)==expected,p
    for p,expected in read(O/'IMPLEMENTATION_FREEZE.json')['sha256'].items():assert sha(p)==expected,p
    save(O/'MECHANISM_RESULTS.json',dict(passed=True,details=details,all_stock_event_phase_deltas_reconciled=True,source_inputs_unchanged=True,local_implementation_unchanged=True,causal_boundary='Actual ledger arithmetic only; endogenous cash/sizing/ACT transmission is not all direct PVR predictive value. Absent funded events have contribution0; unmatched opportunity diagnostic results were not zero-imputed. Phase categories use each current close risk state and are descriptive, not counterfactual attribution.'))
    print(json.dumps(details,ensure_ascii=False,default=str),flush=True);status='complete'
except BaseException as exc:error=repr(exc);raise
finally:
    signal.setitimer(signal.ITIMER_REAL,0);spent=time.monotonic()-started;budget['used_seconds']+=spent;budget['stages'].append(dict(stage='mechanism_accounting',status=status,seconds=spent,error=error));save(O/'COMPUTE_BUDGET.json',budget)
