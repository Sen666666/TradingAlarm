"""THS research adapter. Credentials stay in local capture files, never API output."""
import importlib.util
import socket
import struct
import urllib.parse
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent.parent / 'artifacts/ths-analysis-20261016/deep'

def load_module(name):
    spec = importlib.util.spec_from_file_location(name, EVIDENCE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

snappy = load_module('capture-decode').snappy
hx_table = load_module('capture-hxdecode').hx_table

def frames(data):
    offset = 0
    while offset + 13 <= len(data):
        if data[offset:offset+4] != b'\xfd' * 4:
            raise ValueError('Unsupported frame boundary')
        length = int(data[offset+4:offset+12], 16)
        end = offset + 13 + length
        if end > len(data):
            raise ValueError('Incomplete frame')
        yield data[offset+13:end]
        offset = end

def numeric(raw):
    if raw in (0x80000000, 0xffffffff):
        return None
    scale = 10 ** ((raw >> 28) & 7)
    value = (raw & 0x7ffffff) / scale if raw & 0x80000000 else (raw & 0x7ffffff) * scale
    return -value if raw & 0x8000000 else value

def decode(body, allowed_kinds=(200, 207, 210)):
    if len(body) < 17:
        return None
    head, instance, kind, fmt, length, count = struct.unpack_from('<HIIHIB', body)
    if head != 17 or kind not in allowed_kinds:
        return None
    if fmt == 0:
        return kind, instance, []
    if fmt != 1 or length != len(body) - 17 or len(body) < 27:
        raise ValueError('Unsupported quote response')
    marker = body[21:27]
    if marker in (b'hx1.2\0', b'hx1.3\0'):
        compressed = body[27:]
        # Snappy announces output length as varint; cap before allocation.
        size = shift = 0
        for byte in compressed[:5]:
            size |= (byte & 127) << shift
            if byte < 128:
                break
            shift += 7
        if size > 8 * 1024 * 1024:
            raise ValueError('Decoded data too large')
        raw = marker + snappy(compressed)
    elif marker == b'hx1.0\0':
        raw = body[21:]
    elif marker == b'hx1.1\0':
        # RLE/transposed table without the outer Snappy layer. The retained
        # hx_table implementation selects this inner layout via hx1.3.
        raw = b'hx1.3\0' + body[27:]
    else:
        raise ValueError('Unsupported compression')
    rows, width, columns, data = hx_table(raw)
    descriptors = [struct.unpack_from('<IBBH', raw, 22 + j * 8) for j in range(columns)]
    if sum(x[3] for x in descriptors) != width or len(data) != rows * width:
        raise ValueError('Invalid table dimensions')
    records = []
    for i in range(rows):
        pos = i * width
        record = {}
        for field, typ, charset, width_ in descriptors:
            value = data[pos:pos+width_]
            pos += width_
            if typ == 2 and width_ == 4:
                value = numeric(int.from_bytes(value, 'little'))
            elif typ == 4 and width_ == 4:
                value = int.from_bytes(value, 'little')
            elif typ == 1:
                value = value.split(b'\0')[0].decode('utf-8' if charset == 1 else 'gb18030', errors='replace')
            else:
                value = value.hex()
            record[str(field)] = value
        records.append(record)
    return kind, instance, records

def minute_stamp(value):
    # Packed calendar: 7-bit year since 1900, month, day, hour, minute.
    import datetime
    year, month, day = 1900 + (value >> 20), (value >> 16) & 15, (value >> 11) & 31
    hour, minute = (value >> 6) & 31, value & 63
    dt = datetime.datetime(year, month, day, hour, minute)
    return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')

def bars(records):
    return [{'date': f"{str(r['1'])[:4]}-{str(r['1'])[4:6]}-{str(r['1'])[6:8]}",
             **{key:r.get(field) for key,field in [('open','7'),('high','8'),('low','9'),('close','11'),('volume','13'),('amount','19')]}}
            for r in records if r.get('1') and all(isinstance(r.get(k), (int,float)) for k in ('7','8','9','11'))]

def minutes(records):
    result = []
    previous_date = None
    prior_volume = prior_amount = 0
    for row in records:
        if row.get('1') is None or row.get('10') is None:
            continue
        date, time = minute_stamp(row['1'])
        if date != previous_date:
            prior_volume = prior_amount = 0
        total_volume, total_amount = row.get('13'), row.get('19')
        volume = total_volume-prior_volume if isinstance(total_volume,(int,float)) and isinstance(prior_volume,(int,float)) and total_volume >= prior_volume else None
        amount = total_amount-prior_amount if isinstance(total_amount,(int,float)) and isinstance(prior_amount,(int,float)) and total_amount >= prior_amount else None
        result.append({'date':date, 'time':time, 'price':row['10'], 'volume':volume, 'amount':amount, 'cumulativeVolume':total_volume, 'cumulativeAmount':total_amount})
        previous_date, prior_volume, prior_amount = date, total_volume, total_amount
    return result

class SessionClient:
    """Explicit opt-in only. One short connection per selected-stock refresh."""
    def __init__(self, host, port, handshake_path=None, session_manager=None):
        self.host, self.port, self.handshake_path = host, port, handshake_path
        self.session_manager = session_manager
        self.server_time = None

    def fetch(self, symbol):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        market, code = symbol[:4], symbol[4:]
        today = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d')
        from sessions import SessionManager, validate_handshake_reply, SessionUnavailable
        manager = self.session_manager or SessionManager(self.handshake_path)
        handshake = manager.prepare()
        queries = [dict(id=200, codelist=code, market=market, datatype='5,6,7,8,9,10,13,19,55'),
                   dict(id=207, code=code, market=market, datatype='1,10,13,19,40,41', date=0),
                   dict(id=210, code=code, market=market, start=-749, end=today, fuquan='Q', datatype='1,7,8,9,11,13,19,74', period=16384)]
        results = {}
        def receive(sock):
            def exact(size):
                chunks = bytearray()
                while len(chunks) < size:
                    chunk = sock.recv(size - len(chunks))
                    if not chunk:
                        raise ConnectionError('会话被服务器关闭，可能需要重新登录')
                    chunks.extend(chunk)
                return bytes(chunks)
            header = exact(13)
            if header[:4] != b'\xfd' * 4 or header[12] != 9:
                raise ValueError('不支持的响应帧')
            size = int(header[4:12], 16)
            if size > 4 * 1024 * 1024:
                raise ValueError('响应超过大小限制')
            return exact(size)
        with socket.create_connection((self.host, self.port), timeout=5) as sock:
            sock.settimeout(8)
            sock.sendall(handshake)
            self.server_time = validate_handshake_reply(receive(sock))
            if self.server_time and manager.expires and self.server_time >= manager.expires.timestamp():
                raise SessionUnavailable('服务器时间显示票据已过期，请更新本人会话')
            for index, query in enumerate(queries, 800001):
                query.update(instance=index, zipversion=3)
                payload = urllib.parse.urlencode(query, safe=',').encode()
                sock.sendall(b'\xfd'*4 + f'{len(payload):08x}'.encode() + b'\x09' + payload)
                for _ in range(16):
                    decoded = decode(receive(sock))
                    if decoded and decoded[:2] == (query['id'], index):
                        results[query['id']] = decoded[2]
                        break
                else:
                    raise ValueError('未收到匹配的行情响应')
        if not results.get(200):
            raise ValueError('服务器没有返回该股票的报价')
        return {'quote':results[200][0], 'intraday':minutes(results.get(207, [])), 'bars':bars(results.get(210, []))}
