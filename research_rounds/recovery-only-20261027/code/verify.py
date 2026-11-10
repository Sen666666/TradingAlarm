from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
def load(p):
 d=defaultdict(list)
 with gzip.open(p,'rt') as f:
  for x in map(json.loads,f):d[x['account']].append(x)
 return d
if __name__=='__main__':
 receipts=[];events=[];old=load(ROOT/'research_rounds/tech-drawdown-regime-20261027/CONTROL/accounts-v2/daily.jsonl.gz');market=pd.read_csv(O/'recovery.csv',index_col=0,parse_dates=True)
 for root in sorted(O.iterdir()):
  if not (root/'accounts-v2').exists():continue
  assert json.loads((root/'analysis/accounting.json').read_text())['passed'];a=load(root/'accounts-v2/daily.jsonl.gz');pre=load(root/'technical/prefix/daily.jsonl.gz')
  for aid,ds in a.items():
   obj=json.loads((root/'accounts-v2'/f'{aid}.json').read_text());prefix_obj=json.loads((root/'technical/prefix'/f'{aid}.json').read_text());target=[x for x in ds if x['at'][:10]<='2026-08-31'];assert pre[aid]==target,(root.name,aid,'prefix daily');assert prefix_obj['fills']==[x for x in obj['fills'] if x['at'][:10]<='2026-08-31'];receipts.append(dict(kind='prefix',version=root.name,account=aid,days=len(target)))
   if root.name=='CONTROL':
    assert ds==old[aid];reference=json.loads((ROOT/'research_rounds/tech-drawdown-regime-20261027/CONTROL/accounts-v2'/f'{aid}.json').read_text());assert obj['fills']==reference['fills'];receipts.append(dict(kind='control',account=aid,days=len(ds)));continue
   if root.name=='ACT20_BREAK':
    refroot=ROOT/'research_rounds/actual-risk-recovery-20261027/ACT20_BREAK/accounts-v2';assert ds==load(refroot/'daily.jsonl.gz')[aid];assert obj['fills']==json.loads((refroot/f'{aid}.json').read_text())['fills'];receipts.append(dict(kind='baseline_identity',account=aid))
   rows=[x for x in obj['audit_log'] if x['kind']=='risk_checkpoint'];assert len(rows)==len(ds);on=True;peak=D(1000000);saw=False;prev=False;episode=0;states={}
   for r,day in zip(rows,ds):
    assert r['at']==day['at'];n=D(day['nav']);assert D(r['nav'])==n
    m=market.loc[pd.Timestamp(r['at'][:10])];fast=bool(m.fast_on);br=bool(m[{'ACT20_BREAK':'breakout','REC21':'break21','REC21_P5':'break21_p5','RECEMA_P5':'ema21_p5'}[root.name]]);assert r['fast']==fast and r['breakout']==br
    if on:peak=max(peak,n)
    dd=1-n/peak;assert abs(D(r['episode_drawdown'])-dd)<D('1e-25')
    evt=None
    if on and dd>=(D('.1') if root.name=='ACT10_BREAK' else D('.2')):on=False;saw=not fast;evt='pause'
    elif not on:
     saw=saw or not fast;can=(saw and fast and not prev) if root.name=='ACT20_FAST' else br
     if r['flat'] and can:on=True;peak=n;episode+=1;saw=False;evt='resume'
    prev=fast;assert r['event']==evt and r['on']==on and D(r['peak'])==peak and r['episode']==episode,(root.name,aid,r['at'])
    if r['flat']:assert not day['positions']
    if not on:
     assert not day['pending_buys'];assert set(day['positions'])<=set(day['pending_sells'])
    states[r['at']]=on
    if evt:events.append(dict(version=root.name,account=aid,date=r['at'][:10],event=evt,nav=float(n),episode=episode,episode_drawdown=float(dd),fast=fast,breakout=br))
   for r in obj['audit_log']:
    if r['kind']=='entry_contract':assert states[r['at']],(root.name,aid,'buy while paused',r['at'])
   receipts.append(dict(kind='independent_risk_replay',version=root.name,account=aid,days=len(rows)))
 for path,h in json.loads((O/'freeze.json').read_text()).items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
 (O/'verification.json').write_text(json.dumps({'passed':True,'receipts':receipts,'frozen_unchanged':True},indent=2));pd.DataFrame(events).to_csv(O/'risk-events.csv',index=False);print('verified',len(receipts))
