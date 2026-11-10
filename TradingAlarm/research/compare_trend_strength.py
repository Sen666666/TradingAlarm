"""Matched-date model comparison; no thresholds selected or traded."""
import argparse,json
import pandas as pd
from build_stock_features import ROOT


def main(output):
    out=ROOT/'results'/output;current=pd.read_parquet(out/'strength-observations.parquet');old=pd.read_parquet(ROOT/'results/trend-strength-v1/strength-observations.parquet');rows=[]
    keys=['symbol','model','date'];a=old.set_index(keys).sort_index();b=current.set_index(keys).sort_index();pd.testing.assert_index_equal(a.index,b.index)
    for col in ('forward5','forward21'):pd.testing.assert_series_equal(a[col],b[col],check_exact=True)
    for model in ('price_only','price_volume'):
        for year in (2024,2025,2026):
            for horizon in (5,21):
                parts={}
                for label,t in [('constant',old),('candidate',current)]:
                    g=t[t.model.eq(model)&t.year.eq(year)].dropna(subset=['bin',f'forward{horizon}'])
                    parts[label]=g.groupby(['date','bin'])[f'forward{horizon}'].mean().unstack('bin').reindex(columns=['0-2','2-4','4-6','6-8','8-10']).dropna()
                dates=parts['constant'].index.intersection(parts['candidate'].index)
                result=dict(model=model,year=year,horizon=horizon,common_dates=len(dates))
                for label,part in parts.items():
                    m=part.loc[dates].mean();result[label]=dict(bin_means=m.to_dict(),top_minus_bottom=float(m.iloc[-1]-m.iloc[0]),strictly_increasing=bool(m.diff().iloc[1:].gt(0).all()))
                rows.append(result)
    (out/'matched-comparison.json').write_text(json.dumps(dict(reports=rows,labels_and_rows_exact=True,meaning='Withinmodel datebalancedbinmeans;comparisonusesdateintersection withall5binsavailable inbothmodels. Same instrument-date forwardlabels exactlyverified. Correlated/descriptive,notstatisticalsignificance ortradingreturns.'),indent=2)+'\n')
    for r in rows:
        if r['model']=='price_volume':print(r)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);main(p.parse_args().output)
