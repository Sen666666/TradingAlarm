"""Freeze and inspect four existing inputs before revealing CZSC output."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIOR = ROOT / 'research_rounds/pv-participation-response-20261020'
OUT = HERE / 'outputs/v1'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.tools/czsc/mpl'))
sys.path.insert(0, str(PRIOR / 'code'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from data_utils import load_source, eligible_prices

SYMBOLS = [('600919.SH', '江苏银行'), ('600059.SH', '古越龙山'),
           ('600917.SH', '重庆燃气'), ('HK00700', '腾讯控股')]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'data').mkdir()
    (OUT / 'charts').mkdir()
    prior_freeze = json.loads((PRIOR / 'results/v0-input-fixed/run-freeze.json').read_text())
    code = {}
    for name, expected in prior_freeze['code'].items():
        p = PRIOR / 'code' / name
        assert sha(p) == expected, ('frozen algorithm changed', name)
        code[str(p.relative_to(ROOT))] = expected
    manifest = json.loads((PRIOR / 'prepared/source-precision-v1/manifest.json').read_text())
    mask = json.loads((PRIOR / 'prepared/source-precision-v1/observation-mask-addendum.json').read_text())
    masks = {x['symbol']: x['exclude_price_dates'] for x in mask['series']}
    result_manifest = json.loads((PRIOR / 'results/v0-input-fixed/manifest.json').read_text())
    frozen = {'prepared_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'protocol_sha256': sha(HERE/'PROTOCOL.md'), 'algorithm_code': code,
              'prepare_code_sha256': sha(__file__), 'display_start':'2024-01-01',
              'display_end':'2026-10-16', 'algorithm_changes':0, 'accounts_run':0,
              'market_data_downloads':0, 'series':[]}
    font = FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    fig, axs = plt.subplots(4, 2, figsize=(16, 11), gridspec_kw={'width_ratios':[4,1.6]})
    for n,(sid,name) in enumerate(SYMBOLS):
        source = load_source(sid, PRIOR)
        bars = eligible_prices(source, sid, masks[sid])
        assert bars.volume.gt(0).all() and np.isfinite(bars.volume).all()
        saved = PRIOR / f'results/v0-input-fixed/{sid}-states.csv'
        assert sha(saved) == result_manifest[saved.name]
        record = next(x for x in manifest['series'] if x['symbol']==sid)
        path = PRIOR / 'prepared/source-precision-v1' / record['file']
        source.to_csv(OUT/'data'/f'{sid}-source.csv', float_format='%.17g')
        bars.to_csv(OUT/'data'/f'{sid}-input.csv', float_format='%.17g')
        frozen['series'].append({'symbol':sid,'name':name,
            'source_path':str(path.relative_to(ROOT)), 'source_sha256':sha(path),
            'baseline_path':str(saved.relative_to(ROOT)), 'baseline_sha256':sha(saved),
            'input_sha256':sha(OUT/'data'/f'{sid}-input.csv'),
            'full_source_rows':len(source), 'eligible_rows':len(bars),
            'excluded_dates':[str(x.date()) for x in source.index.difference(bars.index)],
            'first':str(bars.index[0].date()),'last':str(bars.index[-1].date()),
            'price_basis':record['source_metadata']['adjustment'],
            'volume_basis':record['source_metadata']['volume_units']})
        q = bars.loc['2024-01-01':'2026-10-16']
        axs[n,0].plot(q.index,q.raw_close,color='#263f56',lw=1)
        axs[n,0].set_title(name+' '+sid+' | 原价收盘',fontproperties=font,loc='left')
        axs[n,0].grid(alpha=.15)
        axs[n,1].bar(q.index,q.raw_volume,color='#8ea4b5',width=1.6)
        axs[n,1].set_title('源成交量（未跨股比较单位）',fontproperties=font,loc='left')
        axs[n,1].ticklabel_format(axis='y',style='sci',scilimits=(0,0))
        for ax in axs[n]:
            ax.tick_params(labelsize=8)
            ax.spines[['top','right']].set_visible(False)
    fig.suptitle('先看已有原始量价｜四只固定样本｜2024-01-01 — 2026-10-16',fontproperties=font,fontsize=17)
    fig.tight_layout(rect=(0,0,1,.96))
    fig.savefig(OUT/'charts/raw-overview.png',dpi=150)
    plt.close(fig)
    (OUT/'input-freeze.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(OUT),'series':[{k:x[k] for k in ['symbol','eligible_rows','first','last','excluded_dates']} for x in frozen['series']]},ensure_ascii=False))

if __name__=='__main__':
    main()
