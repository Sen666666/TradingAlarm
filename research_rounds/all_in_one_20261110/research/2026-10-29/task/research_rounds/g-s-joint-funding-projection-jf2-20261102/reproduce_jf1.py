"""Reproduce audited bugs with immutable JF1 in a separate process; no account."""
from pathlib import Path
import sys,copy,json,hashlib
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'g-s-joint-funding-projection-jf1-20261101'
sys.path.insert(0,str(OLD));import projector as P
from test_projector import state,lot,demand,AT,END
assert hashlib.sha256((OLD/'projector.py').read_bytes()).hexdigest()=='524c6bd35452eb3726cddece2a1bb323a50ff5df96a5f857e4eeda8b2e8e215d'
s=state([lot()]);d=demand();c=P.solve(s,[d]);bad=copy.deepcopy(c);bad['Q']['NEW']=500
b=P.CertificateBook();b.accept(bad,'same');b.bind_reservation('same','NEW','order',100,AT);b.actual_fill('order',50);b.cancel_request('order')
restored=P.CertificateBook.loads(b.dumps());cap=restored.cap('same','NEW',500,AT);assert cap==400
d2=demand();d2['receipt_id']='different-fresh';same_id=P.solve(s,[d2])['certificate_id']==c['certificate_id'];assert same_id
d3=demand(q=100);d3['price_known_at']='2025-07-04 09:30:00+08:00';future=P.solve(state([],cash='1000000'),[d3])['Q'];assert future['NEW']==100
ar=dict(id='AR|one',kind='sale_receivable',amount=P.D(100),due_at='2025-07-04 09:30:00+08:00',parts=[])
ss=state([lot(q=89,mark='100',floor='99.99',purpose='T')],cash='1000',assets=[ar]);ss['other_saved_goal_need']=100
cc=P.solve(ss,[demand(q=100,mark='.5',floor='.49')]);assert cc['Q']['NEW']==100 and cc['donors']['covered']==P.D('55.028206602500')
(ROOT/'JF1_FAILURE_REPRODUCTION.json').write_text(json.dumps(dict(original_source_sha256=hashlib.sha256((OLD/'projector.py').read_bytes()).hexdigest(),proved100_changed500_after50filled50pending_cap=cap,receipt_only_change_same_id=same_id,future_price_accepted=future,other_goal100_and_new_need_share_AR100=dict(new_need=cc['donors']['raw_need'],cover=cc['donors']['covered'],new_D=cc['donors']['rows']),financial_events=0),default=str,indent=2)+'\n')
print('JF1_AUDITED_FAILURES_REPRODUCED_NO_FINANCIAL_EVENTS',flush=True)
