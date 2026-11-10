"""Build the final local report from audited results, no account computation."""
from pathlib import Path
import os,json,shutil,collections
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/a-selection-report-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import PercentFormatter
import pandas as pd,numpy as np
from build_inputs import HERE,read,write,ref,now

BASE=['T0_base','T1_base','S0_base','S1_base'];COLORS=['#315d97','#48a6a3','#d18a25','#874c9e']
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
def label(ax,title):ax.set_title(title,fontproperties=FONT,loc='left',fontsize=12);ax.grid(alpha=.16)

def plots(out):
 curves=pd.read_csv(HERE/'analysis-v2/curves.csv',parse_dates=['date'])
 fig,axs=plt.subplots(2,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[3,2]})
 for aid,color in zip(BASE,COLORS):
  f=curves[curves.account.eq(aid)];axs[0].plot(f.date,f.nav/1e6,label=aid.split('_')[0],color=color,lw=1.25);axs[1].plot(f.date,f.drawdown,color=color,lw=.9)
 axs[0].set_yscale('log');axs[0].set_ylabel('NAV / initial capital');axs[0].legend(ncol=4)
 label(axs[0],'同为100万元起步：账户净值（对数坐标）');label(axs[1],'日收盘回撤：包含费用、已确认应收与未平仓估值')
 axs[1].yaxis.set_major_formatter(PercentFormatter(1));axs[1].axhline(-.2,ls='--',lw=.8,color='#9b4444');fig.tight_layout();fig.savefig(out/'equity-drawdown.png',dpi=150);plt.close(fig)
 summary={x['account']:x for x in read(HERE/'analysis-v2/summary.json')}
 fig,ax=plt.subplots(figsize=(11,4.5));x=np.arange(4);bottompos=np.zeros(4);bottomneg=np.zeros(4)
 for field,name,color in [('ordinary_closed_pnl','普通闭合周期','#b05b61'),('tail_closed_profit','≥30%闭合周期','#4f9380'),('open_campaign_pnl','尚未闭合持仓','#d4ad64')]:
  v=np.array([summary[a][field]/1e4 for a in BASE]);base=np.where(v>=0,bottompos,bottomneg);ax.bar(x,v,bottom=base,label=name,color=color)
  bottompos+=np.maximum(v,0);bottomneg+=np.minimum(v,0)
 ax.axhline(0,color='#333',lw=.7);ax.set_xticks(x,[a.split('_')[0] for a in BASE]);ax.set_ylabel('CNY 10,000');label(ax,'账户利润来自哪里：已闭合与开放持仓分开');ax.legend(prop=FONT,ncol=3);fig.tight_layout();fig.savefig(out/'profit-sources.png',dpi=150);plt.close(fig)
 stages=pd.read_csv(HERE/'analysis-v2/stages.csv');names=['2015–2017','2018–2020','2021–2023','2024–截点'];fig,ax=plt.subplots(figsize=(12,4.8))
 for i,(aid,color) in enumerate(zip(BASE,COLORS)):
  vals=[float(stages.loc[stages.account.eq(aid)&stages.period.eq(n),'net_return'].iloc[0]) for n in names]
  ax.bar(np.arange(4)+(i-1.5)*.19,vals,width=.18,label=aid.split('_')[0],color=color)
 ax.set_xticks(range(4),names,fontproperties=FONT);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.axhline(0,color='#333',lw=.7);label(ax,'固定四阶段收益：连续账户切段，不在各段重新投入100万元');ax.legend(ncol=4);fig.tight_layout();fig.savefig(out/'fixed-stages.png',dpi=150);plt.close(fig)
 industries=pd.read_csv(HERE/'analysis-v2/actual-industries.csv');fig,axs=plt.subplots(1,2,figsize=(14,6))
 for ax,aid in zip(axs,['T0_base','S0_base']):
  f=industries[industries.account.eq(aid)].sort_values('net_contribution');sel=pd.concat([f.head(5),f.tail(8)]).drop_duplicates('industry').sort_values('net_contribution')
  ax.barh(range(len(sel)),sel.net_contribution/1e4,color=np.where(sel.net_contribution>=0,'#4f9380','#b05b61'));ax.set_yticks(range(len(sel)),sel.industry,fontproperties=FONT,fontsize=9);ax.axvline(0,color='#444',lw=.6);label(ax,aid+' 实际行业贡献（万元）')
 fig.tight_layout();fig.savefig(out/'industry-contribution.png',dpi=150);plt.close(fig)

