"""Read-only independent flow/mark/statistics audit of the two completed long books."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
from datetime import datetime
from bisect import bisect_right
import gzip,hashlib,json,time
import pandas as pd
O=Path(__file__).resolve().parents[1];R=Path(__file__).resolve().parent;Z=D(0);EPS=D('0.000001')
def j(p):return json.loads(Path(p).read_text())
def gz(p,lines=False):
    with gzip.open(p,'rt')as h:return list(map(json.loads,h))if lines else json.load(h)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def n(v):return D(str(v))
def eq(a,b,label):assert abs(n(a)-n(b))<EPS,(label,str(a),str(b))
def main():
    started=time.monotonic();report=j(O/'analysis/LONG_COMPLETED_ACCOUNT_RESULTS.json');source=j(O/'analysis/LONG_FINANCIAL_SOURCE_SHA256.json');assert all(sha(p)==h for p,h in source.items())
    freeze=j(O/'funding/SOURCE_FREEZE.json');assert all(sha(p)==h for p,h in freeze['sources'].items())
    assert j(O/'funding/runs/long_OFF/ORIGINAL_IDENTITY.json')['passed']
    sm={r['symbol']:r for r in j('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};meta=j('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');sectors={meta[s]['sector_id']for s in sm};assert len(sectors)==90
    prices={}
    def price(sid,day):
        if sid not in prices:
            p=Path(sm[sid]['refs']['facts']);assert sha(p)==sm[sid]['output_sha256'][str(p)];f=pd.read_parquet(p,columns=['raw_close']);prices[sid]=(list(f.index.strftime('%Y-%m-%d')),[n(x)for x in f.raw_close])
        dates,values=prices[sid];i=bisect_right(dates,day)-1;assert i>=0;v=values[i];assert v.is_finite()and v>0;return v
    rule=j('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');start=datetime.fromisoformat('2022-01-01T15:10:00+08:00');end=datetime.fromisoformat('2024-12-31T15:10:00+08:00');open_days={t[:10]for t in rule['calendars']['A']if start<=datetime.fromisoformat(t)<=end};assert len(open_days)==726
    result={}
    for mode in ['OFF','BB20']:
        root=O/'funding/runs'/('long_'+mode);assert j(root/'DONE.json')['completed'];b=gz(root/'pair/B.json.gz');ds=gz(root/'pair/daily.jsonl.gz',True);certs=gz(root/'pair/balances.jsonl.gz',True);saved=j(O/'analysis'/('long_'+mode+'_DAILY.json'));layers=j(O/'analysis'/('long_'+mode+'_LAYERS.json'));industries=j(O/'analysis'/('long_'+mode+'_INDUSTRIES.json'));stocks=j(O/'analysis'/('long_'+mode+'_STOCKS.json'));assert len(ds)==len(certs)==len(saved)==726
        tx=defaultdict(list);div=defaultdict(list);cost=defaultdict(lambda:Z)
        for t in b['trades']:
            tx[t['at'][:10]].append(t)
            if t['side']=='buy':cost[t['layer']]+=n(t['gross_cny'])+n(t['fees_cny'])
        for e in b['audit']:
            if e['kind']=='dividend_accrual':div[e['receivable']['ex_at'][:10]].append(e['receivable'])
        wealth_cash=defaultdict(lambda:Z);old_stock=defaultdict(lambda:Z);stock_weight=defaultdict(lambda:Z);industry_delta={};industry_weight={};daily=[];prior_nav=D(1000000);prior_on=True;prior_day='2022-01-01'
        for r,c,a in zip(ds,certs,saved):
            day=r['at'][:10];assert c['at'][:10]==a['day']==day
            for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:eq(c[k],Z,(mode,day,k))
            for v in c['pool_occupancy_difference'].values():eq(v,Z,(mode,day,'pool'))
            buy=sell=fee=gross=Z
            for t in tx[day]:
                g=n(t['gross_cny']);f=n(t['fees_cny']);gross+=g;fee+=f
                if t['side']=='buy':wealth_cash[t['security_id']]-=g+f;buy+=g+f
                else:wealth_cash[t['security_id']]+=g-f;sell+=g-f
            for e in div[day]:wealth_cash[e['security_id']]+=n(e['net_local'])
            inv={sid:D(q)*price(sid,day)for sid,q in r['positions'].items()if q};inventory=sum(inv.values(),Z);eq(inventory,r['inventory'],(mode,day,'raw inventory'))
            stock={s:wealth_cash[s]+inv.get(s,Z)for s in set(wealth_cash)|set(inv)};nav=D(1000000)+sum(stock.values(),Z);eq(nav,r['nav'],(mode,day,'trade consideration fee recognizeddiv rawmark NAV'))
            inc=defaultdict(lambda:Z);weight=defaultdict(lambda:Z)
            for sid,v in stock.items():inc[meta[sid]['sector_id']]+=v-old_stock[sid]
            for sid,v in inv.items():weight[meta[sid]['sector_id']]+=v/nav*100;stock_weight[sid]+=v/nav*100
            eq(sum(inc.values(),Z),nav-prior_nav,(mode,day,'industry sum'))
            industry_delta[day]=inc;industry_weight[day]=weight
            v=dict(day=day,begin_NAV=prior_nav,begin_NAV_day=prior_day,end_NAV=nav,wealth_change=nav-prior_nav,inventory=inventory,exposure_pct=inventory/nav*100,available=n(r['available']),buy_cash=buy,sell_net=sell,fees=fee,fill_sides=len(tx[day]),gross_turnover=gross,has_actual_OPEN=day in open_days,ACT_at_OPEN=prior_on,ACT_after_CLOSE=bool(r['on']))
            for k,value in v.items():
                if isinstance(value,(D,int))and not isinstance(value,bool):eq(a[k],value,(mode,day,k))
                else:assert a[k]==value,(mode,day,k)
            daily.append(v);old_stock=defaultdict(lambda:Z,stock);prior_nav=nav;prior_on=bool(r['on']);prior_day=day
        eq(prior_nav,b['ending_NAV'],(mode,'end'))
        native={l['id']:l for l in b['layers']};snet=defaultdict(lambda:Z);scost=defaultdict(lambda:Z);scount=defaultdict(int)
        assert {l['layer']for l in layers}==set(native)
        for l in layers:
            x=native[l['layer']];v=D(x['qty'])*price(x['sid'],'2024-12-31')if x['qty']else Z;net=n(x['cash'])+n(x['dividend'])+v
            eq(l['value'],v,(mode,l['layer'],'value'));eq(l['net'],net,(mode,l['layer'],'net'));eq(l['cost'],cost[l['layer']],(mode,l['layer'],'cost'));assert l['qty']==x['qty'];snet[x['sid']]+=net;scost[x['sid']]+=cost[l['layer']];scount[x['sid']]+=1
        eq(sum(snet.values(),Z),prior_nav-D(1000000),(mode,'layer bridge'))
        assert {s['sid']for s in stocks}==set(snet)
        for s in stocks:
            eq(s['net'],snet[s['sid']],(mode,s['sid'],'stock net'));eq(s['cost'],scost[s['sid']],(mode,s['sid'],'stock cost'));eq(s['mean_whole_window_NAV_weight_pct'],stock_weight[s['sid']]/726,(mode,s['sid'],'stock mean weight'));assert s['layers']==scount[s['sid']]
        periods=j(O/'analysis'/('long_'+mode+'_PERIODS.json'));assert periods==report['periods'][mode]
        for pname,p in periods.items():
            rr=[v for v in daily if p['begin']<=v['day']<=p['end']];initial=rr[0]['begin_NAV'];peak=initial;worst=Z;peakday=datetime.fromisoformat(rr[0]['begin_NAV_day']);longest=0;under=False
            for v in rr:
                d=datetime.fromisoformat(v['day']);value=v['end_NAV'];worst=max(worst,1-value/max(peak,value))
                # Calendar time-to-recovery ends at the first observed CLOSE
                # recovering the peak, including non-observation holiday gaps.
                if value>=peak:
                    if under:longest=max(longest,(d-peakday).days)
                    peak=value;peakday=d;under=False
                else:under=True;longest=max(longest,(d-peakday).days)
            metrics=dict(CLOSEs=len(rr),begin_NAV=initial,end_NAV=rr[-1]['end_NAV'],wealth_change=rr[-1]['end_NAV']-initial,return_pct=(rr[-1]['end_NAV']/initial-1)*100,max_CLOSE_DD_pct=worst*100,mean_exposure_pct=sum((v['exposure_pct']for v in rr),Z)/len(rr),peak_exposure_pct=max(v['exposure_pct']for v in rr),actual_buy_cash=sum((v['buy_cash']for v in rr),Z),actual_sell_net=sum((v['sell_net']for v in rr),Z),actual_fees=sum((v['fees']for v in rr),Z),actual_fill_sides=sum(v['fill_sides']for v in rr),actual_gross_turnover=sum((v['gross_turnover']for v in rr),Z),gross_turnover_over_mean_NAV=sum((v['gross_turnover']for v in rr),Z)/(sum((v['end_NAV']for v in rr),Z)/len(rr)),actual_OPENs=sum(v['has_actual_OPEN']for v in rr),active_OPENs=sum(v['has_actual_OPEN']and v['ACT_at_OPEN']for v in rr),longest_underwater_calendar_days=longest,end_underwater_censored=under)
            for k,value in metrics.items():
                if isinstance(value,bool):assert p[k]==value
                else:eq(p[k],value,(mode,pname,k))
            inds=[v for v in industries if v['period']==pname];assert len(inds)==90 and {v['sector']for v in inds}==sectors
            for v in inds:
                sec=v['sector'];eq(v['wealth_change'],sum((industry_delta[d['day']][sec]for d in rr),Z),(mode,pname,sec,'industry wealth'));eq(v['mean_NAV_weight_pct'],sum((industry_weight[d['day']][sec]for d in rr),Z)/len(rr),(mode,pname,sec,'industry weight'))
            eq(sum((n(v['wealth_change'])for v in inds),Z),metrics['wealth_change'],(mode,pname,'90 industry bridge'))
        result[mode]=dict(closes=726,actual_fill_sides=len(b['trades']),layers=len(layers),all_daily_native_certificates=True,all_daily_tradecash_dividend_rawmark_NAV_exact=True,all_period_metrics_and_90_industry_wealth_exact=True,all_layer_and_stock_ending_contributions_exact=True,all_period=periods['all'])
    original=gz(Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/B.json.gz'));off=gz(O/'funding/runs/long_OFF/pair/B.json.gz');assert original==off
    delta=n(result['BB20']['all_period']['end_NAV'])-n(result['OFF']['all_period']['end_NAV']);output=dict(passed=True,status='PASS_COMPLETED_LONG_ACCOUNT_FINANCIAL_RESULTS_ONLY',windows_completed_here=['long'],strong_pending=True,new_simulations_by_reviewer=0,original_OFF_book_independently_exact=True,source_freeze_sha256=sha(O/'funding/SOURCE_FREEZE.json'),all_frozen_sources_current=True,financial_analysis_source_hashes=len(source),raw_price_facts_independently_read=len(prices),results=result,BB20_minus_OFF_terminal_NAV=delta,seconds=time.monotonic()-started,interpretation='Actual long-account comparison only: lower terminal wealth and deeper global CLOSE drawdown under BB, despite lower fees/turnover and better 2024/after924 interval results. Strong window remains required; no parameter/window/strategy change follows from this audit.')
    (R/'LONG_ACCOUNT_FINANCIAL_REVIEW.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(output,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
