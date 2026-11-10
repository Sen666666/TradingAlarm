from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib
import pandas as pd
from html import escape
O=Path(__file__).resolve().parent
T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
sources={}
def bind(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
bind(__file__);bind(O/'ACTUAL_FILL_CROSS_PROTOCOL.txt')
f=pd.read_parquet(bind(O/'INDUSTRY_DAILY_BEHAVIOR.parquet')).set_index(['day','sector'])
long=read(T/'loss_correction/entry_risk_commitment_review/2022_2024_ENTRIES.json')
strong=read(T/'loss_correction/entry_risk_commitment_review/strong_ENTRIES.json')
sets={'2022_entries_lifecycle_to2024end':[x for x in long if x['opened'].startswith('2022')],
      '2023_entries_lifecycle_to2024end':[x for x in long if x['opened'].startswith('2023')],
      'POST924_strict303_newfills_to2024end':[x for x in long if '2024-10-09'<=x['opened'][:10]<='2024-12-31'],
      '2026H1_semiconductor_toJun30':[x for x in strong if x['industry']=='半导体' and '2026-01-01'<=x['opened'][:10]<='2026-06-30']}
assert len(sets['POST924_strict303_newfills_to2024end'])==303
allrows=[];sums={}
for case,ls in sets.items():
 groups=defaultdict(list)
 for x in ls:
  key=(x['signal_day'],x['sector']);assert key in f.index
  r=f.loc[key];assert isinstance(r,pd.Series)
  group=('BREAK_promoted_permit' if r.origin=='break_started' else 'REPAIR_promoted_permit') if r.promoted and r.original_permit else 'not_promoted_and_permitted'
  z={k:x[k] for k in ['layer','sid','industry','role','action','signal_day','opened','closed','qty','cost','net']}
  z.update(case=case,evidence_group=group,context_start=r.context_start,origin=r.origin,
    first_promotion=r.first_promotion,original_permit=bool(r.original_permit),literal_tier_event=bool(r.literal_tier_event))
  allrows.append(z);groups[group].append(z)
 sums[case]={}
 for g,rs in groups.items():
  sums[case][g]=dict(layers=len(rs),buy_cost=sum((D(x['cost']) for x in rs),D(0)),
    actual_original_net=sum((D(x['net']) for x in rs),D(0)),closed_negative_layers=sum(not x['qty'] and D(x['net'])<0 for x in rs),
    closed_negative_net=sum((D(x['net']) for x in rs if not x['qty'] and D(x['net'])<0),D(0)),
    original_actions=dict(Counter(x['action'] for x in rs)),literal_same_day_layers=sum(x['literal_tier_event'] for x in rs))
save('ACTUAL_FILL_EVIDENCE_CROSS.json',allrows);save('ACTUAL_FILL_EVIDENCE_SUMMARY.json',sums)

w=pd.DataFrame(read(O/'SEMICONDUCTOR_WEEKLY_CHAIN.json'))
native=f.reset_index();s=native[native.industry.eq('半导体')&native.case.eq('2026H1')].copy()
dates=pd.to_datetime(s.day)
trial=s[s.original_events.map(lambda es:'break_started' in es)]
prom=s[s.first_promotion.eq(s.day)]
panels=[('Industry index, first H1 close = 100',[(dates,s.price/s.price.iloc[0]*100,'#334155','Index')]),
 ('Direction-amount breadth (%)',[(dates,s.breadth*100,'#0f766e','Breadth'),(dates,s.initial_breadth*100,'#7c3aed','Context-start breadth')]),
 ('Actual semiconductor weight (% NAV)',[]),('Weekly actual buy cost (CNY 1,000)',[]),('Actual cumulative H1 contribution (CNY 1,000)',[]),
 ('Weekly planned fresh-mobile receipts / actual all-role filled layers',[])]
for pol,col in [('PVR_BASELINE','#2563eb'),('PVR_NO60','#dc2626')]:
 x=w[w.policy.eq(pol)];xd=pd.to_datetime(x.last_day)
 panels[2][1].append((xd,x.last_industry_weight_pct,col,pol));panels[3][1].append((xd,x.actual_buy_cost/1000,col,pol));panels[4][1].append((xd,x.cumulative_H1_wealth/1000,col,pol))
 panels[5][1].append((xd,x.planned_receipts,col,pol+' planned mobile'));panels[5][1].append((xd,x.actual_all_role_filled_layers,col,pol+' filled all-role'))
lo=dates.min();span=(dates.max()-lo).days
px=lambda d:100+1400*(pd.Timestamp(d)-lo).days/span
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1690" viewBox="0 0 1600 1690">',
 '<rect width="1600" height="1690" fill="#f8fafc"/>',
 '<g font-family="Arial,sans-serif" fill="#0f172a">',
 '<text x="60" y="42" font-size="25" font-weight="700">2026 H1 semiconductor: evidence, funding and actual participation</text>',
 '<text x="60" y="72" font-size="16">Saved PVR / No60 accounts. New two-layer evidence is a diagnostic, not a backtest.</text>']
