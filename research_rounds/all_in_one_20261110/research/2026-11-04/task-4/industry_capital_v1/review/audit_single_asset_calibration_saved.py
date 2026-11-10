"""Independent persisted-trace/actual-book comparison; never runs a new path."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
import gzip,json,hashlib,time
R=Path(__file__).resolve().parent;I=R.parent;P=I/'labels_new';W=I.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
t0=time.monotonic();cal=read(P/'TECHNICAL_CALIBRATION_RESULT.json');sel=read(P/'CALIBRATION_SELECTION.json');assert cal['passed']and cal['paths']==5 and cal['single_asset_shadow_paths']==5 and not cal['full_labels_executed']and cal['new_portfolio_policy_accounts']==0
books={};out=[]
for rr in cal['results']:
 w=rr['window'];sid=rr['sid'];key=rr['key'];lid=int(key.rsplit('|',1)[1]);z=rr['result'];nt=z['native_trace']
 if w not in books:
  with gzip.open(W/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair/B.json.gz','rt')as h:books[w]=json.load(h)
 b=books[w];layer=next(x for x in b['layers']if x['id']==lid);assert layer['sid']==sid and layer['kind']=='core'
 old=[t for t in b['trades']if t['security_id']==sid and layer['opened']<=t['at']<=layer['closed']];new=nt['trades'];assert len(old)==len(new)
 fields=['at','side','shares','gross_cny','fees_cny']
 for a,c in zip(old,new):
  assert datetime.fromisoformat(a['at'])==datetime.fromisoformat(c['at'])and a['side']==c['side']and a['shares']==c['shares']
  for k in ['gross_cny','fees_cny']:assert D(a[k])==D(c[k])
 sl=nt['layers'][0]
 for k in ['cash','dividend','qty']:assert D(str(layer[k]))==D(str(sl[k]))
 expected=D(layer['cash'])+D(layer['dividend']);assert D(z['net_pnl_original_ledger'])==expected==D(rr['expected_net_profit']);assert z['status']=='closed'and z['terminal_qty']==0 and z['known_net']
 seed=D(z['initial_seed_cash']);cn=D(z['entry_cash_actual']);nav=D(z['terminal_NAV']);pnl=nav-seed;assert pnl==expected and D(z['wealth_from_invested_Cn_excluding_unspent_seed'])==cn+pnl;assert D(z['wealth_from_invested_Cn_net_liquidation'])==cn+pnl-D(z['terminal_liquidation_drag']);assert D(z['actual_shadow_fees'])==sum((D(t['fees_cny'])for t in new),D(0))
 assert datetime.fromisoformat(new[0]['at']).date()<datetime.fromisoformat(new[-1]['at']).date()
 ac=[x for x in nt['audit']if x['kind']in ['dividend_accrual','split','split_fraction_floor_proxy']]
 out.append(dict(key=key,sid=sid,window=w,fill_count=len(new),exact_fill_timestamps_sides_qty_gross_fees=True,layer_cash_dividend_qty_exact=True,net_pnl_exact=str(expected),wealth_seed_identity_exact=True,CA_audit_kinds=[x['kind']for x in ac],source_continuity='pending producer guard/saved factual scope check'))
manifest=read(P/'TECHNICAL_SOURCE_SHA256.json');check={str(p):sha(p)==v for p,v in manifest.items()};changed=[p for p,v in check.items()if not v]
res={'saved_result_review_passed':True,'full_labels_admission':False,'blocking_source_guard':'First I/ACT exit may precede a later source break while a sell is pending. Numeric labels must be unknown if original signal-to-final-horizon source continuity is not reliable, regardless of first stop cause.','paths':len(out),'all_actual_fill_layer_and_profit_exact':True,'calibration_CA_covered':any(r['CA_audit_kinds']for r in out),'results':out,'manifest_entries':len(manifest),'current_manifest_mismatches':changed,'schema_review':['Invested wealth=Cn+(nativeNAV-initialseed)-terminal liquidationdrag removes unspent seed after partialbuy.','Partial order remainder cancels at entryCLOSE. Actual entryday exit requests cannot sellsameOPEN; native T+1/window retained.','CA actions/payments reused native; candidate entryday priorholder entitlement not counted, since ledger empty before its buy.','Censored terminal net liquidation is an estimate; known_net/source flags must control main matching.','Sparse no-op hold omission is limited to no interest/reinvestment; original settlements and payments are processed at next retained event, before any trade and terminal valuation.'],'not_exercised_by_these5':['Entry nonfill/partialbuy','ACT firststop (all5 I exits)','Post-proposal source break or source unknown','Still-open terminal liquidation estimate'], 'reviewer_new_single_asset_paths':0,'reviewer_new_portfolio_policy_accounts':0,'reviewer_new_marks':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),P/'TECHNICAL_CALIBRATION_RESULT.json',P/'CALIBRATION_SELECTION.json',P/'native_single_asset.py',P/'calibrate_native.py']},'seconds':time.monotonic()-t0}
(R/'SINGLE_ASSET_CALIBRATION_SAVED_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k not in ['source_sha256','schema_review','results']},indent=2));print(json.dumps(out,indent=2))
