"""Taibao original chain/qualification only; no Account or candidate fill."""
from pathlib import Path
from decimal import Decimal as D
import csv,gzip,hashlib,json,math
import pandas as pd

O=Path(__file__).resolve().parent;Q=O.parents[1];SID='601601.SH';IDS={1904,1914,1931};START='2024-09-02';END='2024-10-10';SRC={}
B=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs')
MARKET=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
PRO=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/economic-protocol.json')
RULES=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(s) for s in f] if lines else json.load(f)
def sidlog(p):
 p=Path(p);SRC[str(p.resolve())]=sha(p);rr=[]
 with gzip.open(p,'rt') as f:
  for i,s in enumerate(f):
   if SID not in s:continue
   r=json.loads(s);day=r.get('day',r.get('at',''))[:10]
   if START<=day<=END and r.get('sid')==SID:rr.append(dict(source_index=i,original=r))
 return rr
def frame(p,expected):
 p=Path(p);assert sha(p)==expected;SRC[str(p.resolve())]=sha(p);return pd.read_parquet(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(D,pd.Timestamp)):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvsave(n,rr):
 with (O/n).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(clean(rr))
def asof(f,day):
 j=f.index.searchsorted(pd.Timestamp(day),side='right')-1
 return (None,None) if j<0 else (str(f.index[j].date()),f.iloc[j].to_dict())

