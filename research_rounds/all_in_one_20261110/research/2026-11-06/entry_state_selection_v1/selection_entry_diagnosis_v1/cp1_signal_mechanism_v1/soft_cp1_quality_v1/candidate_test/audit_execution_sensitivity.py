
from pathlib import Path
import pandas as pd,numpy as np,json
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/soft_cp1_quality_v1/candidate_test')
D=O/'execution_sensitivity';D.mkdir(exist_ok=True)
s=pd.read_parquet(O/'SELECTED_WITH_FIXED_LABELS.parquet');s=s[s.account=='PVR'].copy()
raw={x['series_id']:x['raw']['path']for x in json.loads(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json').read_text())['series']}
records=[]
for sid,g in s[['sid','entry_day']].drop_duplicates().groupby('sid'):
 f=pd.read_parquet(raw[sid]);f.index=pd.to_datetime(f.trade_date)
 for q in g.itertuples():
  day=pd.Timestamp(q.entry_day);z=dict(sid=sid,entry_day=q.entry_day,raw_bar_known=day in f.index)
  if day in f.index:
   j=f.index.get_loc(day);a=f.loc[day];prev=f.iloc[j-1]if j>0 else None
   z.update(raw_open=a.open,raw_high=a.high,raw_low=a.low,raw_close=a.close,raw_amount=a.amount)
   z['one_price_up']=bool(np.isclose(a.high,a.low,atol=1e-8,rtol=0)and prev is not None and a.close>prev.close*(1+1e-8))
  else:z['one_price_up']=False
  records.append(z)
flags=pd.DataFrame(records);flags.to_csv(D/'RAW_NEXT_OPEN_FLAGS.csv',index=False)
s=s.merge(flags,on=['sid','entry_day'],how='left',validate='many_to_one')
s[s.one_price_up].to_csv(D/'ONE_PRICE_UP_SELECTED_EVENTS.csv',index=False)
paired=pd.read_csv(O/'PAIRED_DATE_DETAILS.csv');paired=paired[paired.account.eq('PVR')]
summ=[]
for (year,H),p in paired.groupby(['year','horizon']):
 days=p.loc[p.both_all_complete,'day'];g=s[s.year.eq(year)&s.day.isin(days)].copy()
 g['stress_ret']=g[f'ret{H}'].where(~g.one_price_up,0.)
 g['flagged_ret_contribution']=g[f'ret{H}'].where(g.one_price_up,0.)
 d=g.groupby(['day','strategy'])[['stress_ret',f'ret{H}','flagged_ret_contribution']].mean()
 wide=d.unstack('strategy')
 summ.append(dict(year=int(year),horizon=int(H),same_complete_days=len(days),base_original_mean=wide[(f'ret{H}','ORIGINAL_PVR')].mean(),Q_original_mean=wide[(f'ret{H}','CONTINUOUS_Q')].mean(),original_Q_minus_base=(wide[(f'ret{H}','CONTINUOUS_Q')]-wide[(f'ret{H}','ORIGINAL_PVR')]).mean(),base_stress_mean=wide[('stress_ret','ORIGINAL_PVR')].mean(),Q_stress_mean=wide[('stress_ret','CONTINUOUS_Q')].mean(),stress_Q_minus_base=(wide[('stress_ret','CONTINUOUS_Q')]-wide[('stress_ret','ORIGINAL_PVR')]).mean(),base_one_price_events=int(g[g.strategy=='ORIGINAL_PVR'].one_price_up.sum()),Q_one_price_events=int(g[g.strategy=='CONTINUOUS_Q'].one_price_up.sum())))
out=pd.DataFrame(summ);out.to_csv(D/'ONE_PRICE_ZERO_PATH_SENSITIVITY.csv',index=False)
counts=s.groupby(['year','strategy']).agg(selected=('sid','size'),one_price_up=('one_price_up','sum'),unknown_raw=('raw_bar_known',lambda x:int((~x).sum()))).reset_index();counts.to_csv(D/'RAW_FLAG_COUNTS.csv',index=False)
print(counts.to_string(index=False));print(out.to_string(index=False))
(D/'README.md').write_text('原PVR臂两种同K入选清单的只读执行风险敏感性。one_price_up用次执行日原OHLC的H=L且高于前观察收盘作保守标记，不代表必然不成交，也不是信号日可知的过滤器。路径压力列把这些事后标记的入选收益设0、保持原K和其它槽不变，等价于假设疑似一价单不成交且无替补的路径占位；它不是新账户、不是可执行当日规则、不是新排序，未重新分配资金。原始标签与队列未修改。仅在原主体实验双方全部选中样本同为成熟的日期上比较；不是把缺样本当0。MAE仍以原报告为准。非一价也不证明盘口成交。')
