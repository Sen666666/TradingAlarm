"""Bounded follow-up: original saved mark helper, native trades/exits, current tags.
No account replay, new indicator, alternative mark engine, or industry aggregation.
"""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,json,gzip,hashlib,time
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0);EPS=D('.000001');started=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def near(a,b,label):assert abs(a-b)<EPS,(label,str(a),str(b))
def ser(x):
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return {k:ser(v) for k,v in x.items()}
 if isinstance(x,list):return [ser(v) for v in x]
 return x
binding=json.load(open(T/'attribution_2024_chain_v2/SOURCE_BINDING.json'));reader=Path(binding['original_price_reader']);assert sha(reader)==binding['original_price_reader_sha256']
sp=importlib.util.spec_from_file_location('already_reviewed_saved_mark_only',reader);A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)
summary=json.load(open(T/'attribution_2024_chain_v2/SUMMARY.json'));chains=json.load(open(T/'attribution_2024_chain_v2/NATIVE_STOCK_TRADE_CHAINS.json'))
result={'status':'PASS_BOUNDED_924_GROUP_BRIDGE_THREE_NATIVE_WITNESSES_CURRENT_TAGS','scope':'Reuses unchanged original audited saved A.price(raw_close) and current metadata. No new mark engine/reader, account, signals, backtest, industry aggregate re-review, or PIT certification. Three named witnesses only: native2024 trades/all pilot exit requests exact and actual exit_request evidence; no claim covering all illustrative stocks.','cases':{},'source_sha256':{str(reader):sha(reader)}}
for arm,p,name in [('No60','capacity_cost_guard_v1/runs/long-v1/arms/B/pair','B'),('D_GROSS10','market_gross_admission_native_v1/full-long-v1/pair','D_GROSS10')]:
 bp=T/p/(name+'.json.gz');dp=T/p/'daily.jsonl.gz';b=json.load(gzip.open(bp,'rt'));ds=[json.loads(x) for x in gzip.open(dp,'rt')];beg=next(x for x in ds if x['at'][:10]=='2024-09-23');end=next(x for x in ds if x['at'][:10]=='2024-10-08');old={x['id']:x for x in beg['layers']};last={x['id']:x for x in end['layers']};fin={x['id']:x for x in b['layers']}
 buys=[t for t in b['trades'] if t['side']=='buy' and '2024-09-23'<t['at'][:10]<='2024-10-08'];new={t['layer'] for t in buys};assert not old.keys()&new;assert set(last)==set(old)|new
 def w(l,d):return D(l['cash'])+D(l['dividend'])+D(l['qty'])*A.price(l['sid'],d)
 for r,date in [(beg,'2024-09-23'),(end,'2024-10-08')]:near(sum((D(x['qty'])*A.price(x['sid'],date) for x in r['layers']),Z),D(r['inventory']),(arm,date,'reused rawmark qty native inventory'))
 oldgain=sum((w(last[i],'2024-10-08')-w(l,'2024-09-23') for i,l in old.items()),Z);newgain=sum((w(last[i],'2024-10-08') for i in new),Z);near(oldgain+newgain,D(end['nav'])-D(beg['nav']),(arm,'924 old new NAV bridge'))
 for key,n,value in [('held_at_start_CLOSE',len(old),oldgain),('new_actual_fill_in_phase',len(new),newgain)]:assert summary[arm]['924_six_closes']['layer_groups'][key]['layers']==n;near(value,D(summary[arm]['924_six_closes']['layer_groups'][key]['wealth']),(arm,key,'group quote'))
 lifecycle=sum((D(fin[i]['cash'])+D(fin[i]['dividend']) for i in new),Z);assert all(fin[i]['qty']==0 for i in new)
 witnesses={}
 for sid in ['300085.SZ','601360.SH','002583.SZ']:
  tx=[t for t in b['trades'] if t['security_id']==sid and t['at'][:4]=='2024'];assert tx==chains[arm][sid]['actual_trades'],(arm,sid,'all trade dates/qty/prices/fees/source content exact')
  pilot=[e for e in b['audit'] if e['kind']=='pilot_layer_exit' and e.get('sid')==sid and e['at'][:4]=='2024'];assert pilot==chains[arm][sid]['all_2024_exit_requests'],(arm,sid,'all pilot requests exact')
  exits=[e for e in b['audit'] if e['kind']=='exit_request' and e.get('sid')==sid and e['at'][:4]=='2024']
  net=sum(((D(t['gross_cny']) if t['side']=='sell' else -D(t['gross_cny']))-D(t['fees_cny']) for t in tx),Z)
  # Three witnesses have no inventory at either post boundary and no2024 dividends.
  assert sid not in beg['positions'] and sid not in ds[-1]['positions']
  div=[e for e in b['audit'] if e['kind']=='dividend_accrual' and e['receivable']['security_id']==sid and e['receivable']['ex_at'][:4]=='2024'];assert not div
  near(net,D(chains[arm][sid]['phase_rows']['post_oct8'][0]['wealth']),(arm,sid,'witness original cash contribution'))
  witnesses[sid]=dict(name=A.META[sid]['name'],current_industry=A.META[sid]['industry'],trades_exact=len(tx),pilot_requests_exact=len(pilot),native_exit_requests=exits,trade_cash_net=net,actual_trades=[{k:t[k] for k in ['at','side','shares','price','gross_cny','fees_cny','reason']} for t in tx])
  if sid=='300085.SZ':
   req=next(e for e in exits if e['at']=='2024-10-10 15:10:00+08:00');sell=next(t for t in tx if t['side']=='sell');assert sell['at']=='2024-10-11 09:30:00+08:00'
   close=A.price(sid,'2024-10-10');cost=-sum((-D(t['gross_cny'])-D(t['fees_cny']) for t in tx if t['side']=='buy'),Z);q=sum(int(t['shares']) for t in tx if t['side']=='buy');sale_net=D(sell['gross_cny'])-D(sell['fees_cny'])
   witnesses[sid]['Oct10_CLOSE_to_next_OPEN']=dict(request_at=req['at'],fill_at=sell['at'],shares=q,raw_close=close,buy_cash=cost,CLOSE_marked_pnl=D(q)*close-cost,next_OPEN_net_minus_CLOSE_mark=sale_net-D(q)*close,multi_day_exit_delay=False)
 # Only tag matching, no new industry sums or PIT claim.
 tagrows=0
 for f in (T/'attribution_2024_chain_v2').glob(arm+'_*_ALL_STOCKS.json'):
  for r in json.load(open(f)):
   assert r['name']==A.META[r['sid']]['name'] and r['industry']==A.META[r['sid']]['industry'];tagrows+=1
 result['cases'][arm]=dict(six_close_held_layers=len(old),six_close_held_gain=oldgain,six_close_new_layers=len(new),six_close_new_gain=newgain,new_layer_final_lifecycle=lifecycle,current_metadata_stock_tag_rows_exact=tagrows,witnesses=witnesses)
 for p1 in [bp,dp]:result['source_sha256'][str(p1)]=sha(p1)
