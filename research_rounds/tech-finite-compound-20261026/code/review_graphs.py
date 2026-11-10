from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
CASES={'688498.SH':'源杰科技','688195.SH':'腾景科技','600588.SH':'用友网络','000063.SZ':'中兴通讯'}
def main():
 overlay=sys.argv[1]=='overlay';records={r['series_id']:r for r in read(CORE/'manifest.json')['series']};plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans']
 refs=[]
 for label,start,end in [('2024','2024-01-01','2024-12-31'),('2025-2026','2025-01-01','2026-10-26')]:
  fig,axes=plt.subplots(4,3,figsize=(17,12))
  for row,(sid,name) in enumerate(CASES.items()):
   rec=records[sid];f=read_raw(rec['raw']['path'],rec).loc[start:end];a,b,c=axes[row];a.fill_between(f.index,f.low,f.high,color='#9cacc2',alpha=.4);a.plot(f.index,f.close,color='#283e5b',lw=1);b.bar(f.index,f.volume/1e6,color='#839bb5',width=1.3);c.bar(f.index,f.amount/1e8,color='#8fa28d',width=1.3)
   a.set_ylabel(name+' 原价');b.set_ylabel('成交股数/百万');c.set_ylabel('成交金额/亿元')
   if overlay:
    g=pd.read_parquet(PREP/'facts'/f'{sid}.parquet').loc[start:end];a.plot(g.index,g.i_floor/g.factor,label='I支持（原价坐标）',color='#d68837',lw=.8);ev=g.i_buy.astype(bool);a.scatter(g.index[ev],g.raw_close[ev],s=8,color='#c1444b',label='I原始事件');a.legend(fontsize=7,loc='upper left');b.clear();b.step(g.index,g.g_grade*25,color='#a55a49',lw=1);b.axhline(50,color='#888',lw=.5);b.set_ylabel('G1证据分');b.set_ylim(-85,110)
   for ax in [a,b,c]:ax.grid(alpha=.2);ax.tick_params(axis='x',labelrotation=20,labelsize=7)
   refs.append(dict(symbol=sid,start=start,end=end,source_sha256=rec['raw']['sha256'],rows=len(f)))
  fig.suptitle(('原始量价＋成交金额' if not overlay else '原指标叠加：事件不是实际买入')+'｜'+label);fig.tight_layout();fig.savefig(HERE/(('overlay-' if overlay else 'raw-')+label+'.png'),dpi=125);plt.close(fig)
 write(HERE/(('overlay' if overlay else 'raw')+'-review-inputs.json'),dict(recorded_at=now(),windows=refs,new_accounts=0))
if __name__=='__main__':main()
