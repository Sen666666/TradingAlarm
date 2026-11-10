"""One predeclared conditional opportunity-boundary study. No Account/Runner."""
import os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import sys,json,gzip,hashlib,time,math,copy
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent; ROOT=O.parent
P=ROOT/'account_comparison_continuous_v1/run_1200000/pair'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
sys.path.insert(0,str(ROOT/'account_comparison_continuous_v1/factors'))
from continuous_factors import OpenFactorTimeline
START,END='2022-01-04','2026-05-15'
Z=D(0);ONE=D(1);SLIP=D('.0005')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def out(n,x):
 p=O/n;assert not p.exists(),('no overwrite',p)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def jl(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def fee(q,p,sched,side,par):
 return sum(sched.incremental(side,D(q)*p,{}, {},ONE,shares=q,par_value=par).values(),Z)
def protection(q,p,f,sched,par):
 return max(Z,D(q)*(p-f*(ONE-SLIP))+fee(q,p,sched,'buy',par)+fee(q,f*(ONE-SLIP),sched,'sell',par))
def hashadd(h,p):h[str(p)]=sha(p)
def domain():
 assert not (O/'DOMAIN.parquet').exists()
 src={}
 for p in [O/'PROTOCOL.json',Path(__file__),P/'PVR.json.gz',P/'daily.jsonl.gz',P/'opportunities.jsonl.gz',P/'rank-policy.jsonl.gz',U/'INDUSTRY_MANIFEST.json',U/'STOCK_MANIFEST.json']:
  hashadd(src,p)
 a=json.load(gzip.open(P/'PVR.json.gz','rt'))
 pending={(d['at'][:10],i['sid']):dict(i,day=d['at'][:10],decision_nav=d['nav']) for d in a['decisions'] for i in d['intents'] if i['role']=='core'}
 assert len(pending)==126994
 sec=[];episodes=[]
 for m in read(U/'INDUSTRY_MANIFEST.json'):
  pp=m['refs']['state'];hashadd(src,pp);s=pd.read_parquet(pp).sort_values('day');s['sector']=m['series']
  valid=s[s.E0_valid & s.E0_episode.notna()].copy()
  for ep,g in valid.groupby('E0_episode',sort=False):
   g=g.sort_values('day');g['receipt_seen']=g.receipt.fillna(False).astype(bool).cummax()
   g['probe_seen']=g.action.eq('probe').cummax()
   g['end_seen']=g.action.eq('end_attempt').cummax()
   g['unknown_seen']=g.action.eq('unknown').cummax()
   g['ep_start']=g.day.iloc[0];g['left_truncated']=g.day.iloc[0]<START
   g['pre_first_cp']=~g.receipt_seen & ~g.probe_seen & ~g.end_seen & ~g.unknown_seen
   sec.extend(g[g.day.between(START,END)][['sector','day','E0_episode','ep_start','left_truncated','pre_first_cp','receipt_seen','probe_seen','end_seen','unknown_seen','E0_valid','action']].to_dict('records'))
   cp=g[g.action.eq('probe')]
   rawcp=g[g.receipt]
   following=s[s.day>g.day.iloc[-1]]
   episodes.append(dict(sector=m['series'],episode=ep,ep_start=g.day.iloc[0],last_E0_day=g.day.iloc[-1],E0_end=following.day.iloc[0] if len(following) else None,first_accepted_CP=cp.day.iloc[0] if len(cp) else None,first_raw_CP=rawcp.day.iloc[0] if len(rawcp) else None,left_truncated=g.day.iloc[0]<START))
 ss={(r['sector'],r['day']):r for r in sec}
 held={r['at'][:10]:set(r['positions']) for r in jl(P/'daily.jsonl.gz') if r['account']=='PVR'}
 rows=[];denom=Counter()
 for r in jl(P/'opportunities.jsonl.gz'):
  k=(r['day'],r['sid'])
  if r['account']!='PVR' or k not in pending:continue
  i=pending[k]
  assert not r['held'] and r['sid'] not in held[r['day']] and r['core_Q'] is True and 'core' in r['roles'] and not r['barriers'] and not i['size_reject'] and i['cap']>0
  denom['all_original_core_pending']+=1
  s=ss.get((r['sector'],r['day']))
  if not s:denom['E0_invalid']+=1;continue
  if not s['pre_first_cp']:
   denom['E0_valid_but_prior_or_current_CP_or_failure_or_unknown']+=1;continue
  rows.append(dict(**i,sector=r['sector'],episode=s['E0_episode'],ep_start=s['ep_start'],left_truncated=s['left_truncated'],stock_cp_fresh=r['CP1_id'] is not None))
 c=pd.DataFrame(rows).sort_values(['day','priority_rank','sid']).reset_index(drop=True)
 assert not c.duplicated(['day','sid']).any()
 # Native ranking is used unchanged, not re-sorted PVR values.
 keys=set(zip(c.day,c.sid));seen=set()
 for r in jl(P/'rank-policy.jsonl.gz'):
  k=(r['day'],r['sid'])
  if r['account']=='PVR' and k in keys:
   i=pending[k];assert r['priority_rank']==i['priority_rank'];seen.add(k)
 assert seen==keys
 sm={m['symbol']:m for m in read(U/'STOCK_MANIFEST.json')}
 for sid,g in c.groupby('sid'):
  pp=sm[sid]['refs']['facts'];hashadd(src,pp)
  f=pd.read_parquet(pp,columns=['e0_ready','i_target','g_ready','i_buy']).reindex(pd.DatetimeIndex(g.day))
  assert f.e0_ready.eq(1).all() and f.i_target.eq(1).all() and f.g_ready.eq(True).all() and f.i_buy.eq(True).all(),sid
 c['row']=range(len(c))
 c.to_parquet(O/'DOMAIN.parquet',index=False)
 pd.DataFrame(episodes).to_csv(O/'EPISODE_CALENDAR.csv',index=False)
 out('DOMAIN_QA.json',dict(**denom,candidate_rows=len(c),dates=c.day.nunique(),stocks=c.sid.nunique(),sectors=c.sector.nunique(),episodes=c.episode.nunique(),left_truncated_rows=int(c.left_truncated.sum()),left_truncated_episodes=c[c.left_truncated].episode.nunique(),native_pending_and_opportunity_and_stock_facts_and_rank_verified=True,no_account_run=True))
 out('DOMAIN_HASHES.json',src);print(read(O/'DOMAIN_QA.json'),flush=True)
def inputs():
 assert (O/'DOMAIN.parquet').exists() and not (O/'NEXT_OPEN_INPUTS.parquet').exists()
 c=pd.read_parquet(O/'DOMAIN.parquet');src=read(O/'DOMAIN_HASHES.json')
 rulespath=B/'inputs-v2/market-rules.json';protopath=B/'inputs-v2/economic-protocol.json';rawpath=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
 rules=read(rulespath);proxies=read(protopath)['approved_proxy_ids'];rm={r['series_id']:r for r in read(rawpath)['series']}
 cal=pd.DatetimeIndex([r['at'][:10] for r in jl(P/'daily.jsonl.gz') if r['account']=='PVR'])
 assert cal.is_unique
 for pp in [rulespath,protopath,rawpath,B/'code/sector_account.py',B/'code/market_rules.py',ROOT/'account_comparison_continuous_v1/factors/continuous_factors.py']:hashadd(src,pp)
 values=[];names=rules.get('security_metadata',{})
 for n,(sid,g) in enumerate(c.groupby('sid')):
  rec=rm[sid];pp=rec['raw']['path'];ap=rec['adjustment']['actions']['path'];hashadd(src,pp);hashadd(src,ap)
  raw=pd.read_parquet(pp);raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date));raw=raw.sort_index()
  events=read(ap)['events']
  tf=OpenFactorTimeline(raw,events,method=rec['adjustment']['method'],end=END)
  for r in g.to_dict('records'):
   t=cal.get_loc(pd.Timestamp(r['day']));q=dict(row=r['row'],sid=sid,day=r['day'],name=names.get(sid,{}).get('name',''),industry_name=names.get(sid,{}).get('industry',''),input_status='KNOWN')
   if t+1>=len(cal):q.update(input_status='NO_NEXT_OPEN_IN_ACCOUNT_WINDOW',open_day=None);values.append(q);continue
   od=cal[t+1];ods=str(od.date());q['open_day']=ods
   if od not in raw.index or not np.isfinite(raw.loc[od,'open']) or raw.loc[od,'open']<=0:q['input_status']='MISSING_OPEN';values.append(q);continue
   if rec.get('unavailable_from') and ods>=rec['unavailable_from']:q['input_status']='SOURCE_UNAVAILABLE';values.append(q);continue
   if any(l['end']<ods<rr['start'] for l,rr in zip(rec.get('segments',()),rec.get('segments',())[1:])):q['input_status']='SOURCE_DISCONTINUITY';values.append(q);continue
   try:
    rule=QuantityRule(**version_on(rules['quantity_versions'].get(sid,[]),ods,proxies)['rule'])
    ident=market_identity_on(rules,sid,ods,proxies);sd=version_on(rules['fee_versions'][ident['venue']],ods,proxies)['schedule']
    sched=FeeSchedule(sd['schedule_id'],tuple(FeeComponent(**a) for a in sd['components']))
    par=D(str(names[sid]['par_value'])) if names.get(sid,{}).get('par_value') is not None else None
    op=D(str(raw.loc[od,'open']));fac=tf.factor(ods);p=op*(ONE+SLIP);floor=D(str(r['floor']))/fac;m=rule.buy_minimum
    gross=D(m)*p;buyfee=fee(m,p,sched,'buy',par);pr=protection(m,p,floor,sched,par)
    reject=[]
    if op<=floor:reject.append('open_at_or_below_protection')
    if m>r['cap'] or gross>D(str(r['budget'])) or pr>D(str(r['risk_budget'])):reject.append('open_minimum_exceeds_frozen_contract')
    q.update(raw_open=str(op),factor=str(fac),price=str(p),floor_raw=str(floor),quantity=int(m),gross=str(gross),buy_fee=str(buyfee),nominal_risk=str(D(m)*max(Z,p-floor)),protection_risk=str(pr),original_risk_budget=str(r['risk_budget']),fee_schedule=sd['schedule_id'],quantity_rule=rule.rule_id,preview_reject=','.join(reject),adjusted_open=str(op*fac))
   except (RuleUnavailable,ValueError,KeyError) as e:q.update(input_status='RULE_OR_FACTOR_UNKNOWN',input_error=str(e))
   values.append(q)
  if (n+1)%300==0:print('INPUTS',n+1,flush=True)
 v=pd.DataFrame(values);assert len(v)==len(c);v.to_parquet(O/'NEXT_OPEN_INPUTS.parquet',index=False)
 out('INPUT_HASHES.json',src);out('INPUT_QA.json',dict(rows=len(v),status=v.input_status.value_counts().to_dict(),preview_rejects=v.get('preview_reject',pd.Series()).fillna('UNKNOWN').value_counts().to_dict(),future_labels_computed=False))
 print(read(O/'INPUT_QA.json'),flush=True)
if __name__=='__main__':
 {'domain':domain,'inputs':inputs}[sys.argv[1]]()
