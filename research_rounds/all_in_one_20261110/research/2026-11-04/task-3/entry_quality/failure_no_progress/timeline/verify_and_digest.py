"""Cross-check saved timeline against previously audited independent files."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json, hashlib

O=Path(__file__).parent
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
SRC={}


def read(p):
    SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())


def close(a,b,key):assert abs(D(str(a))-D(str(b)))<D('1e-17'),(key,a,b)


rows=read(O/'2022_2024_DECISION_TIMELINE.json')
bylayer={x['layer']:x for x in rows}
add=read(O.parent.parent/'coverage_audit/add_preprofit_current_no60_v2/ADD_PREPROFIT_ROWS.json')
for x in add:
    y=bylayer[x['layer']]
    assert x['decision_at']==y['decision_at'] and x['pre_close_q']==y['pre_close_stock_quantity']
    for a,b in [('remaining_buy_fee_inclusive_basis','remaining_basis'),('pre_close_unrealized','unrealized')]:
        close(x[a],y['pre_close_held'][b],('old add audit',x['layer'],a))
    close(x['pre_close_campaign_realized'],y['pre_close_current_stock_campaign']['strict_realized'],('old add campaign realized',x['layer']))
    close(x['pre_close_campaign_accrued_dividend_AR'],y['pre_close_current_stock_campaign']['recognized_dividend_AR'],('old add campaign AR',x['layer']))

old=read(B/'loss_correction/continuation2024_layers/PVR_NO60-CAMPAIGNS.json')
new=read(O/'2022_2024_COMPLETED_STOCK_CYCLES.json')
newkey={tuple(sorted(c['layer_ids'])):c for hh in new.values() for c in hh}
assert len(old)==len(newkey)==1677
for x in old:
    y=newkey[tuple(sorted(x['layer_ids']))]
    assert x['position_closed'] and x['closed']==y['closed_at']
    close(x['net'],D(y['net_trade_cash'])+D(y['recognized_dividend_AR']),('old complete cycle',x['sid'],x['campaign_number']))
    close(x['buy_cash'],y['actual_buycash'],('old completed buycash',x['sid'],x['campaign_number']))

periods=read(B/'risk_constraints/absolute_loss_2022_2023/PERIODS.json')
months=read(O/'FIXED_WORST_MONTHS.json')
oldmonth={x['period']:x for x in periods if x['reference']=='NO60_2022_2023' and x['grain']=='month'}
for x in months:
    close(x['actual_period_wealth'],oldmonth[x['month']]['wealth_change'],('old exact month',x['month']))
    close(sum((D(v['wealth']) for v in x['actual_period_by_action'].values()),D(0)),x['actual_period_wealth'],('month actions',x['month']))

summary=read(O/'SUMMARY.json')
digest={}
for ref in ['2022_2024_2022_2023','2022_2024_post303','strong_all']:
    digest[ref]={}
    for dimension,statekey in [('action_recent_account_state','recent21_account_state'),('action_recent_industry_state','recent21_industry_state')]:
        out={}
        for row in summary[ref][dimension]:
            label=row['labels'][statekey]
            if label not in out:out[label]=dict(fills=0,stocks_nonadditive_by_action=True,actual_buycash=D(0),net=D(0),positive_net=D(0),negative_net=D(0),strict_realized=D(0),open_unrealized=D(0),recognized_dividend_AR=D(0))
            x=out[label];x['fills']+=row['fills']
            for k in ['actual_buycash','net','positive_net','negative_net','strict_realized','open_unrealized','recognized_dividend_AR']:x[k]+=D(row[k])
        digest[ref][dimension]=out
    for dimension in ['action_recent_account_state','action_recent_industry_state','action_prior_stock_failure','action_prior_mobile_failure']:
        for k in ['actual_buycash','net','positive_net','negative_net','strict_realized','open_unrealized','recognized_dividend_AR']:
            close(sum((D(x[k]) for x in summary[ref][dimension]),D(0)),summary[ref]['all'][k],(ref,dimension,k))
monthly=[]
for x in months:
    first,last=x['daily_trace'][0],x['daily_trace'][-1]
    monthly.append(dict(month=x['month'],actual_period_wealth=x['actual_period_wealth'],actual_period_by_action=x['actual_period_by_action'],
                        first_close=first['at'],first_recent21=first['recent21_all'],last_close=last['at'],last_recent21=last['recent21_all']))
with (O/'DIGEST.json').open('x') as f:json.dump(dict(scopes=digest,months=monthly),f,ensure_ascii=False,indent=2,default=str)
with (O/'CROSS_FILE_AUDIT.json').open('x') as f:json.dump(dict(passed=True,old_add_snapshots_checked=len(add),completed_stock_cycles_exact=1677,
                                                          fixed_month_period_bridges=len(months),groups_partition_exact=True,
                                                          zero_new_financial_events=True,sources=SRC),f,ensure_ascii=False,indent=2)
print(json.dumps(dict(passed=True,old_add_snapshots=len(add),completed_cycles=1677,months=len(months),digest=digest),ensure_ascii=False,indent=2,default=str))
