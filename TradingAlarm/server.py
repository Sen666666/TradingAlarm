#!/usr/bin/env python3
"""TradingAlarm local application, Python standard library only."""
import argparse
import json
import os
import secrets
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from sessions import SessionManager, SessionUnavailable, HandshakeRejected, DEFAULT_PREFERENCES

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT/'data/market.json').read_text())
STOCKS = {s['symbol']:s for s in DATA['stocks']}
DISCOVERED_PATH=ROOT/'data/discovered.json'
if DISCOVERED_PATH.exists():
    for item in json.loads(DISCOVERED_PATH.read_text()):
        if item['symbol'] not in STOCKS:
            STOCKS[item['symbol']]=item | {'quote':{},'bars':[],'intraday':[],'capturedAt':'','discoveredOnline':True}
SETTINGS_PATH = ROOT/'settings.json'
SETTINGS = json.loads(SETTINGS_PATH.read_text()) if SETTINGS_PATH.exists() else {}
LIVE = os.environ.get('TRADINGALARM_ENABLE_LIVE','1' if SETTINGS.get('liveEnabled') else '0') == '1'
TOKEN = secrets.token_urlsafe(32)
SEARCH_ENABLED = LIVE and SETTINGS.get("searchEnabled",False)
SEARCH_CACHE = {}
CACHE = {}
LOCK = threading.Lock()
from desk.service import Desk
DESK = Desk(Path(os.environ.get('TRADINGALARM_RUNTIME', ROOT/'runtime')))
DESK.paper.live = LIVE
TEST_MODE = os.environ.get('TRADINGALARM_TEST_MODE') == '1'
if TEST_MODE and not str(DESK.runtime.resolve()).startswith(('/private/tmp/', '/tmp/')):
    raise RuntimeError('隔离界面测试只允许使用临时目录中的数据库')
