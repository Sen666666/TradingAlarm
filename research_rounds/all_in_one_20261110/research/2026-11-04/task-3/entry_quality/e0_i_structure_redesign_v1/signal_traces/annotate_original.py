"""Independent read-only annotations after V2 trace; never used by trace()."""
from pathlib import Path
import csv,gzip,hashlib,json
O=Path(__file__).resolve().parent;Q=O.parents[1];OUT=O/'v2_all7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p,gz=False):
 with (gzip.open(p,'rt') if gz else p.open()) as f:return json.load(f)
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def csvsave(n,rr):
 with (OUT/n).open('w') as f:
  flat=[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rr]
  w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
trace=read(OUT/'ALL_DAILY_TRACES.json');lookup={(r['sid'],r['day']):r for r in trace};idx=read(O.parent/'path_inputs/INPUT_INDEX.json');spec={r['sid']:r for r in idx};books={};sources={str(OUT/'ALL_DAILY_TRACES.json'):sha(OUT/'ALL_DAILY_TRACES.json')}
for window in ['2022_2024','strong']:
 p=Q/'trend_exit_controls_v1/runs/BASELINE'/window/'pair/B.json.gz';books[window]=read(p,True);sources[str(p)]=sha(p)
def snapshot(r):
 n=r['original_native_comparison_only'];cp=r['original_CP_comparison_only']
 return dict(C=r['C'],raw_C=r['raw_C'],mode=r['mode'],I_hold=r['I_hold'],I_expand=r['I_expand'],A_active=r['A_active'],B_active=r['B_active'],B_base=r['B_base'],P_old=r['P_old'],P_new=r['P_new'],KA=None if r['current_KA'] is None else r['current_KA']['price_adjusted'],KA_confirmed_at=None if r['current_KA'] is None else r['current_KA']['confirmed_at'],initial_KA=r['initial_KA'],L1=r['L1'],H12=r['H12'],L2=r['L2'],original_I_target=None if n is None else n['i_target'],original_I_buy=None if n is None else n['i_buy'],original_G1_grade=None if n is None else n['g_grade'],original_G1_ready=None if n is None else n['g_ready'],original_CP_receipt=None if cp is None else cp['receipt'],original_CP_candidate=None if cp is None else cp['candidate'])
entry=[];intents=[]
for sid,q in spec.items():
 window='strong' if sid in ['603061.SH','605111.SH','300623.SZ'] else '2022_2024';b=books[window]
 bylayer={t['layer']:t for t in b['trades'] if t['side']=='buy'}
 for a in q['funded_original_stock_structure_roots']:
  lid=a['layer'];t=bylayer[lid];day=a['original_signal_at'][:10];r=lookup.get((sid,day));assert r is not None
  role=b['metadata'][str(lid)]['role']
  entry.append(dict(window=window,sid=sid,original_layer=lid,original_role=role,original_signal_at=a['original_signal_at'],original_actual_fill_at=a['original_fill_at'],original_stock_structure=a['original_stock_structure'],**snapshot(r),comparison_scope='Current new expansion permission only; not an order/fill/grant prediction. CORE launch consumption and candidate positions were not simulated; old CP was not recomputed.'))
 for di,d in enumerate(b['decisions']):
  day=d['at'][:10]
  if (sid,day) not in lookup:continue
  r=lookup[(sid,day)]
  for ii,i in enumerate(d['intents']):
   if i['sid']!=sid:continue
   lid=[x['original_layer'] for x in entry if x['sid']==sid and x['original_signal_at'][:10]==day and x['original_role']==i['role']]
   intents.append(dict(window=window,sid=sid,original_decision_index=di,original_intent_index=ii,original_signal_at=d['at'],original_role=i['role'],original_CP1_id=i.get('CP1_id'),original_actual_layer_ids=lid,**snapshot(r),comparison_scope='Original frozen intent annotation only; no new CP/position/cash/execution path. Permission false/unknown is not a calculated portfolio outcome.'))
save('ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.json',entry);csvsave('ORIGINAL_ACTUAL_ENTRY_SIGNAL_JOIN.csv',entry)
save('ORIGINAL_INTENT_SIGNAL_JOIN.json',intents);csvsave('ORIGINAL_INTENT_SIGNAL_JOIN.csv',intents)
keydates={'000620.SZ':['2022-01-06','2022-01-07','2022-01-10','2022-01-11','2022-01-12','2022-01-13','2022-01-20','2022-01-21','2022-01-24','2022-02-07'],'601019.SH':['2022-11-25','2022-12-12','2023-02-10','2023-06-19','2023-06-26'],'601601.SH':['2024-08-19','2024-08-30','2024-09-24','2024-10-09'],'002583.SZ':['2024-09-19','2024-09-20','2024-11-04','2024-11-25','2024-11-26']}
save('KEY_DATES.json',[dict(sid=sid,day=day,**snapshot(lookup[(sid,day)]),new_pivot=lookup[(sid,day)]['new_confirmed_pivot'],support_exit=lookup[(sid,day)]['support_exit_events'],confirm_event=lookup[(sid,day)]['confirm_event']) for sid,days in keydates.items() for day in days])
save('ORIGINAL_JOIN_RECEIPT.json',dict(status='SAVED_ORIGINAL_ANNOTATIONS_ONLY_NOT_MODEL_INPUT',source_sha256=sources,script_sha256=sha(Path(__file__)),actual_original_entry_layers=len(entry),original_intents=len(intents),new_orders=0,new_quantities=0,new_cash_paths=0,new_returns=0))
print(json.dumps(dict(entries=len(entry),intents=len(intents),by_sid={s:[dict(layer=r['original_layer'],signal=r['original_signal_at'][:10],role=r['original_role'],expand=r['I_expand'],A=r['A_active'],B=r['B_active']) for r in entry if r['sid']==s] for s in spec}),ensure_ascii=False))
