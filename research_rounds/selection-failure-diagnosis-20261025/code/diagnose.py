from pathlib import Path
import json,hashlib,datetime
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parents[1];SRC=HERE.parent/'rs-h1-execution-20261025';OLD=HERE.parent/'a-share-selection-e0-20261024'
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 out=HERE/'results';out.mkdir(exist_ok=False)
 write(HERE/'freeze.json',dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),no_new_accounts=True,code=sha(__file__),protocol=sha(HERE/'PROTOCOL.md'),sources={str(p):sha(p) for p in [SRC/'complete.json',SRC/'analysis-v2/campaigns.json',SRC/'analysis-v2/curves.csv',SRC/'entry-profiles/profiles.json',ROOT/'research_rounds/strategy-switching-20261024/engine.py',ROOT/'research_rounds/strategy-switching-20261024/results/v0/summary.csv']}))
 pm={x['series_id']:x for x in read(SRC/'prepared-v2/manifest.json')['series']};cache={};curves=pd.read_csv(SRC/'analysis-v2/curves.csv');nav={(a,d):float(n) for a,d,n in curves[['account','date','nav']].itertuples(index=False,name=None)}
 profiles={(x['account'],x['symbol'],x['entry_at']):x for x in read(SRC/'entry-profiles/profiles.json')};rows=[]
 def data(sid):
  if sid not in cache:
   p=pm[sid];st=pd.read_parquet(SRC/'prepared-v2'/p['files']['states']['path'],columns=['floor']);sg=pd.read_parquet(SRC/'prepared-v2'/p['files']['signal']['path'],columns=['close','adjustment_factor']);cache[sid]=(st,sg)
  return cache[sid]
 for aid in ['T0_base','T1_base','S0_base','S1_base']:
  obj=read(SRC/'accounts-v2'/(aid+'.json'));buys={(r['receipt']['security_id'],r['receipt']['at']):r for r in obj['audit_log'] if r['kind']=='fill' and r['receipt']['side']=='buy'}
  for c in read(SRC/'analysis-v2/campaigns.json'):
   if c['account']!=aid:continue
   p=profiles[aid,c['symbol'],c['entry_at']];fill=buys[c['symbol'],c['entry_at']];st,sg=data(c['symbol']);decision=pd.Timestamp(p['decision_date']);entry=pd.Timestamp(c['entry_at'][:10]);end=pd.Timestamp(c['exit_at'][:10]) if c['closed'] else pd.Timestamp('2026-10-23')
   floor=float(st.loc[:decision].floor.iloc[-1]);factor=float(sg.loc[entry,'adjustment_factor']);floor_raw=floor/factor;px=float(fill['price']);raw=float(fill['raw_open']);q=int(fill['receipt']['shares']);start_px=px*factor
   path=sg.loc[(sg.index>=entry)&(sg.index<end),'close'];mfe=max(0.,float(path.max()/start_px-1)) if len(path) else 0.
   band='<=0' if mfe<=0 else '0—5%' if mfe<.05 else '5—15%' if mfe<.15 else '15—30%' if mfe<.30 else '>=30%'
   capital=nav[aid,p['decision_date']];gross=float(fill['receipt']['gross_cny']);risk=max(0.,(px-floor_raw)*q)
   rows.append(dict(account=aid,symbol=c['symbol'],name=c['name'],industry=c['industry'],entry_at=c['entry_at'],exit_at=c['exit_at'],closed=c['closed'],h=p['h'],rs_h1=p['rs_h1'],e0_age=p['e0_age_observations'],decision_support_distance=p['close_to_support_fraction'],net_pnl=float(c['net_pnl']),net_return=c['net_return'],buy_gross=float(c['buy_gross']),raw_open=raw,actual_entry_price=px,known_support_raw_at_fill=floor_raw,raw_open_below_known_support=raw<=floor_raw,actual_entry_distance_to_support=(px-floor_raw)/px,initial_gross_weight=gross/capital,initial_price_risk_to_support_nav=risk/capital,close_price_mfe=mfe,mfe_band=band))
 write(out/'funded-paths.json',rows);f=pd.DataFrame(rows);f.to_csv(out/'funded-paths.csv',index=False,encoding='utf-8-sig');summary=[];groups=[]
 for aid,part in f.groupby('account'):
  cl=part.loc[part.closed];loss=cl.loc[cl.net_pnl<0];gap=part.loc[part.raw_open_below_known_support];normal=part.loc[~part.raw_open_below_known_support];wins=cl.loc[cl.net_pnl>0]
  summary.append(dict(account=aid,campaigns=len(part),closed=len(cl),winning=len(wins),losing=len(loss),gross_winning_pnl=float(wins.net_pnl.sum()),gross_losing_pnl=float(loss.net_pnl.sum()),profit_factor=float(wins.net_pnl.sum()/-loss.net_pnl.sum()),avg_win_return=float(wins.net_return.mean()),avg_loss_return=float(loss.net_return.mean()),open_below_known_support_count=len(gap),open_below_support_actual_pnl=float(gap.net_pnl.sum()),open_below_support_losing_count=int((gap.net_pnl<0).sum()),median_initial_gross_weight=float(part.initial_gross_weight.median()),median_initial_price_risk_to_support_nav=float(normal.initial_price_risk_to_support_nav.median()),p90_initial_price_risk_to_support_nav=float(normal.initial_price_risk_to_support_nav.quantile(.9)),losing_mfe_under5_count=int((loss.close_price_mfe<.05).sum()),losing_mfe_under5_gross_loss=float(-loss.loc[loss.close_price_mfe<.05,'net_pnl'].sum()),losing_mfe_30plus_count=int((loss.close_price_mfe>=.30).sum()),losing_mfe_30plus_gross_loss=float(-loss.loc[loss.close_price_mfe>=.30,'net_pnl'].sum())))
  for band,x in loss.groupby('mfe_band'):groups.append(dict(account=aid,mfe_band=band,losing_campaigns=len(x),gross_loss=float(-x.net_pnl.sum())))
 write(out/'summary.json',summary);write(out/'losing-close-mfe-groups.json',groups)
 previous=pd.read_csv(ROOT/'research_rounds/strategy-switching-20261024/results/v0/summary.csv');previous=previous.loc[previous.policy.eq('E0')&previous.scenario.eq('base')];previous.to_csv(out/'previous-e0-base.csv',index=False,encoding='utf-8-sig')
 write(out/'verification.json',dict(passed=True,rows=len(rows),no_new_accounts=True,all_campaigns_match_original_independent_pnl=all(abs(sum(x['net_pnl'] for x in rows if x['account']==a['account'])-(a['final_nav']-1e6))<1e-7 for a in read(SRC/'analysis-v2/summary.json') if a['account'].endswith('_base')),code_sha256=sha(__file__)))
 print(summary,flush=True)
if __name__=='__main__':main()
