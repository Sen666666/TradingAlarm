"""Compare frozen model transfer without selecting a model or threshold."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    out=ROOT/'results/trend-strength-transfer485';protocol=json.loads((out/'protocol.json').read_text())
    for f,h in protocol['source_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    current=json.loads((out/'sleeve-report.json').read_text())['rows'];tail=json.loads((out/'tail-economics.json').read_text())['reports']
    source={'geometry_price':'trend-strength-v4-trades','geometry_price_volume':'trend-strength-v4-trades','linear_geometry_price':'trend-strength-linear-control','linear_geometry_price_volume':'trend-strength-linear-control','adaptive_geometry_price':'trend-strength-adaptive','adaptive_geometry_price_volume':'trend-strength-adaptive'}
    comparisons=[]
    for r in current:
        if r['cutoff']!='2026-10-16':continue
        folder=ROOT/'results'/source[r['strategy']]
        old=json.loads((folder/'sleeve-report.json').read_text())['rows']
        a=next(x for x in old if all(x[k]==r[k] for k in ('strategy','allocation','scenario','cost','terminal','cutoff')))
        comparisons.append({k:r[k] for k in ('strategy','allocation','scenario','cost','terminal')}|{'development_full':a['equal_initial_sleeve_return'],'transfer_full':r['equal_initial_sleeve_return'],'development_2026':a['year2026_carry_return'],'transfer_2026':r['year2026_carry_return']})
    model_pairs=[]
    for a in current:
        if not a['strategy'].startswith('adaptive_') or a['cutoff']!='2026-10-16':continue
        for prefix in ('','linear_'):
            target=prefix+a['strategy'].removeprefix('adaptive_')
            b=next(x for x in current if x['strategy']==target and all(x[k]==a[k] for k in ('allocation','scenario','cost','terminal','cutoff')))
            model_pairs.append({k:a[k] for k in ('strategy','allocation','scenario','cost','terminal')}|{'control':target,'adaptive_full':a['equal_initial_sleeve_return'],'control_full':b['equal_initial_sleeve_return'],'difference':a['equal_initial_sleeve_return']-b['equal_initial_sleeve_return']})
    summary={'source_hashes_unchanged':True,'comparisons':comparisons,'model_pairs':model_pairs,'adaptive_better_full_cases':sum(x['difference']>0 for x in model_pairs),'model_pair_cases':len(model_pairs),'tail_reports':tail,'limits':'Shared market dates and cross-stock dependence; disjoint names not temporal independence. Synthetic fractional sleeves and incomplete PIT/execution certification. No new thresholds or board selection.'}
    (out/'transfer-comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
    for r in comparisons:
        if r['allocation']=='equal_capital' and r['scenario']=='base' and r['cost']==15 and r['terminal']=='last_mark':print(r)
    print('adaptive better',summary['adaptive_better_full_cases'],'/',summary['model_pair_cases'])
if __name__=='__main__':main()