def case_plots(out,windows,contributions):
 # Examine both directions, determined from audited outcomes rather than a
 # different trading policy. No counterfactual buying of all winners is implied.
 bykey=collections.defaultdict(dict)
 for x in windows:
  if x['account'] in BASE and x['window_type']=='episode' and not x['carry_in_before_account']:bykey[x['key']][x['account']]=x
 pairs=[]
 for key,xs in bykey.items():
  if 'T0_base' in xs and 'S0_base' in xs:
   a,b=xs['T0_base'],xs['S0_base'];pairs.append((b['window_net_contribution']-a['window_net_contribution'],a,b,xs))
 choices=[]
 if pairs:choices=[min(pairs,key=lambda x:x[0]),max(pairs,key=lambda x:x[0])]
 # Add the largest S1 missed signal window as a concentration case.
 missed=[x for x in windows if x['account']=='S1_base' and x['window_type']=='episode' and not x['participated'] and not x['carry_in_before_account']]
 if missed:
  w=max(missed,key=lambda x:x['price_return']);choices.append((0,w,w,bykey[w['key']]))
 prep={x['series_id']:x for x in read(HERE/'prepared-v2/manifest.json')['series']};records={x['series_id']:x for x in read(HERE/'inputs-v2/input-manifest.json')['series']}
 curves=pd.read_csv(HERE/'analysis-v2/curves.csv',parse_dates=['date']);nav={(a,str(d.date())):n for a,d,n in curves[['account','date','nav']].itertuples(index=False,name=None)}
 cases=[];seen=set()
 for delta,a,b,xs in choices:
  if a['key'] in seen:continue
  seen.add(a['key']);sid=a['symbol'];start=pd.Timestamp(a['start_date'])-pd.Timedelta(days=80);end=min(pd.Timestamp(a['end_date'])+pd.Timedelta(days=20),pd.Timestamp('2026-10-22'))
  raw=pd.read_parquet(records[sid]['raw']['path']);raw.index=pd.to_datetime(raw.trade_date);raw=raw.loc[start:end]
  p=prep[sid];state=pd.read_parquet(HERE/'prepared-v2'/p['files']['states']['path']);signal=pd.read_parquet(HERE/'prepared-v2'/p['files']['signal']['path']);floor=(state.floor/signal.adjustment_factor).loc[start:end]
  fig,axs=plt.subplots(4,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[3,1,1,1]})
  axs[0].plot(raw.index,raw.close,color='#263a55',lw=1);axs[0].plot(floor.index,floor,color='#d18a25',lw=.9);axs[0].set_yscale('log');label(axs[0],sid+' '+a['name']+'：原价与E0支持（对数）')
  for ax,aid,color in zip(axs[1:],['T0_base','S0_base','S1_base'],[COLORS[0],COLORS[2],COLORS[3]]):
   f=contributions.loc[contributions.account.eq(aid)&contributions.symbol.eq(sid)&contributions.date.between(start,end)]
   ds=curves.loc[curves.account.eq(aid)&curves.date.between(start,end),'date'];value={str(d.date()):v for d,v in f[['date','market_value']].itertuples(index=False,name=None)}
   weights=[value.get(str(d.date()),0)/nav[(aid,str(d.date()))] for d in ds]
   ax.fill_between(ds,weights,color=color,alpha=.6);ax.set_ylabel(aid.split('_')[0]);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(alpha=.15)
  fig.tight_layout();filename='case-'+str(len(cases)+1)+'.png';fig.savefig(out/filename,dpi=130);plt.close(fig)
  cases.append(dict(image='figures/'+filename,symbol=sid,name=a['name'],key=a['key'],start=a['start_date'],end=a['end_date'],price_return=a['price_return'],
   same_window_contribution_delta_S0_minus_T0=delta,accounts=list(xs.values())))
 # Review actual funded failures as well as successful price windows.
 campaigns=read(HERE/'analysis-v2/campaigns.json')
 for aid,kind in [('S0_base','loss'),('T0_base','loss'),('S0_base','gain')]:
  pool=[c for c in campaigns if c['account']==aid and c['closed']]
  if not pool:continue
  c=(min if kind=='loss' else max)(pool,key=lambda x:float(x['net_pnl']));sid=c['symbol'];start=pd.Timestamp(c['entry_at']).tz_localize(None).normalize();end=pd.Timestamp(c['exit_at']).tz_localize(None).normalize()
  key='funded:'+aid+':'+sid+':'+str(start.date());lo=start-pd.Timedelta(days=50);hi=min(end+pd.Timedelta(days=20),pd.Timestamp('2026-10-22'))
  raw=pd.read_parquet(records[sid]['raw']['path']);raw.index=pd.to_datetime(raw.trade_date);raw=raw.loc[lo:hi]
  p=prep[sid];state=pd.read_parquet(HERE/'prepared-v2'/p['files']['states']['path']);signal=pd.read_parquet(HERE/'prepared-v2'/p['files']['signal']['path']);floor=(state.floor/signal.adjustment_factor).loc[lo:hi]
  fig,axs=plt.subplots(4,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[3,1,1,1]});axs[0].plot(raw.index,raw.close,color='#263a55',lw=1);axs[0].plot(floor.index,floor,color='#d18a25',lw=.9);axs[0].set_yscale('log');label(axs[0],sid+' '+c['name']+'：实际出资周期复盘')
  actual=read(HERE/'accounts-v2'/(aid+'.json'))['fills']
  for side,stamp,color,marker in [('buy',c['entry_at'],'#287e68','^'),('sell',c['exit_at'],'#b84b58','v')]:
   matching=[f for f in actual if f['security_id']==sid and f['side']==side and f['at']==stamp]
   if matching:axs[0].scatter([pd.Timestamp(stamp).tz_localize(None)],[float(matching[0]['gross_cny'])/matching[0]['shares']],color=color,marker=marker,s=45,zorder=4,label='实际'+('首笔买入' if side=='buy' else '末笔卖出'))
  axs[0].legend(prop=FONT,fontsize=8)
  xs=[];count=int(((curves.loc[curves.account.eq('S0_base'),'date']>=start)&(curves.loc[curves.account.eq('S0_base'),'date']<=end)).sum());price=signal.loc[start:end,'close'];gain=float(price.iloc[-1]/price.iloc[0]-1) if len(price) else 0
  for rowaid in BASE:
   part=contributions.loc[contributions.account.eq(rowaid)&contributions.symbol.eq(sid)&contributions.date.between(start,end)]
   held=part.loc[part.shares>0];weights=sum(v/nav[(rowaid,str(d.date()))] for d,v in part[['date','market_value']].itertuples(index=False,name=None))
   xs.append(dict(account=rowaid,price_return=gain,holding_days=len(held),window_sessions=count,mean_account_weight=weights/count if count else 0,
    window_net_contribution=float(part.net_contribution.sum()),primary_reason='actual_position_participation' if len(part) else 'no_actual_position_in_window',first_q_true=None))
  for ax,rowaid,color in zip(axs[1:],['T0_base','S0_base','S1_base'],[COLORS[0],COLORS[2],COLORS[3]]):
   f=contributions.loc[contributions.account.eq(rowaid)&contributions.symbol.eq(sid)&contributions.date.between(lo,hi)];ds=curves.loc[curves.account.eq(rowaid)&curves.date.between(lo,hi),'date'];values={str(d.date()):v for d,v in f[['date','market_value']].itertuples(index=False,name=None)}
   weights=[values.get(str(d.date()),0)/nav[(rowaid,str(d.date()))] for d in ds];ax.fill_between(ds,weights,color=color,alpha=.6);ax.set_ylabel(rowaid.split('_')[0]);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(alpha=.15)
  fig.tight_layout();filename='case-'+str(len(cases)+1)+'.png';fig.savefig(out/filename,dpi=130);plt.close(fig)
  cases.append(dict(image='figures/'+filename,symbol=sid,name=c['name'],key=key,start=str(start.date()),end=str(end.date()),price_return=gain,accounts=xs,
   title=('主要亏损周期' if kind=='loss' else '最大盈利周期')+' · '+aid,booked_campaign_net_pnl=float(c['net_pnl']),booked_campaign_net_return=c['net_return']))
 return cases

