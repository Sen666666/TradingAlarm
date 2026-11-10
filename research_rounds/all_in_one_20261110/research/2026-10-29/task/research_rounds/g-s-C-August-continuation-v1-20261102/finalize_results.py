"""Merge per-cell saved-object verification; no account/event execution."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib
P=Path(__file__).resolve().parent;O=P/'analysis';CELLS=['C10','C20','C10_R0','C20_R0']
def rd(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 results=[];checks=[];cpchecks=[];riskchecks=[];f1=[];archive=rd(P/'LOSSLESS_OUTPUT_ARCHIVE.json')['entries'];auth=rd(P/'AUTHORIZATION.json');identity=rd(P/'INPUT_IDENTITY.json')
 for c in CELLS:
  r=rd(O/(c+'-RESULT.json'));assert r['cursor']=='2025-08-29 15:10:00+08:00';v=rd(O/(c+'-VERIFICATION.json'));assert v['passed'];cc=[z for z in v['checks'] if z['cell']==c];assert len(cc)==63 and all(all(D(t)==0 for t in z['differences'].values()) for z in cc);checks+=cc;results.append(r)
  root=P/'runs'/c;q=rd(root/'PROGRESS.json');assert rd(root/'COMPLETED.json')['cursor']==q['cursor'];cp=Path(q['checkpoint']);assert sha(cp)==q['sha256'];final=rd(cp.with_suffix('.json'));f1.append(hashlib.sha256(json.dumps(dict(f1=final['f1'],seq=final['f1seq']),sort_keys=True).encode()).hexdigest())
  for f in root.glob('2025-08-*.provenance.json'):
   raw=root/(f.name[:-len('.provenance.json')]+'.pkl');s=rd(f);b=s['binding'];assert b['cell']==c and b['branch']=='full' and b['end']=='2025-08-29' and b['authorization_sha256']==sha(P/'AUTHORIZATION.json');assert b['source'][str(P/'august_runtime.py')]==sha(P/'august_runtime.py')
   key=str(raw.relative_to(P))
   if raw.exists():assert sha(raw)==s['checkpoint_sha256'];storage='raw'
   else:
    z=archive[key];assert z['original_sha256']==s['checkpoint_sha256'] and z['exact_roundtrip_verified'] and sha(P/z['archive'])==z['gzip_sha256'];storage='lossless gzip, original byte SHA retained'
   cpchecks.append(dict(cell=c,path=str(raw),original_sha256=s['checkpoint_sha256'],storage=storage,engine=s['engine_identity']))
  if c.endswith('_R0'):
   risk=final['approved_risk'];assert set(risk['fills'])==set(final['authority']['events']);spent=defaultdict(F)
   for eid,z in risk['fills'].items():
    value=F(z['shares'])*max(F(0),F(z['price'])-F(z['floor']));assert value==F(z['consumed']);spent[z['key']]+=value
   for key,z in risk['approvals'].items():assert F(z['spent'])==spent[key] and F(0)<=F(z['spent'])<=F(z['approved']['R0'])
   riskchecks.append(dict(cell=c,positive_stock_authorizations=len(risk['approvals']),certificate_count=len({z['approved']['cid'] for z in risk['approvals'].values()}),actual_C_fill_receipts=len(risk['fills']),all_permanent_spent_risk_within_R0=True,no_claim_realized_loss_bounded=True))
  # C10 was verified before this auxiliary arithmetic view was added. Produce
  # it directly from immutable endpoints without rechecking/replaying history.
  cap=defaultdict(lambda:dict(start_inventory=D(0),end_inventory=D(0),actual_buy_gross=D(0),actual_sell_gross=D(0)))
  names=rd(P/'full-August/metadata.json');initial=rd(Path(identity['accounts'][c]['checkpoint']).with_suffix('.json'))
  for x,field in [(initial,'start_inventory'),(final,'end_inventory')]:
   for z in x['account']['layers']:
    if z['qty']:cap[names[z['sid']]['sector']][field]+=D(z['qty'])*D(x['account']['market_marks'][z['sid']])
  for t in final['account']['trades']:
   if t['at'].startswith('2025-08'):cap[names[t['security_id']]['sector']]['actual_buy_gross' if t['side']=='buy' else 'actual_sell_gross']+=D(t['gross_cny'])
  for z in cap.values():z['net_actual_gross_funding']=z['actual_buy_gross']-z['actual_sell_gross'];z['mark_and_execution_price_residual']=z['end_inventory']-z['start_inventory']-z['net_actual_gross_funding']
  save(O/(c+'-ACTIVE_CAPITAL_VS_REVALUATION.json'),dict(definition='Inventory delta = actual gross funding + mark/execution-price residual; not pure passive return.',industries=cap))
  st=rd(O/(c+'-STOCKS.json'));top=st[0];pos=sum((max(D(0),D(z['August_contribution'])) for z in st),D(0));save(O/(c+'-LARGEST_CONTRIBUTOR_SENSITIVITY.json'),dict(largest=top,share_of_gross_positive=D(top['August_contribution'])/pos if pos else None,arithmetic_month_wealth_change_without_largest=D(r['terminal_NAV'])-D(r['initial_Jul31_NAV'])-D(top['August_contribution']),not_a_replayed_policy=True))
 assert len(set(f1))==1 and len(cpchecks)==252
 for p,h in auth['sources'].items():assert sha(p)==h
 for c,z in identity['accounts'].items():assert sha(z['checkpoint'])==z['checkpoint_sha256']
 save(O/'RESULTS.json',results);save(O/'VERIFICATION.json',dict(passed=True,all_four_complete=True,cells=CELLS,event_states=len(checks),checks=checks,original_July_unchanged=True,financial_events_invoked_by_analysis=0))
 save(O/'CHECKPOINT_IDENTITIES.json',dict(passed=True,states=cpchecks,financial_events=0));save(O/'R0_RISK_CONSERVATION.json',dict(passed=True,records=riskchecks,financial_events=0));save(O/'COMMON_MARKET_STATE.json',dict(passed=True,f1_same_at_Aug29=True,hashes=f1))
 print('ALL_FOUR_FINAL_VERIFIED',len(checks),len(cpchecks),flush=True)
if __name__=='__main__':main()
