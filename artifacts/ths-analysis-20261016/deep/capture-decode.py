import json,struct,pathlib
P=pathlib.Path(__file__).parent

def snappy(b):
 i=0;n=0;s=0
 while True:
  v=b[i];i+=1;n|=(v&127)<<s;s+=7
  if v<128:break
 out=bytearray()
 while i<len(b):
  t=b[i];i+=1;k=t&3
  if k==0:
   l=t>>2
   if l<60:l+=1
   else:
    c=l-59;l=int.from_bytes(b[i:i+c],'little')+1;i+=c
   out+=b[i:i+l];i+=l
  else:
   if k==1:l=4+((t>>2)&7);off=((t&224)<<3)|b[i];i+=1
   elif k==2:l=1+(t>>2);off=int.from_bytes(b[i:i+2],'little');i+=2
   else:l=1+(t>>2);off=int.from_bytes(b[i:i+4],'little');i+=4
   for _ in range(l):out.append(out[-off])
 assert len(out)==n,(len(out),n)
 return bytes(out)
if __name__=='__main__':
 ss=json.loads((P/'stream-summary.json').read_text());d=(P/'stream-0-server.bin').read_bytes()
 for f in ss[0]['frames']:
  b=d[f['offset']+13:f['offset']+13+f['length']]
  if len(b)>17 and struct.unpack_from('<I',b,6)[0]==210:
   h=b[21:27];raw=snappy(b[27:]);(P/f'capture-kline-{f["offset"]}.bin').write_bytes(h+raw)
   print(f['offset'],h,len(raw),raw[:96].hex())
