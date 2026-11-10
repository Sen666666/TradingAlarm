"""Compute one G1 candidate and causal policy states; no accounts."""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from g1util import *
from grade import classify,LABELS,COLORS
from policies_g1 import project,e0_adapter,initial

FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
def main():
    out=HERE/'grading';out.mkdir(exist_ok=False);(out/'figures').mkdir();(HERE/'prepared').mkdir()
    cases=read(HERE/'cases.json');summary=[];full={}
    for p in sorted((HERE/'inputs').glob('*.parquet')):
        symbol=p.stem;d=pd.read_parquet(p);e=pd.read_parquet(HERE/'replay'/f'{symbol}-evidence.parquet');b=pd.read_parquet(HERE/'replay'/f'{symbol}-E0.parquet')
        g,ev=classify(e);g.to_parquet(out/f'{symbol}.parquet');write(out/f'{symbol}-events.json',ev)
        states={'E0':e0_adapter(b)}
        for policy in POLICIES[1:]:states[policy]=project(e,b,g,policy)
        for policy,s in states.items():s.to_parquet(out/f'{symbol}-{policy}.parquet')
        for case in [x for x in cases if x['symbol']==symbol]:
            z=d.loc[case['start']:case['end']];a=g.loc[z.index];f=e.loc[z.index];s=b.loc[z.index]
            folder=HERE/'prepared'/case['id'];folder.mkdir();ini={}
            for policy,st in states.items():
                st.loc[z.index].to_parquet(folder/f'{policy}.parquet');ini[policy]=initial(d,st,g,case['start'],policy)
            old_initial=read(OLD/'prepared'/case['id']/'initial.json')['E0']
            assert ini['E0']['active']==old_initial['active'] and ini['E0']['previous_close']==old_initial['previous_close']
            if ini['E0']['active']:assert ini['E0']['floor']==old_initial['floor']
            else:assert ini['E0']['floor'] is None and not np.isfinite(old_initial['floor'])
            write(folder/'initial.json',ini)
            summary.append(dict(case=case['id'],symbol=symbol,role=case['role'],rows=len(a),upgrades=int(a.transition.eq('upgrade').sum()),downgrades=int(a.transition.eq('downgrade').sum()),blocked_upgrades=int(a.promotion_blocked.sum()),freeze_days=int(a.acute_down.sum()),warm_days=int(a.grade.ge(2).sum()),cold_days=int(a.grade.le(-2).sum()),**{f'grade_{k}':int(v) for k,v in a.grade.value_counts().items()}))
            fig,axs=plt.subplots(5,1,figsize=(14,10),sharex=True,gridspec_kw={'height_ratios':[3,1,1.7,1.1,1.2]})
            axs[0].plot(z.index,z.close,color='#222d3c',lw=.9);axs[0].scatter(z.index,z.close,c=[COLORS[int(x)] for x in a.grade],s=9,zorder=3)
            axs[0].set_title(case['id']+' '+case['name']+'：B5-G1证据等级与E0资格（账户前图检）',fontproperties=FONT)
            axs[0].scatter(z.index[s.entered.eq(1)],z.loc[s.entered.eq(1),'close'],marker='^',s=35,facecolors='none',edgecolors='green',label='E0 enter');axs[0].scatter(z.index[s.exited.eq(1)],z.loc[s.exited.eq(1),'close'],marker='v',s=35,facecolors='none',edgecolors='red',label='E0 exit');axs[0].legend(fontsize=7)
            axs[1].bar(z.index,f.strength_activity,color='#9099a4',width=1);axs[1].set_ylabel('relative volume')
            axs[2].step(z.index,a.score,where='post',color='#b1692c',lw=1,label='G1 score');axs[2].plot(z.index,a.proposal*25,color='gray',lw=.4,alpha=.5,label='proposal before evidence lock')
            for y in [-50,0,50,75]:axs[2].axhline(y,color='gray',lw=.4,ls='--')
            mask=a.acute_down;axs[2].scatter(z.index[mask],a.loc[mask,'score'],marker='x',color='red',s=24,label='freeze (acute event)');axs[2].set_ylim(-85,110);axs[2].legend(fontsize=7,ncol=3)
            axs[3].plot(z.index,a.z5,label='z5',alpha=.6,lw=.6);axs[3].plot(z.index,a.z21,label='z21',lw=.8);axs[3].axhline(0,color='gray',lw=.4);axs[3].legend(fontsize=7,ncol=2)
            for j,policy in enumerate(POLICIES):axs[4].step(z.index,states[policy].loc[z.index,'target']*.6+j,where='post',label=policy,lw=.7)
            axs[4].set_yticks(range(4),POLICIES);axs[4].set_ylabel('eligibility')
            for ax in axs:ax.grid(alpha=.15)
            fig.tight_layout();fig.savefig(out/'figures'/f"{case['id']}.png",dpi=110);plt.close(fig)
        full[symbol]=dict(rows=len(d),events=len(ev),unjustified_upgrades=int(((g.transition=='upgrade')&~g.fresh_up).sum()))
    pd.DataFrame(summary).to_csv(out/'diagnostics.csv',index=False)
    write(out/'manifest.json',dict(recorded_at=now(),series=full,accounts=0,candidate_count=1,changes_after_economic_results=0))
    print(pd.DataFrame(summary)[['case','rows','upgrades','downgrades','blocked_upgrades','freeze_days','warm_days','cold_days']].to_string(index=False),flush=True)

if __name__=='__main__':main()
