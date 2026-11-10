import json, pathlib, hashlib, csv
import numpy as np
import pandas as pd
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'pvr_2026_sector_opportunity_attribution_v1'
O.mkdir(exist_ok=True)
S={
 'first':R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv',
 'round':R/'act_entry_loss_attribution_v1/ALL_ROUND_ATTRIBUTION.csv',
 'daily':R/'act_entry_loss_attribution_v1/DAILY_HELD_PATH.csv',
 'prior_sector':R/'technology_winrate_scope_audit_v1/CURRENT_PVR_2026_INDUSTRY_CLOSED.csv',
 'tech':pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/tech-finite-compound-20261026/data/core-v3/manifest.json'),
 'master':pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv'),
 'cache':pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
hashes={k:{'path':str(p),'sha256':sha(p)} for k,p in S.items()}
json.dump({'window':['2026-01-01','2026-05-15'],'cohort':'actual first BUY in window; not all holdings or full account annual NAV','full_vs_initial':'separate native stored net attribution; open marks not wins or closed net','classifications':'old407 stock manifest; strict semi current master name 半导体; nontech disjoint from407; current mapping NON-PIT','capital':'actual remaining fee-inclusive buy cost per daily close; mean over85 common dates, not nominal1200000 extra cash','price_paths':'strict daily descriptive only, no new account or signal; all90 and purchased68 industry; posthoc maximum rally does not mean executable profit','unknown':'original historical terms PIT, true executability and external dividend payout UNKNOWN inherited; no new zero imputation','sources':hashes},open(O/'FROZEN_SCOPE.json','w'),ensure_ascii=False,indent=2)
f=pd.read_csv(S['first'])
a=pd.read_csv(S['round'])
f=f[(f.account=='PVR')&(f.entry_day>='2026-01-01')&(f.entry_day<='2026-05-15')].copy()
a=a[(a.account=='PVR')&(a.entry_year==2026)].copy()
d=f.merge(a,on=['account','sid'],left_on=None,right_on=None) if False else f.merge(a,left_on=['account','sid','first_layer'],right_on=['account','sid','initial_layer'],suffixes=('_first',''),validate='one_to_one')
assert len(d)==257 and len(a)==257
assert np.allclose(d.loc[d.round_status=='CLOSED','round_pnl'],d.loc[d.round_status=='CLOSED','round_pnl_first'],atol=1e-6)
# FIRST_ENTRIES intentionally omits open net; use original layer-attribution terminal marks separately.
assert (d.opened.str[:10]==d.entry_day).all()
assert (d.closed_first==(d.round_status=='CLOSED')).all()
m=pd.read_csv(S['master'],dtype=str).drop_duplicates('symbol').set_index('symbol')
d['name']=d.sid.map(m.name)
d['industry']=d.sid.map(m.industry_name)
assert (d.sid.map(m.industry_index_symbol)==d.sector).all()
tech={x['series_id'] for x in json.load(open(S['tech']))['series'] if x['kind']=='stock'}
assert len(tech)==407
d['oldtech407']=d.sid.isin(tech)
d['strict_semi']=d.industry.eq('半导体')
d['pool_group']=np.where(d.oldtech407,'旧407科技','非科技')
cache=np.load(S['cache'],allow_pickle=True)
days=cache['dates'].astype('datetime64[D]').astype(str)
days=days[(days>='2026-01-01')&(days<='2026-05-15')].tolist()
assert len(days)==85
x=pd.read_csv(S['daily'])
x=x[(x.account=='PVR')&x.round_id.isin(d.round_id)&x.day.isin(days)].copy()
x=x.merge(d[['round_id','sector','industry','pool_group']],on='round_id',validate='many_to_one')
x['inventory_mark']=x.round_quantity*x.native_mark
def capital(v):
 ids=set(v.round_id)
 z=x[x.round_id.isin(ids)].groupby('day')[['round_remaining_cost','initial_remaining_cost','inventory_mark']].sum().reindex(days,fill_value=0)
 return {'round_capital_days':float(z.round_remaining_cost.sum()),'round_avg_capital':float(z.round_remaining_cost.mean()),'round_peak_capital':float(z.round_remaining_cost.max()),'round_peak_capital_day':str(z.round_remaining_cost.idxmax()),'initial_capital_days':float(z.initial_remaining_cost.sum()),'initial_avg_capital':float(z.initial_remaining_cost.mean()),'inventory_mark_avg':float(z.inventory_mark.mean()),'inventory_mark_peak':float(z.inventory_mark.max()),'terminal_remaining_cost':float(z.round_remaining_cost.iloc[-1]),'terminal_inventory_mark':float(z.inventory_mark.iloc[-1])}
def stats(v):
 r={'new_rounds':len(v),'stocks':v.sid.nunique(),'first_signal':v.signal_day.min(),'last_signal':v.signal_day.max(),'first_buy':v.entry_day.min(),'last_buy':v.entry_day.max(),'initial_total_buy_cost':float(v.initial_buy_cost.sum()),'whole_total_buy_cost':float(v.round_buy_cost.sum())}
 for p in ['round','initial']:
  c=v[v[p+'_status']=='CLOSED'];o=v[v[p+'_status']!='CLOSED']; win=c[c[p+'_pnl']>1e-8];loss=c[c[p+'_pnl']< -1e-8]
  mw=float(win[p+'_pnl'].mean()) if len(win) else None
  ml=-float(loss[p+'_pnl'].mean()) if len(loss) else None
  r.update({p+'_closed':len(c),p+'_wins':len(win),p+'_losses':len(loss),p+'_zero':len(c)-len(win)-len(loss),p+'_open':len(o),p+'_winrate':len(win)/len(c) if len(c) else None,p+'_closed_net':float(c[p+'_pnl'].sum()),p+'_mean_win':mw,p+'_mean_loss':ml,p+'_payoff':mw/ml if mw is not None and ml is not None and ml else None,p+'_open_mark_net_NOT_final':float(o[p+'_pnl'].sum()),p+'_gross_win':float(win[p+'_pnl'].sum()),p+'_gross_loss':float(loss[p+'_pnl'].sum())})
  if len(c):
   worst=c.sort_values(p+'_pnl').iloc[0]
   r[p+'_worst_sid']=worst.sid;r[p+'_worst_name']=worst['name'];r[p+'_worst_net']=float(worst[p+'_pnl']);r[p+'_worst_entry']=worst.entry_day
 r.update(capital(v))
 assert abs(r['round_capital_days']-v.round_capital_days.sum())<1e-4
 assert abs(r['initial_capital_days']-v.initial_capital_days.sum())<1e-4
 return r
groups=[]
for name,v in [('全体',d),('旧407科技',d[d.oldtech407]),('非科技',d[~d.oldtech407]),('严格半导体_科技子集',d[d.strict_semi])]:
 groups.append({'group':name,**stats(v)})
sectors=[]
for sec,v in d.groupby('sector'):
 sectors.append({'sector':sec,'industry':v.industry.iloc[0],'oldtech407':bool(v.oldtech407.all()),**stats(v)})
g=pd.DataFrame(groups);s=pd.DataFrame(sectors)
prior=pd.read_csv(S['prior_sector'])
check=s.merge(prior,on='sector',suffixes=('','_prior'),validate='one_to_one')
assert (check.new_rounds==check.new_rounds_prior).all()
assert (check.round_closed==check.closed).all()
assert (check.round_wins==check.wins).all()
assert (check.round_open==check.still_open).all()
assert np.allclose(check.round_closed_net,check.closed_net,atol=1e-6)
assert s.new_rounds.sum()==257 and s.round_closed.sum()==193 and s.round_wins.sum()==41
g.to_csv(O/'GROUP_STATISTICS.csv',index=False)
s.sort_values('round_closed_net').to_csv(O/'INDUSTRY_TRADE_STATISTICS.csv',index=False)
keep=['round_id','sid','name','industry','sector','pool_group','strict_semi','signal_day','entry_day','closed','first_kind','first_reason','initial_pool','PVR_decision','priority_rank','initial_buy_cost','round_buy_cost','initial_status','initial_pnl','round_status','round_pnl','later_layer_pnl','followup_add_count','round_held_closes','round_capital_days','initial_capital_days','historical_real_tradability','external_dividend_payout','historical_terms_PIT']
d[keep].sort_values(['entry_day','sid']).to_csv(O/'ALL_257_ACTUAL_ENTRY_ROUNDS.csv',index=False)
x.groupby(['day','sector','industry'])[['round_remaining_cost','initial_remaining_cost','inventory_mark']].sum().reset_index().to_csv(O/'DAILY_SECTOR_CAPITAL.csv',index=False)
worst=d[d.round_status=='CLOSED'].sort_values('round_pnl')
worst[keep].head(15).to_csv(O/'LARGEST_15_CLOSED_LOSSES.csv',index=False)
m3=[]
for arm in ['all1709','tech407']:
 p=R/'m3_ab_shared_probe_v1/tech407_admission_mask_ablation_v1'/('run_'+arm+'_once')
 j=json.load(open(p/'EXACT_TRADE_JOURNAL.json'))
 z=[r for r in j if '2026-01-01'<=r['day'][:10]<='2026-05-15']
 res=json.load(open(p/'RESULT.json'))
 m3.append({'arm':arm,'2026_trade_count':len(z),'2026_initial_buy_count':sum(r['side']=='buy_core' for r in z),'2026_add_count':sum(r['side']=='buy_add' for r in z),'last_actual_trade':max(r['day'] for r in j),'final_reconciliation':res['final_reconciliation'],'source':str(p)})
json.dump(m3,open(O/'M3_2026_ACTUAL_ACTIVITY.json','w'),ensure_ascii=False,indent=2)
for k,p in S.items():assert hashes[k]['sha256']==sha(p)
json.dump({'status':'ARITHMETIC_PASS','cohort':257,'stocks':242,'sectors':68,'days':85,'closed':193,'wins':41,'losses':152,'open':64,'sector_reconciles_to_prior_68':True,'initial_and_full_reconcile':True,'daily_capital_reconciles':True,'sources_unchanged':True,'not_claimed':'independent audit or new account validation'},open(O/'ARITHMETIC_CHECKS.json','w'),ensure_ascii=False,indent=2)
print('GROUPS');print(g.to_string(index=False))
print('ALL68');print(s[['industry','new_rounds','round_wins','round_losses','round_open','round_closed_net','round_payoff','initial_wins','initial_closed_net','round_avg_capital']].sort_values('round_closed_net').to_string(index=False))
print('WORST');print(worst[['sid','name','industry','entry_day','closed','round_pnl','initial_pnl','round_buy_cost']].head(15).to_string(index=False))
print('OUTPUT',O)
