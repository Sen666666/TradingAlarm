"""Thin reuse of the original audited 484-row continuation finance reader."""
from pathlib import Path
from decimal import Decimal as D
import sys,importlib.util,json,gzip,hashlib

HERE=Path(__file__).resolve().parent;OUT=HERE/'no60_continuation2023_finance'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
PVR=W/'pvr-slot1-native-readiness-20261101';CON=PVR/'continuation-2023-readiness'
sys.path.insert(0,str(CON));p=CON/'analyze_continuation.py';sp=importlib.util.spec_from_file_location('saved_original_2023_finance',p)
C=importlib.util.module_from_spec(sp);sp.loader.exec_module(C);A=C.A;Z=D(0)
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def book(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
    OUT.mkdir(exist_ok=False);A.O=OUT;C.M.O=OUT;C.O=OUT;result={};sources={str(p):sha(p)}
    specs=[('PVR_SLOT1',CON/'run-2023',PVR/'runs/2022'),('PVR_NO_CONFIRMED60',HERE.parent/'pvr_pool_feasibility/continuation2023/run-2023',HERE.parent/'pvr_pool_feasibility/runs/2022')]
    for ref,root,parent in specs:
        assert json.loads((root/'DONE.json').read_text())['completed']
        a=C.account484('2022_2023',ref,root);b=a['book'];old=book(parent/'pair/B.json.gz');ds=[r for r in a['daily'] if day(r['at']).startswith('2023')]
        assert len(ds)==242 and day(ds[0]['at'])=='2023-01-03' and day(ds[-1]['at'])=='2023-12-29'
        parentdaily=rows(parent/'pair/daily.jsonl.gz');assert a['daily'][:242]==parentdaily and b['trades'][:len(old['trades'])]==old['trades']
        initial=n(old['ending_NAV']);end=n(b['ending_NAV']);rb=C.real_bridge(b,'2023-12-29');ob=C.real_bridge(old,'2022-12-30')
        delta={k:rb[k]-ob[k] for k in ['realized_trading_net','unrealized_net_mark_minus_allocated_buy_cost','recognized_dividends']}
        assert abs(sum(delta.values(),Z)-(end-initial))<D('.000001')
        balances=rows(root/'pair/balances.jsonl.gz');assert len(balances)==484
        for r in balances:
            assert all(abs(n(r[k]))<D('.000001') for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'])
            assert all(abs(n(v))<D('.000001') for v in r['pool_occupancy_difference'].values())
        tx=[t for t in b['trades'] if day(t['at']).startswith('2023')]
        rec=dict(initial_2023_own_Dec30_NAV=initial,end_NAV=end,year2023_return_pct=(end/initial-1)*100,
            year2023_DD=A.dd([('own2022Dec30',initial)]+[(day(r['at']),n(r['nav'])) for r in ds]),
            original_1m_cumulative_return_pct=(end/D(1000000)-1)*100,
            cumulative_2022_2023_DD=A.dd([('original1m',D(1000000))]+[(day(r['at']),n(r['nav'])) for r in a['daily']]),
            year_mean_exposure_pct=sum((n(r['inventory'])/n(r['nav'])*100 for r in ds),Z)/242,
            year_mean_nominal_risk_pct=sum(((n(r['pool_probe'][1])+n(r['pool_confirmed'][1]))/n(r['nav'])*100 for r in ds),Z)/242,
            year_mean_available_cash_pct=sum((n(r['available'])/n(r['nav'])*100 for r in ds),Z)/242,
            year_fees=sum((n(t['fees_cny']) for t in tx),Z),cumulative_fees=a['metrics']['fees'],
            year_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in tx if t['side']=='buy'),Z),
            year_buy_fills=sum(t['side']=='buy' for t in tx),year_sell_fills=sum(t['side']=='sell' for t in tx),
            year_paused_closes=sum(not r['on'] for r in ds),year_ACT_events=[r for r in a['metrics']['ACT_events'] if day(r['at']).startswith('2023')],
            cumulative_money_split=rb,year_money_component_changes=delta,terminal_dividend_AR=ds[-1]['dividend_receivable'],
            year_record_only_loss_change=n(ds[-1]['shared_loss'])-n(parentdaily[-1]['shared_loss']),terminal_record_only_loss=ds[-1]['shared_loss'],
            terminal_positions=ds[-1]['positions'],pending_exit_stocks=len(b['exits']),
            realized_label='old real_bridge includes any fractional basis writeoff in realized; pure-trade requires separate split check',
            source_parent_prefix_exact=True,original_1m_not_reset=True,Jan3_included_in_year=True,financial_events=0)
        result[ref]=rec;save(OUT/(ref+'_2023_DAILY.json'),ds)
        for name in ['B.json.gz','daily.jsonl.gz','balances.jsonl.gz']:sources[str(root/'pair'/name)]=sha(root/'pair'/name)
        sources[str(parent/'pair/B.json.gz')]=sha(parent/'pair/B.json.gz')
    result['end_NAV_difference']=result['PVR_NO_CONFIRMED60']['end_NAV']-result['PVR_SLOT1']['end_NAV']
    result['year_percentage_point_difference']=result['PVR_NO_CONFIRMED60']['year2023_return_pct']-result['PVR_SLOT1']['year2023_return_pct']
    save(OUT/'COMPARISON.json',result);sources[str(Path(__file__))]=sha(__file__)
    save(OUT/'SOURCE_MANIFEST.json',dict(sources=sources,financial_events=0,math='original account484 and real_bridge unchanged',
        comparison='own2023 segments have different inherited 2022 capital/positions; not pure 2023 alpha; total wealth starts original1m'))
    print('NO60_CONTINUATION_2023_FINANCE_READY',result['end_NAV_difference'],flush=True)
if __name__=='__main__':main()
