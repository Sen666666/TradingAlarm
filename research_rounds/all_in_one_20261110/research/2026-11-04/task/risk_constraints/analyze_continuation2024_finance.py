"""Thin reuse of saved period accounting for own 726-CLOSE continuations."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import importlib.util,json

HERE=Path(__file__).resolve().parent;OUT=HERE/'continuation2024_finance'
sp=importlib.util.spec_from_file_location('absolute_saved_finance_2024',HERE/'analyze_absolute_loss.py')
F=importlib.util.module_from_spec(sp);sp.loader.exec_module(F)
Z=D(0)
def save(p,x):F.save(p,x)
def main():
    OUT.mkdir(exist_ok=False);summary={};periods=[];sectors=[]
    base=HERE.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024'
    for ref,side in [('PVR_SLOT1','original'),('PVR_NO_CONFIRMED60','no60')]:
        root=base/side/'run-2024';a=F.analyze(ref,root,726);daily=a['daily'];b=F.book(root/'pair/B.json.gz')
        summary[ref]=dict(cumulative2022_2024=F.period_summary(daily),year2024=F.period_summary([r for r in daily if r['day'].startswith('2024')]),ACT_events=a['ACT_events'],fractional_splits=a['fractional_splits'])
        save(OUT/(ref+'_DAILY.json'),daily);save(OUT/(ref+'_SECTOR_DAILY.json'),a['sector_daily'])
        buycost=defaultdict(lambda:Z);jr={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'}
        for t in b['trades']:
            if t['side']=='buy':buycost[t['layer']]+=F.n(t['gross_cny'])+F.n(t['fees_cny'])
        ll=[]
        for x in b['layers']:
            sid=x['sid'];m=b['metadata'][str(x['id'])];j=jr[x['id']];value=D(x['qty'])*F.A.price(sid,'2024-12-31') if x['qty'] else Z
            ll.append(dict(layer=x['id'],sid=sid,name=F.A.META[sid]['name'],industry=F.A.META[sid]['industry'],sector=m['sector'],role=j['role'],pool_at_fill=j['pool'],
                signal_day=F.day(x['signal_at']),opened=x['opened'],closed=x['closed'],qty=x['qty'],cost=buycost[x['id']],net=F.n(x['cash'])+F.n(x['dividend'])+value,value=value,receipt=j['CP1_id'],attempt=m['attempt']))
        F.close(sum((x['net'] for x in ll),Z),F.n(b['ending_NAV'])-D(1000000),(ref,'derived LAYERS wealth'))
        target=OUT/'analysis/2022_2024'/ref;target.mkdir(parents=True,exist_ok=False);save(target/'LAYERS.json',ll)
        for grain in ['all','year','quarter','month']:
            for p in sorted({F.key(r['day'],grain) for r in daily}):
                dr=[r for r in daily if F.key(r['day'],grain)==p];period=F.period_summary(dr)
                periods.append(dict(reference=ref,grain=grain,period=p,**period));sectorrows=[]
                for s in sorted({r['sector'] for r in a['sector_daily']}):
                    rr=[r for r in a['sector_daily'] if r['sector']==s and F.key(r['day'],grain)==p]
                    z={k:sum((r[k] for r in rr),Z) for k in F.SUMKEYS};num=len(rr)
                    z.update(reference=ref,grain=grain,period=p,sector=s,industry=rr[0]['industry'],closes=num,inventory_begin=rr[0]['inventory_begin'],inventory_end=rr[-1]['inventory_end'],
                        mean_held_cost_basis=sum((r['held_cost_basis'] for r in rr),Z)/num,mean_market_value=sum((r['market_value'] for r in rr),Z)/num,mean_exposure_pct=sum((r['exposure_pct'] for r in rr),Z)/num)
                    sectorrows.append(z);sectors.append(z)
                F.close(sum((x['wealth_change'] for x in sectorrows),Z),period['wealth_change'],(ref,p,'sector wealth'))
        save(OUT/'SUMMARY.json',summary);save(OUT/'PERIODS.json',periods);save(OUT/'SECTORS.json',sectors)
        print('SAVED2024_FINANCE',ref,'2024',summary[ref]['year2024']['wealth_change'],'cumulative',summary[ref]['cumulative2022_2024']['wealth_change'],flush=True)
    for sid in F.A.frames:
        p=Path(F.A.SM[sid]['refs']['facts']);actual=F.sha(p);assert actual==F.A.SM[sid]['output_sha256'][str(p)];F.SRC[str(p)]=actual
    for p in [Path(__file__),HERE/'analyze_absolute_loss.py',F.P]:F.SRC[str(p)]=F.sha(p)
    save(OUT/'SOURCE_MANIFEST.json',dict(sources=F.SRC,account_events=0,
        accounting='Unchanged pure saved period analyze() and period_summary(), actual trade cash plus rawmark/dividend and actual-sale-basis real/unreal dual bridges; zero account objects',
        start='Original1m at2022start; 2024 normalized own2023ending NAV, not fresh1m or common inherited capital',
        inputs_signals='Canonical/source/parentprefix identity separately bound in continuation2024_drawdown; owner/reviewer signal fidelity separate, not implied by money bridge',
        sampling='DD only actual saved daily CLOSE; intraday joint maxDD unknown; no OHLC basket assembled'))
    print('SAVED2024_FINANCE_COMPLETE',len(periods),len(sectors),flush=True)
if __name__=='__main__':main()
