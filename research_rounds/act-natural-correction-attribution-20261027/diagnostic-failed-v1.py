exec(open('/tmp/act_diag.py').read().split('out={};')[0])
P0=P/'S0/accounts-v2';snap=pathlib.Path(json.loads((P/'input.json').read_text())['snapshot']);a=json.loads((P0/'ACT0__S0_delay1.json').read_text());cache={};out=[]
for r in a['audit_log']:
 if r['kind']!='buy_day_expiry' or r['filled_shares']!=0:continue
 sid=r['sid'];day=r['at'][:10]
 if sid not in cache:cache[sid]=pd.read_parquet(snap/'signals'/f'{sid}.parquet')
 z=cache[sid].loc[:day].iloc[-1];later=[x for x in a['audit_log'] if x['kind']=='reserve' and x['sid']==sid and x['at']==r['at']]
 out.append(dict(sid=sid,day=day,structure=bool(z.i_target),warm=bool(z.g_ready and z.g_grade>=2),fresh=bool(z.i_buy),reaccepted=bool(later),credit=r['delay_credit']))
pd.DataFrame(out).to_csv(O/'zero-fill-expiries.csv',index=False);d=pd.DataFrame(out);print('EXP',len(d),d.sum(numeric_only=True).to_dict());print('warm+structure+noevent',len(d[d.structure & d.warm & ~d.fresh]))
s=pd.read_csv(P/'summary.csv');print(s[(s.strategy=='ACT')&(s.seed==0)][['cohort','scenario','net_return','max_drawdown','buy_fills','tail_profit','ordinary_profit','fees']].to_string(index=False))
d=pd.read_csv(O/'delay-stock-difference.csv');x=d[(d.cohort=='S0')&(d.seed==0)];print('TOTALDELTA',x.difference.sum(),'TOP4',x.nsmallest(4,'difference').difference.sum(),'OTHER',x.difference.sum()-x.nsmallest(4,'difference').difference.sum());print('POS',x.nlargest(5,'difference').to_string(index=False))
