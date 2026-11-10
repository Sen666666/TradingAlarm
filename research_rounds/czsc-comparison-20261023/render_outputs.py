"""Align the two chart price axes, reading saved outputs without rerunning models."""
from pathlib import Path
import hashlib
import json
import shutil
import pandas as pd
import build

HERE=Path(__file__).resolve().parent
OUT=HERE/'outputs/v2'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    archive=OUT/'charts/prior-axis-v1'
    archive.mkdir(exist_ok=False)
    receipt={'purpose':'Identical price y-ranges for paired charts; no signal/model rerun',
             'renderer_sha256':sha(__file__),'plot_code_sha256':sha(HERE/'build.py'),
             'models_recomputed':False,'series':[]}
    for s in json.loads((OUT/'summary.json').read_text()):
        sid=s['symbol']
        p=OUT/'data'/f'{sid}-daily-output.csv'
        g=OUT/'data'/f'{sid}-terminal-geometry.json'
        d=pd.read_csv(p,index_col='date',parse_dates=True,float_precision='round_trip')
        price=['open','high','low','close','volume']
        causal=[c for c in d if c.startswith('czsc_')]
        state=[c for c in d if c not in price+causal]
        geo=json.loads(g.read_text())
        old={}
        for suffix in ['comparison.html','comparison.png']:
            f=OUT/'charts'/f'{sid}-{suffix}'
            old[f.name]=sha(f)
            shutil.copy2(f,archive/f.name)
        build.OUT=OUT
        build.make_plot(sid,s['name'],d[price],d[state],d[causal],
                        geo['bis'],geo['zs'],geo['fx'],geo['unfinished'])
        native=OUT/'charts'/f'{sid}-native.html'
        # The renderer's decorative LIVE badge is misleading for saved data.
        shutil.copy2(native,archive/native.name)
        native.write_text(native.read_text().replace('LWC · LIVE','LWC · LOCAL SNAPSHOT'))
        receipt['series'].append({'symbol':sid,'daily_input_sha256':sha(p),
                                  'geometry_sha256':sha(g),'old_chart_sha256':old})
    (OUT/'rendering-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    main()
