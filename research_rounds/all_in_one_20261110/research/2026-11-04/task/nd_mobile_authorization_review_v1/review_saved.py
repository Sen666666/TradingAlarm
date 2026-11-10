from pathlib import Path
from decimal import Decimal as D
import gzip,json,hashlib,collections
W=Path(__file__).resolve().parents[1]; O=Path(__file__).resolve().parent
sources={}
def read(p,gz=False):
 sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return json.loads(gzip.decompress(p.read_bytes())) if gz else json.loads(p.read_text())
def stat(rs):
 vals=[D(x['net']) for x in rs]
 return dict(layers=len(rs),buy_cash=str(sum((D(x['cost'])for x in rs),D(0))),original_net=str(sum(vals,D(0))),original_positive=str(sum((max(x,D(0))for x in vals),D(0))),original_negative=str(sum((min(x,D(0))for x in vals),D(0))))
r=read(W/'nd_mobile_authorization_candidate_v1/ROWS.json');s=read(W/'nd_mobile_authorization_candidate_v1/SUMMARY.json');out={};unknown=[]
for win in ('long','strong'):
 p=W/'market_gross_admission_native_v1'/f'full-{win}-v1'/'pair';b=read(p/'D_GROSS10.json.gz',True)
 lp=W/'market_gross_admission_outcome_analysis_v1'/f'full_{win}_v1'/'analysis'/win/'D_GROSS10'/'LAYERS.json'; layers=read(lp);lm={int(x['layer']):x for x in layers};m=b['metadata']
 ip=p/'industry.jsonl.gz';sources[str(ip)]=hashlib.sha256(ip.read_bytes()).hexdigest();inds=[json.loads(t)for t in gzip.open(ip,'rt')]
 fail=collections.defaultdict(list);confirm=collections.defaultdict(list)
 for i,e in enumerate(b['audit']):
  if e['kind']=='pilot_layer_exit' and e['reason']=='CP1_add_protection':
   assert e['at'][11:19]=='15:10:00'
   for lid in e['layers']:
    z=m[str(lid)];assert z['role']=='mobile';fail[(z['sector'],z['episode'])].append((e['at'][:10],int(lid),i))
 for e in inds:
  if e['result'] in ('probe','confirmed','expanded'):confirm[(e['sector'],e['episode'])].append(e['day'])
  else:assert e['result']=='invalidated'
 same_close=0;affected=0
 for a in r[win]:
  l=lm[int(a['layer'])]
  for k,v in l.items():assert a[k]==v,(win,a['layer'],k)
  key=(a['sector'],m[str(a['layer'])]['episode']);day=a['signal_day']
  fs=[f for f in fail[key] if f[0]<=day];cs=[c for c in confirm[key] if c<=day]
  fd=max((f[0]for f in fs),default=None);cd=max(cs,default=None)
  expected=fd is not None and(cd is None or cd<=fd)
  assert a['episode']==key[1] and a['prior_structure_failure_CLOSE']==fd and a['latest_accepted_industry_CP1_CLOSE']==cd
  assert a['confirmed_right_revoked']==expected and a['candidate_affected']==(expected and a['pool_at_fill']=='confirmed')
  assert sorted(a['failure_layer_ids'])==sorted(f[1]for f in fs if f[0]==fd)
  same_close+=int(fd is not None and cd==fd);affected+=int(a['candidate_affected'])
 assert len(r[win])==sum(x['role']=='mobile' for x in layers)
 groups={'all_mobile':r[win]}
 if win=='long':
  for name,lo,hi in [('June22_ND','2022-06-07','2022-06-30'),('MarApr23_ND','2023-03-22','2023-04-21'),('Feb24_ND','2024-02-20','2024-02-29'),('Sep24_resume','2024-09-30','2024-10-08'),('post924_new','2024-10-09','2024-12-31')]:groups[name]=[x for x in r[win]if lo<=x['opened'][:10]<=hi]
 for name,rows in groups.items():
  summary=s['results'][win][name]
  for group,rr in [('all',rows),('affected_confirmed',[x for x in rows if x['candidate_affected']]),('not_affected',[x for x in rows if not x['candidate_affected']]),('revoked_but_original_probe',[x for x in rows if x['confirmed_right_revoked']and not x['candidate_affected']])]:
   st=stat(rr)
   for k,v in st.items():assert D(str(v))==D(str(summary[group][k])),(win,name,group,k)
 out[win]={'all_mobile_rows':len(r[win]),'affected_confirmed_rows':affected,'rowwise_original_layer_fields_and_group_money_PASS':True,'same_day_failure_and_latest_industry_evidence_rows':same_close,'affected_groups':{k:stat([x for x in rs if x['candidate_affected']])for k,rs in groups.items()}}
post=out['long']['affected_groups']['post924_new'];mobile=D(s['results']['long']['post924_new']['all']['original_net']);entire=D('-186615.4970584907010');net=D(post['original_net'])
# Bind original implementation source for request/fill and runner ordering; no importing.
sp=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py');jp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py')
for p in (sp,jp,W/'nd_mobile_authorization_candidate_v1/PRE_ANALYSIS_CARD.txt',W/'nd_mobile_authorization_candidate_v1/analyze_saved_permissions.py'):sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
z=dict(status='PASS_LIMITED_SAVED_ASSOCIATION_AND_EXPLICIT_P1_CLOCK_ONLY',windows=out,trigger='audit pilot_layer_exit CP1_add_protection logged at CLOSE after request_reduction/update of exit responsibility; NOT actual sell fill',same_close_order='Original J.Runner.planning: stock structural exits -> sync -> industry.observe/stage_events -> stock pending intents; original opening: actual exit fills -> fresh stock route/reserve. P1 explicitly gives failure-CLOSE priority and requires STRICTLY later industry CLOSE, so same-CLOSE industry evidence does not renew this added right.',post_affected_share_of_mobile_net_loss_pct=str(net/mobile*100),post_affected_share_of_entire_post_net_loss_pct=str(net/entire*100),decision_scope='STOP is supported for this specific request-CLOSE P1 association by profitable counterexamples, not for every possible authorization mechanism or destruction timestamp. No counterfactual probe quantities, deletion profit, execution or full financial certification.',unknown=['READOUT file absent at review time; PRE_ANALYSIS_CARD/SUMMARY/ROWS/source reviewed.','No cross-file global timestamp sequencer exists in day-only industry log; ordering is bound to actual frozen runner source, not guessed by date.','No runtime P1 implementation exists; candidate cannot claim actual stock commitment was changed.'],new_accounts_indicators_or_financial_events=0,source_SHA256=sources)
for p,h in sources.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
z['checker_SHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();dest=O/'LIMITED_P1_REVIEW.json';dest.write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n');print('PASS',hashlib.sha256(dest.read_bytes()).hexdigest());print(json.dumps({k:z[k]for k in ['post_affected_share_of_mobile_net_loss_pct','post_affected_share_of_entire_post_net_loss_pct','windows']},ensure_ascii=False))
