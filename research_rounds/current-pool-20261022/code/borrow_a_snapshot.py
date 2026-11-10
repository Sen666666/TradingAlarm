"""Bounded current-snapshot work between this task's A-history batches.

Stops only the verified queue parent, lets its child finish, and resumes in
finally. No collector modification and no simultaneous use of its quote node.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, os, signal, subprocess, time

R = Path(__file__).resolve().parents[1]
PY = '/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python'
PID = 26889
OUT = R / 'diagnostics/a-snapshot-control-01'
OUT.mkdir(exist_ok=False)
events = []

def record(stage, **kwargs):
    events.append(dict(stage=stage, at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), **kwargs))
    (OUT / 'receipt.json').write_text(json.dumps(events, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(events[-1], ensure_ascii=False), flush=True)

def processes():
    raw = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,stat=,command='], text=True)
    return [x.strip().split(None, 3) for x in raw.splitlines() if len(x.strip().split(None, 3)) == 4]

def collect(script, plan, output, timeout):
    with (OUT / (output + '.stdout.log')).open('x') as stdout, (OUT / (output + '.stderr.log')).open('x') as stderr:
        p = subprocess.run([PY, str(R/'code'/script), '--plan', str(R/'plans'/plan),
                            '--output', str(R/'downloads'/output)], stdout=stdout, stderr=stderr,
                           timeout=timeout, check=False)
    summary = json.loads((R/'downloads'/output/'run-summary.json').read_text())
    record('collection_finished', output=output, returncode=p.returncode, summary=summary)
    return p.returncode, summary

row = next(x for x in processes() if int(x[0]) == PID)
assert 'history_queue.py' in row[3] and '--output research_rounds/current-pool-20261022/downloads/a-tail-queue-01' in row[3]
paused = False
try:
    os.kill(PID, signal.SIGSTOP); paused = True
    record('verified_parent_stopped_child_allowed_to_finish', pid=PID)
    deadline = time.monotonic() + 180
    while any(int(x[1]) == PID and not x[2].startswith('Z') for x in processes()):
        if time.monotonic() > deadline:
            raise RuntimeError('Child wait exceeded bound; no request sent')
        time.sleep(2)
    record('node_idle')
    rc, summary = collect('snapshot_batch.py', 'a-snapshot-pilot-02.json', 'a-snapshot-pilot-02', 120)
    if rc or summary['status'] != 'finished':
        raise RuntimeError('Snapshot pilot failed; full collection skipped')
    rows = json.loads((R/'downloads/a-snapshot-pilot-02/snapshot.json').read_text())['rows']
    assert len(rows) == 8 and all(float(x['raw_fields'].get('3541450') or 0) > 0 for x in rows)
    record('pilot_cap_and_identity_passed', securities=8)
    rc, summary = collect('snapshot_batch.py', 'a-snapshot-all-01.json', 'a-snapshot-all-01', 600)
    if rc or summary['status'] != 'finished':
        raise RuntimeError('Snapshot all halted; FX query skipped')
    collect('history_batch.py', 'fx-history-9602-01.json', 'fx-history-9602-01', 180)
finally:
    if paused:
        os.kill(PID, signal.SIGCONT)
        record('parent_resumed', pid=PID)
