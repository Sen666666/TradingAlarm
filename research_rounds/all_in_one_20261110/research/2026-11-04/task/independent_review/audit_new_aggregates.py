from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import Counter
from datetime import datetime
import json,csv,hashlib
import pyarrow.parquet as pq
getcontext().prec=80
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
issues=[];resolved=[];counts={};sources={}
def check_sha(d):
 for p,h in d.items():
  if sha(p)!=h:
   matching=[z for z in (ROOT/'participation').glob('PROTOCOL_*_SNAPSHOT.txt') if sha(z)==h] if p.endswith('/participation/PROTOCOL.txt') else []
   if matching:resolved.append({'kind':'append_only_protocol_stage_snapshot','original_path':p,'saved':h,'exact_snapshot':str(matching[0])})
   else:issues.append({'kind':'provenance_mismatch','path':p,'saved':h,'actual':sha(p)})
  else:sources[p]=h
r=read(ROOT/'participation/RESULTS.json');check_sha(r['source_sha256'])
cols=['day','sector','industry','global_F1_permit','F1_permit','F1_mature','I_entry_Q','canonical_CP1_Q','canonical_status']
for w,c in r['coverage'].items():
 p=next(Path(p)for p in r['source_sha256']if p.endswith(w+'-FULL_TABLE_WITH_HISTORY.parquet'))
 rows=pq.read_table(p,columns=cols).to_pylist();assert len(rows)==len({(z['day'],z['sector']) for z in rows})
 assert c['from']==min(z['day']for z in rows) and c['to']==max(z['day']for z in rows)
 assert c['days']==len({z['day']for z in rows}) and c['industries']==len({z['sector']for z in rows}) and c['industry_observations']==len(rows)
 masks={'global_only':lambda z:z['global_F1_permit'] and not z['F1_permit'],'local_only':lambda z:not z['global_F1_permit'] and z['F1_permit'],'both':lambda z:z['global_F1_permit'] and z['F1_permit'],'neither':lambda z:not z['global_F1_permit'] and not z['F1_permit'],'local_mature_while_global_false':lambda z:not z['global_F1_permit'] and z['F1_permit'] and z['F1_mature']}
 for k,fun in masks.items():
  rr=[z for z in rows if fun(z)];v=c['groups'][k] if k in c['groups'] else c[k]
  assert v['industry_observations']==len(rr) and v['distinct_days']==len({z['day']for z in rr}) and v['distinct_industries']==len({z['sector']for z in rr})
  assert v['I_entry_Q_stock_observations']==sum(z['I_entry_Q']for z in rr)
  if w=='OLD924':assert v['canonical_CP1_Q_stock_observations'] is None
  else:assert v['canonical_CP1_Q_stock_observations']==sum(z['canonical_CP1_Q']for z in rr)
 counts['coverage_'+w]={'industry_days':len(rows),'local_only_stock_CP1_observations':c['groups']['local_only']['canonical_CP1_Q_stock_observations'],'unique_stock_CP1_episodes':'not_observable_from_industry_day_aggregate'}
f=read(ROOT/'participation/FUNDING_RESULTS.json');check_sha(f['source_sha256'])
sp=next(Path(p)for p in f['source_sha256']if p.endswith('SEMICONDUCTOR_OPPORTUNITY_FUNNEL.json'));sr=read(sp)['all_receipts'];sem=f['semiconductor_old_PVR_H1_2026'];assert len(sr)==833
assert Counter(z['category']for z in sr)==sem['categories']
assert len({(z['sid'],z['signal_day'],z['receipt'])for z in sr})==len(sr)
sids={z['sid']for z in sr};fsids={z['sid']for z in sr if z['category']=='reserved_and_filled'}
assert [len(sids),len(fsids),len(sids-fsids)]==[sem['stock_count_with_any_signal'],sem['stock_count_with_filled_signal'],sem['stock_count_with_signals_but_no_filled_signal_in_this_mother']]
cp=next(Path(p)for p in f['source_sha256']if p.endswith('C10-FIRST_OPPORTUNITIES.json'));cr=read(cp);c=f['C10_July_August_2025'];assert Counter(z['status']for z in cr)==c['statuses']
assert len(cr)==len({(z['first_market_qualified']['sid'],z['first_market_qualified']['offered_context'])for z in cr})==2241
for z in cr:
 m=z['first_market_qualified'];assert m['ACT_on'] and m['market_permission']
 if z['first_actual_fill']:
  assert z['source_context']==m['offered_context'] and z['status']=='actually_funded_same_context'
  assert datetime.fromisoformat(z['first_actual_fill']).date().isoformat()>m['day']
  assert z['first_actual_fill'][:10]<=z['observation_cutoff']
  if z['market_context_ended_close']:assert z['first_actual_fill'][:10]<=z['market_context_ended_close']
 else:
  assert z['status']!='actually_funded_same_context'
  ended=z['market_context_ended_close'];assert bool(ended)==(z['status']=='unfunded_market_context_ended')
