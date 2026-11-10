"""Only raw price/volume and frozen B5; no grade or account import."""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from g1util import HERE,ROOT,OLD,sha,read,write,now,b5,old_hashes,verify_hashes

FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')

def main():
    out=HERE/'replay';out.mkdir(exist_ok=False)
    (HERE/'inputs').mkdir();(out/'figures').mkdir()
    identities=old_hashes();verify_hashes(identities)
    write(HERE/'old-identity-before.json',dict(recorded_at=now(),sha256=identities))
    cases=read(OLD/'cases.json')
    assert [x for x in cases if x['role']=='fixed_scenario']==read(ROOT/'research_rounds/fixed-scenarios-v1/cases.json')
    write(HERE/'cases.json',cases)
    registry=read(ROOT/'research_rounds/fixed-scenarios-v1/manifest.json')
    api=b5();records=[];diagnostics=[]
    for symbol,rec in registry['data_snapshot'].items():
        source=ROOT/rec['path'];assert sha(source)==rec['sha256']
        d=pd.read_parquet(source)
        f=d[['open','high','low','close','volume']].copy()
        f['segment_id']=0;f['valid_price_observation']=True
        f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
        assert f.valid_strength_observation.all()
        f.to_parquet(HERE/'inputs'/f'{symbol}.parquet')
        result=api.run_b5(f,enhancements=False);ev=result['evidence'];state=result['state']
        ev.to_parquet(out/f'{symbol}-evidence.parquet');state.to_parquet(out/f'{symbol}-E0.parquet')
        write(out/f'{symbol}-journal.json',result['journal'])
        # This compares the policy, not the old numeric kernel's embedded target.
        original=pd.read_parquet(OLD/'contexts'/symbol/'shadow-E0.parquet')
        for c in ['target','entered','exited','floor','pending','pending_lower','pending_reclaim']:
            np.testing.assert_array_equal(state[c].to_numpy(dtype=float,na_value=np.nan),original[c].to_numpy(dtype=float,na_value=np.nan))
        records.append(dict(symbol=symbol,rows=len(f),source=rec,input_sha256=sha(HERE/'inputs'/f'{symbol}.parquet'),state_identity=True))
        for case in [c for c in cases if c['symbol']==symbol]:
            z=ev.loc[case['start']:case['end']];s=state.loc[z.index]
            a=z.strength_mu21.to_numpy(float);s21=z.strength_S21.to_numpy(float);s63=z.strength_S63.to_numpy(float)
            diagnostics.append(dict(case=case['id'],rows=len(z),mu21_negative=int((a<0).sum()),both_up_negative_pace=int(((s21==1)&(s63==1)&(a<0)).sum()),acute_down=int(z.strength_acute_down.sum()),acute_up=int(z.strength_acute_up.sum()),e0_entries=int(s.entered.sum()),e0_exits=int(s.exited.sum()),**{f'phase_{k}':int(v) for k,v in z.strength_phase.value_counts().items()}))
            if case['role']!='fixed_scenario':continue
            fig,axs=plt.subplots(4,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[3,1,1.5,1]})
            axs[0].plot(z.index,z.close,color='#262626',lw=1);axs[0].set_title(case['id']+' '+case['name']+'：原始量价与B5证据（无G1、无账户）',fontproperties=FONT)
            axs[0].scatter(z.index[s.entered.eq(1)],z.loc[s.entered.eq(1),'close'],marker='^',s=25,color='#2c9b5f',label='E0 eligibility enter')
            axs[0].scatter(z.index[s.exited.eq(1)],z.loc[s.exited.eq(1),'close'],marker='v',s=25,color='#c54b4b',label='E0 eligibility exit');axs[0].legend(fontsize=7)
            axs[1].bar(z.index,z.strength_activity,color='#9099a4',width=1);axs[1].axhline(1,color='gray',lw=.5);axs[1].set_ylabel('V / prior median')
            axs[2].plot(z.index,z.strength_mu5_bp,label='mu5 (bp/obs)',lw=.7,alpha=.65);axs[2].plot(z.index,z.strength_mu21_bp,label='mu21 (bp/obs)',lw=1);axs[2].axhline(0,color='gray',lw=.6);axs[2].legend(fontsize=7)
            axs[3].step(z.index,z.strength_S21,where='post',label='S21');axs[3].step(z.index,z.strength_S63,where='post',label='S63',alpha=.7)
            shock=z.strength_acute_down.eq(1);axs[3].scatter(z.index[shock],np.full(shock.sum(),-1.25),marker='x',color='red',s=15,label='acute down');axs[3].set_ylim(-1.5,1.4);axs[3].legend(fontsize=7,ncol=3)
            for ax in axs:ax.grid(alpha=.15)
            fig.tight_layout();fig.savefig(out/'figures'/f"{case['id']}.png",dpi=120);plt.close(fig)
    pd.DataFrame(diagnostics).to_csv(out/'diagnostics.csv',index=False)
    write(out/'manifest.json',dict(recorded_at=now(),records=records,cases=len(cases),main_cases=11,account_calls=0,grade_defined=False,network=0))
    print(pd.DataFrame(diagnostics).to_string(index=False),flush=True)

if __name__=='__main__':main()
