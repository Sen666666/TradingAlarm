from pathlib import Path
from decimal import Decimal as D
import json,hashlib,collections,statistics
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'indexed_execution_v1'
ZERO=D(0)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):
    with (HERE/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def mean(xs):return sum(xs,ZERO)/D(len(xs)) if xs else None
def metric(rows,scope):
    islayer=scope!='FULL'
    status='layer_status' if islayer else 'status';netkey='NET80' if islayer else 'whole_round_NET80'
    retkey='return_on_layer_buy_cash' if islayer else 'conditional_return_on_actual_buy_cash'
    closed=[x for x in rows if x[status]=='EXECUTION_AND_SETTLEMENT_CLOSED' and x[netkey] is not None]
    pos=[x for x in closed if D(x[netkey])>0];neg=[x for x in closed if D(x[netkey])<0]
    pn=[D(x[netkey]) for x in pos];nn=[D(x[netkey]) for x in neg]
    pr=[D(x[retkey]) for x in pos];nr=[D(x[retkey]) for x in neg]
    tails=[dict(round_id=x['round_id'],sid=x['sid'],NET80=x[netkey],net_return_on_actual_buy_cash=x[retkey]) for x in closed if D(x[retkey])>=D('.30')]
    return dict(scope=scope,total_filled=len(rows),status_counts=dict(collections.Counter(x[status] for x in rows)),
        strict_closed_denominator=len(closed),positive_count=len(pos),negative_count=len(neg),zero_count=len(closed)-len(pos)-len(neg),
        win_fraction=None if not closed else D(len(pos))/D(len(closed)),net_CNY=sum((D(x[netkey]) for x in closed),ZERO),
        mean_NET80_CNY=mean([D(x[netkey]) for x in closed]),mean_winning_NET80_CNY=mean(pn),mean_losing_NET80_CNY=mean(nn),
        payoff_CNY_mean_win_over_abs_mean_loss=None if not pn or not nn else mean(pn)/abs(mean(nn)),
        profit_factor_sum_positive_over_abs_sum_negative=None if not nn else sum(pn,ZERO)/abs(sum(nn,ZERO)),
        mean_equal_weight_net_return=mean([D(x[retkey]) for x in closed]),mean_winning_net_return=mean(pr),mean_losing_net_return=mean(nr),
        payoff_return_mean_win_over_abs_mean_loss=None if not pr or not nr else mean(pr)/abs(mean(nr)),
        tail_at_least_30pct_count=len(tails),tail_at_least_30pct_fraction=None if not closed else D(len(tails))/D(len(closed)),tails=tails,
        unknown_mark_count=sum(x[netkey] is None for x in rows),
        settlement_open_count=sum(x[status]=='EXECUTION_CLOSED_SETTLEMENT_OPEN' for x in rows),
        open_position_count=sum(x[status]=='OPEN_CENSORED' for x in rows),
        denominator_rule='Only execution AND settlement closed, known NET80; no unknown/open/unsettled in hit-rate or payoff denominator')
def main():
    checks={};out={}
    for window in ('2022','2024_924'):
        folder=BASE/('cohort_'+window);seal=json.loads((folder/'OUTPUT_SEAL.json').read_text())
        for name,h in seal.items():assert sha(folder/name)==h
        checks[window]=dict(output_seal_sha256=sha(folder/'OUTPUT_SEAL.json'),files=len(seal))
        layers=json.loads((folder/'LAYER_REPORT.json').read_text());rounds=json.loads((folder/'ROUND_REPORT.json').read_text())
        out[window]=[metric([x for x in layers if x['layer']=='core'],'CORE'),metric([x for x in layers if x['layer']=='add'],'ADD'),metric(rounds,'FULL')]
    write('SOURCE_OUTPUT_SEALS.json',checks);write('MAIN_STATISTICS.json',out)
    write('DEFINITIONS.json',dict(scope='Post-processing existing frozen cohort outputs only; no account rerun or old-independent join',
        currency='CNY',cash_payoff='mean positive NET80 / abs(mean negative NET80)',profit_factor='sum positive NET80 / abs(sum negative NET80)',
        return_payoff='mean winning per-layer/round net return / abs(mean losing net return), not the cash payoff',
        net_return='NET80 divided by actual fees-included buy cash of that layer/round; not portfolio NAV return',
        tails='Final net return >=30% among strict closed units; threshold not gross-price rise',
        main_warning='2022 total NAV is uncertified after Jan13 and its closed subset is not full-cohort return. CORE is attribution, not a separate no-ADD wallet. No old independent labels joined.'))
    for w,rows in out.items():
        for x in rows:print(w,x['scope'],'n',x['strict_closed_denominator'],'wins',x['positive_count'],'net',x['net_CNY'],'avgWin',x['mean_winning_NET80_CNY'],'avgLoss',x['mean_losing_NET80_CNY'],'payoff',x['payoff_CNY_mean_win_over_abs_mean_loss'],'PF',x['profit_factor_sum_positive_over_abs_sum_negative'],'tails',x['tail_at_least_30pct_count'])
if __name__=='__main__':main()
