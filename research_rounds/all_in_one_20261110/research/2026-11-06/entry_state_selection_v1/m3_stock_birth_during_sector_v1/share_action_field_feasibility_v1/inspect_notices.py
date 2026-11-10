from pathlib import Path
import subprocess,json
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1/share_action_field_feasibility_v1')
for code in ['603005','000672','300655','688300']:
 p=O/'notices'/(code+'.pdf')
 script='ObjC.import("Foundation"); ObjC.import("PDFKit"); var d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(p))+')); var a=[]; for(var i=0;i<d.pageCount;i++){a.push({page:i+1,text:ObjC.unwrap(d.pageAtIndex(i).string)})}; JSON.stringify({pages:a});'
 r=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,text=True,check=True)
 data=json.loads(r.stdout)
 assert data['pages'] and all(x['text'] for x in data['pages'])
 (O/'notices'/(code+'.text.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 print(code,len(data['pages']),sum(len(x['text']) for x in data['pages']))
for code,page in [('603005',0),('688300',0),('300655',2),('000672',2)]:
 p=O/'notices'/(code+'.pdf'); png=O/'notices'/(code+'.page'+str(page+1)+'.png')
 script='ObjC.import("Foundation"); ObjC.import("AppKit"); ObjC.import("PDFKit"); var d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(p))+')); var im=d.pageAtIndex('+str(page)+').thumbnailOfSizeForBox($.NSMakeSize(1400,1800),$.kPDFDisplayBoxMediaBox); var bm=$.NSBitmapImageRep.imageRepWithData(im.TIFFRepresentation); var data=bm.representationUsingTypeProperties($.NSPNGFileType,$.NSDictionary.dictionary); data.writeToFileAtomically('+json.dumps(str(png))+',true);'
 r=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,text=True,check=True)
 assert png.exists() and png.stat().st_size>10000
 print('rendered',png.name,png.stat().st_size)
