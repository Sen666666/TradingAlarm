import json,gzip,pathlib,collections,hashlib
import pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');S=R/'act_only_ablation_continuous_v1';N=R/'act_candidate_funnel_v1';O=R/'act_entry_research_independent_audit_v1';U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
C=json.loads((N/'CONTRACT.json').read_text()); periods=C['periods']; df=pd.read_parquet(N/'ROLE_CANDIDATE_TRACE.parquet'); keys=['account','signal_day','sid','role']; assert not df.duplicated(keys).any();tmap={tuple(r[:4]):r[4:] for r in df[keys+['industry_active','original_pending','actual_first_entry','actual_buy_shares','held_at_signal','priority_rank','frozen_cap','native_birth']].itertuples(index=False,name=None)}
def rows(p):
 for l in gzip.open(p,'rt'):yield json.loads(l)
def per(day):return [p for p,(lo,hi) in periods.items() if lo<=day<=hi]
closes={}; days=[]
for d in rows(S/'run/pair/daily.jsonl.gz'):
 day=d['at'][:10];closes[d['account'],day]=(bool(d['on']),set(d['positions']));
 if d['account']=='PVR':days.append(day)
prev={d:days[i-1] for i,d in enumerate(days) if i};active={};births={}
for m in json.loads((U/'INDUSTRY_MANIFEST.json').read_text()):
 z=pd.read_parquet(m['refs']['state'],columns=['day','E0_valid','attempt_id','stage']);z=z[z.day.isin(days)]
 for x in z.itertuples():active[m['series'],x.day]=bool(x.E0_valid and pd.notna(x.attempt_id) and x.stage>0)
# Independent sequential native-birth state, no author import or vectorized grouping reuse.
for m in json.loads((U/'STOCK_MANIFEST.json').read_text()):
 z=pd.read_parquet(m['refs']['facts'],columns=['segment_id','e0_target']);state={};live={};lookup={}
 for day,seg,on in z.reset_index().itertuples(index=False,name=None):
  d=str(day.date());on=False if pd.isna(on) else bool(on)
  if on and not state.get(seg,False):live[seg]=m['symbol']+':'+d
  lookup[d]=live.get(seg,'UNKNOWN') if on else 'UNKNOWN';state[seg]=on
 births[m['symbol']]=lookup
for key,v in tmap.items():assert births[key[2]].get(key[1],'UNKNOWN')==v[-1],('nativebirth',key)
# Check actual first-entry markers from raw 0-to-0 trade cycles using source round membership independently audited in audit_loss.
source_rounds=pd.read_csv(S/'analysis/STOCK_ROUNDS.csv');first={(r.account,int(r.initial_layer)) for r in source_rounds.itertuples()};pending={};buys={};rankrows=collections.defaultdict(list)
for arm in ['PVR','NOACT']:
 a=json.load(gzip.open(S/f'run/pair/{arm}.json.gz','rt'))
 for d in a['decisions']:
  for x in d['intents']:pending[arm,d['at'][:10],x['sid'],x['role']]=x
 for t in a['trades']:
  if t['side']=='buy':
   key=(arm,t['signal_at'][:10],t['security_id'],'core' if t['kind']=='core' else 'mobile');assert key not in buys;buys[key]={'first':(arm,int(t['layer'])) in first,'entry_day':t['at'][:10],'shares':int(t['shares'])}
for k,x in pending.items():
 assert k in tmap and tmap[k][1];assert tmap[k][5]==x['priority_rank'] and tmap[k][6]==x['cap']
assert sum(v[1] for v in tmap.values())==len(pending)
for k,b in buys.items():
 v=tmap[k];assert v[2]==b['first'] and v[3]==b['shares'] and v[4]==(not b['first'])
assert sum(v[3]>0 for v in tmap.values())==len(buys)
rankroles=set()
for x in rows(S/'run/pair/rank-policy.jsonl.gz'):
 rankrows[x['account'],x['day']].append(x)
 for role in x['roles']:
  k=(x['account'],x['day'],x['sid'],role);rankroles.add(k);assert pending[k]['priority_rank']==x['priority_rank']
assert rankroles==set(pending)
for k,g in rankrows.items():
 assert len({x['sid'] for x in g})==len(g);assert sorted(x['original_slot'] for x in g)==list(range(len(g)));assert sorted(x['final_slot'] for x in g)==list(range(len(g)))
