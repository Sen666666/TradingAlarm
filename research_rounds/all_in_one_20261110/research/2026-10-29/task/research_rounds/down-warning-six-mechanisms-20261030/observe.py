"""Observational T0/T1/T2 facts only; no indicators or trading engines run."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,json,hashlib,time,sys
import numpy as np,pandas as pd
T=time.monotonic();O=Path(__file__).resolve().parent;P=O.parent/'act-loss-facts-20261030';M=O.parent/'main-up-state-six-case-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');PH=R/'ph1-cross-sector-20261028';BASE=R/'pvr-local-finite-capital-20261029/baseline/accounts-v2'
def read(p):return json.loads(Path(p).read_text())
def rows(p):return list(csv.DictReader(Path(p).open()))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
for f,h in read(M/'INPUT_IDENTITY.json')['sha256'].items():assert sha(f)==h,f
sys.path.insert(0,str(R/'pv-strength-b5-20261025/code'));from arithmetic import compare
ids={'605118.SH','301486.SZ','688143.SH','601138.SH','688498.SH','002130.SZ'};cycles=[x for x in rows(P/'actual-cycles.csv') if x['symbol'] in ids];assert len(cycles)==7
snapshot=Path(read(R/'pvr-act-comparison-20261027/input.json')['snapshot']['path']);warnings={x['cycle_id']:x for x in rows(O.parent/'old-side-exit-all69-20261030/FROZEN_69_CYCLES.csv')};hold=rows(P/'actual-holding-close-paths.csv');two=read(M/'two-trigger-facts.json');cp={x['at'][:10]:x for x in read(BASE/'I__S0_base.json')['audit_log'] if x['kind']=='risk_checkpoint'}
sources=[Path(__file__),P/'actual-cycles.csv',P/'actual-holding-close-paths.csv',O.parent/'old-side-exit-all69-20261030/FROZEN_69_CYCLES.csv',M/'two-trigger-facts.json',BASE/'I__S0_base.json']
for s in ids:sources.extend([M/'fields'/f'{s}.parquet',PH/'events/TECH'/f'{s}.parquet',snapshot/'facts'/f'{s}.parquet'])
identity={str(p):sha(p) for p in sources};save('INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),study='Only descriptive fixed-seven-cycle comparison. Outcome labels never decision features. H1 prior progress/carrying history may distinguish; H2 later repair may add evidence. Neither assumed true.',T0='First existing native down warning, no new timestamp selection',T1='First native event+1 confirmation strictly after T0 and not after original exit request. Only known on confirmation day.',T2='Original structure/ACT exit request',repair_fraction_definition='(C_T1-L_T1)/(H_T0-L_T1), no clipping; all same causal price units. L known only at T1.',sha256=identity))
data=[];summary=[]
for c in cycles:
 key=c['cycle_id'];s=c['symbol'];w=warnings[key];t0=pd.Timestamp(w['date']);t2=pd.Timestamp(c['exit_request'][:10]);entry=pd.Timestamp(c['entry_at'][:10]);dec=pd.Timestamp(c['entry_decision'][:10]);f=pd.read_parquet(snapshot/'facts'/f'{s}.parquet');g=pd.read_parquet(M/'fields'/f'{s}.parquet');ev=pd.read_parquet(PH/'events/TECH'/f'{s}.parquet');assert f.index.equals(g.index) and f.index.equals(ev.index);np.testing.assert_array_equal(g.event.to_numpy(float),ev.event.to_numpy(float));assert int(ev.loc[t0,'event'])==-1
 epoch_start=None;prevactive=False;prevseg=None;epochs={}
 for day,z in f.loc[:t0].iterrows():
  active=bool(pd.notna(z.e0_target) and z.e0_target);seg=z.segment_id
  if active and (not prevactive or seg!=prevseg):epoch_start=day
  if not active:epoch_start=None
  epochs[day]=epoch_start;prevactive=active;prevseg=seg
 start=epochs[t0];assert start is not None;seg=f.loc[start:t0];es=ev.loc[start:t0];increases=[]
 for i in range(1,len(seg)):
  if compare(float(seg.iloc[i].e0_floor),float(seg.iloc[i-1].e0_floor))>0:increases.append(str(seg.index[i].date()))
 prevconfirmed=[dict(confirm=str(d.date()),event=int(z.event),pivot_date=str(z.pivot_date)[:10],pivot=float(z.pivot)) for d,z in ev.loc[start:t0].iterrows() if d<t0 and int(z.event)!=0]
 a=f.loc[t0];z=g.loc[t0];H=D(str(ev.loc[t0,'pivot']));F=D(str(a.e0_floor));C0=D(str(a.close));cand=ev[(ev.index>t0)&(ev.index<=t2)&(ev.event==1)];t1=cand.index[0] if len(cand) else None;h=[x for x in hold if x['cycle_id']==key];ht0=next(x for x in h if x['day']==str(t0.date()));credit=next((x for x in two if x['symbol']==s and x['S21_confirmed_down']==str(t0.date())),None)
 base=dict(cycle_id=key,symbol=s,name=c['name'],retrospective_severe=c['severe_final']=='True',retrospective_final_return=c['net_return'],T0=str(t0.date()),T0_pivot_date=str(ev.loc[t0,'pivot_date'])[:10],T0_peak_causal=H,T0_close=C0,T0_E0_start=str(start.date()),entry_to_T0_valid_price_observations=len(g.loc[entry:t0]),entry_decision_to_T0_valid_price_observations=len(g.loc[dec:t0]),E0_segment_up_confirmations=int((es.event==1).sum()),E0_segment_floor_increases_excluding_creation=len(increases),floor_increase_confirm_dates=increases,T0_floor=F,support_to_warning_peak=H/F-1,current_floor_down_distance=1-F/C0,T0_close_net_liquidation_return=ht0['net_liquidation_return'],prior_confirmed_sequence=prevconfirmed,T0_S21=float(z.S21),T0_mu21_logbp=float(z.mu21)*10000,T0_acute_down=bool(z.g_acute_down),T0_S21_confirmed_credit=credit['S21_confirmation_credit'] if credit else None,T0_S21_threshold=credit['S21_frozen_threshold'] if credit else None,credit_status='saved_same_day_S21_receipt' if credit else 'not_saved_at_T0_do_not_copy_later_receipt',native_E0_confirmation_magnitude='not_saved_in_minimal_event_cache',T1=str(t1.date()) if t1 is not None else None,T2=str(t2.date()),T2_original_reason=c['exit_reason'],T2_actual_exit=c['exit_at'],T2_I_active=bool(f.loc[t2,'i_target']),T2_ACT_on=cp[str(t2.date())]['on'])
 if t1 is not None:
  L=D(str(ev.loc[t1,'pivot']));C1=D(str(f.loc[t1,'close']));old=f.loc[:t1].iloc[-2];Fbefore=D(str(old.e0_floor));Fafter=D(str(f.loc[t1,'e0_floor']));same=epochs.get(t1)
  base.update(T1_pivot_date=str(ev.loc[t1,'pivot_date'])[:10],T1_confirmed_low=L,T1_close=C1,T1_floor_before=Fbefore,T1_floor_after=Fafter,T1_low_vs_T0_floor=L/F-1,T1_low_vs_immediate_old_floor=L/Fbefore-1,T1_floor_raised=compare(float(Fafter),float(Fbefore))>0,T1_peak_to_confirmed_low=L/H-1,T1_repaired_fraction_of_peak_low_decline=(C1-L)/(H-L) if H>L else None,T1_close_vs_T0_peak=C1/H-1,T1_recovered_T0_peak=compare(float(C1),float(H))>=0,T1_E0_I_active=bool(f.loc[t1,'e0_target'] and f.loc[t1,'i_target']),T1_ACT_on=cp[str(t1.date())]['on'],T1_close_net_liquidation_return=next((x['net_liquidation_return'] for x in h if x['day']==str(t1.date())),None))
 else:
  # Sequential checkpoints are retrospective observations, never features at T0.
  base['post_T0_observed_loss_checkpoints']={str(n):next((x['day'] for x in h if x['day']>str(t0.date()) and D(x['net_liquidation_return'])<=-D(n)/100),None) for n in [10,20,30]}
 data.append(base);summary.append({k:base.get(k) for k in ['cycle_id','T0','entry_to_T0_valid_price_observations','T0_E0_start','E0_segment_up_confirmations','E0_segment_floor_increases_excluding_creation','support_to_warning_peak','current_floor_down_distance','T0_close_net_liquidation_return','T0_S21','T0_mu21_logbp','T0_acute_down','T1','T1_confirmed_low','T1_floor_before','T1_floor_after','T1_peak_to_confirmed_low','T1_repaired_fraction_of_peak_low_decline','T1_close_vs_T0_peak','T1_floor_raised','T2']})
save('facts.json',data);pd.DataFrame(summary).to_csv(O/'facts-summary.csv',index=False);assert all(sha(p)==h for p,h in identity.items());save('COMPLETION.json',dict(at=datetime.now(timezone.utc).isoformat(),cycles=7,symbols=6,new_indicators=0,new_trade_paths=0,new_exit_PnL=0,source_hashes_unchanged=True,seconds=time.monotonic()-T));print(json.dumps(dict(summary=summary,seconds=time.monotonic()-T),ensure_ascii=False,default=str),flush=True)
