import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import trend_competing_state as model
import stock_actions

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(root,out):
    assert not (out/'behavior-summary.json').exists()
    selected=json.loads((out/'selected-for-review.json').read_text());cohort=root/'data/ths-refresh-20261018/validated-input-balanced-second500.json';records={r['symbol']:r for r in json.loads(cohort.read_text())['records']};inputs={str(cohort):sha(cohort)};summary=[]
    for case in selected:
        if case.get('missing'):continue
        s=case['symbol'];rec=records[s];base=cohort.parent;code=rec['ths_symbol'];paths={'signal':base/f'{code}-signal.parquet','history':base/f'ths-raw/{code}.json','rights':base/f'rights/{code}.json'}
        for kind,p in paths.items():inputs[str(p)]=sha(p);assert inputs[str(p)]==rec[kind+'_sha256']
        z=pd.read_parquet(paths['signal']);v=z.volume.copy();factor=pd.Series(1.,index=z.index)
        for r in json.loads(paths['rights'].read_text())['records']:
            t=pd.to_datetime(str(r['1']),format='%Y%m%d')
            if not z.index.min()<t<=z.index.max():continue
            e=stock_actions.parse_ths_rights(code,r);ratio=1+e['bonus_shares_per_old_share']+e['capitalization_shares_per_old_share']
            if ratio!=1 and t in factor.index:factor.loc[t:]*=ratio
        v=v/factor;good=z.signal_close.gt(0)&v.gt(0)&np.isfinite(z.signal_close)&np.isfinite(v);c=z.signal_close.loc[good];v=v.loc[good]
        f=model.competing_frame(c,v);f['target']=model.exposure(f.strength);f['price_strength']=model.competing_frame(c,v,joint=False).strength;f['price_target']=model.exposure(f.price_strength);f['sma63_target']=(c>c.rolling(63).mean()).astype(float);f['close']=c;f['volume']=v
        cutoff=str(case['year'])+'-06-30';prefix=c.loc[:cutoff];pf=model.competing_frame(prefix,v.reindex(prefix.index));pd.testing.assert_frame_equal(pf,f.loc[prefix.index,pf.columns]);pd.testing.assert_series_equal(model.exposure(pf.strength),f.target.loc[prefix.index])
        d=f.loc[str(case['year'])+'-01-01':str(case['year'])+'-12-31'];f.to_csv(out/f"{case['id']}-full-history.csv",index_label='date')
        rows={}
        for col in ['target','price_target','sma63_target']:
            a=d[col];runs=a.groupby(a.ne(a.shift()).cumsum()).agg(['first','size']);rows[col]=dict(entries=int(f[col].diff().loc[d.index].eq(1).sum()),exits=int(f[col].diff().loc[d.index].eq(-1).sum()),duty=float(a.mean()),max_active_run=int(runs.loc[runs['first'].eq(1),'size'].max()) if a.any() else 0)
        row=dict(id=case['id'],symbol=s,year=int(case['year']),price_return=float(d.close.iloc[-1]/d.close.iloc[0]-1),price_drawdown=float((d.close/d.close.cummax()-1).min()),volume_changed_target_days=int(d.target.ne(d.price_target).sum()),models=rows,prefix_check_date=str(prefix.index[-1].date()),source_excluded_rows=int((~good).sum()),execution='none; signals only, not account performance')
        summary.append(row)
        fig,ax=plt.subplots(4,1,figsize=(11,8),sharex=True);ax[0].plot(d.index,d.close,color='black');ax[0].set_yscale('log');ax[0].set_title(f"{case['id']} {s} {case['year']} | A-stock signal-only development review");ax[1].bar(d.index,d.volume,color='gray');ax[1].set_ylabel('Adjusted volume');ax[2].plot(d.index,d.strength,label='PV');ax[2].plot(d.index,d.price_strength,label='price',alpha=.65);ax[2].axhline(1,color='gray',ls=':');ax[2].axhline(0,color='black',lw=.6);ax[2].legend()
        for col in rows:ax[3].step(d.index,d[col],where='post',label=col,alpha=.65)
        ax[3].legend(ncol=3,fontsize=8);fig.tight_layout();fig.savefig(out/f"{case['id']}-review.png",dpi=110);plt.close(fig)
    (out/'behavior-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n');(out/'review-manifest.json').write_text(json.dumps({'inputs':inputs,'code':{str(p):sha(p) for p in [Path(__file__).resolve(),Path(model.__file__),Path(stock_actions.__file__)]},'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.root,a.out)
