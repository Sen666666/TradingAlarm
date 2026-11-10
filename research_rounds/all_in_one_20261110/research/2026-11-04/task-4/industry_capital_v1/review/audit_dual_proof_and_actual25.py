"""Original actual role/qualification/fee facts; no route, mark or financial path."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,ROUND_CEILING,ROUND_HALF_UP
from datetime import datetime
import gzip,json,hashlib,time
import pandas as pd
R=Path(__file__).resolve().parent;I=R.parent;W=I.parent;P=I/'actual25_role_entry';M=I/'dual_proof_memo';Z=D(0);SLIP=D('.0005')
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt')as h:
  for s in h:yield json.loads(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dec(x):return D(str(x))
def eff(xs,d):return next(x for x in reversed(xs)if x['from']<=d and(x.get('to')is None or d<x['to']))
t0=time.monotonic();r25=read(P/'ALL25_ACTUAL_ENTRY_ROLE_CHAIN.json');rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');semis={k for k,v in meta.items()if v['industry']=='半导体'};base=W/'new_price_trend_v1/funding/runs/strong_OFF/pair'
with gzip.open(base/'B.json.gz','rt')as h:b=json.load(h)
trades=b['trades'];actual25={t['layer']:t for t in trades if t['side']=='buy'and t['security_id']in semis and'2026-01-01'<=t['at'][:10]<='2026-06-30'};assert len(actual25)==25 and set(actual25)=={x['layer']for x in r25};jfills={j['layer']:j for j in b['journal']if j['kind']=='real_buy_fill'};ds={x['at'][:10]:x for x in rows(base/'daily.jsonl.gz')};decisions={x['at'][:10]:x for x in b['decisions']};ids={x['sid']for x in r25};ops={(x['day'],x['sid']):x for x in rows(base/'opportunities.jsonl.gz')if x['sid']in ids};fund=defaultdict(list)
for x in rows(base/'funding.jsonl.gz'):
 if x['role']=='core'and x['sid']in ids:fund[x['at'][:10],x['sid']].append(x)
inds=list(rows(base/'industry.jsonl.gz'));sm={x['symbol']:x for x in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};facts={};eps={}
for sid in ids:
 fp=Path(sm[sid]['refs']['facts']);assert sha(fp)==sm[sid]['output_sha256'][str(fp)];f=pd.read_parquet(fp,columns=['i_buy','i_target','g_ready','g_grade','g_fresh_up','segment_id','close','raw_close','factor','i_floor']);facts[sid]=f;prior=None;ep=0;watch=None
 for day in decisions:
  p=f.index.searchsorted(pd.Timestamp(day),side='right')-1;key=(bool(f.iloc[p].i_target),int(f.iloc[p].segment_id))if p>=0 else(False,-1)
  if key!=prior:prior=key;ep+=1;watch=None
  if ops[day,sid]['core_Q']is True:watch=(key[1],ep)
  eps[day,sid]=([key[1],ep],list(watch)if watch is not None else None)
def fee(q,p,s,side,par):
 v=Z
 for c in s['components']:
  if c.get('side','both')not in[side,'both']:continue
  basis=c.get('amount_basis','notional');amt=q*p if basis=='notional'else D(q)if basis=='shares'else D(q)*par;t=max(dec(c.get('minimum_local',0)),amt*dec(c['rate']))
  if c.get('maximum_local')is not None:t=min(t,dec(c['maximum_local']))
  if c.get('rounding_unit')is not None:
   u=dec(c['rounding_unit']);t=(t/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  v+=t
 return v
mobile=[];open11=[];size7=[];held6=[];allbranches=Counter()
for r in r25:
 sid,day,lid=r['sid'],r['signal_day'],r['layer'];op=ops[day,sid];assert r['actual_buy']==actual25[lid]and r['original_opportunity']==op;assert r['actual_role']==jfills[lid]['role']and r['actual_pool']==jfills[lid]['pool'];assert r['original_native_current_epoch']==eps[day,sid][0]and r['original_shadow_watch_epoch']==eps[day,sid][1]
 z=facts[sid].loc[day]
 for k,v in r['original_signal_facts'].items():assert z[k]==v,(lid,k,z[k],v)
 prior=[t for t in trades if t['side']=='buy'and t['kind']=='core'and t['security_id']==sid and datetime.fromisoformat(t['at'])<=datetime.fromisoformat(day+'T15:10:00+08:00')];locked=any(t['epoch']==r['original_shadow_watch_epoch']for t in prior);assert r['original_prior_actual_CORE_fills']==prior and r['original_CORE_epoch_locked']==locked
 old=[x for x in ds[day]['layers']if x['sid']==sid];assert old==r['original_same_stock_layers_at_signal'];ci=[i for i in decisions[day]['intents']if i['sid']==sid and i['role']=='core'];assert r['original_CORE_intents']==ci
 ev=next(x for x in reversed(inds)if x['sector']==op['sector']and x['day']<=day);assert r['original_industry_latest_financial_event_at_signal']==ev
 sf=[x for x in fund[day,sid]if'15:10:00'in x['at']];of=[x for x in fund[r['OPEN'],sid]if'09:30:00'in x['at']];assert sf==r['original_CORE_signal_funding_rows']and of==r['original_CORE_OPEN_funding_rows']
 m=r['signal_minimum_CORE_necessary'];qr=eff(rules['quantity_versions'][sid],day)['rule'];venue=eff(rules['venue_versions'][sid],day)['venue'];schedule=eff(rules['fee_versions'][venue],day)['schedule'];q=qr['buy_minimum'];ref=dec(z.raw_close)*(1+SLIP);floor=dec(z.i_floor)/dec(z.factor);sell=floor*(1-SLIP);par=dec(rules['security_metadata'][sid]['par_value']);risk=max(Z,D(q)*(ref-sell)+fee(q,ref,schedule,'buy',par)+fee(q,sell,schedule,'sell',par));nav=dec(decisions[day]['nav']);assert risk==dec(m['fee_inclusive_risk_to_I'])and D(q)*ref==dec(m['minimum_gross'])and nav*D('.0025')==dec(m['original_quarter_percent_risk_budget']);assert m['minimum_risk_pass']==(risk<=nav*D('.0025'))and m['minimum_nominal_pass']==(D(q)*ref<=nav*D('.1'))
 branch=r['original_planning_branch'];allbranches[branch]+=1
 if r['actual_role']=='mobile':
  mobile.append(r);assert bool(z.i_buy)and bool(z.i_target)and bool(z.g_ready)and z.g_grade>=2 and bool(z.g_fresh_up)and r['G1_observed_category']=='warm_fresh';assert r['actual_MOBILE_CP_same_day_identity']and op['CP1_id']==jfills[lid]['CP1_id']
 if branch=='original_CORE_intent_but_OPEN_rejected_before_MOBILE_fill':assert ci and all(x['result']!='reserved'for x in of);open11.append(r)
 if branch=='original_CORE_qualified_but_CLOSE_size_rejected':assert not op['held']and not locked and not ci and sf and any(x['result']=='minimum_unit_exceeds_risk_or_nominal_cap'for x in sf)and risk>nav*D('.0025')and D(q)*ref<=nav*D('.1');size7.append(r)
 if branch=='original_held_prevents_new_CORE':assert op['held'];held6.append(r)
assert len(mobile)==24 and len(open11)==11 and len(size7)==7 and len(held6)==6
failsets=[set(x['result'].split(','))for r in open11 for x in r['original_CORE_OPEN_funding_rows']];assert len(failsets)==11 and sum(s<={'probe_risk','sector_capital'}for s in failsets)==9 and sum('sector_risk'in s for s in failsets)==2 and all('cash_or_original_reserve'not in s for s in failsets);assert Counter(r['original_industry_latest_financial_event_at_signal']['financial_level']for r in open11)==Counter({2:9,1:2});assert all(r['actual_pool']=='confirmed'for r in open11)
assert sum(any(x['kind']=='core'for x in r['original_same_stock_layers_at_signal'])for r in held6)==1;assert sum(not r['original_CORE_epoch_locked']for r in held6)==5
# Primary first-reject mother versus selected actual fallback witnesses are separate.
primary={x['key']:x for x in rows(I/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz')if x['is_first_sector_reject_in_original_source_I_epoch']};duals=[x for x in primary.values()if x['original_opportunity']['CP1_id']and x['original_opportunity']['core_Q']is True and'mobile'in x['original_opportunity']['roles']];assert len(primary)==8335 and len(duals)==2940
h1=[x for x in duals if x['window']=='strong'and x['sid']in semis and'2026-01-01'<=x['OPEN']<='2026-06-30'];saved62=read(M/'H1_SEMICONDUCTOR_ALL62_FIRST_DUAL_PROOF.json');assert len(h1)==len(saved62)==62 and {x['key']for x in h1}=={x['key']for x in saved62};assert sum('cash_or_original_reserve'in x['failure_tags']for x in h1)==61 and sum('sector_risk'in x['failure_tags']for x in h1)==14
w315=read(M/'ORIGINAL_315_SAMEOPEN_DUAL_PROOF.json');assert len(w315)==315 and Counter(x['window']for x in w315)==Counter(long=236,strong=79);commits=read(I/'events/ACTUAL_SAMEOPEN_RESERVE_COMMITMENTS.json')
for x in w315:
 e=primary[x['key']];op=e['original_opportunity'];c=commits[x['window']+'|'+x['actual_MOBILE']['budget_order']];assert x['original_CORE_failure_set']==e['failure_tags']and op['core_Q']is True and not op['held']and not op['barriers'];assert c['CP1_id']==op['CP1_id']and c['role']=='mobile'and c['pool']=='confirmed'and c['OPEN']==e['OPEN']and c['funding_stream_index']>e['funding_stream_index'];assert c['actual_fills_after_all_funding']==x['actual_MOBILE']['fills']and sum(t['shares']for t in c['actual_fills_after_all_funding'])==x['actual_MOBILE']['shares_filled']>0
assert sum(x['H1_semiconductor']for x in w315)==1
res={'passed':True,'scope':'Original strong25 actual-entry facts/roles/epochs/gating and signal minimum risk independently checked; primary dual-proof mother and315 retrospective fallback witnesses identity checked. No route/marks/ledger.','actual25':{'layers':25,'stocks':18,'CORE':1,'MOBILE':24,'all24_mobile_original_I_buy_G1_warm_fresh':True,'branches':dict(allbranches),'held':6,'held_has_actual_CORE':1,'held_only_MOBILE_CORE_epoch_unconsumed':5,'CLOSE_size_reject':7,'these7_risk_alone_sufficient_to_reject_and_nominal_pass':True,'OPEN_CORE_reject_then_MOBILE_confirmed_fill':11,'eleven_financial_levels':{'2':9,'1':2},'eleven_only_probe_or_sector_capital_failures':9,'eleven_sector_risk_also':2,'new_CORE_admission_proved':False},'first_reject_other_denominator':{'all_first':8335,'same_day_dual':2940,'H1_semiconductor_first':167,'H1_first_dual':62,'H1_first_dual_cash_gate':61,'H1_first_dual_sector_risk':14,'first_sameOPEN_MOBILE_fill_witnesses':315,'by_window':{'long':236,'strong':79},'H1_first_sameOPEN_MOBILE_fill_witness':1},'legal_memo_review':['CP-after-I firstCORE architecture already oldBP1; exact presentNo60 typedCORE-confirmed permission remains proposed, not tested profitable.','N1 is TRIAL→CORE after confirmation with different protections/epoch/minimum rules, not permission to arbitrarily convert existingMOBILE.','Industry confirmed/expanded is independent authorization; stockCP alone grants no industry budget.','Typed role, fullflat/originalI/i_buy/S0, actualCORE epoch acrossbothpools, CP source/time/attempt and singleconsume, Mobile fallback exclusivity all must remain explicit.','Original sector1%risk/cash10%/stock10%/.25%I-floor size/fees/units remain;9 observed old-prefix cases are not9 guaranteed newCOREfills.','First62/1 cannot be used as denominator for later actual11/9; neither selected sample proves whole-market policy effect.'],'reviewer_new_accounts':0,'reviewer_new_marks':0,'reviewer_new_route_projections':0,'source_sha256':{str(p.resolve()):sha(p)for p in [Path(__file__),P/'ALL25_ACTUAL_ENTRY_ROLE_CHAIN.json',P/'SUMMARY.json',P/'READOUT.txt',M/'ORIGINAL_315_SAMEOPEN_DUAL_PROOF.json',M/'H1_SEMICONDUCTOR_ALL62_FIRST_DUAL_PROOF.json',M/'LEGALITY_AND_DEDUP.txt']},'seconds':time.monotonic()-t0};(R/'DUAL_PROOF_AND_ACTUAL25_REVIEW.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items()if k not in ['source_sha256','legal_memo_review']},ensure_ascii=False,indent=2))
