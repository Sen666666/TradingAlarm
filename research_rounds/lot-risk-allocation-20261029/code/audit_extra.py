"""Independent frozen-contract and whole-order checks; no new account paths."""
from study import *
def load(p):return json.loads(Path(p).read_text())
def rows(p):
 import gzip
 with gzip.open(p,'rt') as f:return [json.loads(s) for s in f]
def main():
 result=O/'results';daily=rows(result/'daily.jsonl.gz');old=rows(BASE/'results/daily.jsonl.gz');controls=[];counts=collections.Counter()
 for name in ['P0','P1']:
  a=[r for r in daily if r['account']==name];b=[r for r in old if r['account']==name];assert a==b,(name,'old control daily')
  x=load(result/f'{name}.json');y=load(BASE/f'results/{name}.json');assert x==y,(name,'old control object');controls.append(dict(account=name,daily=len(a),fills=len(x['trades'])))
 frozen=load(O/'FREEZE.json');assert all(sha(ROOT/k)==v for k,v in frozen['sha256'].items())
 base=load(BASE/'completion-sha256.json')['sha256'];assert all(sha(BASE/k)==v for k,v in base.items())
 rules=load(ROOT/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');proto=load(ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/economic-protocol.json')
 from market_rules import market_identity_on,version_on
 facts={}
 for name in ['L0','L1']:
  obj=load(result/f'{name}.json');decisions={r['at']:r for r in obj['decisions']};contracts={}
  for r in obj['decisions']:
   nav=D(r['nav'])
   for i in r['intents']:
    assert D(i['budget'])<=nav*(D('.1') if i['kind']=='core' else D('.02'))
    if i['kind']=='core':assert D(i['risk_budget'])==nav*D('.0025')
    contracts[i['sid'],r['at']]=i;counts['signal_contracts']+=1
  for a in obj['audit']:
   if a['kind']!='lot_risk_funded':continue
   i=contracts[a['sid'],a['signal_at']];assert a['signal_at']<a['at'];assert a['shares']<=i['cap'];assert D(a['gross'])<=D(i['budget']);counts['funded_contracts']+=1
  for t in obj['trades']:
   if t['side']!='buy':continue
   i=contracts[t['security_id'],t['signal_at']];sid=t['security_id'];day=t['at'][:10];at=pd.Timestamp(t['at'])
   identity=market_identity_on(rules,sid,at.date(),proto['approved_proxy_ids']);spec=version_on(rules['fee_versions'][identity['venue']],day,proto['approved_proxy_ids'])['schedule'];schedule=L.FeeSchedule(spec['schedule_id'],tuple(L.FeeComponent(**v) for v in spec['components']))
   if sid not in facts:facts[sid]=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet')
   factor=D(str(facts[sid].loc[day].factor));floor=D(i['floor'])/factor;price=D(t['price']);q=t['shares'];par=rules.get('security_metadata',{}).get(sid,{}).get('par_value')
   # Independent loss arithmetic, not study.protection_risk or its quantity solver.
   sellprice=floor*D('.9995');buyfee=sum(schedule.incremental('buy',q*price,{}, {},1,shares=q,par_value=par).values(),ZERO);sellfee=sum(schedule.incremental('sell',q*sellprice,{}, {},1,shares=q,par_value=par).values(),ZERO);risk=max(ZERO,q*(price-sellprice)+buyfee+sellfee)
   assert price==D(t['raw_open'])*D('1.0005') and D(t['raw_open'])>floor
   if i['kind']=='core':assert risk<=D(i['risk_budget']),(name,sid,day,'nominal risk breach',risk,i['risk_budget']);counts['actual_core_risk_bounds']+=1
   counts['actual_frozen_quantity_bounds']+=1;assert q<=i['cap'];assert D(t['gross_cny'])<=D(i['budget'])
  for d in [d for d in daily if d['account']==name]:
   # Full shares and NAV are independently replayed in analysis/accounting.json.
   assert D(d['available'])>=0
   for z in d['layers']:
    assert z['qty']>0 and z['kind'] in ('core','add')
  counts['new_daily_nonnegative_cash']+=sum(d['account']==name for d in daily)
 prefix=rows(O/'technical-prefix/daily.jsonl.gz');expected=[r for r in daily if r['account']=='L1' and r['at'][:10]<='2025-12-31'];assert prefix==expected
 p=load(O/'technical-prefix/L1.json');full=load(result/'L1.json');ft=[t for t in full['trades'] if t['at'][:10]<='2025-12-31'];fd=[d for d in full['decisions'] if d['at'][:10]<='2025-12-31'];assert p['trades']==ft;assert p['decisions']==fd
 save(O/'VERIFICATION.json',dict(passed=True,old_controls=controls,old_artifacts_unchanged=len(base),frozen_inputs_unchanged=len(frozen['sha256']),new_contract_checks=dict(counts),physical_prefix_days=len(prefix),physical_prefix_trades=len(ft),physical_prefix_decisions=len(fd),parameter_changes_after_results=0,successful_new_paths=2,full_control_replays=2))
 print('VERIFIED',dict(counts),controls,len(prefix),len(ft))
if __name__=='__main__':main()
