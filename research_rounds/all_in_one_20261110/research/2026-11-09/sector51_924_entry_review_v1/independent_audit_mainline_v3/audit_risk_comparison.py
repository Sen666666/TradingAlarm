"""Independent M3 risk, matched-date comparisons, original securities cohort, ex-post OHLC diagnosis."""
from pathlib import Path
O=Path(__file__).resolve().parent
exec(compile((O/'reconcile_actual_ledger.py').read_text().split('for row in ledger:')[0],str(O/'reconcile_actual_ledger.py'),'exec'),globals())
floors=read(run/'ADD_FLOOR_RISK.json');rb={(r['day'],r['sid'],r['cp_id']):r for r in floors};risks=[];prior=None;diagnostics=[]
for dt in sorted(ld):
 for tr in od.get(dt,[]):
  s=tr['sid'];z=raw[s].loc[pd.Timestamp(dt)]
  if tr['side']=='BUY_ADD':
   hs=[h for h in hd.get(prior,[]) if h['round_id']==tr['round_id']];ifl=next(D(h['protection_signal']) for h in hs if h['kind']=='SEED');cp=cpcreated[tr['cp_id']];fl=max(ifl,D(cp['candidate']));p=fl/price(s,dt,'adjustment_factor')*D('.9995');q=tr['qty'];cost=-D(tr['cash_delta']);loss=cost-(q*p-fee(s,dt,q,p,'sell'));r=rb[(dt,s,tr['cp_id'])]
   for k,v in dict(known_protection_signal=fl,hypothetical_raw_sell=p,buy_all_in=cost,incremental_known_floor_loss=loss,pre_add_close_net=D(tr['close_net']),pre_add_open_net=D(tr['open_net'])).items():equal('ADD_floor_risk_'+k,D(r[k]),v,tr['order_seq'])
   equal('ADD_floor_risk_not_profit_covered',r['not_profit_covered'],loss>D(tr['open_net']),tr['order_seq']);risks.append(dict(day=dt,sid=s,sector51=mapping[s],qty=q,pre_add_net=tr['open_net'],new_principal=str(cost),known_floor_loss=str(loss),risk_exceeds_old_profit=loss>D(tr['open_net'])))
  if tr['side'].startswith('BUY'):
   prev=raw[s][raw[s].index<pd.Timestamp(dt)].iloc[-1];diagnostics.append(dict(day=dt,sid=s,sector51=mapping[s],side=tr['side'],qty=tr['qty'],price=tr['price'],raw_OPEN=str(z.raw_open),raw_HIGH=str(z.raw_high),raw_LOW=str(z.raw_low),raw_CLOSE=str(z.raw_close),raw_volume=str(z.raw_volume),prev_observed_close=str(prev.raw_close),prev_observed_day=str(prev.name.date()),open_pct_change=str(100*(D(str(z.raw_open))/D(str(prev.raw_close))-1)),oneprice=bool(z.raw_open==z.raw_high==z.raw_low==z.raw_close),proxy_above_high=D(tr['price'])>D(str(z.raw_high)),cash=str(-D(tr['cash_delta']))))
 prior=dt
fixed=pd.read_csv(P.parent.parent/'2026-11-06/entry_state_selection_v1/momentum_persistence_breadth_v1/FIXED_ROSTER.csv') if False else pd.read_csv('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/momentum_persistence_breadth_v1/FIXED_ROSTER.csv');broker=set(fixed.loc[fixed.sector_name.eq('证券'),'symbol']);signals=[r for r in candidates if r['phase']=='CLOSE' and r['day'] in ['2024-09-06','2024-09-09'] and r['sid'] in broker and r['event'] in ['A','B']];filled=[r for r in orders if r['side']=='BUY_SEED' and r['signal_day'] in ['2024-09-06','2024-09-09'] and r['sid'] in broker];closed=[r for r in filled if attempts[r['round_id']]['final_qty']==0];pnl=sum((D(attempts[r['round_id']]['cashflow'])+D(attempts[r['round_id']]['dividend']) for r in closed),D(0));cohort=dict(signals=len(signals),actual=len(filled),not_entered=len(signals)-len(filled),closed=len(closed),unfinished=len(filled)-len(closed),closed_net=str(pnl));equal('original_35_securities_cohort_count',len(signals),35,'all');equal('original_securities_cohort_30_closed',len(closed),30,'all');equal('original_securities_cohort_closed_net',pnl,D('-237.9925290027000'),'all')
baseline=P/'mainline_candidate_v3_core_reference/m2_fact_extension_20241008/account_20241008';bl={r['day']:r for r in read(baseline/'DAY_LEDGER.json')};bs={(r['day'],r['sector51']):r for r in read(baseline/'SECTOR_DAILY.json')};compare=[];sectorcompare=[];keydays=['2024-09-23','2024-09-27','2024-09-30','2024-10-08']
for dt in keydays:
 a=ld[dt];b=bl[dt];compare.append(dict(day=dt,M2=b,M3=a,NAV_difference=str(D(a['NAV'])-D(b['NAV'])),fee_difference=str(D(a['fees_paid'])-D(b['fees_paid']))))
 for s in sectors:
  a=next(r for r in sd[dt] if r['sector51']==s);b=bs[(dt,s)];sectorcompare.append(dict(day=dt,sector51=s,M2_value=b['market_value'],M3_value=a['market_value'],M2_pct=b['account_weight_pct'],M3_pct=a['account_weight_pct'],M2_pnl=b['marked_net_pnl'],M3_pnl=a['marked_net_pnl'],M3_seed_fills=a['seeds_filled'],M3_ADD_fills=a['adds_filled']))
peak=D(1200000);mdd=D(0)
for r in ledger:peak=max(peak,D(r['NAV']));mdd=max(mdd,1-D(r['NAV'])/peak)
report=dict(result='PASS' if not errors else 'FAIL',checks=dict(checks),error_count=len(errors),errors=errors,ADD_count=len(risks),risk_exceeds_prior_profit=sum(r['risk_exceeds_old_profit'] for r in risks),max_single_known_floor_loss=max((D(r['known_floor_loss']) for r in risks),default=D(0)),close_max_drawdown_percent=str(mdd*100),securities_cohort=cohort,matched_accounts=compare,limitations=['New principal, not profit financing; protection-price net-sale hypothetical is not guaranteed or maximum loss.','Per-ADD losses from different dates cannot be summed as simultaneous portfolio risk.','OPEN+5bp is a cost proxy; daily H/L/volume are ex-post only and cannot certify auction fills or impossibility.','Both account paths now have actual 10/8 endpoints; no future M3 extension.'])
for name,data in [('RISK_COMPARISON_AUDIT',report),('INDEPENDENT_ADD_RISK',risks),('INDEPENDENT_KEYDAY_ALL50',sectorcompare),('INDEPENDENT_BUY_EXECUTION_DIAGNOSTICS',diagnostics)]:
 (O/(run.name+'_'+name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['checks','matched_accounts']},ensure_ascii=False,default=str))