# Raw opportunity facts and all published stockday stages, no candidate return recomputation.
fund=collections.defaultdict(list);reserved=set()
for x in rows(S/'run/pair/funding.jsonl.gz'):
 phase='CLOSE' if x['at'][11:16]=='15:10' else 'OPEN';sd=x['at'][:10] if phase=='CLOSE' else prev[x['at'][:10]];key=(x['account'],sd,x['sid'],x['role']);fund[key].append((phase,x['result']))
 if x['result']=='reserved':reserved.add(key[:3])
def term(key):
 if key in buys:return 'ACTUAL_FIRST_ENTRY' if buys[key]['first'] else 'ACTUAL_HELD_ADD'
 opens=[v for phase,v in fund[key] if phase=='OPEN']
 if 'reserved' in opens:return 'RESERVED_NO_FILL'
 if opens:
  if 'industry_invalidated' in opens:return 'OPEN_INDUSTRY_INVALIDATED'
  if set(opens)&{'missing_open','open_at_or_below_protection','open_minimum_exceeds_frozen_contract'}:return 'OPEN_PRICE_OR_FROZEN_SIZE_REJECT'
  return 'OPEN_BUDGET_OR_TOKEN_REJECT'
 if key[:3] in reserved:return 'SAME_STOCK_OTHER_ROLE_RESERVED'
 return 'RIGHT_CENSORED_NO_NEXT_OPEN' if key[1]==days[-1] else 'UNKNOWN_PLANNED_NO_OPEN_RECORD'
exclusive_counts=collections.Counter();counts=collections.Counter();seen=set();rolecount=0;rawcounts=collections.Counter()
for r in rows(S/'run/pair/opportunities.jsonl.gz'):
 arm,day,sid=r['account'],r['day'],r['sid'];on,held=closes[arm,day];assert r['held']==(sid in held);isactive=active[r['sector'],day];roles=r['roles'];barriers=r['barriers'];q=r['core_Q'] is True or (r['mobile_Q'] is True and bool(r['CP1_id']));sector_signal=not any(b.startswith('sector_up:') for b in barriers);birth=births[sid].get(day,'UNKNOWN');plans=[role for role in roles if (arm,day,sid,role) in pending];bs=[buys[arm,day,sid,role] for role in roles if (arm,day,sid,role) in buys];legal=bool(roles and not barriers and isactive)
 stages={'01_FIXED_UNIVERSE':True,'01b_ACTIVE_NATIVE_STRUCTURE_PRESENT':birth!='UNKNOWN','02_ACT_ON':on,'03_ACT_ON_SECTOR_SIGNAL_PASS':on and sector_signal,'04_ACT_ON_SECTOR_SIGNAL_AND_ACTIVE':on and sector_signal and isactive,'RAW_ANY_FRESH_SIGNAL_Q':q,'RAW_ANY_ROLE':bool(roles),'RAW_FLAT_ROLE':bool(roles) and not r['held'],'05_ALL_ABOVE_FRESH_SIGNAL_Q':on and sector_signal and isactive and q,'NATIVE_NO_BARRIER_ROLE':bool(roles) and not barriers,'06_LEGAL_ROLE_AFTER_INDUSTRY':legal,'NATIVE_ALL_PENDING_STOCKDAYS':bool(plans),'07_LEGAL_POSITIVE_SIZE_RANKED':legal and bool(plans),'08_FLAT_POSITIVE_SIZE_RANKED':legal and not r['held'] and bool(plans),'09_ACTUAL_BUY_STOCKDAYS':bool(bs),'10_ACTUAL_FIRST_ENTRY_STOCKDAYS':any(b['first'] for b in bs)}
 if not on:ex='01_ACT_PAUSED'
 elif not sector_signal:ex='02_SECTOR_SIGNAL_FAIL_OR_UNKNOWN'
 elif not isactive:ex='03_INDUSTRY_ATTEMPT_INACTIVE'
 elif not q:ex='04_NO_FRESH_SIGNAL_OR_STOCK_Q'
 elif not roles:ex='05_NO_ROLE_HELD_OR_CORE_EPOCH_LOCK'
 elif barriers:ex='06_ACCOUNT_PENDING_BARRIER'
 elif not plans:ex='07_CLOSE_SIZE_OR_UNKNOWN_NO_PLAN'
 else:
  terms={term((arm,day,sid,role)) for role in plans};ordered=[('ACTUAL_FIRST_ENTRY','12_'),('ACTUAL_HELD_ADD','13_'),('RESERVED_NO_FILL','11_'),('OPEN_BUDGET_OR_TOKEN_REJECT','10_'),('OPEN_PRICE_OR_FROZEN_SIZE_REJECT','09_'),('OPEN_INDUSTRY_INVALIDATED','08_')];ex=next((prefix+label for label,prefix in ordered if label in terms),'14_'+','.join(sorted(terms)))
 for p in per(day):
  exclusive_counts[arm,p,ex]+=1
  for stage,yes in stages.items():
   if yes:counts[arm,p,stage]+=1
 for role in roles:
  k=(arm,day,sid,role);v=tmap[k];assert v[0]==isactive and v[4]==r['held'];seen.add(k);rolecount+=1
 rawcounts[arm]+=1
