"""Serve this bounded offline research artifact on loopback only."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
if __name__=='__main__':
    root=Path(__file__).resolve().parent
    server=ThreadingHTTPServer(('127.0.0.1',8769),partial(SimpleHTTPRequestHandler,directory=str(root)))
    print('http://127.0.0.1:8769/',flush=True)
    server.serve_forever()
