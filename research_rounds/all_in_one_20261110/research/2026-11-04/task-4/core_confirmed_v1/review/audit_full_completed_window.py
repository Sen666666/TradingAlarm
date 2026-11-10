"""Saved native prefixes only; no Account/Runner init/Market/mark recomputation."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
from datetime import datetime
import json,gzip,hashlib,sys,time,argparse,traceback
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parent;T=P.parent;O=P/'funding';K=O/'technical';OLD=T/'new_price_trend_v1/funding';begun=time.monotonic();sys.dont_write_bytecode=True;sys.path.insert(0,str(O));import run_confirmed as F
C,J=F.C,F.C.J;Z=D(0);sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):sources[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
 sources[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return [json.loads(s)for s in f]
def book(p):
 sources[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return json.load(f)
def near(a,b):assert abs(float(a)-float(b))<1e-6,(a,b)
def exactpair(a,b,cut=None,include_book=True):
 checked={}
 if include_book:assert book(a/'B.json.gz')==book(b/'B.json.gz');checked['B']=True
 for n in F.STREAMS:
  x,y=rows(a/(n+'.jsonl.gz')),rows(b/(n+'.jsonl.gz'))
  if cut:x=[v for v in x if str(v.get('day',v.get('at')))[:10]<=cut];y=[v for v in y if str(v.get('day',v.get('at')))[:10]<=cut]
  assert x==y,n;checked[n]=True
 return checked
def eff(xs,d):return next(x for x in reversed(xs)if x['from']<=d and(x.get('to')is None or d<x['to']))
def fee(q,p,s,side,par):
 v=Z
 for c in s['components']:
  if c.get('side','both')not in[side,'both']:continue
  basis=c.get('amount_basis','notional');amt=D(q)*p if basis=='notional'else D(q)if basis=='shares'else D(q)*par;a=max(D(str(c.get('minimum_local',0))),amt*D(str(c['rate'])))
  if c.get('maximum_local')is not None:a=min(a,D(str(c['maximum_local'])))
  if c.get('rounding_unit')is not None:
   u=D(str(c['rounding_unit']));a=(a/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  v+=a
 return v
def fact(sid,day):
 if sid not in facts:
  p=Path(sm[sid]['refs']['facts']);assert sha(p)==sm[sid]['output_sha256'][str(p)];facts[sid]=pd.read_parquet(p,columns=['e0_target','i_target','i_buy','g_ready','g_grade','segment_id','factor','i_floor'])
 f=facts[sid];ix=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert ix>=0;return f.iloc[ix]
def cpfor(w,sid,day):
 k=w,sid
 if k not in receiptcache:
  paths=[(sm[sid]['refs']['receipts'],sm[sid]['output_sha256'][sm[sid]['refs']['receipts']])]if w=='strong'else[(a[sid]['output_path'],a[sid]['output_sha256'])for a in canonical];out={}
  for p,h in paths:
   rr=read(p);assert sha(p)==h
   for x in rr:
    if x['confirmed_day']in out:assert out[x['confirmed_day']]==x
    out[x['confirmed_day']]=x
  receiptcache[k]=out
 return receiptcache[k].get(day)

def main(window):
 global begun,sources,rules,sm,canonical,facts,receiptcache
 begun=time.monotonic();sources={}
 window=window.lower();assert window in ('long','strong')
 full=O/'runs'/(window+'_ON')
 # Hard completion guard is before any saved financial book/outcome read.
 assert read(full/'DONE.json')['completed'], 'Target ON incomplete; do not read partial economics'
 complete=read(O/'runs'/(window+'_COMPLETE.json'));assert complete['passed'] and complete['new_ON_accounts']==1 and complete['new_OFF_accounts']==0
 admission=read(R/'FULL_ADMISSION.json');assert admission['approved'] and admission['scope']=='CORE_CONFIRMED_TWO_FULL_ON'
 assert complete['source_freeze_sha256']==sha(O/'SOURCE_FREEZE.json')==admission['source_freeze_sha256']
 timing=read(O/'runs'/(window+'_TIMING.json'));assert timing['used_seconds']<={'long':1600,'strong':800}[window]
 fresh=read(O/'runs'/(window+'_FRESH.json'));assert fresh=={'cash':1000000,'positions':0,'orders':0,'imported_accounts':0}
 oldidentity=read(OLD/'runs'/(window+'_INPUT_IDENTITY.json'));newidentity=read(O/'runs'/(window+'_INPUT_IDENTITY.json'))
 assert {k:v for k,v in oldidentity.items()if k!='seconds'}=={k:v for k,v in newidentity.items()if k!='seconds'}, 'Actual immutable input identity differs'
 freeze=read(O/'SOURCE_FREEZE.json');assert F.freeze()==freeze['sources'];gate=read(K/'GATE.json');assert gate['passed']and gate['prefix_paths']==6 and gate['native_seconds']<=180 and gate['source_freeze_sha256']==sha(O/'SOURCE_FREEZE.json');F.baseline_source_agreement()
 Q=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');rules=read(Q/'pvr-act-comparison-20261027/execution-rules-v2.json');sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};canonical=[{x['sid']:x for x in read(p)}for p in F.D.RECEIPT_MANIFESTS];facts={};receiptcache={}
 report={};total_success=0;total_filled=0;total_none=0;total_partial=0;total_proofs=0;total_balance=0
 for w,cut in [(window,F.D.WINDOWS[window][1])]:
  off=OLD/'runs'/(w+'_OFF');full=O/'runs'/(w+'_ON')
  offid={'reused_prior_full_OFF_native_identity':True};fullid={'common_window_and_input_identity':True};physicalid={'same_frozen_source_passed_technical_physical_prefix':True}
  assert read(full/'DONE.json')['completed']
  for root in[full]:
   b0=book(root/'pair/B.json.gz');daily0=rows(root/'pair/daily.jsonl.gz');balances=rows(root/'pair/balances.jsonl.gz')
   assert D(daily0[0]['nav'])==D(1000000)and not daily0[0]['positions']
   for x in balances:
    for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:near(x[k],0)
    for z in x['pool_occupancy_difference'].values():near(z,0)
    total_balance+=1
   for d in daily0:
    at=d['at'];assert all(sum(x['qty']for x in d['layers']if x['sid']==sid)==q for sid,q in d['positions'].items());assert set(x['sid']for x in d['layers']if x['qty'])==set(d['positions'])
    cash=sum((D(t['gross_cny'])-D(t['fees_cny'])if t['side']=='sell'else-D(t['gross_cny'])-D(t['fees_cny'])for t in b0['trades']if t['at']<=at),Z);div=sum((D(a['receivable']['net_local'])for a in b0['audit']if a['kind']=='dividend_accrual'and a['receivable']['ex_at']<=at),Z);assert abs(D(1000000)+cash+div+D(d['inventory'])-D(d['nav']))<D('.00000001')
  b=b0;dailys=daily0;assert len(dailys)==({'long':726,'strong':242}[w]) and dailys[-1]['at'][:10]==cut;assert [x['at'][:10]for x in dailys]==[x['at'][:10]for x in rows(off/'pair/daily.jsonl.gz')];dec={x['at'][:10]:x for x in b['decisions']};proofs=rows(full/'pair/core-proof.jsonl.gz');logs=rows(full/'pair/core-confirmed.jsonl.gz');fund=rows(full/'pair/funding.jsonl.gz');pmap={};intents={(d,i['sid']):i for d,r in dec.items()for i in r['intents']if i['role']=='core'};ops={(x['day'],x['sid']):x for x in rows(full/'pair/opportunities.jsonl.gz')if(x['day'],x['sid'])in intents};layers={x['id']:x for x in b['layers']};journal=b['journal'];reserve={x['budget_order']:x for x in journal if x['kind']=='real_reserve'};reserve_by={(x['at'],x['sid'],x['role']):x for x in journal if x['kind']=='real_reserve'};audits={x['order_id']:x for x in b['audit']if x['kind']=='reserve'};jf=defaultdict(list)
  for j in journal:
   if j['kind']=='real_buy_fill':jf[j['budget_order']].append(j)
  corebuys=[x for x in b['trades']if x['side']=='buy'and x['kind']=='core'];assert len({(x['security_id'],tuple(x['epoch']))for x in corebuys})==len(corebuys)
  core_first={(t['security_id'],tuple(t['epoch'])):t['at']for t in corebuys}
  for (d,sid),i in intents.items():assert core_first.get((sid,tuple(i['epoch'])),'9999')>d+' 23:59:59'
  for pr in proofs:
   sid,day=pr['sid'],pr['signal_day'];i=intents[day,sid];z=fact(sid,day);cp=cpfor(w,sid,day);assert pr['epoch']==i['epoch']and pr['source_segment']==int(z.segment_id);assert day==pr['at'][:10]and day<=cut and pr['CP_present']==(cp is not None)and pr['receipt_id']==(cp['receipt_id']if cp else None)
   op=ops[day,sid];assert op['core_Q']is True and op['held']is False and not op['barriers'];assert all(bool(z[k])for k in ['i_target','i_buy','e0_target','g_ready'])and z.g_grade>=2
   fr=dict(policy=C.POLICY,account=pr['account'],sid=sid,signal_day=day,epoch=i['epoch'],sector=pr['sector'],industry_episode=pr['industry_episode'],industry_attempt=pr['industry_attempt'],industry_level=pr['industry_level'],source_segment=int(z.segment_id),i_target=bool(z.i_target),i_buy=bool(z.i_buy),e0_target=bool(z.e0_target),G1_ready=bool(z.g_ready),G1_grade=float(z.g_grade),ACT_on=True,canonical_receipt=cp);fr['receipt_sha256']=C.digest(cp)if cp else None;assert pr['receipt_sha256']==fr['receipt_sha256']and pr['proof_sha256']==C.digest(fr);pmap[day,sid]=(pr,cp)
  assert set(pmap)==set(intents);total_proofs+=len(proofs)
  # All original funding reservations are complete before any actual buy fill on that OPEN.
  for at in {j['at']for j in journal if j['kind']=='real_reserve'}:
   ri=[k for k,j in enumerate(journal)if j['at']==at and j['kind']=='real_reserve'];fi=[k for k,j in enumerate(journal)if j['at']==at and j['kind']=='real_buy_fill'];assert not fi or max(ri)<min(fi)
  wanted_logs={(x['at'],x['sid'],'core')for x in logs};original_front={};active_at=None;front=[]
  for x in fund:
   if '09:30:00'not in x['at']:continue
   if x['at']!=active_at:active_at=x['at'];front=[]
   key=(x['at'],x['sid'],x['role'])
   if key in wanted_logs:original_front[key]=tuple(front)
   if x.get('result')=='reserved':front.append(reserve_by[key])
  core_first={(x['security_id'],tuple(x['epoch'])):x['at']for x in corebuys}
  success=filled=partial=none=0;failures=Counter()
  for log in logs:
   sid,day,at=log['sid'],log['signal_day'],log['at'];i=intents[day,sid];pr,cp=pmap[day,sid];assert datetime.fromisoformat(at)>datetime.fromisoformat(i['clock']['decision_at'])if 'clock'in i else at[:10]>day;assert set(log['probe_failures'])and set(log['probe_failures'])<={'probe_risk','sector_capital'};assert log['proof_sha256']==pr['proof_sha256'];assert log['original_frozen_cap']==i['cap']and D(log['original_frozen_budget'])==D(i['budget'])and D(log['original_risk_budget'])==D(i['risk_budget'])==D(dec[day]['nav'])*D('.0025')
   bef=log['before'];aft=log['after'];level=bef['sector_state']['level'];assert log['I_floor_adjusted']==i['floor'];factor=D(str(fact(sid,at[:10]).factor));assert D(log['I_floor_raw'])==D(i['floor'])/factor
   # Read exact original reservation prefix, no reconstruction or replay of orders.
   rr=original_front[at,sid,'core'];assert bef['live_order_quantity']=={x['budget_order']:x['shares']for x in rr};near(bef['pending_fees'],sum(float(audits[x['order']]['fee_reserved_cny'])for x in rr));near(bef['global_resources'][2],sum(float(D(audits[x['order']]['fee_reserved_cny'])+D(audits[x['order']]['gross_budget_cny']))for x in rr))
   if'minimum'in log:
    qr=eff(rules['quantity_versions'][sid],at[:10])['rule'];venue=eff(rules['venue_versions'][sid],at[:10])['venue'];schedule=eff(rules['fee_versions'][venue],at[:10])['schedule'];par=D(rules['security_metadata'][sid]['par_value']);px=D(log['known_OPEN'])*D('1.0005');floor=D(log['I_floor_raw']);assert log['minimum']['quantity']==qr['buy_minimum'];assert level>=1 and bef['sector_state']['active']and bef['sector_state']['episode']==pr['industry_episode']and bef['sector_state']['attempt']==pr['industry_attempt'];assert not any(layers[int(k)]['sid']==sid and q for k,q in bef['lots_quantity'].items())
    def scalar(q):
     f0=fee(q,px,schedule,'buy',par);nav=bef['budget_NAV']-bef['pending_fees']-float(f0);cap=q*float(px);risk=q*max(0.,float(px)-float(floor));frac=(.02,.1,.2)[level];cash=min(float(D(bef['available'])-D(bef['decision_NAV'])*D('.1')),bef['budget_cash']-bef['global_resources'][2]);fs=[]
     if cap+float(f0)>cash+1e-9:fs.append('cash_or_original_reserve')
     if bef['sector_resources'][0]+cap>frac*nav+1e-9:fs.append('sector_capital')
     if bef['sector_resources'][1]+risk>.01*nav+1e-9:fs.append('sector_risk')
     if cap>.10*float(D(bef['decision_NAV']))+1e-9:fs.append('stock_capital')
     return {'quantity':q,'fee':float(f0),'budget_NAV':nav,'capital':cap,'nominal_risk':risk,'industry_capital_limit':frac*nav,'industry_risk_limit':.01*nav,'cash_after_original_reserve':cash,'failures':fs}
    for name in ['minimum','confirmed_detail']:
     val=log.get(name)
     if val:
      scalarval=scalar(val['quantity']);assert val['failures']==scalarval['failures']
      for k,v in scalarval.items():
       if k not in['quantity','failures']:near(val[k],v)
    q=log['confirmed_quantity']
    if q:
     assert not scalar(q)['failures']and q<=log['preview_maxq']<=i['cap']and q>=qr['buy_minimum']and(q-qr['buy_minimum'])%qr['buy_step']==0
     if q+qr['buy_step']<=log['preview_maxq']:assert scalar(q+qr['buy_step'])['failures']
    else:assert scalar(qr['buy_minimum'])['failures']
   if log['result']!='reserved':assert bef==aft;failures[log['fallback_reason']]+=1;continue
   success+=1;q=log['shares'];bid=log['budget_order'];j=reserve[bid];a=audits[j['order']];assert j['role']=='core'and j['pool']=='confirmed'and j['receipt']==log['receipt_id']==cp['receipt_id']and j['shares']==q and D(j['price'])==px and a['target_shares']==q;paid=fee(q,px,schedule,'buy',par);assert D(log['fees'])==paid==D(a['fee_reserved_cny']);assert D(a['gross_budget_cny'])==q*px<=D(i['budget']);risk=max(Z,q*(px-floor*D('.9995'))+paid+fee(q,floor*D('.9995'),schedule,'sell',par));assert risk<=D(i['risk_budget']);assert bef['token_consumed']is False and aft['token_consumed']is True and cp['receipt_id']in b['budget']['consumed'];assert bef['lots_quantity']==aft['lots_quantity'];assert aft['stock_request_count']==bef['stock_request_count']+1
   for ix,delta in enumerate([q*float(px),q*max(0.,float(px)-float(floor)),q*float(px)+float(paid)]):near(aft['global_resources'][ix],bef['global_resources'][ix]+delta);near(aft['sector_resources'][ix],bef['sector_resources'][ix]+delta)
   bo=b['budget']['orders'][bid];assert bo['role']=='core'and bo['pool']=='confirmed'and bo['created_bar']==J.ordinal(day)and bo['expiry_bar']==J.ordinal(at[:10]);assert not any(x['at']==at and x['sid']==sid and x['role']=='mobile'for x in journal if x['kind']=='real_reserve')
   fs=jf[bid]
   if not fs:none+=1
   else:
    filled+=1;assert sum(x['shares']for x in fs)<=q
    if sum(x['shares']for x in fs)<q:partial+=1
    for f in fs:
     t=next(x for x in b['trades']if x.get('layer')==f['layer']and x['side']=='buy');l=layers[f['layer']];assert f['role']=='core'and f['pool']=='confirmed'and f['CP1_id']==cp['receipt_id']and t['kind']=='core'and t['epoch']==i['epoch']and t['floor']==i['floor'];assert D(t['raw_open'])==D(log['known_OPEN'])and D(t['price'])==px and D(t['gross_cny'])==t['shares']*px;assert D(t['fees_cny'])==fee(t['shares'],px,schedule,'buy',par);assert l['epoch']==i['epoch']and l['signal_at'][:10]==day
  for t in b['trades']:
   if t['side']!='sell':continue
   assert sum(x['shares']for x in t['parts'])==t['shares']and abs(sum((D(x['net_cash'])for x in t['parts']),Z)-(D(t['gross_cny'])-D(t['fees_cny'])))<D('.00000001');assert [x['layer']for x in t['parts']]==sorted(x['layer']for x in t['parts'])
   for x in t['parts']:assert t['at'][:10]>layers[x['layer']]['opened'][:10]
  report[w]={'OFF_book_and_six_streams':offid,'old_full_stream_prefix':fullid,'ON_full_vs_physical':physicalid,'proof_rows':len(proofs),'fallback_rows':len(logs),'new_typed_reservations':success,'typed_with_real_buy_fill':filled,'typed_nonfill':none,'typed_partial':partial,'failed_reasons':dict(failures),'all_new_numeric_scalar_min_max_and_original_frozen_risk_checked':True,'all_typed_journal_CP_epoch_order_and_buyfee_identity_checked':True,'all_saved_daily_cashflow_NAV_and_budget_certificates_checked':True};total_success+=success;total_filled+=filled;total_none+=none;total_partial+=partial
 assert total_success==sum(x['new_typed_reservations']for x in report.values())
 out={'passed':True,'scope':'Complete saved one-window ON proof/reservation/real-fill, clocks/epoch/token, cashflow NAV and native mirror audit. No new financial or mark path.','window':window,'source_freeze_sha256':sha(O/'SOURCE_FREEZE.json'),'technical_gate_sha256':sha(K/'GATE.json'),'full_admission_sha256':sha(R/'FULL_ADMISSION.json'),'full_CLOSEs':{'long':726,'strong':242}[window],'proof_rows':total_proofs,'typed_reservations':total_success,'typed_with_real_fill':total_filled,'typed_no_fill':total_none,'typed_partial':total_partial,'saved_balance_rows_checked':total_balance,'windows':report,'not_economic_result':'Contract/clock and financial equations, not arm selection. Economic summary and ON-OFF contribution conservation require completed saved analysis.','review_limits':['Native inventory marks/certificates cashflow reconciled; completed financial reader independently values source prices later.','Epoch/T+1/FIFO/CA behavior and unchanged native sources, no checkpoint unpickling or new financial initialization.','Unobserved boundary cases remain source/pure-fixture scope, no invented actual partial/nonfill.','Current leaf closure frozen; absent historical OFF leaf hashes not claimed.'],'reviewer_new_native_accounts_or_marks':0,'sources_sha256':sources,'seconds':time.monotonic()-begun}
 (R/(window.upper()+'_FULL_NATIVE_REVIEW.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in['sources_sha256','windows']},ensure_ascii=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--execute',action='store_true');parser.add_argument('--window',choices=['long','strong']);args=parser.parse_args();assert args.prepare!=args.execute
 if args.prepare:
  paths=[Path(__file__),R/'audit_native_technical_prefixes.py',R/'FULL_ADMISSION.json',O/'SOURCE_FREEZE.json',P/'PROTOCOL.txt']
  value={'passed':True,'prepared_only':True,'source_sha256':{str(p.resolve()):sha(p)for p in paths},'windows':{'long':726,'strong':242},'hard_completion_guard_before_any_book_read':True,'full_ON_results_read':False,'new_Account_or_Market_or_route_runs':0,'new_marks':0,'differences_from_audited_prefix_reader':['One completed window, full input identity/count/date and scoped run budget checks.','Reuses prior full OFF identity and passed physical-prefix evidence; no duplicate full OFF path or financial re-audit.','Literal per-OPEN prefix lookup and epoch map replace quadratic scans.','Sub-cent finite Decimal allocation tolerance; exact shares.','No fixed108/3684 assertions; count actual full observations including nonfill and partial.']}
  (R/'FULL_READER_PREPARATION.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print('PREPARED_ONLY_NO_FULL_RESULTS_READ')
 else:
  assert args.window
  try:main(args.window)
  except BaseException as error:
   (R/(args.window.upper()+'_FULL_REVIEW_FAILURE.json')).write_text(json.dumps({'passed':False,'window':args.window,'error':str(error),'traceback':traceback.format_exc(),'new_native_accounts_or_marks':0},ensure_ascii=False,indent=2)+'\n');raise
