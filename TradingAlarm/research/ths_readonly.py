"""Bounded read-only THS access for new batches. Two verified nodes only.

Credentials are read through sessions.SessionManager and only ever written to
the authorized sockets; callers receive status metadata and 12-hex fingerprints.
"""
import hashlib
import json
import socket
import struct
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from market import decode, bars  # noqa: E402
from search import search_payload, decode_search  # noqa: E402
from sessions import SessionManager, SessionUnavailable, HandshakeRejected, validate_handshake_reply  # noqa: E402

QUOTE = ('119.3.43.91', 9602)
SEARCH = ('8.134.69.102', 9605)
ALLOWED_ENDPOINTS = (QUOTE, SEARCH)
TEMPLATE = REPO/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin'
PRIVATE_SNAPSHOT = REPO/'private/session.bin'
CLIENT_PREFERENCES = tuple(Path.home()/f'Library/Containers/{c}/Data/Library/Preferences/{c}.plist'
                           for c in ('cn.com.10jqka.macstock', 'cn.com.10jqka.macstockPro'))
FRAME_LIMIT = 4*1024*1024
# Local, git-ignored. Holds only truncated frame fingerprints of rejected sessions.
REJECTION_LATCH = REPO/'logs/ths-session/rejected-fingerprints.json'


class NetworkFailure(Exception):
    pass


class BudgetExhausted(Exception):
    pass


def fingerprint(manager):
    manager.load()
    return hashlib.sha256(manager.wire).hexdigest()[:12] if manager.wire else None


def rejected_fingerprints():
    try:
        return json.loads(REJECTION_LATCH.read_text())
    except (OSError, ValueError):
        return {}


def latch_rejection(manager, endpoint):
    """A rejected frame is never resent; only a new client login (new fingerprint) is tried."""
    fp = fingerprint(manager)
    if not fp:
        return
    latched = rejected_fingerprints()
    latched.setdefault(fp, dict(rejected_at=datetime.now().astimezone().isoformat(timespec='seconds'), endpoint=f'{endpoint[0]}:{endpoint[1]}'))
    REJECTION_LATCH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REJECTION_LATCH.with_suffix('.tmp')
    tmp.write_text(json.dumps(latched, indent=2)+'\n')
    tmp.replace(REJECTION_LATCH)


def session_candidates(preference='auto', include_latched=False):
    """Ordered (label, manager): the logged-in client first, migrated snapshot second.
    Sources whose current frame was already rejected are skipped."""
    out = []
    if preference in ('auto', 'client'):
        for path in CLIENT_PREFERENCES:
            if path.exists():
                out.append(('client_preferences', SessionManager(TEMPLATE, preferences_path=path)))
                break
    if preference in ('auto', 'snapshot') and PRIVATE_SNAPSHOT.exists():
        out.append(('private_snapshot', SessionManager(PRIVATE_SNAPSHOT)))
    if include_latched:
        return out
    latched = rejected_fingerprints()
    return [(label, m) for label, m in out if fingerprint(m) not in latched]


def safe_status(label, manager):
    s = manager.status()
    return dict(source=label, state=s['state'], expires_at=s['expiresAt'],
                remaining_days=round(s['remainingSeconds']/86400, 2) if s['remainingSeconds'] is not None else None,
                fingerprint=fingerprint(manager), message=s['message'])


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Connection:
    """One handshake, many paced requests, hard request budget."""

    def __init__(self, endpoint, manager, interval=.3, max_requests=1500, connect_timeout=8, read_timeout=20, instance_base=860001):
        if tuple(endpoint) not in ALLOWED_ENDPOINTS:
            raise ValueError('endpoint is not an authorized THS node')
        self.endpoint, self.manager = tuple(endpoint), manager
        self.interval, self.max_requests = interval, max_requests
        self.connect_timeout, self.read_timeout = connect_timeout, read_timeout
        self.instance = instance_base
        self.requests = 0
        self.last = 0.
        self.sock = None
        self.server_time = None

    def __enter__(self):
        return self if self.sock is not None else self.open()

    def open(self):
        wire = self.manager.prepare()
        try:
            self.sock = socket.create_connection(self.endpoint, timeout=self.connect_timeout)
            self.sock.settimeout(self.read_timeout)
            self.sock.sendall(wire)
            reply = self._frame()
        except (OSError, ValueError) as exc:
            self.close()
            self.manager.failed()
            raise NetworkFailure(f'handshake transport {type(exc).__name__}') from None
        finally:
            del wire
        try:
            self.server_time = validate_handshake_reply(reply)
        except HandshakeRejected:
            self.close()
            self.manager.failed(rejected=True)
            latch_rejection(self.manager, self.endpoint)
            raise
        finally:
            del reply
        if self.server_time and self.manager.expires and self.server_time >= self.manager.expires.timestamp():
            self.close()
            raise SessionUnavailable('服务器时间显示票据已过期，请在官方客户端重新登录')
        self.manager.success(self.server_time)
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _exact(self, size):
        out = bytearray()
        while len(out) < size:
            part = self.sock.recv(size-len(out))
            if not part:
                raise ConnectionError('server closed connection')
            out.extend(part)
        return bytes(out)

    def _frame(self):
        header = self._exact(13)
        if header[:4] != b'\xfd'*4 or header[12] != 9:
            raise ValueError('unsupported frame')
        size = int(header[4:12], 16)
        if size > FRAME_LIMIT:
            raise ValueError('oversized frame')
        return self._exact(size)

    def _send(self, payload):
        if self.sock is None:
            raise NetworkFailure('connection not open')
        if self.requests >= self.max_requests:
            raise BudgetExhausted('request budget exhausted')
        wait = self.interval-(time.monotonic()-self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        self.requests += 1
        try:
            self.sock.sendall(b'\xfd'*4+f'{len(payload):08x}'.encode()+b'\x09'+payload)
        except OSError as exc:
            self.close()
            raise NetworkFailure(f'send {type(exc).__name__}') from None

    def _receive_matching(self, match, frames=16):
        try:
            for _ in range(frames):
                body = self._frame()
                if match(body):
                    return body
        except (OSError, ValueError) as exc:
            self.close()
            raise NetworkFailure(f'receive {type(exc).__name__}') from None
        self.close()
        raise NetworkFailure('no matching response')

    def quote(self, kind, **params):
        """Return (query, raw_body, records-or-None). Raw body never contains credentials."""
        self.instance += 1
        instance = self.instance
        query = dict(id=kind, instance=instance, zipversion=3, **params)
        self._send(urllib.parse.urlencode(query, safe=',').encode())

        def match(body):
            if len(body) < 10:
                return False
            head, inst, k = struct.unpack_from('<HII', body)
            return head == 17 and inst == instance and k == kind
        body = self._receive_matching(match)
        decoded = decode(body, allowed_kinds=(kind,))
        return query, body, (decoded[2] if decoded else None)

    def search(self, pattern):
        self.instance += 1
        instance = self.instance
        payload = search_payload(pattern, instance)
        self._send(payload)

        def match(body):
            return len(body) >= 17 and struct.unpack_from('<I', body, 6)[0] == 8 and struct.unpack_from('<I', body, 2)[0] == instance
        body = self._receive_matching(match, frames=8)
        return payload.decode('gb18030'), body, decode_search(body, instance)


def daily_bars(records):
    return sorted(bars(records or []), key=lambda r: r['date'])
