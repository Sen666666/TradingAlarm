"""Post-outcome descriptive case; no strategy or account execution."""
from fw_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def main():
 root=O/'DRUG/accounts-v2';out=O/'case-plots';out.mkdir(exist_ok=True);sid='688278.SH';start,end='2024-08-01','2024-12-01';records={};proof={}
 for mode in ['A3CP','A10CP']:
  obj=read(root/f'{mode}__S0_base.json');risk=[r for r in obj['audit_log'] if r['kind']=='risk_checkpoint'];z=next(r for r in obj['audit_log'] if r['kind']=='cp_start' and r['sid']==sid and r['entry_at'].startswith('2024-09-12'));cid=z['cycle_id'];check=[r for r in obj['audit_log'] if r['kind']=='cp_checkpoint' and r['cycle_id']==cid];sample=next(r for r in check if r['at'].startswith('2024-09-23'));riskday=next(r for r in risk if r['at'].startswith('2024-09-23'))
  records[mode]=dict(risk=risk,check=check);proof[mode]=dict(risk=riskday,cp=sample)
 a,b=proof['A3CP'],proof['A10CP'];assert a['cp']['old_P']==b['cp']['old_P'] and a['cp']['close']>a['cp']['old_P'];assert a['risk']['on'] and not b['risk']['on'] and b['cp']['reason']=='ACT'
 fig,axes=plt.subplots(3,1,figsize=(14,11),sharex=True)
 for mode,color in [('A3CP','#2573a9'),('A10CP','#dc7923')]:
  f=pd.DataFrame(records[mode]['risk']);f.index=pd.to_datetime(f['at'].str[:10]);f=f.loc[start:end]
  axes[0].plot(f.index,f.nav.astype(float)/1e6,label=LABELS[mode],color=color);axes[1].plot(f.index,f.episode_drawdown.astype(float)*100,label=LABELS[mode],color=color)
  p=pd.Series({pd.Timestamp(r['at'][:10]):r['old_P'] for r in records[mode]['check']});axes[2].plot(p.index,p,color=color,label=LABELS[mode]+' effective CP protection')
 raw=pd.read_parquet(PREPS['DRUG']/'facts'/f'{sid}.parquet').loc[start:end];axes[2].plot(raw.index,raw.close,color='black',label='688278.SH actual close')
 for ax in axes:
  ax.axvline(pd.Timestamp('2024-09-23'),color='red',linestyle=':',label='2024-09-23 A10CP account pause');ax.legend(fontsize=8)
 axes[1].axhline(20,color='red',linestyle='--');axes[0].set_ylabel('NAV (CNY million)');axes[1].set_ylabel('ACT episode drawdown (%)');axes[2].set_ylabel('Causal adjusted price');axes[0].set_title('Same entry and same stock protection, different portfolio paths trigger different exits')
 fig.tight_layout();fig.savefig(out/'drug-w3-w10-account-path.png',dpi=130);plt.close(fig)
 save(O/'case-evidence.json',dict(selected_after_outcome=True,not_strategy_input=True,security_id=sid,date='2024-09-23',proof=proof,interpretation='特宝当日收盘高于两组相同CP旧保护，A10CP因整户ACT暂停而退出，A3CP未退出。不能把它误归因为CP阈值不同；不是对所有同股都排除CP触线，三生同日两组也触CP。'))
if __name__=='__main__':main()
