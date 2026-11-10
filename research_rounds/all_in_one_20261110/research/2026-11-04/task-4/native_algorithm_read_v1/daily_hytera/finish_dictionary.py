"""Lightweight completion from own saved43 rows only. No model or frames read."""
from pathlib import Path
import csv
import hashlib
import json
import math
import time

O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((O/n).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def cell(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'))if x else 'NONE'
def light(l):return {k:l.get(k,'NOT_SAVED')for k in ['id','kind','qty','floor','last_core_line','pool','role','stock_structure','opened','signal_at','epoch','reason']}

start=time.monotonic();raw=read('ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json');by={x['day']:x for x in raw}
rows=read('HYTERA_DAILY_NATIVE_ROWS.json');refs=read('SOURCE_REFERENCE_MAP.json')
oldcsv=O/'HYTERA_DAILY_NATIVE.csv';oldjson=O/'HYTERA_DAILY_NATIVE_ROWS.json'
csvsha=sha(oldcsv);jsonsha=sha(oldjson)
(O/'HYTERA_DAILY_NATIVE.v1.csv').write_bytes(oldcsv.read_bytes())
(O/'HYTERA_DAILY_NATIVE_ROWS.v1.json').write_bytes(oldjson.read_bytes())
floor_known=0;floor_unknown=[];floor_mismatches=[]
layer_rows=[]
for r in rows:
    x=by[r['date']];prev=x['previous_CLOSE_stock_layers'];cur=x['current_CLOSE_stock_layers']
    cp=[l for l in cur if l['kind']=='core'];pid={l['id']:l for l in prev};cid={l['id']:l for l in cur}
    r['CORE_stored_layer_floor_a_by_id']=cell([{'layer':l['id'],'floor':l['floor']}for l in cp])
    r['CORE_actual_last_core_line_a_by_id']=cell([{'layer':l['id'],'last_core_line':l.get('last_core_line','NOT_SAVED')}for l in cp])
    r['CORE_current_I_reference_a']=x['facts']['i_floor']if cp else 'NONE'
    r['actual_layer_floors_previous_CLOSE']=cell([light(l)for l in prev])
    r['actual_layer_floors_current_CLOSE']=cell([light(l)for l in cur])
    if r['floor_before_after_saved_comparison']!='NONE':
        comp=json.loads(r['floor_before_after_saved_comparison'])
        for c in comp:
            lid=c['layer'];c['previous_CLOSE_last_core_line']=pid.get(lid,{}).get('last_core_line','NOT_SAVED')
            c['current_CLOSE_last_core_line']=cid[lid].get('last_core_line','NOT_SAVED')
        r['floor_before_after_saved_comparison']=cell(comp)
    a=x['facts']['e0_floor'];b=x['E0_states']['floor']
    if isinstance(a,(int,float))and isinstance(b,(int,float)):
        floor_known+=1
        if not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12):floor_mismatches.append({'day':r['date'],'facts_floor':a,'states_floor':b})
    else:floor_unknown.append({'day':r['date'],'facts_floor':a,'states_floor':b})
    for lid in sorted(set(pid)|set(cid)):
        p=pid.get(lid);c=cid.get(lid);l=c or p
        layer_rows.append({'date':r['date'],'layer':lid,'kind':l['kind'],
            'previous_CLOSE_qty':p['qty']if p else 0,'current_CLOSE_qty':c['qty']if c else 0,
            'previous_CLOSE_stored_floor_a':p['floor']if p else 'NONE_NEW_LAYER',
            'current_CLOSE_stored_floor_a':c['floor']if c else 'NONE_CLOSED',
            'previous_CLOSE_saved_last_core_line_a':p.get('last_core_line','NOT_SAVED')if p else 'NONE_NEW_LAYER',
            'current_CLOSE_saved_last_core_line_a':c.get('last_core_line','NOT_SAVED')if c else 'NONE_CLOSED',
            'current_facts_I_floor_a':x['facts']['i_floor'],
            'intra_CLOSE_preupdate_floor':'NOT_SAVED'})
assert not floor_mismatches
save('HYTERA_DAILY_NATIVE_ROWS.json',rows)
with oldcsv.open('w',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (O/'LAYER_FLOOR_TIMELINE.csv').open('w',newline='')as f:
    w=csv.DictWriter(f,fieldnames=list(layer_rows[0]));w.writeheader();w.writerows(layer_rows)
save('DAILY_TABLE_CORRECTION_RECEIPT.json',{'change':'Add saved CORE last_core_line/currentI alongside stored layer.floor; enrich layer lists with saved metadata. No I/CP/model recomputation.',
    'first_CSV_sha256':csvsha,'first_JSON_sha256':jsonsha,'retained_first_versions':['HYTERA_DAILY_NATIVE.v1.csv','HYTERA_DAILY_NATIVE_ROWS.v1.json'],
    'corrected_CSV_sha256':sha(oldcsv),'corrected_JSON_sha256':sha(oldjson),
    'E0_floor_crosscheck':{'known_pairs_equal':floor_known,'unknown_pairs':floor_unknown,'mismatches':floor_mismatches},
    'source_frames_read_by_this_step':0,'new_accounts':0,'seconds':time.monotonic()-start})

def dictionary_entry(k):
    d={'column':k,'value_policy':'Original saved value; no inferred permission or model recomputation.'}
    if k.startswith('E0_'):
        if k in ['E0_target','E0_floor_a','E0_ready']:d.update(source='actual_frames.facts',field={'E0_target':'e0_target','E0_floor_a':'e0_floor','E0_ready':'e0_ready'}[k],consumed_actual_facts_column=True)
        elif k=='E0_base_event':d.update(source='actual_frames.E0_events',field='event',consumed_actual_facts_column=False,note='Auxiliary native E0 event output, not inferred from target transition and not identical to entered.')
        else:d.update(source='actual_frames.E0_states',field={'E0_entered_native_state':'entered','E0_exited_native_state':'exited','E0_entry_kind':'entry_kind','E0_state_price_event':'price_event'}[k],consumed_actual_facts_column=False,note='Direct auxiliary original E0 states output. actualfacts did not export entered/event; existence here does not claim they were directly consumed by native I. Target and42 known floor pairs independently match actualfacts.')
    elif k.startswith('I_'):d.update(source='actual_frames.facts',field={'I_target':'i_target','I_floor_a':'i_floor','I_buy':'i_buy'}.get(k,'NOT_SAVED'),note='Actual No60 I exclusively from consumed facts. Entered/exited/exit_reason absent here: NOT_SAVED, never copied from legacy IX.')
    elif k.startswith('G1_'):d.update(source='actual_frames.IX_signal'if 'source_IX'in k else 'actual_frames.facts',note='Facts g_grade/g_ready/g_fresh_up/g_acute_down are actual consumed columns and match cached IX G1 fields on43 dates. up_reasons/phase are auxiliary old IX G1 context, not actual I exit semantics.')
    elif k.startswith('CP_'):d.update(source='actual_frames.CP1',field=k.removeprefix('CP_').replace('_native','').replace('_a',''),note='Stored CP output untouched. candidate is continuous-price coordinate; anchor/frontier/credit/scale retain original CP native/log coordinates and must not be compared directly to raw price. No CP calculation.')
    elif k.startswith('PVR_'):
        d.update(source='actual_long_PVR_scores'if k=='PVR_source_score'else'original rank-policy.jsonl.gz / decision.intents',note='Source score exists daily even without an intent. Original H1 key, PVR key and slots only when actual rank-policy row exists; otherwise NONE. rank-policy policy name from stored intent.priority_policy, not synthesized. trade.pvr is a legacy original intent.score alias, not this source score.')
    elif k.startswith('CORE_'):d.update(source='original daily.layers metadata / actualfacts.i_floor',note='Stored layer.floor, saved last_core_line, and current I reference are separate fields. CORE exits are not universally a direct C<layer.floor test. Nov20 andNov26 layer1994 floor42.59907875674594, last_core_line/currentI111.27463844110417. NONE when no live Core.')
    elif 'floor'in k:d.update(source='original previous/current daily.layers plus actual buy floor',note='Previous CLOSE snapshot and actual new-buy initial floor are saved observations; current CLOSE is saved post-planning state. Intra-CLOSE update-before/after event was not logged: NOT_SAVED. No final-book floor backfill.')
    elif 'qty'in k:d.update(source='original daily.positions/layers and actual trades',note='Before OPEN is previous original CLOSE quantity; after actual OPEN adds/subtracts only saved actual fills, verified against current CLOSE quantity on43 dates. No split in this slice. add layer-kind denotes Mobile.')
    elif k in ['raw_open','raw_high','raw_low','raw_close','raw_volume','source_volume_coordinate']:
        d.update(source='actual_frames.source_signal',note='Original saved raw_* versus original normalized signal.volume retained separately; no newly fetched bars. raw_volume is raw shares, source_volume_coordinate is original transformed share coordinate, not interchangeable.')
    elif k in ['continuous_close','factor','source_segment']:d.update(source='actual_frames.facts',note='Original continuous/rights price coordinate and factor, no new adjustment. raw and continuous price must not be mixed.')
    elif k in ['date','source_observed_at','source_publication_timestamp','source_observed_bar','original_CLOSE_at','previous_original_CLOSE']:
        d.update(source='source_signal date/flags plus original daily.at',note='Original native consumption CLOSE is saved15:10+08. Cached source publication instant is NOT_SAVED; observed_at blank is preserved, not a claimed known timestamp.')
    elif k in ['previous_CLOSE_plans_for_this_OPEN','CLOSE_actual_signal_intents']:d.update(source='original B.decisions.intents',note='Plans from actual corresponding decision, never a guarantee of nextOPEN fill. Full roles/cap/budget/protection/rank fields kept.')
    elif k=='OPEN_actual_funding_records':d.update(source='original funding.jsonl.gz',note='Actual role funding outcomes, including comma-joined rejection union. Sorted reasons are not inferred first blocker.')
    elif k in ['OPEN_actual_buy_records','OPEN_actual_sell_records']:d.update(source='original B.trades',note='Saved actual proxy fills/fees/parts/timestamps. Daily-bar proxy fills do not establish real exchange queue execution.')
    elif k=='CLOSE_original_opportunity_records':d.update(source='original opportunities.jsonl.gz',note='Saved core_Q/mobile_Q/CP/roles/barriers, no inferred new intent.')
    elif k in ['CLOSE_actual_exit_proposals','original_stock_audit_records']:d.update(source='original B.audit',note='Historical exit proposals reside in audit; final B.exits map is not historical proposal history. Original close-to-nextOPEN timing retained.')
    elif k in ['original_account_NAV_CLOSE','original_ACT_on']:d.update(source='original daily.nav/on',note='Original full account context, not a stock return or new account result.')
    else:raise ValueError('Unmapped dictionary column '+k)
    d['clock']='Original actual consuming CLOSE, or explicit original OPEN action timestamp in saved record.'
    return d

dictionary={'scope':'43 original Hytera stock observations,2024-09-23..2024-11-27. No EMA/Bollinger/risk design additions.',
    'markers':{'NOT_SAVED':'Field/event-level boundary or publication instant was not saved; not reconstructed.','SOURCE_NULL':'An explicit NaN/pandasNA in an existing source field. Original JSON null remains null; CSV may display blank.','NONE':'No actual plan/action/rank row or live layer in this category.','0/false':'Actual saved zero or false, distinct from missing.'},
    'source_reference_map':'SOURCE_REFERENCE_MAP.json','columns':[dictionary_entry(k)for k in rows[0]],
    'critical_identity':'Legacy IX.ix_target differs from actualfacts.i_target on19/43 observations. No copying IX exit/entered into actual I. E0entered is direct auxiliary E0 states, not an actualfacts export.',
    'floor_warning':'Actual stored x.floor is not universally Core current risk reference. Read daily saved last_core_line and actualfacts.i_floor separately; no claim of a general direct line-price Core exit.'}
save('DATA_DICTIONARY.json',dictionary)
intents=sum(r['CLOSE_actual_signal_intents']!='NONE'for r in rows);ranked=sum(r['PVR_actual_rank_policy_record']!='NONE'for r in rows)
checks=read('CHECKS_AND_COST.json')
text=f'''海能达002583：原No60逐日变量与实际动作

范围：2024-09-23至2024-11-27，共{len(rows)}个实际股票观察/CLOSE；起点原qty0，终点原qty0。
这是现成原facts/CP/E0states/events/G1来源/PVR缓存与原B/daily日志的只读提取。
没有模型、Market、Account、指标计算、风险设计或新回测。

先读HYTERA_DAILY_NATIVE.csv。每行分开原CLOSE变量、当日原计划、前CLOSE给本OPEN的
计划、OPEN实际资金拒因/买卖、CLOSE退出提案和真实持层。只有{ranked}个观察有实际
rank-policy行，其余slots/rank为NONE；43日PVR_source_score均来自实际long的2024_full
缓存，存在分数不代表入选或有排名。不能将成交原trade.pvr别名当真PVR源。

实际动作：10/15 OPEN CORE100股；10/21 OPEN MOBILE1100股；10/22 OPEN MOBILE1000股。
11/4 CLOSE两Mobile提出CP退出，11/5 OPEN卖2100股；Core100仍持有。
11/26 CLOSE原I失效提退出，11/27 OPEN卖剩100股。原10/16、17的Mobile资金记录是
probe_risk拒绝，后续还有行业/现金拒因，表内保留原组合字符串而不伪称第一约束。

三处来源边界
1. 实际I_target/i_floor/i_buy只取long真正消费的facts。旧IX与I有19/43日不同，不能
   用旧IX的G1冷却退出解释实际I；I_entered/exited/exit_reason在actualfacts未导出，
   记NOT_SAVED。E0entered/event可从原E0states/events旁取，但不称actualfacts导出。
   E0target43日核同，E0floor42个共同已知日核同，11/27两边SOURCE_NULL。
2. CORE1994的stored x.floor一直42.59907875674594，但11/20起saved last_core_line与
   actualfacts I参考已为111.27463844110417。主CSV两者已分列，不能把Core静态stored
   floor一概当直接价格止损。Mobile逐层CP floor也来自每日快照，不取最终book回填。
   intra-CLOSE提线之前的即时floor没有独立日志，明确NOT_SAVED；以前CLOSE/真实买入
   初始线/当前CLOSE三种已保存边界比较。补充LAYER_FLOOR_TIMELINE.csv可逐层查看。
3. 原source observed_at为空，发布时间不详；表中的15:10是原账户实际消费CLOSE时钟，
   不是供应商发布时间。OPEN成交为原日线执行代理记录，不声称真实排队必成交。

KEY_DAYS_ORIGINAL_OUTPUTS.json保留7个关键日原字段；ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json
保留43日完整股票切片。DATA_DICTIONARY.json逐列说明来源和NOT_SAVED/SOURCE_NULL/NONE。
SOURCE_REFERENCE_MAP.json钉实际long文件路径，SOURCE_SHA256.json绑定原输入。
主CSV补列前版本保留.v1，DAILY_TABLE_CORRECTION_RECEIPT.json记录前后SHA；原源未改。

成功原源提取内部计时{checks['extraction_seconds']:.6f}秒；其前I/IX身份断言中止、空值
序列化错误与读取方式修正均为只读提取，不是金融运行。初次中止日志已留存。
新增账户/回测/参数/模型/行情/特征均0。
'''
(O/'READOUT.txt').write_text(text)
save('FINAL_OUTPUT_SHA256.json',{p.name:sha(p)for p in sorted(O.iterdir())if p.is_file()and p.name!='FINAL_OUTPUT_SHA256.json'})
print(json.dumps({'observations':len(rows),'columns':len(rows[0]),'actual_rank_rows':ranked,'E0_floor_known_pairs_equal':floor_known,'dictionary_complete':True,'new_models':0}))
