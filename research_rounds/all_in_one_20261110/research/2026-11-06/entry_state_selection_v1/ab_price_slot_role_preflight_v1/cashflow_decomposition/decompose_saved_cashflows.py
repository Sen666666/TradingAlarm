
import csv,json,hashlib,math,pathlib,collections,decimal,sys
from decimal import Decimal as D
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
J=R/'independent_channel_joint_economic_v1'
BASE={'2022':R/'m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/dynamic','2024':R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/economic'}
SOURCES={}
def read(p):
 SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return json.loads(p.read_text())
def csvread(p):
 SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with p.open() as f:return list(csv.DictReader(f))
def num(v):return D(str(v)) if v not in ('',None) else D(0)
def output(v):
 if isinstance(v,D):return float(v)
 if isinstance(v,set):return sorted(v)
 raise TypeError(type(v).__name__)
def norm(v):
 if v in ('',None):return None
 if isinstance(v,bool):return v
 try:
  n=D(str(v))
  if n.is_finite():return str(n.normalize())
 except decimal.InvalidOperation:pass
 s=str(v)
 if len(s)>=10 and s[4]=='-' and s[7]=='-' and s[10:] in ('',' 00:00:00','T00:00:00'):return s[:10]
 return s
def canon(rows,excluded):
 return sorted(json.dumps({k:norm(v) for k,v in x.items() if k not in excluded and norm(v) is not None},sort_keys=True) for x in rows)
def agg(rows):
 return dict(rounds=len(rows),entered_rounds=sum(x['entered'] for x in rows),stocks=len({x['sid'] for x in rows}),entered_stocks=len({x['sid'] for x in rows if x['entered']}),buy=sum((x['buy'] for x in rows),D(0)),sell=sum((x['sell'] for x in rows),D(0)),trade_net=sum((x['trade_net'] for x in rows),D(0)),income=sum((x['income'] for x in rows),D(0)),net=sum((x['net'] for x in rows),D(0)),fees=sum((x['fees'] for x in rows),D(0)))
summaries={}; allstocks=[]; allevents=[]; allrounds=[]; pathrecords=[]
for y in ('2022','2024'):
 report=read(J/f'economic_{y}/COMPARISON_REPORT_RECOVERED.json')
 offers_raw=read(J/f'economic_{y}/OFFER_AUDIT.json')
 assert canon(offers_raw,set())==canon(report['offer_audit'],set()),'RAW_OFFER_REPORT_MISMATCH'
 decisions_raw=read(J/f'economic_{y}/AB_DECISION_AUDIT.json')
 assert canon(decisions_raw,set())==canon(report['original_ab_decision_audit'],set()),'RAW_DECISION_REPORT_MISMATCH'
 rc={x['round_id']:x for x in report['round_coverage']}
 lr={(x['sid'],x['arm'],x['lane']):x for x in report['lane_rows']}
 sr={(x['sid'],x['arm']):x for x in report['stock_rows']}
 roster={x['sid'] for x in report['stock_rows']}
 assert len(roster)==1709
 raw={}
 for arm,folder,label in [('baseline',BASE[y],'A_UNION_B'),('joint',J/f'economic_{y}/joint','A_UNION_B_PLUS_PRICE')]:
  rounds=[x for x in csvread(folder/'ROUNDS.csv') if x['arm']==label]
  ids={x['round_id'] for x in rounds}
  actions=[x for x in csvread(folder/'ACTIONS.csv') if x['round_id'] in ids]
  claims=[x for x in read(folder/'CLAIMS.json') if x['owner_round_id'] in ids]
  manifest=read(folder/'OUTPUT_HASHES.json')
  for name in ('ROUNDS.csv','ACTIONS.csv','CLAIMS.json'):
   assert SOURCES[str(folder/name)]==manifest[name],(y,arm,name)
  aa=collections.defaultdict(list);cc=collections.defaultdict(list)
  for a in actions:aa[a['round_id']].append(a)
  for c in claims:cc[c['owner_round_id']].append(c)
  derived=[]
  for r in rounds:
   rid=r['round_id']; a=aa[rid]; c=cc[rid]
   buy=sum((num(t['q'])*num(t['price'])+num(t['fee']) for t in a if t['side'].startswith('buy')),D(0))
   sell=sum((num(t['q'])*num(t['price'])-num(t['fee']) for t in a if t['side'].startswith('sell')),D(0))
   inc=sum((num(t['amount']) for t in c if t.get('recognized') is True),D(0))
   inv=sum((num(t['q'])*(1 if t['side'].startswith('buy') else -1) for t in a),D(0))
   d=dict(year=y,arm=arm,lane=r.get('owner_lane','AB'),sid=r['sid'],round_id=rid,event_id=r['event_id'],signal_day=r['signal_day'][:10],entry_day=r.get('entry_day','')[:10],exit_day=r.get('exit_day','')[:10],status=r['status'],entered=any(t['side'].startswith('buy') and num(t['q'])>0 for t in a),buy=buy,sell=sell,trade_net=sell-buy,income=inc,fees=sum((num(t['fee']) for t in a),D(0)),net=sell-buy+inc,inventory=inv,financial_covered=rc[rid]['financial_covered'])
   if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':
    assert inv==0,(rid,inv)
    assert abs(d['net']-num(r['cash_after_payouts'])-num(r['receivable_after_payouts']))<D('0.0000001'),rid
    assert abs(d['fees']-num(r['all_fees']))<D('0.0000001'),rid
   derived.append(d)
  raw[arm]=dict(rounds=rounds,derived=derived,actions=aa,claims=cc)
 # Reconstruct common-stock denominator from native statuses, per-round saved coverage,
 # no unresolved execution book, and explicit no-responsibility zero.
 eligible={}
 for sid in roster:
  for arm in ('baseline','joint'):
   rs=[r for r in raw[arm]['derived'] if r['sid']==sid]
   unresolved=False
   if arm=='joint':
    for r in rs:
     b=report['execution_books'].get(r['round_id'])
     if b and (b.get('unknown') or b.get('live_leaves',0) or b.get('exit_pending') or not b.get('all_orders_reconciled',False)):unresolved=True
   unknown=any('UNKNOWN' in r['status'] or 'PENDING' in r['status'] for r in rs) or unresolved
   covered=all(r['financial_covered'] for r in rs)
   # These saved runs contain no open-known terminal marks. Verify, do not assume.
   open_known=any(r['inventory']!=0 and 'UNKNOWN' not in r['status'] for r in rs)
   assert not open_known,(y,sid,arm)
   eligible[sid,arm]=covered and not unknown
   assert eligible[sid,arm]==sr[sid,arm]['comparable'],(y,sid,arm,'denominator')
 common={s for s in roster if eligible[s,'baseline'] and eligible[s,'joint']}
 assert common==set(report['summary'][0]['common_covered_sids'])==set(report['summary'][1]['common_covered_sids'])
 bcommon=[r for r in raw['baseline']['derived'] if r['sid'] in common]
 jcommon=[r for r in raw['joint']['derived'] if r['sid'] in common]
 assert all(r['inventory']==0 and 'UNKNOWN' not in r['status'] for r in bcommon+jcommon)
 assert not report['terminal_marks']
 for arm,rs in [('baseline',bcommon),('joint',jcommon)]:
  assert abs(agg(rs)['net']-D(str(next(s['common_covered_pnl'] for s in report['summary'] if s['arm']==arm))))<D('0.0000001')
  for lane in ('AB','PRICE'):
   subtotal=agg([r for r in rs if r['lane']==lane])
   for col in ('fees','trade_realized','confirmed_net80_income','known_total_pnl'):
    ours={'fees':'fees','trade_realized':'trade_net','confirmed_net80_income':'income','known_total_pnl':'net'}[col]
    reference=sum((D(str(lr[s,arm,lane][col])) for s in common),D(0))
    assert abs(subtotal[ours]-reference)<D('0.0000001'),(y,arm,lane,col)
 b=agg(bcommon);ja=agg([r for r in jcommon if r['lane']=='AB']);jp=agg([r for r in jcommon if r['lane']=='PRICE']);j=agg(jcommon)
 base_by={r['event_id']:r for r in raw['baseline']['derived']}; joint_by={r['event_id']:r for r in raw['joint']['derived'] if r['lane']=='AB'}
 assert len(base_by)==len(raw['baseline']['derived']); assert len(joint_by)==sum(r['lane']=='AB' for r in raw['joint']['derived'])
 br={r['round_id']:r for r in raw['baseline']['rounds']};jr={r['round_id']:r for r in raw['joint']['rounds']}
 retained=set(base_by)&set(joint_by)
 for eid in retained:
  l=base_by[eid];r=joint_by[eid];bid=l['round_id'];jid=r['round_id']
  actions_equal=canon(raw['baseline']['actions'][bid],{'arm','round_id'})==canon(raw['joint']['actions'][jid],{'arm','round_id'})
  # Native claim key contains arm, so exclude identity keys; compare all economic fields.
  claims_equal=canon(raw['baseline']['claims'][bid],{'key','arm','owner_round_id'})==canon(raw['joint']['claims'][jid],{'key','arm','owner_round_id'})
  exit_equal=all(norm(br[bid].get(k))==norm(jr[jid].get(k)) for k in ('status','exit_day','exit_price','exit_reason'))
  assert actions_equal and claims_equal and exit_equal,(y,eid,actions_equal,claims_equal,exit_equal)
  assert abs(l['net']-r['net'])<D('0.0000001')
  pathrecords.append(dict(year=y,event_id=eid,sid=l['sid'],common=l['sid'] in common,actions_equal=actions_equal,claims_equal=claims_equal,exit_equal=exit_equal))
 labels=collections.defaultdict(list)
 for c in report['ab_changes']:
  if c['result']=='NOT_SELECTED_BOTH':continue
  l=base_by.get(c['event_id']); r=joint_by.get(c['event_id'])
  assert bool(l)==bool(c['baseline_round_ids']) and bool(r)==bool(c['joint_round_ids'])
  e=dict(year=y,event_id=c['event_id'],sid=c['sid'],day=c['day'][:10],common=c['sid'] in common,source_label=c['result'],baseline_round_id=l['round_id'] if l else '',joint_round_id=r['round_id'] if r else '',baseline_entered=bool(l and l['entered']),joint_entered=bool(r and r['entered']),baseline_net=l['net'] if l and c['sid'] in common else None,joint_net=r['net'] if r and c['sid'] in common else None,delta=(r['net'] if r else D(0))-(l['net'] if l else D(0)) if c['sid'] in common else None,audit_results=';'.join(sorted({a['result'] for a in c['audit']})))
  allevents.append(e)
  if e['common']:labels[e['source_label']].append(e)
 label_summary={}
 for label,ee in labels.items():
  label_summary[label]=dict(events=len(ee),stocks=len({e['sid'] for e in ee}),baseline_entered=sum(e['baseline_entered'] for e in ee),joint_entered=sum(e['joint_entered'] for e in ee),baseline_net=sum((e['baseline_net'] or D(0) for e in ee),D(0)),joint_net=sum((e['joint_net'] or D(0) for e in ee),D(0)),delta=sum((e['delta'] for e in ee),D(0)))
 assert abs(sum((v['delta'] for v in label_summary.values()),D(0))-(ja['net']-b['net']))<D('0.0000001')
 stock_groups=collections.defaultdict(list); first_groups=collections.defaultdict(list)
 for sid in sorted(common):
  bs=[r for r in bcommon if r['sid']==sid];js=[r for r in jcommon if r['sid']==sid and r['lane']=='AB'];ps=[r for r in jcommon if r['sid']==sid and r['lane']=='PRICE']
  be={r['event_id'] for r in bs};je={r['event_id'] for r in js}
  removed=be-je;added=je-be
  kind='BOTH_NO_AB_ROUND' if not be and not je else 'SAME_AB_EVENT_PATH' if be==je else 'REMOVED_AND_ADDED_AB_EVENTS' if removed and added else 'REMOVED_ONLY_AB_EVENTS' if removed else 'ADDED_ONLY_AB_EVENTS'
  bf=min((r['entry_day'] for r in bs if r['entered']),default='');jf=min((r['entry_day'] for r in js if r['entered']),default='')
  first='BOTH_NO_AB_BUY' if not bf and not jf else 'LOST_ALL_AB_BUY' if bf and not jf else 'NEW_AB_BUY_STOCK' if jf and not bf else 'SAME_FIRST_AB_BUY_DAY' if bf==jf else 'JOINT_FIRST_AB_BUY_LATER' if jf>bf else 'JOINT_FIRST_AB_BUY_EARLIER'
  v=dict(year=y,sid=sid,category=kind,first_ab_buy_relation=first,baseline_first_ab_buy=bf,joint_first_ab_buy=jf,retained_events=len(be&je),removed_events=len(removed),added_events=len(added),baseline_ab_net=agg(bs)['net'],joint_ab_net=agg(js)['net'],joint_price_net=agg(ps)['net'],ab_delta=agg(js)['net']-agg(bs)['net'],total_delta=agg(js+ps)['net']-agg(bs)['net'])
  allstocks.append(v);stock_groups[kind].append(v);first_groups[first].append(v)
 def sg(groups):return {k:dict(stocks=len(v),ab_delta=sum((x['ab_delta'] for x in v),D(0)),price_net=sum((x['joint_price_net'] for x in v),D(0)),total_delta=sum((x['total_delta'] for x in v),D(0))) for k,v in groups.items()}
 excluded=roster-common
 unknown_finance_by_arm={a:dict(unknown=sum(sr[s,a]['unknown_liability'] for s in roster),financial_uncovered=sum(not sr[s,a]['financial_covered'] for s in roster)) for a in ('baseline','joint')}
 unknown={s for s in roster if any(sr[s,a]['unknown_liability'] for a in ('baseline','joint'))}
 uncovered={s for s in roster if any(not sr[s,a]['financial_covered'] for a in ('baseline','joint'))}
 summaries[y]=dict(unknown_finance_by_arm=unknown_finance_by_arm,common_stocks=len(common),excluded=len(excluded),any_unknown=len(unknown),any_uncovered=len(uncovered),unknown_uncovered_overlap=len(unknown&uncovered),uncovered_without_unknown=len(uncovered-unknown),both_never_entered=sum(sr[s,'baseline']['never_entered'] and sr[s,'joint']['never_entered'] for s in common),common_baseline=b,common_joint_ab=ja,common_joint_price=jp,common_joint=j,ab_change=ja['net']-b['net'],total_delta=j['net']-b['net'],identity_residual=j['net']-b['net']-(ja['net']-b['net']+jp['net']),retained_events_all=len(retained),retained_events_common=sum(base_by[e]['sid'] in common for e in retained),retained_path_mismatches=0,ab_original_labels=label_summary,stock_ab_path_groups=sg(stock_groups),first_ab_buy_groups=sg(first_groups),common_terminal_marks=0,common_remaining_inventory=0,raw_closed_cash_and_fee_checks='PASS',source_manifests_verified=True)
 for arm in ('baseline','joint'):
  for r in raw[arm]['derived']:
   r['common']=r['sid'] in common
   if not r['common']:r['net']=None;r['trade_net']=None # no absent total implied, raw cash retained
   allrounds.append(r)
print(json.dumps(summaries,ensure_ascii=False,indent=2,default=output))
if len(sys.argv)>1 and sys.argv[1]=='--write':
 OUT=R/'ab_price_slot_role_preflight_v1/cashflow_decomposition'
 OUT.mkdir(parents=True,exist_ok=False)
 def save(name,v):
  with (OUT/name).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=output);f.write('\n')
 save('SUMMARY.json',summaries)
 save('SOURCE_HASHES.json',SOURCES)
 for filename,rows in [('STOCK_AB_PATH_DECOMPOSITION.csv',allstocks),('AB_EVENT_DECOMPOSITION.csv',allevents),('RAW_ROUND_CASHFLOW_CHECKS.csv',allrounds),('RETAINED_AB_PATH_CHECKS.csv',pathrecords)]:
  with (OUT/filename).open('x',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 for p,h in SOURCES.items():assert hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h,p
 save('QA.json',dict(status='PASS_READ_ONLY_SAVED_LEDGER_DECOMPOSITION',economic_runs=0,consumer_calls=0,engines_imported=0,all_source_hashes_unchanged=True,sources=len(SOURCES),common_sets_reconstructed_from_native_status_saved_round_financial_coverage_and_books=True,common_pnl_recomputed_from_native_actions_and_recognized_claims=True,unknown_excluded_not_zero=True,terminal_marks=0,fee_lane_owner='NATIVE_ROUND_OWNER',role_fee_allocation='NOT_NEEDED_FOR_AB_VS_PRICE_LANE_SUMS',retained_native_actions_claims_exit_exact=True))
