"""Two original layers: CP-source annotation, fixed k arithmetic, two B identities."""
from pathlib import Path
from decimal import Decimal as D, getcontext
import gzip, hashlib, json, math
import pandas as pd
getcontext().prec=55
O=Path(__file__).resolve().parent; P=O.parent; Q=P.parent
audit_rows=json.loads((P/'peak_scan/DAILY_LAYER_SCAN.json').read_text())
first_rows=json.loads((P/'peak_scan/FIRST_HITS_BY_LAYER_K.json').read_text())
b_rows=json.loads((P/'penetration/ACTUAL_FIRST_CP_TRIGGER_POINTS.json').read_text())
refs=json.loads((P/'peak_scan/SOURCE_AND_VALIDATION.json').read_text())['source_refs']
bp=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz'
dp=bp.parent/'daily.jsonl.gz'
with gzip.open(bp,'rt') as f:book=json.load(f)
targets={'601601.SH':1904,'002583.SZ':2017}; ids=set(targets.values())
diary=[]
with gzip.open(dp,'rt') as f:
    for line in f:
        d=json.loads(line);diary.append({'at':d['at'],'layers':{h['id']:h for h in d['layers'] if h['id'] in ids}})
buys={t['layer']:t for t in book['trades'] if t['side']=='buy' and t['layer'] in ids}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest(); sources={str(bp):sha(bp),str(dp):sha(dp)}
checks=[]
for sid,lid in targets.items():
    rr=refs[sid]; f=pd.read_parquet(rr['facts']); cp=pd.read_parquet(rr['CP1']); sig=pd.read_parquet(rr['original_signal']).reindex(f.index)
    canon={r['confirmed_day']:r for r in json.loads(Path(rr['canonical_2024_receipts']).read_text())}
    for p in rr.values():sources[str(p)]=sha(p)
    def cp_tag(day):
        r=canon[day]; z=cp.loc[pd.Timestamp(day)]
        assert bool(z.receipt) and float(z.candidate)==r['original_candidate'] and float(z.scale)==r['original_scale']
        assert not r['trace_unknown']
        c=float(f.loc[pd.Timestamp(day),'close'])
        assert math.isclose(c*math.exp(-math.sqrt(21)*float(z.scale)),float(z.candidate),rel_tol=1e-12)
        return {'kind':'CP','day':day,'scale':float(z.scale),'receipt':r['receipt_id'],'frozen_at':r['scale_frozen_at']}
    buy=buys[lid]; sd=buy['signal_at'][:10]; z=cp.loc[pd.Timestamp(sd)]; fi=f.loc[pd.Timestamp(sd)]
    ih=D(str(fi.i_floor)); ch=D(str(z.candidate)); level=max(ih,ch)
    assert level==D(buy['floor'])
    origin=cp_tag(sd) if ch>ih else {'kind':'I','day':sd}
    peak=None; peakday=None; first={k:None for k in [2,3,4]}; checked=0; trigger_detail=None
    first_native=min(a['at'] for a in book['audit'] if a['kind']=='pilot_layer_exit' and a.get('sid')==sid and lid in a.get('layers',[]))
    for j,d in enumerate(diary):
        h=d['layers'].get(lid)
        if h is None:continue
        day=d['at'][:10]; dt=pd.Timestamp(day); row=f.loc[dt]; raw=sig.loc[dt]
        prev=diary[j-1]['layers'].get(lid) if j else None
        old=D(prev['floor']) if prev else D(buy['floor']); assert old==level
        a=next(x for x in audit_rows if x['sid']==sid and x['layer']==lid and x['day']==day)
        valid=bool(raw.price_eligible and raw.observed_bar and not raw.source_invalid and not raw.synthetic_event_bar)
        assert valid and int(row.segment_id)==int(f.loc[pd.Timestamp(buy['at'][:10]),'segment_id'])
        C=float(row.close); eligible=peak is not None and origin['kind']=='CP'
        assert a['eligible']==eligible
        if origin['kind']=='CP':
            assert a['old_floor_source']['receipt_id']==origin['receipt'] and a['s_activeCP']==origin['scale']
        if peak is not None:
            assert a['H_prior_adjusted']==peak and a['H_prior_day']==peakday
        for k in [2,3,4]:
            hit=math.log(peak/C)>k*origin['scale'] if eligible else None
            assert hit==a['k_hits'][str(k)]
            if hit and first[k] is None:first[k]=day
        if day==first_native[:10]:
            assert prev is not None
            pd0=diary[j-1]['at'][:10]; pr=f.loc[pd.Timestamp(pd0)]
            assert D(str(pr.factor))==D(str(row.factor)) and prev['qty']==h['qty']
            Cprev=D(str(pr.raw_close)); Cnow=D(str(row.raw_close)); Hraw=old/D(str(row.factor))
            parts={'delta_C':Cprev-Cnow,'previous_C_to_old_floor':Cprev-Hraw,'old_floor_minus_current_C':Hraw-Cnow}
            assert parts['delta_C']==parts['previous_C_to_old_floor']+parts['old_floor_minus_current_C']
            br=next(x for x in b_rows if x['sid']==sid and x['layer']==lid)
            for name,v in parts.items():assert abs(v-D(br[name]))<D('1e-45')
            assert origin['kind']=='CP' and origin['receipt']==br['unique_CP_receipt_id']
            assert origin['scale']==br['unique_CP_frozen_scale'] and origin['frozen_at']==br['scale_frozen_at']
            trigger_detail={'day':day,'C_prev_raw':str(Cprev),'C_raw':str(Cnow),'old_floor_raw':str(Hraw),
                            **{k:str(v) for k,v in parts.items()},'controller':origin.copy(),
                            'current_s63_not_used':float(cp.loc[dt,'s']),
                            'next_scale_at_receipt_not_used':float(cp.loc[pd.Timestamp(origin['day']),'next_scale'])}
        # Existing after-CLOSE saved line is the oracle; only annotate strict increases.
        after=D(h['floor']); assert after>=old
        if after>old:
            value=old; new=origin
            iv=D(str(row.i_floor))
            if iv>value:value=iv;new={'kind':'I','day':day}
            cz=cp.loc[dt]
            if bool(cz.receipt) and D(str(cz.candidate))>value:value=D(str(cz.candidate));new=cp_tag(day)
            assert value==after;origin=new
        level=after
        if peak is None or C>peak:peak=C;peakday=day
        checked+=1
    for k,day in first.items():
        claim=next(x for x in first_rows if x['sid']==sid and x['layer']==lid and x['k']==k)
        assert claim['first_trigger']==day
    checks.append({'sid':sid,'layer':lid,'original_held_CLOSEs_checked':checked,'first_A_by_k':first,
                   'original_first_request':first_native,'B_at_original_request':trigger_detail})
for n in ['peak_scan/DAILY_LAYER_SCAN.json','peak_scan/FIRST_HITS_BY_LAYER_K.json','penetration/ACTUAL_FIRST_CP_TRIGGER_POINTS.json']:
    sources[str(P/n)]=sha(P/n)
sources[str(Path(__file__))]=sha(__file__)
out={'status':'PASS_TWO_ORIGINAL_LAYERS_CP_SCALE_PEAK_AND_PENETRATION_WITH_LIMITS','checks':checks,'source_sha256':sources,
     'scope':'Only TaiBao1904 and Hai2017 all original held CLOSEs; k exactly2/3/4, two actual first CP-request B points. No other layers independently recalculated.',
     'limits':['Pure annotation against recorded old/after floors, not an account or alternative protection path.','No CP model, volatility arrays or future next_scale recalculation.','After a candidate earlier first action, later original rows are not its continued holdings.','No candidate price, sale cash, PNL or intraday old-line fill assumed.'],
     'new_accounts':0,'new_backtests':0,'new_strategy_paths':0,'new_parameter_searches':0}
(O/'TWO_LAYER_A_B_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':out['status'],'checks':checks},ensure_ascii=False))
