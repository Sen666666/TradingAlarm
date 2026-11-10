"""Post-result corrections and review, no candidate parameter changes."""
import argparse,json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(out):
    # Same preselected 512480 security; protocol used display-market prefix, loader uses USHJ.
    (out/'case-alias-correction.json').write_text(json.dumps({'protocol_case':'SH512480','actual_loader_key':'USHJ512480','reason':'Same preselected security, symbol alias correction after trajectory run; frozen protocol retained','model_or_case_selection_changed':False},indent=2))
    d=pd.read_csv(out/'USHJ512480-signals.csv',index_col='date',parse_dates=True).loc['2024-01-01':'2026-10-16'];fig,ax=plt.subplots(4,1,figsize=(12,8),sharex=True)
    ax[0].plot(d.index,d.close,color='black');ax[0].set_title('512480 retained impact; original protocol symbol alias corrected')
    ax[1].bar(d.index,d.volume,color='gray');ax[2].plot(d.index,d.strength,label='PV');ax[2].plot(d.index,d.price_strength,label='Price');ax[2].axhline(0,color='black',lw=.5);ax[2].axhline(1,ls=':',color='black');ax[2].legend();ax[3].step(d.index,d.target,where='post');fig.tight_layout();fig.savefig(out/'USHJ512480-trajectory.png',dpi=130);plt.close(fig)
    rows=[]
    for s in ['HK03033','HK00700','USHJ512480']:
        d=pd.read_csv(out/f'{s}-signals.csv',index_col='date',parse_dates=True).loc['2022-01-01':'2026-10-16'];rows.append(dict(symbol=s,entries=int(d.target.diff().fillna(d.target.iloc[0]).eq(1).sum()),held_fraction=float(d.target.mean()),volume_price_target_different=int(d.target.ne(d.price_target).sum())))
    (out/'review-summary.json').write_text(json.dumps({'status':'rejected at trajectory gate; no new account results','same_2022_2026_window':rows,'reason':'Repeated overlapping price intervals counted as independent retained evidence. No change to thresholds or decay after outcomes.'},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
