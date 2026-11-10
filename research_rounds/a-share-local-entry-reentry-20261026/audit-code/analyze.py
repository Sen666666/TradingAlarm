from pathlib import Path
from decimal import Decimal
import sys,json,gzip,collections,math,hashlib,importlib.util
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';SEC=ROOT/'research_rounds/sector-ix-i-20261026'
sys.path[:0]=[str(OLD/'code'),str(IX/'code'),str(SEC/'code')]
from analyze_ix import IndependentPrices
spec=importlib.util.spec_from_file_location('ler_independent_cash',OLD/'code/analyze_accounts.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
D=Decimal;ZERO=D(0)
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 short='--short' in sys.argv;source=HERE/('technical/short-v2' if short else 'accounts');out=HERE/('technical/short-audit-v1' if short else 'analysis-v1');out.mkdir(exist_ok=False)
 end='2021-02-26' if short else '2026-10-16';daily=collections.defaultdict(list)
 with gzip.open(source/'daily.jsonl.gz','rt') as f:
  for l in f:r=json.loads(l);daily[r['account']].append(r)
 scope=read(SEC/'scope.json');meta=read(OLD/'inputs-v2/metadata.json');meta={s:dict(x) for s,x in meta.items()}
 for s in scope['groups']['DRUG']:meta[s]['sector_id']='THEME931152';meta[s]['industry']='创新药'
 prices=IndependentPrices();calendar=[audit.t(x) for x in read(OLD/'inputs-v2/market-rules.json')['calendars']['A']];manifest={x['series_id']:x for x in read(OLD/'prepared-v2/manifest.json')['series']};cache={};factors={}
 def data(sid):
  if sid not in cache:
   f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');f['e0_seq']=f.groupby('segment_id',sort=False).e0_entered.cumsum();cache[sid]=f;factors[sid]=pd.read_parquet(OLD/'prepared-v2'/manifest[sid]['files']['signal']['path'],columns=['adjustment_factor']).adjustment_factor
  return cache[sid]
 results=[];campaigns=[];curves=[];years=[];checks=[];bindings=guard=exit_checks=handoffs=0
 for aid,ds in daily.items():
  group,policy,stress=aid.split('__')[0].split('_');obj=read(source/(aid+'.json'));cc,rc=audit.audit_account('S1_'+stress,obj,ds,prices,meta,calendar);rc['account']=aid;checks.append(rc)
  reserves={x['order_id']:x for x in obj['audit_log'] if x['kind']=='reserve'};bound={(x['sid'],x['first_fill_at']):x for x in obj['audit_log'] if x['kind']=='local_bound'};firstbuys={}
  for x in obj['audit_log']:
   kind=x['kind']
   if kind=='fill' and x['receipt']['side']=='buy':firstbuys.setdefault((x['receipt']['security_id'],x['receipt']['at']),x)
   if kind=='local_bound':
    sid=x['sid'];day=pd.Timestamp(x['receipt_day']);f=data(sid);r=pd.read_parquet(HERE/'signals-v1'/f'{sid}.parquet');assert bool(r.loc[day,'receipt']);assert abs(x['local_floor']-r.loc[day,'local_floor'])<1e-12
    assert day<pd.Timestamp(x['first_fill_at']).tz_localize(None).normalize();assert x['order_id'] in reserves;bindings+=1
   elif kind=='local_open_cancel':
    assert float(x['raw_open'])*x['factor']<=x['known_floor_signal'];assert pd.Timestamp(x['decision_at'])<pd.Timestamp(x['at']);guard+=1
   elif kind=='local_exit_signal':
    sid=x['sid'];day=pd.Timestamp(x['at']).tz_localize(None).normalize();f=data(sid);r=f.loc[day]
    if x['reason']=='local_failure':assert bool(r.e0_target) and float(r.close)<=x['protection']
    elif x['reason']=='E0_structure':assert not bool(r.e0_target)
    elif x['reason']!='source_segment_reset':raise AssertionError(x)
    exit_checks+=1
   elif kind=='local_E0_handoff':assert x['E0_floor']>=x['local_floor'];handoffs+=1
  frame=pd.DataFrame(ds);nav=frame.nav.astype(float).to_numpy();dd=nav/np.maximum.accumulate(np.r_[1e6,nav])[1:]-1
  for c in cc:
   sid=c['symbol'];b=firstbuys[sid,c['entry_at']];res=reserves[b['order_id']];day=pd.Timestamp(res['decision_at']).tz_localize(None).normalize();ed=pd.Timestamp(c['entry_at']).tz_localize(None).normalize();f=data(sid);r=f.loc[day];factor=float(factors[sid].loc[ed]);floor=float(r.e0_floor);binding=None
   if policy!='I':
    binding=bound[sid,c['entry_at']]
    if policy=='LER':floor=max(floor,binding['local_floor'])
    assert float(b['raw_open'])*factor>binding['known_floor_at_decision']
   p=float(b['price']);q=int(b['receipt']['shares']);risk=(p-floor/factor)*q
   decision_nav=float(frame.loc[frame['at'].str[:10].eq(str(day.date())),'nav'].iloc[0]);px=p*factor;xd=pd.Timestamp(c['exit_at']).tz_localize(None).normalize() if c['closed'] else pd.Timestamp(end)+pd.Timedelta(days=1);path=f.loc[(f.index>=ed)&(f.index<xd)&(f.index<=end),'close']
   actualR=float(c['net_pnl'])/risk if risk>0 and c['buy_fills']==1 else None
   c.update(account=aid,group=group,policy=policy,scenario=stress,source_industry=scope['meta'][sid]['industry'],decision_day=str(day.date()),source_segment=str(r.segment_id),e0_seq=int(r.e0_seq),entry_old_IX_event=bool(r.IX),initial_protection_signal=floor,first_fill_price=p,initial_price_risk_cny=risk,initial_price_risk_nav=risk/decision_nav if risk>0 else None,net_R=actualR,close_mfe=max(0.,float(path.max()/px-1)) if len(path) else None,local_receipt_day=binding['receipt_day'] if binding else None)
   campaigns.append(c)
  closed=[c for c in cc if c['closed']];tail=[c for c in closed if c['tail_closed']];ordinary=[c for c in closed if not c['tail_closed']];wins=[c for c in closed if c['net_pnl']>0];losses=[c for c in closed if c['net_pnl']<0]
  tailp=sum((c['net_pnl'] for c in tail),ZERO);ordinaryp=sum((c['net_pnl'] for c in ordinary),ZERO);op=sum((c['net_pnl'] for c in cc if not c['closed']),ZERO);winp=sum((c['net_pnl'] for c in wins),ZERO);lossp=-sum((c['net_pnl'] for c in losses),ZERO)
  assert abs(tailp+ordinaryp+op-(D(ds[-1]['nav'])-D(1000000)))<D('1e-8')
  wr=np.array([c['net_R'] for c in wins if c['net_R'] is not None]);lr=np.array([-c['net_R'] for c in losses if c['net_R'] is not None])
  results.append(dict(account=aid,group=group,policy=policy,scenario=stress,net_return=nav[-1]/1e6-1,max_drawdown=float(-dd.min()),final_nav=nav[-1],mean_exposure=float((frame.inventory.astype(float)/frame.nav.astype(float)).mean()),fees_cny=float(frame.fees_cny.iloc[-1]),closed=len(closed),open=len(cc)-len(closed),win_rate=len(wins)/len(closed) if closed else None,profit_factor=float(winp/lossp) if lossp else None,average_win_return=np.mean([c['net_return'] for c in wins]) if wins else None,average_loss_return=np.mean([c['net_return'] for c in losses]) if losses else None,tail_count=len(tail),tail_pnl=float(tailp),ordinary_pnl=float(ordinaryp),open_pnl=float(op),gross_loss=float(lossp),ordinary_loss_to_tail=float(-ordinaryp/tailp) if tailp>0 and ordinaryp<0 else 0. if ordinaryp>=0 else None,mean_win_R=wr.mean() if len(wr) else None,mean_loss_R=lr.mean() if len(lr) else None,loss_over_1R_count=int((lr>1).sum()),new_entry_dates_not_old_IX=sum(not c['entry_old_IX_event'] for c in cc)))
  for j,d in enumerate(ds):curves.append(dict(account=aid,group=group,policy=policy,scenario=stress,date=d['at'][:10],nav=float(d['nav']),drawdown=float(dd[j]),exposure=float(d['inventory'])/float(d['nav'])))
  previous=1e6
  for y,part in frame.groupby(frame['at'].str[:4],sort=True):
   vv=part.nav.astype(float).to_numpy();years.append(dict(account=aid,group=group,policy=policy,scenario=stress,year=y,net_return=vv[-1]/previous-1,max_drawdown=float(-(vv/np.maximum.accumulate(np.r_[previous,vv])[1:]-1).min())));previous=vv[-1]
  if not short:print(dict(audited=aid,closed=len(closed),net_return=results[-1]['net_return']),flush=True)
 def serial(x):
  if isinstance(x,dict):return {k:serial(v) for k,v in x.items()}
  if isinstance(x,(tuple,list)):return [serial(v) for v in x]
  if isinstance(x,D):return str(x)
  if isinstance(x,np.generic):return serial(x.item())
  if isinstance(x,float) and not math.isfinite(x):return None
  return x
 for name,rows in [('summary',results),('campaigns',campaigns),('curves',curves),('annual',years)]:
  pd.DataFrame(serial(rows)).to_csv(out/(name+'.csv'),index=False);(out/(name+'.json')).write_text(json.dumps(serial(rows),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 clusters=[]
 cf=pd.DataFrame(serial(campaigns));cf['net_pnl']=cf.net_pnl.astype(float)
 for key,g in cf.groupby(['account','group','policy','scenario','symbol','source_segment','e0_seq'],dropna=False):
  aid,group,policy,stress,sid,seg,seq=key;f=data(sid);ended=bool(((f.segment_id.astype(str)==seg)&f.e0_seq.eq(seq)&f.e0_exited.astype(bool)&(f.index<=end)).any());cl=g[g.closed];tails=cl[cl.tail_closed];loss=cl[cl.net_pnl<0];clusters.append(dict(account=aid,group=group,policy=policy,scenario=stress,symbol=sid,name=g.name.iloc[0],source_segment=seg,e0_seq=seq,structure_ended=ended,all_positions_closed=bool(g.closed.all()),attempts=len(g),closed_attempts=len(cl),tail_count=len(tails),tail_pnl=float(tails.net_pnl.sum()),all_closed_loss=float(-loss.net_pnl.sum()),ordinary_pnl=float(cl.loc[~cl.tail_closed,'net_pnl'].sum()),open_pnl=float(g.loc[~g.closed,'net_pnl'].sum()),net_pnl=float(g.net_pnl.sum()),first_entry=g.entry_at.min(),last_exit=cl.exit_at.max() if len(cl) else None))
 pd.DataFrame(clusters).to_csv(out/'structure-clusters.csv',index=False)
 rc=dict(passed=True,technical_only=short,accounts=len(daily),daily_rows=sum(len(x) for x in daily.values()),independent_money_share_checks=checks,max_absolute_NAV_difference_cny=max(D(x['max_absolute_nav_difference_cny']) for x in checks),executed_local_bindings=bindings,known_open_guard_checks=guard,actual_exit_signal_checks=exit_checks,E0_handoff_checks=handoffs,code_sha256=sha(__file__))
 (out/'accounting.json').write_text(json.dumps(serial(rc),ensure_ascii=False,indent=2)+'\n')
 print(dict(passed=True,short=short,accounts=len(daily),days=rc['daily_rows'],bindings=bindings,guards=guard,exit_checks=exit_checks,handoffs=handoffs),flush=True)
if __name__=='__main__':main()
