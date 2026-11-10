from pathlib import Path
from decimal import Decimal as D
import json,hashlib,sys,collections
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'indexed_execution_v1'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import FeeSchedule,FeeComponent
ZERO=D(0);SLIP=D('.0005')
def read(p):return json.loads(Path(p).read_text())
def write(name,v):
    with (HERE/name).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def mean(xs):return sum(xs,ZERO)/D(len(xs)) if xs else None
def basic(rows,net,ret):
    pos=[D(r[net]) for r in rows if D(r[net])>0];neg=[D(r[net]) for r in rows if D(r[net])<0]
    return dict(n=len(rows),net_CNY=sum((D(r[net]) for r in rows),ZERO),positive_count=len(pos),
        win_fraction=D(len(pos))/D(len(rows)),profit_factor=None if not neg else sum(pos,ZERO)/abs(sum(neg,ZERO)),
        cash_payoff=None if not pos or not neg else mean(pos)/abs(mean(neg)),equal_weight_mean_net_return=mean([D(r[ret]) for r in rows]),
        tail_ge_30pct_count=sum(D(r[ret])>=D('.30') for r in rows))
def main():
    folder=BASE/'cohort_2024_924';archive=read(folder/'ARCHIVES.json');layers=read(folder/'LAYER_REPORT.json');rounds=read(folder/'ROUND_REPORT.json')
    concentration={}
    for scope,rows,net,ret in [
      ('CORE',[r for r in layers if r['layer']=='core' and r['layer_status']=='EXECUTION_AND_SETTLEMENT_CLOSED'],'NET80','return_on_layer_buy_cash'),
      ('FULL',[r for r in rounds if r['status']=='EXECUTION_AND_SETTLEMENT_CLOSED'],'whole_round_NET80','conditional_return_on_actual_buy_cash')]:
        biggest=max(rows,key=lambda r:(D(r[net]),r['round_id']));rest=[r for r in rows if r['round_id']!=biggest['round_id']]
        total=sum((D(r[net]) for r in rows),ZERO);positive=sum((D(r[net]) for r in rows if D(r[net])>0),ZERO)
        concentration[scope]=dict(maximum_winner=dict(round_id=biggest['round_id'],event_id=archive[biggest['round_id']]['event_id'],sid=biggest['sid'],
            NET80=biggest[net],net_return=biggest[ret],share_of_total_net=D(biggest[net])/total,share_of_sum_positive=D(biggest[net])/positive),
            all_observed=basic(rows,net,ret),fixed_observation_leave_maximum_out=basic(rest,net,ret),
            warning='Static influence diagnostic only. No signal exclusion, NAV/budgets/quantity recalculation or strategy rerun. It is not the portfolio that would have existed without that stock.')
    write('MAXIMUM_WINNER_INFLUENCE_2024.json',concentration)
    rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
    sourcehash=read(folder/'SOURCE_HASHES.json')
    for p in [B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']:
        assert sourcehash[str(p)]==hashlib.sha256(p.read_bytes()).hexdigest()
    attempts=read(HERE/'diagnostics/2024_924_ADD_ATTEMPTS.json');completed=[]
    for r in attempts:
        if r.get('source_q')!=0:continue
        sid=r['sid'];day=r['day'][:10];ident=market_identity_on(rules,sid,day,proxies)
        v=version_on(rules['fee_versions'][ident['venue']],day,proxies)['schedule']
        fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components']));par=D(str(rules['security_metadata'][sid]['par_value']))
        q=r['source_minimum_quantity'];px=D(r['buy_reference']);fl=D(r['effective_ADD_floor']);sp=fl*(1-SLIP)
        fee=lambda side,price:sum(fs.incremental(side,D(q)*price,{}, {},1,shares=q,par_value=par).values(),ZERO)
        risk=max(ZERO,D(q)*(px-sp)+fee('buy',px)+fee('sell',sp));cost=D(q)*px+fee('buy',px)
        assert risk>D(r['remaining_fee_risk']) and cost<=D(r['ADD_buy_budget']) and r['prior_quantity_capacity']>=q
        completed.append(dict(round_id=r['round_id'],sid=sid,day=day,original_size_q=0,remaining_fee_risk=r['remaining_fee_risk'],
            minimum_quantity=q,minimum_quantity_fee_risk=risk,minimum_buy_cash=cost,ADD_buy_budget=r['ADD_buy_budget'],
            reason='ZERO_REMAINING_RISK' if r['zero_remaining_risk'] else 'POSITIVE_REMAINING_RISK_BELOW_MINIMUM_QUANTITY_FEE_RISK'))
    assert len(completed)==14
    write('ADD_ZERO_SIZE_CLASSIFICATION_2024.json',dict(rows=completed,counts=dict(collections.Counter(r['reason'] for r in completed)),
        denominator_qualified_CP_attempts=56,zero_slot=0,shared_budget_rejected=0,shared_accepted_but_shrunk=0))
    print(json.dumps(concentration,default=str))
    print('Zero ADD q classifications',collections.Counter(r['reason'] for r in completed))
if __name__=='__main__':main()
