"""THS keyboard search (id=8), recovered from client and captured responses."""
import socket
import struct
from market import snappy
from sessions import validate_handshake_reply

# Matches observed SearchPattern behavior: uppercase and GB18030, raw query value.
def search_payload(query, instance=810001):
    query=query.strip().upper()
    if not query or len(query)>40 or any(ord(c)<32 or c in '&=\x00' for c in query):
        raise ValueError('请输入 1–40 个字符的股票名称、代码或拼音')
    return f'id=8&instance={instance}&pattern={query}&needmarket='.encode('gb18030')

def decode_search(body, instance=None):
    if len(body)<17:
        raise ValueError('搜索响应不完整')
    head,inst,kind,fmt,size,count=struct.unpack_from('<HIIHIB',body)
    if head!=17 or kind!=8 or size!=len(body)-17 or (instance is not None and inst!=instance):
        raise ValueError('搜索响应编号不匹配')
    if fmt==0 and size==0:
        return []
    if fmt!=258 or len(body)<22:
        raise ValueError('搜索响应格式尚不支持')
    blocksize=struct.unpack_from('<I',body,17)[0]
    compressed=body[21:]
    length=shift=0
    for byte in compressed[:5]:
        length|=(byte&127)<<shift
        if byte<128:break
        shift+=7
    if length>2*1024*1024:
        raise ValueError('搜索结果过大')
    raw=snappy(compressed)
    if blocksize!=len(raw) or len(raw)<4:
        raise ValueError('搜索数据长度不匹配')
    textsize=struct.unpack_from('<I',raw)[0]
    if textsize>len(raw)-4:
        raise ValueError('搜索文本不完整')
    text=raw[4:4+textsize].decode('gb18030').split('\0',1)[0]
    result=[];seen=set()
    for line in text.splitlines():
        fields=line.strip().split('|')
        if len(fields)<3:continue
        code,name,market=fields[:3]
        if not code or not name or len(market)!=4 or not market.isascii() or not market.isalpha():continue
        if not code.isascii() or not code.isalnum() or len(code)>20:continue
        symbol=market+code
        if symbol in seen:continue
        seen.add(symbol)
        result.append({'symbol':symbol,'code':code,'name':name,'market':market,'aliases':'','price':None,'previousClose':None,'hasBars':False,'hasIntraday':False,'discoveredOnline':True})
    return result

class SearchClient:
    def __init__(self,session_manager,host='8.134.69.102',port=9605):
        self.session=session_manager;self.host=host;self.port=port;self.server_time=None

    def search(self,query):
        payload=search_payload(query)
        handshake=self.session.prepare()
        def read(sock):
            def exact(size):
                out=bytearray()
                while len(out)<size:
                    chunk=sock.recv(size-len(out))
                    if not chunk:raise ConnectionError('搜索节点关闭了连接')
                    out.extend(chunk)
                return bytes(out)
            h=exact(13)
            if h[:4]!=b'\xfd'*4 or h[12]!=9:raise ValueError('搜索帧格式不支持')
            n=int(h[4:12],16)
            if n>2*1024*1024:raise ValueError('搜索响应过大')
            return exact(n)
        with socket.create_connection((self.host,self.port),timeout=5) as sock:
            sock.settimeout(8);sock.sendall(handshake)
            self.server_time=validate_handshake_reply(read(sock))
            sock.sendall(b'\xfd'*4+f'{len(payload):08x}'.encode()+b'\x09'+payload)
            for _ in range(8):
                body=read(sock)
                if len(body)>=17 and struct.unpack_from('<I',body,6)[0]==8:
                    return decode_search(body,810001)
            raise ValueError('没有收到匹配的搜索结果')