SESSION = SessionManager(os.environ.get('TRADINGALARM_HANDSHAKE',str(ROOT.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin')), preferences_path=None if os.environ.get('TRADINGALARM_SESSION_SOURCE')=='capture' else DEFAULT_PREFERENCES)

def summary(stock):
    q = stock['quote']
    return {k:stock[k] for k in ('symbol','code','name','market','aliases')} | {'price':q.get('10'),'previousClose':q.get('6'),'hasBars':bool(stock['bars']),'hasIntraday':bool(stock['intraday']),'discoveredOnline':bool(stock.get('discoveredOnline'))}

class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def trusted_host(self):
        return self.headers.get('Host','').split(':')[0] in ('127.0.0.1','localhost')

    def do_GET(self):
        if not self.trusted_host():
            return self.send(403, {'error':'仅支持本机访问'})
        url = urlparse(self.path)
        if url.path == '/api/paper':
            try:
                return self.send(200, DESK.paper.view())
            except Exception:
                return self.send(500, {'error':'模拟仓读取失败，请检查本地服务日志'})
        if url.path.startswith('/api/desk'):
            try:
                if url.path == '/api/desk':
                    return self.send(200, DESK.overview())
                if url.path == '/api/desk/chart':
                    symbol = parse_qs(url.query).get('symbol', [''])[0]
                    return self.send(200, DESK.data.chart(symbol))
                if url.path == '/api/desk/trades':
                    from desk.store import effective_events
                    rows=DESK.store.events()
                    return self.send(200, {'events':effective_events(rows),'audit_events':rows})
            except (ValueError, KeyError) as exc:
                return self.send(400, {'error': str(exc)})
            except Exception:
                return self.send(500, {'error': '交易台资料读取失败，请检查本地服务日志'})
        if url.path == '/api/config':
            return self.send(200, {'name':'TradingAlarm','liveEnabled':LIVE,'csrf':TOKEN,'source':'capture','capturedAt':DATA['capturedAt'],'stockCount':len(STOCKS),'searchEnabled':SEARCH_ENABLED,'testMode':TEST_MODE})
        if url.path == '/api/session':
            with LOCK:
                return self.send(200,SESSION.status() | {'enabled':LIVE})
        if url.path == '/api/search':
            query = parse_qs(url.query).get('q',[''])[0].casefold().strip()[:80]
            result = [summary(s) for s in list(STOCKS.values()) if query in ' '.join(str(s[k]) for k in ('symbol','code','name','aliases')).casefold()]
            result.sort(key=lambda s:(s['symbol']!='USHA688008',not s['hasBars'],not s['hasIntraday'],s['code']))
            return self.send(200, {'stocks':result})
        if url.path.startswith('/api/stocks/'):
            symbol = url.path.rsplit('/',1)[-1]
            if symbol not in STOCKS:
                return self.send(404, {'error':'没有找到该股票'})
            return self.send(200, STOCKS[symbol] | {'source':'capture'})
        files = {'/':'desk.html','/simulation':'paper.html','/paper.js':'paper.js','/paper.css':'paper.css','/quotes':'index.html','/desk.js':'desk.js','/desk.css':'desk.css','/app.js':'app.js','/style.css':'style.css','/favicon.svg':'favicon.svg'}
        if url.path not in files:
            return self.send(404, {'error':'页面不存在'})
        file = ROOT/'static'/files[url.path]
        content_type = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml'}[file.suffix]
        return self.send(200, file.read_bytes(), content_type)

    def do_POST(self):
        if not self.trusted_host():
            return self.send(403, {'error':'仅支持本机访问'})
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://'+self.headers.get('Host',''),):
            return self.send(403, {'error':'请求来源不匹配'})
        desk_routes = ('/api/desk/account','/api/desk/trades','/api/desk/corporate','/api/desk/size','/api/desk/refresh','/api/desk/schedule','/api/paper/start','/api/paper/sync')
        if self.path not in ('/api/refresh','/api/search') + desk_routes:
            return self.send(404, {'error':'接口不存在'})
        if self.headers.get('X-TradingAlarm-Token') != TOKEN:
            return self.send(403, {'error':'请从本机应用发起刷新'})
        if self.path in desk_routes:
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('请求参数无效')
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError('请求参数无效')
                if self.path == '/api/paper/start':
                    result = DESK.paper.start()
                elif self.path == '/api/paper/sync':
                    result = DESK.paper.request_sync()
                elif self.path == '/api/desk/account':
                    result = DESK.initialize(payload)
                elif self.path == '/api/desk/trades':
                    result = DESK.record_trade(payload)
                elif self.path == '/api/desk/corporate':
                    result = DESK.record_corporate(payload)
                elif self.path == '/api/desk/size':
                    result = DESK.size_open(payload)
                elif self.path == '/api/desk/schedule':
                    if type(payload.get('enabled')) is not bool:
                        raise ValueError('定时设置无效')
                    result = dict(enabled=payload['enabled'], time='15:30')
                    DESK.store.set_setting('schedule', result)
                else:
                    if not LIVE:
                        return self.send(409, {'error':'同花顺在线行情未启用'})
                    result = DESK.refresh()
                return self.send(200, result)
            except (ValueError, TypeError) as exc:
                return self.send(400, {'error':str(exc)})
            except Exception:
                return self.send(500, {'error':'本地账本操作失败，原记录保持不变'})
        if self.path == '/api/search':
            return self.online_search()
        if not LIVE:
            return self.send(409, {'error':'当前为采集数据模式。在线模式需要显式启用本人会话。'})
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 1024:
                raise ValueError()
            symbol = json.loads(self.rfile.read(length)).get('symbol')
            if symbol not in STOCKS or STOCKS[symbol]['market'] not in ('USHA','USHJ','USHI','USZA','USZJ','USZI'):
                return self.send(400, {'error':'当前在线适配器只支持已有目录内的 A 股市场标的'})
        except (ValueError, TypeError):
            return self.send(400, {'error':'请求参数无效'})
        with LOCK:
            session_status = SESSION.status()
            cached = CACHE.get(symbol)
            if cached and cached[2] == SESSION.generation and time.monotonic()-cached[0] < 60 and session_status['state'] == 'ready':
                return self.send(200,cached[1])
            try:
                SESSION.prepare()
                from market import SessionClient
                client = SessionClient(os.environ.get('TRADINGALARM_HOST','119.3.43.91'),int(os.environ.get('TRADINGALARM_PORT','9602')),session_manager=SESSION)
                received = client.fetch(symbol)
                SESSION.success(client.server_time)
                value = STOCKS[symbol] | received | {'source':'live','capturedAt':datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')}
                CACHE[symbol] = (time.monotonic(),value,SESSION.generation)
                return self.send(200,value)
            except SessionUnavailable as exc:
                return self.send(409, {'error':str(exc), 'session':SESSION.status()})
            except HandshakeRejected:
                SESSION.failed(rejected=True)
                return self.send(401, {'error':'当前会话未被行情节点接受；已停止重试，等待本人票据更新。', 'session':SESSION.status()})
            except Exception:
                SESSION.failed()
                return self.send(502, {'error':'在线取数失败，已进入退避等待并保留已有数据。', 'session':SESSION.status()})

    def online_search(self):
        if not SEARCH_ENABLED:
            return self.send(409,{'error':'在线搜索尚未启用，仍可使用本地搜索'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024:raise ValueError()
            payload=json.loads(self.rfile.read(length))
            query=payload.get('query')
            if not isinstance(query,str):raise ValueError()
            from search import SearchClient, search_payload
            search_payload(query)
        except (ValueError,TypeError,AttributeError,UnicodeError):
            return self.send(400,{'error':'请输入 1–40 个字符的股票名称、代码或拼音'})
        with LOCK:
            try:
                SESSION.prepare()
                key=(SESSION.generation,query.strip().upper())
                cached=SEARCH_CACHE.get(key)
                if cached and time.monotonic()-cached[0]<300:
                    result=cached[1]
                else:
                    client=SearchClient(SESSION)
                    result=client.search(query)
                    SESSION.success(client.server_time)
                    if len(SEARCH_CACHE)>=256:SEARCH_CACHE.pop(next(iter(SEARCH_CACHE)))
                    SEARCH_CACHE[key]=(time.monotonic(),result)
                response=[]
                for item in result:
                    symbol=item['symbol']
                    if symbol not in STOCKS:
                        STOCKS[symbol]={k:item[k] for k in ('symbol','code','name','market','aliases')} | {'quote':{},'bars':[],'intraday':[],'capturedAt':'','discoveredOnline':True}
                    else:
                        STOCKS[symbol]['name']=item['name']
                    response.append(summary(STOCKS[symbol]) | {'discoveredOnline':bool(STOCKS[symbol].get('discoveredOnline')), 'liveSupported':item['market'] in ('USHA','USHJ','USHI','USZA','USZJ','USZI')})
                discovered=[{k:s[k] for k in ('symbol','code','name','market','aliases')} for s in STOCKS.values() if s.get('discoveredOnline')]
                temp=DISCOVERED_PATH.with_suffix('.tmp')
                temp.write_text(json.dumps(discovered,ensure_ascii=False))
                temp.replace(DISCOVERED_PATH)
                return self.send(200,{'stocks':response,'source':'online','query':query})
            except SessionUnavailable as exc:
                return self.send(409,{'error':str(exc)})
            except HandshakeRejected:
                SESSION.failed(rejected=True)
                return self.send(401,{'error':'搜索节点未接受当前会话，请更新本人票据'})
            except Exception:
                SESSION.failed()
                return self.send(502,{'error':'在线搜索暂不可用，已保留本地搜索结果，请稍后重试'})

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    def scheduler():
        while True:
            try:
                DESK.paper.tick()
                if LIVE:
                    DESK.tick()
            except Exception:
                pass
            time.sleep(30)
    threading.Thread(target=scheduler, daemon=True, name='desk-scheduler').start()
    print(f'TradingAlarm http://127.0.0.1:{args.port} | mode={"live-enabled" if LIVE else "capture"}',flush=True)
    server.serve_forever()
