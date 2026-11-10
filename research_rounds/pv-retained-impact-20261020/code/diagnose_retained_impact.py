"""Frozen trajectory checks. No account ranking before this review."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from trend_retained_impact import retained_frame,exposure
from run_pv_segment_round import assets,volume,manifest

def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def main(out):
    protocol=json.loads((out/'protocol.json').read_text());assert hashlib.sha256((out/'protocol.json').read_bytes()).hexdigest()==json.loads((out/'freeze.json').read_text())['sha256'];assert hashlib.sha256(Path(__file__).with_name('trend_retained_impact.py').read_bytes()).hexdigest()==protocol['code_sha256']
    assert not (out/'validation.json').exists()
    ix=pd.bdate_range('2020-01-01',periods=230);warm=.001*np.sin(np.arange(100)*2*np.pi/10);paths={}
    paths['drift']=np.r_[warm,np.arange(130)*.002]
    paths['bounded_range']=np.r_[warm,.03*np.sin(np.arange(130)*2*np.pi/10)]
    paths['jump_plateau']=np.r_[warm,np.full(130,.08)]
    common=np.r_[warm,np.arange(40)*.002,np.linspace(.078,.048,10)]
    paths['pullback_recovery']=np.r_[common,np.linspace(.051,.20,80)]
    paths['persistent_reversal']=np.r_[common,np.linspace(.045,-.15,80)]
    summary=[];frames={};fig,axs=plt.subplots(3,1,figsize=(12,9),sharex=True)
    for name,y in paths.items():
        c=pd.Series(np.exp(y),index=ix);v=pd.Series(100.,index=ix);v.iloc[100:105]=800.
        f=retained_frame(c,v);f['target']=exposure(f.strength);f['close']=c;f['volume']=v;f['price_strength']=retained_frame(c,v,joint=False).strength;frames[name]=f
        f.to_csv(out/f'synthetic-{name}.csv',index_label='date')
        for cut in [150,190]:pd.testing.assert_frame_equal(retained_frame(c[:cut],v[:cut]),f.drop(columns=['target','close','volume','price_strength']).iloc[:cut])
        np.testing.assert_allclose(retained_frame(c*100,v*1000),f[['strength','positive_retained','negative_retained','normalizer','retained_mass']],rtol=1e-8,atol=1e-10,equal_nan=True)
        np.testing.assert_allclose(retained_frame(1/c,v).strength,-f.strength,rtol=1e-8,atol=1e-10,equal_nan=True)
        changes=f.target.diff().fillna(0);summary.append(dict(case=name,max_strength=float(f.strength.max()),min_strength=float(f.strength.min()),entry_count=int(changes.iloc[100:].eq(1).sum()),held_sessions=int(f.target.iloc[100:].sum()),last_strength=float(f.strength.iloc[-1]),price_volume_target_different=int(f.target.ne(exposure(f.price_strength)).sum())))
        axs[0].plot(ix,c,label=name);axs[1].plot(ix,f.strength,label=name);axs[2].plot(ix,f.target,label=name,alpha=.7)
    pd.testing.assert_frame_equal(frames['pullback_recovery'].iloc[:150],frames['persistent_reversal'].iloc[:150])
    axs[0].set_ylabel('Price');axs[1].set_ylabel('Retained impact');axs[2].set_ylabel('Target');axs[1].axhline(1,color='black',ls=':');axs[1].axhline(0,color='black',lw=.5)
    for ax in axs:ax.legend(fontsize=7,ncol=3)
    fig.tight_layout();fig.savefig(out/'synthetic-trajectories.png',dpi=130);plt.close(fig)
    groups,audit=assets();checks=[]
    for group,items in groups.items():
        for s,a in items.items():
            c=a['signal'].close;v=volume(a);f=retained_frame(c,v);f['target']=exposure(f.strength);f['price_strength']=retained_frame(c,v,joint=False).strength;f['price_target']=exposure(f.price_strength);f['close']=c;f['volume']=v
            for cut in [len(c)//2,len(c)-50]:pd.testing.assert_frame_equal(retained_frame(c.iloc[:cut],v.iloc[:cut]),f[['strength','positive_retained','negative_retained','normalizer','retained_mass']].iloc[:cut])
            f.to_csv(out/f'{s}-signals.csv',index_label='date');checks.append(dict(group=group,symbol=s,rows=len(f),entries=int(f.target.diff().fillna(0).eq(1).sum()),volume_price_target_different=int(f.target.ne(f.price_target).sum())))
            if any(s==x[0] for x in protocol['cases']):
                case=next(x for x in protocol['cases'] if s==x[0]);d=f.loc[case[1]:case[2]];fig,ax=plt.subplots(4,1,figsize=(12,9),sharex=True)
                ax[0].plot(d.index,d.close,color='black');ax[0].set_title(s+' retained impact, historical development');ax[1].bar(d.index,d.volume,color='gray');ax[2].plot(d.index,d.strength,label='PV');ax[2].plot(d.index,d.price_strength,label='Price');ax[2].axhline(1,ls=':',color='black');ax[2].axhline(0,color='black',lw=.5);ax[2].legend();ax[3].step(d.index,d.target,where='post',label='PV target');ax[3].legend();fig.tight_layout();fig.savefig(out/f'{s}-trajectory.png',dpi=130);plt.close(fig)
    # Illustrate repeated overlapping displacement counted as independent retained mass.
    overlap=[]
    for n in [1,3,6]:
        y=np.r_[np.zeros(100),np.zeros(63-2*n+1),np.tile([.03,0.],n-1),[.03],np.zeros(0)]
        c=pd.Series(np.exp(y));f=retained_frame(c,pd.Series(100.,index=c.index));row=f.iloc[-1]
        overlap.append(dict(up_traversals=n,current_log_displacement=.03,positive_retained=float(row.positive_retained),strength=float(row.strength)))
    write(out/'validation.json',dict(synthetic=summary,synthetic_prefix_checks=10,real_prefix_checks=48,scale_invariance=True,sign_symmetry=True,shared_prefix=True,assets=checks,overlap_counterexample=overlap,accounts_run=False));manifest(out,'trajectory');print(json.dumps(dict(synthetic=summary,overlap=overlap),indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
