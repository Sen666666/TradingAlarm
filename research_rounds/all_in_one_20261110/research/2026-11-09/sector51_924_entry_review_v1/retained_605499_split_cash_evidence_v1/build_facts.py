from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda n,v:(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
p=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2/001464/signal.parquet')
a=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions/605499.SH.json')
z=pd.read_parquet(p);prev=z.loc['2024-10-08'];cur=z.loc['2024-10-09'];cols=['source_kind','source_path','segment_id'];origin=tuple(str(prev[c]) for c in cols)
assert origin==tuple(str(cur[c]) for c in cols)
fo,fn,pc=map(lambda x:D(str(x)),[prev.adjustment_factor,cur.adjustment_factor,prev.raw_close])
residual=fo*pc*D('1.30')/(pc-D('2.50'))/fn-1
assert abs(residual)<D('1e-11')
assert sha(p)=='aff47fd8e44033ae262f5ab0752604aacf91f86224d72a109a71f3c4c0a9987c'
t=[e for e in json.loads(a.read_text())['events'] if e['effective_date']=='2024-10-09'];assert len(t)==1
assert D(t[0]['cash_per_old_share'])==D('2.50') and D(t[0]['split_ratio'])==D('1.30')
e=dict(sid='605499.SH',economic_event_id_candidate='605499.SH|2024-10-09|2024-088|Q0_RETAINED_ONLY',record_date='2024-10-08',ex_date='2024-10-09',pay_date='2024-10-09',new_shares_sellable_at='2024-10-09',d_source='2.50',d_cash='2.50',split_ratio='1.30',factor_old=str(fo),factor_new=str(fn),admission_scope='ZERO_HOLDING_NEVER_SEEDED_RETAINED_TICKET_ONLY',held_split_supported=False,review_status='FACTS_VERIFIED_RUNTIME_GUARDS_REQUIRED',not_PIT=True,not_production_admission=True,source_lineage=origin,source_fact_path=str(p),source_fact_sha256=sha(p),signal_path=str(p),signal_sha256=sha(p),local_action_path=str(a),local_action_sha256=sha(a),notice=dict(url='https://static.cninfo.com.cn/finalpage/2024-09-26/1221291027.PDF',announcement='2024-088',publication_date='2024-09-26',pdf_path=str(O/'605499_2024_088.pdf'),pdf_sha256=sha(O/'605499_2024_088.pdf')),evidence_hashes={str(p):sha(p),str(a):sha(a),str(O/'605499_2024_088.pdf'):sha(O/'605499_2024_088.pdf')})
save('Q0_ONLY_EVENT_FACTS.json',[e])
save('FACTOR_BRIDGE_QA.json',dict(result='PASS_FACTS_ONLY',record_close=str(pc),formula='factor_new = factor_old * record_raw_close * split_ratio / (record_raw_close - gross_cash_per_old_share)',relative_residual=str(residual),same_source=True,rows=[dict(day=d,**{c:str(z.loc[d,c]) for c in ['raw_open','raw_close','adjustment_factor']+cols}) for d in ['2024-10-08','2024-10-09']],local_action=t[0],historical_simulation_run=False))
print(sha(O/'Q0_ONLY_EVENT_FACTS.json'))
