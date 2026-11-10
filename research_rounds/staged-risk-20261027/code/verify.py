from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parents[1];R=O.parents[1]
def load(p):
 d=defaultdict(list)
 with gzip.open(p,'rt') as f:
  for x in map(json.loads,f):d[x['account']].append(x)
 return d
if __name__=='__main__':
 receipts=[];events=[];market=pd.read_csv(O/'recovery.csv',index_col=0,parse_dates=True)
 for v in ['CONTROL','HALF','ACT20_BREAK','STEP']:
  p=O/v;assert json.loads((p/'analysis/accounting.json').read_text())['passed'];ds=load(p/'accounts-v2/daily.jsonl.gz');pr=load(p/'technical/prefix/daily.jsonl.gz')
  for aid,days in ds.items():
   obj=json.loads((p/'accounts-v2'/f'{aid}.json').read_text());po=json.loads((p/'technical/prefix'/f'{aid}.json').read_text())
   assert pr[aid]==[x for x in days if x['at'][:10]<='2026-08-31'];assert po['fills']==[x for x in obj['fills'] if x['at'][:10]<='2026-08-31'];receipts.append(dict(kind='prefix',version=v,account=aid,days=len(pr[aid])))
   if v!='STEP':
    refroot=(R/'research_rounds/tech-finite-compound-20261026') if v=='HALF' else (R/'research_rounds/actual-risk-recovery-20261027'/v)
    refaid=aid.replace('I__','H50__') if v=='HALF' else aid;ref=load(refroot/'accounts-v2/daily.jsonl.gz')[refaid]
    for x,y in zip(days,ref):assert {k:w for k,w in x.items() if k!='account'}=={k:w for k,w in y.items() if k!='account'},(v,aid,x['at'])
    assert len(days)==len(ref);assert obj['fills']==json.loads((refroot/'accounts-v2'/f'{refaid}.json').read_text())['fills'];receipts.append(dict(kind='control',version=v,account=aid));continue
   rows=[x for x in obj['audit_log'] if x['kind']=='risk_checkpoint'];assert len(rows)==len(days);phase='full';peak=D(1000000);episode=0;states={};reductions={}
   for a,d in zip(rows,days):
    assert a['at']==d['at'];nav=D(d['nav']);assert nav==D(a['nav']);m=market.loc[pd.Timestamp(a['at'][:10])];fast=bool(m.fast_on);br=bool(m.breakout)
    if phase!='paused':peak=max(peak,nav)
    dd=1-nav/peak;assert abs(dd-D(a['episode_drawdown']))<D('1e-25');event=None
    if phase!='paused' and dd>=D('.2'):phase='paused';event='pause'
    elif phase=='full' and not fast and dd>=D('.1'):phase='defensive';event='reduce'
    elif phase in ['defensive','paused'] and br and a['no_exits'] and (phase!='paused' or a['flat']):phase='full';peak=nav;episode+=1;event='resume'
    assert (a['phase'],a['event'],D(a['peak']),a['episode'])==(phase,event,peak,episode)
    if phase!='full':assert not d['pending_buys']
    if phase=='paused':assert set(d['positions'])<=set(d['pending_sells'])
    states[a['at']]=(phase,event,d)
    if event:events.append(dict(version=v,account=aid,date=a['at'][:10],event=event,phase=phase,nav=float(nav)))
   upgrades=set()
   for a in obj['audit_log']:
    if a['kind']=='entry_contract':assert states[a['at']][0]=='full'
    if a['kind']=='risk_reduction_intent':
     assert states[a['at']][1]=='reduce';assert int(states[a['at']][2]['positions'][a['sid']])==a['held_shares'];assert 0<a['shares']<=a['held_shares']//2
     reductions[a['event_id']]=a['shares']
    if a['kind']=='risk_reduction_upgrade':upgrades.add(a['event_id'])
   sold=defaultdict(int)
   for a in obj['audit_log']:
    if a['kind']=='fill' and a.get('order_id') in reductions:sold[a['order_id']]+=a['receipt']['shares']
   for key,value in sold.items():assert key in upgrades or value<=reductions[key]
   receipts.append(dict(kind='independent_staged_risk',version=v,account=aid,days=len(days),reduction_orders=len(reductions)))
 for p,h in json.loads((O/'freeze.json').read_text()).items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
 (O/'verification.json').write_text(json.dumps({'passed':True,'receipts':receipts},indent=2));pd.DataFrame(events).to_csv(O/'risk-events.csv',index=False);print('verified',len(receipts))
