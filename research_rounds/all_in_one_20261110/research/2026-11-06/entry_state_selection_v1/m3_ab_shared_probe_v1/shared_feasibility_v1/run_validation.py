from pathlib import Path
import sys,json,hashlib,subprocess,os,traceback
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,default=str);f.write('\n')
def main():
 seal=json.loads((HERE/'VALIDATION_EXECUTION_SEAL.json').read_text())
 for name,h in seal['sha256'].items():assert sha(HERE/name)==h
 dest=HERE/'validation';dest.mkdir(exist_ok=False)
 save(dest/'STARTED.json',{'at':datetime.now(timezone.utc).isoformat(),'stage':'SYNTHETIC_PLUS_REAL_INPUT_RESERVATION_ONLY','execution_seal':sha(HERE/'VALIDATION_EXECUTION_SEAL.json'),'no_shared_fills':True})
 try:
  env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
  tests=subprocess.run([sys.executable,'-B','-m','unittest','-v','test_limits'],cwd=HERE,env=env,text=True,capture_output=True)
  with (dest/'SYNTHETIC_TEST_LOG.txt').open('x') as f:f.write(tests.stdout+tests.stderr)
  assert tests.returncode==0,'synthetic test failure'
  actual=subprocess.run([sys.executable,'-B','run_first_open_v2.py'],cwd=HERE,env=env,text=True,capture_output=True)
  with (dest/'FIRST_OPEN_DRIVER_LOG.txt').open('x') as f:f.write(actual.stdout+actual.stderr)
  assert actual.returncode==0,'real-input reservation-only fixture failure'
  for name,h in seal['sha256'].items():assert sha(HERE/name)==h
  result={'status':'AUTHOR_PASS_BOUNDED_RESERVATION_ONLY','synthetic_tests':12,'real_first_open':json.loads((HERE/'first_open_2022/RESULT.json').read_text()),'independent_review':'PENDING','shared_fills':False}
  save(dest/'RESULT.json',result);print(json.dumps(result),flush=True)
 except BaseException as e:
  save(dest/'RESULT.json',{'status':'FAIL','error_type':type(e).__name__,'error':str(e)})
  raise
if __name__=='__main__':main()
