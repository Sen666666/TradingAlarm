"""Source-only final verification and explanatory corrections; no account/indicator imports."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import json,gzip,hashlib,shutil
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
R=O.parents[1];A=R/'act_only_ablation_continuous_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
sources={}
def sh(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected:assert h==expected,('source hash drift',p)
 sources[str(p)]={'sha256':h,**({'expected':expected}if expected else{})};return h
def read(p,expected=None):sh(p,expected);return json.loads(Path(p).read_text())
def ident(*v):return hashlib.sha256(json.dumps(v,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def dump(name,x):
 p=O/name;assert not p.exists();p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def csv(name,x):
 p=O/name;assert not p.exists();pd.DataFrame(x).to_csv(p,index=False)
def j(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),default=str)
sh(__file__)
prior=read(O/'SOURCE_HASHES.json')
for p,v in prior.items():sh(p,v['sha256'])
summary=read(O/'SUMMARY.json');cases=read(O/'CASE_SUMMARY.json')
m={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
raises=pd.read_csv(O/'FLOOR_RAISES.csv')
advance_rows=[];receipt_checks=[]
for c in cases:
 sid=c['sid'];f=pd.read_parquet(m[sid]['refs']['facts'])
 obs={ident('price-observation',sid,str(int(fr.segment_id)),str(dt.date())):str(dt.date())for dt,fr in f.iterrows()}
 receipts={}
 for path,info in prior.items():
  if Path(path).name==sid+'.json' and 'receipts'in path:
   for x in read(path,info['sha256']):receipts[x['confirmed_day']]=x
 entry=receipts[c['signal_day']]
 selected=[('ENTRY_SIGNAL',c['signal_day'])]
 selected += [('FLOOR_RAISE',d)for d in raises[(raises.round_id==c['round_id'])&raises.final_source.eq('CP1')].day]
 for purpose,d in selected:
  r=receipts[d];dates=[obs[x]for x in r['new_advance_price_event_ids']]
  after_fill=all(t>=c['entry_day']for t in dates)
  overlap=set(r['new_advance_price_event_ids'])&set(entry['new_advance_price_event_ids'])
  previous=next((v for v in receipts.values()if v['receipt_id']==r.get('previous_market_receipt_id')),None)
  if previous:assert all(t>previous['confirmed_day']for t in dates)
  assert all(t>r['formation_start_exclusive']for t in dates)
  if purpose=='FLOOR_RAISE':assert after_fill and not overlap,(c['round_id'],d,'premature or reused advance')
  for pid,t in zip(r['new_advance_price_event_ids'],dates):advance_rows.append({'round_id':c['round_id'],'sid':sid,'purpose':purpose,'receipt_day':d,'receipt_id':r['receipt_id'],'anchor_day_exclusive':r['formation_start_exclusive'],'entry_at':c['entry_day']+' 09:30:00+08:00','advance_observation_day':t,'advance_observation_available_phase':'CLOSE','advance_after_actual_fill':t>=c['entry_day'],'price_event_id':pid,'also_in_entry_receipt':pid in set(entry['new_advance_price_event_ids']),'previous_market_receipt_id':r.get('previous_market_receipt_id'),'previous_market_confirmed_day':previous['confirmed_day']if previous else None})
  rc={'round_id':c['round_id'],'sid':sid,'purpose':purpose,'receipt_day':d,'anchor_day_exclusive':r['formation_start_exclusive'],'anchor_before_fill_date':r['formation_start_exclusive']<c['entry_day'],'new_advance_days':dates,'all_new_advances_after_fill':after_fill,'entry_receipt_advance_overlap_count':len(overlap),'previous_market_receipt_is_entry_signal':r.get('previous_market_receipt_id')==entry['receipt_id']}
  receipt_checks.append(rc)
  if purpose=='FLOOR_RAISE' and d==c['last_floor_day']:
   c.update(last_raise_new_advance_days=dates,last_raise_all_new_advances_after_fill=after_fill,last_raise_entry_advance_overlap_count=len(overlap),anchor_vs_credit_note='Anchor before fill does not establish pre-fill credit. New advances are separately dated and are post-fill.')
sh(W/'cp1-evidence-trace-20261031/trace.py')
csv('CP_ADVANCE_DATES.csv',advance_rows);dump('CP_ADVANCE_VERIFICATION.json',receipt_checks)
# Confirm native raw bars and original window receipts for every pending common OPEN.
runtime=read(A/'run/RUNTIME_DEPENDENCY_FREEZE.json')
mp=P/'manifest.json';manifest=read(mp,runtime.get(str(mp)))
market={x['series_id']:x for x in manifest['series']}
winpath=A/'run/SHARED_WINDOW_AUDIT.jsonl.gz';expected=read(A/'run/OUTPUT_HASHES.json')['SHARED_WINDOW_AUDIT.jsonl.gz'];sh(winpath,expected)
windows=defaultdict(list)
for line in gzip.open(winpath,'rt'):
 x=json.loads(line)
 if x.get('sid')in {c['sid']for c in cases}:windows[(x['sid'],str(x['at'])[:10])].append(x)
calendar=sorted({str(json.loads(l)['at'])[:10]for l in gzip.open(A/'run/pair/daily.jsonl.gz','rt')if '"account": "NOACT"'in l})
native_rows=[]
for c in cases:
 sid=c['sid'];rec=market[sid];rawp=Path(rec['raw']['path']);sh(rawp,rec['raw']['sha256']);raw=pd.read_parquet(rawp);raw.index=pd.to_datetime(raw.trade_date).dt.tz_localize(None);raw=raw.sort_index()
 actp=rec['adjustment']['actions']['path'];actions=read(actp,rec['adjustment']['actions']['sha256']).get('events',[])
 pending=[d for d in calendar if c['trigger_day']<d<=c['exit_day']]
 for d in pending:
  rows=windows.get((sid,d),[]);sell=[x for x in rows if x.get('side')=='sell'];exists=pd.Timestamp(d)in raw.index
  previous=raw[raw.index<pd.Timestamp(d)].iloc[-1];today=raw.loc[d]if exists else None
  acts=[x for x in actions if str(previous.name.date())<x.get('effective_date','')<=d]
  if not exists:assert not sell and not acts
  if d==c['exit_day']:assert any(x.get('raw_open')==c['sell_raw_open']and x.get('price')==c['sell_price']for x in sell),(sid,d,'window mismatch')
  native_rows.append({'round_id':c['round_id'],'sid':sid,'pending_OPEN_day':d,'same_day_native_raw_bar_exists':exists,'known_same_day_raw_open':float(today.open)if exists else None,'prior_observed_close_day':str(previous.name.date()),'prior_observed_raw_close':float(previous.close),'OPEN_mark_value_if_no_same_day_open':float(previous.close)if not exists and not acts else None,'OPEN_mark_source_status':'Prior valid raw close per ContinuousMarket.latest_mark; no intervening action'if not exists and not acts else 'Current raw OPEN available','original_sell_window_rows':j(sell),'original_sell_window_record_count':len(sell),'window_status':'ACTUAL_RECORDED_SELL_WINDOW'if sell else 'NO_WINDOW_MISSING_OPEN_RETURN_BY_ORIGINAL_CODE'if not exists else 'UNKNOWN_NO_RECORDED_WINDOW','actual_first_layer_sell_day':d==c['exit_day'],'native_source_sha256':rec['raw']['sha256'],'tradability_status':'UNKNOWN historical proxy; no official halt inference'})
csv('PENDING_EXIT_WINDOW_DAILY.csv',native_rows)
# Verify observed original funding is day-level: it includes both OPEN routing and CLOSE sizing.
post=pd.read_csv(O/'POST_EXIT_20_COMMON_CLOSES.csv',keep_default_na=False)
post=post.rename(columns={'original_funding_at_this_OPEN':'original_funding_and_sizing_at_this_day'})
post['original_OPEN_funding']=post.original_funding_and_sizing_at_this_day.map(lambda s:j([x for x in json.loads(s)if '09:30:00'in x.get('at','')]))
post['original_CLOSE_sizing']=post.original_funding_and_sizing_at_this_day.map(lambda s:j([x for x in json.loads(s)if '15:10:00'in x.get('at','')]))
assert len(post)==294
assert sum(len(json.loads(x))for x in post.actual_later_buys_at_this_OPEN)==0
# Preserve the primary narrative, including the overstrong formation wording, before correction.
snap=O/'pre_verification_snapshot';assert not snap.exists();snap.mkdir()
for name in ['SUMMARY.json','CASE_SUMMARY.json','CASE_SUMMARY.csv','READOUT.md','POST_EXIT_20_COMMON_CLOSES.csv','OUTPUT_HASHES.json']:shutil.copy2(O/name,snap/name)
summary.update(critical_result='6/7 fast failures and Jiangfeng already broke immutable initial BUY floor. All 7 fast failures had CP-dominant initial floor; Ningbo 361 alone among 14 had I-dominant floor. Gree 1542 is the only raised-floor-only fast failure. Its 1/16 CP anchor is 1/9 before 1/10 OPEN, but all new advances are 1/10,1/15,1/16 CLOSE, with zero overlap with entry CP. Anchor-before-fill is not proof of pre-fill or reused credit.',initial_CP_dominant_cases=13,initial_I_dominant_cases=1,all_fast_failures_initial_CP_dominant=True,CP_floor_raises_all_new_advances_after_fill=True,CP_floor_raise_new_advances_overlap_entry_receipt=0,post_exit_actual_rebuy_fills=0,post_exit_fixed_common_close_rows_excluding_exit_day=280,post_exit_includes_exit_day_separately=True,first_exit_reason_and_final_layer_sell_reason_agree_all14=True,unknowns=['Jiangfeng immediate next common OPEN after 2026-01-29 is missing. Five common-day native raw bars are absent before 2026-02-06; no official halt cause inferred.','Historical tradability remains UNKNOWN under original causal OPEN proxy.'],clarification='Original source behavior is old-floor check before update. A migration to first-layer I protection would require original-I risk sizing, not reuse of existing CP-sized quantities. No alternative strategy profits calculated.')
(O/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
(O/'CASE_SUMMARY.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
pd.DataFrame(cases).to_csv(O/'CASE_SUMMARY.csv',index=False);post.to_csv(O/'POST_EXIT_20_COMMON_CLOSES.csv',index=False)
lines=(O/'READOUT.md').read_text().splitlines()
lines=[line.replace('Gree 1542 raised floor from fresh CP formed after entry.','Gree 1542 raised floor from fresh CP with post-fill new advances; its anchor precedes fill.')for line in lines]
lines=[line if not line.startswith('- Gree last raise was')else '- Gree last raise was confirmed on 1/16 with anchor 1/9, before its 1/10 OPEN fill. Its new advances are 1/10, 1/15 and 1/16 CLOSE, all post-fill; previous receipt is the 1/9 entry signal, and the advance-ID overlap is zero. Anchor-before-fill is not evidence of pre-fill or reused credit.'for line in lines]
lines+=['','## Verified source and exposure appendix','- All 7 fast failures had CP-dominant initial max(I,CP). The only I-dominant initial floor among 14 is Ningbo 361, whose actual first exit was I_structure_exit.','- Every CP floor-raising receipt in the 14 paths contains only post-fill new advance observations and zero reuse of entry-receipt advance IDs. CP_ADVANCE_DATES lists the observations. Do not use anchor-day comparison alone as a credit-contamination test.','- First I invalidation within entry through the fixed follow-up end: TianShan 2022-01-25, HuaDong 2022-02-22, SanHua 2022-01-24, NingBo 2022-07-11, China Galaxy 2024-10-15. For the other 9 cases, I stayed valid continuously from original trigger to follow-up end. A later return to I=true does not erase an earlier invalidation.','- RunZe 1942 and China Galaxy 1952 both raised CP on 2024-10-08, triggered on 10/09 and sold 10/10. RunZe I remains continuously valid through 11/07; Galaxy I first becomes invalid 10/15 then later valid again.','- In all 14 fixed windows, actual original-account rebuys are zero. Fresh evidence and some signal-side legal opportunities occur, but original industry/cash/risk/capital barriers often prevent entry. They are not counterfactual funding evidence.','- PENDING_EXIT_WINDOW_DAILY reads the actual native raw-bar manifest and original SHARED_WINDOW records. Jiangfeng is missing 1/30, 2/2, 2/3, 2/4 and 2/5 native bars. No same-day OPEN is available; original code returns no window, while prior close 113.48 is the mark, not an executable quote. On 2/6 the actual recorded sell window has raw OPEN 113.58, price 113.523210, capacity 158736 and prior-volume last observation 1/29. This does not establish official suspension.','- The final POST_EXIT file separates original OPEN funding from CLOSE sizing; the first draft mislabeled a day-level list as OPEN-only. This was a label correction, not a change to original outcomes.','','## Verification history','- failure_01_uncropped_future_tail retains the initial source-preflight failure and exact script. It compared unequal future tails, corrected by applying the original consumer cutoff 2026-05-15.','- pre_verification_snapshot preserves primary text before correcting the distinction between CP anchor and new-credit observation dates, plus the OPEN/CLOSE funding label. Corrected main files and FINAL_VERIFICATION are authoritative.','- Original account, signal/fact and CP files are unchanged. Original account simulations=0; indicator recomputations=0; candidate consumer tests=0.']
(O/'READOUT.md').write_text('\n'.join(lines)+'\n')
dump('FINAL_VERIFICATION.json',{'passed':True,'original_account_runs':0,'indicator_recomputations':0,'case_count':14,'daily_floor_matches':277,'raw_buy_sell_price_exact':28,'first_exit_reason_matches_final14':True,'new_CP_advance_date_records':len(advance_rows),'CP_receipt_checks':len(receipt_checks),'all_CP_raises_have_only_post_fill_advances':all(x['all_new_advances_after_fill']for x in receipt_checks if x['purpose']=='FLOOR_RAISE'),'CP_raise_entry_advance_overlap_sum':sum(x['entry_receipt_advance_overlap_count']for x in receipt_checks if x['purpose']=='FLOOR_RAISE'),'pending_common_OPEN_rows':len(native_rows),'missing_native_bar_OPEN_rows':sum(not x['same_day_native_raw_bar_exists']for x in native_rows),'post_exit_common_close_rows':280,'exit_day_close_rows_separate':14,'actual_rebuys_in_observation_windows':0,'original_source_hashes_verified':len(prior),'supplement_source_hashes':len(sources),'preserved_corrections':['Future tails cropped to original cutoff before prefix comparison','Anchor-before-fill cannot establish pre-fill credit; separately decode advance IDs','Funding is day-level; OPEN routing and CLOSE sizing separately labeled'],'source_files_unchanged':True,'limitations':'Fixed history-labelled cases, no efficacy or out-of-sample claim; no alternative realizable profit or changed-exit funding calculation.'})
for p,v in sources.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==v['sha256'],('source changed',p)
dump('VERIFICATION_SOURCE_HASHES.json',sources)
# Preserve original hash manifest in snapshot; create a final one binding every result and failure.
final={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(O.rglob('*'))if p.is_file()and p.name!='FINAL_OUTPUT_HASHES.json'}
dump('FINAL_OUTPUT_HASHES.json',final)
print(json.dumps({'passed':True,'files':len(final),'CP_receipts':len(receipt_checks),'new_advance_rows':len(advance_rows),'pending_open_rows':len(native_rows),'raw_missing':sum(not x['same_day_native_raw_bar_exists']for x in native_rows)}))
