import re,struct,pathlib
P=pathlib.Path(__file__).parent
ASM={int(m[1],16):(m[2],m[3].split(';')[0].split('<')[0].strip()) for l in (P/'capture-hxzip.asm').read_text().splitlines() if (m:=re.match(r'([0-9a-f]+): [0-9a-f]+\s+(\S+)\s*(.*)',l))}
def hx_rle(b):
 n=int.from_bytes(b[:4],'big');assert n<10000000
 mem=bytearray(2000000+n);mem[1000:1000+len(b)]=b;r=[0]*32;r[0]=1000000;r[20]=1000;r[22]=n;r[19]=len(b)
 pc=0x1004cc900;cmp=0
 def val(s):
  if s in ('wzr','xzr'):return 0
  if s.startswith('#'):return int(s[1:],0)
  z=r[int(s[1:])];return z&0xffffffff if s[0]=='w' else z
 def put(s,v):r[int(s[1:])]=v & ((1<<(32 if s[0]=='w' else 64))-1)
 for count in range(10000000):
  if pc==0x1004cccc0:
   assert r[8]==1000+len(b),(r[8]-1000,len(b));return bytes(mem[1000000:1000000+n])
  assert pc!=0x1004cccd4,'invalid'
  op,a=ASM[pc];pc+=4;v=[t.strip() for t in a.split(',')]
  if op in ('mov','lsl','add','sub','and','orr'):
   z=val(v[1]);w=val(v[2]) if len(v)>2 else 0
   if len(v)>3:w=w<<int(v[3].split('#')[1],0)
   z={'mov':lambda:z,'lsl':lambda:z<<w,'add':lambda:z+w,'sub':lambda:z-w,'and':lambda:z&w,'orr':lambda:z|w}[op]();put(v[0],z)
  elif op in ('cmp','tst'):cmp=val(v[0])-val(v[1]) if op=='cmp' else val(v[0])&val(v[1])
  elif op.startswith('b.'):
   if {'eq':cmp==0,'ne':cmp!=0,'hi':cmp>0,'lo':cmp<0,'lt':cmp<0}[op[2:]]:pc=int(v[0],16)
  elif op=='b':pc=int(v[0],16)
  elif op in ('tbz','tbnz'):
   yes=bool(val(v[0])&(1<<val(v[1])))
   if yes==(op=='tbnz'):pc=int(v[2],16)
  elif op=='cbz':
   if val(v[0])==0:pc=int(v[1],16)
  elif op in ('ldrb','ldrsb','strb'):
   m=re.match(r'(\w+), \[(\w+)(?:, (#[^\]]+))?\](!)?(?:, (#.+))?',a);dst,base,off,pre,post=m.groups();addr=val(base)+(val(off) if off else 0)
   if pre:put(base,addr)
   if op=='strb':mem[addr]=val(dst)&255
   else:put(dst,mem[addr]-(256 if op=='ldrsb' and mem[addr]>127 else 0))
   if post:put(base,val(base)+val(post))
  else:raise Exception((hex(pc-4),op,a))
 raise Exception('budget')
def hx_table(b):
 rows,head,width,cols,tail=struct.unpack_from('<IIHHI',b,6)
 if b[:6]==b'hx1.3\0':
  length=struct.unpack_from('<I',b,head)[0];r=hx_rle(b[head+4:head+4+length]);assert len(r)==rows*width
  data=bytes(r[c*rows+i] for i in range(rows) for c in range(width))
 else:data=b[head:head+rows*width]
 return rows,width,cols,data
if __name__=='__main__':
 for f in sorted(P.glob('capture-kline-*.bin')):
  b=f.read_bytes();rows,width,cols,data=hx_table(b);print(f.name,rows,struct.unpack_from('<8I',data,0),struct.unpack_from('<8I',data,len(data)-width));(P/(f.stem+'-rows.bin')).write_bytes(data)
