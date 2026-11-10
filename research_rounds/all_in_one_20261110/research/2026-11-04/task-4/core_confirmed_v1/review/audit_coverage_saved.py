"""Independent saved/source joins and scalar fees; no native import or new ledger."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
import json,gzip,hashlib,time
import pandas as pd
R=Path(__file__).resolve().parent;P=R.parent;T=P.parent;O=P/'coverage';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Q=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0);SLIP=D('.0005');begun=time.monotonic();sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);raw=p.read_bytes();sources[str(p.resolve())]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
def lines(p):
 with gzip.open(p,'rt')as f:
  for s in f:yield json.loads(s)
def effective(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))
def fee(q,p,s,side,par):
 v=Z
 for c in s['components']:
  if c.get('side','both')not in(side,'both'):continue
  basis=c.get('amount_basis','notional');a=D(q)*p if basis=='notional'else D(q)if basis=='shares'else D(q)*par
  t=max(D(str(c.get('minimum_local',0))),a*D(str(c['rate'])))
  if c.get('maximum_local')is not None:t=min(t,D(str(c['maximum_local'])))
  if c.get('rounding_unit')is not None:
   u=D(str(c['rounding_unit']));t=(t/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  v+=t
 return v
def period(day):return day[:4]if day[:4]in('2022','2023')else('2024_924_after'if day>='2024-09-24'else'2024_pre924')if day[:4]=='2024'else'2025H2'if day[:4]=='2025'else'2026H1'
def group(x):return x['window'],x['sid'],tuple(x['original_intent']['epoch'])
allowed={'probe_risk','sector_capital'};numeric=allowed|{'cash_or_original_reserve','sector_risk','pool_capital','stock_capital'};preview={'missing_open','open_minimum_exceeds_frozen_contract','open_at_or_below_protection'}
summary=read(O/'SUMMARY.json');detail={x['key']:x for x in lines(O/'NARROW_CANDIDATES.jsonl.gz')};savedres=read(O/'ORIGINAL_RESERVED_ORDERS.json');rules=read(Q/'pvr-act-comparison-20261027/execution-rules-v2.json');liq={(x['window'],x['OPEN']):x for x in read(T/'cash_release_v1/ALL_MARKET_OPEN_LIQUIDITY_STOCKS.json')};sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json');canonical=[{x['sid']:x for x in read(p)}for p in[W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]]
initial={}
for m in im:
 f=pd.read_parquet(m['refs']['state'],columns=['day','E0_episode','attempt_id','action','receipt_id','stage'])
 for window,start in [('long','2022-01-01'),('strong','2025-07-01')]:
  past=f[f.day<start];last=past.iloc[-1];ep=last.E0_episode
  if pd.isna(ep):non=past.E0_episode.dropna();ep=non.iloc[-1]if len(non)else None
  attempt=None;level=0
  if pd.notna(last.attempt_id):first=past[(past.attempt_id==last.attempt_id)&(past.action=='probe')].iloc[0];attempt=str(ep)+':'+str(first.receipt_id);level=int(last.stage)-1
  initial[window,m['series']]={'day':'INITIAL_BEFORE_WINDOW','episode':ep,'attempt':attempt,'financial_level':level,'result':'initial_native_warm_state'}
books={};fund={};ops={};intents={};dec={};states={};prefixdata={};reservations={};original_core_rows={};fill_epochs={};receipts={}
for window in ['long','strong']:
 base=T/'new_price_trend_v1/funding/runs'/(window+'_OFF')/'pair'
 with gzip.open(base/'B.json.gz','rt')as f:b=json.load(f)
 books[window]=b;dec[window]={x['at'][:10]:x for x in b['decisions']};intents[window]={(day,i['sid']):i for day,d in dec[window].items()for i in d['intents']if i['role']=='core'};ff=list(lines(base/'funding.jsonl.gz'));fund[window]=ff
 wanted={(liq[window,x['at'][:10]]['signal_day'],x['sid'])for x in ff if x['role']=='core'and'09:30:00'in x['at']};ops[window]={(x['day'],x['sid']):x for x in lines(base/'opportunities.jsonl.gz')if(x['day'],x['sid'])in wanted};assert len(ops[window])==len(wanted)
 events=defaultdict(list)
 for x in lines(base/'industry.jsonl.gz'):events[x['day']].append(x)
 current={x['series']:initial[window,x['series']]for x in im};states[window]={}
 for day in dec[window]:
  for x in events[day]:current[x['sector']]=x
  states[window][day]=current.copy()
 for t in b['trades']:
  if t['side']=='buy'and t['kind']=='core':fill_epochs[window,t['security_id'],tuple(t['epoch'])]=min(fill_epochs.get((window,t['security_id'],tuple(t['epoch'])),'9999'),t['at'])
 journal={(x['at'][:10],x['sid'],x['role']):x for x in b['journal']if x['kind']=='real_reserve'};aud={x['order_id']:x for x in b['audit']if x['kind']=='reserve'};prefix=[];od=None;consumed=set()
 for idx,x in enumerate(ff):
  if'09:30:00'not in x['at']:continue
  if od!=x['at'][:10]:od=x['at'][:10];prefix=[]
  if x['role']=='core':
   day=liq[window,od]['signal_day'];op=ops[window][day,x['sid']];key='|'.join([window,day,x['sid'],'core']);assert key not in original_core_rows;original_core_rows[key]=(window,idx,x);prefixdata[key]=(tuple(prefix),op['CP1_id']not in consumed if op['CP1_id']else False)
  if x['result']=='reserved':
   j=journal[od,x['sid'],x['role']];a=aud[j['order']];bo=b['budget']['orders'][j['budget_order']];key=window+'|'+j['budget_order'];saved=savedres[key]
   for k,v in {'window':window,'OPEN':od,'funding_stream_index':idx,'sid':x['sid'],'role':x['role'],'sector':bo['sector'],'episode':bo['episode'],'attempt':bo['attempt'],'pool':j['pool'],'CP1_id':j['receipt'],'shares':j['shares'],'price':j['price'],'gross':a['gross_budget_cny'],'buy_fee':a['fee_reserved_cny'],'native_order_id':j['order'],'native_budget_order':j['budget_order']}.items():assert saved[k]==v,(key,k)
   reservations[key]=saved;prefix.append(key)
   if j['receipt']:consumed.add(j['receipt'])
 assert time.monotonic()-begun<60,'read-only review time bound'
assert set(reservations)==set(savedres)
def getcp(window,sid,day):
 k=window,sid
 if k not in receipts:
  paths=[(sm[sid]['refs']['receipts'],sm[sid]['output_sha256'][sm[sid]['refs']['receipts']])]if window=='strong'else[(m[sid]['output_path'],m[sid]['output_sha256'])for m in canonical]
  out={}
  for p,digest in paths:
   raw=read(p);assert sources[str(Path(p).resolve())]==digest
   for x in raw:
    d=x['confirmed_day']
    if('2022-01-01'<=d<='2024-12-31')if window=='long'else('2025-07-01'<=d<='2026-06-30'):assert d not in out;out[d]=x
  receipts[k]=out
 return receipts[k].get(day)
counts=Counter();strata=defaultdict(Counter);seen=set();narrow=set();first={};eligiblefirst={};witnesses=0;cp_count=0;firstrows={}
def bump(c,r):
 c.update({'total':1,'original_probe_reserved':int(r['stage']=='reserved_unchanged'),'original_preview_failed':int(r['stage']=='OPEN_preview_failed'),'route_rejected':int(r['stage']=='probe_route_rejected'),'allowed_failure_set':int(r['raw_reject_set_eligible']),'dual_CP_mature_numeric':int(r['dual_proof_mature_before_reject_gate']),'dual_CP_mature_cash_block':int(r['dual_proof_mature_before_reject_gate']and'cash_or_original_reserve'in r['original_failure_set']),'dual_CP_mature_sector_risk_block':int(r['dual_proof_mature_before_reject_gate']and'sector_risk'in r['original_failure_set']),'same_attempt_front_probe_migration_block':int(r['raw_reject_set_eligible']and r['dual_proof_mature_before_reject_gate']and not r['native_same_attempt_migration_necessary_pass']),'narrow_candidates':int(r['narrow_fallback_necessary_candidate'])})
for r in lines(O/'ALL_CORE_OPEN_ORIGINAL_MOTHER.jsonl.gz'):
 key=r['key'];assert key not in seen;seen.add(key);window,idx,x=original_core_rows[key];day,sid=r['signal_day'],r['sid'];i=intents[window][day,sid];op=ops[window][day,sid];s=states[window][day][op['sector']];tags=set(x['result'].split(','));num=bool(tags)and tags<=numeric;cp=getcp(window,sid,day)if op['CP1_id']else None;front,unused=prefixdata[key];same=[reservations[k]for k in front if reservations[k]['sector']==op['sector']];blocked=[a['key']for a in same if a['pool']=='probe'and a['attempt']==s['attempt']]
 assert r['funding_stream_index']==idx and r['original_result']==x['result']and r['original_failure_set']==sorted(tags)and r['original_intent']==i and r['original_opportunity']==op and r['industry_financial_at_signal']==s
 assert op['core_Q']is True and op['held']is False and not op['barriers']and'core'in op['roles']and i['epoch']is not None and not i.get('size_reject')and i['cap']>0
 assert fill_epochs.get((window,sid,tuple(i['epoch'])),'9999')>day+' 23:59:59'
 assert D(i['risk_budget'])==D(dec[window][day]['nav'])*D('.0025') and r['decision_NAV']==dec[window][day]['nav']
 assert r['period']==period(day)and r['year']==day[:4]
 assert r['same_day_canonical_CP']==cp
 if cp:
  cp_count+=1;assert cp['receipt_id']==op['CP1_id']and cp['canonical_series']==sid and cp['confirmed_day']==day and int(cp['source_segment'])==i['epoch'][0]and cp['formation_start_exclusive']<=cp['formation_end_inclusive']==day and not cp['trace_unknown']
 fresh=bool(cp and unused);pre=num and fresh and int(s['financial_level'])>=1;candidate=pre and tags<=allowed and not blocked;qr=effective(rules['quantity_versions'][sid],r['OPEN'])['rule']
 assert r['CP_unconsumed_at_candidate']==fresh and r['dual_proof_mature_before_reject_gate']==pre and r['raw_reject_set_eligible']==(num and tags<=allowed)and r['narrow_fallback_necessary_candidate']==candidate
 assert r['dated_OPEN_minimum']==qr['buy_minimum']and r['dated_OPEN_quantity_rule']==qr and r['same_OPEN_prior_same_attempt_probe_order_keys']==blocked and r['native_same_attempt_migration_necessary_pass']==(not blocked)
 assert r['preexisting_S0_buy_reserve']==liq[window,r['OPEN']]['prior_existing_submitted_order_reserve']==0
 assert r['prior_original_reserve_count']==len(front)and r['prior_original_same_sector_reserve_count']==len(same)and D(r['prior_original_reserved_gross'])==sum((D(reservations[k]['gross'])for k in front),Z)and D(r['prior_original_reserved_buy_fees'])==sum((D(reservations[k]['buy_fee'])for k in front),Z)and D(r['prior_original_same_sector_reserved_gross'])==sum((D(k['gross'])for k in same),Z)
 assert r['stage']==('reserved_unchanged'if x['result']=='reserved'else'OPEN_preview_failed'if x['result']in preview else'probe_route_rejected')
 bump(counts,r);bump(strata['window',window],r);bump(strata['period',r['period']],r)
 if r['industry']=='半导体':bump(strata['semi',r['period']],r)
 g=group(r)
 if g not in first:first[g]=key;firstrows[key]=r
 if candidate:
  narrow.add(key);eligiblefirst.setdefault(g,key);d=detail[key]
  for k,v in r.items():assert d[k]==v,(key,k)
  scalar=d['minimum_frozen_signal_scalar'];q=qr['buy_minimum'];ref=D(i['reference_price']);fl=D(i['frozen_floor_raw']);factor=D(i['floor'])/fl;mf=max(D(i['floor']),D(str(cp['original_candidate'])))/factor;par=D(rules['security_metadata'][sid]['par_value']);venue=effective(rules['venue_versions'][sid],day)['venue'];fs=effective(rules['fee_versions'][venue],day)['schedule']
  for field,floor in [('CORE_fee_risk_at_signal_reference',fl),('Mobile_fee_risk_at_signal_reference',mf)]:
   stop=floor*(1-SLIP);risk=max(Z,D(q)*(ref-stop)+fee(q,ref,fs,'buy',par)+fee(q,stop,fs,'sell',par));assert D(scalar[field])==risk
  assert scalar['q']==q and D(scalar['frozen_CORE_risk_budget'])==D(i['risk_budget'])and scalar['frozen_cap']==i['cap']and D(scalar['frozen_gross_budget'])==D(i['budget'])
  ms=[a for a in savedres.values()if a['window']==window and a['OPEN']==r['OPEN']and a['sid']==sid and a['role']=='mobile'];w=d['original_confirmed_MOBILE_minimum_existence_witness'];checks={}
  if ms:
   assert len(ms)==1;m=ms[0];venue=effective(rules['venue_versions'][sid],r['OPEN'])['venue'];fs=effective(rules['fee_versions'][venue],r['OPEN'])['schedule'];mq=m['shares'];px=D(m['price']);fm=fee(q,px,fs,'buy',par);fb=fee(mq,px,fs,'buy',par)
   checks={'funding_rows_adjacent':m['funding_stream_index']==idx+1,'actual_confirmed':m['pool']=='confirmed','same_CP':m['CP1_id']==cp['receipt_id'],'qmin_no_larger':q<=mq,'min_BUY_legal':q>=qr['buy_minimum']and(q-qr['buy_minimum'])%qr['buy_step']==0,'actual_fee_exact':fb==D(m['buy_fee']),'fee_non_decreasing':fm<=fb,'original_CORE_sector_risk_pass':'sector_risk'not in tags,'original_CORE_preview_pass':r['stage']=='probe_route_rejected'}
   assert w['checks']==checks and w['proven']==all(checks.values())and w['qmin']==q and w['reserved_shares']==mq and D(w['min_buy_fee'])==fm and w['original_MOBILE_order_key']==m['key']
  else:assert not w['proven']and w['reason']=='no_same_OPEN_original_confirmed_MOBILE_reservation'
  witnesses+=int(w['proven'])
 assert time.monotonic()-begun<60,'read-only review time bound'
assert seen==set(original_core_rows)and narrow==set(detail)and len(seen)==117121 and len(narrow)==1536 and witnesses==1374
assert dict(counts)==summary['raw']
for w in ['long','strong']:assert dict(strata['window',w])==summary['by_window'][w]
for p,v in summary['by_period'].items():assert dict(strata['period',p])==v
for p,v in summary['semiconductors_by_period'].items():assert dict(strata['semi',p])==v
fc=Counter()
for x in firstrows.values():bump(fc,x)
assert dict(fc)==summary['first_source_I_any_CORE_OPEN']and len(first)==21085 and len(eligiblefirst)==1459 and list(eligiblefirst.values())==summary['candidate_source_I_first_keys']
target=read(O/'ALL11_TARGET_CROSSCHECK.json');assert len(target)==11 and sum(x['narrow_candidate_detail']is not None for x in target)==9 and all(x['narrow_candidate_detail']['original_confirmed_MOBILE_minimum_existence_witness']['proven']for x in target if x['narrow_candidate_detail'])
for x in target:
 k=x['full_mother']['key'];assert k in seen
 if x['narrow_candidate_detail']:assert x['narrow_candidate_detail']==detail[k]
 else:assert'sector_risk'in x['full_mother']['original_failure_set']
# Bind output/source/artifact bytes reviewed, without another native or price run.
for n in ['ALL_CORE_OPEN_ORIGINAL_MOTHER.jsonl.gz','NARROW_CANDIDATES.jsonl.gz','ORIGINAL_RESERVED_ORDERS.json','cover_original.py','SUMMARY.json','ALL11_TARGET_CROSSCHECK.json']:sources[str((O/n).resolve())]=sha(O/n)
result={'passed':True,'scope':'All saved raw CORE OPEN rows independently joined to original funding/opportunity/intents, epoch fills, canonical receipts, native industry startup/forward state, real reservation prefix and dated quantities; all candidate fee-risk scalars/minimum witnesses recomputed without native financial initialization.','raw_CORE_OPEN':117121,'by_window':{'long':70128,'strong':46993},'original_probe_reserved':829,'preview_failed':622,'narrow_candidates':1536,'candidate_windows':{'long':1062,'strong':474},'unique_original_source_I':21085,'source_I_with_any_candidate':1459,'first_CORE_OPEN_candidates':183,'CP_trace_source_rows_checked':cp_count,'all_original_reservations_checked':len(savedres),'minimum_only_existence_witnesses':1374,'unwitnessed_not_infeasible':162,'H1_semiconductor_targets':{'original_OPEN_branches':11,'narrow':9,'minimum_witnesses':9,'sector_risk_excluded':2},'causal_scope':['Candidate predicate uses only original qualification, fixed CP, financial maturity, failure set, unconsumed CP and pending migration lock; Mobile reservation is after-selection audit only.','Original numeric min set plus preview proves retained cash/sector-risk/stock guards; adjacent same-prefix confirmed Mobile legal reserve q>=COREmin and nondecreasing fees prove mature sector capital/cash minimum existence, conditional on typed permission.','Migration changes pool only; does not reduce all-pool sector capital/risk or create cash.','No witness proves maximum size, fill window, changed-policy resource availability, holding path or portfolio profit.','Full pre-candidate numeric SC/SR/NAV and altered policy feedback remain uncomputed.'],'coverage_material_for_next_technical_check':True,'candidate_patch_or_financial_run_admitted':False,'reviewer_new_accounts_or_ledgers':0,'reviewer_new_marks':0,'seconds':time.monotonic()-begun,'sources_sha256':sources};(R/'COVERAGE_AND_MINIMUM_WITNESS_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['sources_sha256','causal_scope']},ensure_ascii=False))
