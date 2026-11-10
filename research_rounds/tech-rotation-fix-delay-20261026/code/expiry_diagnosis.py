from study_common import *
import collections
obj=read(BASE/'accounts-v2/I__S0_delay1.json');rs={r['order_id']:r for r in obj['audit_log'] if r['kind']=='reserve'};fs={r['order_id'] for r in obj['audit_log'] if r['kind']=='fill' and r['receipt']['side']=='buy'};out=[];cache={}
for e in obj['audit_log']:
 if e['kind']!='buy_day_expiry' or e['order_id'] in fs:continue
 sid=e['sid'];r=rs[e['order_id']];T=r['decision_at'][:10];day=e['at'][:10]
 if sid not in cache:cache[sid]=pd.read_parquet(PREP/'facts'/f'{sid}.parquet')
 f=cache[sid];z=f.loc[:day].iloc[-1];out.append(dict(symbol=sid,signal_day=T,expiry_day=day,delay_credit=bool(e['delay_credit']),i_target=bool(z.i_target),i_buy=bool(z.i_buy),warm=bool(z.g_ready and z.g_grade>=2),grade=float(z.g_grade),held_no_new_event=bool(z.i_target and z.g_ready and z.g_grade>=2 and not z.i_buy)))
pd.DataFrame(out).to_csv(HERE/'old-I-expiry-status.csv',index=False)
write(HERE/'old-I-expiry-summary.json',dict(zero_fill_expiries=len(out),skipped_credit=sum(x['delay_credit'] for x in out),structure_still_active=sum(x['i_target'] for x in out),still_warm=sum(x['warm'] for x in out),warm_active_but_no_fresh_event=sum(x['held_no_new_event'] for x in out),fresh_event_again=sum(x['i_buy'] for x in out)))
print(read(HERE/'old-I-expiry-summary.json'))
