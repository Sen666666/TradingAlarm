"""Serve this offline report on loopback only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
if __name__=='__main__':
    h=partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).resolve().parent))
    s=ThreadingHTTPServer(('127.0.0.1',8768),h)
    print('2024 selection comparison: http://127.0.0.1:8768/',flush=True)
    s.serve_forever()
