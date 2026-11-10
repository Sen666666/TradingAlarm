"""Join existing four-stock descriptive metrics to saved original actions only."""
from pathlib import Path
import csv,json,collections,hashlib
O=Path(__file__).resolve().parent
def rows(p):return list(csv.DictReader(Path(p).open()))
def truth(x):return str(x).lower()in ['true','1','1.0']
def dec(s,default=None):
 try:return json.loads(s)
 except (TypeError,ValueError):return default
def outcsv(path,rr):
 fields=list(dict.fromkeys(k for r in rr for k in r))
 with path.open('w',newline='')as h:
  w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rr)
allrows=[];counts=[];inputhash={}
for sid in ['000620.SZ','002583.SZ','601019.SH','000547.SZ']:
 mp=O/'metrics'/(sid+'.csv');directory='case_links_yingxin_shandong'if sid in ['000620.SZ','601019.SH']else'case_links';lp=O/directory/(sid+'.csv')
 for p in [mp,lp]:inputhash[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 links={r['day']:r for r in rows(lp)};merged=[]
 for m in rows(mp):
  day=m['date'];l=links[day];cp=truth(m['CP_market_receipt']);lc=truth(l.get('CP_present',l.get('original_CP_receipt')));assert cp==lc,(sid,day,'CP mismatch')
  r=dict(m)
  if directory=='case_links':
   ff=dec(l['next_OPEN_original_MOBILE_fills'],[]);fund=dec(l['next_OPEN_original_MOBILE_funding'],[]);mi=dec(l['original_MOBILE_intents'],[])
   qty=sum(int(x['shares'])for x in ff);prices=';'.join(x['price']for x in ff);status=l['connection_status'];nextat=l['next_original_OPEN'];fundres=';'.join(x['result']for x in fund)
   intentcount=int(l['original_MOBILE_intent_count']);held=l['original_CLOSE_held_qty'];rid=l['original_canonical_CP_receipt_id'];role=bool('mobile'in dec(l['original_roles'],[]))
   budget=';'.join(x['budget']for x in mi);cap=';'.join(str(x['cap'])for x in mi)
  else:
   qty=int(l['next_OPEN_actual_mobile_shares']);prices=l['next_OPEN_actual_mobile_prices'];oldstatus=l['next_OPEN_status'];nextat=l['next_original_OPEN_at'];fundres=l['next_OPEN_original_mobile_results'];intentcount=int(l['original_mobile_intent_count']);held=l['original_qty_at_signal_CLOSE'];rid=l['CP1_id'];role=truth(l['original_mobile_role']);budget=l['original_intent_budget'];cap=l['original_intent_cap']
   if not cp:status='NO_ORIGINAL_CP_RECEIPT'
   elif qty:status='ORIGINAL_MOBILE_FILL'
   elif int(l['next_OPEN_other_core_shares'])>0 and not fundres:status='MOBILE_SKIPPED_AFTER_SAME_STOCK_CORE_RESERVED'
   elif 'REJECT'in oldstatus.upper():status='ORIGINAL_MOBILE_OPEN_REJECTED'
   else:status=oldstatus
   r['original_link_status_unmodified']=oldstatus
  r.update(original_mobile_role=role,original_mobile_intent_count=intentcount,original_CP_receipt_id=rid,original_held_qty_at_signal_CLOSE=held,original_mobile_gross_budget=budget,original_mobile_cap=cap,next_original_OPEN=nextat,original_mobile_next_OPEN_status=status,original_mobile_next_OPEN_funding_results=fundres,original_mobile_filled_shares=qty,original_mobile_filled_prices=prices)
  r['close_above_EMA20_description']=float(m['close_a'])>float(m['ema20_a'])
  r['EMA20_above_EMA60_description']=float(m['ema20_a'])>float(m['ema60_a'])
  r['EMA20_five_observation_slope_positive_description']=float(m['ema20_five_observation_slope_pct_per_observation'])>0
  r['relationships_are_not_a_new_entry_or_risk_rule']='True'
  # Preserve unmodified linkage columns separately for audits.
  r.update({'ledger__'+k:v for k,v in l.items()});merged.append(r)
 allrows.extend(merged);cps=[r for r in merged if truth(r['CP_market_receipt'])]
 counts.append({'sid':sid,'daily_rows':len(merged),'CP_receipts':len(cps),'original_mobile_intents':sum(r['original_mobile_intent_count']for r in cps),'outcomes':dict(collections.Counter(r['original_mobile_next_OPEN_status']for r in cps))})
outcsv(O/'ALL_DAILY_METRICS_AND_ORIGINAL_LINKS.csv',allrows)
cp=[r for r in allrows if truth(r['CP_market_receipt'])]
compactkeys=[k for k in allrows[0]if not k.startswith('ledger__')]
compact=[{k:r.get(k,'')for k in compactkeys}for r in cp]
outcsv(O/'MOBILE_SIGNAL_METRICS_AND_ORIGINAL_ACTIONS.csv',compact)
(O/'MOBILE_SIGNAL_METRICS_AND_ORIGINAL_ACTIONS.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n')
(O/'JOIN_COUNTS_AND_INPUTS.json').write_text(json.dumps({'case_counts':counts,'daily_rows':len(allrows),'CP_receipt_rows':len(cp),'inputs_sha256':inputhash,'no_strategy_or_account':True,'join':'Exact sid+original signal CLOSE; source action times remain subsequent outcomes, never metric inputs.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(counts,ensure_ascii=False))
