from common import *
from study import native
import model
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
COLOR={'E0':'#087f8c','F':'#d37517','CP1':'#2768bd','PRICE':'#9568a3'}
def main():
 assert read(O/'history-verification.json')['passed']
 dest=O/'charts';dest.mkdir(exist_ok=False);summaries=[];contexts=[]
 meta={c['symbol']:c for c in read(PH/'shadow/summary.json')['cases'] if c['group']=='TECH'}
 cases=read(O/'cases.json')['focused']
 for batch in range(2):
  fig,axs=plt.subplots(3,3,figsize=(18,10),gridspec_kw={'height_ratios':[4,1,1]},sharex='col')
  for j,c in enumerate(cases[3*batch:3*batch+3]):
   sid=c['symbol'];m=meta[sid];f=frame(sid).loc[:c['end']];z=pd.read_parquet(O/'signals'/f'{sid}.parquet');zp=pd.read_parquet(O/'price-control'/f'{sid}.parquet');start=m['entry_at'][:10];norm=m['opening_price']
   old=read(PH/f'shadow/TECH-{sid}-trace.json');paths={p:[dict(date=r['date'],close=r['obs']['close'],P_before=r['P_before'],P_after=r['P_after'],exit=r['exit_required'],reason=r['exit_reason']) for r in old if r['policy']==p] for p in ['E0','F']}
   paths['CP1']=model.project(f,z,start,m['E_entry'],True);paths['PRICE']=model.project(f,zp,start,m['E_entry'],True)
   b=pd.read_parquet(PREP/'signals'/f'{sid}.parquet').reindex(f.index).loc[c['start']:c['end']]
   ax,av,aq=axs[:,j];ax.plot(b.index,b.close/norm*100,c='#293d4b',lw=1.3,label='收盘')
   for p in ['E0','F','PRICE','CP1']:
    rr=paths[p];ts=pd.to_datetime([r['date'] for r in rr]);ax.step(ts,[r['P_before']/norm*100 for r in rr],where='post',c=COLOR[p],lw=1.8 if p=='CP1' else 1,ls='--' if p in ['F','PRICE'] else '-',label=p)
    if rr[-1]['exit']:
     ax.scatter(ts[-1],rr[-1]['close']/norm*100,c=COLOR[p],marker='x',s=55,zorder=8)
     ax.annotate(p+' '+rr[-1]['date'][5:],(ts[-1],rr[-1]['close']/norm*100),xytext=(3,8 if p=='CP1' else -12 if p=='E0' else 20),textcoords='offset points',fontsize=7,color=COLOR[p])
   rr=paths['CP1'];raises=[r for r in rr if r['receipt'] and r['P_after']>r['P_before'] and r['candidate'] is not None and r['candidate']>r['P_before']]
   if raises:
    r=raises[0];ax.scatter(pd.Timestamp(r['date']),r['P_after']/norm*100,marker='^',c=COLOR['CP1'],s=50);ax.annotate('首次推进抬线 '+r['date'][5:],(pd.Timestamp(r['date']),r['P_after']/norm*100),xytext=(3,-25),textcoords='offset points',fontsize=7,color=COLOR['CP1'])
   ax.axvline(pd.Timestamp(start),c='#777',ls=':',lw=.8);ax.set_title(c['name']+' '+sid+'\n共同观察锚 '+start,fontsize=11);ax.legend(fontsize=7,ncol=3);ax.set_ylabel('共同开盘=100')
   av.bar(b.index,b.amount/1e8,color='#829d9b',width=1.4);av.set_ylabel('金额/亿元',fontsize=8)
   zz=z.reindex(b.index);aq.plot(zz.index,zz.credit/(model.A*zz.scale),c=COLOR['CP1'],lw=.8);aq.axhline(1,c='#999',ls=':',lw=.6);aq.set_ylabel('信用/门槛',fontsize=8)
   for a in [ax,av,aq]:a.grid(alpha=.15);a.set_xlim(b.index[0],b.index[-1]+pd.Timedelta(days=1));a.tick_params(axis='x',rotation=20,labelsize=8)
   item=dict(symbol=sid,name=c['name'],anchor=start,anchor_kind=m['anchor_kind'],CP1_actual_receipt_raises=len(raises))
   for p,rs in paths.items():item[p+'_exit']=rs[-1]['date'] if rs[-1]['exit'] else None;item[p+'_observations']=len(rs)
   summaries.append(item);contexts.append(dict(case=c,anchor=m,paths=paths))
  fig.suptitle('固定局部窗 | E0 / 全程F / 连续推进CP1 / 去金额PRICE\n只比较同锚单次观察；X=收盘退出判定，非成交；ACT开启，无资金/名额/再入场',fontsize=13);fig.tight_layout(rect=(0,0,1,.93));fig.savefig(dest/f'focused-{batch+1}.png',dpi=130);plt.close(fig)
 for batch in range(2):
  fig,axs=plt.subplots(3,3,figsize=(18,10),gridspec_kw={'height_ratios':[4,1,1]},sharex='col')
  for j,c in enumerate(cases[3*batch:3*batch+3]):
   sid=c['symbol'];f=frame(sid).loc['2024':];z=pd.read_parquet(O/'signals'/f'{sid}.parquet').reindex(f.index);zp=pd.read_parquet(O/'price-control'/f'{sid}.parquet').reindex(f.index);norm=f.close.iloc[0]
   a,av,aq=axs[:,j];a.plot(f.index,f.close/norm*100,c='#293d4b',lw=1.2,label='收盘');a.plot(f.index,f.i_floor/norm*100,c=COLOR['E0'],lw=.9,label='原E0保护')
   for label,q in [('PRICE',zp),('CP1',z)]:
    mask=q.receipt;a.scatter(q.index[mask],q.loc[mask,'candidate']/norm*100,s=10 if label=='CP1' else 5,c=COLOR[label],alpha=.8,label=label+'新候选')
   a.set_title(c['name']+'｜2024至当前完整轨迹');a.legend(fontsize=7);a.set_ylabel('期初收盘=100')
   av.bar(f.index,f.amount/1e8,color='#829d9b',width=1.4);av.set_ylabel('金额/亿元',fontsize=8)
   aq.plot(z.index,z.m,color=COLOR['CP1'],lw=.6);aq.axhline(1,c='#999',ls=':',lw=.6);aq.set_ylabel('金额调制m',fontsize=8)
   for aa in [a,av,aq]:aa.grid(alpha=.15);aa.tick_params(axis='x',rotation=20,labelsize=8)
  fig.suptitle('固定连续窗 | 圆点为新推进保护候选，不是假定全程持有或成交\nE0无效段没有CP候选；只生成市场事实，不叠加新向下退出',fontsize=13);fig.tight_layout(rect=(0,0,1,.93));fig.savefig(dest/f'continuous-{batch+1}.png',dpi=130);plt.close(fig)
 pd.DataFrame(summaries).to_csv(O/'fixed-window-summary.csv',index=False);save(O/'fixed-window-paths.json',native(contexts))
 print(pd.DataFrame(summaries).to_string(index=False))
if __name__=='__main__':main()
