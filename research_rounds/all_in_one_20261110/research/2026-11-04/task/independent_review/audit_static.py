from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
import json,hashlib
ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC=ROOT/'C10-account6-ablation-five-snapshots-v1-20261103'
OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def close(a,b):assert abs(D(a)-D(b))<D('1e-15'),(a,b)
f=read(SRC/'AUTHORIZATION_AND_FREEZE.json');sm=read(SRC/'SUMMARY.json')
hashes={}
for p,h in f['sources_sha256'].items():
 assert sha(p)==h,p;hashes[p]=h
for n,h in f['full_candidate_inputs'].items():assert sha(SRC/n)==h,n
cases=[];checks_count=0;all_changes=[]
for day in f['dates']:
 x=read(SRC/f'INPUT-{day}.json');v=x['trusted'];s=v['snapshot'];ds={d['sid']:d for d in v['demands']};lots={l['id']:l for l in s['lots']}
 assert len(ds)==len(v['demands'])
 at=datetime.fromisoformat(s['at'])
 for d in ds.values():
  b=d['receipt_binding'];assert b['sid']==d['sid'] and b['event_id']==d['receipt_id']
  assert s['receipt_registry'][d['receipt_id']]==digest(b)
  assert datetime.fromisoformat(b['start'])<=datetime.fromisoformat(b['end'])<=datetime.fromisoformat(b['confirmed'])==at<datetime.fromisoformat(d['deadline'])
  assert datetime.fromisoformat(d['price_known_at'])<=at and datetime.fromisoformat(d['known_at'])<=at
 modes={};rr={}
 for name in ['ORIGINAL_6','NO_AR6']:
  z=read(SRC/f'{name}-{day}.json');r=z['result'];rr[name]=r
  assert set(r['Q'])==set(ds) and z['financial_events']==0 and z['full_OPEN_not_run'] is True
  assert r['analysis_only'] and not r['submit_allowed']
  if name=='ORIGINAL_6':assert r==x['original_result'] and digest(r)==x['certificate']['projection_hash']
  qcount=sum(q>0 for q in r['Q'].values())
  for sid,q in r['Q'].items():
   d=ds[sid];ru=d['quantity'];assert 0<=q<=d['max_q']
   assert q==0 or (q>=ru['buy_minimum'] and (q-ru['buy_minimum'])%ru['buy_step']==0)
  cap=sum((D(a['capital']) for a in s['rows']),D(0));risk=sum((D(a['risk']) for a in s['rows']),D(0));by_sid={};Dgross=D(0)
  for z in r['donors']['rows']:
   lot=lots[z['layer']];q=z['q'];assert q<=lot['sellable_qty'] and lot['donor_eligible'] and lot['B_donor_eligible'] and lot['locked_capital']=='0'
   close(z['capital'],D(q)*D(lot['mark']));close(z['risk_release'],D(q)*max(D(0),D(lot['mark'])-D(lot['floor'])))
   cap-=D(z['capital']);risk-=D(z['risk_release']);Dgross+=D(z['capital']);by_sid[lot['sid']]=by_sid.get(lot['sid'],0)+q
  assert by_sid==r['D']
  for sid,q in r['Q'].items():
   d=ds[sid];cap+=D(q)*D(d['mark']);risk+=D(q)*max(D(0),D(d['mark'])-D(d['floor']))
  term=r['validation']['terminal'];close(cap,term['capital']);close(risk,term['risk'])
  negatives={}
  for c in r['validation']['checks']:
   # All frozen checks store positive headroom as limit minus value.
   close(D(c['limit'])-D(c['value']),c['residual']);checks_count+=1
   if D(c['residual'])<0:negatives[c['constraint']]=negatives.get(c['constraint'],0)+1
  assert not negatives if name=='ORIGINAL_6' else set(negatives)<= {'account_risk6'}
  nv=D(term['nav']);case=next(c for c in sm['cases'] if c['day']==day)['modes'][name]
  for key,val in [('capital_pct',cap/nv*100),('nominal_risk_pct',risk/nv*100),('conditional_cash_pct',D(term['available'])/nv*100)]:assert abs(float(val)-case[key])<1e-10
  close(Dgross,case['D_mark_gross']);assert qcount==case['Q_positive']
  modes[name]={'Q_positive':qcount,'D_positive':len(by_sid),'capital_pct':float(cap/nv*100),'risk_pct':float(risk/nv*100),'conditional_cash_pct':float(D(term['available'])/nv*100),'D_mark_gross':str(Dgross),'ignored_negative_risk6_checks':negatives.get('account_risk6',0)}
 changed=[sid for sid in ds if rr['ORIGINAL_6']['Q'][sid]!=rr['NO_AR6']['Q'][sid]];all_changes.extend((day,sid) for sid in changed)
 cases.append({'day':day,'full_candidates':len(ds),'changed_Q':len(changed),'modes':modes,'financial_events':0})
assert set(all_changes)=={(c['day'],c['sid']) for c in sm['changes']} and len(all_changes)==13
record={'passed':True,'scope':'independent stdlib JSON arithmetic, full original payload identity, input/source SHA, causal timestamps; not solver rerun or native OPEN audit','cases':cases,'source_files_sha_checked':len(hashes),'residual_checks_independently_recomputed':checks_count,'Q_changes':13,'financial_events':0,'native_OPEN_pass_claim':False,'continuous_trial_admission':'SUPPORTED: ONE C10 NO_AR6 July1-Aug29 plus January4-28 adverse control, OFF native short-prefix identity before ON; no promotion','limitations':['Five states all in July-August2025 and prior C10 paths, no dynamic counterfactual','Summary nominal risk is mark-to-actual-line, not a guaranteed maximum loss or DD','Only account6 is relaxed; all other constraints and original economic behavior must remain','Jan2022/C2024Sep/2026H1 are not validated by static five states']}
(OUT/'STATIC_INDEPENDENT_AUDIT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='cases'},ensure_ascii=False));print('cases',len(cases))
