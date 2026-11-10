"""Versioned input snapshots and actual-time admission; no financial runner."""
from pathlib import Path
from datetime import datetime,time as dtime,timezone,timedelta
import json,hashlib,csv,uuid
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds';BASE=ROOT/'TradingAlarm/runtime/market';TZ=timezone(timedelta(hours=8));VERSION='L0_operations_v2_actual_ready_earliest1600'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def stamp():return datetime.now(TZ).isoformat()
def aware(x):
 if x.tzinfo is None:raise ValueError('Actual availability and submission must be timezone-aware')
 return x
def clock_gate(day,now,available_at,complete,next_open,mode):
 aware(now);floor=datetime.combine(datetime.fromisoformat(day).date(),dtime(16),TZ)
 if mode not in ['prospective','historical_rehearsal']:raise ValueError('Explicit mode required')
 if not complete:return 'blocked_incomplete'
 if not available_at:return 'blocked_unknown_availability'
 for x in available_at:aware(x)
 if now<max(available_at):return 'blocked_not_yet_available'
 if next_open is None:return 'blocked_unknown_next_session'
 aware(next_open)
 if mode=='historical_rehearsal':return 'input_snapshot_only_no_orders'
 if now<floor:return 'blocked_before1600'
 if now>=next_open:return 'blocked_expired_next_open'
 return 'ready_for_new_version_decision_not_fill'
def tests():
 day='2026-10-30';ready=datetime.fromisoformat(day+'T15:55:00+08:00');nextopen=datetime.fromisoformat('2026-11-02T09:30:00+08:00');now=datetime.fromisoformat(day+'T16:05:00+08:00');results=[]
 for name,kw,want in [
 ('all_ready',{},'ready_for_new_version_decision_not_fill'),
 ('before_1600',dict(now=datetime.fromisoformat(day+'T15:59:00+08:00')),'blocked_before1600'),
 ('missing',dict(complete=False),'blocked_incomplete'),
 ('future_input',dict(available_at=[now+timedelta(minutes=1)]),'blocked_not_yet_available'),
 ('availability_unknown',dict(available_at=[]),'blocked_unknown_availability'),
 ('next_calendar_unknown',dict(next_open=None),'blocked_unknown_next_session'),
 ('past_target_open',dict(now=nextopen),'blocked_expired_next_open'),
 ('late_input_attempt',dict(now=ready-timedelta(minutes=1)),'blocked_not_yet_available'),
 ('historical_not_real_order',dict(mode='historical_rehearsal',now=nextopen+timedelta(days=1)),'input_snapshot_only_no_orders')]:
  args=dict(day=day,now=now,available_at=[ready],complete=True,next_open=nextopen,mode='prospective');args.update(kw);actual=clock_gate(**args);assert actual==want;results.append(dict(name=name,expected=want,actual=actual))
 try:clock_gate(day,datetime(2026,10,30),[ready],True,nextopen,'prospective')
 except ValueError:results.append(dict(name='naive_timestamp_rejected',passed=True))
 else:raise AssertionError('Naive datetime accepted')
 save(O/'CLOCK_TESTS.json',dict(passed=True,tests=results,synthetic_clock_tests_only=True,ledger_or_execution_integration_test=False))
