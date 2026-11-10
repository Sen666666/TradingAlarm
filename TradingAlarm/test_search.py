import struct
import unittest
from market import EVIDENCE,frames
from search import decode_search,search_payload

class SearchTests(unittest.TestCase):
    def test_captured_search_responses(self):
        results=[]
        for body in frames((EVIDENCE/'search-response-fixture.bin').read_bytes()):
            if len(body)>=17 and struct.unpack_from('<H',body)[0]==17 and struct.unpack_from('<I',body,6)[0]==8:
                results+=decode_search(body)
        names={r['symbol']:r['name'] for r in results}
        self.assertEqual(names['USHA688331'],'荣昌生物')
        self.assertEqual(names['UHKMHK3750'],'宁德时代')
        self.assertEqual(names['USHD600806'],'退市昆机')

    def test_encoding_and_literal_native_query(self):
        self.assertEqual(search_payload(' gzmt ',42),b'id=8&instance=42&pattern=GZMT&needmarket=')
        self.assertIn('贵州茅台'.encode('gb18030'),search_payload('贵州茅台'))
        for query in ('','&id=200','a\npassword','x'*41):
            with self.assertRaises(ValueError):search_payload(query)

    def test_empty_result_and_wrong_instance(self):
        body=struct.pack('<HIIHIB',17,123,8,0,0,0)
        self.assertEqual(decode_search(body,123),[])
        with self.assertRaises(ValueError):decode_search(body,124)

if __name__=='__main__':unittest.main()
