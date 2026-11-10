"""Read saved tags/money only. No prices, indicators, account, or new wealth basis."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal as D, localcontext
import json, hashlib

O=Path(__file__).resolve().parent; T=O.parent
SOURCE=T/'risk_constraints/ma63_exposure_axis_v1/DAILY_ALIGNED.json'
GROUP=T/'risk_constraints/ma63_exposure_axis_v1/GROUPS_BY_AXIS_AND_SLOPE.json'
PROTOCOL=T/'risk_constraints/ma63_exposure_axis_v1/PROTOCOL.txt'
AUDIT=T/'independent_review/ma63_axis_review_v1/LAG_WEALTH_AND_RESOURCE_AUDIT.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')

def main():
    assert not(O/'AXIS_RECONSTRUCTION.json').exists(),'do not repeat completed review'
    sources={str(p):sha(p)for p in [Path(__file__),SOURCE,GROUP,PROTOCOL,AUDIT]}
    save('SOURCE_FREEZE.json',dict(scope='existing labels/money only; no Account/price/indicator',source_sha256=sources))
    rows=[x for x in read(SOURCE)if x['arm']=='NO60']
    assert len(rows)==484 and len({x['day']for x in rows})==484
    assert [x['day']for x in rows]==sorted(x['day']for x in rows)
    spells=[]; current=None
    with localcontext()as context:
        context.prec=60
        for i,r in enumerate(rows):
            prior=r['prior_benchmark_CLOSE']; close=datetime.fromisoformat(prior['day']+'T15:10:00+08:00'); op=datetime.fromisoformat(r['day']+'T09:30:00+08:00')
            assert close<op and prior['day']==r['benchmark_CLOSE']['previous_observed_CLOSE']
            if i: assert prior['day']==rows[i-1]['day']
            selected=prior['axis_slope']=='below_down'
            if not selected:
                current=None
                continue
            # Boundaries are selected on the full original calendar. A false
            # intervening observation always closes the spell, including when
            # the next true tag shares a broad below episode.
            if current is None:
                current=dict(id=f'S{len(spells)+1:02}',first_calendar_index=i,last_calendar_index=i,
                    first_execution_day=r['day'],last_execution_day=r['day'],
                    first_signal_CLOSE=prior['day'],last_signal_CLOSE=prior['day'],days=[],
                    account_start_NAV=r['lag_NAV'],start_inventory=r['lag_inventory'],end_NAV=r['NAV'],
                    wealth=D(0),buy_cash=D(0),fees=D(0),pre_open_held_days=0)
                spells.append(current)
            assert i==current['last_calendar_index'] or i==current['last_calendar_index']+1
            current['last_calendar_index']=i;current['last_execution_day']=r['day'];current['last_signal_CLOSE']=prior['day']
            current['days'].append(r['day']);current['end_NAV']=r['NAV']
            current['wealth']+=D(r['wealth_change']);current['buy_cash']+=D(r['actual_buy_cash']);current['fees']+=D(r['actual_fees'])
            current['pre_open_held_days']+=D(r['lag_inventory'])>0
        for s in spells:
            s['days_count']=len(s['days']);assert s['last_calendar_index']-s['first_calendar_index']+1==s['days_count']
            s['NAV_difference']=D(s['end_NAV'])-D(s['account_start_NAV']);s['source_decimal_residual']=s['wealth']-s['NAV_difference']
            assert abs(s['source_decimal_residual'])<D('1e-20')
        selected=[r for r in rows if r['prior_benchmark_CLOSE']['axis_slope']=='below_down']
        assert len(selected)==298 and sum(s['days_count']for s in spells)==298
        wealth=sum((s['wealth']for s in spells),D(0));cash=sum((s['buy_cash']for s in spells),D(0));fees=sum((s['fees']for s in spells),D(0))
        ref=next(x for x in read(GROUP)if x['arm']=='NO60'and x['clock']=='priorCLOSE_to_current_day'and x['label']=='below_down')
        assert cash==D(ref['actual_buy_cash'])and fees==D(ref['actual_fees'])and abs(wealth-D(ref['actual_wealth']))<D('1e-20')
        save('AXIS_RECONSTRUCTION.json',dict(status='PASS_EXISTING_AXIS_CLOCK_AND_MONEY',full_calendar_rows=len(rows),selected_execution_days=298,
            spells=len(spells),positive_spells=sum(s['wealth']>0 for s in spells),negative_spells=sum(s['wealth']<0 for s in spells),zero_spells=sum(s['wealth']==0 for s in spells),
            zero_preopen_inventory_spells=sum(s['pre_open_held_days']==0 for s in spells),
            source_wealth_sum=wealth,source_buy_cash_sum=cash,source_fees_sum=fees,
            prior_source_wealth_aggregation_residual=wealth-D(ref['actual_wealth']),all_spells=spells,
            not_signal_cohort_lifetime_net=True,no_new_Account_or_price_or_financial_basis=True))
    for p,h in sources.items():assert sha(p)==h
    print(json.dumps({k:v for k,v in read(O/'AXIS_RECONSTRUCTION.json').items()if k!='all_spells'}))
if __name__=='__main__':main()