assert seen==set(tmap)
published=pd.read_csv(N/'STOCKDAY_FUNNEL.csv')
for r in published.itertuples():assert counts[r.account,r.period,r.stage]==r.stockdays,('stockday',r)
assert len(counts)==len(published)
exclusive=pd.read_csv(N/'EXCLUSIVE_STOCKDAY_STAGES.csv')
for x in exclusive.itertuples():assert exclusive_counts[x.account,x.period,x.exclusive_stage]==x.stockdays
for (arm,p),g in exclusive.groupby(['account','period']):assert g.stockdays.sum()==counts[arm,p,'01_FIXED_UNIVERSE']
# Both clocks bridge to source actual rounds; entry-year differences are legitimate.
clocks=pd.read_csv(N/'FIRST_ENTRY_TWO_CLOCKS.csv');clock_results=[]
for r in clocks.itertuples():
 selected=[(k,b) for k,b in buys.items() if k[0]==r.account and b['first'] and r.period in per(k[1] if r.clock=='SIGNAL' else b['entry_day'])]
 assert len(selected)==r.actual_first_entries and sum(k[-1]=='core' for k,b in selected)==r.core and sum(k[-1]=='mobile' for k,b in selected)==r.mobile
 clock_results.append(r._asdict())
# Old queue exact identity; reject extrapolating old response percentage.
old=pd.read_parquet(R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');print('OLD_COLS',old.columns.tolist())
# Consumer coverage is stockdays (dedup same-stock core/mobile), not role rows or orders.
coverage=pd.read_csv(N/'CONSUMER_COVERAGE.csv');cov=[]
for r in coverage.itertuples():
 z=df[df.account.eq(r.account)&df.signal_day.between(*periods[r.period])&~df.held_at_signal&df.legal_ranked];stock=z[['signal_day','sid','sector']].drop_duplicates();assert len(stock)==r.flat_legal_ranked_stockdays
 pairs=stock.groupby(['signal_day','sector']).size();mult=set(pairs[pairs>=2].index);coexist=sum((x.signal_day,x.sector) in mult for x in stock.itertuples());name='within_sector_coexisting_candidate_stockdays' if hasattr(r,'within_sector_coexisting_candidate_stockdays') else 'within_sector_competitive_candidate_stockdays';assert coexist==getattr(r,name)
 cov.append({'account':r.account,'period':r.period,'flat_legal_stockdays':len(stock),'same_sector_coexist_stockdays':coexist,'coexist_share':coexist/len(stock),'first_entries':r.actual_first_entries})
# Frozen raw output seal is authoritative regardless of newly added report files.
hashes=json.loads((S/'run/OUTPUT_HASHES.json').read_text())
for p,h in hashes.items():
 path=pathlib.Path(p) if pathlib.Path(p).is_absolute() else S/'run'/p;assert hashlib.sha256(path.read_bytes()).hexdigest()==h
out={'status':'PASS','account_runs':0,'candidate_future_return_runs':0,'raw_opportunity_rows':dict(rawcounts),'role_rows':rolecount,'pending_role_rows':len(pending),'rank_stockday_groups_verified_permutation':len(rankrows),'actual_buy_orders':len(buys),'actual_first_entries':sum(b['first'] for b in buys.values()),'native_birth_trace_labels_verified':len(tmap),'stockday_stage_rows_verified':len(published),'exclusive_partition_total_check_only':False,'exclusive_stockday_stage_rows_verified':len(exclusive),'two_clocks':clock_results,'consumer_coverage':cov,'original_run_hashes_verified':len(hashes),'limits':['Exclusive stage hierarchy is descriptive precedence, not a unique causal allocation.','Same-sector coexistence is not evidence of binding budget competition or reranking impact.','Old empty-MOBILE response rate 78.71% does not transfer to all-role ACT-arm first-entry domain.','Native stock_structure labels are not original-I big60 events.','No hypothetical candidate trading returns were computed.']}
(O/'FUNNEL_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
