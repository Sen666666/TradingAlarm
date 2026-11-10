"""Existing financial books + original signed-m export. No trading-model import."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import json,gzip,hashlib,time,ast,csv,copy
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');ROOT=RR.parent;Z=D(0)
SRC={};FM={};OLDTRACE={};OLDPRICE={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def rows(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def gz(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,set)):return [clean(v) for v in x]
 if isinstance(x,D):return str(x)
 if x is None:return None
 if not isinstance(x,(str,bool,int)):
  try:
   if pd.isna(x):return None
  except (TypeError,ValueError):pass
 return x.item() if hasattr(x,'item') else x
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
META=read(RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
IM={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
ROSTER=pd.read_csv(RR/'tech-compound-design-20261026/proposed-pool.csv')
OLD_PREP=Path(read(RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path'])
OLD_COVER=pd.read_csv(RR/'pvr-act-comparison-20261027/coverage.csv').set_index('symbol')
OLD_DIAG=RR/'tech-drawdown-regime-20261027/diagnostic-v1'
def nativefacts(sid):
 if sid not in FM:
  p=Path(SM[sid]['refs']['facts']);assert sha(p)==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p);FM[sid]=pd.read_parquet(p)
 return FM[sid]
def mark(sid,d,domain):
 if domain=='NATIVE1709':f=nativefacts(sid)
 else:
  if sid not in OLDPRICE:
   p=OLD_PREP/'signals'/f'{sid}.parquet';assert sha(p)==OLD_COVER.loc[sid,'signal_sha256'];SRC[str(p)]=sha(p);OLDPRICE[sid]=pd.read_parquet(p,columns=['raw_close'])
  f=OLDPRICE[sid]
 i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert i>=0
 return n(f.iloc[i].raw_close)
def old_m(sid,d):
 if sid not in OLDTRACE:
  p=OLD_DIAG/'traces'/f'{sid}.parquet';SRC[str(p)]=sha(p);OLDTRACE[sid]=pd.read_parquet(p)
 f=OLDTRACE[sid];t=pd.Timestamp(d)
 return float(f.loc[t,'m']) if t in f.index and bool(f.loc[t,'ready']) and pd.notna(f.loc[t,'m']) else None
def loadcase(name,p,domain,start=None):
 modern=domain=='NATIVE1709';b=gz(p/'B.json.gz') if modern else read(p/'I__S0_base.json');audit=b['audit'] if modern else b['audit_log'];daily=rows(p/'daily.jsonl.gz')
 if not modern:daily=[r for r in daily if r['account']=='I__S0_base']
 dd={day(r['at']):r for r in daily};risks=[x for x in audit if x['kind']=='risk_checkpoint'];points=defaultdict(list);spec=dict(name=name,domain=domain,path=str(p),modern=modern)
 if start:
  resume=next(x for x in risks if day(x['at'])==start and x['event']=='resume');episode=resume['episode'];phase=[x for x in risks if x['episode']==episode and x['at']>=resume['at']];pause=next((x for x in phase if x.get('event')=='pause'),None)
  if pause:phase=[x for x in phase if x['at']<=pause['at']]
  peak=max(phase,key=lambda x:n(x['nav']));give=next((x for x in phase[1:] if 1-n(x['nav'])/n(x['peak'])>=D('.1')),None)
  flat=next((r for r in daily if pause and r['at']>pause['at'] and not r['positions'] and not r.get('pending_sells')),None)
  for lab,x in [('recovery',resume),('actual_full_phase_peak',peak),('first_running_phase_giveback10',give),('ACT_pause',pause),('first_actual_flat',flat)]:
   if x:points[day(x['at'])].append(lab)
  if not modern:
   points['2024-09-23'].append('pre924_paused');points['2024-09-24'].append('924_start');points['2024-09-30'].append('first_post_recovery_open');points['2024-12-31'].append('924_window_end_still_on')
   observed=max((x for x in phase if day(x['at'])<='2024-12-31'),key=lambda x:n(x['nav']));points[day(observed['at'])].append('924_window_observed_peak_not_full_phase_peak')
  spec.update(resume=resume,peak=peak,giveback10=give,pause=pause,flat=flat,phase=episode,primary_window=['2024-09-24','2024-12-31'] if not modern else [start,day(flat['at'])],full_phase_later_context_separate=not modern)
  marketp=W/'mainline-absolute-Q4-20261031/recovery.csv' if modern else RR/'actual-risk-recovery-20261027/recovery.csv';SRC[str(marketp)]=sha(marketp);market=pd.read_csv(marketp,index_col=0)
  firstoff=next((d for d in market.index if d>start and d<=day(flat['at']) and not bool(market.loc[d,'fast_on'])),None)
  if firstoff:points[firstoff].append('first_original_fast_field_false_descriptive_only')
  spec['first_original_fast_field_false']=firstoff
 else:
  for d in ['2026-04-30','2026-05-07','2026-06-30']:points[d].append('fixed_local_semiconductor_chemical_context')
  spec['primary_window']=['2026-04-30','2026-06-30']
 spec['points']=dict(points)
 return dict(spec=spec,book=b,audit=audit,daily=daily,dd=dd,risks=risks,fills=b['trades'] if modern else b['fills'])

def export_native(dates):
 """Expose original function internals, changing ONLY its last return."""
 p=ROOT/'TradingAlarm/desk/refresh.py';SRC[str(p)]=sha(p);source=p.read_text();tree=ast.parse(source);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='compute_recovery')
 text='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])+'\n';(O/'ORIGINAL_COMPUTE_RECOVERY.py').write_text(text)
 original_return=ast.dump(node.body[-1]);assert isinstance(node.body[-1],ast.Return) and ast.unparse(node.body[-1].value)=='z'
 node=copy.deepcopy(node);node.body[-1].value=ast.Tuple(elts=[ast.Name(id=k,ctx=ast.Load()) for k in ['z','mom','sector_b']],ctx=ast.Load());module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]));env=dict(np=np,pd=pd);exec(compile(module,str(p),'exec'),env);fn=env['compute_recovery']
 expected=read(W/'native-I-cache-interface-20261031/FREEZE.json')['stocks'];assert set(expected)==set(SM) and len(expected)==1709
 signals={};entries=[];maxday=max(dates);pilot_start=time.monotonic();pilot=[]
 for j,sid in enumerate(expected):
  sp=Path(next(k for k in SM[sid]['source_sha256'] if k.endswith('/signal.parquet')));expected_sha=SM[sid]['source_sha256'][str(sp)];assert sha(sp)==expected_sha;SRC[str(sp)]=expected_sha
  f=pd.read_parquet(sp,columns=['close','amount','price_eligible','observed_bar','synthetic_event_bar','segment_id']).loc[:maxday];valid=f.price_eligible&f.observed_bar&~f.synthetic_event_bar
  if valid.any():signals[sid]=f
  entries.append(dict(sid=sid,rows=len(f),valid_rows=int(valid.sum()),absent_by_max_checkpoint=not bool(valid.any())))
  if j==9:
   estimate=(time.monotonic()-pilot_start)/10*1709;save('EXPORT_PILOT.json',dict(files=10,seconds=time.monotonic()-pilot_start,estimated_source_loading_seconds=estimate,original_m_formula_only=True))
   print('PILOT_NATIVE_LOADING_SECONDS',round(estimate,2),flush=True)
   if estimate>120:raise RuntimeError('Source loading pilot exceeds120s; no blind bulk export')
 roster=pd.DataFrame([dict(symbol=s,sector_id=META[s]['sector_id']) for s in expected if s in signals]);started=time.monotonic();z,mom,sector_b=fn(signals,roster)
 reference=pd.read_csv(W/'mainline-absolute-Q4-20261031/recovery.csv',index_col=0,parse_dates=True);SRC[str(W/'mainline-absolute-Q4-20261031/recovery.csv')]=sha(W/'mainline-absolute-Q4-20261031/recovery.csv')
 check=z.reindex(pd.DatetimeIndex(dates));ref=reference.reindex(check.index);dif={}
 for c in ['market','prior_high63','breadth']:
  np.testing.assert_allclose(check[c],ref[c],rtol=1e-12,atol=1e-12,equal_nan=True);dif[c]=float((check[c]-ref[c]).abs().max())
 assert check.breakout.equals(ref.breakout),'original BREAK mismatch'
 sector_values={sec:series.reindex(pd.DatetimeIndex(dates)) for (sec,_),series in zip(roster.groupby('sector_id'),sector_b)}
 points=[];industry=[]
 for d in dates:
  t=pd.Timestamp(d)
  for sec,g in roster.groupby('sector_id'):
   vals={sid:float(mom[sid].loc[t]) if t in mom[sid].index and pd.notna(mom[sid].loc[t]) else None for sid in g.symbol};valid=[v for v in vals.values() if v is not None]
   industry.append(dict(domain='NATIVE1709',day=d,sector=sec,identities=len(g),ready=len(valid),positive=sum(v>0 for v in valid),negative=sum(v<0 for v in valid),zero=sum(v==0 for v in valid),breadth=float(sector_values[sec].loc[t]) if pd.notna(sector_values[sec].loc[t]) else None))
  for sid in expected:
   v=float(mom[sid].loc[t]) if sid in mom and t in mom[sid].index and pd.notna(mom[sid].loc[t]) else None;points.append(dict(domain='NATIVE1709',day=d,sid=sid,m_signed_EWM21=v))
 # Three original engineering stocks, causal input physically truncated at2023Jan19.
 prefix=[];cut='2023-01-19';ids=[s for s in ['000021.SZ','000034.SZ','000050.SZ'] if s in signals];sub={s:signals[s].loc[:cut] for s in ids};_,small,_=fn(sub,roster[roster.symbol.isin(ids)])
 for s in ids:pd.testing.assert_series_equal(small[s],mom[s].loc[:cut],check_exact=True);prefix.append(s)
 save('ORIGINAL_M_EXPORT_GATE.json',dict(passed=True,original_function_source=str(p),original_function_sha256=sha(p),only_AST_change='return z -> return z,mom,sector_b',original_return_AST=original_return,
  fixed_stock_identities=1709,loaded_nonempty=len(signals),absent=len(expected)-len(signals),selected_dates=dates,csv_global_max_abs_differences=dif,comparison_tolerance='rtol=atol1e-12 for CSV roundtrip; BREAK exact',prefix_stocks=prefix,prefix_cutoff=cut,
  loading_seconds=started-pilot_start,original_formula_seconds=time.monotonic()-started,no_account_model_import=True))
 save('NATIVE_INPUT_COVERAGE.json',entries);save('STOCK_M_SELECTED.json',points);save('INDUSTRY_M_BREADTH_SELECTED.json',industry)
 return {(x['sid'],x['day']):x['m_signed_EWM21'] for x in points},{(x['sector'],x['day']):x for x in industry}

def main():
 begun=time.monotonic();specs=[('OLD924_RS',RR/'pvr-act-comparison-20261027/RS/accounts-v2','OLD407','2024-09-27'),('OLD924_PVR',RR/'pvr-act-comparison-20261027/PVR/accounts-v2','OLD407','2024-09-27'),
  ('BDIAG2022',W/'2022-normal-reference-20261031/runs/B_diag/pair','NATIVE1709','2022-06-17'),('BDIAG2023',W/'recovery-2023-readiness-20261101/runs/Bdiag/pair','NATIVE1709','2023-01-19'),
  ('PVR_SLOT1_2026_LOCAL',W/'pvr-slot1-native-readiness-20261101/runs/2025_26/pair','NATIVE1709',None)]
 cases=[loadcase(*s) for s in specs];save('FIXED_CASES_BEFORE_COMPONENT_EXPORT.json',[c['spec'] for c in cases]);dates=sorted({d for c in cases if c['spec']['domain']=='NATIVE1709' for d in c['spec']['points']});nm,ni=export_native(dates)
 old_sec={};oldpoints=sorted({d for c in cases if c['spec']['domain']=='OLD407' for d in c['spec']['points']});oldcoverage=[]
 for sec,g in ROSTER.groupby('sector_id'):
  p=OLD_DIAG/f'sector-{sec}.csv';SRC[str(p)]=sha(p);f=pd.read_csv(p,index_col=0)
  for d in oldpoints:
   if d not in f.index:old_sec[sec,d]=dict(breadth=None,ready=0,identities=len(g));continue
   r=f.loc[d];old_sec[sec,d]=dict(breadth=float(r.m) if r.n>=5 else None,ready=int(r.n),identities=len(g));oldcoverage.append(dict(day=d,sector=sec,**old_sec[sec,d]))
 save('OLD407_CACHED_INDUSTRY_BREADTH.json',oldcoverage)
 market={}
 for domain,p in [('OLD407',RR/'actual-risk-recovery-20261027/recovery.csv'),('NATIVE1709',W/'mainline-absolute-Q4-20261031/recovery.csv')]:SRC[str(p)]=sha(p);market[domain]=pd.read_csv(p,index_col=0)
 modern_states={}
 def modern_stage(sec,d):
  if sec not in modern_states:
   p=Path(IM[sec]['refs']['state']);assert sha(p)==IM[sec]['output_sha256'][str(p)];SRC[str(p)]=sha(p);modern_states[sec]=pd.read_parquet(p).set_index('day')
  f=modern_states[sec];return f.loc[d].to_dict() if d in f.index else None
 allrecords=[];series=[];phase_summary=[]
 for c in cases:
  s=c['spec'];domain=s['domain'];df=market[domain];fills=c['fills'];audit=c['audit'];resume_day=day(s['resume']['at']) if s.get('resume') else s['primary_window'][0];base=n(s['resume']['nav']) if s.get('resume') else n(c['dd']['2026-04-30']['nav'])
  receipt_origin={};res={}
  for a in audit:
   if a['kind']=='reserve':res[a['order_id']]=a['at']
   if a['kind']=='fill' and a['receipt']['side']=='buy':receipt_origin[a['receipt']['receipt_id']]=res.get(a['order_id'])
  def origin(t):return t.get('signal_at') or receipt_origin.get(t['receipt_id'])
  phase_end=day(s['flat']['at']) if s.get('flat') else s['primary_window'][1]
  firstoff=next((d for d in df.index if d>resume_day and d<=phase_end and not bool(df.loc[d,'fast_on'])),None)
  if firstoff and 'first_original_fast_field_false_descriptive_only' not in s['points'].get(firstoff,[]):s['points'].setdefault(firstoff,[]).append('first_original_fast_field_false_descriptive_only')
  # Extra first-off fields are market/account only; original-m export remained fixed.
  for d,labels in sorted(s['points'].items()):
   r=c['dd'][d];mv={sid:D(q)*mark(sid,d,domain) for sid,q in r['positions'].items()};assert abs(sum(mv.values(),Z)-n(r['inventory']))<D('.00001'),(s['name'],d,'mark/inventory bridge')
   marketrow=df.loc[d].to_dict();held=defaultdict(lambda:Z);byrole=defaultdict(lambda:Z);known_m=Z;positive=negative=zero=Z;warm=unknown_g=Z;weighted=Z;known_ind=Z;details=[]
   for sid,value in mv.items():
    sec=META[sid]['sector_id'];held[sec]+=value;m=old_m(sid,d) if domain=='OLD407' else nm.get((sid,d));broad=old_sec.get((sec,d)) if domain=='OLD407' else ni.get((sec,d));bb=broad.get('breadth') if broad else None
    if m is not None:known_m+=value;positive+=value if m>0 else Z;negative+=value if m<0 else Z;zero+=value if m==0 else Z
    if bb is not None:known_ind+=value;weighted+=value*n(bb)
    if c['spec']['modern']:
     f=nativefacts(sid);t=pd.Timestamp(d);z=f.loc[t] if t in f.index else None
     if z is not None and bool(z.g_ready):warm+=value if z.g_grade>=2 else Z
     else:unknown_g+=value
    else:z=None;unknown_g+=value
    details.append(dict(sid=sid,name=META[sid]['name'],sector=sec,capital=value,weight_pct=value/n(r['nav'])*100,m_signed_EWM21=m,industry_breadth=bb,
      current_G1_grade=float(z.g_grade) if z is not None and bool(z.g_ready) else None,I_valid=bool(z.i_target) if z is not None else None))
   if s['modern']:
    for l in r['layers']:byrole[l['role']+'_'+l['pool']]+=D(l['qty'])*mark(l['sid'],d,domain)
   else:byrole['old_single_I_position_no_core_mobile_pools']=n(r['inventory'])
   today=[t for t in fills if day(t['at'])==d];buys=[t for t in today if t['side']=='buy'];industry=[]
   for sec in set(held)|({'URFI881121','URFI881172'} if domain=='NATIVE1709' else set()):
    data=old_sec.get((sec,d)) if domain=='OLD407' else ni.get((sec,d));industry.append(dict(sector=sec,capital=held.get(sec,Z),breadth_data=data,original_stage=modern_stage(sec,d) if s['modern'] and sec in IM else 'NOT PART OF OLD POLICY'))
   allrecords.append(dict(case=s['name'],domain=domain,day=d,labels=labels,clock='completed close; same-day actual buys originate from their prior recorded signals',market=marketrow,
    NAV=r['nav'],phase_return_from_resume_pct=(n(r['nav'])/base-1)*100 if s.get('resume') else None,exposure_pct=n(r['inventory'])/n(r['nav'])*100,available=r['available'],order_reserved=r['order_reserved'],
    actual_buys=len(buys),actual_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in buys),Z),actual_sells=sum(t['side']=='sell' for t in today),actual_buy_signal_dates=[day(origin(t)) if origin(t) else None for t in buys],
    pending_sells=r.get('pending_sells'),role_pool_capital=dict(byrole),held_capital=n(r['inventory']),stock_m_positive_capital=positive,stock_m_negative_capital=negative,stock_m_zero_capital=zero,stock_m_unknown_capital=n(r['inventory'])-known_m,
    industry_breadth_capital_weighted=weighted/known_ind if known_ind else None,industry_breadth_known_capital=known_ind,industry_breadth_unknown_capital=n(r['inventory'])-known_ind,
    original_G1_warm_capital=warm,original_G1_unknown_capital=unknown_g,held_top10=sorted(details,key=lambda x:-x['capital'])[:10],held_industry_strength=sorted(industry,key=lambda x:-x['capital'])))
  for d,r in c['dd'].items():
   if not resume_day<=d<=phase_end:continue
   if domain=='OLD407' and d>'2024-12-31':continue
   tt=[t for t in fills if day(t['at'])==d];rr=next((x for x in c['risks'] if day(x['at'])==d),None)
   series.append(dict(case=s['name'],day=d,NAV=r['nav'],exposure_pct=n(r['inventory'])/n(r['nav'])*100,phase_on=rr['on'] if rr else r.get('on'),
     market=df.loc[d].to_dict(),buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in tt if t['side']=='buy'),Z),sell_cash=sum((n(t['gross_cny'])-n(t['fees_cny']) for t in tt if t['side']=='sell'),Z),pending_sells=len(r.get('pending_sells',[]))))
  if s.get('resume'):
   phasebuys=[t for t in fills if t['side']=='buy' and resume_day<day(t['at'])<=phase_end];offbuys=[t for t in phasebuys if origin(t) and day(origin(t)) in df.index and not bool(df.loc[day(origin(t)),'fast_on'])]
   phase_summary.append(dict(case=s['name'],domain=domain,resume=resume_day,actual_phase_peak=day(s['peak']['at']),first_running_giveback10=day(s['giveback10']['at']) if s.get('giveback10') else None,pause=day(s['pause']['at']) if s.get('pause') else None,first_actual_flat=phase_end,
    first_original_fast_field_false=firstoff,peak_return_from_resume_pct=(n(s['peak']['nav'])/base-1)*100,flat_return_from_resume_pct=(n(s['flat']['nav'])/base-1)*100 if s.get('flat') else None,
    phase_buy_fills=len(phasebuys),phase_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in phasebuys),Z),buys_with_known_signal_fast_false=len(offbuys),buy_cash_signal_fast_false=sum((n(t['gross_cny'])+n(t['fees_cny']) for t in offbuys),Z),
    not_a_backtested_withdrawal_policy=True,later_old924_phase_context_not_current_PVR_SLOT1=True if domain=='OLD407' else False))
 save('CHECKPOINT_LIFECYCLE.json',allrecords);save('DAILY_ORIGINAL_MARKET_AND_CAPITAL.json',series);save('PHASE_SUMMARY.json',phase_summary);save('SOURCE_SHA256.json',SRC)
 save('COMPLETION.json',dict(completed=True,seconds=time.monotonic()-begun,cases=len(cases),checkpoints=len(allrecords),new_accounts=0,new_thresholds=0,new_gates=0,original_m_export_only=True,source_same_formula_gate=True,no_counterfactual_PnL=True))
 print('LIFECYCLE_READY',len(allrecords),'seconds',round(time.monotonic()-begun,2),flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(reason=repr(e),no_account_run=True));raise