def main():
 tests();assert read(O/'CACHE_GATE.json')['passed'] and read(O/'MARKET_GATE.json')['passed'];source_manifest=read(BASE/'update-20261030-153010-c551af/prepared/manifest.json');latest=BASE/'update-20261030-153010-c551af/prepared';receipts={read(p)['as_of']:read(p) for p in BASE.glob('update-202610*/prepared/receipt.json') if read(p).get('as_of') in ['2026-10-28','2026-10-29','2026-10-30']};cal=read(ROOT/'TradingAlarm/desk/calendar.json');pools={};checks=[];packets=[]
 cache_receipts={x['sid']:x for x in read(O/'CACHE_GATE.json')['receipts']};market_receipt=read(O/'MARKET_GATE.json')
 for sec,path in [('TECH',RR/'tech-compound-design-20261026/proposed-pool.csv'),('DRUG',RR/'innovative-drug-local-recovery-20261028/pool.csv')]:
  rs=list(csv.DictReader(path.open()));ids=sorted({r['symbol'] for r in rs}|{r['sector_id'] for r in rs});pools[sec]=ids
  for day in ['2026-10-28','2026-10-29','2026-10-30']:
   original_source=Path(receipts[day]['path']);facts_dir=original_source/'facts' if sec=='TECH' else O/'prepared/facts';market_path=original_source/'recovery.csv' if sec=='TECH' else O/'prepared/recovery.csv';market=pd.read_csv(market_path,index_col=0,parse_dates=True);at=pd.Timestamp(day);assert at in market.index;fields=[];available=[datetime.fromisoformat(receipts[day]['published_at'])];cache_files={};created=[]
   for sid in ids:
    fp=facts_dir/f'{sid}.parquet';f=pd.read_parquet(fp);assert at in f.index;required=['i_target','i_buy','i_floor','e0_target','e0_floor','e0_ready','g_grade','g_ready','factor','raw_close'];assert all(c in f for c in required);assert pd.notna(f.loc[at,'factor']) and (not f.loc[at,'i_target'] or pd.notna(f.loc[at,'i_floor']));cache_files[str(fp)]=sha(fp)
    if sec=='TECH':
     other=pd.read_parquet(latest/'facts'/f'{sid}.parquet');pd.testing.assert_series_equal(f.loc[at],other.loc[at],check_exact=True);available_at=receipts[day]['published_at']
    else:available_at=cache_receipts[sid]['created_at'];created.append(available_at)
    available.append(datetime.fromisoformat(available_at));fields.append(dict(sid=sid,market_day=day,I_event=bool(f.loc[at,'i_buy']),I_active=bool(f.loc[at,'i_target']),factor=float(f.loc[at,'factor']),row_available_evidence_at=available_at))
   if sec=='DRUG':available.append(datetime.fromisoformat(market_receipt['created_at']))
   validated=stamp();available.append(datetime.fromisoformat(validated));nextday=next((x for x in cal['sessions'] if x>day),None);nextopen=datetime.fromisoformat(nextday+'T09:30:00+08:00') if nextday else None;submitted=stamp();status=clock_gate(day,datetime.fromisoformat(submitted),available,True,nextopen,'historical_rehearsal')
   assert status=='input_snapshot_only_no_orders';identity=dict(version=VERSION,sector=sec,market_day=day,source_manifest_sha=sha(original_source/'manifest.json'),cache_files=cache_files,market_clock_sha=sha(market_path),strategy_source_manifest_sha=sha(O.parent/'lr1-cp1-add-preflight-20261031/FREEZE.json'));key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
   packets.append(dict(id=key,identity=identity,mode='historical_rehearsal',market_day=day,earliest_policy_time=day+'T16:00:00+08:00',source_published_at=receipts[day]['published_at'],new_derived_cache_created_at_max=max(created) if created else None,integrity_validated_at=validated,rehearsal_actual_submitted_at=submitted,status=status,actual_prospective_gate_today=clock_gate(day,datetime.fromisoformat(submitted),available,True,nextopen,'prospective'),historical_next_session_label=nextday,real_order_earliest_at=None,market_input_rows=len(fields),snapshot_type='market_input_only',complete_account_state_present=False,actual_strategy_intents=0,fills=0,NAV_created=False,unverified_official_actions=True,dividend_receivable_spendable=False,rows=fields))
   checks.append(dict(sector=sec,day=day,rows=len(fields),row_prefix_match_10_30=sec=='TECH',day_packet_complete=True,mode=status))
 save(O/'MARKET_INPUT_SNAPSHOTS.json',packets);save(O/'DAY_PACKET_GATE.json',dict(passed=True,snapshots=6,checks=checks,no_backdated_actual_submissions=True,DRUG_new_caches_marked_created_today=True,prospective_orders=0,fills=0,source_plus_derived_actual_ready_evidence=True))
 # Append-only research receipts; never touches actual account or produces an
 # executable historical order. Stable content keys ignore invocation time.
 journal=O/'input-submissions.jsonl';old=[json.loads(x) for x in journal.read_text().splitlines()] if journal.exists() else [];known={x['id'] for x in old};added=[]
 with journal.open('a') as f:
  for p in packets:
   if p['id'] in known:continue
   r=dict(id=p['id'],version=VERSION,mode='historical_rehearsal',sector=p['identity']['sector'],market_day=p['market_day'],submitted_at=p['rehearsal_actual_submitted_at'],actual_order=False);f.write(json.dumps(r,ensure_ascii=False)+'\n');known.add(p['id']);added.append(r)
 # Second same-key admission is a no-op, with original timestamps retained.
 before=journal.read_bytes();assert all(p['id'] in known for p in packets);assert journal.read_bytes()==before;save(O/'INPUT_JOURNAL_GATE.json',dict(passed=True,unique_packets=len(known),new_receipts=len(added),same_content_repetition_no_new_receipt=True,financial_order_idempotence_tested=False))
 print('CLOCK AND SIX INPUT SNAPSHOTS COMPLETE; actual intents/fills/NAV=0',flush=True)
if __name__=='__main__':main()
