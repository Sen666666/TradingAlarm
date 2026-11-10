import pandas as pd,numpy as np,json,gzip,pathlib,collections
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
S=R/'act_only_ablation_continuous_v1'
master=pd.read_csv('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv',dtype=str).drop_duplicates('symbol').set_index('symbol')
f=pd.read_csv(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv');f=f[f.account=='PVR']
mapping=dict(zip(f.sid,f.sector));name=master.name.to_dict()
def grp(sid):return {'URFI881121':'半导体','URFI881169':'A股贵金属含白银'}.get(mapping.get(sid),'其他')
with gzip.open(S/'run/pair/PVR.json.gz','rt') as h:account=json.load(h)
daily={}
with gzip.open(S/'run/pair/daily.jsonl.gz','rt') as h:
 for line in h:
  x=json.loads(line);day=x['at'][:10]
  if x['account']=='PVR' and day>='2024-12-31':daily[day]=x
days=sorted(daily);assert days[0]=='2024-12-31' and days[-1]=='2026-05-15'
nav=pd.Series({k:float(v['nav']) for k,v in daily.items()})
hp=pd.read_csv(R/'act_entry_loss_attribution_v1/DAILY_HELD_PATH.csv')
hp=hp[(hp.account=='PVR')&hp.day.isin(days)].copy()
hp['original_stored_mark_missing']=hp.native_mark.isna()
F=json.load(open(R/'act_entry_loss_attribution_v1/FREEZE.json'))
# For valuation only, reconstruct original last-observed native mark at missing source dates.
# A stale mark is NOT a fresh observed price or executable liquidation quote.
for sid in hp.loc[hp.native_mark.isna(),'sid'].unique():
 b=pd.read_parquet(F['price_source_by_sid'][sid],columns=['raw_close','price_eligible','observed_bar','source_invalid','synthetic_event_bar'])
 valid=b.price_eligible.fillna(False)&b.observed_bar.fillna(False)&~b.source_invalid.fillna(True)&~b.synthetic_event_bar.fillna(True)&np.isfinite(b.raw_close)&b.raw_close.gt(0)
 marks=b.raw_close.where(valid).reindex(b.index.union(pd.DatetimeIndex(days))).sort_index().ffill()
 ix=hp.index[(hp.sid==sid)&hp.native_mark.isna()]
 hp.loc[ix,'native_mark']=marks.reindex(pd.DatetimeIndex(hp.loc[ix,'day'])).values
assert hp.native_mark.notna().all()
hp['inventory']=hp.round_quantity*hp.native_mark;hp['group']=hp.sid.map(grp)
inv=hp.groupby(['day','sid']).inventory.sum().unstack(fill_value=0).reindex(days,fill_value=0)
cost=hp.groupby(['day','sid']).round_remaining_cost.sum().unstack(fill_value=0).reindex(days,fill_value=0)
assert np.max(abs(inv.sum(axis=1)-pd.Series({k:float(v['inventory']) for k,v in daily.items()})))<1e-7
cf=collections.defaultdict(lambda:collections.defaultdict(float))
for t in account['trades']:
 day=t['at'][:10]
 if day<='2026-05-15':
  cf[day][t['security_id']]+=float(t['gross_cny'])-float(t['fees_cny']) if t['side']=='sell' else -float(t['gross_cny'])-float(t['fees_cny'])
cf=pd.DataFrame.from_dict(cf,orient='index').fillna(0).sort_index().cumsum().reindex(days,method='ffill').fillna(0)
assert np.max(abs((cf.sum(axis=1)-cf.sum(axis=1).iloc[0])-(pd.Series({k:float(v['available']) for k,v in daily.items()})-float(daily[days[0]]['available']))))<1e-6
cut=['2024-12-31','2025-03-31','2025-06-30','2025-09-30','2025-12-31','2026-03-31','2026-05-15']
div={}
for day in cut:
 a=collections.defaultdict(float)
 for l in account['layers']:
  if l.get('closed') and l['closed'][:10]<=day:a[l['sid']]+=float(l['dividend'])
 for l in daily[day]['layers']:a[l['sid']]+=float(l['dividend'])
 div[day]=dict(a)
 assert abs(sum(a.values())-float(daily[day]['dividend_receivable']))<1e-6,(day,'div',sum(a.values()),daily[day]['dividend_receivable'])
div=pd.DataFrame.from_dict(div,orient='index').fillna(0)
syms=sorted(set(inv.columns)|set(cf.columns)|set(div.columns));inv=inv.reindex(columns=syms,fill_value=0);cf=cf.reindex(columns=syms,fill_value=0);div=div.reindex(columns=syms,fill_value=0);cost=cost.reindex(columns=syms,fill_value=0)
wealth=cf.loc[cut]+div.loc[cut]+inv.loc[cut]
for day in cut:assert abs((wealth.loc[day]-wealth.loc[cut[0]]).sum()-(nav.loc[day]-nav.loc[cut[0]]))<1e-6
stage=[];stocks=[]
for start,end in [(cut[0],cut[-1])]+list(zip(cut[:-1],cut[1:])):
 label=start+' → '+end
 pnl=wealth.loc[end]-wealth.loc[start]
 for sid in syms:
  if grp(sid)=='其他':continue
  v=inv.loc[(inv.index>start)&(inv.index<=end),sid]
  if abs(pnl[sid])>1e-8 or v.max()>0:stocks.append({'period':label,'sid':sid,'name':name.get(sid,sid),'group':grp(sid),'contribution':pnl[sid],'start_inventory':inv.loc[start,sid],'end_inventory':inv.loc[end,sid],'mean_inventory':v.mean(),'mean_nav_fraction':(v/nav.loc[v.index]).mean(),'held_days':int((v>0).sum()),'buy_fills':sum(t['side']=='buy' and t['security_id']==sid and start<t['at'][:10]<=end for t in account['trades'])})
 for group in ['半导体','A股贵金属含白银','其他','全账户']:
  ss=syms if group=='全账户' else [s for s in syms if grp(s)==group]
  vd=inv.loc[(inv.index>start)&(inv.index<=end),ss].sum(axis=1);cd=cost.loc[vd.index,ss].sum(axis=1);rat=vd/nav.loc[vd.index]
  stage.append({'period':label,'group':group,'sessions':len(vd),'contribution':float(pnl[ss].sum()),'contribution_vs_start_NAV':float(pnl[ss].sum()/nav.loc[start]),'start_NAV':nav.loc[start],'end_NAV':nav.loc[end],'mean_inventory':vd.mean(),'mean_NAV_fraction':rat.mean(),'peak_NAV_fraction':rat.max(),'peak_NAV_fraction_day':rat.idxmax(),'mean_remaining_cost':cd.mean(),'held_days':int((vd>0).sum()),'zero_days':int((vd==0).sum()),'end_inventory':float(inv.loc[end,ss].sum()),'buy_fills':sum(t['side']=='buy' and t['security_id'] in ss and start<t['at'][:10]<=end for t in account['trades'])})
out=pd.DataFrame(stage);stockout=pd.DataFrame(stocks)
print(out.to_string(index=False))
print('FULL STOCKS');print(stockout[stockout.period==cut[0]+' → '+cut[-1]].sort_values(['group','contribution']).to_string(index=False))
# Save only if explicitly called with output directory.
import sys
if len(sys.argv)>1:
 O=pathlib.Path(sys.argv[1]);O.mkdir(exist_ok=True)
 out.to_csv(O/'FIXED_QUARTER_ACTUAL_CONTRIBUTIONS.csv',index=False);stockout.to_csv(O/'SEMICONDUCTOR_PRECIOUS_STOCK_CONTRIBUTIONS.csv',index=False)
 pd.DataFrame([{'day':day,'group':group,'inventory':float(inv.loc[day,[s for s in syms if grp(s)==group]].sum()),'NAV':nav.loc[day],'inventory_NAV_fraction':float(inv.loc[day,[s for s in syms if grp(s)==group]].sum()/nav.loc[day]),'remaining_cost':float(cost.loc[day,[s for s in syms if grp(s)==group]].sum())} for day in days for group in ['半导体','A股贵金属含白银']]).to_csv(O/'DAILY_THEME_EXPOSURE.csv',index=False)
 json.dump({'stale_native_marks_reconstructed':int(hp.original_stored_mark_missing.sum()),'fresh_or_executable_price_claimed':False,'status':'PASS','dates':cut,'daily_inventory_equals_native':True,'cashflow_equals_native_available_delta':True,'cut_booked_dividend_equals_receivable':True,'all_stock_contributions_equal_native_NAV_delta':True,'no_account_rerun':True,'method':'delta(cumulative actual net trade cash + booked dividends + native close inventory); fixed current industry map NON-PIT; external payout/real fill UNKNOWN'},open(O/'CONTRIBUTION_RECONCILIATION.json','w'),ensure_ascii=False,indent=2)
