from cp_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def main():
 sector='DRUG';sid='688166.SH';root=O/sector;out=O/'case-plots';out.mkdir(exist_ok=True)
 f=frame(sector,sid).loc['2025-04-01':'2025-10-01'];obj=read(root/'accounts-v2/MCP__S0_base.json')
 logs=[r for r in obj['audit_log'] if r['kind']=='cp_checkpoint' and r['sid']==sid and '2025-05-09'<=r['at'][:10]<='2025-06-27'];p=pd.Series({pd.Timestamp(r['at'][:10]):r['old_P'] for r in logs})
 c=pd.read_csv(root/'analysis/campaigns.csv');q=c[c.policy.isin(['SAMT','MCP'])&c.scenario.eq('base')&c.symbol.eq(sid)&c.entry_at.str.startswith('2025-05-09')]
 fig,ax=plt.subplots(2,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[3,1]});ax[0].plot(f.index,f.close,color='black',label='Actual close');ax[0].plot(f.index,f.i_floor,label='E0 floor',color='#9c9c9c');ax[0].plot(p.index,p.values,label='MCP effective protection (old P)',color='#e45520',linewidth=2)
 for _,r in q.iterrows():
  exit=pd.Timestamp(r.exit_at[:10]);color='#1756a9' if r.policy=='SAMT' else '#e45520';ax[0].axvline(exit,color=color,linestyle='--',label=f'{r.policy} actual next-open exit {exit.date()}, net {r.net_return:.2%}')
 ax[0].axvline(pd.Timestamp('2025-05-09'),color='green',linestyle=':',label='Both actual entries 2025-05-09');ax[0].set_title('688166.SH Borui: earlier exit and actual capital opportunity must be evaluated together');ax[0].legend(fontsize=9);ax[0].set_ylabel('Causal adjusted price')
 ax[1].bar(f.index,f.amount/1e8);ax[1].set_ylabel('Turnover CNY 100m');fig.tight_layout();fig.savefig(out/'borui-actual.png',dpi=135);plt.close(fig)
if __name__=='__main__':main()
