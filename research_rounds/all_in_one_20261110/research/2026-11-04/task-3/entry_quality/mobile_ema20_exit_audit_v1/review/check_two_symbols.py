"""Isolated original-source EMA and clock checks for two fixed symbols only."""
from pathlib import Path
from datetime import datetime
import gzip, hashlib, json, math
import pandas as pd

O=Path(__file__).resolve().parent; P=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
timeline=json.loads((P/'candidate_timeline/DAILY_TIMELINE.json').read_text())
comparisons=json.loads((P/'candidate_timeline/TARGET_LAYER_REQUEST_COMPARISON.json').read_text())
manifest_path=W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
records={r['symbol']:r for r in json.loads(manifest_path.read_text())}
rules_path=RR/'pvr-act-comparison-20261027/execution-rules-v2.json'
rules=json.loads(rules_path.read_text())
cal=[x[:10] for x in rules['calendars']['A']]; ci={d:i for i,d in enumerate(cal)}
sources={}; sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):sources[str(p)]=sha(p)
bind(manifest_path);bind(rules_path)
alpha=2.0/21.0; selected={'002583.SZ':[2017,2039],'002670.SZ':[2225]}
result=[]
for sid,lids in selected.items():
    rec=records[sid]; fp=Path(rec['refs']['facts'])
    sp=Path(next(p for p in rec['source_sha256'] if p.endswith('/signal.parquet')))
    bind(fp);bind(sp)
    assert sha(fp)==rec['output_sha256'][str(fp)] and sha(sp)==rec['source_sha256'][str(sp)]
    f=pd.read_parquet(fp); sig=pd.read_parquet(sp).reindex(f.index)
    values={}; prev_seg=object(); y=None; n=0; run=-1
    for day,row in f.iterrows():
        seg=row.segment_id
        if seg!=prev_seg:y=None;n=0;run+=1
        prev_seg=seg; raw=sig.loc[day]; c=float(row.close)
        valid=(raw.price_eligible==True and raw.observed_bar==True and raw.source_invalid==False
               and raw.synthetic_event_bar==False and math.isfinite(c) and c>0
               and raw.segment_id==seg and math.isfinite(float(raw.close))
               and abs(float(raw.close)-c)<=1e-10+1e-10*abs(c))
        if valid:
            y=c if y is None else (1-alpha)*y+alpha*c;n+=1
        values[str(day.date())]={'C':c,'E':y if valid and n>=20 else None,'valid':bool(valid),'run':run,'n':n,'factor':float(row.factor)}
    maxdiff=0.0; checked=[]
    for r in timeline:
        if r['sid']!=sid:continue
        d=r['day']; v=values.get(d); j=ci[d]
        six=[values.get(z) for z in cal[j-5:j+1]] if j>=5 else []
        a=values.get(cal[j-5]) if j>=5 else None
        ready=bool(len(six)==6 and all(x and x['valid'] for x in six)
                   and len({x['run'] for x in six})==1 and v['E'] is not None and a['E'] is not None)
        assert r['slope5_ready']==ready,(sid,d,'ready')
        if v and v['E'] is not None:
            diff=abs(v['E']-r['EMA20_adj']);maxdiff=max(maxdiff,diff)
            assert diff<=1e-10,(sid,d,diff)
        if ready:
            slope=(v['E']-a['E'])/5.0
            assert abs(slope-r['slope5_adj'])<=1e-10
            assert r['tminus5_market_day']==cal[j-5]
            expected=v['C']<v['E'] and slope<0
            assert r['joint_condition_state']==expected,(sid,d,'joint')
            assert abs(r['EMA20_raw']*v['factor']-r['EMA20_adj'])<1e-9
        else: assert r['joint_condition_state'] is None
        checked.append(d)
    result.append({'sid':sid,'timeline_days_checked':len(checked),'first_day':min(checked),'last_day':max(checked),'maximum_EMA_absolute_difference':maxdiff})

# Original receipt/request identities only; no account execution or new valuation.
bp=P.parents[0]/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz'
dp=bp.parent/'daily.jsonl.gz';bind(bp);bind(dp)
with gzip.open(bp,'rt') as stream:book=json.load(stream)
layer_by_id={x['id']:x for x in book['layers']}
target_rows=[r for r in comparisons if r['sid'] in selected and r.get('layer') in selected[r['sid']]]
days_needed=set(); clock_rows=[]
for r in target_rows:
    lid=r['layer']; native=layer_by_id[lid]
    reqs=[(i,a) for i,a in enumerate(book['audit']) if a['kind']=='pilot_layer_exit' and a.get('sid')==r['sid'] and lid in a['layers']]
    first=min(a['at'] for _,a in reqs)
    assert first==r['original_first_request']
    assert native['closed']==r['original_fill_closed']
    rows=[z for z in timeline if z['sid']==r['sid'] and lid in z['original_MOBILE_held_layers']]
    hits=[z['day'] for z in rows if z['joint_condition_state'] is True]
    assert not hits and r['first_joint_state_while_original_held_including_pending'] is None
    assert r['first_additional_request_before_original'] is None
    d=first[:10];days_needed.update([d,cal[ci[d]-1]])
    clock_rows.append({'sid':r['sid'],'layer':lid,'original_first_request':first,'original_closed':native['closed'],'original_request_audit_indices':[i for i,a in reqs if a['at']==first],'joint_hits_while_original_held':hits})
daily={}
with gzip.open(dp,'rt') as stream:
    for line in stream:
        d=json.loads(line)
        if d['at'][:10] in days_needed:daily[d['at'][:10]]=d
for r in clock_rows:
    sid=r['sid'];lid=r['layer'];d=r['original_first_request'][:10];old=next(x for x in daily[cal[ci[d]-1]]['layers'] if x['id']==lid)
    t=next(z for z in timeline if z['sid']==sid and z['day']==d)
    h=next(x for x in t['original_layer_state'] if x['layer']==lid)
    assert str(old['floor'])==h['old_floor_used_at_original_CLOSE_adj']
    at_events=[a for a in book['audit'] if a['kind']=='pilot_layer_exit' and a['at']==r['original_first_request'] and lid in a.get('layers',[])]
    if any(a['reason']=='CP1_add_protection' for a in at_events):
        assert t['adjusted_C']<=float(old['floor'])
    r.update(original_old_CP_floor=old['floor'],C_at_request=t['adjusted_C'],EMA_at_request=t['EMA20_adj'],slope5_at_request=t['slope5_adj'])
for n in ['PROTOCOL.json','DAILY_TIMELINE.json','TARGET_LAYER_REQUEST_COMPARISON.json']:
    bind(P/'candidate_timeline'/n)
bind(__file__)
out={'status':'PASS_TWO_SYMBOL_ISOLATED_EMA_AND_ORIGINAL_CLOCK_WITH_LIMITS','symbols':result,'original_clocks':clock_rows,'source_sha256':sources,
     'scope':'Only002670 and002583 indicators/full-history seeds, visible102days each, and three selected original MOBILE layer request/close/old-line identities. No7-symbol independent numeric claim.',
     'limits':['No new order/fill or counterfactual cash simulation.','Actual source prefix inspected; no synthetic parameter or EMA-span trials.','Original diary HLV execution proxy remains; next OPEN is scheduling only.','Stage wealth/lifetime PNL fields are kept distinct; monetary bridges not independently recomputed here.'],
     'new_accounts':0,'new_backtests':0,'new_strategy_changes':0}
(O/'TWO_SYMBOL_INDICATOR_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':out['status'],'symbols':result,'clocks':clock_rows},ensure_ascii=False))
