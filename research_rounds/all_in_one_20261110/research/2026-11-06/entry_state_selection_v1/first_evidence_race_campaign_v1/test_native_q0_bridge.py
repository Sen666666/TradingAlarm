from campaign_engine import *
import ast
source=E/'cash_equity_baseline_2024_v1/engine.py';txt=source.read_text();tree=ast.parse(txt)
g=dict(D=D,BRIDGE=True,ALLOWED_EVENT_IDS=None,bridges=[],snapshots={},EVENT_AT={},finite=lambda x:x is not None and np.isfinite(x),claim_key=lambda arm,e:(arm,e['economic_event_id']))
for name in ['enabled','coordinate_matches','pending_bridge']:
 node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name);exec(compile(ast.get_source_segment(txt,node),str(source)+':exact_test','exec'),g)
d=pd.Timestamp('2024-12-31');sid='SYNTHETIC';e=dict(economic_event_id='CASH',sid=sid,d_source=D(1),factor_old=D(1),factor_new=D(10)/D(9));g['EVENT_AT'][(sid,d)]=e
st=dict(sid=sid,arm='D',round_id='R',i_floor=8);prev=dict(raw_close=10,adjustment_factor=1);z=dict(adjustment_factor=float(D(10)/D(9)))
g['snapshots'][('D','CASH')]=dict(record_q=0);assert g['pending_bridge'](st,d,z,prev)
assert g['bridges'][-1]['record_q']==0 and g['bridges'][-1]['dividend']==0
assert abs(g['bridges'][-1]['floor_raw']-D('7.2'))<D('1e-10')
g['snapshots'][('D','CASH')]=dict(record_q=100);assert not g['pending_bridge'](st,d,z,prev)
g['snapshots'][('D','CASH')]=dict(record_q=None);assert not g['pending_bridge'](st,d,z,prev)
g['snapshots'][('D','CASH')]=dict(record_q=0);assert not g['pending_bridge'](st,d,dict(adjustment_factor=2),prev)
p=O/'NATIVE_Q0_BRIDGE_QA.json';assert not p.exists();p.write_text(json.dumps(dict(pass_all=True,zero_quantity_coordinate_bridge=True,no_dividend_or_claim=True,nonzero_unknown_or_bad_coordinate_rejected=True,source_sha256=sha(source),test_sha256=sha(Path(__file__))),indent=2)+'\n');print('Q0_BRIDGE_PASS')
