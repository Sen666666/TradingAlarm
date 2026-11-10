from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
COL={'E0':'#087f8c','F':'#d37517','CP1':'#2768bd'}
def note(ax,xy,text,pos,color):
 ax.annotate(text,xy=xy,xytext=pos,textcoords='axes fraction',fontsize=12,color=color,ha='left',va='top',bbox=dict(boxstyle='round,pad=.45',fc='white',ec=color,alpha=.96),arrowprops=dict(arrowstyle='->',color=color,lw=1.5))
def main():
 for c in read(O/'fixed-window-paths.json'):
  sid=c['case']['symbol']
  if sid not in ['688498.SH','002987.SZ']:continue
  meta=c['anchor'];anchor=meta['opening_price'];paths=c['paths'];window=c['case'];start=window['start'];end=window['end'];f=frame(sid).loc[start:end]
  fig,(ax,av)=plt.subplots(2,1,figsize=(14,8),sharex=True,gridspec_kw={'height_ratios':[4,1]})
  ax.plot(f.index,f.close/anchor*100,c='#293d4b',lw=1.7,label='真实收盘走势')
  for policy in ['E0','F','CP1']:
   r=paths[policy];t=pd.to_datetime([x['date'] for x in r]);ax.step(t,[x['P_before']/anchor*100 for x in r],where='post',c=COL[policy],lw=2 if policy=='CP1' else 1.6,ls='--' if policy=='F' else '-',label=policy+'有效保护')
   if r[-1]['exit']:ax.scatter(t[-1],r[-1]['close']/anchor*100,marker='X',c=COL[policy],s=90,zorder=7)
  ax.axvline(pd.Timestamp(meta['entry_at'][:10]),c='#888',ls=':',lw=1)
  if sid=='688498.SH':
   t='2025-11-24';cp=next(r for r in paths['CP1'] if r['date']==t);fr=paths['F'][-1]
   note(ax,(pd.Timestamp(t),fr['close']/anchor*100),f"11/24：F已触线\nCP1保护约{cp['P_before']/anchor*100:.1f}，仍低于收盘\n这次回调未触发CP1退出",(.035,.94),COL['CP1'])
   r=next(r for r in paths['CP1'] if r['date']=='2025-12-24')
   note(ax,(pd.Timestamp(r['date']),r['P_before']/anchor*100),'蓝线可在持续上涨中继续抬升\n不必等新的回调低点\n本窗CP1与E0都未触发退出',(.53,.40),COL['CP1'])
   title='源杰科技：补上连续推进保护，这段也比F宽容'
  else:
   r=paths['CP1'][-1];note(ax,(pd.Timestamp(r['date']),r['close']/anchor*100),f"CP1在{r['date'][5:]}首次触线\n早于F的09/02、E0的11/11\n第一次回调已结束本次观察",(.03,.95),COL['CP1'])
   later=f.loc['2025-08-01':'2025-09-01'];day=later.close.idxmax();note(ax,(day,float(later.loc[day,'close'])/anchor*100),'后面还有一轮上涨\n这就是保护更近的代价\n图中没有假设自动买回',(.58,.94),'#293d4b')
   title='京北方：推进保护也会过早触线，仍有截断行情的代价'
  av.bar(f.index,f.amount/1e8,color='#829d9b',width=1.4);av.set_ylabel('成交额/亿元');ax.set_ylabel('共同入场开盘=100');ax.legend(loc='lower left',ncol=3)
  for a in [ax,av]:a.grid(alpha=.15);a.set_xlim(f.index[0],f.index[-1]+pd.Timedelta(days=1));a.tick_params(axis='x',rotation=15)
  fig.suptitle(title,fontsize=18);fig.text(.5,.935,'同一观察起点、同一原E0初始保护；只比较首次收盘触线，无资金账户/成交收益/再入场',ha='center',fontsize=11,color='#526575')
  fig.text(.5,.015,'CP1只在新增推进确认后抬线，保护供下一观察使用。X为收盘退出判定，实际执行须等下一可成交开盘。',ha='center',fontsize=10,color='#526575')
  fig.tight_layout(rect=(0,.04,1,.91));fig.savefig(O/'charts'/('explain-'+sid+'.png'),dpi=140);plt.close(fig)
if __name__=='__main__':main()
