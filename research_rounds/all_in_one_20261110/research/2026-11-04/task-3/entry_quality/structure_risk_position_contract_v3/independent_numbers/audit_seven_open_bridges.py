"""Seven fixed original OPEN bridges; source rows and arithmetic, no account replay."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib
import pandas as pd
OUT=Path(__file__).resolve().parent;V3=OUT.parent;ENTRY=V3.parent;SRC={};CHECKS=[];Z=D(0)
def read(p):
 p=Path(p);b=p.read_bytes();SRC[str(p)]=hashlib.sha256(b).hexdigest()
 if '.jsonl'in p.name:return [json.loads(x)for x in gzip.decompress(b).splitlines()]
 return json.loads(gzip.decompress(b)if p.suffix=='.gz'else b)
def sha(p):p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();SRC[str(p)]=h;return h
def check(n,x):CHECKS.append({'name':n,'pass':bool(x)});assert x,n
def money(n,a,b):check(n,abs(D(str(a))-D(str(b)))<=D('1e-20'))
bridge=read(V3/'open_prefix/SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json')
manifest_path='/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
manifest={r['symbol']:r for r in read(manifest_path)}
for p,h in bridge['sources'].items():check('bridge source SHA '+p,sha(p)==h)
check('bridge producer source stable',sha(V3/'open_prefix/read_original_open_prefix.py')==bridge['script_sha256'])
card=V3/'designer/MINIMUM_MATH_CONTRACT.md';sha(card);cardtext=card.read_text()
check('G2 current contract uses boundary below market and 0.64 common shock', 'b_i=min(Z_i' in cardtext and 'X_i=b_i·.64·(1−s)' in cardtext)
cache={};books={};daily={};TABLE=[]
for b in bridge['results']:
 w,at=b['window'],b['next_OPEN'];day=at[:10];pair=ENTRY/'trend_exit_controls_v1/runs/BASELINE'/w/'pair'
 if w not in books:books[w]=read(pair/'B.json.gz');daily[w]=read(pair/'daily.jsonl.gz')
 book=books[w];pre=max((x for x in daily[w]if x['at']<at and x['at'][:10]<day),key=lambda x:x['at'])
 check(at+': exact previous native CLOSE components',b['previous_CLOSE']==pre['at'] and all(b['previous_daily_components'][k]==pre[k]for k in b['previous_daily_components']))
 check(at+': no ignored prior cash/pending components',all(D(pre[k])==0 for k in ['order_reserved','settlement_locked','payable','sale_receivable']))
 first=next((n for n,a in enumerate(book['audit'])if a['kind']=='reserve'and a.get('at')==at),None)
 check(at+': cutoff is first actual new reserve',first==b['first_new_reserve_audit_index'])
 before=[(n,a)for n,a in enumerate(book['audit'][:first if first is not None else len(book['audit'])])if pre['at']<str(a.get('at')or a.get('receipt',{}).get('at')or a.get('receivable',{}).get('ex_at')or'')<=at]
 check(at+': complete original prefix event indices and no hidden CA/cash actions',[n for n,_ in before]==b['original_prefix_event_indices'] and all(a['kind']in ['fill','settle']for _,a in before) and not b['CA_or_other_event_kinds'])
 sells=[(n,a['receipt'])for n,a in before if a['kind']=='fill'];settles=[(n,a['settlement'])for n,a in before if a['kind']=='settle']
 check(at+': actual sell receipts exact',all(t['side']=='sell'for _,t in sells)and[{'audit_index':n,'receipt':t,'net_sale':str(D(t['gross_cny'])-D(t['fees_cny']))}for n,t in sells]==b['actual_sells'])
 check(at+': actual settlement receipts exact',[{'audit_index':n,**s}for n,s in settles]==b['actual_settlements'] and all(not s['debit']for _,s in settles))
 cash=D(pre['available'])+sum((D(s['cny_amount'])for _,s in settles),Z);net=sum((D(t['gross_cny'])-D(t['fees_cny'])for _,t in sells),Z)
 money(at+': all sale proceeds actually settled',sum((D(s['cny_amount'])for _,s in settles),Z),net);money(at+': available cash after actual settles',b['cash_after_original_settles'],cash)
 q0=pre['positions'];sold={sid:sum(t['shares']for _,t in sells if t['security_id']==sid)for sid in q0};q={sid:n-sold[sid]for sid,n in q0.items()}
 check(at+': all original stocks retained in bridge rows',{r['sid']for r in b['rows']}==set(q0))
 beforemark=aftermark=openmark=Z
 for row in b['rows']:
  sid=row['sid'];check(at+'/'+sid+': actual remaining q after only actual sells',row['previous_qty']==q0[sid]and row['actual_sold_before_prefix']==sold[sid]and row['prefix_qty']==q[sid])
  if sid not in cache:
   m=manifest[sid];path=next(p for p in m['source_sha256']if p.endswith('/signal.parquet'))
   check(sid+': quoted source is same frozen original source',path in bridge['sources']and m['source_sha256'][path]==bridge['sources'][path]);cache[sid]=pd.read_parquet(path,columns=['raw_close','raw_open'])
  f=cache[sid];past=f.loc[:pre['at'][:10],'raw_close'].dropna();price=D(str(past.iloc[-1]));money(at+'/'+sid+': original prior known raw mark',row['previous_known_raw_mark'],price)
  check(at+'/'+sid+': prior mark clock not future',row['mark_source_day']==str(past.index[-1].date())and row['mark_source_day']<=pre['at'][:10])
  beforemark+=D(q0[sid])*price;aftermark+=D(q[sid])*price
  if q[sid]:
   check(at+'/'+sid+': exact execution-day OPEN present',pd.Timestamp(day)in f.index and pd.notna(f.loc[pd.Timestamp(day),'raw_open'])and f.loc[pd.Timestamp(day),'raw_open']>0)
   op=D(str(f.loc[pd.Timestamp(day),'raw_open']));money(at+'/'+sid+': bridge uses actual raw OPEN, not CLOSE',row['exact_day_raw_OPEN'],op);openmark+=D(q[sid])*op
  else:check(at+'/'+sid+': no price invented for already sold position',row['exact_day_raw_OPEN']is None)
 for name,val in [('previous_inventory_rebuilt',beforemark),('native_known_mark_inventory_after_sells',aftermark),('exact_raw_OPEN_inventory_after_sells',openmark)]:money(at+': '+name,b[name],val)
 money(at+': previous total mark reconciles to original native inventory',beforemark,pre['inventory'])
 ar=D(pre['dividend_receivable']);money(at+': dividend AR unchanged at no-CA prefix',b['remaining_dividend_AR'],ar);money(at+': sale AR after real settlements',b['remaining_sale_AR'],Z)
 navnative=cash+aftermark+ar;navopen=cash+openmark+ar
 checkpoint=max((a for a in book['audit']if a['kind']=='risk_checkpoint'and a['at']<=pre['at']),key=lambda a:a['at']);check(at+': exact original ACT checkpoint',b['ACT_checkpoint']==checkpoint)
 peak=D(checkpoint['peak']);money(at+': ACT peak unchanged at OPEN',b['ACT_peak'],peak)
 An=max(Z,navnative-D('.8')*peak);Ao=max(Z,navopen-D('.8')*peak);Ln=D('.36')*aftermark;Lo=D('.36')*openmark
 for name,val in [('native_known_mark_NAV_prefix',navnative),('raw_OPEN_valued_NAV_prefix',navopen),('OPEN_minus_native_mark_bridge',openmark-aftermark),('A_native_domain',An),('A_OPEN_valuation_domain',Ao),('G2_lower_native_mark_domain',Ln),('G2_lower_OPEN_valuation_domain',Lo)]:money(at+': '+name,b[name],val)
 check(at+': lower bound rejects in both clearly separated valuation domains',Ln>An and Lo>Ao and b['native_domain_lower_exceeds_A']and b['OPEN_domain_lower_exceeds_A']and b['grant_conclusion']=='DENY_ZERO_ALREADY_EXISTING_G2_LOWER_EXCEEDS_A'and not b['errors'])
 TABLE.append({'window':w,'actual_OPEN':at,'native_inventory':str(aftermark),'native_NAV':str(navnative),'native_A':str(An),'native_G2_lower':str(Ln),'OPEN_inventory':str(openmark),'OPEN_NAV':str(navopen),'OPEN_A':str(Ao),'OPEN_G2_lower':str(Lo),'grant_quantity_at_original_prefix':0})
res={'status':'PASS_SEVEN_ORIGINAL_OPEN_LOWER_BOUND_BRIDGES','checks':CHECKS,'rows':TABLE,'source_stock_series_checked':len(cache),'source_sha256':SRC,'mathematical_scope':'With b_i<=Z_i<=M_i and G2 quote<=.64M, original existing inventory alone has loss at least .36*inventory before fees/request locks. This is a necessary-rejection witness, not full Omega or a replacement account. Both native last-known-mark domain and exact-date raw-OPEN domain are separately reconciled; actual sells/settles occur before the cutoff.','not_claimed':['New strategy from-flat portfolio path','Complete Phi/Lambda/sector T or liquidity simulation','Economic performance or universal falsification of position sizing','Historical legal 20% price limit or worst-loss guarantee'],'new_accounts':0,'new_models':0,'new_parameter_sweeps':0,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(OUT/'SEVEN_ACTUAL_OPEN_BRIDGE_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':res['status'],'checks':len(CHECKS),'series':len(cache),'q':[0]*len(TABLE)},ensure_ascii=False))
