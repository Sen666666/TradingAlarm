from shared import *
from collections import Counter
T=time.monotonic();rs=csvrows(O/'full/unit-results.csv');us=read(O/'UNITS.json');U={u['unit_id']:u for u in us};RRs={(r['unit_id'],r['arm']):r for r in rs};aud={(x['unit_id'],x['arm']):x for x in gz(O/'full/audit.jsonl.gz')};cur=pd.read_parquet(O/'full/equity.parquet');summary=[];pairs=[];diffs=[];chains=[];unknown=[];sourcecost=[]
for sec in ['TECH','DRUG']:
 for st in ['base','delay1']:
  units=[u for u in us if u['sector']==sec and u['stress']==st];ctx=loadcase(sec,st);fr=Feed(sec,{u['symbol'] for u in units});log=ctx['logs'];buyorders={x['order_id'] for x in log if x['kind']=='reserve' and x.get('purpose')=='risk_restore'};actualfills=[x for x in log if x['kind']=='partial_event' and x['detail']['kind']=='actual_role_buy' and x['detail']['action']=='risk_restore'];currentcycle={};actual=defaultdict(list)
  for x in log:
   if x['kind']!='partial_event':continue
   e=x['detail'];s=e.get('sid')
   if e['kind']=='actual_role_buy':
    if e['action']=='initial':currentcycle[s]=e['receipt']['receipt_id'] if s not in currentcycle else currentcycle[s]
    else:actual[s,currentcycle[s]].append(e['receipt'])
   elif e['kind']=='actual_role_sell' and e['K']+e['R']==0:currentcycle.pop(s,None)
  for u in units:
   aid=u['unit_id'];a=aud.get((aid,'R'));rbuys=[f for f in a['fills'] if f['side']=='buy'] if a else [];pbuys=[f for f in actual[u['symbol'],u['cycle']] if f['at']>=u['seed_at']];sig=lambda fs:[(x['at'],int(x['shares']),D(x['gross_cny']),D(x['fees_cny'])) for x in fs];diffs.append(dict(unit_id=aid,sector=sec,stress=st,symbol=u['symbol'],name=u['name'],original_buys=len(pbuys),local_R_buys=len(rbuys),same_dates_qty_gross_fees=sig(pbuys)==sig(rbuys),original_buy_spend=sum((D(f['gross_cny'])+D(f['fees_cny']) for f in pbuys),Z),local_buy_spend=sum((D(f['gross_cny'])+D(f['fees_cny']) for f in rbuys),Z),initial_private_cash=u['seed_cash'],original= pbuys,local=rbuys))
   # The only future-blind opportunity clock is recorded P admission. Missing Q is unknown, never false.
   if u['actionable']:
    for d in ctx['ds']:
     day=d['at'][:10]
     if day<u['seed_at'][:10] or d['at']>=u['stop_signal'] or day>u['end_at'][:10]:continue
     ob=fr.obs(u['symbol'],day,u['group']);row=fr.row(u['symbol'],day)
     if ob['native'] and bool(row.i_buy):
      pa=ctx['pa'].get(d['at']);el=next((x for x in pa['decisions'][-1]['eligibility'] if x['security_id']==u['symbol']),None) if pa else None
      if el is None or el.get('q') is None:unknown.append(dict(unit_id=aid,at=d['at'],kind='fresh_I_but_original_P_Q_unknown'))
   for arm in ['R','G','N']:
    a=aud.get((aid,arm))
    if not a:continue
    for x in a['extra']:
     if x['kind']=='risk_close':
      for k in x['detail']['current_unknown']:unknown.append(dict(unit_id=aid,arm=arm,at=x['at'],kind=k))
      assert not(x['detail']['exit_locked'] and x['detail']['exit_reason']=='original_floor'),'Unwired original floor exit'
    if u['symbol'] in ['603256.SH','688331.SH','603259.SH']:
     for x in a['extra']:
      if x['kind']=='independent_risk_request':chains.append(dict(unit_id=aid,arm=arm,kind=x['kind'],at=x['at'],shares=x['shares'],B=x['B']))
     for f in a['fills']:chains.append(dict(unit_id=aid,arm=arm,kind=f['side'],at=f['at'],shares=f['shares'],price=D(f['gross_cny'])/int(f['shares']),fees=f['fees_cny']))
     for x in a['extra']:
      if x['kind']=='restore_application' and x['ok']:
       chains.append(dict(unit_id=aid,arm=arm,kind='accepted_signal',at=x['at'],floor=x['floor'],B=x['oldB']))
  for arm in ['R','G','N']:
   z=[RRs[u['unit_id'],arm] for u in units];asub=[aud[u['unit_id'],arm] for u in units if (u['unit_id'],arm) in aud];ns=lambda k:sum((D(x[k]) for x in z),Z);count=lambda k:sum(int(x[k]) for x in z);c=cur[cur.unit_id.isin([u['unit_id'] for u in units])&(cur.arm==arm)];postpos=sum((max(D(x['after_seed_profit']),Z) for x in z),Z);postneg=sum((min(D(x['after_seed_profit']),Z) for x in z),Z)
   summary.append(dict(sector=sec,stress=st,arm=arm,units=len(z),active_units=sum(x['actionable']=='True' for x in z),initial_equity=ns('initial_equity'),seed_equity=ns('seed_equity'),final_equity=ns('final_equity'),net_contribution=ns('net_contribution'),after_seed_profit=ns('after_seed_profit'),after_seed_positive=postpos,after_seed_negative=postneg,new_fees=ns('new_fees'),all_fees=ns('full_fees'),buy_fills=count('buys'),sell_fills=count('sells'),units_restored=sum(int(x['buys'])>0 for x in z),requests=count('new_risk_requests'),applications=count('applications'),accepted=count('accepted'),gate_rejected=count('gate_rejected'),budget_rejected=count('budget_rejected'),expired=sum(x['kind']=='buy_day_expiry' for a in asub for x in a['audit']),open_support_reject=sum(x['kind']=='open_support_or_factor_reject' for a in asub for x in a['extra']),credit_consumed=sum(x['kind']=='credit_consumed' for a in asub for x in a['extra']),held_closes=count('held_closes'),waiting_closes=count('waiting_closes'),inventory_cny_closes=ns('inventory_time'),terminal_claims=ns('terminal_claim'),terminal_held_units=sum(int(x['terminal_shares'])>0 for x in z),max_individual_drawdown_after_seed=max((D(x['max_drawdown_after_seed']) for x in z),default=Z),longest_wait_to_first_buy_market_closes=max([int((c[(c.unit_id==x['unit_id'])&(c['at']<x['first_restore'])]).shape[0]) for x in z if x.get('first_restore')] or [0])))
  for aa,bb in [('G','R'),('R','N'),('G','N')]:
   ds=[(u['unit_id'],D(RRs[u['unit_id'],aa]['final_equity'])-D(RRs[u['unit_id'],bb]['final_equity'])) for u in units];positive=[v for _,v in ds if v>Z];negative=[v for _,v in ds if v<Z];nzero=sum(v==Z for _,v in ds);assert len(positive)+len(negative)+nzero==len(units)
   pairs.append(dict(sector=sec,stress=st,comparison=aa+'-'+bb,units=len(units),positive_count=len(positive),negative_count=len(negative),equal_count=nzero,positive_amount=sum(positive,Z),negative_amount=sum(negative,Z),net=sum((v for _,v in ds),Z),top_positive=sorted(ds,key=lambda x:-x[1])[:3],top_negative=sorted(ds,key=lambda x:x[1])[:3]))