def main():
 assert read(HERE/'analysis-v2/independent-accounting.json')['all_passed']
 assert all(read(HERE/'technical-prefix-v2'/d/'exact-comparison.json')['passed'] for d in ['2017-12-31','2020-12-31','2023-12-31'])
 conclusion=read(HERE/'analysis-v2/conclusion.json')
 out=HERE/'report-v2';out.mkdir(exist_ok=False);fig=out/'figures';fig.mkdir();downloads=out/'downloads';downloads.mkdir()
 plots(fig);windows=read(HERE/'misses-v2/windows.json');con=pd.read_csv(HERE/'analysis-v2/daily-stock-contributions.csv',parse_dates=['date']);cases=case_plots(fig,windows,con)
 for name in ['summary','annual','stages','campaigns','fills','actual-stocks','actual-industries','curves','daily-stock-contributions']:shutil.copy2(HERE/'analysis-v2'/(name+'.csv'),downloads/(name+'.csv'))
 for name,path in [('winner-windows.csv',HERE/'misses-v2/windows.csv'),('all-current-A-annual-price.csv',HERE/'opportunities-v2/annual-all-current-A.csv'),('candidate-days.csv',HERE/'funnel-v2/daily-candidate-counts.csv'),('funded-entry-profiles.csv',HERE/'entry-quality-v2/funded-entry-profiles.csv')]:shutil.copy2(path,downloads/name)
 for name,path in [('algorithm-registry.json',HERE.parent/'algorithm-baselines-20261024/registry.json'),('data-closeout-v2.json',HERE/'audit/data-closeout-v2.json'),('economic-protocol.json',HERE/'inputs-v2/economic-protocol.json'),('independent-accounting.json',HERE/'analysis-v2/independent-accounting.json')]:shutil.copy2(path,downloads/name)
 basewindows=[x for x in windows if x['account'] in BASE]
 lean=[{k:v for k,v in x.items() if k not in ('reason_candidate_days','eligibility_component_days','first_q_true')} for x in basewindows]
 data=dict(created_at=now(),conclusion=conclusion,summary=read(HERE/'analysis-v2/summary.json'),annual=read(HERE/'analysis-v2/annual.json'),stages=read(HERE/'analysis-v2/stages.json'),
  stocks=read(HERE/'analysis-v2/actual-stocks.json'),industries=read(HERE/'analysis-v2/actual-industries.json'),windows=lean,cases=cases,
  funnel_totals=read(HERE/'funnel-v2/totals.json'),miss_summary=read(HERE/'misses-v2/summary.json'),data_summary=read(HERE/'data-adjudicated-v2/summary.json'),
  entry_quality=read(HERE/'entry-quality-v2/summary.json'),
  industry_repair=read(HERE/'audit/industry-repair-v2/report.json'),account_audit=read(HERE/'analysis-v2/independent-accounting.json'),
  prefix_checks=[read(HERE/'technical-prefix-v2'/d/'exact-comparison.json') for d in ['2017-12-31','2020-12-31','2023-12-31']],
  remaining_data_unknowns=['000016/002731 当前市值未知；000016行业未知；002731源起点未证实，均保留为未知资格','601326最后源价格为10月20日，未虚构21/22日可成交行情'],
  backtest_scope='2015-01-01—2026-10-22；当前存续A股、当前市值>100亿元、当前行业固定；含选样偏差，非历史时点全池/样本外。',
  bse_facts=read(HERE/'audit/bse-listing-facts.json')['rows'])
 write(out/'data.json',data);template=Path(__file__).with_name('report_template.html');shutil.copy2(template,out/'index.html')
 write(out/'provenance.json',dict(recorded_at=now(),generator=ref(__file__),template=ref(template),package=ref(HERE/'inputs-v2/package.json'),conclusion=ref(HERE/'analysis-v2/conclusion.json'),data=ref(out/'data.json'),
  source_account_provenance=ref(HERE/'accounts-v2/provenance.json'),analysis=ref(HERE/'analysis-v2/independent-accounting.json'),no_new_accounts=True))
 print({'report':str(out),'case_charts':len(cases),'base_diagnostic_windows':len(lean)},flush=True)

if __name__=='__main__':main()
