import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent

def main():
    out=ROOT/'results/strength-volume-units';r=json.loads((out/'results.json').read_text());v=json.loads((out/'validation.json').read_text());assert v['new_ledgers']==36 and v['exact_controls']==18
    pairs=[]
    for b in r:
        if not b['strategy'].endswith('_split_units'):continue
        a=next(x for x in r if x['strategy']==b['strategy'].removesuffix('_split_units') and all(x[k]==b[k] for k in ('group','scenario')))
        if b['group']=='hk7':
            pd.testing.assert_frame_equal(pd.read_parquet(out/f"{a['case']}-path.parquet"),pd.read_parquet(out/f"{b['case']}-path.parquet"),check_exact=True)
            assert json.loads((out/f"{a['case']}-orders.json").read_text())==json.loads((out/f"{b['case']}-orders.json").read_text())
        pairs.append({'group':a['group'],'strategy':a['strategy'],'scenario':a['scenario'],'old_return':a['total_return'],'new_return':b['total_return'],'difference':b['total_return']-a['total_return'],'old_2026':a['year2026']['return_fraction'],'new_2026':b['year2026']['return_fraction'],'old_mdd':a['max_drawdown'],'new_mdd':b['max_drawdown']})
    (out/'comparison.json').write_text(json.dumps({'pairs':pairs,'verification':v,'hk_all_paths_orders_exact':True,'interpretation':'Signalvolumeunit correction only,originalraw volume stillusedinactualexecution. Performance effectsare reportednot optimized. Unchanged512480states meanJune/Julycase conclusions persist.'},indent=2)+'\n')
    for p in pairs:
        if p['scenario']=='base':print(p)
if __name__=='__main__':main()
