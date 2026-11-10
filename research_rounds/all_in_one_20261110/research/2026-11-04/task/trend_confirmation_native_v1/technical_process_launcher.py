"""PID/argv evidence only; executes the unchanged frozen technical entry."""
from pathlib import Path
import datetime, hashlib, json, os, runpy, sys
O=Path(__file__).resolve().parent
args=sys.argv[1:]
assert '--technical'in args and '--out'in args
out=Path(args[args.index('--out')+1]).resolve()
assert str(out).startswith(str(O.resolve())+'/')
out.mkdir(parents=True,exist_ok=True)
record=out/'PROCESS_IDENTITY.json';assert not record.exists()
driver=O/'run_trend_window.py'
record.write_text(json.dumps(dict(pid=os.getpid(),parent_pid=os.getppid(),
    started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    interpreter=sys.executable,argv=[str(driver)]+args,
    launcher_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    driver_SHA256=hashlib.sha256(driver.read_bytes()).hexdigest(),
    action='execute unchanged driver via runpy; no engine/account modifications'),indent=2)+'\n')
sys.argv=[str(driver)]+args
try:
    runpy.run_path(str(driver),run_name='__main__')
except BaseException as e:
    (out/'PROCESS_EXIT.json').write_text(json.dumps(dict(success=False,error=repr(e)),indent=2)+'\n')
    raise
else:
    (out/'PROCESS_EXIT.json').write_text(json.dumps(dict(success=True,pid=os.getpid(),
        ended_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
