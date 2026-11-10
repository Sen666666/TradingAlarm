"""Algebra on saved JSON scalars only; no feature/model/account imports or calls."""
from pathlib import Path
from decimal import Decimal as D, localcontext
import json, hashlib, math

O=Path(__file__).resolve().parent
ROOT=O.parents[1]
CFG=[('000620.SZ',ROOT/'native_algorithm_read_v1/yingxin_reentry_evidence/CONTINUOUS_FOUR_CLOSE_RAWDICTS.json',['2022-01-21','2022-01-24']),
     ('002583.SZ',ROOT/'native_algorithm_read_v1/daily_hytera/ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json',['2024-10-18'])]
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def cp(r):return r['original_CP_cache']if 'original_CP_cache'in r else r['CP1']
def facts(r):return r['original_stock_facts']if 'original_stock_facts'in r else r['facts']
def dec(x):
    if not isinstance(x,(D,int)):raise TypeError('Missing/non-numeric saved scalar; do not fill: '+repr(x))
    return D(x)

SOURCES={};out=[];inputs=[]
with localcontext()as ctx:
    ctx.prec=50
    for sid,p,days in CFG:
        raw=p.read_bytes();SOURCES[str(p)]=hashlib.sha256(raw).hexdigest();data=json.loads(raw,parse_float=D)
        rows=data['rows']if isinstance(data,dict)else data
        assert [r['day']for r in rows]==sorted({r['day']for r in rows})
        for day in days:
            j=next(i for i,r in enumerate(rows)if r['day']==day)
            if j==0:raise ValueError('Previous observation not saved')
            r,previous=rows[j],rows[j-1];c,pc=cp(r),cp(previous);f,pf=facts(r),facts(previous)
            scale=dec(c['scale']);close=dec(f['close']);factor=dec(f['factor']);rawclose=dec(f['raw_close'])
            delta=dec(c['delta_frontier']);disp=dec(c['displacement']);credit=dec(c['credit']);m=dec(c['m'])
            threshold=D(5).sqrt()*scale;discount=(-D(21).sqrt()*scale).exp()
            frontier_difference=dec(c['frontier'])-dec(pc['frontier'])
            displacement_difference=dec(c['frontier'])-dec(c['anchor'])
            bridge=dec(pc['next_credit'])+delta*m
            candidate=close*discount;candidate_saved=dec(c['candidate']);rawcandidate=candidate_saved/factor
            fb={k:float(v)for k,v in c.items()if isinstance(v,(D,int))and not isinstance(v,bool)}
            prevb={k:float(v)for k,v in pc.items()if isinstance(v,(D,int))and not isinstance(v,bool)}
            threshold_b=math.sqrt(5)*float(scale);discount_b=math.exp(-math.sqrt(21)*float(scale))
            exactbridge=dict(previous_next_anchor_equals_current_anchor=pc['next_anchor']==c['anchor'],previous_next_scale_equals_current_scale=pc['next_scale']==c['scale'],previous_next_phase_equals_current_phase=pc['next_phase']==c['phase'],previous_and_current_source_segment_equal=pf['segment_id']==f['segment_id'])
            assert all(exactbridge.values())
            binary64=dict(threshold=threshold_b,displacement_margin=float(disp)-threshold_b,credit_margin=float(credit)-threshold_b,discount=discount_b,candidate=float(close)*discount_b,
              delta_frontier_saved_minus_frontier_difference=float(delta)-(fb['frontier']-prevb['frontier']),
              displacement_saved_minus_frontier_anchor=float(disp)-(fb['frontier']-fb['anchor']),
              credit_saved_minus_fsum_bridge=float(credit)-math.fsum([prevb['next_credit'],float(delta)*float(m)]),
              candidate_saved_minus_close_times_discount=float(candidate_saved)-float(close)*discount_b,
              candidate_raw=float(candidate_saved)/float(factor))
            row=dict(sid=sid,day=day,previous_saved_observation=previous['day'],saved_receipt=c['receipt'],saved_reset_reason=c['reset_reason'],close_adjusted=close,raw_close=rawclose,factor=factor,
              saved_delta_frontier=delta,saved_displacement=disp,saved_credit=credit,saved_frozen_scale=scale,saved_current_z=c['z'],sqrt5_times_frozen_scale=threshold,
              displacement_trigger_margin=disp-threshold,credit_trigger_margin=credit-threshold,both_trigger_margins_positive=bool(disp>threshold and credit>threshold and delta>0),
              delta_from_saved_frontiers=frontier_difference,delta_saved_minus_decimal_frontier_difference=delta-frontier_difference,
              displacement_from_saved_frontier_anchor=displacement_difference,displacement_saved_minus_decimal_difference=disp-displacement_difference,
              saved_previous_next_credit=pc['next_credit'],saved_current_m=m,credit_new_increment=delta*m,credit_bridge_from_previous_next_credit=bridge,credit_saved_minus_decimal_bridge=credit-bridge,
              m_from_saved_u_v=D(1)+D('.5')*abs(dec(c['u']))*dec(c['v']),m_saved_minus_decimal_u_v=m-(D(1)+D('.5')*abs(dec(c['u']))*dec(c['v'])),
              exact_saved_next_state_bridge=exactbridge,exp_minus_sqrt21_frozen_scale=discount,discount_percent_from_close=(D(1)-discount)*100,
              candidate_adjusted_recomputed=candidate,candidate_adjusted_saved=candidate_saved,candidate_saved_minus_decimal_formula=candidate_saved-candidate,
              candidate_raw_from_saved_candidate_factor=rawcandidate,candidate_raw_from_raw_close_discount=rawclose*discount,raw_conversion_difference=rawcandidate-rawclose*discount,
              close_adjusted_minus_raw_close_times_factor=close-rawclose*factor,binary64_same_scalar_operations=binary64)
            out.append(row);inputs.append(dict(sid=sid,day=day,previous_day=previous['day'],previous_CP=pc,current_CP=c,previous_facts=pf,current_facts=f))
    save('THREE_CLOSE_ALGEBRA.json',out);save('SELECTED_SAVED_INPUTS.json',inputs)
    save('SOURCE_SHA256.json',SOURCES);save('SCOPE.json',dict(status='SAVED_SCALAR_ALGEBRA_ONLY',source_JSONs=2,target_observations=3,missing_values_filled=0,new_parquet_reads=0,model_or_features_calls=0,new_accounts=0,decimal_precision=50,binary64_replay='Only sqrt/exp/subtract/multiply/fsum on saved scalars, never calculate/features.',rounding='Decimal treats serialized decimal scalars literally; small decimal residuals are reported rather than silently zeroed. Binary64 scalar residuals are separate.'))
    for r in out:print(r['sid'],r['day'],'threshold',r['sqrt5_times_frozen_scale'],'margins',r['displacement_trigger_margin'],r['credit_trigger_margin'],'bridge64_residual',r['binary64_same_scalar_operations']['credit_saved_minus_fsum_bridge'])
    files={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(O.iterdir())if p.is_file()and p.name!='OUTPUT_SHA256.json'};save('OUTPUT_SHA256.json',files)
