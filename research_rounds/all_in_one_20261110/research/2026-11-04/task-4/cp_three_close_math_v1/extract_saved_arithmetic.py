"""Scalar substitution into three saved CP states; never import a model/engine."""
from pathlib import Path
import json, math, hashlib, csv, io
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
YP=ROOT/'native_algorithm_read_v1/yingxin_reentry_evidence/CONTINUOUS_FOUR_CLOSE_RAWDICTS.json'
HP=ROOT/'native_algorithm_read_v1/daily_hytera/ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json'
y=json.loads(YP.read_text())['rows'];h=json.loads(HP.read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
records=[];raw=[]
for name,sid,rows,day,anchor_day,ck,fk,bk,path in [
 ('盈新','000620.SZ',y,'2022-01-21','2022-01-20','original_CP_cache','original_stock_facts','original_bar',YP),
 ('盈新','000620.SZ',y,'2022-01-24','2022-01-21','original_CP_cache','original_stock_facts','original_bar',YP),
 ('海能达','002583.SZ',h,'2024-10-18','2024-10-16','CP1','facts','source_signal',HP)]:
 idx=next(i for i,r in enumerate(rows)if r['day']==day);r=rows[idx];prev=rows[idx-1];ar=next(r for r in rows if r['day']==anchor_day)
 q=r[ck];pq=prev[ck];f=r[fk];af=ar[fk];pf=prev[fk];bar=r[bk]
 raw.append({'sid':sid,'day':day,'source':str(path),'source_sha256':sha(path),'current':{'facts':f,'CP':q,'bar':bar},'previous':{'day':prev['day'],'facts':pf,'CP':pq},'anchor_day':{'day':anchor_day,'facts':af,'CP':ar[ck]}})
 F=f['factor'];oldanchor=pq['next_anchor'];oldfront=pq['frontier'];oldcredit=pq['next_credit'];oldscale=pq['next_scale'];p=math.log(f['close'])
 fresh=max(p-oldfront,0.);saved_fresh=q['delta_frontier'];inc=saved_fresh*q['m'];credit=math.fsum((oldcredit,inc));disp=q['frontier']-q['anchor'];T=math.sqrt(5)*q['scale'];K=math.sqrt(21)*q['scale'];mult=math.exp(-K);pa=f['close']*mult;pr=pa/F
 rec={'name':name,'sid':sid,'day':day,'price_inputs':{'C_a':f['close'],'C_raw':f['raw_close'],'factor':F,'anchor_day':anchor_day,'anchor_C_a_saved':af['close'],'anchor_C_raw_saved':af['raw_close'],'previous_day':prev['day'],'previous_C_a':pf['close'],'previous_C_raw':pf['raw_close'],'amount_CNY':bar['amount']},
 'feature_inputs_saved':{k:q[k]for k in ['r','s','z','B','u','v','m']},
 'pre_state_from_previous_next':{'anchor':oldanchor,'frontier':oldfront,'credit':oldcredit,'scale':oldscale,'phase':pq['next_phase']},
 'current_saved_CP':q,
 'arithmetic':{'p_log_C_a':p,'fresh_from_log_C_minus_previous_frontier':fresh,'fresh_saved_used_for_credit':saved_fresh,'u_from_tanh_saved_r_over_s':math.tanh(q['r']/q['s']),'v_from_tanh_log_amount_over_saved_B':math.tanh(math.log(bar['amount']/q['B'])),'m_from_saved_u_v':1+.5*abs(q['u'])*q['v'],'new_credit':inc,'credit_before':oldcredit,'credit_after':credit,'displacement':disp,'sqrt5':math.sqrt(5),'frozen_scale':q['scale'],'threshold_sqrt5_scale':T,'displacement_margin':disp-T,'credit_margin':credit-T,'minimum_trigger_margin':min(disp-T,credit-T),'sqrt21_scale':K,'protection_multiplier_exp_negative_sqrt21_scale':mult,'candidate_a':pa,'candidate_raw_from_a_over_factor':pr,'candidate_raw_from_raw_close_times_multiplier':f['raw_close']*mult,'candidate_gap_a':f['close']-pa,'candidate_gap_raw':f['raw_close']-pr,'price_advance_from_anchor_a':f['close']-af['close'],'price_advance_from_anchor_raw':f['raw_close']-af['raw_close'],'frontier_price_advance_today_a':f['close']-pf['close'],'frontier_price_advance_today_raw':f['raw_close']-pf['raw_close'],'anchor_log_raw_current_coordinate':q['anchor']-math.log(F),'frontier_before_log_raw_current_coordinate':oldfront-math.log(F),'frontier_after_log_raw_current_coordinate':q['frontier']-math.log(F),'then_next_anchor':q['next_anchor'],'then_next_credit':q['next_credit'],'then_next_scale':q['next_scale']},
 'checks':{'all_input_factors_equal':F==af['factor']==pf['factor'],'anchor_matches_previous_next':q['anchor']==oldanchor,'scale_matches_previous_next':q['scale']==oldscale,'fresh_matches_saved_abs_error':abs(fresh-saved_fresh),'credit_matches_saved_abs_error':abs(credit-q['credit']),'displacement_matches_saved_abs_error':abs(disp-q['displacement']),'candidate_matches_saved_abs_error':abs(pa-q['candidate']),'receipt_by_saved_fresh_and_both_margins':bool(saved_fresh>0 and disp>=T and credit>=T),'saved_receipt':q['receipt']},
 'units':'r/s/z/scale/anchor/frontier/displacement/credit/threshold are log-coordinate numbers, not CNY. Fixed same factor over each shown formation interval makes log displacement/credit invariant. C_a and converted raw levels are CNY/share. raw candidate is derived display, not separately saved or an executable fill.',
 'source_scope':'Rolling63 s and rolling21 B were copied, not recalculated. All transformations use saved then-CLOSE fields. No receipt/signal/model/account recalculation.'}
 records.append(rec)
write('READONLY_INPUTS.json',raw);write('THREE_CLOSE_SCALAR_SUBSTITUTIONS.json',records)
headers=['name','day','C_a','C_raw','frozen_scale','frontier_before','anchor','fresh','credit_before','new_credit','credit_after','displacement','threshold','displacement_margin','credit_margin','multiplier','candidate_a','candidate_raw']
s=io.StringIO();w=csv.DictWriter(s,fieldnames=headers);w.writeheader()
for r in records:
 a=r['arithmetic'];f=r['price_inputs'];q=r['current_saved_CP'];pre=r['pre_state_from_previous_next']
 w.writerow(dict(name=r['name'],day=r['day'],C_a=f['C_a'],C_raw=f['C_raw'],frozen_scale=q['scale'],frontier_before=pre['frontier'],anchor=q['anchor'],fresh=q['delta_frontier'],credit_before=a['credit_before'],new_credit=a['new_credit'],credit_after=a['credit_after'],displacement=a['displacement'],threshold=a['threshold_sqrt5_scale'],displacement_margin=a['displacement_margin'],credit_margin=a['credit_margin'],multiplier=a['protection_multiplier_exp_negative_sqrt21_scale'],candidate_a=a['candidate_a'],candidate_raw=a['candidate_raw_from_a_over_factor']))
(OUT/'THREE_CLOSE_SUMMARY.csv').write_text(s.getvalue())
mp=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py');lines=mp.read_text().splitlines()
(OUT/'CP_ORIGINAL_FORMULA_WITH_LINES.txt').write_text('PATH '+str(mp)+'\nSHA256 '+sha(mp)+'\n\n'+'\n'.join(f'{i:4d} {lines[i-1]}'for i in range(1,59))+'\n')
write('ROOT_SCOPE.json',{'source_files':{str(YP):sha(YP),str(HP):sha(HP),str(mp):sha(mp)},'saved_target_states':3,'saved_anchor_previous_states_only':True,'new_models':0,'new_indicators':0,'new_accounts':0,'new_backtests':0,'new_market_data':0,'calculation_scope':'Scalar substitution and coordinate conversion from saved rows only; not recalculating features or emitting new signals.'})
for r in records:print(r['name'],r['day'],r['checks'])
