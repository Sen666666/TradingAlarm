"""C10 only. Pure reads of audited saved JSON; no runner/finance import."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
NEW=W/'g-s-C-R0-continuous-july-v1-20261102';OLD=W/'g-s-C-month-continuation-20261102'
Z=D(0);EPS=D('0.00000000001');READS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);assert '/runs/C_BATCH20/' not in str(p) and '/runs/2025_26-C_BATCH20/' not in str(p) and 'C20_' not in p.name
 READS[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,default=str,indent=2)+'\n')
def eq(a,b):assert abs(a-b)<EPS,(a,b)
def key(z):return (z['sid'],z['signal_at'],z['role'],z['pool'])
def totals(rows):
 return {k:sum((D(z[k]) for z in rows),Z) for k in ['realized_trade_PNL','unrealized_net_buy_cost','booked_dividend_income','total_contribution','buy_gross','all_actual_fees']}
def main():
 auditfile=Path('/tmp/R0-continuous-independent-20261102/FINAL_AUDIT.json');audit=read(auditfile)
 assert audit['verdict'].startswith('PASS_C10_COMPLETE_JULY')
 ll={'OLD':read(OLD/'july_end_analysis/ALL_LAYERS.json')['2025_26-C10'],'R0':read(NEW/'analysis/ALL_LAYERS.json')['C10']}
 result={'OLD':next(x for x in read(OLD/'july_end_analysis/RESULTS.json') if x['arm']=='2025_26-C10'),'R0':next(x for x in read(NEW/'analysis/RESULTS.json') if x['mode']=='C10')}
 metadata=read(OLD/'inputs/2025_26/metadata.json');sectors={x['sector']:x['name'] for x in read(OLD/'july_end_analysis/MARKET_SECTORS.json')};assert len(sectors)==90
 risk=read(NEW/'analysis/AUTHORIZATION_RISK_BRIDGES.json')['C10'];riskorders={r['order']:r for r in risk['rows'] if r['order'] is not None};assert len(riskorders)==sum(r['order'] is not None for r in risk['rows'])
 finals={};checks={'OLD':read(OLD/'july_end_analysis/ARTIFACT_SHA256.json'),'R0':{z['file']:z['sha256'] for z in read(NEW/'analysis/VERIFICATION.json')['checks']}}
 for mode,root,arm in [('OLD',OLD,'2025_26-C10'),('R0',NEW,'C10')]:
  path=root/'runs'/arm/'2025-07-31-CLOSE.json'
  expected=checks[mode].get(str(path)) if mode=='R0' else checks[mode].get(str(path.relative_to(OLD)))
  assert expected and sha(path)==expected,'audited final saved JSON mismatch'
  x=read(path);assert x['last_completed']=='2025-07-31 15:10:00+08:00';finals[mode]=x
  eq(D(x['account']['balance']['nav']),D(result[mode]['NAV']))
  for z in ll[mode]:
   a=x['account'];m=a['capital_meta'][str(z['layer'])];s=a['supports'][m['order']];receipt=s.get('receipt') or {}
   z.update(name=metadata[z['sid']]['name'],industry=sectors[z['sector']],canonical_receipt=receipt.get('event_id'),receipt_source=receipt.get('source'),original_epoch=s['original_intent'].get('epoch'),all_actual_fees=D(z['buy_fee'])+sum((D(v['fee_cny']) for v in z['actual_sell_parts']),Z),R0_authorization=riskorders.get(m['order']) if mode=='R0' else None)
   eq(D(z['realized_trade_PNL'])+D(z['unrealized_net_buy_cost'])+D(z['booked_dividend_income']),D(z['total_contribution']))
  eq(totals(ll[mode])['total_contribution'],D(result[mode]['NAV'])-1000000);eq(totals(ll[mode])['all_actual_fees'],D(result[mode]['fees']))
 maps={m:{key(z):z for z in rs} for m,rs in ll.items()};assert all(len(maps[m])==len(ll[m]) for m in ll)
 entries=[]
 for k in sorted(maps['OLD'].keys()|maps['R0'].keys()):
  a=maps['OLD'].get(k);b=maps['R0'].get(k);z=a or b
  category='new_actual_entry' if a is None else 'old_actual_entry_absent' if b is None else 'matched_smaller' if b['initial_qty']<a['initial_qty'] else 'matched_larger' if b['initial_qty']>a['initial_qty'] else 'matched_equal_quantity'
  A=totals([a]) if a else {f:Z for f in totals([])};B=totals([b]) if b else {f:Z for f in totals([])}
  entries.append(dict(key=k,sid=z['sid'],name=z['name'],sector=z['sector'],industry=z['industry'],opened=z['opened'],signal_at=z['signal_at'],category=category,old_layer=a,new_layer=b,canonical_entry_equal=(a['canonical_receipt'],a['receipt_source'],a['original_epoch'],a['purpose'],a['opened'])==(b['canonical_receipt'],b['receipt_source'],b['original_epoch'],b['purpose'],b['opened']) if a and b else None,OLD=A,R0=B,delta={f:B[f]-A[f] for f in A},new_R0_C_authorization_present=bool(b and b['R0_authorization'])))
 save('ENTRY_BRIDGE.json',entries)
 groups=defaultdict(list)
 for e in entries:groups[e['category']].append(e)
 catrows={k:dict(entries=len(rs),stocks=len({r['sid'] for r in rs}),R0_C_authorized_entries=sum(r['new_R0_C_authorization_present'] for r in rs),canonical_entry_mismatch=sum(r['canonical_entry_equal'] is False for r in rs),delta={f:sum((z['delta'][f] for z in rs),Z) for f in totals([])}) for k,rs in groups.items()}
 sids={m:{z['sid'] for z in rs} for m,rs in ll.items()};stocks=[]
 for sid in sorted(sids['OLD']|sids['R0']):
  rs=[e for e in entries if e['sid']==sid];z=rs[0]
  stocks.append(dict(sid=sid,name=z['name'],sector=z['sector'],industry=z['industry'],participation='new_stock' if sid not in sids['OLD'] else 'old_stock_absent' if sid not in sids['R0'] else 'both',OLD=totals([l for l in ll['OLD'] if l['sid']==sid]),R0=totals([l for l in ll['R0'] if l['sid']==sid]),delta={f:sum((e['delta'][f] for e in rs),Z) for f in totals([])}))
 stocks.sort(key=lambda z:z['delta']['total_contribution'],reverse=True);save('STOCK_BRIDGE.json',stocks)
 sectorsout=[]
 for sec,name in sectors.items():
  rs=[e for e in entries if e['sector']==sec]
  sectorsout.append(dict(sector=sec,industry=name,OLD=totals([l for l in ll['OLD'] if l['sector']==sec]),R0=totals([l for l in ll['R0'] if l['sector']==sec]),delta={f:sum((e['delta'][f] for e in rs),Z) for f in totals([])}))
 save('INDUSTRY_BRIDGE.json',sorted(sectorsout,key=lambda z:z['R0']['total_contribution']))
 net=D(result['R0']['NAV'])-D(result['OLD']['NAV']);pnl={k:D(result['R0']['pnl'][k])-D(result['OLD']['pnl'][k]) for k in ['realized_actual_sales_net_buy_and_sell_fees','unrealized_mark_minus_remaining_net_buy_cost','booked_dividends']}
 eq(sum(pnl.values(),Z),net)
 fee_saved=D(result['OLD']['fees'])-D(result['R0']['fees'])
 for rows in [entries,stocks,sectorsout]:eq(sum((r['delta']['total_contribution'] for r in rows),Z),net)
 eng={m:[z for z in rs if z['sector']=='URFI881268'] for m,rs in ll.items()};cohorts=[]
 for day in sorted({z['opened'][:10] for rs in eng.values() for z in rs}):
  A=[z for z in eng['OLD'] if z['opened'][:10]==day];B=[z for z in eng['R0'] if z['opened'][:10]==day]
  cohorts.append(dict(entry_day=day,OLD=totals(A),R0=totals(B),OLD_layers=len(A),R0_layers=len(B),OLD_stocks=[z['sid'] for z in A],R0_stocks=[z['sid'] for z in B]))
 j23={m:[z for z in eng[m] if z['opened'][:10]=='2025-07-23'] for m in eng}
 assert len(j23['R0'])==7 and totals(j23['R0'])['buy_gross']==D('487450.603500')
 assert next(z['initial_qty'] for z in j23['R0'] if z['sid']=='000680.SZ')==1600
 originalfive={z['sid'] for z in j23['OLD']};samefive=[z for z in j23['R0'] if z['sid'] in originalfive];backfill=[z for z in j23['R0'] if z['sid'] not in originalfive]
 daily={'OLD':read(OLD/'july_end_analysis/DAILY.json')['2025_26-C10'],'R0':read(NEW/'analysis/DAILY.json')['C10']}
 j23close={m:next(z for z in rs if z['day']=='2025-07-23') for m,rs in daily.items()}
 engproof=dict(all_engineering_layers=eng,cohorts=cohorts,July23_original_five_stock_ids=sorted(originalfive),July23_original_five_OLD=totals(j23['OLD']),July23_original_five_R0=totals(samefive),July23_backfill_R0=totals(backfill),July23_backfill_stocks=[z['sid'] for z in backfill],July23_close={m:dict(NAV=z['NAV'],engineering=next(s for s in z['industries'] if s['sector']=='URFI881268')) for m,z in j23close.items()})
 save('ENGINEERING_REMAINING_LOSS.json',engproof)
 selected={z['sid'] for z in stocks[:5]+stocks[-5:]}|{z['sid'] for z in eng['R0']}
 evidence={m:dict(final_saved_json=str((NEW if m=='R0' else OLD)/'runs'/('C10' if m=='R0' else '2025_26-C10')/'2025-07-31-CLOSE.json'),decisions=[dict(at=v['at'],certificate_id=v.get('certificate',{}).get('certificate_id'),selected_trace=[t for t in v['projection']['trace'] if t['sid'] in selected],selected_Q={s:q for s,q in v['projection']['Q'].items() if s in selected},D=v['projection']['D']) for v in x['results'] if 'projection' in v],selected_rejections=[r for r in x['account']['rejections'] if r['sid'] in selected],selected_layers=[z for z in ll[m] if z['sid'] in selected]) for m,x in finals.items()}
 save('ACTUAL_CHAIN_EVIDENCE.json',evidence)
 bridge=dict(NAV_OLD=result['OLD']['NAV'],NAV_R0=result['R0']['NAV'],NAV_difference=net,net_pnl_difference=pnl,fees_already_included=True,alternative_gross_price_difference=net-pnl['booked_dividends']-fee_saved,alternative_fee_saving_add_once=fee_saved,dividend_receivable_difference=pnl['booked_dividends'],layer_category_differences=catrows,OLD_layers=len(ll['OLD']),R0_layers=len(ll['R0']),union_entry_keys=len(entries),stock_union=len(stocks),old_funded_stocks=len(sids['OLD']),R0_funded_stocks=len(sids['R0']),new_stocks=sorted(sids['R0']-sids['OLD']),absent_old_stocks=sorted(sids['OLD']-sids['R0']),positive_stock_deltas=sum((z['delta']['total_contribution'] for z in stocks if z['delta']['total_contribution']>0),Z),negative_stock_deltas=sum((z['delta']['total_contribution'] for z in stocks if z['delta']['total_contribution']<0),Z),remaining_R0_net_loss=1000000-D(result['R0']['NAV']))
 save('EXACT_BRIDGE.json',bridge)
 assert all(sha(p)==h for p,h in READS.items()),'read-only source changed'
 save('READ_INPUTS.json',READS)
 save('CHECKS.json',dict(passed=True,financial_events_executed=0,financial_runner_imports=0,active_C20_files_read=0,originals_modified=False,source_hashes_unchanged=True,all_stock_industry_entry_equity_and_fees_bridges=True,tolerance_CNY=str(EPS),Jul23_continuous_7_stocks_487450_6035_Shantui1600=True,all_industries=90,all_entry_keys=len(entries),independent_audit_sha256=sha(auditfile)))
 print(json.dumps(bridge,default=str,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
