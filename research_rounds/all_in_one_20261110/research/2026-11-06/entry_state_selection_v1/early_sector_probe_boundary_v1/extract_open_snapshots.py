"""Extract original OPEN reservation snapshots without constructing/running accounts.
Use system python3 -B (same available pickle imports as original extraction).
Default --verify-only checks existing output. --out must be a NEW JSON in this directory.
Import continuous_inputs registers original pickle classes only; never call inputs().
"""
import sys
sys.dont_write_bytecode=True
import argparse,collections,hashlib,json,pickle
from pathlib import Path
from decimal import Decimal as D
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent/'account_comparison_continuous_v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def extract():
 sys.path.insert(0,str(ROOT/'inputs'))
 import continuous_inputs
 cp=ROOT/'run_1200000/latest_checkpoint/checkpoint.pkl'
 digest=sha(cp);meta=json.loads(cp.with_suffix('.json').read_text());prov=json.loads(cp.with_suffix('.provenance.json').read_text())
 assert digest==meta['sha256']==prov['checkpoint_sha256']
 with cp.open('rb') as f:x=pickle.load(f)
 a=x['accounts']['PVR'];g=collections.defaultdict(list);j=collections.defaultdict(collections.Counter)
 rsum=collections.defaultdict(lambda:D(0));gsum=collections.defaultdict(lambda:D(0));fsum=collections.defaultdict(lambda:D(0))
 for ix,s in enumerate(a['sync_rows']):g[s['at']].append((ix,s))
 for s in a['journal']:j[s['at']].update([s['kind']])
 for s in a['audit_log']:
  if s['kind']=='reserve':
   rsum[s['at']]+=s['gross_budget_cny']+s['fee_reserved_cny'];gsum[s['at']]+=s['gross_budget_cny'];fsum[s['at']]+=s['fee_reserved_cny']
 rows=[]
 for c in x['runner']['open_checks']:
  if c['account']!='PVR':continue
  at=c['at'];rr=g[at];n=j[at]['real_reserve'];s=j[at]['real_sell_fill'];b=j[at]['real_buy_fill'];ix=s+n
  assert len(rr)==s+n+2*b+2,(at,len(rr),s,n,b)
  glob,v=rr[ix];bal=v['components']
  assert bal['order_reserved']==rsum[at],at
  assert not v['pending_cancel_ack'],at
  assert sum((bal[k] for k in ('available','order_reserved','settlement_locked','sale_receivable','inventory','dividend_receivable')),D(0))-bal['payable']==bal['nav'],at
  rows.append(dict(at=str(at),components=bal,sell_fill_count_S=s,reservation_count_N=n,buy_fill_count_B=b,same_at_sync_row_count=len(rr),same_at_index_zero_based=ix,global_sync_index_zero_based=glob,reservation_gross_exact=gsum[at],reservation_fees_exact=fsum[at],reservation_total_exact=rsum[at],reservation_difference_exact=bal['order_reserved']-rsum[at],pending_cancel_ack=v['pending_cancel_ack'],sync_differences=v['differences']))
 assert len(rows)==1054
 return dict(account='PVR',source_checkpoint=str(cp),source_checkpoint_sha256=digest,source_policy=x['runner']['integration_policy'],snapshot_clock='After original OPEN sells and settlement, after every original buy reservation, before any original buy fill',qa=dict(passed=True,open_dates_verified=len(rows),total_sync_rows=len(a['sync_rows']),source_checksum_matches_metadata_and_provenance=True,row_count_identity='S + N + 2*B + 2',selected_zero_based_index='S + N',all_reservation_totals_exact=True,all_balance_components_reconcile_exactly=True,no_pending_cancel_ack=True,no_account_initialization=True,no_account_execution=True,all_original_files_read_only=True,contains_lots_or_pool_risk=False),rows=rows)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path);z=ap.parse_args()
 result=extract();encoded=json.dumps(result,ensure_ascii=False,indent=2,default=str,allow_nan=False);h=hashlib.sha256(encoded.encode()).hexdigest()
 original=HERE/'ORIGINAL_OPEN_RESERVATION_SNAPSHOTS.json'
 assert h==sha(original),('extraction_not_byte_identical',h,sha(original))
 if z.out:
  out=z.out.resolve();assert out.parent==HERE and out.suffix=='.json'
  with out.open('x') as f:f.write(encoded)
 print(json.dumps(dict(verified=True,rows=len(result['rows']),sha256=h,output=str(z.out) if z.out else None)))
