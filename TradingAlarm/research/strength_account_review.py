"""Frozen cross-market results, account paths and best hindsight rise bound."""
import json
from pathlib import Path
import pandas as pd
from workbench_period_report import describe
ROOT=Path(__file__).resolve().parent

def drawup(nav):
    # Initial cash included. This is a retrospective best pair, not an executable cycle rule.
    low=1.;low_date='initial_cash';best=0.;start=low_date;end=low_date
    for date,value in nav.items():
        if value<low:low=float(value);low_date=str(date.date())
        rise=float(value/low-1)
        if rise>best:best=rise;start=low_date;end=str(date.date())
    return {'max_hindsight_drawup':best,'start':start,'end':end}

def main():
    out=ROOT/'results/trend-strength-ah-transfer';rows=json.loads((out/'results.json').read_text());assert len(rows)==42
    verification=json.loads((out/'validation.json').read_text());assert verification['new_ledgers']==42 and verification['exact_controls']==6
    episodes={r['case']:r for r in json.loads((out/'episode-attribution.json').read_text())['results']}
    reviews=[]
    for r in rows:
        path=pd.read_parquet(out/f"{r['case']}-path.parquet");annual=describe(path);rise=drawup(path.nav)
        result={k:r[k] for k in ('case','group','strategy','scenario','total_return','max_drawdown','fees','orders','year2026')}
        result.update(rise);result['annual']=annual['years']
        result['sample_mdd_within20']=r['max_drawdown']>=-.2;result['any_hindsight_rise80']=rise['max_hindsight_drawup']>=.8
        if r['case'] in episodes:
            e=episodes[r['case']];result['hk_episodes']={k:e[k] for k in ('closed_count','open_count','closed_win_rate','average_win','average_loss','ordinary_all_bottom90','parent_closed_with_remaining_claims')}
        reviews.append(result)
    pairs=[]
    for r in rows:
        if not r['strategy'].startswith('adaptive_'):continue
        for prefix in ('','linear_'):
            name=prefix+r['strategy'].removeprefix('adaptive_');old=next(x for x in rows if x['strategy']==name and all(x[k]==r[k] for k in ('group','scenario')))
            pairs.append({'group':r['group'],'scenario':r['scenario'],'adaptive':r['strategy'],'control':name,'full_return_difference':r['total_return']-old['total_return'],'mdd_difference':r['max_drawdown']-old['max_drawdown'],'year2026_difference':r['year2026']['return_fraction']-old['year2026']['return_fraction']})
    (out/'account-review.json').write_text(json.dumps({'verification':verification,'reviews':reviews,'pairs':pairs,'limits':'42 conditional selected-universe runs. Hindsight maxrise is an upper-bound existence diagnostic; not a predefined marketcycle, target-achievement claim or deployable entry/exit. Below80 rules out80 in this path; above80 does not validate future cycles. Bottom90 PNL removes hindsight winners only, not executable selection.'},indent=2)+'\n')
    for r in reviews:
        if r['scenario']=='base' and r['strategy']!='short21':print({k:v for k,v in r.items() if k not in ('annual','year2026','hk_episodes')},'2026',r['year2026']['return_fraction'],flush=True)
if __name__=='__main__':main()