export(O/'ARM_SUMMARY.csv',summary);export(O/'PAIRED_DIFFERENCES.csv',[{k:v for k,v in x.items() if not k.startswith('top_')} for x in pairs]);save(O/'SUMMARY.json',dict(arms=summary,pairs=pairs,unknown_records=unknown,actual_P_vs_local_R=dict(same=sum(x['same_dates_qty_gross_fees'] for x in diffs),different=sum(not x['same_dates_qty_gross_fees'] for x in diffs)),seconds=time.monotonic()-T));save(O/'ACTUAL_P_vs_LOCAL_R.json',diffs);export(O/'ACTUAL_P_vs_LOCAL_R.csv',[{k:v for k,v in x.items() if k not in ['original','local']} for x in diffs]);export(O/'EXAMPLE_CHAINS.csv',sorted(chains,key=lambda x:(x['unit_id'],x['arm'],x['at'],x['kind'])));save(O/'POSTCHECK.json',dict(passed=True,unknown_records=unknown,original_floor_unwired=0,actual_source_vs_local_not_identical_expected=True,summary_seconds=time.monotonic()-T));print(json.dumps(H.encoded(dict(pairs=pairs,unknown=unknown,actual_P_vs_local_R=read(O/'SUMMARY.json')['actual_P_vs_local_R'])),ensure_ascii=False,indent=2))
