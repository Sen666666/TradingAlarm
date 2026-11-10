from pathlib import Path
import pandas as pd,numpy as np,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];A=O.parent/'actual-risk-recovery-20261027'
def build(x):
 z=x.copy();p=z.market;up=p.diff()>0;breadth=z.breadth>.6;p5=breadth.rolling(5,min_periods=5).sum().eq(5);z['high21']=p.shift().rolling(21,min_periods=21).max();z['ema21']=p.ewm(span=21,adjust=False).mean();z['break21']=up&breadth&p.gt(z.high21);z['break21_p5']=z.break21&p5;z['ema21_p5']=up&p5&p.gt(z.ema21)&z.ema21.gt(z.ema21.shift(5));return z
if __name__=='__main__':
 x=pd.read_csv(A/'recovery.csv',index_col=0,parse_dates=True);z=build(x);z.to_csv(O/'recovery.csv');ends=['2024-12-31','2025-12-31','2026-06-30','2026-08-31']
 for end in ends:pd.testing.assert_frame_equal(z.loc[:end],build(x.loc[:end]))
 assert not (z.break21_p5 & ~z.break21).any();assert z['breakout'].equals(x['breakout']);assert not z.loc[z.breadth.isna(),['break21','break21_p5','ema21_p5']].any().any()
 (O/'recovery-validation.json').write_text(json.dumps({'passed':True,'prefixes':ends,'baseline_exact':True,'nested_condition':True,'missing_rejected':True},indent=2))
 out=O/'diagnostic';out.mkdir(exist_ok=False);plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 for year in [2024,2025,2026]:
  t=z.loc[str(year)];fig,ax=plt.subplots(3,1,figsize=(14,9),sharex=True);t[['market','prior_high63','high21','ema21']].plot(ax=ax[0]);t.breadth.plot(ax=ax[1]);ax[1].axhline(.6,color='gray',ls='--')
  for i,k in enumerate(['breakout','break21','break21_p5','ema21_p5']):ax[2].scatter(t.index[t[k]],np.repeat(i,int(t[k].sum())),marker='|',s=65,label=k)
  ax[2].set_yticks(range(4),['原63突破','21突破','21突破+5日广度','EMA21+5日广度']);ax[0].set_title(str(year)+' 恢复条件图：标记仅表示条件成立，不是实际恢复或买入');ax[1].set_ylabel('金额方向广度');fig.tight_layout();fig.savefig(out/f'{year}.png',dpi=120);plt.close(fig)
 print(z.loc['2024':].groupby(z.loc['2024':].index.year)[['breakout','break21','break21_p5','ema21_p5']].sum().to_string())
