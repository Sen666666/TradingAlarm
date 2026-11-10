from pathlib import Path
import pandas as pd,numpy as np,json,gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];PREV=ROOT/'research_rounds/tech-drawdown-regime-20261027'
if __name__=='__main__':
 out=O/'diagnostic';out.mkdir(exist_ok=False)
 a=pd.read_csv(PREV/'diagnostic-v1/breadth.csv',index_col=0,parse_dates=True);b=pd.read_csv(PREV/'signals-v1/breadth.csv',index_col=0,parse_dates=True);g=pd.read_csv(PREV/'signals-v1/market-gates.csv',index_col=0,parse_dates=True)
 p=a.equal_sector_price;prior=p.shift().rolling(63,min_periods=63).max();z=pd.DataFrame({'market':p,'prior_high63':prior,'breadth':b.m21,'fast_on':g.m21},index=a.index);z['breakout']=(p>prior)&(p.diff()>0)&(b.m21>.6);z.to_csv(O/'recovery.csv')
 # Check physical prefix of causal rolling breakout using input series already physically verified.
 for end in ['2024-12-31','2025-12-31','2026-06-30','2026-08-31']:
  q=p.loc[:end];expected=(q>q.shift().rolling(63,min_periods=63).max())&(q.diff()>0)&(b.m21.loc[:end]>.6);pd.testing.assert_series_equal(expected,z.breakout.loc[:end],check_names=False)
 curves=pd.read_csv(PREV/'results-final/curves.csv',parse_dates=['date']);f=curves[curves.scenario=='base'];x=f[f.version=='CONTROL'].set_index('date');y=f[f.version=='SHADOW20'].set_index('date');joined=pd.DataFrame({'shadow_nav':x.nav,'actual_nav':y.nav,'shadow_dd':x.drawdown,'actual_dd':y.drawdown,'shadow_exposure':x.market_value/x.nav,'actual_exposure':y.market_value/y.nav});joined.to_csv(out/'divergence.csv');joined.resample('ME').last().to_csv(out/'monthly.csv')
 # Explain losses from all security contributions over exact historical drawdown interval.
 contributions=pd.read_csv(PREV/'SHADOW20/analysis/contributions.csv');print(contributions.columns.tolist(),flush=True)
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 fig,ax=plt.subplots(3,1,figsize=(14,10),sharex=True);joined[['shadow_nav','actual_nav']].div(1e6).plot(ax=ax[0]);joined[['shadow_dd','actual_dd']].plot(ax=ax[1]);joined[['shadow_exposure','actual_exposure']].plot(ax=ax[2]);ax[0].set_title('SHADOW20与原I影子分叉：实际损耗不可由另一账户代替');fig.tight_layout();fig.savefig(out/'divergence.png',dpi=120);plt.close(fig)
 fig,ax=plt.subplots(3,1,figsize=(14,9),sharex=True);v=z.loc['2024':];ax[0].plot(v.index,v.market,label='科技等行业描述序列');ax[0].plot(v.index,v.prior_high63,label='此前63观察高点');ax[0].scatter(v.index[v.breakout],v.loc[v.breakout,'market'],marker='^',s=12,label='价格＋金额广度恢复');ax[0].legend();ax[1].plot(v.index,v.breadth,label='金额正方向广度');ax[1].axhline(.6,color='grey',ls='--');ax[1].legend();ax[2].plot(v.index,v.fast_on.astype(int),label='前轮快开关');ax[2].legend();fig.tight_layout();fig.savefig(out/'recovery.png',dpi=120);plt.close(fig)
 (O/'recovery-validation.json').write_text(json.dumps({'passed':True,'prefixes':4,'prior_full_pool_prefix_reference':str(PREV/'signal-validation.json')},indent=2));print('prepared')
