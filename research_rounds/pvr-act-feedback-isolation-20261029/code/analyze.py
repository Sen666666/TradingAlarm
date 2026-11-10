"""Compare the four completed fixed-calendar paths to existing self-feedback ledgers."""
from pathlib import Path
import json,gzip,time,signal,hashlib,datetime
from decimal import Decimal as D
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-feedback-isolation-20261029');OLD=O.parent/'pvr-local-finite-capital-20261029'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def export(n,rs):pd.DataFrame(rs).to_csv(O/(n+'.csv'),index=False)
start=time.monotonic();budget=read(O/'COMPUTE_BUDGET.json');assert budget['used_seconds']<300
def timeout(*_):raise TimeoutError('Cumulative300s accounting budget exhausted')
signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,300-budget['used_seconds']);status='failed';error=None
try:
    assert read(O/'REPLICATION_VERIFICATION.json')['passed']
    paths={('original','base'):O/'original-base',('original','cost2'):O/'original-cost2',('local','base'):O/'local',('local','cost2'):O/'local'}
    data={};summary=[];diffs=[];keyrows=[];costsets=[];component_rows=[]
    keydates=['2023-12-29','2024-01-02','2025-05-23','2025-05-26','2025-05-28','2025-06-10','2025-06-27','2025-10-31','2026-07-13','2026-07-14','2026-07-17','2026-07-20']
    for feedback in ['fixed','self']:
      for (policy,sc),p0 in paths.items():
        p=p0 if feedback=='fixed' else OLD/('baseline' if policy=='original' else 'local');aid='I__S0_'+sc
        if feedback=='fixed':assert read(p/'CALENDAR_VERIFICATION.json')['passed']
        obj=read(p/'accounts-v2'/f'{aid}.json');daily={r['at']:r for r in rows(p/'accounts-v2/daily.jsonl.gz') if r['account']==aid};decisions={r['at']:r for r in rows(p/'accounts-v2/decisions.jsonl.gz') if r['account']==aid};risk={r['at']:r for r in obj['audit_log'] if r['kind']=='risk_checkpoint'};orders={(r['decision_at'],r['sid']):r for r in obj['audit_log'] if r['kind']=='entry_contract'}
        data[(feedback,policy,sc)]=dict(obj=obj,daily=daily,decisions=decisions,risk=risk,orders=orders)
        s=pd.read_csv(p/'analysis/summary.csv',dtype=str).set_index('scenario').loc[sc];cs=pd.read_csv(p/'analysis/campaigns.csv',dtype=str);cs=cs[cs.scenario.eq(sc)].to_dict('records');last=list(daily.values())[-1];pnl=D(last['nav'])-D(1000000)
        tail=sum((D(c['net_pnl']) for c in cs if D(c['net_return'])>=D('.30')),D(0));ordinary=sum((D(c['net_pnl']) for c in cs if D(c['net_return'])<D('.30')),D(0));assert tail+ordinary==pnl
        fees=D(last['fees_cny']);slip=sum((abs(D(r['price'])-D(r['raw_open']))*r['receipt']['shares'] for r in obj['audit_log'] if r['kind']=='fill'),D(0));loss=-sum((D(c['net_pnl']) for c in cs if D(c['net_pnl'])<0),D(0))
        stat=dict(feedback=feedback,policy=policy,scenario=sc,final_nav=last['nav'],net_pnl=pnl,net_return=pnl/D(1000000),max_drawdown=s['max_drawdown'],tail_profit=tail,ordinary_profit=ordinary,all_negative_cycle_losses=loss,negative_cycles=sum(D(c['net_pnl'])<0 for c in cs),cycles=len(cs),open_cycles=sum(c['closed']!='True' for c in cs),fees=fees,slippage=slip,fees_plus_slippage=fees+slip,terminal_inventory=last['inventory'],terminal_dividend_receivable=last['dividend_receivable'],terminal_sale_receivable=last['sale_receivable'],terminal_reserved=last['order_reserved']);summary.append(stat);data[(feedback,policy,sc)]['stat']=stat
        for at,r in daily.items():
            if at[:10] in keydates:
                cp=risk[at];od=[dict(symbol=sid,budget=x['budget']) for (a,sid),x in orders.items() if a==at]
                keyrows.append(dict(feedback=feedback,policy=policy,scenario=sc,at=at,nav=r['nav'],inventory=r['inventory'],available=r['available'],reserved=r['order_reserved'],risk_on=cp['on'],risk_event=cp['event'],episode_drawdown=cp['episode_drawdown'],positions=json.dumps(r['positions']),pending_sells='|'.join(r['pending_sells']),accepted='|'.join(decisions[at]['accepted']),new_entry_budgets=json.dumps(od)))
    def compare(a,b,label,sc):
        orderrows=[]
        for key in sorted(set(a['orders'])|set(b['orders'])):
            x=a['orders'].get(key);y=b['orders'].get(key)
            if x is None or y is None or D(x['budget'])!=D(y['budget']):orderrows.append(dict(comparison=label,scenario=sc,at=key[0],symbol=key[1],a_present=x is not None,b_present=y is not None,a_budget=x['budget'] if x else 0,b_budget=y['budget'] if y else 0))
        diffs.extend(orderrows);fm=[]
        for v in [a,b]:fm.append({(r['at'],r['security_id'],r['side']):(r['shares'],r['gross_cny'],r['fees_cny']) for r in v['obj']['fills']})
        changedfills=[dict(at=k[0],symbol=k[1],side=k[2],a=fm[0].get(k),b=fm[1].get(k)) for k in sorted(set(fm[0])|set(fm[1])) if fm[0].get(k)!=fm[1].get(k)]
        return dict(first_order_differences=orderrows[:5],first_identity_order_difference=next((r for r in orderrows if r['a_present']!=r['b_present']),None),first_fill_differences=changedfills[:4],order_differences=len(orderrows),fill_differences=len(changedfills))
    comparisons={};effects={}
    for sc in ['base','cost2']:
        a=data[('fixed','original',sc)];b=data[('fixed','local',sc)];sa=data[('self','original',sc)];sb=data[('self','local',sc)];fd=b['stat']['net_pnl']-a['stat']['net_pnl'];sd=sb['stat']['net_pnl']-sa['stat']['net_pnl']
        comparisons[sc]=compare(a,b,'fixed_local_vs_original',sc)
        effects[sc]=dict(fixed_local_minus_original=fd,self_local_minus_original=sd,feedback_interaction_under_this_calendar=fd-sd,fixed_tail_delta=b['stat']['tail_profit']-a['stat']['tail_profit'],fixed_ordinary_delta=b['stat']['ordinary_profit']-a['stat']['ordinary_profit'],fixed_negative_loss_delta=b['stat']['all_negative_cycle_losses']-a['stat']['all_negative_cycle_losses'],fixed_fee_delta=b['stat']['fees']-a['stat']['fees'],fixed_slippage_delta=b['stat']['slippage']-a['stat']['slippage'],original_fixed_minus_self=a['stat']['net_pnl']-sa['stat']['net_pnl'],local_fixed_minus_self=b['stat']['net_pnl']-sb['stat']['net_pnl'])
        for policy in ['original','local']:comparisons[policy+'_'+sc+'_fixed_vs_self']=compare(data[('self',policy,sc)],data[('fixed',policy,sc)],'fixed_vs_self_'+policy,sc)
    for policy in ['original','local']:
        a=data[('fixed',policy,'base')];b=data[('fixed',policy,'cost2')]
        for at,x in a['decisions'].items():
            y=b['decisions'][at]
            if set(x['accepted'])!=set(y['accepted']):costsets.append(dict(policy=policy,at=at,base_accepted='|'.join(x['accepted']),cost2_accepted='|'.join(y['accepted']),base_available=a['daily'][at]['available'],cost2_available=b['daily'][at]['available'],base_positions=json.dumps(a['daily'][at]['positions']),cost2_positions=json.dumps(b['daily'][at]['positions'])))
    # Exact raw ledger stock/cycle accounting, not a unique causal allocation.
    for sc in ['base','cost2']:
        stock={}
        for policy in ['original','local']:
            p=paths[(policy,sc)];f=pd.read_csv(p/'analysis/campaigns.csv',dtype=str);f=f[f.scenario.eq(sc)];stock[policy]={}
            for c in f.to_dict('records'):stock[policy][c['symbol']]=stock[policy].get(c['symbol'],D(0))+D(c['net_pnl'])
        for sid in set(stock['original'])|set(stock['local']):component_rows.append(dict(scenario=sc,symbol=sid,original_pnl=stock['original'].get(sid,D(0)),local_pnl=stock['local'].get(sid,D(0)),delta=stock['local'].get(sid,D(0))-stock['original'].get(sid,D(0))))
        assert sum((r['delta'] for r in component_rows if r['scenario']==sc),D(0))==effects[sc]['fixed_local_minus_original']
    reversal=effects['base']['fixed_local_minus_original']*effects['cost2']['fixed_local_minus_original']<0
    interaction_cost_gap=(effects['cost2']['fixed_local_minus_original']-effects['base']['fixed_local_minus_original'])-(effects['cost2']['self_local_minus_original']-effects['base']['self_local_minus_original'])
    export('summary',summary);export('key-date-positions-budgets-actions',keyrows);export('order-differences',diffs);export('fixed-cost-candidate-differences',costsets);export('fixed-stock-contributions',component_rows)
    for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():assert sha(p)==expected,p
    result=dict(passed=True,post_hoc_not_deployable=True,effects=effects,sign_reversal_persists=reversal,cost_gap_interaction_under_this_fixed_calendar=interaction_cost_gap,first_forks=comparisons,first_same_calendar_cost_stock_set_differences=costsets[:6],causal_boundary='Difference-in-differences describes interaction under one baseline-generated fixed historical ACT calendar, not a unique general causal decomposition or executable strategy. No alternative calendar searched.',source_inputs_unchanged=True,full_paths=4,extra_paths=0,branch_stopped=True)
    save(O/'RESULTS.json',result)
    print(json.dumps(dict(effects=effects,sign_reversal_persists=reversal,first_same_calendar_cost_stock_set_differences=costsets[:2]),ensure_ascii=False,default=str),flush=True);status='complete'
except BaseException as exc:error=repr(exc);raise
finally:
    signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-start;budget['used_seconds']+=elapsed;budget['stages'].append(dict(stage='fixed_calendar_accounting',status=status,seconds=elapsed,error=error));save(O/'COMPUTE_BUDGET.json',budget)
