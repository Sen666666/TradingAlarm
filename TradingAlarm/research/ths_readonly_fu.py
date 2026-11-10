"""Read-only access to the client's own 9603 quote node (owner authorization 2026-10-18).

Scope: the owner's session, read-only quote/history queries (id=200/210/211) to the
single 9603 endpoint the local official client was observed using; never orders.
The endpoint is pinned. Other addresses the configured hostname resolves to are not
used. Handshake rejections here are latched in a separate file so that a 9603
rejection cannot stop the 9602 recorder; frames already latched by 9602 are never
sent here either. ths_readonly.py is reused unchanged (its hash is frozen in earlier
protocols).
"""
import json
import socket
from datetime import datetime

import ths_readonly as ths
from sessions import HandshakeRejected, SessionUnavailable, validate_handshake_reply

FU_QUOTE = ('119.3.4.152', 9603)
FU_AUTHORIZATION = dict(
    authorized_on='2026-10-18',
    by='repository owner (本人), in the Cursor task conversation',
    scope='本人同花顺会话，只读行情/历史查询（id=200 名称/快照、id=210 日K、id=211 权息）；绝不下单或调用交易接口',
    purpose='补港股与同花顺 881 行业指数历史（及同节点的中证 UZZI 指数），并加入每日前瞻记录',
    endpoint=f'{FU_QUOTE[0]}:{FU_QUOTE[1]}',
    endpoint_source=dict(
        client_config='~/Library/Containers/cn.com.10jqka.macstock/Data/Documents/DataCenter/DataCenter.xml '
                      'QuoteV2 EndPoint macfu1.123ths.com:9603 (the only 9603 entry; tags include 48 URFI, 120 UZZI, 176 UHK)',
        observed_live='official client process held an ESTABLISHED TCP connection to 119.3.4.152:9603 (lsof, 2026-10-18 ~21:05 +08:00); '
                      'this is the address the client was currently using',
        dns_note='macfu1.123ths.com resolved to 6 A records on 2026-10-18 (122.9.89.1, 8.134.115.93, 119.3.5.222, 116.63.96.36, '
                 '119.3.4.152, 8.134.117.141); only 119.3.4.152 is used. 8.134.115.93 appears in the 2026-10-16 capture from the '
                 'original machine and is not used.'),
    credentials='no ticket, signature or handshake content is stored or logged; only 12-hex frame fingerprints')
FU_LATCH = ths.REPO/'logs/ths-session/rejected-fingerprints-9603.json'


def fu_rejected():
    try:
        return json.loads(FU_LATCH.read_text())
    except (OSError, ValueError):
        return {}


def _latch(manager):
    fp = ths.fingerprint(manager)
    if not fp:
        return
    latched = fu_rejected()
    latched.setdefault(fp, dict(rejected_at=datetime.now().astimezone().isoformat(timespec='seconds'), endpoint=FU_AUTHORIZATION['endpoint']))
    FU_LATCH.parent.mkdir(parents=True, exist_ok=True)
    tmp = FU_LATCH.with_suffix('.tmp')
    tmp.write_text(json.dumps(latched, indent=2)+'\n')
    tmp.replace(FU_LATCH)


def session_candidates(preference='auto'):
    """Same sources as ths_readonly; skips frames latched by either node."""
    latched = set(ths.rejected_fingerprints()) | set(fu_rejected())
    return [(label, m) for label, m in ths.session_candidates(preference, include_latched=True) if ths.fingerprint(m) not in latched]


class FuConnection(ths.Connection):
    """ths_readonly.Connection pinned to FU_QUOTE, with a node-local rejection latch."""

    def __init__(self, manager, interval=.3, max_requests=1500, connect_timeout=8, read_timeout=20, instance_base=960001):
        self.endpoint, self.manager = FU_QUOTE, manager
        self.interval, self.max_requests = interval, max_requests
        self.connect_timeout, self.read_timeout = connect_timeout, read_timeout
        self.instance = instance_base
        self.requests = 0
        self.last = 0.
        self.sock = None
        self.server_time = None

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
            raise ths.NetworkFailure(f'handshake transport {type(exc).__name__}') from None
        finally:
            del wire
        try:
            self.server_time = validate_handshake_reply(reply)
        except HandshakeRejected:
            self.close()
            self.manager.failed(rejected=True)
            _latch(self.manager)
            raise
        finally:
            del reply
        if self.server_time and self.manager.expires and self.server_time >= self.manager.expires.timestamp():
            self.close()
            raise SessionUnavailable('服务器时间显示票据已过期，请在官方客户端重新登录')
        self.manager.success(self.server_time)
        return self


def open_fu(preference='auto', **kw):
    """First accepted source; each tried at most once; network failure stops. Returns (conn, info)."""
    attempts = []
    for label, manager in session_candidates(preference):
        try:
            conn = FuConnection(manager, **kw).open()
            return conn, dict(endpoint=FU_AUTHORIZATION['endpoint'], source=label, fingerprint=ths.fingerprint(manager), attempts=attempts,
                              expires_at=manager.expires.isoformat() if manager.expires else None)
        except HandshakeRejected:
            attempts.append(dict(source=label, result='handshake_rejected_latched_9603', fingerprint=ths.fingerprint(manager)))
        except SessionUnavailable as exc:
            attempts.append(dict(source=label, result='session_unavailable', message=str(exc)))
        except ths.NetworkFailure as exc:
            attempts.append(dict(source=label, result='network_failure', message=str(exc)))
            return None, dict(endpoint=FU_AUTHORIZATION['endpoint'], attempts=attempts, failure='network')
    return None, dict(endpoint=FU_AUTHORIZATION['endpoint'], attempts=attempts, failure='session')
