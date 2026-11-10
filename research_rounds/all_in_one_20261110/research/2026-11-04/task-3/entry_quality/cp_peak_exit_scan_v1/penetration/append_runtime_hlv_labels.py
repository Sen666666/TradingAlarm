"""Read raw runtime H/L/V and append ex-post partial-filter labels, no window call."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv,hashlib,json,math
import pandas as pd
O=Path(__file__).resolve().parent
M=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
P=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/economic-protocol.json')
C=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvsave(n,rr):
 with (O/n).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(clean(rr))
manifest=json.loads(M.read_text());protocol=json.loads(P.read_text());records=manifest['series'];records={r['series_id']:r for r in records} if isinstance(records,list) else records
assert protocol['daily_execution']['A']['reject_flat_day'] is True and protocol['participation_rate']=='.01'
source={str(M):sha(M),str(P):sha(P),str(C):sha(C)};frames={}
main=O/'MOBILE_DAILY_PENETRATION.json';before=sha(main);data=json.loads(main.read_text());saved={id(x):dict(x['summary']) for x in data}
for sid in {x['summary']['sid'] for x in data}:
 r=records[sid];p=Path(r['raw']['path']);assert sha(p)==r['raw']['sha256'];source[str(p)]=sha(p);f=pd.read_parquet(p);f['trade_date']=pd.to_datetime(f.trade_date);frames[sid]=f.set_index('trade_date')
for x in data:
 r=x['summary'];day=r['expost_next_market_day'];f=frames[r['sid']]
 z=dict(expost_runtime_next_HIGH=None,expost_runtime_next_LOW=None,expost_runtime_next_VOLUME=None,expost_runtime_next_AMOUNT=None,
  expost_runtime_flat_HL_proxy_reject=None,expost_runtime_volume_positive=None,expost_runtime_OPEN_matches_reference=None,
  expost_runtime_HLV_status='UNKNOWN_MISSING_EXACT_NEXT_RAW_BAR',expost_HLV_availability='AFTER_NEXT_SESSION_FULL_BAR_ONLY_NOT_CURRENT_SIGNAL_INPUT')
 if day is not None and pd.Timestamp(day) in f.index:
  b=f.loc[pd.Timestamp(day)];z.update(expost_runtime_next_HIGH=b.high,expost_runtime_next_LOW=b.low,expost_runtime_next_VOLUME=b.volume,expost_runtime_next_AMOUNT=b.amount,
   expost_runtime_flat_HL_proxy_reject=bool(b.high<=b.low),expost_runtime_volume_positive=bool(math.isfinite(float(b.volume)) and b.volume>0),
   expost_runtime_OPEN_matches_reference=r['expost_next_raw_OPEN'] is not None and D(str(b.open))==D(str(r['expost_next_raw_OPEN'])),
   expost_runtime_HLV_status='KNOWN_RAW_BAR_FLAT_REJECT_ONLY_NO_OTHER_EXECUTION_ASSESSMENT')
 r.update(clean(z));assert all(r[k]==v for k,v in saved[id(x)].items())
 x['expost_HLV_scope']='Full next-day H/L/V is retrospective. False flat_reject means this one filter does not reject; it does not establish availability, capacity, a real fill or line-price execution. No market.window or candidate fill was run.'
rows=[x['summary'] for x in data];cross=[r for r in rows if r['actual_first_CP_request_today']]
save('MOBILE_DAILY_PENETRATION.json',data);csvsave('MOBILE_DAILY_PENETRATION.csv',rows)
save('ACTUAL_FIRST_CP_TRIGGER_POINTS.json',cross);csvsave('ACTUAL_FIRST_CP_TRIGGER_POINTS.csv',cross)
groups=[];seen=set()
for r in cross:
 k=(r['sid'],r['day'],r['old_floor_adjusted'])
 if k in seen:continue
 seen.add(k);rr=[x for x in cross if (x['sid'],x['day'],x['old_floor_adjusted'])==k];groups.append(dict(**r,layers=[x['layer'] for x in rr],total_actual_qty=sum(x['qty_current_original'] for x in rr)))
save('SIX_ORIGINAL_STOCK_TRIGGER_EVENTS.json',groups)
case=[]
for day in ['2024-11-04','2024-11-05']:
 b=frames['002583.SZ'].loc[day];case.append(dict(day=day,raw_bar=b.to_dict(),H_le_L=bool(b.high<=b.low)))
code=C.read_text().splitlines()
save('HAINENGDA_HLV_PROXY_CHECK.json',dict(status='PASS_READ_ONLY_RAW_AND_PARTIAL_PROXY_RULE_CHECK',series='002583.SZ',runtime_record=records['002583.SZ'],raw_rows=case,
 protocol_daily_execution=protocol['daily_execution']['A'],protocol_participation_rate=protocol['participation_rate'],
 source_code_excerpt=[dict(line=i+1,source=code[i]) for i in range(44,64)],
 conclusion='Nov04 O=C=L=22.84 but H=26.15, so H>L. The original reject_flat_day filter does not reject this day. This does not prove any actual seller execution or a candidate exit before Nov05. O*.9995 is only a price reference. No window or candidate fill was called.',
 capacity_semantics='fast_market.py:60 uses int(min(mean of previous20 positive volumes * .01, full current-session volume)); no capacity quantity was reconstructed or used here.',source_sha256=source))
save('EXPOST_HLV_JOIN_RECEIPT.json',dict(status='PASS_EXPOST_RAW_JOIN_EXISTING_FIELDS_UNCHANGED',before_main_sha256=before,after_main_sha256=sha(main),rows=len(rows),flat_filter_reject_points=sum(r['expost_runtime_flat_HL_proxy_reject'] is True for r in rows),raw_OPEN_exact_matches=sum(r['expost_runtime_OPEN_matches_reference'] is True for r in rows),source_sha256=source,script_sha256=sha(Path(__file__)),new_accounts=0,new_models=0,new_backtests=0,market_window_calls=0,candidate_fills=0))
text=(O/'READOUT.md').read_text()
text+='\n## 追加：下一日完整HLV的事后标签\n\n主表附actual runtime raw源的下一日HIGH/LOW/VOLUME/AMOUNT，以及原单一`reject_flat_day`过滤标签；全部标AFTER_NEXT_SESSION_FULL_BAR_ONLY，不进入A/B信号。标签false只说明H≤L这一项不拒，不能推定其它可交易状态、容量或成交。容量源码为前20正量均值×.01与当天完整量的较小值；本次没有调用window或重算capacity/候选fill。\n\n海能达11/4原O=L=C=22.84，但H=26.15，V=472899434.99999994；11/5 O23/H23.7/L21.27/C22.32，V=448417365.00000006。11/4不是flat day，不能从O=C推导H=L，也不能据此认定原代理最早只能11/5卖。仍无法从日线证明22.82858或其它价为真实可成交价。原runtime manifest/raw SHA、protocol与源码45–64见HAINENGDA_HLV_PROXY_CHECK.json。\n'
(O/'READOUT.md').write_text(text)
(O/'PRE_HLV_SEAL_REFERENCE.json').write_bytes((O/'SEAL_RECEIPT.json').read_bytes())
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_FULL_14_LAYER_209_CLOSE_ORIGINAL_PENETRATION_WITH_EXPOST_HLV',readout_sha256=sha(O/'READOUT.md'),main_rows_sha256=sha(main),source_manifest_sha256=sha(O/'SOURCE_MANIFEST.json'),provenance_crosscheck_sha256=sha(O/'STRUCTURAL_OWNER_PROVENANCE_CROSSCHECK.json'),expost_join_sha256=sha(O/'EXPOST_NEXT_OPEN_JOIN_RECEIPT.json'),expost_HLV_join_sha256=sha(O/'EXPOST_HLV_JOIN_RECEIPT.json'),HAINENGDA_HLV_sha256=sha(O/'HAINENGDA_HLV_PROXY_CHECK.json'),deliverable_sha256=sha(O/'DELIVERABLE_SHA256.json'),new_accounts=0,new_models=0,new_backtests=0,new_indicators=0,candidate_fills=0)
save('SEAL_RECEIPT.json',seal);print(json.dumps(seal,ensure_ascii=False))