book=read(B/'B.json.gz',True);daily=read(B/'daily.jsonl.gz',True,True)
op=sidlog(B/'opportunities.jsonl.gz');fu=sidlog(B/'funding.jsonl.gz')
m=next(r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json') if r['symbol']==SID)
facts=frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]);cp=frame(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])
ixp=next(p for p in m['source_sha256'] if p.endswith('/601601.SH.parquet') and 'ix-a-share' in p);ix=frame(ixp,m['source_sha256'][ixp])
rec=next(r for r in read(R/'MANIFEST.json') if r['sid']==SID);rp=Path(rec['output_path']);assert sha(rp)==rec['output_sha256'];receipts=read(rp);rd={r['confirmed_day']:r for r in receipts}
rt=read(MARKET)['series'];rt=rt[SID] if isinstance(rt,dict) else next(r for r in rt if r['series_id']==SID)
raw=frame(rt['raw']['path'],rt['raw']['sha256']);raw['trade_date']=pd.to_datetime(raw.trade_date);raw=raw.set_index('trade_date')
protocol=read(PRO);rules=read(RULES)
decisions={d['at'][:10]:(i,d) for i,d in enumerate(book['decisions'])}
buys={t['layer']:(i,t) for i,t in enumerate(book['trades']) if t['side']=='buy' and t['layer'] in IDS}
fills={a['receipt']['receipt_id']:(i,a) for i,a in enumerate(book['audit']) if a['kind']=='fill'}
rows=[];records=[]
for di,d in enumerate(daily):
 day=d['at'][:10]
 if not START<=day<=END:continue
 p=daily[di-1];prev=[x for x in p['layers'] if x['sid']==SID];live=[x for x in d['layers'] if x['sid']==SID]
 fd,f=asof(facts,day);cd,c=asof(cp,day);xd,x=asof(ix,day)
 ds=decisions[day];ints=[dict(intent_index=i,original=v) for i,v in enumerate(ds[1]['intents']) if v['sid']==SID]
 oo=[r for r in op if r['original']['day']==day];ff=[r for r in fu if r['original']['at'][:10]==day]
 tt=[dict(trade_index=i,original=t) for i,t in enumerate(book['trades']) if t['security_id']==SID and t['at'][:10]==day]
 audit=[dict(audit_index=i,original=a) for i,a in enumerate(book['audit']) if a.get('sid',a.get('security_id'))==SID and a.get('at','')[:10]==day]
 current_raw=None if pd.Timestamp(day) not in raw.index else raw.loc[day].to_dict()
 fields=['close','raw_close','factor','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready']
 record=dict(day=day,original_CLOSE=d['at'],daily_index=di,ACT_on=d['on'],original_account_NAV=d['nav'],original_CLOSE_available=d['available'],original_CLOSE_pool_probe=d['pool_probe'],original_CLOSE_pool_confirmed=d['pool_confirmed'],original_shared_loss=d['shared_loss'],
  actual_position_qty=d['positions'].get(SID,0),actual_previous_CLOSE_layers=prev,actual_layers_after_original_CLOSE_checks=live,original_pending_sells=[s for s in d['pending_sells'] if s==SID],
  fact_source_day=fd,original_facts={k:f[k] for k in fields if k in f},CP_source_day=cd,original_CP_cache=c,original_new_CP_canonical_receipt=rd.get(day),G1_IX_source_day=xd,original_G1_IX=x,
  original_opportunities=oo,original_decision_index=ds[0],original_frozen_intents=ints,original_funding_today=ff,original_trades_today=tt,original_audit_today=audit,original_runtime_raw_bar=current_raw,
  missing=['No at-route per-pool searched q, successful binding-constraint vector, or before-this-reserve available snapshot is saved in the cited reserve/funding rows. CLOSE available is a different clock and not substituted.','No candidate sell or candidate reentry funding state is built; original subsequent refusals do not prove a refusal after hypothetical removal of layer1904.'])
 records.append(record)
 o=oo[0]['original'] if oo else {}
 rows.append(dict(day=day,daily_index=di,actual_position_qty=record['actual_position_qty'],actual_layers=json.dumps([dict(id=h['id'],qty=h['qty'],role=h['role'],opened=h['opened']) for h in live]),raw_C=f['raw_close'],factor=f['factor'],i_target=f['i_target'],i_floor=f['i_floor'],i_buy=f['i_buy'],g_grade=f['g_grade'],g_fresh_up=f['g_fresh_up'],g_acute_down=f['g_acute_down'],G1_up_reasons=json.dumps(x.get('up_reasons')),CP_receipt=c['receipt'],CP_candidate=c['candidate'],CP_current_s=c['s'],CP_receipt_original_scale=None if day not in rd else rd[day]['original_scale'],CP_scale_frozen_at=None if day not in rd else rd[day]['scale_frozen_at'],CP_receipt_id=o.get('CP1_id'),core_Q=o.get('core_Q'),mobile_Q=o.get('mobile_Q'),roles=json.dumps(o.get('roles')),barriers=json.dumps(o.get('barriers')),intents=json.dumps([dict(role=v['original']['role'],cap=v['original']['cap'],budget=v['original']['budget'],floor=v['original']['floor'],priority_rank=v['original'].get('priority_rank')) for v in ints]),funding_today=json.dumps([r['original'] for r in ff]),CLOSE_NAV=d['nav'],CLOSE_available=d['available']))
