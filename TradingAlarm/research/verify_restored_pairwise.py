import json
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from strategy_signals import build_signals
from asymmetric_pairwise import asymmetric_frame
from volume_units import split_consistent_volume
out=Path('results/strength-restored-pairwise');etf,_=load_extended();hk,_=load_assets();rows=[]
for group,assets in [('etf17',etf),('hk7',hk)]:
    old=build_signals(assets,'asymmetric_pairwise_volume');new=build_signals(assets,'restored_pairwise_volume')
    for s in assets:
        a=old[s].loc['2022-01-01':'2026-10-16'];b=new[s].reindex(a.index)
        rows.append(dict(group=group,symbol=s,compared_sessions=len(a),changed_sessions=int(a.ne(b).sum())))
    for scenario in ['base','cost2','delay1']:
        oldcase=f'{group}-asymmetric_pairwise_volume-daily-{scenario}';newcase=f'{group}-restored_pairwise_volume-daily-{scenario}'
        pd.testing.assert_frame_equal(pd.read_parquet(out/f'{oldcase}-path.parquet'),pd.read_parquet(out/f'{newcase}-path.parquet'),check_exact=True)
        assert json.loads((out/f'{oldcase}-orders.json').read_text())==json.loads((out/f'{newcase}-orders.json').read_text())
asset=etf['USHJ512480'];raw=asset['raw'];sig=asset['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
f=asymmetric_frame(sig.close.reindex(valid),split_consistent_volume(raw.volume,asset.get('splits',[])).reindex(valid),False)
selected=f.loc[['2026-06-03','2026-06-22','2026-06-30']]
selected.to_csv(out/'june-state.csv')
result=dict(symbols=rows,exact_path_and_order_pairs=6,changed_sessions=sum(r['changed_sessions'] for r in rows),interpretation='Upcross requirement is redundant on this development panel; removal changes no observed target. June22 slow score below entry threshold, so missed recovery is estimator/threshold eligibility, not lack of crossing alone.')
(out/'mechanism-audit.json').write_text(json.dumps(result,indent=2));print(selected);print('Changed target sessions:',result['changed_sessions'])
