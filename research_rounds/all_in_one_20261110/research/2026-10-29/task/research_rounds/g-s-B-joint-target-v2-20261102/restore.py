"""Verify only a pure result against trusted input bytes and frozen selector."""
from selector import *
ip=Path(sys.argv[1]);assert sha(ip)==sys.argv[2],'trusted input changed'
x=json.loads(ip.read_text());r=json.loads(Path(sys.argv[3]).read_text());assert r['result_id']==J.digest({k:v for k,v in r.items() if k!='result_id'})
assert r['selector_sha256']==sha(O/'selector.py') and r['joint_guard_sha256']==sha(J.__file__)
if 'demands' in x and 'B_demands' not in x:ds=x['demands']
elif 'B_demands' in x and 'demands' not in x:ds=x['B_demands']
else:raise ValueError('unsupported or ambiguous pure-input schema')
fresh=solve_B(x['snapshot'],ds);assert fresh['result_id']==r['result_id']
save(sys.argv[4],dict(exact=True,Q=fresh['Q'],D=fresh['D'],financial_events=0))
