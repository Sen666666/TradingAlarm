from pathlib import Path
import json,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R=Path(__file__).resolve().parent;S=R/'../three-layer-prototype-20261024/inputs';(R/'review').mkdir(exist_ok=False)
cases=[('bear_semi22','USHJ512480','半导体ETF','2022-01-01','2022-12-31','熊市'),('bear_jd23','HK09618','京东集团','2023-01-01','2023-12-31','熊市'),('strong_semi21','USHJ512480','半导体ETF','2021-01-01','2021-12-31','偏强震荡候选'),('strong_clp23','HK00002','中电控股','2023-01-01','2023-12-31','偏强震荡候选'),('weak_csi21','USHJ510300','沪深300ETF','2021-01-01','2021-12-31','偏弱震荡候选'),('weak_hktech23','HK03033','恒生科技ETF','2023-01-01','2023-12-31','偏弱震荡候选'),('neutral_semi23','USHJ512480','半导体ETF','2023-01-01','2023-12-31','高振幅中性震荡候选'),('neutral_hl22','HK00101','恒隆地产','2022-01-01','2022-12-31','高振幅中性震荡候选'),('low_gold21','USHJ518880','黄金ETF','2021-01-01','2021-12-31','低振幅震荡候选')]
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Arial Unicode.ttf');plt.rcParams.update({'font.family':'Arial Unicode MS','axes.unicode_minus':False,'font.size':9})
rows=[]
for idx in range(0,len(cases),3):
 fig,axs=plt.subplots(6,1,figsize=(15,12),sharex=False,layout='constrained',gridspec_kw={'height_ratios':[3,1]*3})
 for j,(cid,sym,name,start,end,typ) in enumerate(cases[idx:idx+3]):
  d=pd.read_parquet(S/f'{sym}.parquet').loc[start:end];lr=np.log(d.close/d.close.iloc[0]);ret=d.close.iloc[-1]/d.close.iloc[0]-1;vol=lr.diff().std()*np.sqrt(252);span=d.close.max()/d.close.min()-1;eff=abs(lr.iloc[-1])/lr.diff().abs().sum()
  rows.append(dict(id=cid,symbol=sym,name=name,start=start,end=end,requested_type=typ,price_return=float(ret),range=float(span),annualized_vol=float(vol),efficiency=float(eff),observations=len(d)))
  a,v=axs[2*j:2*j+2];a.plot(d.index,d.close,c='#376675');a.set_yscale('log');a.set_title(f'{cid} {name} {typ}；净涨跌{ret:+.1%}，振幅{span:.1%}，年化日波动{vol:.1%}，方向效率{eff:.3f}',loc='left');v.bar(d.index,d.volume,width=1.4,c='#aab8ae') if False else v.bar(d.index,d.volume,width=1.4,color='#aab8ae')
  for ax in [a,v]:ax.grid(alpha=.14)
 fig.savefig(R/'review'/f'raw-{idx//3+1}.png',dpi=110);plt.close(fig)
pd.DataFrame(rows).to_csv(R/'review/candidates-price-only.csv',index=False);(R/'review/candidate-list.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(pd.DataFrame(rows).to_string(index=False))
