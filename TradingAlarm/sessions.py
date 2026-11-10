"""Local passport lifecycle, explicit expiry, rejection latch and bounded retries.
Only safe status metadata is returned to the UI. No passwords are accessed.
"""
import base64
import hashlib
import re
import plistlib
import struct
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Shanghai')
DEFAULT_PREFERENCES = Path.home()/'Library/Containers/cn.com.10jqka.macstockPro/Data/Library/Preferences/cn.com.10jqka.macstockPro.plist'
class SessionUnavailable(Exception):
    pass
class HandshakeRejected(Exception):
    pass

def passport_expiry(body):
    match = re.search(rb'(?:^|[\r\n])passport64=([^\r\n\x00]+)', body)
    if not match:
        raise SessionUnavailable('会话包缺少 passport64，请重新导入本人会话')
    try:
        passport = base64.b64decode(match[1], validate=True)
    except ValueError:
        raise SessionUnavailable('会话票据格式无效') from None
    expiry = re.search(rb'(?:^|[\r\n,])signvalid=(\d{10})(?=[\r\n,\x00]|$)', passport)
    if not expiry:
        raise SessionUnavailable('无法确认票据有效期，请更新本人会话')
    try:
        expires = datetime.strptime(expiry[1].decode(), '%Y%m%d%H').replace(tzinfo=TZ)
    except ValueError:
        raise SessionUnavailable('票据有效期格式无效') from None
    return expires

def validate_handshake_reply(body):
    reply = re.search(rb'(?:^|[\r\n\x00])Reply=([^\r\n\x00]+)', body)
    code = re.search(rb'(?:^|[\r\n\x00])VerifyCode=([^\r\n\x00]+)', body)
    # Observed success is Reply=login and VerifyCode=0. Anything else is not accepted.
    if not reply or reply[1] != b'login' or not code or code[1] != b'0':
        raise HandshakeRejected('行情节点未接受当前会话，请在同花顺重新登录后更新票据')
    stamp = re.search(rb'(?:^|[\r\n\x00])(?:S-)?Time=(\d+)', body)
    return int(stamp[1]) if stamp else None

def build_local_passport(passport, signature):
    if not isinstance(passport,str) or not isinstance(signature,str):
        raise SessionUnavailable('同花顺尚未保存可用票据，请先正常登录')
    if not signature or len(signature)%2 or any(c<'A' or c>'P' for c in signature):
        raise SessionUnavailable('本地签名编码无效')
    if 'signlength=' not in passport:
        raise SessionUnavailable('本地票据格式不支持')
    sig=bytes((ord(signature[i])-65)|((ord(signature[i+1])-65)<<4) for i in range(0,len(signature),2))
    text=(passport.split('signlength=',1)[0].replace('|','\r\n')+'\0').encode('gb18030')
    size=5+len(sig)+len(text)
    if size>16384:
        raise SessionUnavailable('本地票据超出长度限制')
    return struct.pack('<HBH',size,45,len(sig))+sig+text

def account_field(passport):
    if len(passport)<5:
        raise SessionUnavailable('账号绑定校验失败')
    length,kind,siglen=struct.unpack_from('<HBH',passport)
    if length!=len(passport) or kind!=45 or 5+siglen>=length:
        raise SessionUnavailable('账号绑定校验失败')
    match=re.search(rb'(?:^|[\r\n])account=([^\r\n\x00]+)',passport[5+siglen:])
    if not match:
        raise SessionUnavailable('缺少票据账号绑定字段')
    return match[1]

def replace_from_preferences(body, path):
    prefs=plistlib.loads(Path(path).read_bytes())
    passport=build_local_passport(prefs.get('HXPassport'),prefs.get('HXSignature'))
    match=re.search(rb'(?:^|[\r\n])passport64=([^\r\n\x00]+)',body)
    if not match:
        raise SessionUnavailable('握手模板缺少票据字段')
    original=base64.b64decode(match[1],validate=True)
    if account_field(original)!=account_field(passport):
        raise SessionUnavailable('同花顺账号已切换，请先更新对应账号的握手模板')
    return body[:match.start(1)]+base64.b64encode(passport)+body[match.end(1):]

