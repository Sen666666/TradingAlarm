"""Display four already audited paths; no strategy/account replay."""
from pathlib import Path
from decimal import Decimal as D
import csv,gzip,hashlib,json,os
O=Path(__file__).resolve().parent;ROOT=O.parent
os.environ['MPLCONFIGDIR']=str(O/'.mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

CYCLE=ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024'
BENCH=ROOT/'benchmark_2022_2023/continuation2024'
STOCK_AUDIT=ROOT/'independent_review/PVR_2024_INDEPENDENT_AUDIT.json'
ETF_AUDIT=ROOT/'independent_review/BENCHMARK_2024_CONTINUATION_INDEPENDENT_AUDIT.json'
SOURCES={
 'Original PVR':CYCLE/'original/run-2024/pair/daily.jsonl.gz',
 'No60':CYCLE/'no60/run-2024/pair/daily.jsonl.gz',
 'ETF MA63':BENCH/'daily_2022_2024/MA63_90.csv',
 'ETF buy & hold':BENCH/'daily_2022_2024/BUY_HOLD.csv'}
KEYS={'Original PVR':'PVR_SLOT1','No60':'PVR_NO_CONFIRMED60','ETF MA63':'MA63_90','ETF buy & hold':'BUY_HOLD'}
COLS={'Original PVR':'PVR','No60':'No60','ETF MA63':'ETF_MA63','ETF buy & hold':'ETF_BH'}
COLORS={'Original PVR':'#78657e','No60':'#de7c32','ETF MA63':'#2878ac','ETF buy & hold':'#2f936c'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
    if p.suffix=='.gz':
        with gzip.open(p,'rt') as f:rows=[json.loads(x) for x in f]
        return [(x['at'][:10],D(x['nav'])) for x in rows]
    with p.open() as f:return [(x['date'],D(x['NAV'])) for x in csv.DictReader(f)]
def main():
    assert not(O/'VALIDATION.json').exists(),'completed display not silently regenerated'
    stocks=json.loads(STOCK_AUDIT.read_text());etfs=json.loads(ETF_AUDIT.read_text())
    data={n:load(p) for n,p in SOURCES.items()};dates=[d for d,_ in data['Original PVR']]
    assert len(dates)==726 and len(set(dates))==726 and dates==sorted(dates)
    assert dates[0]=='2022-01-04' and dates[-1]=='2024-12-31'
    dd={};checks={}
    for name,rows in data.items():
        assert [d for d,_ in rows]==dates and rows[0][1]==D(1000000)
        peak=D(1000000);out=[]
        for day,nav in rows:peak=max(peak,nav);out.append((nav/peak-1)*100)
        dd[name]=out
        if name in ('Original PVR','No60'):
            ref=stocks[KEYS[name]];endpoint=D(ref['NAV']);maximum=D(ref['close_DD'])*100
        else:
            ref=etfs[KEYS[name]];maximum=D(ref['close_DD_pct']);endpoint=D(1000000)*(1+D(ref['return_pct'])/100)
        assert abs(rows[-1][1]-endpoint)<D('.00000001')
        assert abs(-min(out)-maximum)<D('.00000001')
        checks[name]=dict(closes=726,endpoint_CNY=str(rows[-1][1]),global_maxDD_pct=str(-min(out)),matched_existing_independent_audit=True)
    with (O/'four_paths_daily.csv').open('w',newline='') as f:
        fields=['date']+[COLS[n]+'_NAV_CNY' for n in data]+[COLS[n]+'_global_DD_pct' for n in data]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for j,date in enumerate(dates):w.writerow(dict(date=date,**{COLS[n]+'_NAV_CNY':str(data[n][j][1]) for n in data},**{COLS[n]+'_global_DD_pct':str(dd[n][j]) for n in data}))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,(ax,down)=plt.subplots(2,1,figsize=(12,8),sharex=True,gridspec_kw={'height_ratios':[2.15,1.3]})
    x=[datetime.fromisoformat(d) for d in dates]
    for name,rows in data.items():
        label=name+(' (90% entry)' if name=='ETF MA63' else '')
        ax.plot(x,[float(v)/1e6 for _,v in rows],color=COLORS[name],lw=1.7,label=label)
        ax.scatter(x[-1],float(rows[-1][1])/1e6,s=18,color=COLORS[name],zorder=5)
        down.plot(x,[float(v) for v in dd[name]],color=COLORS[name],lw=1.5)
    ax.axhline(1,color='#667085',lw=.8,ls='--',alpha=.6)
    ax.set_ylabel('Net asset value (CNY million)');ax.legend(ncol=2,loc='upper left',frameon=False)
    ax.set_title('2022-2024: audited paths from CNY 1,000,000',loc='left',fontsize=15,pad=15)
    down.set_ylabel('Global drawdown (%)');down.set_ylim(-47,1)
    for a in (ax,down):a.grid(True,color='#d8dce2',alpha=.65,lw=.6);a.margins(x=.012)
    down.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1,7]));down.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig.subplots_adjust(left=.09,right=.98,top=.92,bottom=.18,hspace=.13)
    caption=('726 observed closes; each path keeps its own state and running global peak, with no annual reset or exposure scaling.\n'
       'Snapshot A-share development history; ETF daily execution proxies (dated halt/limit/queue state unverified).\n'
       'Stock/ETF cost contracts differ. Reference display only, not an alpha claim or new evidence; raw audits remain authoritative.')
    fig.text(.09,.075,caption,ha='left',va='center',fontsize=8.7,color='#485365',linespacing=1.6)
    fig.savefig(O/'four_paths.png',dpi=200,facecolor='white');fig.savefig(O/'four_paths.svg',facecolor='white');plt.close(fig)
    sources={str(p):sha(p) for p in list(SOURCES.values())+[STOCK_AUDIT,ETF_AUDIT,Path(__file__)]}
    (O/'SOURCES_SHA256.json').write_text(json.dumps(sources,indent=2))
    (O/'VALIDATION.json').write_text(json.dumps(dict(passed=True,scope='display only; no strategy simulation',checks=checks,dates=[dates[0],dates[-1]],each_path_own_global_peak=True),indent=2))
    text='Display only:726 audited closes2022Jan4-2024Dec31, raw1m capital. No scaling or annual reset.\nSource SHA:SOURCES_SHA256.json. Endpoint/globalDD validation:VALIDATION.json.\nCSV:four_paths_daily.csv; figures:four_paths.png and four_paths.svg.\nSnapshot A-share development history; ETF daybar execution proxy, dated execution state unverified.\nDifferent stock/ETF contracts; differences are not labelled alpha. Raw financial audits remain authoritative.\n'
    (O/'README.txt').write_text(text)
    print(json.dumps(checks,indent=2),flush=True)
if __name__=='__main__':main()
