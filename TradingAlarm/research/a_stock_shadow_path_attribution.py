"""Account for sizing versus opportunity-path differences; not causal alpha proof."""
import json
import pandas as pd
from build_stock_features import ROOT


def campaigns(directory,case):
    data=json.loads((directory/f'{case}-campaigns.json').read_text())
    buys=[o for o in json.loads((directory/f'{case}-orders.json').read_text()) if o['side']=='buy']
    quantities={(o['symbol'],o['date']):o['quantity'] for o in buys}
    rows=[]
    for status in ('closed','open'):
        for r in data[status]:
            rows.append(dict(symbol=r['symbol'],entry_date=r['entry_date'],
                end_date=r.get('exit_date',r.get('mark_date')),status=status,pnl=r['pnl'],
                quantity=quantities[r['symbol'],r['entry_date']]))
    result=pd.DataFrame(rows)
    assert not result.duplicated(['symbol','entry_date']).any()
    return result


def compare(left,right):
    joined=left.merge(right,on=['symbol','entry_date'],how='outer',suffixes=('_partial','_full'),indicator=True)
    joined['pnl_difference']=joined.pnl_full.fillna(0)-joined.pnl_partial.fillna(0)
    joined['category']='same_entry_changed_exit_or_mark'
    joined.loc[joined._merge.eq('left_only'),'category']='partial_only_entry'
    joined.loc[joined._merge.eq('right_only'),'category']='full_only_entry'
    same=(joined._merge.eq('both')&joined.status_partial.eq(joined.status_full)&joined.end_date_partial.eq(joined.end_date_full))
    joined.loc[same,'category']='same_path_sizing'
    for _,r in joined.loc[same].iterrows():
        unit_partial=r.pnl_partial/r.quantity_partial;unit_full=r.pnl_full/r.quantity_full
        assert abs(unit_partial-unit_full)<1e-7*max(1.,abs(unit_partial))
        assert abs(r.pnl_difference-(r.quantity_full-r.quantity_partial)*unit_partial)<1e-6
    assert abs(joined.pnl_difference.sum()-(right.pnl.sum()-left.pnl.sum()))<1e-6
    return joined.drop(columns='_merge')


def compare_same_exit(left,right):
    """Pair overlapping holdings ending together, including one-day entry shifts.

    Symmetric decomposition avoids attributing an interaction entirely to size
    or price: delta(q*u) = delta(q)*mean(u) + delta(u)*mean(q).
    """
    keys=['symbol','end_date','status']
    assert not left.duplicated(keys).any() and not right.duplicated(keys).any()
    joined=left.merge(right,on=keys,how='outer',suffixes=('_partial','_full'),indicator=True)
    joined['pnl_difference']=joined.pnl_full.fillna(0)-joined.pnl_partial.fillna(0)
    joined['quantity_effect']=0.;joined['per_unit_effect']=0.;joined['unmatched_effect']=0.
    matched=joined._merge.eq('both')
    q0=joined.loc[matched,'quantity_partial'];q1=joined.loc[matched,'quantity_full']
    u0=joined.loc[matched,'pnl_partial']/q0;u1=joined.loc[matched,'pnl_full']/q1
    joined.loc[matched,'quantity_effect']=(q1-q0)*(u1+u0)/2
    joined.loc[matched,'per_unit_effect']=(u1-u0)*(q1+q0)/2
    joined.loc[~matched,'unmatched_effect']=joined.loc[~matched,'pnl_difference']
    error=joined.pnl_difference-joined.quantity_effect-joined.per_unit_effect-joined.unmatched_effect
    assert error.abs().max()<1e-6
    assert abs(joined.pnl_difference.sum()-(right.pnl.sum()-left.pnl.sum()))<1e-6
    return joined.drop(columns='_merge')


def main():
    out=ROOT/'results/a-stock-shadow-path-attribution';out.mkdir(exist_ok=True)
    left=ROOT/'results/a-stock-campaign-shadow';right=ROOT/'results/a-stock-campaign-shadow-fullrisk'
    summaries=[]
    for label in ('strength_all','lowvol_all','lowvol_best_quintile'):
        for cost in (15,30):
            case=f'{label}-{cost}';a=campaigns(left,case);b=campaigns(right,case);diff=compare(a,b)
            diff.to_parquet(out/f'{case}.parquet',index=False)
            overlap=compare_same_exit(a,b)
            overlap.to_parquet(out/f'{case}-same-exit.parquet',index=False)
            groups=diff.groupby('category').agg(count=('symbol','size'),pnl_difference=('pnl_difference','sum')).reset_index()
            symbols=diff.groupby('symbol').pnl_difference.sum().sort_values()
            summaries.append(dict(case=case,full_minus_partial=float(diff.pnl_difference.sum()),
                same_exit_decomposition={key:float(overlap[key].sum()) for key in ('quantity_effect','per_unit_effect','unmatched_effect')},
                groups=groups.to_dict('records'),largest_positive_symbol_contributions=symbols.tail(5).sort_values(ascending=False).to_dict(),
                largest_negative_symbol_contributions=symbols.head(5).to_dict()))
    result=dict(interpretation='Exact arithmetic attribution of full-risk minus partial-risk shadow PnL. Matched paths isolate quantity changes. Different entries are path selection effects,not evidence an asset could have been selected with hindsight. Openmarks remain unrealized. Do not sum symbols to claim independent trades.',cases=summaries)
    (out/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