class SessionManager:
    def __init__(self, path, clock=time.time, preferences_path=None):
        self.path = Path(path)
        self.preferences_path = Path(preferences_path) if preferences_path else None
        self.clock = clock
        self.revision = None
        self.wire = None
        self.expires = None
        self.error = None
        self.rejected = False
        self.failures = 0
        self.retry_at = 0
        self.last_success = None
        self.server_skew = 0
        self.generation = 0

    def load(self):
        try:
            # Read only the first frame, not the entire stream.
            with self.path.open('rb') as file:
                header = file.read(13)
                if len(header)!=13 or header[:4]!=b'\xfd'*4 or header[12]!=9:
                    raise SessionUnavailable('会话文件头无效')
                size = int(header[4:12],16)
                if not 0<size<=16384:
                    raise SessionUnavailable('会话包长度无效')
                body = file.read(size)
                if len(body)!=size:
                    raise SessionUnavailable('会话包不完整')
            if self.preferences_path:
                body = replace_from_preferences(body,self.preferences_path)
                header = b'\xfd'*4+f'{len(body):08x}'.encode()+b'\x09'
            expires = passport_expiry(body)
            revision = hashlib.sha256(header+body).digest()
            if revision != self.revision:
                self.revision = revision
                self.wire = header+body
                self.expires = expires
                self.rejected = False
                self.failures = 0
                self.retry_at = 0
                self.generation += 1
                self.last_success = None
            self.wire = header+body
            self.expires = expires
            self.error = None
        except SessionUnavailable as exc:
            self.wire = None
            self.error = str(exc)
        except (OSError,ValueError,plistlib.InvalidFileException):
            self.wire = None
            self.error = '无法读取有效的本人会话文件，请更新后重试'

    def status(self):
        self.load()
        now = self.clock()+self.server_skew
        remaining = self.expires.timestamp()-now if self.expires and self.wire else None
        if self.error:
            state = 'missing'
        elif remaining is None or remaining<=0:
            state = 'expired'
        elif self.rejected:
            state = 'rejected'
        elif self.clock()<self.retry_at:
            state = 'backoff'
        else:
            state = 'ready'
        return {'state':state,'source':'ths_preferences' if self.preferences_path else 'local_capture','expiresAt':self.expires.isoformat() if self.expires else None,
                'remainingSeconds':max(0,int(remaining)) if remaining is not None else None,
                'retryAfterSeconds':max(0,int(self.retry_at-self.clock()+.999)),
                'nearExpiry':remaining is not None and 0<remaining<24*3600,
                'lastSuccess':self.last_success, 'generation':self.generation,
                'message':self.error, 'expiryTimezone':'Asia/Shanghai',
                'renewal':'同花顺正常登录并保存新票据后自动识别；不读取账户密码' if self.preferences_path else '更新捕获文件后自动识别新票据；不读取账户密码'}

    def prepare(self):
        status = self.status()
        messages={'expired':'本人会话已过期，请在同花顺重新登录并更新票据',
                  'rejected':'会话已被服务器拒绝，等待票据更新后再尝试',
                  'backoff':f"连接暂不可用，{status['retryAfterSeconds']} 秒后可重试",'missing':self.error}
        if status['state']!='ready':
            raise SessionUnavailable(messages[status['state']])
        return self.wire

    def success(self, server_time=None):
        if server_time is not None and abs(server_time-self.clock())<7*24*3600:
            self.server_skew=server_time-self.clock()
        self.failures=0
        self.retry_at=0
        self.last_success=datetime.fromtimestamp(self.clock(),TZ).isoformat()

    def failed(self, rejected=False):
        self.rejected=rejected
        self.failures+=1
        self.retry_at=self.clock()+min(900,30*2**min(self.failures-1,5))