counts['semiconductor_mother']={'receipts':833,'stocks':len(sids),'stock_filled_in_mother':len(fsids),'unfunded_in_mother':len(sids-fsids),'terminal_next_open_outside_account':26}
counts['C10_context_mother']={'contexts':2241,'distinct_stocks':len({z['first_market_qualified']['sid']for z in cr}),'statuses':dict(Counter(z['status']for z in cr)),'not_all_executable_or_censored':True}
# Independent layer arithmetic; no importing the agent aggregation.
expected=read(ROOT/'loss_correction/SUMMARY.json');check_sha(read(ROOT/'loss_correction/SOURCE_SHA256.json'))
sets=[]
for sub,suff in [('baseline_readonly',''),('analysis','_R0')]:
 for cell,ls in read(OLD/'g-s-C-R0-continuous-january-v1-20261102'/sub/'ALL_LAYERS.json').items():sets.append(('2022Jan',cell+suff,ls))
for cell in ['C10','C20','C10_R0','C20_R0']:sets.append(('2025JulAug',cell,read(OLD/'g-s-C-August-continuation-v1-20261102/analysis'/f'{cell}-LAYERS.json')))
layer_stats=[]
for period,cell,ls in sets:
 x=next(x for x in expected if x['period']==period and x['cell']==cell);assert len(ls)==len({z['layer']for z in ls})
 assert len(ls)==x['layers']
 for z in ls:
  assert abs(D(z['total_contribution'])-sum((D(z[k])for k in ['realized_trade_PNL','unrealized_net_buy_cost','booked_dividend_income']),D(0)))<D('1e-20')
 closed=[z for z in ls if z['remaining_qty']==0];opened=[z for z in ls if z['remaining_qty']!=0];neg=sorted((D(z['total_contribution'])for z in closed if D(z['total_contribution'])<0));pos=[D(z['total_contribution'])for z in closed if D(z['total_contribution'])>0]
 assert (len(closed),len(opened),len(neg),len(pos))==(x['closed'],x['open'],x['negative_closed'],x['positive_closed'])
 loss=-sum(neg,D(0));gross=sum((D(z['buy_gross'])for z in ls),D(0));opencon=sum((D(z['total_contribution'])for z in opened),D(0))
 for key,v in [('buy_gross',gross),('negative_closed_amount',loss),('positive_closed_amount',sum(pos,D(0))),('open_layer_contribution',opencon),('all_contribution',sum(pos,D(0))-loss+opencon),('closed_negative_to_all_buy_gross_pct',100*loss/gross),('largest_5_negative_share_pct',-100*sum(neg[:5],D(0))/loss)]:assert abs(D(x[key])-v)<D('1e-20'),(period,cell,key)
 assert min(100*D(z['total_contribution'])/D(z['buy_cost'])for z in closed)==D(x['worst_closed_return_pct'])
 for lv in [10,20,30]:
  bad=[z for z in closed if 100*D(z['total_contribution'])<=-lv*D(z['buy_cost'])];assert len(bad)==x[f'loss_ge_{lv}_pct_count'];assert -sum((D(z['total_contribution'])for z in bad),D(0))==D(x[f'loss_ge_{lv}_pct_amount'])
 layer_stats.append({'period':period,'cell':cell,'layers':len(ls),'distinct_stocks':len({z['sid']for z in ls}),'closed_negative_layers':len(neg),'closed_ge30_loss_layers':x['loss_ge_30_pct_count'],'booked_dividends_in_closed_layers':str(sum((D(z['booked_dividend_income'])for z in closed),D(0))),'open_layer_contribution_is_not_pure_unrealized':True})
record={'passed_arithmetic':True,'provenance_issues':issues,'provenance_resolved':resolved,'files_sha_verified':len(sources),'coverage':counts,'layers':layer_stats,'financial_events':0,'not_claimed':['raw stock-level canonical generation independently recomputed','new continuous strategy profitability','unique stock episodes inferred from stock-day counts','all unfunded offers were executable or right censored'],'review_notes':['Coverage CP1 sums are stock-days, not distinct events/stocks/independent samples. OLD924 has only11industries and canonicalCP1 missing.','Semis833 mother is confirmed-stage canonicalCP1 stock-day events;105 stocks without a fill within that mother does not prove never held through another role.','C10 mother2241 stock/context groups spans1577 stocks;107 ended,2001 still-context-active,133 funded. Context active does not imply executable stock proof at cutoff.','Loss layer is not a campaign or independent failure. Closed means zero remaining shares, total contribution includes booked dividends that may be unpaid. Open total may include partial realized PNL.','Negative loss/purchase cash is a descriptive turnover denominator, not account drawdown or causal prediction deterioration.']}
(OUT/'NEW_AGGREGATES_AUDIT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed_arithmetic':True,'provenance_issues':issues,'files_sha_verified':len(sources),'datasets':len(layer_stats)},ensure_ascii=False))
