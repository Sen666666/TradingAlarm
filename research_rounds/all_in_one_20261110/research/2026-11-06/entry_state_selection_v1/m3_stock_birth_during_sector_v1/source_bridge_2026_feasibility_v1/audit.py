"""Read-only 2026 H1 unknown-path source evidence; never imports/runs economics."""
from pathlib import Path
import json,hashlib,datetime
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
R=O.parent.parent
E=R/'m3_stock_birth_during_sector_v1'
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
MP=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CAN=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
PREP=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-a/prepare_a.py')
CAL=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f: json.dump(x,f,ensure_ascii=False,indent=2,default=str,allow_nan=False);f.write('\n')
src={}; rows=[]; overlaps=[]; transitions=[]; eventrows=[]; tails=[]
def record(p):
 p=Path(p);src[str(p)]=sha(p);return p
roundfile=record(E/'lifecycle_v1/ALL_2026H1_SEMI_ROUNDS.csv')
z=pd.read_csv(roundfile)
u=z[z.arm.eq('A_UNION_B')&z.status.str.contains('UNKNOWN')].copy()
assert len(u)==20 and u.status.value_counts().to_dict()=={'SOURCE_CHANGE_PATH_UNKNOWN':16,'FACTOR_PATH_UNKNOWN':4}
ms={m['symbol']:m for m in read(record(MP))}
record(PREP);record(CAL);record(Path(__file__))
cal=pd.DatetimeIndex(sorted(pd.read_parquet(CAL,columns=['day']).day.unique()))
raw=pd.read_parquet(CAN,filters=[('symbol','in',u.sid.tolist())]); record(CAN)
assert set(raw.source)=={'tushare'}
for r in u.itertuples():
 sp=record(next(p for p in ms[r.sid]['source_sha256'] if p.endswith('/signal.parquet')))
 assert src[str(sp)]==ms[r.sid]['source_sha256'][str(sp)], 'Frozen signal hash mismatch'
 p=pd.read_parquet(sp);d=pd.Timestamp(r.status_day);b=p.loc[d]; prev=p.loc[p.index<d].iloc[-1];prevday=p.index[p.index<d][-1]
 row=dict(round_id=r.round_id,sid=r.sid,name=r.name,status=r.status,day=r.status_day,
   previous_day=str(prevday.date()),old_kind=prev.source_kind,new_kind=b.source_kind,
   old_path=prev.source_path,new_path=b.source_path,old_segment=int(prev.segment_id),new_segment=int(b.segment_id),
   factor_old=float(prev.adjustment_factor),factor_new=float(b.adjustment_factor),volume_factor_old=float(prev.volume_factor),volume_factor_new=float(b.volume_factor),raw_open=float(b.raw_open),raw_close=float(b.raw_close),
   observed=bool(b.observed_bar),price_eligible=bool(b.price_eligible),volume_eligible=bool(b.volume_eligible),source_invalid=bool(b.source_invalid),synthetic=bool(b.synthetic_event_bar))
 if r.status.startswith('SOURCE'):
  jp=record(b.source_path); tj=read(jp);ths=pd.DataFrame(tj['bars']).set_index('date');ths.index=pd.to_datetime(ths.index)
  can=raw[raw.symbol.eq(r.sid)].set_index('trade_date');can['volume']*=100;can['amount']*=1000
  ix=can.index.intersection(ths.index);ix=ix[ix<d]
  assert len(ix)>0 and ix.max()==prevday and not can.index.duplicated().any() and not ths.index.duplicated().any()
  count=0
  for c in ['open','high','low','close','volume','amount']:
   a=can.loc[ix,c].to_numpy();bvals=ths.loc[ix,c].to_numpy();delta=np.abs(a-bvals)
   atol,rtol=(1e-6,0) if c in ['open','high','low','close'] else (1.,1e-6)
   bad=~np.isclose(a,bvals,atol=atol,rtol=rtol);count+=int(bad.sum())
   overlaps.append(dict(sid=r.sid,field=c,rows=len(ix),first=str(ix.min().date()),last=str(ix.max().date()),
      maximum_absolute_difference=float(delta.max()),maximum_relative_difference=float((delta/np.maximum(abs(a),abs(bvals))).max()),
      different_over_1e6=int((delta>1e-6).sum()),existing_atol=atol,existing_rtol=rtol,conflicts_existing_tolerance=int(bad.sum())))
  future_index=cal[(cal>=d)&(cal<=pd.Timestamp('2026-06-30'))]
  w=p.reindex(future_index);t=ths.reindex(future_index)
  boolcols=['observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']
  for bc in boolcols:
   assert w[bc].notna().all() and all(isinstance(v,(bool,np.bool_)) for v in w[bc]), (r.sid,bc,'Missing/nonboolean flag; fail closed')
  wb=w[boolcols].astype(bool)
  field_pairs=[('raw_open','open'),('raw_high','high'),('raw_low','low'),('raw_close','close'),('raw_volume','volume'),('amount','amount')]
  differences={pc:float(np.nanmax(np.abs(w[pc]-t[tc]))) for pc,tc in field_pairs}
  assert all(x==0 for x in differences.values())
  tail=dict(sid=r.sid,common_sessions=len(future_index),source_rows=int(t.open.notna().sum()),
    signal_rows=int(w.raw_open.notna().sum()),missing_dates='|'.join(str(v.date()) for v in future_index[t.open.isna()]),
    source_path_count=int(w.source_path.nunique()),invalid_or_synthetic=int((~wb.observed_bar|~wb.price_eligible|~wb.volume_eligible|wb.source_invalid|wb.synthetic_event_bar).sum()),
    signal_vs_source_max_abs_difference=differences,
    factor_change_dates='|'.join(str(v.date()) for v in w.index[w.adjustment_factor.ne(w.adjustment_factor.shift())][1:]))
  tails.append(tail)
  row.update(overlap_rows=len(ix),canonical_last=str(can.index.max().date()),conflicts_existing_tolerance=count,
      price_coordinate_unchanged=bool(prev.adjustment_factor==b.adjustment_factor and prev.volume_factor==b.volume_factor and prev.segment_id==b.segment_id),
      archive_fetched_at=tj.get('fetched_at',tj.get('observed_at')),bridge_candidate=True)
  assert count==0 and row['price_coordinate_unchanged']
  transitions.append(dict(sid=r.sid,transition_day=str(d.date()),previous_day=str(prevday.date()),
    from_lineage=[prev.source_kind,prev.source_path,int(prev.segment_id)],to_lineage=[b.source_kind,b.source_path,int(b.segment_id)],
    factor=float(b.adjustment_factor),volume_factor=float(b.volume_factor),old_source_sha256=src[str(CAN)],new_source_sha256=src[str(jp)],
    signal_path=str(sp),signal_sha256=src[str(sp)],overlap_before_transition=len(ix),existing_tolerance_conflicts=0,
    status='CANDIDATE_NOT_ACTIVATED',scope='only this exact source transition; do not disable later factor/missing/source checks'))
 rights_path=record(AS/'data-adjudicated-v2/rights'/(r.sid+'.json')); rights=read(rights_path)
 source_rights=record(rights['source_path'])
 assert src[str(source_rights)]==rights['source_sha256']
 terms={e['effective_date']:e for e in rights['events']}
 old=p.shift(1);w=p.loc[d:'2026-06-30'];change=w.index[w.adjustment_factor.ne(old.loc[w.index].adjustment_factor)]
 for day in change:
  a=old.loc[day];b2=p.loc[day];tx=terms.get(str(day.date()),{})
  cash=tx.get('gross_cash_per_old_share');split=1+tx.get('bonus_shares_per_old_share',0)+tx.get('capitalization_shares_per_old_share',0)
  expected=a.adjustment_factor*split*a.raw_close/(a.raw_close-cash) if cash is not None else None
  eventrows.append(dict(sid=r.sid,day=str(day.date()),first_interrupt=r.status_day==str(day.date()),d_source=cash,
    split=split,previous_close=float(a.raw_close),factor_old=float(a.adjustment_factor),factor_new=float(b2.adjustment_factor),
    formula_relative_error=abs(float(b2.adjustment_factor/expected-1)) if expected else None,
    raw_open=float(b2.raw_open),pay_date=tx.get('pay_date'),announcement_date=tx.get('announcement_date'),
    record_date=tx.get('record_date'),rights_path=str(rights_path),rights_source_path=str(source_rights),
    source_text=' | '.join(x['471'] for x in rights['records'] if str(x['1'])==str(day.date()).replace('-','')),
    coordinate_evidence_only=True,entitlement_admitted=False))
 rows.append(row)
