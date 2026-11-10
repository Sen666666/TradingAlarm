"""Read-only aggregation of audited2022-23 paths; no strategy/account replay."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict
import csv,gzip,hashlib,json
getcontext().prec=50
O=Path(__file__).resolve().parent;ROOT=O.parent
PH=ROOT/'pvr_pool_feasibility/market_phase_2022_2023'
CYCLE=ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024'
BENCH=ROOT/'benchmark_2022_2023'
NAMES=('No60','PVR','MA63_90','BH');START='2022-01-04';END='2023-12-29';ZERO=D(0);INITIAL=D(1000000)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(name,value):Path(O/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
def writecsv(name,rows):
    with (O/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    assert not(O/'TELESCOPE_PROOF.json').exists(),'completed axis not silently rebuilt'
    paths={};books={};flows={};sources=[]
    phase=read(PH/'ALL_PERIODS.json');bphase=read(PH/'BENCHMARK_ALL_PERIODS.json')
    primary=list(csv.DictReader((BENCH/'PERIODS.csv').open()))
    sources += [PH/'ALL_PERIODS.json',PH/'BENCHMARK_ALL_PERIODS.json',BENCH/'PERIODS.csv']
    for name,where in [('No60','no60'),('PVR','original')]:
        daily=CYCLE/where/'run-2024/pair/daily.jsonl.gz';book=CYCLE/where/'run-2024/pair/B.json.gz';sources += [daily,book]
        with gzip.open(daily,'rt')as f:rows=[json.loads(x) for x in f]
        paths[name]=[dict(date=x['at'][:10],NAV=D(x['nav']),market_value=D(x['inventory']),cumfee=D(x['fees_cny'])) for x in rows if START<=x['at'][:10]<=END]
        with gzip.open(book,'rt')as f:trades=json.load(f)['trades']
        flows[name]=[dict(date=x['at'][:10],side=x['side'],gross=D(x['gross_cny']),fee=D(x['fees_cny'])) for x in trades if START<=x['at'][:10]<=END]
    for name,source in [('MA63_90','MA63_90'),('BH','BUY_HOLD')]:
        daily=BENCH/'daily'/f'{source}.csv';fills=BENCH/'logs'/f'{source}_fills.json';sources += [daily,fills]
        rows=list(csv.DictReader(daily.open()))
        paths[name]=[dict(date=x['date'],NAV=D(x['NAV']),market_value=D(x['market_value']),dayfee=D(x['fee'])) for x in rows]
        flows[name]=[dict(date=x['day'],side=x['side'],gross=D(x['gross']),fee=D(x['fee'])) for x in read(fills)]
    dates=[x['date'] for x in paths['No60']];assert len(dates)==484 and dates[0]==START and dates[-1]==END and len(set(dates))==484
    assert all([x['date'] for x in paths[n]]==dates for n in NAMES)
    dailyby={};monthly=[];checkcounts=0;max_legacy_cash_aggregation_delta=ZERO
    for name in NAMES:
        flow=defaultdict(lambda:dict(buy_gross=ZERO,sell_gross=ZERO,buy_fee=ZERO,sell_fee=ZERO,buy_fills=0,sell_fills=0))
        for f in flows[name]:
            z=flow[f['date']];z[f['side']+'_gross']+=f['gross'];z[f['side']+'_fee']+=f['fee'];z[f['side']+'_fills']+=1
        prevnav=INITIAL;prevexp=ZERO;prevcumfee=ZERO;items=[]
        for x in paths[name]:
            f=flow[x['date']];fee=f['buy_fee']+f['sell_fee']
            expectedfee=x.get('dayfee',x.get('cumfee',ZERO)-prevcumfee)
            assert fee==expectedfee,(name,x['date'],'daily fill fee mismatch')
            item=dict(date=x['date'],policy=name,NAV_begin_CNY=prevnav,NAV_end_CNY=x['NAV'],net_PnL_CNY=x['NAV']-prevnav,
                previous_close_exposure_pct=prevexp,close_exposure_pct=x['market_value']/x['NAV']*100,
                buy_gross_CNY=f['buy_gross'],sell_gross_CNY=f['sell_gross'],fees_CNY=fee,
                buy_cash_incl_fees_CNY=f['buy_gross']+f['buy_fee'],sell_net_after_fees_CNY=f['sell_gross']-f['sell_fee'],buy_fills=f['buy_fills'],sell_fills=f['sell_fills'])
            items.append(item);prevnav=x['NAV'];prevexp=item['close_exposure_pct'];prevcumfee=x.get('cumfee',ZERO)
        dailyby[name]={x['date']:x for x in items}
        for month in sorted({d[:7] for d in dates}):
            ds=[x for x in items if x['date'].startswith(month)];begin=ds[0]['NAV_begin_CNY'];ending=ds[-1]['NAV_end_CNY']
            z=dict(month=month,policy=name,start_date=ds[0]['date'],end_date=ds[-1]['date'],days=len(ds),carried_NAV_CNY=begin,ending_NAV_CNY=ending,
                net_PnL_CNY=ending-begin,return_pct=(ending/begin-1)*100,cumulative_profit_CNY=ending-INITIAL,
                mean_previous_close_exposure_pct=sum((x['previous_close_exposure_pct'] for x in ds),ZERO)/len(ds),
                buy_gross_CNY=sum((x['buy_gross_CNY']for x in ds),ZERO),sell_gross_CNY=sum((x['sell_gross_CNY']for x in ds),ZERO),
                fees_CNY=sum((x['fees_CNY']for x in ds),ZERO),buy_cash_incl_fees_CNY=sum((x['buy_cash_incl_fees_CNY']for x in ds),ZERO),
                sell_net_after_fees_CNY=sum((x['sell_net_after_fees_CNY']for x in ds),ZERO),buy_fills=sum(x['buy_fills']for x in ds),sell_fills=sum(x['sell_fills']for x in ds))
            assert z['net_PnL_CNY']==sum((x['net_PnL_CNY']for x in ds),ZERO)
            refpolicy={'No60':'NO60','PVR':'PVR','MA63_90':'benchmark_MA63_90','BH':'benchmark_BUY_HOLD'}[name]
            refs=phase if name in ('No60','PVR') else bphase
            ref=next(x for x in refs if x['grain']=='month' and x['policy']==refpolicy and x['period']==month)
            for key,other in [('carried_NAV_CNY','begin_NAV'),('ending_NAV_CNY','end_NAV'),('net_PnL_CNY','net_PnL')]:assert z[key]==D(ref[other])
            assert abs(z['return_pct']-D(ref['return_pct']))<D('1e-20')
            assert abs(z['mean_previous_close_exposure_pct']-D(ref['mean_lag_exposure_pct']))<D('1e-20')
            assert z['fees_CNY']==D(ref.get('actual_fees',ref.get('fees')))
            if name in ('No60','PVR'):
                delta=max(abs(z['buy_cash_incl_fees_CNY']-D(ref['actual_buy_cash'])),abs(z['sell_net_after_fees_CNY']-D(ref['actual_sell_net'])))
                max_legacy_cash_aggregation_delta=max(max_legacy_cash_aggregation_delta,delta)
                assert delta<D('1e-18'),'legacy phase cash aggregation materially differs'
            else:
                prim=next(x for x in primary if x['benchmark']==('BUY_HOLD' if name=='BH' else name) and x['frequency']=='M' and x['period']==month)
                assert abs(z['return_pct']-D(prim['return_pct']))<D('1e-10')
            checkcounts+=1;monthly.append(z)
    lookup={(x['month'],x['policy']):x for x in monthly};months=sorted({x['month']for x in monthly});assert len(months)==24
    wide=[];gaps=[]
    for month in months:
        row=dict(month=month,start_date=lookup[month,'No60']['start_date'],end_date=lookup[month,'No60']['end_date'])
        for name in NAMES:
            x=lookup[month,name];ma=lookup[month,'MA63_90']
            x['monthly_PnL_difference_vs_MA63_CNY']=x['net_PnL_CNY']-ma['net_PnL_CNY']
            x['wealth_difference_vs_MA63_CNY']=x['ending_NAV_CNY']-ma['ending_NAV_CNY']
            for k in ('carried_NAV_CNY','ending_NAV_CNY','net_PnL_CNY','return_pct','mean_previous_close_exposure_pct','buy_gross_CNY','sell_gross_CNY','fees_CNY','buy_cash_incl_fees_CNY','sell_net_after_fees_CNY','monthly_PnL_difference_vs_MA63_CNY','wealth_difference_vs_MA63_CNY'):row[name+'_'+k]=x[k]
        wide.append(row);n=lookup[month,'No60'];gaps.append(dict(month=month,No60_net_PnL_CNY=n['net_PnL_CNY'],MA63_net_PnL_CNY=lookup[month,'MA63_90']['net_PnL_CNY'],monthly_gap_CNY=n['monthly_PnL_difference_vs_MA63_CNY'],cumulative_gap_CNY=n['wealth_difference_vs_MA63_CNY']))
    axis=[]
    for date in dates:
        row=dict(date=date)
        for name in NAMES:
            x=dailyby[name][date]
            for k in ('NAV_begin_CNY','NAV_end_CNY','net_PnL_CNY','previous_close_exposure_pct','buy_gross_CNY','sell_gross_CNY','fees_CNY'):row[name+'_'+k]=x[k]
        row['No60_minus_MA63_day_gap_CNY']=row['No60_net_PnL_CNY']-row['MA63_90_net_PnL_CNY'];row['No60_minus_MA63_wealth_gap_CNY']=row['No60_NAV_end_CNY']-row['MA63_90_NAV_end_CNY'];axis.append(row)
    endinggap=paths['No60'][-1]['NAV']-paths['MA63_90'][-1]['NAV'];total=sum((x['monthly_gap_CNY']for x in gaps),ZERO)
    assert total==endinggap==sum((x['No60_minus_MA63_day_gap_CNY']for x in axis),ZERO)
    for name in NAMES:
        ms=[lookup[m,name]for m in months];assert sum((x['net_PnL_CNY']for x in ms),ZERO)==paths[name][-1]['NAV']-INITIAL
        for left,right in zip(ms,ms[1:]):assert left['ending_NAV_CNY']==right['carried_NAV_CNY']
    writecsv('MONTHLY_TIDY.csv',monthly);writecsv('MONTHLY_WIDE.csv',wide);writecsv('MONTHLY_GAPS.csv',gaps);writecsv('DAILY_AXIS.csv',axis)
    unfavorable=sorted([x for x in gaps if x['monthly_gap_CNY']<0],key=lambda x:x['monthly_gap_CNY']);favorable=sorted([x for x in gaps if x['monthly_gap_CNY']>0],key=lambda x:x['monthly_gap_CNY'],reverse=True)
    save('TELESCOPE_PROOF.json',dict(passed=True,scope='read-only monthly arithmetic, not new strategy or money account',days=484,months=24,policy_months=96,existing_period_rows_matched=checkcounts,
        month_carry_and_2023_inheritance_exact=True,No60_minus_MA63_monthly_sum_CNY=total,No60_minus_MA63_ending_wealth_difference_CNY=endinggap,
        max_legacy_phase_cash_aggregation_roundoff_CNY=max_legacy_cash_aggregation_delta,
        unfavorable_months=len(unfavorable),unfavorable_month_gap_sum_CNY=sum((x['monthly_gap_CNY']for x in unfavorable),ZERO),favorable_months=len(favorable),favorable_month_gap_sum_CNY=sum((x['monthly_gap_CNY']for x in favorable),ZERO),
        year_gap_CNY={y:sum((x['monthly_gap_CNY']for x in gaps if x['month'].startswith(y)),ZERO) for y in ('2022','2023')},
        most_negative_months_posthoc_only=unfavorable[:6],most_positive_months_posthoc_only=favorable[:4],no_new_strategy_replay=True,percentages_not_summed=True))
    sources += [Path(__file__),ROOT/'independent_review/BENCHMARK_2022_2023_INDEPENDENT_AUDIT.json',ROOT/'independent_review/PVR_2024_INDEPENDENT_AUDIT.json']
    save('SOURCE_SHA256.json',{str(p):sha(p) for p in sources})
    print('MONTHLY_AXIS_PASS','24months','96policy-months','484dates','GAP',endinggap,'ADVERSE',len(unfavorable),'FAVOURABLE',len(favorable),flush=True)
if __name__=='__main__':main()
