"""2026 illustrative failures and winner, selected retrospectively by category PNL."""
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
OUT=Path('results/shared-entry-path-audit');root=Path('data/ths-refresh-20261018')
f=pd.read_parquet(OUT/'episodes.parquet');f=f[f.model.eq('first_cross')&f.entry.ge('2026-01-01')]
manifest=json.loads((root/'validated-input-balanced-second500.json').read_text());records={r['symbol']:r for r in manifest['records']};scores=pd.read_parquet('results/broad-exit-disagreement/all-observed-signals.parquet')
selected=[]
for kind in ['never_positive_loss','profitable_then_loss','gave_back_tail30','retained_tail30']:
 g=f[f.kind.eq(kind)];e=g.sort_values('pnl',ascending=kind!='retained_tail30').iloc[0];selected.append(e.to_dict())
fig,axes=plt.subplots(4,3,figsize=(16,12))
for i,e in enumerate(selected):
 r=records[e['symbol']];p=pd.read_parquet(root/f"{r['ths_symbol']}-signal.parquet");start=pd.Timestamp(e['entry'])-pd.Timedelta(days=35);end=pd.Timestamp(e['exit'])+pd.Timedelta(days=7);p=p.loc[start:end];z=scores[scores.symbol.eq(e['symbol'])].set_index('date').loc[start:end]
 axes[i,0].plot(p.index,p.signal_close/p.signal_open.loc[e['entry']]);axes[i,0].set_title(e['symbol']+' | '+e['kind']);axes[i,0].set_ylabel('Adjusted close / entry open')
 axes[i,1].plot(z.index,z.strength);axes[i,1].axhline(5,color='grey',linestyle=':');axes[i,1].axhline(8.807970779778824,color='grey',linestyle=':');axes[i,1].set_ylim(0,10);axes[i,1].set_title('Existing 21-bar pairwise strength')
 axes[i,2].plot(z.index,z.fast5,color='darkorange');axes[i,2].axhline(0,color='grey',linestyle=':');axes[i,2].set_title('5-bar net return / (sqrt(5) * RMS21)')
 for ax in axes[i]:
  ax.axvline(pd.Timestamp(e['entry']),color='green',linestyle='--');ax.axvline(pd.Timestamp(e['exit']),color='red',linestyle='--');ax.grid(alpha=.2);ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=4));ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
fig.suptitle('2026 retrospective case review: green=entry, red=exit\nExamples diagnose score lag; they do not validate a faster exit rule')
fig.tight_layout();fig.savefig(OUT/'2026-cases.png',dpi=140);(OUT/'2026-cases.json').write_text(json.dumps(selected,indent=2))
