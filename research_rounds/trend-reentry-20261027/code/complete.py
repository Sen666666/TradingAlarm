from study import *
from audit import rows
from collections import Counter
prefix=[]
for v in ['ACT','PB','BOX','BOTH']:
 full=O/v/'accounts-v2';small=O/v/'technical/prefix'
 for name in ['daily','decisions']:
  a=rows(small/f'{name}.jsonl.gz');b=[r for r in rows(full/f'{name}.jsonl.gz') if r['at'][:10]<='2026-06-30'];assert a==b,(v,name,'prefix mismatch');prefix.append(dict(version=v,stream=name,rows=len(a)))
 for sc in ['base','cost2','delay1']:
  aid='I__S0_'+sc;assert read(small/f'{aid}.json')['fills']==[r for r in read(full/f'{aid}.json')['fills'] if r['at'][:10]<='2026-06-30'],(v,sc)
# Describe resource state after the same close's decision; not a counterfactual fill.
f=pd.read_csv(O/'event-funnel.csv');meta=pd.read_csv(P.C.DESIGN/'proposed-pool.csv').set_index('symbol');tr=[]
for v in ['PB','BOX','BOTH']:
 dec={r['at'][:10]:r for r in rows(O/v/'accounts-v2/decisions.jsonl.gz') if r['account']=='I__S0_base'}
 for e in f[(f.version==v)&(f.scenario=='base')&(f.reason=='eligible_not_admitted')].itertuples():
  occ=dec[e.date]['occupancy'];sectors=Counter(r['sector_id'] for r in occ);sec=meta.loc[e.symbol,'sector_id'];reason='budget_ranking_or_memory'
  if len(occ)>=6:reason='six_slots_occupied'
  elif sectors[sec]>=2:reason='two_stocks_in_sector'
  elif sec not in sectors and len(sectors)>=3:reason='three_sectors_occupied'
  tr.append(dict(version=v,date=e.date,symbol=e.symbol,resource_state=reason,occupied=len(occ)))
pd.DataFrame(tr).to_csv(O/'resource-diagnosis.csv',index=False)
s=pd.read_csv(O/'summary.csv');c=pd.read_csv(O/'curves.csv');l=pd.read_csv(O/'local-contribution.csv');deltas=[]
for v in ['PB','BOX','BOTH']:
 for sc in ['base','cost2','delay1']:
  old=s[(s.version=='ACT')&(s.scenario==sc)].iloc[0];new=s[(s.version==v)&(s.scenario==sc)].iloc[0];q=l[(l.version==v)&(l.scenario==sc)].iloc[0]
  deltas.append(dict(version=v,scenario=sc,account_profit_delta=new.net_profit-old.net_profit,local_entry_net=q.local_profit,remaining_path_delta=new.net_profit-old.net_profit-q.local_profit,tail_profit_delta=new.tail_profit-old.tail_profit,ordinary_profit_delta=new.ordinary_profit-old.ordinary_profit))
pd.DataFrame(deltas).to_csv(O/'profit-bridge.csv',index=False)
# Whole account held days over original ACT winner windows, plus entire-path stock PnL.
cs=pd.read_csv(O/'campaigns.csv');w=cs[(cs.version=='ACT')&(cs.scenario=='base')&cs.tail_closed];part=[]
for v in ['ACT','PB','BOX','BOTH']:
 ds=[r for r in rows(O/v/'accounts-v2/daily.jsonl.gz') if r['account']=='I__S0_base']
 for r in w.itertuples():part.append(dict(version=v,symbol=r.symbol,name=r.name,original_entry=r.entry_at,original_exit=r.exit_at,held_stock_days=sum(r.entry_at[:10]<=d['at'][:10]<r.exit_at[:10] and r.symbol in d['positions'] for d in ds)))
pd.DataFrame(part).to_csv(O/'winner-participation.csv',index=False)
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(2,1,figsize=(11,8),sharex=True)
for v,label,col in [('ACT','原ACT（BOX完全重合）','#333333'),('PB','回调PB（BOTH完全重合）','#2178a7')]:
 z=c[(c.version==v)&(c.scenario=='base')];t=pd.to_datetime(z.date);ax[0].plot(t,z.nav/1e4,label=label,color=col);ax[1].plot(t,z.drawdown*100,color=col)
ax[0].set_ylabel('账户净值/万元');ax[0].legend();ax[1].set_ylabel('历史峰值回撤/%');ax[1].invert_yaxis();fig.suptitle('趋势内再入场：基础情景，初始100万元，已计费用滑点');fig.tight_layout();fig.savefig(O/'comparison.png',dpi=125);plt.close(fig)
verification=read(O/'full-verification.json');verification.update(prefix_paths=12,prefix_daily_rows=sum(r['rows'] for r in prefix if r['stream']=='daily'),prefix_decision_rows=sum(r['rows'] for r in prefix if r['stream']=='decisions'),prefix_fills_exact=True,signal_prefixes=read(O/'signal-checks.json')['physical_prefixes'],synthetic_checks=len(read(O/'tests.json')['checks']))
save(O/'verification.json',verification)
print(json.dumps(verification,ensure_ascii=False,indent=2));print(pd.DataFrame(tr).groupby(['version','resource_state']).size().to_string());print(pd.DataFrame(deltas).to_string(index=False));print(pd.DataFrame(part).groupby('version').held_stock_days.sum().to_string())
