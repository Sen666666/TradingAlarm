from pathlib import Path
import json,csv,hashlib,math
import pandas as pd
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=R/'mainline_daily_industry_robotics_appendix_v1';OLD=R/'mainline_daily_industry_evidence_v1';B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rd(p):return json.loads(Path(p).read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def finite(x):
 try:return x is not None and math.isfinite(float(x))
 except:return False
def tri(x):
 if isinstance(x,(bool,np.bool_)):return int(x)
 return int(x) if finite(x) and x in (0,1) else -1
def bt(x):return int(x) if isinstance(x,(bool,np.bool_)) else -1
def lin(r):
 v=[r.get(k) for k in ['source_kind','source_path','segment_id']]
 return tuple(str(x) for x in v) if all(pd.notna(x) and str(x).strip().lower() not in ('','none','null','nan','na','unknown') for x in v) else None
def valid(r):
 return all(bt(r.get(k))==1 for k in ['observed_bar','price_eligible','volume_eligible']) and all(bt(r.get(k))==0 for k in ['source_invalid','synthetic_event_bar'])
hashes={};source=rd(B/'SOURCE_HASHES.json')
def pq(p,h,**kw):
 assert sha(p)==h;hashes[str(p)]=h;return pd.read_parquet(p,**kw)
ten=rd(O/'TEN_MATURE_IDENTITIES.json');ids=[x['sid'] for x in ten];manifestpath=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
assert sha(manifestpath)==source[str(manifestpath)];hashes[str(manifestpath)]=sha(manifestpath);m={x['symbol']:x for x in rd(manifestpath)}
Q=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');kp=Q/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet';rp=kp.with_name('RIGHT3.parquet');pp=Q/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'
k=pq(kp,source[str(kp)],columns=ids);right=pq(rp,source[str(rp)],columns=ids)
pvr=pq(pp,source[str(pp)],columns=['sid','day','state']);pvr=pvr[pvr.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=ids);k=k&pvr.ge(0)
sec={x['day']:x for x in rd(B/'SECTOR_DAILY.json') if x['sector51']=='自动化与机器人'}
dates=[d for d in sorted(sec) if '2024-12-03'<=d<='2024-12-10']
market={x['close_day']:x for x in rd(O/'DAILY_EVIDENCE.json') if x['cohort']=='BIRTH_PRICE_KNOWN'}
life=[];final=[]
for ticket in ten:
 sid=ticket['sid'];mm=m[sid];hs={**mm['source_sha256'],**mm['output_sha256']};path=next(p for p in mm['source_sha256'] if p.endswith('/signal.parquet'))
 raw=pq(path,hs[path]).loc['2024-12-03':'2024-12-10'];facts=pq(mm['refs']['facts'],hs[mm['refs']['facts']]).loc['2024-12-03':'2024-12-10']
 origin=lin(raw.iloc[0]);factor=raw.iloc[0].adjustment_factor;floor=None;cancel=None;blocked=None;first_unknown=None
 for ds in dates:
  dt=pd.Timestamp(ds);r=raw.loc[dt] if dt in raw.index else pd.Series(dtype=object);f=facts.loc[dt] if dt in facts.index else pd.Series(dtype=object)
  source_known=lin(r) is not None;quote=valid(r);fac=r.get('adjustment_factor');fac_known=finite(fac) and fac>0
  changed=source_known and origin is not None and lin(r)!=origin
  factor_changed=fac_known and finite(factor) and abs(float(fac)/float(factor)-1)>1e-11
  # No unknown action bridge is silently admitted; present branch would stop for review.
  if changed and cancel is None:cancel=(ds,'SOURCE_CHANGED')
  if factor_changed and blocked is None:blocked=(ds,'FACTOR_CHANGED_NOT_REVIEWED_IN_THIS_APPENDIX')
  state_unknown=not source_known or origin is None or not quote or not fac_known
  if ds>'2024-12-03':
   op=r.get('raw_open');opok=not state_unknown and finite(op) and op>0
   if cancel is None and blocked is None and opok and floor is not None and float(op)*float(fac)<=floor:cancel=(ds,'OPEN_BELOW_RATCHETED_I')
   if not opok and first_unknown is None:first_unknown=(ds,'OPEN_QUOTE_OR_SOURCE_UNKNOWN')
   life.append(dict(round_id=ticket['round_id'],sid=sid,name=ticket['name'],day=ds,phase='OPEN',cancel_day=cancel[0] if cancel else None,cancel_reason=cancel[1] if cancel else None,blocked=blocked,quote_known=opok,source_changed=changed,factor_changed=factor_changed,I_floor=floor))
  it=tri(f.get('i_target'));ss=-1 if dt not in k.index or bt(k.at[dt,sid])!=1 else bt(right.at[dt,sid]);sector=sec[ds]['state']
  reasons=[reason for v,reason in [(it,'I_FALSE'),(ss,'STOCK_FALSE'),(sector,'SECTOR_FALSE')] if v==0]
  if cancel is None and reasons:cancel=(ds,'+'.join(reasons))
  il=f.get('i_floor');cl=r.get('raw_close');closeok=not state_unknown and finite(cl) and cl>0 and finite(il) and il>0
  if cancel is None and blocked is None and closeok:
   floor=max(floor or 0.,float(il))
   if float(cl)*float(fac)<=floor:cancel=(ds,'CLOSE_BELOW_RATCHETED_I')
  if (not closeok or -1 in [it,ss,sector]) and first_unknown is None:first_unknown=(ds,'CLOSE_OR_ORIGINAL_STATE_UNKNOWN')
  phase='MATURE' if sector==1 and sec[ds]['M']==1 and sec[ds]['E']>0 else 'RESIDUAL' if sector==1 and sec[ds]['M']==0 else 'PAUSED'
  now_unknown=not closeok or -1 in [it,ss,sector] or sec[ds]['M']==-1
  status='CANCELLED' if cancel else 'BLOCKED_UNVERIFIED_BRIDGE' if blocked else 'UNKNOWN_PAUSED' if now_unknown else 'ORIGINAL_CHECKS_PASS'
  life.append(dict(round_id=ticket['round_id'],sid=sid,name=ticket['name'],day=ds,phase='CLOSE',I_state=it,stock_state=ss,sector_state=sector,M=sec[ds]['M'],current_allocation_phase=phase,G=market[ds]['G'],cancel_day=cancel[0] if cancel else None,cancel_reason=cancel[1] if cancel else None,blocked=blocked,quote_known=closeok,source_changed=changed,factor_changed=factor_changed,I_floor=floor,original_status=status))
  if fac_known:factor=fac
 final.append(dict(round_id=ticket['round_id'],sid=sid,name=ticket['name'],original_signal_day='2024-12-03',hypothetical_never_filled=True,industry_G_recovery_CLOSE='2024-12-10',industry_next_OPEN='2024-12-11',
  cancel_day=cancel[0] if cancel else None,cancel_reason=cancel[1] if cancel else None,blocked=blocked,first_unknown=first_unknown,
  original_checks_at_recovery=life[-1]['original_status'],current_phase_at_recovery=life[-1]['current_allocation_phase'],
  eligible_for_industry_plus_original_price_state_reexamination=life[-1]['original_status']=='ORIGINAL_CHECKS_PASS' and life[-1]['current_allocation_phase']=='MATURE',
  next_OPEN_economics_cash_capacity_and_event_not_verified=True))
assert not any(x['source_changed'] or x['factor_changed'] for x in life)
save('WAIT_TICKET_LIFECYCLE',life);save('WAIT_TICKET_AT_RECOVERY',final);save('WAIT_SOURCE_HASHES',hashes)
lines=['# 机器人原10张未成交票：到行业G恢复时的存续核查','',
'这是把原10张票视为尚未成交时，对原signal=12/3至12/10 CLOSE的原I/stock/sector、每日OPEN保护、只上调I线、来源/因子连续性作只读核查。没有借用原已持仓账户后来的确认。原已知false/保护破坏为吸收取消；UNKNOWN暂停，不把恢复当新票。','',
'所有10张票本段均未见来源或调整因子改变。若出现因子变动，本附录会标未核桥接并停止资格判断，不自行放行。没有声称复建通用跨缺口公司行动链。','',
'| 股票 | 首次原取消日 / 原因 | 12/10原票状态 | 当日phase | 行业+原价线状态可重审 |',
'|---|---|---|---|---|']
for x in final:lines.append(f"| {x['name']} / {x['sid']} | {x['cancel_day'] or '无'} / {x['cancel_reason'] or '无'} | {x['original_checks_at_recovery']} | {x['current_phase_at_recovery']} | {x['eligible_for_industry_plus_original_price_state_reexamination']} |")
lines+=['',
'“可重审”仍不是12/11可买。没有核12/11 OPEN成交约束、dated lot、容量、成本、事件剩余额度、资金竞争或候选账户。若采用另有入场CP门槛的基准，也没有在此叠加它。已经原false取消的票不随12/10行业G恢复复活；需要之后新的A/B新机会。',
'',
'期间行业12/6为UNKNOWN、12/9的M为UNKNOWN，按暂停记录。任何该期间同时明确出现I或stock false的票仍按原false取消，不以UNKNOWN遮盖已知失败。',
'']
(O/'WAIT_READOUT.md').write_text('\n'.join(lines))
# Append a link-like local section without altering the prior market rows or main 57-day artifacts.
p=O/'READOUT.md';s=p.read_text();s+='\n\n## 8. 原票存续补充\n\n已补 WAIT_READOUT.md、WAIT_TICKET_AT_RECOVERY 和逐日 WAIT_TICKET_LIFECYCLE。行业12/10恢复不等于这10票全部仍可重审；以该附表的原吸收取消结果为准，未核次OPEN完整经济/资金资格。\n';p.write_text(s)
old=rd(O/'ORIGINAL_OUTPUT_SEAL.json');assert all(sha(OLD/n)==h for n,h in old.items()) and old==rd(OLD/'OUTPUT_SEAL.json')
save('OUTPUT_SEAL',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'})
print(json.dumps(final,ensure_ascii=False))