pd.DataFrame(rows).to_csv(O/'UNKNOWN_FIRST_INTERRUPTION.csv',index=False)
pd.DataFrame(overlaps).to_csv(O/'SOURCE_OVERLAP.csv',index=False)
pd.DataFrame(tails).to_csv(O/'POST_SWITCH_RAW_COVERAGE.csv',index=False)
pd.DataFrame(eventrows).to_csv(O/'CASH_FACTOR_EVENTS.csv',index=False)
save('SOURCE_BRIDGE_CANDIDATES.json',transitions)
summary=dict(unknown=20,source_changes=16,initial_factor_changes=4,
 total_overlap_stock_days=sum(t['overlap_before_transition'] for t in transitions),
 OHLC_conflict_cells=0,OHLCV_amount_conflict_cells_existing_tolerance=sum(x['conflicts_existing_tolerance'] for x in overlaps),
 tail_sessions_per_stock=31,tail_source_bars=16*31,tail_missing_source_bars=sum(t['common_sessions']-t['source_rows'] for t in tails),
 subsequent_cash_factor_events=sum(not x['first_interrupt'] for x in eventrows),cash_factor_events_total=len(eventrows),
 pure_cash_events=sum(x['split']==1 and x['d_source'] is not None for x in eventrows),
 max_cash_factor_formula_relative_error=max(x['formula_relative_error'] for x in eventrows),
 activated_bridges=0,economic_runs=0,account_runs=0,original_source_files_modified=False,
 archived_PIT_certified=False,held_positions_counted_as_wins=False,
 source_validation_policy='Existing prepare_a.py tolerances retained, no silent renormalization beyond documented Tushare lots/1000 CNY units',
 caveats=['Actual historical orderability unknown.','Archived history collected in October 2026; no certification of historical information availability.',
 'Six source-bridge candidates encounter later cash factors. Four initial cash factors need official entitlement timing/amount evidence.',
 'Original permits, original M3/I/CP features and queues are not reconstructed or corrected.',
 'Restoring originally selected paths can later change occupancy and selections; bounded replay is not a complete A+B strategy result.'])
save('SUMMARY.json',summary)
save('SOURCE_HASHES.json',src)
save('OUTPUT_HASHES.json',{x.name:sha(x) for x in O.iterdir() if x.is_file() and x.name!='OUTPUT_HASHES.json'})
print(json.dumps(summary,ensure_ascii=False,indent=2))
