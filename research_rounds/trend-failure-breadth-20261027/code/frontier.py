from pathlib import Path
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parents[1];R=O.parent
sources=[('tech-drawdown-regime-20261027','results-final'),('actual-risk-recovery-20261027','results'),('risk-warning-budget-20261027','results'),('staged-risk-20261027','results')]
frames=[]
for root,folder in sources:
 s=pd.read_csv(R/root/folder/'scoreboard.csv');s['source']=root;frames.append(s)
a=pd.concat(frames).drop_duplicates(['version','scenario'],keep='last');a.to_csv(O/'results/all-policy-scenarios.csv',index=False)
x=a.groupby('version').agg(worst_return=('net_return','min'),worst_drawdown=('max_drawdown','max'),worst_h2_return=('h2_return','min'),minimum_pre_profit_retention=('pre_profit_retention','min'),scenario_count=('scenario','nunique'))
assert x.scenario_count.eq(3).all()
# Non-dominated on all four reported objectives; no fitted score or arbitrary weights.
vals=x[['worst_return','worst_h2_return','minimum_pre_profit_retention']].copy();vals['negative_worst_drawdown']=-x.worst_drawdown
x['dominated']=[bool(((vals>=v).all(axis=1)&(vals>v).any(axis=1)).any()) for _,v in vals.iterrows()];x.to_csv(O/'results/stress-frontier.csv')
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(13,8));ax.scatter(x.minimum_pre_profit_retention*100,x.worst_drawdown*100,c=np.where(x.dominated,'gray','tab:blue'),s=45)
for name,r in x.iterrows():
 if not r.dominated:ax.annotate(name,(r.minimum_pre_profit_retention*100,r.worst_drawdown*100),xytext=(5,5),textcoords='offset points')
ax.set_xlabel('三情景最低前期累计利润保留（%）');ax.set_ylabel('三情景最大全历史回撤（%）');ax.set_title('已完成策略取舍：右下更好；蓝点为四指标未被支配方案\n不同最差指标可能来自不同情景，不是一条实际账户路径');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(O/'results/stress-frontier.png',dpi=130);print(x[~x.dominated].to_string())
