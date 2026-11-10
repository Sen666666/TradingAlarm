"""Post-account trajectory review and repeatable prefix check; unique destination."""
import argparse
from pv_impact_sector import *

def main(src,out):
    out.mkdir(exist_ok=False);etfs,_=load_extended();hk,_=load_assets();stocks={s:hk[s] for s in ['HK00700','HK03690','HK09618']};etf=etfs['HK03033'];cut=pd.Timestamp('2024-12-31')
    def trim(a):return dict(a,signal=a['signal'].loc[:cut],raw=a['raw'].loc[:cut])
    gate,targets,events,frame=make_targets(etf,stocks,True,'top2');g,t,e,f=make_targets(trim(etf),{s:trim(a) for s,a in stocks.items()},True,'top2')
    pd.testing.assert_series_equal(gate.loc[:cut],g)
    for s in stocks:pd.testing.assert_series_equal(targets[s].loc[:cut],t[s])
    assert [x for x in events if x['date']<='2024-12-31']==e
    write(out/'prefix.json',dict(cut=str(cut.date()),gate=True,targets=True,selections=True))
    rows=[]
    for kind in ['etf','all3','top2']:
        for ep in json.loads((src/f'volume-{kind}-base-episodes.json').read_text()):rows.append(dict(implementation=kind,**ep))
    pd.DataFrame(rows).to_csv(out/'reviewed-episodes.csv',index=False)
    fig,axes=plt.subplots(4,1,figsize=(13,10),sharex=True)
    for s,a in stocks.items():
        f=pairwise_frame(a['signal'].close,volume(a),joint=True);c=a['signal'].close.loc['2024-12-01':'2025-04-15']
        axes[0].plot(c.index,c/c.iloc[0],label=s);axes[1].plot(c.index,f.strength.reindex(c.index),label=s)
        axes[2].plot(c.index,volume(a).reindex(c.index)/volume(a).rolling(63).median().reindex(c.index),label=s)
    orders=json.loads((src/'volume-top2-base-orders.json').read_text())
    for s in stocks:
        p=targets[s].loc['2024-12-01':'2025-04-15'];axes[3].step(p.index,p,label=s,where='post')
    for ax in axes:
        ax.axvline(pd.Timestamp('2025-01-21'),ls=':',color='black');ax.legend(loc='upper left',fontsize=8)
    axes[0].set_ylabel('Normalized close');axes[1].set_ylabel('Own PV strength');axes[2].set_ylabel('Relative volume');axes[3].set_ylabel('Top2 target')
    for o in orders:
        day=pd.Timestamp(o['date'])
        if pd.Timestamp('2024-12-01')<=day<=pd.Timestamp('2025-04-15'):axes[3].axvline(day,color='gray',alpha=.3)
    axes[0].set_title('Post-result review: entry rank missed Tencent tail; dotted=signal, gray=fills');fig.tight_layout();fig.savefig(out/'missed-tail.png',dpi=130);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source,a.output)