for k,(title,series) in enumerate(panels):
 top=125+k*250;vals=[float(v) for _,vs,_,_ in series for v in vs if pd.notna(v)]
 mn=min(vals);mx=max(vals);pad=(mx-mn)*.12 or 1;mn-=pad;mx+=pad
 py=lambda v:top+185-175*(float(v)-mn)/(mx-mn)
 svg.append(f'<text x="60" y="{top-10}" font-size="18" font-weight="700">{escape(title)}</text>')
 for q in range(5):
  v=mn+(mx-mn)*q/4;y=py(v)
  svg.append(f'<path d="M100 {y:.2f}H1500" stroke="#dbe3ec"/><text x="88" y="{y+5:.2f}" text-anchor="end" font-size="13">{v:.1f}</text>')
 for j,(ds,vs,col,label) in enumerate(series):
  pieces=[];part=[]
  for d,v in zip(ds,vs):
   if pd.isna(v):
    if part:pieces.append(part);part=[]
   else:part.append(f'{px(d):.2f},{py(v):.2f}')
  if part:pieces.append(part)
  for pts in pieces:
   dash=' stroke-dasharray="5 4"' if 'filled all-role' in label else ''
   svg.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2.5"{dash}/>')
  svg.append(f'<text x="{110+(j%2)*650}" y="{top+220+(j//2)*17}" font-size="14" fill="{col}">{escape(label)}</text>')
 if k==0:
  for _,r in trial.iterrows():svg.append(f'<circle cx="{px(r.day):.2f}" cy="{py(r.price/s.price.iloc[0]*100):.2f}" r="6" fill="#f59e0b"/>')
  for _,r in prom.iterrows():svg.append(f'<circle cx="{px(r.day):.2f}" cy="{py(r.price/s.price.iloc[0]*100):.2f}" r="5" fill="#7c3aed"/>')
  svg.append(f'<text x="770" y="{top+220}" font-size="14" fill="#7c3aed">Purple: promotion; amber: original BREAK</text>')
 for month in range(1,7):
  d=pd.Timestamp(2026,month,5);xx=px(d)
  svg.append(f'<text x="{xx:.2f}" y="{top+202}" font-size="13" text-anchor="middle">{d.strftime("%b")}</text>')
svg.append('<text x="60" y="1660" font-size="14">Fixed present-day universe / classification. Daily-bar execution proxies. Contributions include open inventory valuation.</text></g></svg>')
(O/'SEMICONDUCTOR_WEEKLY_CHAIN.svg').write_text('\n'.join(svg))
save('SUPPLEMENT_SOURCE_SHA256.json',sources)
print(json.dumps(sums,ensure_ascii=False,indent=2,default=str))
