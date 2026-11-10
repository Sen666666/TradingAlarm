"""Read-only post-result mechanism evidence; does not run or alter accounts."""
from audit import *

def main():
 summary=pd.read_csv(O/'summary.csv');campaigns=pd.read_csv(O/'campaigns.csv');rot=pd.read_csv(O/'rotations.csv');snap=Path(read(PREVIOUS/'input.json')['snapshot']['path']);meta=pd.read_csv(C.DESIGN/'proposed-pool.csv').set_index('symbol');duration=[]
 for v in ['RS','PVR','ROT','ROT25']:
  f=campaigns[(campaigns.version==v)&(campaigns.scenario=='base')&campaigns.closed]
  d=(pd.to_datetime(f.exit_at,utc=True)-pd.to_datetime(f.entry_at,utc=True)).dt.total_seconds()/86400
  duration.append({'version':v,'median_calendar_holding_days':float(d.median()),'mean_calendar_holding_days':float(d.mean())})
 pd.DataFrame(duration).to_csv(O/'holding-duration.csv',index=False)
 diagnostics=[];roots={'RS':PREVIOUS/'RS','PVR':PREVIOUS/'PVR','ROT':O/'ROT'}
 for v,root in roots.items():
  dd={r['at'][:10]:r for r in rows(root/'accounts-v2/daily.jsonl.gz') if r['account']=='I__S0_base'};decs={r['at'][:10]:r for r in rows(root/'accounts-v2/decisions.jsonl.gz') if r['account']=='I__S0_base'}
  for day,ids in [('2025-06-27',['300502.SZ']),('2025-10-20',['688498.SH','688048.SH'])]:
   a=dd[day];d=decs[day];groups=Counter(meta.loc[s,'industry'] for s in a['positions']);stocks='|'.join(str(meta.loc[s,'name']) for s in a['positions'])
   for sid in ids:diagnostics.append({'version':v,'date':day,'symbol':sid,'name':meta.loc[sid,'name'],'eligible':sid in d['eligible'],'accepted':sid in d['accepted'],'held_stocks':stocks,'held_sector_counts':json.dumps(dict(groups),ensure_ascii=False),'held_count':len(a['positions'])})
 pd.DataFrame(diagnostics).to_csv(O/'winner-capacity-traces.csv',index=False)
 x=rot[(rot.version=='ROT')&(rot.scenario=='base')&rot.victim.eq('603186.SH')&rot.signal_at.str.startswith('2026-04-15')].iloc[0]
 cases=campaigns[(campaigns.version.isin(['PVR','ROT']))&(campaigns.scenario=='base')&campaigns.symbol.eq('603186.SH')&campaigns.entry_at.str.startswith('2026-04-08')]
 save(O/'case-huazheng.json',{'rotation':x.to_dict(),'same_entry_campaigns':cases.to_dict('records'),'interpretation':'相对分差可以替换仍正向的持仓；两路径仓位大小和其他交易不同，不把机会差额当无成本可追回的因果增量。','post_result_only':True})
 graph(snap)
 for sc in ['base','cost2','delay1']:
  a=summary[(summary.version=='PVR')&(summary.scenario==sc)].iloc[0];b=summary[(summary.version=='ROT')&(summary.scenario==sc)].iloc[0]
  assert abs((b.tail_profit-a.tail_profit)+(b.ordinary_profit-a.ordinary_profit)+(b.open_profit-a.open_profit)-(b.net_profit-a.net_profit))<1e-7
 save(O/'postmortem.json',{'duration':duration,'winner_capacity_traces':diagnostics,'economic_reruns':0,'strategy_revisions':0,'post_result_only':True})

def graph(snap):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Rectangle
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 fig,ax=plt.subplots(3,2,figsize=(15,9),sharex='col',gridspec_kw={'height_ratios':[2,1,1]})
 for j,sid in enumerate(['603186.SH','002552.SZ']):
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc['2026-04-01':'2026-07-20'];z=pd.read_parquet(PREVIOUS/'scores'/f'{sid}.parquet').reindex(f.index);xx=np.arange(len(f))
  for i,(_,r) in enumerate(f.iterrows()):
   color='#b6382f' if r.close>=r.open else '#28764f';ax[0,j].vlines(i,r.low,r.high,color=color,lw=.6);ax[0,j].add_patch(Rectangle((i-.3,min(r.open,r.close)),.6,max(abs(r.close-r.open),1e-5),facecolor=color,lw=.4))
  markers=[('2026-04-08','两组共同买入华正','#567cb1'),('2026-04-16','换仓组卖出华正','#d27325'),('2026-07-14','仅PVR组卖出华正','#249078')] if j==0 else [('2026-04-16','换仓组买入宝鼎','#d27325')]
  for day,label,col in markers:
   if pd.Timestamp(day) in f.index:
    ix=f.index.get_loc(day);ax[0,j].axvline(ix,color=col,ls='--',lw=.9,label=label)
  ax[0,j].set_title(sid+' 因果复权OHLC');ax[0,j].legend(fontsize=8);ax[1,j].bar(xx,f.amount/1e8,color='#8a9fb2');ax[1,j].set_ylabel('金额 / 亿元');ax[2,j].plot(xx,z.score,label='PVR');ax[2,j].axhline(50,color='grey',lw=.6,ls='--');ax[2,j].set_ylim(0,100);ticks=np.linspace(0,len(f)-1,5,dtype=int);ax[2,j].set_xticks(ticks,[str(f.index[i].date())[2:] for i in ticks],rotation=20)
 fig.suptitle('事后机制复盘：华正新材67.01分，被83.62分的宝鼎科技替换；价格图不代表可追回收益');fig.tight_layout();fig.savefig(O/'case-huazheng-v2.png',dpi=125);plt.close(fig)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='graph':graph(Path(read(PREVIOUS/'input.json')['snapshot']['path']))
 else:main()
