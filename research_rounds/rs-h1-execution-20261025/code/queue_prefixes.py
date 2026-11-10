"""Fixed technical prefixes wait for main progression; never tune policy."""
import subprocess,sys,time,json
from build_inputs import HERE,read,write,now
out=HERE/'technical-prefix-v2';out.mkdir(exist_ok=False)
for cutoff in ['2017-12-31','2020-12-31','2023-12-31']:
 while True:
  dates=[]
  for g in ['G0','G1']:
   p=HERE/'accounts-v2/groups'/(g+'.log');rows=[]
   if p.exists():
    for line in p.read_text().splitlines():
     try:
      x=json.loads(line)
      if 'progress_date' in x:rows.append(x['progress_date'])
     except json.JSONDecodeError:pass
   dates.append(max(rows,default=''))
  if min(dates)>cutoff:break
  p=HERE/'accounts-v2/summary.json'
  if p.exists():
   assert read(p).get('status')!='failed_partial_run'
   break
  time.sleep(10)
 with (out/(cutoff+'.log')).open('x') as f:
  result=subprocess.run([sys.executable,str(HERE/'code/prefix_live_v2.py'),cutoff],stdout=f,stderr=f)
 assert result.returncode==0,cutoff
 print({'cutoff':cutoff,'passed':True},flush=True)
write(out/'summary.json',dict(recorded_at=now(),passed=True,technical_prefix_accounts=12,economic_accounts_added=0,cutoffs=['2017-12-31','2020-12-31','2023-12-31']))
