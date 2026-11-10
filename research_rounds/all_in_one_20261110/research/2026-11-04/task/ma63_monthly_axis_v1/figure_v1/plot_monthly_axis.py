"""Display only two existing audited tables; no account/strategy computation."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
import csv,hashlib,json,os,shutil
O=Path(__file__).resolve().parent;P=O.parent
cache=O/'.mplconfig';cache.mkdir(exist_ok=True)
prior=P.parent/'three_year_path_2022_2024/.mplconfig/fontlist-v3.11.0.json'
if prior.exists() and not(cache/prior.name).exists():shutil.copyfile(prior,cache/prior.name)
os.environ['MPLCONFIGDIR']=str(cache)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DAILY=P/'DAILY_AXIS.csv';MONTH=P/'MONTHLY_WIDE.csv'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert not(O/'VALIDATION.json').exists() or os.environ.get('LAYOUT_REFRESH')=='1','completed display not silently regenerated'
    before={str(p):sha(p) for p in (DAILY,MONTH)}
    d=list(csv.DictReader(DAILY.open()));m=list(csv.DictReader(MONTH.open()))
    assert len(d)==484 and len(m)==24
    dates=[r['date'] for r in d];months=[r['month'] for r in m]
    assert dates==sorted(set(dates)) and dates[0]=='2022-01-04' and dates[-1]=='2023-12-29'
    assert months==[f'{y}-{mo:02d}' for y in (2022,2023) for mo in range(1,13)]
    endpoints={}
    for name in ('PVR','No60','MA63_90','BH'):
        assert D(d[0][name+'_NAV_begin_CNY'])==D(1000000)
        assert D(d[-1][name+'_NAV_end_CNY'])==D(m[-1][name+'_ending_NAV_CNY'])
        endpoints[name]=d[-1][name+'_NAV_end_CNY']
    gaps=[D(r['No60_monthly_PnL_difference_vs_MA63_CNY']) for r in m]
    total=sum(gaps,D(0));assert total==D(endpoints['No60'])-D(endpoints['MA63_90'])==D('-209443.4076219099465')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,(top,middle,bottom)=plt.subplots(3,1,figsize=(13.2,10.5),sharex=True,gridspec_kw={'height_ratios':[2.2,1.1,1.65]})
    x=[datetime.fromisoformat(day)for day in dates];xm=[datetime.fromisoformat(r['month']+'-15')for r in m]
    colors={'PVR':'#78657e','No60':'#de7c32','MA63_90':'#2878ac','BH':'#2f936c'}
    labels={'PVR':'Original PVR','No60':'No60','MA63_90':'ETF MA63 (90% entry)','BH':'ETF buy & hold'}
    for n in colors:top.plot(x,[float(r[n+'_NAV_end_CNY'])/1e6 for r in d],color=colors[n],lw=1.7,label=labels[n])
    top.axhline(1,color='#7b8591',lw=.8,ls='--',alpha=.6)
    top.set_ylabel('NAV (CNY million)');top.legend(ncol=2,loc='lower left',frameon=False,fontsize=9)
    top.set_title('2022-2023: audited wealth, prior-close exposure and monthly wealth gaps',loc='left',fontsize=14,pad=15)
    for n in ('No60','MA63_90'):
        middle.plot(xm,[float(r[n+'_mean_previous_close_exposure_pct']) for r in m],color=colors[n],marker='o',markersize=3,lw=1.5,label=labels[n])
    middle.set_ylabel('Mean prior-close\nexposure (%)');middle.set_ylim(-3,104);middle.legend(ncol=2,loc='lower right',frameon=False,fontsize=9)
    vals=[float(v)/1000 for v in gaps]
    bottom.bar(xm,vals,width=21,color=['#c85050' if v<0 else '#2f936c' if v>0 else '#a7adb5'for v in vals],zorder=3)
    bottom.axhline(0,color='#555f6d',lw=.9);bottom.set_ylabel('No60 minus MA63\nmonthly P&L (CNY thousands)')
    for mon,offset in [('2022-12',(-85,40)),('2023-04',(35,-25))]:
        j=months.index(mon);value=vals[j]
        bottom.annotate(f'{mon} gap\n{float(gaps[j]):+,.0f} CNY',xy=(xm[j],value),xytext=offset,textcoords='offset points',ha='right'if offset[0]<0 else'left',va='top',fontsize=9,color='#a33333'if value<0 else'#216c4f',arrowprops={'arrowstyle':'-','color':'#77808c','lw':.8})
    j=months.index('2022-12')
    middle.annotate('Dec22: both highly invested\nNo60 87.2% / MA63 90.1%',xy=(xm[j],90.13),xytext=(-90,-26),textcoords='offset points',ha='right',va='top',fontsize=8.5,color='#485365',arrowprops={'arrowstyle':'-','color':'#77808c','lw':.7})
    for a in (top,middle,bottom):a.grid(True,color='#d8dce2',lw=.55,alpha=.65);a.set_axisbelow(True)
    bottom.set_xticks(xm);bottom.set_xticklabels(months,rotation=55,ha='right',fontsize=8)
    bottom.set_xlim(datetime(2022,1,1),datetime(2023,12,31))
    fig.subplots_adjust(left=.10,right=.985,top=.94,bottom=.17,hspace=.15)
    caption=('484 audited closes / all 24 months / original CNY1m; 2023 inherits each path\'s actual capital. Snapshot A-share development history.\n'
      'ETF daily execution proxy (dated halt/limit/queue state unverified); different universes and fee contracts. Gaps are not alpha and not all macro.\n'
      'Display of existing audited tables only: no new strategy or account. Monthly wealth differences are not entry-lifetime attribution.')
    fig.text(.10,.065,caption,ha='left',va='center',fontsize=8.4,color='#485365',linespacing=1.6)
    fig.savefig(O/'monthly_axis_2022_2023.png',dpi=200,facecolor='white');fig.savefig(O/'monthly_axis_2022_2023.svg',facecolor='white');plt.close(fig)
    assert {str(p):sha(p) for p in (DAILY,MONTH)}==before,'frozen tables changed'
    (O/'SOURCES_SHA256.json').write_text(json.dumps(dict(before,**{str(Path(__file__)):sha(__file__)}),indent=2))
    (O/'VALIDATION.json').write_text(json.dumps(dict(passed=True,display_only=True,dates=484,months=24,endpoints_CNY=endpoints,total_monthly_gap_CNY=str(total),source_tables_unchanged=True,strategy_or_account_replays=0),indent=2))
    print('DISPLAY_PASS',len(d),'dates',len(m),'months','total_gap',total,flush=True)
if __name__=='__main__':main()
