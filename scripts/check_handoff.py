#!/usr/bin/env python3
"""Test an exported tree with a caller-supplied Python research environment."""
import argparse,json,os,subprocess,sys,time,urllib.request
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tree',required=True)
    parser.add_argument('--python',required=True)
    parser.add_argument('--report',required=True)
    parser.add_argument('--private',action='store_true',help='Verify private migration tree with offline networking mode')
    args=parser.parse_args()
    root=Path(args.tree).absolute();app=root/'TradingAlarm';research=app/'research'
    python=os.path.abspath(args.python) # Do not resolve the venv interpreter symlink.
    checks=[]
    for name,command,cwd in [
        ('app_tests',[sys.executable,'-m','unittest','test_market','test_sessions','test_search'],app),
        ('research_tests',[python,'-m','unittest','test_trend_engine','test_campaign_claims','test_monthly_claims','test_trend_slot_engine','test_volume_clock_strength','test_sector_gate_opportunity_audit'],research),
        ('javascript',['node','--check','static/app.js'],app)]:
        p=subprocess.run(command,cwd=cwd,capture_output=True,text=True)
        checks.append(dict(name=name,exit_code=p.returncode,output=(p.stdout+p.stderr)[-3000:]))
        if p.returncode:raise RuntimeError(checks[-1])
    if args.private:
        assert (root/'private/session.bin').is_file()
        assert (root/'artifacts/ths-analysis-20261016/deep/handshake').is_dir()
    else:
        assert not (app/'settings.json').exists()
        assert not (root/'artifacts/ths-analysis-20261016/deep/handshake').exists()
    env=os.environ.copy();env.update(TRADINGALARM_ENABLE_LIVE='0',TRADINGALARM_SESSION_SOURCE='capture',TRADINGALARM_HANDSHAKE='/tmp/no-handoff-ticket')
    p=subprocess.Popen([sys.executable,'server.py','--port','18765'],cwd=app,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        config=None
        for _ in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18765/api/config',timeout=2) as r:config=json.load(r)
                break
            except OSError:time.sleep(.1)
        if config is None:raise RuntimeError('Offline server unavailable; check local socket permissions or port 18765')
        assert config['liveEnabled'] is False and config['searchEnabled'] is False
        for endpoint in ['/','/api/search?q=688008','/api/stocks/USHA688008']:
            with urllib.request.urlopen('http://127.0.0.1:18765'+endpoint,timeout=3) as r:assert r.status==200 and r.read()
        checks.append(dict(name='offline_http',passed=True,stock_count=config['stockCount'],endpoints=4))
    finally:p.terminate();p.wait(timeout=5)
    report=dict(date='2026-10-18',source='private migration tree, forced offline mode' if args.private else 'clean staged export, no settings or handshake',checks=checks,limitations=['Existing Python research environment reused; dependency install not repeated','No remote session requests','Historical experiment suite not fully rerun'])
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False))
if __name__=='__main__':main()
