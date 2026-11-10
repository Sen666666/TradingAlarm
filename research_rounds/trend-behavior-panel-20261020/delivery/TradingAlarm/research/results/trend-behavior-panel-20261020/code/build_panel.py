import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main(source, out):
    assert not (out/'summary.json').exists()
    assert digest(out/'protocol.json') == json.loads((out/'freeze.json').read_text())['sha256']
    protocol=json.loads((out/'protocol.json').read_text())
    inputs={}; rows=[]
    def read(p, kind):
        inputs[str(p)]=digest(p)
        if kind=='csv': return pd.read_csv(p,index_col='date',parse_dates=True)
        if kind=='parquet': return pd.read_parquet(p)
        return json.loads(p.read_text())
    for case in protocol['cases']:
        key,s,g=case['id'],case['symbol'],case['group']
        f=read(source/f'{s}-signals.csv','csv')
        f['sma63_target']=(f.close>f.close.rolling(63).mean()).astype(float)
        p=read(source/f'{g}-pv-base-path.parquet','parquet')
        orders=read(source/f'{g}-pv-base-orders.json','json')
        episodes=read(source/f'{g}-pv-base-episodes.json','json')
        d=f.loc[case['start']:case['end']].copy()
        assert len(d)>40 and d.index.is_monotonic_increasing
        cut=f.loc[:case['checkpoint']]; cp=cut.iloc[-1]; c=cut.close
        past_volume=cut.volume.iloc[-21:-1].median()
        snap={'asof':str(cut.index[-1].date()),'close':float(c.iloc[-1]),'return21':float(c.iloc[-1]/c.iloc[-22]-1), 'return63':float(c.iloc[-1]/c.iloc[-64]-1),'drawdown_from_past63_high':float(c.iloc[-1]/c.iloc[-63:].max()-1),'volume_vs_prior20median':float(cut.volume.iloc[-1]/past_volume),'pv_strength':float(cp.strength),'pv_target':float(cp.target),'price_target':float(cp.price_target),'sma63_target':float(cp.sma63_target)}
        selected_orders=[o for o in orders if o['symbol']==s and case['start']<=o['date']<=case['end']]
        selected_ep=[e for e in episodes if e['symbol']==s and e['entry']<=case['end'] and (not e.get('exit') or e['exit']>=case['start'])]
        actual=p.loc[case['start']:case['end'],'w_'+s]
        row={**case,'observations':len(d),'window_price_return':float(d.close.iloc[-1]/d.close.iloc[0]-1),'window_price_max_drawdown':float((d.close/d.close.cummax()-1).min()),'mean_actual_weight':float(actual.mean()),'max_actual_weight':float(actual.max()),'checkpoint_facts':snap,'orders':len(selected_orders),'overlapping_episodes_full_cycle':selected_ep}
        for col in ['target','price_target','sma63_target']:
            changes=f[col].diff().loc[d.index]
            row[col]={'entries':int(changes.eq(1).sum()),'exits':int(changes.eq(-1).sum()),'duty':float(d[col].mean()),'already_active_at_start':bool(d[col].iloc[0])}
        d.to_csv(out/f'{key}-trajectory.csv',index_label='date')
        (out/f'{key}-orders.json').write_text(json.dumps(selected_orders,indent=2)+'\n')
        for prefix in [False,True]:
            plot=d.loc[:case['checkpoint']] if prefix else d
            fig,axs=plt.subplots(3,1,figsize=(10,7),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
            axs[0].plot(plot.index,plot.close,color='black');axs[0].set_yscale('log')
            axs[0].set_title(f'{key} {s}: {case["intent"]} | '+('PREFIX (retrospective)' if prefix else 'FULL DEVELOPMENT PATH'))
            for o in selected_orders:
                t=pd.Timestamp(o['date'])
                if t in plot.index:
                    axs[0].scatter(t,plot.loc[t,'close'],color='green' if o['units']>0 else 'red',marker='^' if o['units']>0 else 'v',s=25)
            axs[0].set_ylabel('Signal price, log axis')
            axs[1].bar(plot.index,plot.volume,color='gray',width=1.7)
            axs[1].set_ylabel('Split-adjusted volume')
            for col,label in [('target','PV'),('price_target','price ablation'),('sma63_target','SMA63')]:
                axs[2].step(plot.index,plot[col],where='post',label=label,alpha=.7)
            w=actual.reindex(plot.index)
            axs[2].plot(plot.index,w,label='actual PV NAV weight',color='black')
            axs[2].legend(loc='upper left',fontsize=8,ncol=4)
            if not prefix:
                for ax in axs:ax.axvline(pd.Timestamp(snap['asof']),color='blue',ls=':',lw=.8)
            axs[2].set_ylim(-.05,1.2)
            fig.text(.02,.01,'Triangles: saved execution dates on signal close, NOT fill prices. Targets are not filled weights.',fontsize=8)
            fig.tight_layout(rect=[0,.025,1,1])
            fig.savefig(out/f'{key}-{"prefix" if prefix else "full"}.png',dpi=110);plt.close(fig)
        rows.append(row)
    (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    flat=[{k:v for k,v in r.items() if not isinstance(v,(list,dict))} | {f'{m}_{k}':v for m in ['target','price_target','sma63_target'] for k,v in r[m].items()} for r in rows]
    pd.DataFrame(flat).to_csv(out/'summary.csv',index=False)
    manifest={'source_code':{str(Path(__file__).resolve()):digest(Path(__file__))},'inputs':inputs,'outputs':{p.name:digest(p) for p in out.iterdir() if p.is_file()},'scope':'post-run evidence hash, not historical unseen proof'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(flat)[['id','symbol','window_price_return','target_entries','target_duty','mean_actual_weight']].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source,a.output)
