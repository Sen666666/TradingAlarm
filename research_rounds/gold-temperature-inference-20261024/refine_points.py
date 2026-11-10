"""Refine geometric centers with each marker's observed vertical price coordinate.

This is measurement, not signal optimization. Original target bands retained;
printed dates fixed, source-index identity and price basis remain uncertain.
"""
from pathlib import Path
import json,numpy as np,pandas as pd,datetime
HERE=Path(__file__).resolve().parent;PRIOR=HERE.parent/'gold-chart-fit-20261024'
def main():
    old=json.loads((PRIOR/'targets.json').read_text());d=pd.read_csv(PRIOR/'data/sina-AU0.csv',index_col='date',parse_dates=True).loc['2025':]
    a=old['alignment']['pixels_per_observation'];b=old['alignment']['x_intercept'];yi=old['alignment']['y_intercept'];ys=old['alignment']['logprice_slope']
    rows=[];points=[]
    for p in old['points']:
        candidates=[]
        for n in range(max(0,p['index']-p['uncertainty_observations']),min(len(d),p['index']+p['uncertainty_observations']+1)):
            xerr=(b+a*n)-p['x'];yerr=(yi+ys*np.log(d.close.iloc[n]))-p['y']
            score=(xerr/(3*a))**2+(yerr/12)**2
            row=dict(id=p['id'],candidate_date=str(d.index[n].date()),index=n,x_error_pixels=float(xerr),y_error_pixels=float(yerr),measurement_cost=float(score));candidates.append(row);rows.append(row)
        chosen=min(candidates,key=lambda r:r['measurement_cost']);new=dict(p,old_geometric_date=p['date'],date=chosen['candidate_date'],index=chosen['index'],refinement='Observed marker y and raw curve, within old uncertainty band; no algorithm signal used',measurement_cost=chosen['measurement_cost'])
        points.append(new)
    pd.DataFrame(rows).to_csv(HERE/'marker-date-candidates.csv',index=False)
    info=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),points=points,original_alignment=old['alignment'],criterion='Squared x error / (3*1.836)^2 plus squared vertical price residual/12^2. 12 pixels approximates existing curve residual90th percentile. Printed dates fixed; no point leaves old date band.',limitations=['Marker vertical coordinate resolves sharp daily jumps better than x alone. Price calibration remains a proxy; dates are still estimates.','Previous Apr22 and Feb02 centers were x-only estimates with +/-3-observation bands; do not treat their one-day refinement as a changed signal or recovered timestamp.'])
    (HERE/'refined-targets.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(points)[['id','old_geometric_date','date','earliest','latest']].to_string(index=False))
if __name__=='__main__':main()
