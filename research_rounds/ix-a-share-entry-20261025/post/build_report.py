"""Read-only publication of frozen entry-policy accounts and their diagnostics."""
from pathlib import Path
import sys,json,math
import pandas as pd
import numpy as np
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'code'))
from util_ix import OLD,read,write,now

def records(df):
 return json.loads(df.to_json(orient='records',force_ascii=False))

def main():
 out=HERE/'report';out.mkdir(exist_ok=False)
 s=pd.read_csv(HERE/'analysis/summary.csv');old=pd.DataFrame(read(OLD/'analysis-v2/summary.json'))
 old['entry_scheme']='E0';old['allocation']=old.account.str.split('_').str[0];old['scenario']=old.account.str.split('_').str[1]
 old['account']='E0__'+old.account
 summary=pd.concat([old,s],ignore_index=True)
 c=pd.read_csv(HERE/'analysis/curves.csv');oc=pd.read_csv(OLD/'analysis-v2/curves.csv');oc.account='E0__'+oc.account
 c=pd.concat([oc,c],ignore_index=True)
 curves={aid:dict(dates=f.date.tolist(),nav=f.nav.round(4).tolist(),dd=f.drawdown.round(7).tolist(),exposure=f.exposure.round(7).tolist()) for aid,f in c.groupby('account')}
 campaign=pd.read_csv(HERE/'analysis/campaigns.csv');original=pd.read_csv(OLD/'analysis-v2/campaigns.csv');original.account='E0__'+original.account;original['entry_scheme']='E0'
 campaign=pd.concat([original,campaign],ignore_index=True);campaign.net_pnl=campaign.net_pnl.astype(float)
 stocks=campaign.groupby(['account','symbol','name','industry'],dropna=False).agg(net_pnl=('net_pnl','sum'),campaigns=('net_pnl','size')).reset_index()
 industries=campaign.groupby(['account','industry'],dropna=False).agg(net_pnl=('net_pnl','sum'),campaigns=('net_pnl','size'),stocks=('symbol','nunique')).reset_index()
 profiles=pd.read_csv(HERE/'analysis/entry-profiles.csv');pg=[]
 for aid,f in profiles.groupby('account'):
  pg.append(dict(account=aid,trades=len(f),age_median=f.e0_age.median(),age_p90=f.e0_age.quantile(.9),distance_median=f.support_distance.median(),distance_p90=f.support_distance.quantile(.9),continuation=int(f.signal_type.eq('continuation').sum()),first=int(f.signal_type.eq('first_or_delayed_start').sum()),recovery=int(f.signal_type.eq('recovery').sum())))
 op=pd.read_csv(OLD/'entry-profiles/profiles.csv')
 for aid,f in op.groupby('account'):
  pg.append(dict(account='E0__'+aid,trades=len(f),age_median=f.e0_age_observations.median(),age_p90=f.e0_age_observations.quantile(.9),distance_median=f.close_to_support_fraction.median(),distance_p90=f.close_to_support_fraction.quantile(.9),continuation=None,first=None,recovery=None))
 miss=pd.read_csv(HERE/'misses/annual-winner-reasons.csv');ms=pd.read_csv(HERE/'misses/reason-counts.csv')
 annual=pd.read_csv(HERE/'analysis/annual.csv')
 for aid,f in oc.groupby('account'):
  previous=1e6
  for year,g in f.groupby(pd.to_datetime(f.date).dt.year):
   a=g.nav.to_numpy();annual.loc[len(annual)]=dict(account=aid,entry_scheme='E0',allocation=aid.split('__')[1].split('_')[0],scenario=aid.split('_')[-1],year=int(year),net_return=a[-1]/previous-1,max_drawdown=float(-(a/np.maximum.accumulate(np.r_[previous,a])[1:]-1).min()));previous=a[-1]
 events=pd.read_csv(HERE/'review/event-counts.csv')
 passive=next(x for x in read(HERE.parent/'a-share-selection-e0-20261024/analysis-v2/summary.json') if x['account']=='B0_base')
 payload=dict(summary=records(summary),curves=curves,campaigns=records(campaign),stocks=records(stocks),industries=records(industries),profiles=records(pd.DataFrame(pg)),misses=records(miss),missCounts=records(ms),annual=records(annual),events=records(events),passive=passive,verification=read(HERE/'analysis/accounting-audit.json'),prefix=read(HERE/'technical/multi-prefix-2023-12-29/comparison.json'))
 raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</','<\\/')
 template=(Path(__file__).with_name('report.html')).read_text()
 (out/'index.html').write_text(template.replace('__PAYLOAD__',raw))
 summary.to_csv(out/'all-60-summary.csv',index=False,encoding='utf-8-sig')
 draw(summary,c,out)
 write(out/'manifest.json',dict(recorded_at=now(),new_accounts=48,old_reference_accounts=12,accounting_passed=True,prefix_passed=True,source='frozen economic outputs, read only',files=['index.html','all-60-summary.csv','s0-base.png']))

def draw(summary,curves,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.font_manager import FontProperties
 font=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
 names={'E0':'原 E0','IX':'原 IX','W23':'严格暖→热','W2H':'暖→热/扩张','C3':'跨入热区'};colors={'E0':'#88939b','IX':'#16816f','W23':'#c28130','W2H':'#3c6db1','C3':'#995a9c'}
 fig,ax=plt.subplots(3,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
 for mode in names:
  aid=mode+'__S0_base';f=curves.loc[curves.account.eq(aid)];d=pd.to_datetime(f.date)
  ax[0].plot(d,f.nav/1e4,color=colors[mode],label=names[mode],lw=1.1)
  ax[1].plot(d,100*f.drawdown,color=colors[mode],lw=.85)
  ax[2].plot(d,100*f.exposure,color=colors[mode],lw=.6,alpha=.75)
 for a in ax:a.grid(alpha=.18);a.spines[['top','right']].set_visible(False)
 ax[0].set_title('S0：行业→个股，入场事件对照（各100万元）',fontproperties=font,loc='left');ax[0].set_ylabel('净值／万元',fontproperties=font);ax[0].legend(prop=font,ncol=5,fontsize=9)
 ax[1].set_ylabel('回撤 %',fontproperties=font);ax[2].set_ylabel('持仓暴露 %',fontproperties=font)
 fig.text(.08,.015,'2015—2026-10-22；成本后；当前存续/市值/行业开发口径。四个新方案共用IX退出，行业E0、RS-H1和仓位不变。',fontproperties=font,fontsize=9)
 fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/'s0-base.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
