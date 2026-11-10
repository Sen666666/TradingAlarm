"""Signal-time diagnostics for frozen692 PVR2022 completed stock rounds.
No accounts, thresholds, parameter grid, or future-feature inputs.
"""
from pathlib import Path
import sys,json,pickle,hashlib,csv,ast
from decimal import Decimal as D
from collections import defaultdict
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;ROOT=O.parent.parent;OLD=O.parent/'2022_loss_attribution'
sys.path.insert(0,str(ROOT/'inputs'));import continuous_inputs as C
P=ROOT/'run_1200000/latest_checkpoint/checkpoint-2022-12-30.pkl';W=C.W;U=C.U
H1=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
FORMULA=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
HFORM=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/rs_h1_model.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,indent=2,allow_nan=False,default=str))
def safe(v):
 if v is None:return None
 try:return float(v)if np.isfinite(float(v))else None
 except (TypeError,ValueError):return str(v)
def main():
 b=P.read_bytes();hh=hashlib.sha256(b).hexdigest();assert hh==read(P.with_suffix('.json'))['sha256']==read(P.with_suffix('.provenance.json'))['checkpoint_sha256'];x=pickle.loads(b);del b;a=x['accounts']['PVR']
 roundfile=OLD/'STOCK_ROUNDS_2022.csv';rr=[r for r in csv.DictReader(roundfile.open())if r['account']=='PVR'and r['closed']];assert len(rr)==692
 fills={t['layer']:t for t in a['journal']if t['kind']=='real_buy_fill'}
 buys={t['layer']:t for t in a['trades']if t['side']=='buy'};births=[]
 for r in rr:
  ids=ast.literal_eval(r['layer_ids']);t=min((buys[k]for k in ids),key=lambda t:(t['at'],t['layer']));assert str(t['at'])==r['opened'];births.append((r,t))
 sources={str(p):sha(p)for p in [P,roundfile,H1,FORMULA,HFORM,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json']}
 assert sources[str(FORMULA)]=='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
 env=dict(np=np,pd=pd);exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),env);pvr=env['score']
 with np.load(H1)as z:
  dates=pd.DatetimeIndex(z['dates']);cols={str(s):i for i,s in enumerate(z['symbols'])};lo=dates.searchsorted(pd.Timestamp('2022-01-01'))-252;hi=dates.searchsorted(pd.Timestamp('2023-01-01'));hd=dates[lo:hi];H={k:z[k][lo:hi].copy()for k in ['score','close','segment','obs_count','h','raw','nref']}
 sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')};im={r['series']:r for r in read(U/'INDUSTRY_MANIFEST.json')};sector=a['sector_by_sid'];needed={sector[t['security_id']]for r,t in births};industry={}
 for s in needed:
  rec=im[s];p=Path(rec['refs']['state']);assert sha(p)==rec['output_sha256'][str(p)];sources[str(p)]=sha(p);industry[s]=pd.read_parquet(p)
 stage=defaultdict(list)
 for r in x['runner']['stage_events']:
  if r['account']=='PVR':stage[r['sector']].append(r)
 decisions={str(r['at'])[:10]:r for r in a['decisions']};by=defaultdict(list)
 for r,t in births:by[t['security_id']].append((r,t))
 features=[];validation=dict(rounds=692,H1_trade_and_cache_equal=0,H1_raw_components_equal=0,PVR_native_cache_equal=0,PVR_decision_equal=0,missing_resistance20=0,industry_level_from_native_log=0,industry_level_from_initial_warm_state=0)
 for sid,group in sorted(by.items()):
  rec=sm[sid];src=Path(next(p for p in rec['source_sha256']if p.endswith('/signal.parquet')));assert sha(src)==rec['source_sha256'][str(src)];sources[str(src)]=sha(src)
  latest=max(pd.Timestamp(t['signal_at'].date())for r,t in group);fullsignal=pd.read_parquet(src);f=fullsignal.loc[:latest];calc=pvr(f)
  cpfile=Path(rec['refs']['CP1']);assert sha(cpfile)==rec['output_sha256'][str(cpfile)];sources[str(cpfile)]=sha(cpfile);cp=pd.read_parquet(cpfile).loc[:latest]
  factsfile=Path(rec['refs']['facts']);assert sha(factsfile)==rec['output_sha256'][str(factsfile)];sources[str(factsfile)]=sha(factsfile);facts=pd.read_parquet(factsfile).loc[:latest]
  sp=C.D/'scores'/f'{sid}.parquet';smeta=next(z for z in read(C.D/'SCORES_MANIFEST.json')['entries']if z['symbol']==sid);assert sha(sp)==smeta['output_sha256'];sources[str(sp)]=sha(sp);native=pd.read_parquet(sp)
  valid=f.price_eligible.eq(True)&f.observed_bar.eq(True)&f.is_observed_bar.eq(True)&~f.source_invalid.eq(True)&~f.synthetic_event_bar.eq(True)&f.close.gt(0)&np.isfinite(f.close)
  for rr,t in group:
   day=pd.Timestamp(t['signal_at'].date());daystr=str(day.date());j=cols[sid];ti=hd.get_loc(day);h=int(H['h'][ti,j]);bounds=np.minimum(np.arange(5)*63,h);components=[]
   for k,w in enumerate([.4,.2,.2,.2],1):
    near,far=int(bounds[k-1]),int(bounds[k]);v=0. if near==far else H['close'][ti-near,j]/H['close'][ti-far,j]-1;components.append((v,w*v))
   rawcalc=round(sum(v for _,v in components),12);cached=float(H['raw'][ti,j]);assert abs(rawcalc-cached)<1e-10;validation['H1_raw_components_equal']+=1
   hscore=float(H['score'][ti,j]);assert abs(hscore-float(t['pvr']))<1e-10;validation['H1_trade_and_cache_equal']+=1
   pv=calc.loc[day];ns=native.loc[day,'score'];assert (pd.isna(pv.score)and pd.isna(ns))or abs(pv.score-ns)<1e-10;validation['PVR_native_cache_equal']+=1
   intent=next(i for i in decisions[daystr]['intents']if i['sid']==sid and i['role']==('core'if t['kind']=='core'else'mobile'))
   ds=intent['PVR_score'];assert (pd.isna(ns)and ds is None)or abs(ns-ds)<1e-10;validation['PVR_decision_equal']+=1
   price=safe(pv.r);amount_ratio=safe(f.loc[day,'amount']/pv.amount_ref);amount_log=safe(np.log(amount_ratio))if amount_ratio is not None else None
   quadrant='UNKNOWN'if price is None or amount_log is None else 'ZERO_AXIS'if price==0 or amount_log==0 else ('UP_'if price>0 else'DOWN_')+('AMOUNT_ABOVE_PRIOR_MEDIAN'if amount_log>0 else'AMOUNT_BELOW_PRIOR_MEDIAN')
   sidsector=sector[sid];industryframe=industry[sidsector];ir=industryframe[industryframe.day.eq(daystr)];assert len(ir)==1;ir=ir.iloc[0]
   se=[r for r in stage[sidsector]if r['day']<=daystr]
   if se:fin=se[-1]['financial_level'];level_source='native_stage_event';validation['industry_level_from_native_log']+=1
   else:
    warm=industryframe[industryframe.day.lt('2022-01-01')].iloc[-1];fin=int(warm.stage)-1 if pd.notna(warm.attempt_id)else 0;level_source='unchanged_initial_warm_state';validation['industry_level_from_initial_warm_state']+=1
   prior=f[(f.index<day)&valid&f.segment_id.eq(f.loc[day,'segment_id'])&np.isfinite(f.high)&f.high.gt(0)].tail(20)
   resistance=extension=highdist=closedist=meanclose=None
   if len(prior)==20:
    resistance=float(prior.high.max());highdist=float(f.loc[day,'close']/resistance-1);closedist=float(f.loc[day,'close']/prior.close.max()-1);meanclose=float(prior.close.mean());extension=float(f.loc[day,'close']/meanclose-1)
   else:validation['missing_resistance20']+=1
   fr=facts.loc[day];rawclose=D(str(fr.raw_close));execution_open=t['raw_open'];pnl=D(rr['pnl'])
   row=dict(account='PVR',sid=sid,round_id=int(rr['id']),first_buy_layer=t['layer'],signal_at=str(t['signal_at']),execution_at=str(t['at']),signal_quarter=str(day.to_period('Q')),entry_quarter=str(pd.Timestamp(t['at'].date()).to_period('Q')),closed_at=rr['closed'],round_pnl=float(pnl),round_outcome='WIN'if pnl>0 else'LOSS'if pnl<0 else'FLAT',round_layers=int(rr['layers']),first_role='CORE'if t['kind']=='core'else'MOBILE',first_buy_shares=t['shares'],first_buy_gross=float(t['gross_cny']),H1_score=hscore,H1_raw=cached,H1_h=h,H1_nref=int(H['nref'][ti,j]),H1_obs_count=int(H['obs_count'][ti,j]),PVR_score=safe(pv.score),PVR_r=price,PVR_scale=safe(pv.scale),PVR_amount_reference=safe(pv.amount_ref),signal_amount=safe(f.loc[day,'amount']),PVR_amount_ratio=amount_ratio,PVR_log_amount_ratio=amount_log,PVR_u=safe(pv.u),PVR_b=safe(pv.b),PVR_e=safe(pv.e),PVR_E=safe(pv.E),PVR_signal_bar_quadrant=quadrant,sector=sidsector,industry_E0_valid=bool(ir.E0_valid),industry_stage=int(ir.stage),industry_stage_name=ir.stage_name,industry_financial_level=int(fin),industry_level_source=level_source,industry_action=ir.action,industry_new_receipt=bool(ir.new_receipt),signal_adjusted_close=float(f.loc[day,'close']),signal_raw_close=float(rawclose),signal_factor=float(fr.factor),original_G_grade=safe(fr.g_grade),original_I_floor=safe(fr.i_floor),prior20_valid_observations=len(prior),prior20_last_day=str(prior.index[-1].date())if len(prior)else None,prior20_high_resistance=resistance,distance_to_prior20_high=highdist,distance_to_prior20_close_max=closedist,prior20_mean_close=meanclose,extension_to_prior20_mean_close=extension,signal_above_prior20_high='UNKNOWN'if highdist is None else 'ABOVE'if highdist>0 else 'AT_OR_BELOW',execution_raw_open=float(execution_open),execution_buy_price=float(t['price']),execution_open_gap_vs_signal_raw_close=float(execution_open/rawclose-1),execution_gap_information_time='EXECUTION_OPEN_ONLY_NOT_SIGNAL_TIME')
   cpday=cp.loc[day];hist=facts.loc[:day];keys=list(zip(hist.i_target.astype(bool),hist.segment_id));start=len(hist)-1
   while start>0 and keys[start-1]==keys[-1]:start-=1
   istart=hist.index[start] if bool(fr.i_target) else None
   efactor=D(str(fullsignal.loc[pd.Timestamp(t['at'].date()),'adjustment_factor']));sfactor=D(str(fr.factor));floor=t['floor'];cpscale=safe(cpday.s)
   row.update(first_buy_reason=t['reason'],first_buy_CP1_id=intent.get('CP1_id'),signal_fresh_CP1=bool(cpday.receipt),signal_I_target=bool(fr.i_target),signal_I_run_start=str(istart.date())if istart is not None else None,signal_I_run_age_valid_bars=int(valid.loc[istart:day].sum()-1)if istart is not None else None,first_buy_actual_pool=fills[t['layer']]['pool'],first_buy_actual_industry_attempt=fills[t['layer']]['attempt'],first_buy_floor_adjusted=float(floor),first_buy_floor_raw_signal=float(floor/sfactor),first_buy_floor_raw_execution=float(floor/efactor),signal_floor_risk_distance=float(1-floor/sfactor/rawclose),execution_floor_risk_distance=float(1-floor/efactor/execution_open),execution_factor=float(efactor),execution_open_gap_factor_aligned=float(execution_open*efactor/(rawclose*sfactor)-1),CP1_sigma=cpscale,extension20_log_sigma=safe(np.log(1+extension)/cpscale)if extension is not None and cpscale and cpscale>0 else None,distance20_high_log_sigma=safe(np.log(1+highdist)/cpscale)if highdist is not None and cpscale and cpscale>0 else None)
   for k,(v,wv)in enumerate(components,1):row[f'H1_segment{k}_return']=float(v);row[f'H1_segment{k}_weighted']=float(wv);row[f'H1_segment{k}_near_lag']=int(bounds[k-1]);row[f'H1_segment{k}_far_lag']=int(bounds[k])
   features.append(row)
  if len(features)%100<5:print('features',len(features),flush=True)
 f=pd.DataFrame(features).sort_values(['execution_at','sid','round_id']);assert len(f)==692 and not f[['account','sid','round_id']].duplicated().any();assert f.round_outcome.eq('LOSS').sum()==562
 f.to_csv(O/'ENTRY_FEATURES.csv',index=False)
 categorical=['signal_fresh_CP1','signal_I_target','first_buy_actual_pool','first_role','PVR_signal_bar_quadrant','industry_stage_name','industry_financial_level','signal_above_prior20_high'];summ=[]
 for category in categorical:
  for quarter,q in [('ALL',f)]+list(f.groupby('entry_quarter')):
   for label,g in q.groupby(category,dropna=False):
    summ.append(dict(entry_quarter=quarter,feature=category,value=str(label),n=len(g),wins=int(g.round_outcome.eq('WIN').sum()),losses=int(g.round_outcome.eq('LOSS').sum()),win_rate=float(g.round_outcome.eq('WIN').mean()),mean_round_pnl=float(g.round_pnl.mean()),net_pnl=float(g.round_pnl.sum()),negative_pnl_sum=float(g.loc[g.round_pnl<0,'round_pnl'].sum()),positive_pnl_sum=float(g.loc[g.round_pnl>0,'round_pnl'].sum())))
 pd.DataFrame(summ).to_csv(O/'CATEGORICAL_QUARTER_DIAGNOSTICS.csv',index=False)
 numerics=['signal_I_run_age_valid_bars','signal_floor_risk_distance','execution_floor_risk_distance','extension20_log_sigma','distance20_high_log_sigma','CP1_sigma','H1_score','H1_raw','H1_h','H1_segment1_return','H1_segment2_return','H1_segment3_return','H1_segment4_return','PVR_score','PVR_r','PVR_u','PVR_b','PVR_e','PVR_E','PVR_amount_ratio','distance_to_prior20_high','distance_to_prior20_close_max','extension_to_prior20_mean_close','execution_open_gap_vs_signal_raw_close'];out=[]
 for quarter,q in [('ALL',f)]+list(f.groupby('entry_quarter')):
  for outcome,g in q.groupby('round_outcome'):
   for col in numerics:
    z=pd.to_numeric(g[col],errors='coerce');out.append(dict(entry_quarter=quarter,outcome=outcome,feature=col,n=len(g),known=int(z.notna().sum()),mean=safe(z.mean()),median=safe(z.median()),round_pnl_sum=float(g.round_pnl.sum())))
 pd.DataFrame(out).to_csv(O/'NUMERIC_QUARTER_OUTCOME_DIAGNOSTICS.csv',index=False)
 cross=[]
 for (quarter,role,outcome),g in f.groupby(['entry_quarter','first_role','round_outcome']):
  for col in numerics:
   z=pd.to_numeric(g[col],errors='coerce');cross.append(dict(entry_quarter=quarter,first_role=role,outcome=outcome,feature=col,n=len(g),known=int(z.notna().sum()),mean=safe(z.mean()),median=safe(z.median()),round_pnl_sum=float(g.round_pnl.sum())))
 pd.DataFrame(cross).to_csv(O/'ROLE_QUARTER_OUTCOME_NUMERICS.csv',index=False)
 cross=[]
 for col in categorical[2:]:
  if col=='first_role':continue
  for (quarter,role,label),g in f.groupby(['entry_quarter','first_role',col],dropna=False):
   cross.append(dict(entry_quarter=quarter,first_role=role,feature=col,value=str(label),n=len(g),wins=int(g.round_outcome.eq('WIN').sum()),win_rate=float(g.round_outcome.eq('WIN').mean()),net_pnl=float(g.round_pnl.sum())))
 pd.DataFrame(cross).to_csv(O/'ROLE_QUARTER_CATEGORICAL.csv',index=False)
 save('VALIDATION.json',dict(**validation,account_runs=0,parameter_searches=0,thresholds_selected=0,feature_information_time='signal_at except separately labelled execution_open fields',source_sha256=sources))
 save('OUTPUT_SHA256.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print('PASS',json.dumps(validation),flush=True);print(pd.DataFrame(summ).query('entry_quarter=="ALL"').to_string(index=False),flush=True)
if __name__=='__main__':main()
