"""Mathematical path descriptors under old CP anchors; no new G/receipt/account."""
from pathlib import Path
import csv,hashlib,json,math
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];H={}
def bind(p):
 p=Path(p).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def clean(v):
 if v is pd.NA or v is pd.NaT:return None
 if isinstance(v,pd.Timestamp):return v.isoformat()
 if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x)for x in v]
 if hasattr(v,'item'):return clean(v.item())
 if isinstance(v,float)and not math.isfinite(v):return None
 return v
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n')
def csvsave(n,rows):
 with(OUT/n).open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))
def main():
 bind(__file__)
 sm={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 summary={}
 for sid in ['002583.SZ','300085.SZ']:
  rec=sm[sid];frames={}
  for key in ['facts','CP1','CP1_input']:
   path=bind(rec['refs'][key]);assert H[str(path)]==rec['output_sha256'][str(path)];frames[key]=pd.read_parquet(path)
  f=frames['CP1_input'].loc[:'2024-11-27'];cp=frames['CP1'].loc[:'2024-11-27'];facts=frames['facts'];assert f.index.equals(cp.index)
  anchor=None;anchor_day=None;path=0.;high=None;steps=0;prev=None;prevseg=None;rows=[]
  for day,raw in f.loc[:'2024-11-27'].iterrows():
   c=cp.loc[day];p=math.log(float(raw.close));seg=raw.segment_id
   r=p-prev if prev is not None and prevseg==seg else None
   incomingA=p-anchor if anchor is not None else None
   incomingL=math.fsum([path,abs(r)])if anchor is not None and r is not None else None
   incomingN=steps+1 if incomingL is not None else 0
   incomingDD=max(high,p)-p if high is not None else None
   incomingER=incomingA/incomingL if incomingL is not None and incomingL>0 else None
   incoming_anchor=anchor;incoming_day=anchor_day
   reason=None if pd.isna(c.reset_reason)else str(c.reset_reason)
   missing=pd.isna(c.anchor)
   reanchor=not missing and reason in ['start','E0_down_reset','lower_anchor']
   if missing:
    A=L=ER=DD=None;n=0;used_day=None;used_anchor=None;kind='ORIGINAL_NO_VALID_ANCHOR'
    anchor=None;anchor_day=None;path=0.;high=None;steps=0
   elif reanchor:
    used_anchor=float(c.anchor);assert math.isclose(used_anchor,p,abs_tol=1e-12)
    A=0.;L=0.;ER=None;DD=0.;n=0;used_day=str(day.date());kind='ORIGINAL_REANCHOR_'+reason
    anchor=used_anchor;anchor_day=used_day;path=0.;high=p;steps=0
   else:
    assert anchor is not None and incomingL is not None,(sid,day,reason)
    assert math.isclose(anchor,float(c.anchor),abs_tol=1e-12),(sid,day,anchor,c.anchor)
    A=incomingA;L=incomingL;ER=incomingER;DD=incomingDD;n=incomingN;used_day=anchor_day;used_anchor=anchor
    kind='ORIGINAL_RECEIPT_PRE_RESET'if bool(c.receipt)else'ORIGINAL_CONTINUING_PATH'
    path=L;high=max(high,p);steps=n
   before_reset=bool(c.receipt)
   if bool(c.receipt):
    # Row above records old-anchor path. Only future observations see this reset.
    anchor=float(c.next_anchor);anchor_day=str(day.date());path=0.;high=p;steps=0
   daystr=str(day.date());fa=facts.loc[day]
   if '2024-09-23'<=daystr<='2024-11-27':
    rows.append(dict(sid=sid,date=daystr,clock='Original CLOSE15:10+08 consuming protocol; not vendor timestamp',
     raw_close=float(fa.raw_close),continuous_close=float(raw.close),source_segment=int(seg),original_I_target=int(fa.i_target),
     old_CP_phase=None if pd.isna(c.phase)else str(c.phase),old_CP_reset_reason=reason,old_CP_receipt=bool(c.receipt),
     path_kind=kind,original_used_anchor_log=used_anchor,original_anchor_day=used_day,anchor_CLOSE=math.exp(used_anchor)if used_anchor is not None else None,
     observations_since_anchor=n,r_log_current=r,A_net_log_progress=A,L_all_abs_log_returns=L,ER=A/L if L is not None and L>0 else None,DD_log_known_high_to_current=DD,
     is_new_frontier_original=bool(c.delta_frontier>0),original_delta_frontier=float(c.delta_frontier),
     receipt_path_is_pre_reset=before_reset,
     incoming_old_anchor_day_before_reanchor=incoming_day if reanchor or missing else None,
     incoming_old_anchor_log_before_reanchor=incoming_anchor if reanchor or missing else None,
     incoming_A_before_reanchor=incomingA if reanchor or missing else None,
     incoming_L_before_reanchor=incomingL if reanchor or missing else None,
     incoming_ER_before_reanchor=incomingER if reanchor or missing else None,
     incoming_DD_before_reanchor=incomingDD if reanchor or missing else None,
     after_this_row_anchor_day=anchor_day,after_this_row_L=path,
     no_new_G_or_trading_state=True))
   prev=p;prevseg=seg
  assert len(rows)==43
  save(sid+'_ORIGINAL_ANCHOR_ER_DAILY.json',rows);csvsave(sid+'_ORIGINAL_ANCHOR_ER_DAILY.csv',rows)
  # Show all non-new-high observations, not only favorable or failed examples.
  nonhigh=[r for r in rows if not r['is_new_frontier_original']]
  save(sid+'_ALL_NON_NEW_HIGH_ROWS.json',nonhigh)
  save(sid+'_ORIGINAL_REANCHORS_AND_RECEIPTS.json',[r for r in rows if r['path_kind']!='ORIGINAL_CONTINUING_PATH'])
  # Separate descriptive clock: previous original confirmed receipt, never local
  # down/SEEK resets. This is NOT a new candidate that may borrow old receipts.
  confirmed_rows=[];ca=None;cad=None;cl=0.;ch=None;cn=0;pp=None;ps=None
  for day,raw in f.iterrows():
   c=cp.loc[day];p=math.log(float(raw.close));seg=raw.segment_id
   source_break=ps is not None and seg!=ps
   if source_break:ca=None;cad=None;cl=0.;ch=None;cn=0
   r=p-pp if pp is not None and not source_break else None
   incomingA=p-ca if ca is not None else None
   incomingL=math.fsum([cl,abs(r)])if ca is not None and r is not None else None
   incomingDD=max(ch,p)-p if ch is not None else None
   incomingER=incomingA/incomingL if incomingL is not None and incomingL>0 else None
   usedca=ca;usedcad=cad
   if not bool(raw.e0_valid):
    A=L=ER=DD=None;n=0;kind='ORIGINAL_I_DOMAIN_OFF_CLEAR'
    ca=None;cad=None;cl=0.;ch=None;cn=0
   elif ca is None:
    A=L=ER=DD=None;n=0;kind='NO_PRIOR_ORIGINAL_RECEIPT_IN_VALID_DOMAIN'
   else:
    A=incomingA;L=incomingL;ER=incomingER;DD=incomingDD;n=cn+1
    cl=L;ch=max(ch,p);cn=n
    kind='ORIGINAL_RECEIPT_PRE_RESET'if bool(c.receipt)else'CONTINUING_SINCE_LAST_ORIGINAL_RECEIPT'
   if bool(c.receipt)and bool(raw.e0_valid):ca=p;cad=str(day.date());cl=0.;ch=p;cn=0
   d=str(day.date());fa=facts.loc[day]
   if '2024-09-23'<=d<='2024-11-27':
    confirmed_rows.append(dict(sid=sid,date=d,clock='Original CLOSE15:10+08 consuming protocol; not vendor timestamp',
     raw_close=float(fa.raw_close),continuous_close=float(raw.close),source_segment=int(seg),original_I_target=int(fa.i_target),
     old_CP_reset_reason=None if pd.isna(c.reset_reason)else str(c.reset_reason),old_CP_receipt=bool(c.receipt),
     anchor_kind='LAST_ORIGINAL_RECEIPT_ANCHOR_DIAGNOSTIC_NOT_CANDIDATE',path_kind=kind,
     last_original_receipt_anchor_day=usedcad,last_original_receipt_anchor_log=usedca,anchor_CLOSE=math.exp(usedca)if usedca is not None else None,
     observations_since_anchor=n,A_net_log_progress=A,L_all_abs_log_returns=L,ER=ER,DD_log_known_high_to_current=DD,
     is_new_frontier_original=bool(c.delta_frontier>0),receipt_path_is_pre_reset=bool(c.receipt),
     source_break_cleared=source_break,down_or_SEEK_reset_did_not_clear=bool(str(c.reset_reason)in['E0_down_reset','lower_anchor']and bool(raw.e0_valid)),
     incoming_A_before_domain_off=incomingA if not bool(raw.e0_valid)else None,
     incoming_L_before_domain_off=incomingL if not bool(raw.e0_valid)else None,
     incoming_ER_before_domain_off=incomingER if not bool(raw.e0_valid)else None,
     after_this_row_anchor_day=cad,after_this_row_L=cl,
     not_a_new_G_or_trading_state=True,
     original_receipt_reset_is_for_description_only=True))
   pp=p;ps=seg
  assert len(confirmed_rows)==43
  save(sid+'_LAST_ORIGINAL_RECEIPT_ANCHOR_ER_DAILY.json',confirmed_rows)
  csvsave(sid+'_LAST_ORIGINAL_RECEIPT_ANCHOR_ER_DAILY.csv',confirmed_rows)
  summary[sid]=dict(observations=43,non_new_high_rows=len(nonhigh),defined_ER=sum(r['ER']is not None for r in rows),
   receipts=sum(r['old_CP_receipt']for r in rows),
   defined_non_new_high_ER_rows=[{k:r[k]for k in ['date','raw_close','original_anchor_day','observations_since_anchor','A_net_log_progress','L_all_abs_log_returns','ER','DD_log_known_high_to_current','original_I_target']}for r in nonhigh if r['ER']is not None],
   computed_history_start=str(f.index.min()),price_input=str(rec['refs']['CP1_input']),old_CP_anchor_source=str(rec['refs']['CP1']),
   last_original_receipt_mode_defined_ER=sum(r['ER']is not None for r in confirmed_rows),
   last_original_receipt_mode_does_not_clear_on_down_or_SEEK=True)
 save('COUNTS_AND_NONHIGH_COVERAGE.json',summary)
 save('SCOPE_AND_FORMULAS.json',dict(formulas={'A':'ln(C_t/C_anchor)','L':'sum allabs ln(C_i/C_prev) after anchor through t, including declines and recoveries','ER':'A/L when L>0, undefined whenL0; not clamped','DD':'ln(max known C from anchor through t / C_t)'},
  clock='Receipt day is recorded using old anchor then resets. Original down/start/SEEK lower-anchor day is mainA0/L0, with incoming old-anchor path separately copied before reset.',
  native_CP_not_rerun=True,reset_membership_from_original_CP_cache=True,new_G_states=0,new_receipt_rules=0,new_accounts=0,new_returns=0,new_thresholds=0,
  identity='Two separately labelled diagnostics: local original CP anchor resets on original down/SEEK/receipt; LAST_ORIGINAL_RECEIPT_ANCHOR clears only source/I off and resets after each old receipt is recorded. Neither is a new candidate. A future G model must not reset using a receipt it did not itself pass. Single positive observation after any anchor impliesER1 algebraically.'))
 save('SOURCE_SHA256.json',H)
if __name__=='__main__':main()
