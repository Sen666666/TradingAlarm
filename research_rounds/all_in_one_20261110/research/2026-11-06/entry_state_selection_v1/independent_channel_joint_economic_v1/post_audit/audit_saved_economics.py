"""Independent read-only audit of saved G2 outputs. Never imports a consumer."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal as D
import argparse, ast, csv, datetime, hashlib, json, math, sys
O=Path(__file__).resolve().parent.parent
ROOT=O.parent
EPS=D('0.0000001')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def csvrows(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def dec(x):return D(str(x)) if x not in (None,'') else D(0)
def close(a,b,label,eps=EPS):
 assert abs(dec(a)-dec(b))<=eps,(label,str(a),str(b))
def fee_environment():
 base=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
 sys.path.insert(0,str(base/'code'))
 from market_rules import version_on,market_identity_on
 from sector_account import QuantityRule,FeeComponent,FeeSchedule
 source=ROOT/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py'
 text=source.read_text()
 env=dict(D=D,meta={},rules=read(base/'inputs-v2/market-rules.json'),
  proxies=read(base/'inputs-v2/economic-protocol.json')['approved_proxy_ids'],
  version_on=version_on,market_identity_on=market_identity_on,
  QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule)
 for n in ast.parse(text).body:
  if isinstance(n,ast.FunctionDef) and n.name in ('getmeta','fee'):
   exec(compile(ast.get_source_segment(text,n),str(source)+':auditor_fee_definitions_only','exec'),env)
 return env
def ledger(directory,feeenv,baseline=False):
 rounds=csvrows(directory/'ROUNDS.csv')
 if baseline:rounds=[r for r in rounds if r['arm']=='A_UNION_B']
 ids={r['round_id'] for r in rounds};assert len(ids)==len(rounds)
 acts=[a for a in csvrows(directory/'ACTIONS.csv') if a['round_id'] in ids]
 claims=[c for c in read(directory/'CLAIMS.json') if c['owner_round_id'] in ids]
 by=defaultdict(list);cb=defaultdict(list)
 for a in acts:by[a['round_id']].append(a)
 keys=set()
 for c in claims:
  key=json.dumps(c['key'],sort_keys=True);assert key not in keys;keys.add(key)
  assert int(c['record_q'])>0 and c['owner_round_id'] in ids
  close(c['amount'],dec(c['record_q'])*dec(c['d_cash'])*D('.8'),'NET80 claim')
  close(c['core_amount'],dec(c['core_record_q'])*dec(c['d_cash'])*D('.8'),'CORE NET80')
  assert not c['settled'] or c['recognized']
  cb[c['owner_round_id']].append(c)
 stats={};maxerr=D(0)
 for r in rounds:
  rid=r['round_id'];q=0;cash=D(0);spent=D(0);fees=D(0);bought=defaultdict(int);cost_lots={'PROBE':[],'ADD':[]}
  for a in by[rid]:
   n=int(a['q']);p=dec(a['price']);f=dec(a['fee']);assert n>0 and p>0 and f>=0
   side='buy' if a['side'].startswith('buy') else 'sell'
   qr,fs,par=feeenv['getmeta'](a['sid'],datetime.datetime.fromisoformat(a['day']))
   expected=feeenv['fee'](n,p,fs,side,par);close(f,expected,('dated fee',rid,a['day'],side))
   if side=='buy':
    assert qr.buy_floor(n)==n
    q+=n;cash-=n*p+f;spent+=n*p+f;bought[a['day']]+=n
    role='ADD' if a['side']=='buy_add' else 'PROBE';cost_lots[role].append([n,n*p+f])
   else:
    assert n<=q-bought[a['day']],(rid,'T+1 or oversell')
    if a['side']=='sell_all':
     assert n==q;cost_lots={'PROBE':[],'ADD':[]}
    elif a['side']=='sell_add':
     remain=n
     while remain:
      lot=cost_lots['ADD'][0];take=min(remain,lot[0]);part=lot[1]*D(take)/D(lot[0]);remain-=take;lot[0]-=take;lot[1]-=part
      if lot[0]==0:cost_lots['ADD'].pop(0)
    else:raise AssertionError(('unrecognized sell role',a['side']))
    q-=n;cash+=n*p-f
   fees+=f
  recognized=sum((dec(c['amount']) for c in cb[rid] if c['recognized']),D(0))
  paid=sum((dec(c['amount']) for c in cb[rid] if c['settled']),D(0))
  recv=recognized-paid
  close(r.get('cash_after_payouts'),cash+paid,('cash',rid))
  close(r.get('receivable_after_payouts'),recv,('receivable',rid))
  close(r.get('dividend_net80_total'),recognized,('recognized',rid))
  close(r.get('dividend_net80_paid'),paid,('paid',rid))
  if by[rid]:
   close(r['all_fees'],fees,('fees',rid));close(r['total_buy_cash'],spent,('buy cash',rid))
   assert q==int(dec(r.get('core_qty')))+int(dec(r.get('add_qty'))),(rid,'inventory')
  unknown='UNKNOWN' in r['status'] or 'PENDING' in r['status'] or any(not c['recognized'] for c in cb[rid])
  value=None
  if not unknown:
   if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':
    assert q==0;value=cash+recognized;close(r['net_pnl'],value,('closed net',rid))
   elif 'CENSORED' in r['status'] and q:
    assert str(r.get('last_known_mark_day',''))[:10]=='2026-06-30'
    value=dec(r['last_mark_net'])
   else:
    assert not by[rid] and not cb[rid],(rid,'unclassified economic state');value=D(0)
  remaining_cost=sum((lot[1] for ls in cost_lots.values() for lot in ls),D(0))
  stats[rid]=dict(sid=r['sid'],lane='AB' if baseline else r['owner_lane'],value=value,
   remaining_cost=remaining_cost,trade_realized=cash+remaining_cost,
   unknown=unknown,q=q,cash=cash,recognized=recognized,paid=paid,fees=fees,buy_cash=spent,
   entered=any(a['side'].startswith('buy') for a in by[rid]),status=r['status'])
 return dict(rounds=rounds,actions=acts,claims=claims,by=by,cb=cb,stats=stats)
def clean(v):
 if isinstance(v,D):return str(v)
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 return v
def audit(window,forensic_only=False,recovered=False):
 dest=O/('economic_'+window)
 assert (dest/'ECONOMIC_LOOP_COMPLETE.json').exists(),'WAIT_FOR_SAVED_NATIVE_LEDGER'
 failure=read(dest/'FAILED_NO_RETRY.json') if (dest/'FAILED_NO_RETRY.json').exists() else None
 assert failure is None or forensic_only or recovered, failure
 auth=read(O/'ROOT_ECONOMIC_AUTHORIZATION.json');pre=read(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json')
 assert auth['implementation_audit_sha256']==sha(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json')
 assert auth['code_sha256']==pre['reviewed_code_sha256'] and auth['input_sha256']==pre['reviewed_input_sha256']
 for n,h in auth['code_sha256'].items():assert sha(O/n)==h,('code drift',n)
 for p,h in auth['input_sha256'].items():assert sha(p)==h,('input drift',p)
 for p,h in read(dest/'joint/SOURCE_HASHES.json').items():
  assert auth['input_sha256'][str(Path(p).resolve())]==h and sha(p)==h
 for n,h in read(dest/'joint/OUTPUT_HASHES.json').items():assert sha(dest/'joint'/n)==h
 feeenv=fee_environment()
 bpath=ROOT/'m3_stock_birth_during_sector_v1'/('relative_priority_equity_run_2022_v1/dynamic' if window=='2022' else 'cash_equity_baseline_2024_v1/economic')
 b=ledger(bpath,feeenv,True);j=ledger(dest/'joint',feeenv)
 roster=sorted(x['sid'] for x in csvrows(ROOT/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv'))
 assert len(roster)==len(set(roster))==1709
 rows={}
 for arm,source in [('baseline',b),('joint',j)]:
  for sid in roster:
   rr=[r for r in source['stats'].values() if r['sid']==sid]
   unknown=any(r['unknown'] for r in rr)
   value=None if unknown else sum((r['value'] for r in rr),D(0))
   rows[sid,arm]=dict(value=value,unknown=unknown,entered=any(r['entered'] for r in rr),
    rounds=sum(r['entered'] for r in rr),
    lanes={lane:sum((r['value'] for r in rr if r['lane']==lane),D(0)) if not any(r['value'] is None for r in rr if r['lane']==lane) else None for lane in ('AB','PRICE')})
 # Every full-fill proxy target is evidenced separately, never an actual ACK.
 books=read(dest/'EXECUTION_BOOKS.json')
 for rid,book in books.items():
  s=j['stats'][rid];assert s['lane']=='PRICE'
  assert sum(l['remaining'] for l in book['lots'].values())==s['q']
  for role,p in book['parents'].items():
   target=p['target'];assert target['evidence_domain']=='PROXY'
   assert p['filled_F']==target['target_Q']
   side='buy_core' if target['role']=='PROBE' else 'buy_add'
   assert sum(int(a['q']) for a in j['by'][rid] if a['side']==side)==p['filled_F']
   buys=[a for a in j['by'][rid] if a['side']==side]
   assert len(buys)==1
   a=buys[0];n=int(a['q']);px=dec(a['price']);bf=dec(a['fee']);floor=dec(target['protection_raw'])
   raw_open=px/D('1.0005');assert raw_open>floor
   _,fs,par=feeenv['getmeta'](a['sid'],datetime.datetime.fromisoformat(a['day']))
   sell_at_floor=feeenv['fee'](n,floor*D('.9995'),fs,'sell',par)
   added_risk=max(D(0),D(n)*(px-floor*D('.9995'))+bf+sell_at_floor)
   if target['role']=='PROBE':
    close(target['budget'],D(24000),'initial budget')
    assert D(n)*px+bf<=D(24000)+EPS and added_risk<=D(3000)+EPS
   else:
    core=next(x for x in j['by'][rid] if x['side']=='buy_core');q0=int(core['q'])
    prior=max(D(0),D(q0)*(px-floor*D('.9995'))+dec(core['fee'])+feeenv['fee'](q0,floor*D('.9995'),fs,'sell',par))
    budget=max(D(0),min(D(24000),D(48000)-D(q0)*raw_open))
    close(target['budget'],budget,'ADD current market value budget')
    assert D(n)*px+bf<=budget+EPS and added_risk+prior<=D(3000)+EPS
    assert dec(a.get('prior_round_net'))>0
    assert target['signal_receipt_id'][1]>=core['day'],'ADD receipt predates completed probe OPEN'
   assert target['registered_known_at']['day']==a['day']==target['decision_open']
   assert target['signal_receipt_id'][1]<a['day']
   lots=[x for x in book['lots'].values() if x['parent_id']==target['parent_id']]
   assert len(lots)==1 and lots[0]['quantity']==n
   close(lots[0]['price'],px,'proxy lot/native buy price');close(lots[0]['fee'],bf,'proxy lot/native buy fee')
   assert target['registered_known_at']['sequence']<lots[0]['known_at']['sequence']
  for order in book['orders'].values():
   assert order['evidence_domain']=='PROXY' and order['live_leaves']==0
   assert order['terminal_filled']==order['quantity']
 # Retained AB events independently match the original chronological ledgers.
 bm={r['event_id']:r for r in b['rounds']};jm={r['event_id']:r for r in j['rounds'] if r['owner_lane']=='AB'}
 retained=0
 for eid in set(bm)&set(jm):
  br,jr=bm[eid],jm[eid];ba,ja=b['by'][br['round_id']],j['by'][jr['round_id']]
  assert len(ba)==len(ja),(eid,'action count')
  for a,x in zip(ba,ja):
   for k in a:
    if k in ('round_id','arm'):continue
    if k in ('q','price','fee'):close(a[k],x[k],(eid,'action',k))
    else:assert a[k]==x[k],(eid,'action',k,a[k],x[k])
  def claim_normal(cs):
   return [{k:v for k,v in c.items() if k not in ('key','arm','owner_round_id')} for c in cs]
  assert claim_normal(b['cb'][br['round_id']])==claim_normal(j['cb'][jr['round_id']]),(eid,'claims')
  for k in ('status','exit_day','exit_price','exit_reason'):
   assert br.get(k,'')==jr.get(k,''),(eid,k)
  retained+=1
 result=dict(window=window,result='PASS_RAW_ACCOUNTING_PENDING_REPORT',new_strategy_runs_by_auditor=0,
  fixed_roster=1709,source_code_and_output_hashes_passed=True,dated_fees_and_lots_verified=True,
  all_cash_claims_inventory_and_T1_verified=True,proxy_books=len(books),retained_ab_events_path_exact=retained,
  arm_rounds={a:len(s['rounds']) for a,s in [('baseline',b),('joint',j)]},
  actual_entered_stocks={a:sum(rows[sid,a]['entered'] for sid in roster) for a in ('baseline','joint')},
  unknown_stocks={a:sum(rows[sid,a]['unknown'] for sid in roster) for a in ('baseline','joint')},
  repeated_participation_stocks={a:sum(rows[sid,a]['rounds']>1 for sid in roster) for a in ('baseline','joint')},
  joint_newly_entered_stocks=sum(rows[sid,'joint']['entered'] and not rows[sid,'baseline']['entered'] for sid in roster),
  joint_no_longer_entered_stocks=sum(rows[sid,'baseline']['entered'] and not rows[sid,'joint']['entered'] for sid in roster))
 result['runtime_failure_record']=failure
 result['publication_blocked']=failure is not None
 reportpath=dest/('COMPARISON_REPORT_RECOVERED.json' if recovered else 'COMPARISON_REPORT.json')
 summarypath=dest/('CORE_SUMMARY_RECOVERED.json' if recovered else 'CORE_SUMMARY.json')
 marker=dest/('REPORT_RECOVERY_QA.json' if recovered else 'COMPLETE.json')
 if reportpath.exists() and marker.exists():
  if recovered:
   qa=read(marker);assert qa['status']=='PASS_POSTERIOR_SAVED_LEDGER_RECOVERY'
   assert qa['new_economic_runs']==0 and qa['consumer_calls']==0 and qa['retained_ab_exact']['mismatch_count']==0
   assert qa['report_sha256']==sha(reportpath) and qa['summary_sha256']==sha(summarypath)
   assert qa['recovered_script_sha256']==sha(O/'recover_saved_report.py')
   result.update(publication_blocked=False,original_runtime_report_failure_retained=failure is not None,posterior_representation_recovery_verified=True)
  report=read(reportpath);summary=read(summarypath)
  assert report['fixed_roster_count']==1709 and len(report['stock_rows'])==3418
  ix={(r['sid'],r['arm']):r for r in report['stock_rows']};assert len(ix)==3418
  li={(r['sid'],r['arm'],r['lane']):r for r in report['lane_rows']};assert len(li)==6836
  for arm,source in [('baseline',b),('joint',j)]:
   for sid in roster:
    for lane in ('AB','PRICE'):
     stats=[x for x in source['stats'].values() if x['sid']==sid and x['lane']==lane]
     rr=li[sid,arm,lane]
     for field in ('remaining_cost','trade_realized'):
      close(rr[field],sum((x[field] for x in stats),D(0)),(sid,arm,lane,field),D('.000001'))
     close(rr['confirmed_net80_income'],sum((x['recognized'] for x in stats),D(0)),(sid,arm,lane,'confirmed_income'),D('.000001'))
  for key,r in rows.items():
   q=ix[key]
   assert q['unknown_liability']==r['unknown'],(key,'unknown')
   if r['value'] is None:assert q['known_total_pnl'] is None,key
   else:close(q['known_total_pnl'],r['value'],(key,'stock pnl'),D('.000001'))
  common=[sid for sid in roster if all(ix[sid,a]['comparable'] for a in ('baseline','joint'))]
  assert set(common)==set(report['summary'][0]['common_covered_sids'])
  totals={a:sum((rows[sid,a]['value'] for sid in common),D(0)) for a in ('baseline','joint')}
  price=sum((rows[sid,'joint']['lanes']['PRICE'] for sid in common),D(0))
  ab=sum((rows[sid,'joint']['lanes']['AB']-rows[sid,'baseline']['lanes']['AB'] for sid in common),D(0))
  close(totals['joint']-totals['baseline'],price+ab,'contribution decomposition',D('.000001'))
  for key,value in [('common_baseline_net',totals['baseline']),('common_joint_net',totals['joint']),('common_joint_minus_baseline',price+ab),('common_price_contribution',price),('common_ab_path_delta',ab)]:
   close(summary[key],value,key,D('.000001'))
  for key in ('actual_entered_stocks','joint_newly_entered_stocks','joint_no_longer_entered_stocks','repeated_participation_stocks'):assert summary[key]==result[key],key
  assert summary['common_comparable_stocks']==len(common)
  assert report['permit_exact_verified'] is True
  assert not any(x in {'ORIGINAL_AB_PERMITS_NOT_EXACT','RETAINED_AB_PATH_MISMATCH_REQUIRES_REVIEW'} for x in report['adapter_blockers'])
  result.update(result='PASS_CORE_ECONOMIC_ACCOUNTING_AND_DENOMINATORS',common_comparable_stocks=len(common),
   common_both_never_entered=summary['common_both_never_entered'],common_actual_entered=summary['common_at_least_one_entered'],
   common_baseline_net=totals['baseline'],common_joint_net=totals['joint'],common_delta=price+ab,
   common_price_contribution=price,common_ab_path_delta=ab,report_blockers=report['adapter_blockers'],
   final_summary_sha256=sha(summarypath),final_report_sha256=sha(reportpath))
 result['auditor_script_sha256']=sha(__file__)
 return clean(result)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--window',required=True,choices=['2022','2024']);p.add_argument('--output')
 p.add_argument('--forensic-only',action='store_true')
 p.add_argument('--recovered',action='store_true')
 args=p.parse_args();result=audit(args.window,args.forensic_only,args.recovered)
 if args.output:
  with Path(args.output).open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps(result,ensure_ascii=False,indent=2))