save('ORIGINAL_DAILY_CHAIN.json',records);csvsave('ORIGINAL_DAILY_CHAIN.csv',rows)
save('ORIGINAL_OPPORTUNITIES.json',op);save('ORIGINAL_FUNDING.json',fu)
dates=dict(CP_true=[r['day'] for r in rows if r['CP_receipt']],i_buy_true=[r['day'] for r in rows if r['i_buy']],both_true=[r['day'] for r in rows if r['CP_receipt'] and r['i_buy']],i_buy_only=[r['day'] for r in rows if r['i_buy'] and not r['CP_receipt']],CP_only=[r['day'] for r in rows if r['CP_receipt'] and not r['i_buy']])
save('CP_I_BUY_TRUE_DATE_SETS.json',dates)
entry=[]
for lid,(ti,t) in sorted(buys.items()):
 afi,af=fills[t['receipt_id']];res=next((i,a) for i,a in enumerate(book['audit']) if a['kind']=='reserve' and a['order_id']==af['order_id']);j=next((i,a) for i,a in enumerate(book['journal']) if a['kind']=='real_buy_fill' and a.get('layer')==lid)
 ds=decisions[t['signal_at'][:10]];it=[dict(intent_index=i,original=v) for i,v in enumerate(ds[1]['intents']) if v['sid']==SID and v['role']=='mobile']
 entry.append(dict(layer=lid,actual_buy_trade_index=ti,actual_buy=t,actual_fill_audit_index=afi,actual_fill_audit=af,reserve_audit_index=res[0],actual_reserve=res[1],actual_fill_journal_index=j[0],actual_fill_journal=j[1],original_signal_decision_index=ds[0],original_signal_NAV=ds[1]['nav'],original_frozen_intents=it,original_signal_CP_canonical_receipt=rd.get(t['signal_at'][:10]),at_reserve_available='NOT_RECORDED_IN_ORIGINAL_RESERVE_ROW_NOT_REBUILT',per_pool_search_q='NOT_RECORDED'))
save('THREE_ACTUAL_ENTRY_AND_RESERVE_DETAILS.json',entry)

open_day='2024-09-10';bar=raw.loc[open_day];days=[d['at'][:10] for d in daily];t1=[]
for lid in [1904,1914]:
 t=buys[lid][1];buyday=t['at'][:10];nextday=days[days.index(buyday)+1]
 t1.append(dict(layer=lid,actual_buy_at=t['at'],actual_shares=t['shares'],protocol_sellable_lag_sessions=protocol['sellable_lag_sessions']['A'],next_original_A_session_day=nextday,inferred_protocol_sellable_at=nextday+' 09:30:00+08:00',necessary_T_plus_1_satisfied_by_Sept10=nextday<=open_day,
  evidence_status='Static source protocol plus recorded fill/session dates, not a serialized per-lot timestamp snapshot and not a candidate fill.'))
def version(xs,day):return next(v for v in xs if v['from']<=day and (v['to'] is None or day<v['to']))
av=version(rules['availability_versions'][SID],open_day);qr=version(rules['quantity_versions'][SID],open_day)
save('SEPT10_OPEN_NECESSARY_STATE_ONLY.json',dict(hypothesis_date_not_original_exit='2024-09-09 CLOSE A2 is an external paper trigger; original No60 did not submit an exit then.',symbol=SID,raw_bar=bar.to_dict(),raw_OPEN=str(bar.open),raw_OPEN_minus_5bps_reference=str(D(str(bar.open))*D('.9995')),H_le_L=bool(bar.high<=bar.low),volume_positive=bool(bar.volume>0),price_and_observation_flags={k:bar[k] for k in ['price_eligible','volume_eligible','source_invalid','observed_bar','synthetic_event_bar']},protocol=protocol['daily_execution']['A'],T_plus_1_necessary_lots=t1,original_availability_research_proxy=av,original_quantity_research_proxy=qr,
  snapshot_Sept09_CLOSE=next(r for r in records if r['day']=='2024-09-09'),capacity_policy='min(previous20 positive volume mean*.01, entire next-day volume); no window/capacity quantity/candidate fill called',
  missing=['No actual candidate exit order, submission, real broker ACK, execution depth or filled quantity.', 'No candidate sell fees/cash/reentry grant calculated. Positive H>L/volume/T+1 only passes these necessary source checks, not a complete execution or funding proof.']))
for p in [Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py'),Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')]:SRC[str(p)]=sha(p)
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,script_sha256=sha(__file__),new_accounts=0,new_models=0,new_backtests=0,new_candidate_fills=0,original_files_changed=False))
print(json.dumps(dict(status='PASS',days=len(rows),CP_true=dates['CP_true'],i_buy_true=dates['i_buy_true'],both=dates['both_true'],open_raw=str(bar.open),new_accounts=0,new_candidate_fills=0),ensure_ascii=False))