for sid in A.frames:
 p=Path(A.SM[sid]['refs']['facts']);h=sha(p);assert h==A.SM[sid]['output_sha256'][str(p)],('original manifest facts identity',sid);result['source_sha256'][str(p)]=h
meta=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');result['source_sha256'][str(meta)]=sha(meta)
for p in [T/'attribution_2024_chain_v2/NATIVE_STOCK_TRADE_CHAINS.json',T/'attribution_2024_chain_v2/SUMMARY.json',T/'attribution_2024_chain_v2/READOUT.txt']:result['source_sha256'][str(p)]=sha(p)
result['checker_sha256']=sha(__file__);result['elapsed_seconds']=time.monotonic()-started
(O/'FOLLOWUP_924_THREE_WITNESSES_REVIEW.json').write_text(json.dumps(ser(result),ensure_ascii=False,indent=2))
for a,v in result['cases'].items():print(a,'924 old/new',v['six_close_held_layers'],v['six_close_held_gain'],v['six_close_new_layers'],v['six_close_new_gain'],'newLifecycle',v['new_layer_final_lifecycle'],'tagrows',v['current_metadata_stock_tag_rows_exact']);print('three witness cash net',{s:x['trade_cash_net'] for s,x in v['witnesses'].items()})
print('PASS',result['elapsed_seconds'],'seconds')
