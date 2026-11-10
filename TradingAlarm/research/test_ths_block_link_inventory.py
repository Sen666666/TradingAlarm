import unittest
from ths_block_link_inventory import parse_links
class LinkTests(unittest.TestCase):
 def test_preserves_repeated_keys_and_sections(self):
  rows,unknown=parse_links('[ConfigInfo]\nConfigVer=202610161800\n[stock_24_I_K]\n881201=248:EF2A\n881201=255:ABCD\n[stock_32_I_K]\n881201=248:AAAA\n')
  self.assertEqual(len(rows),3);self.assertEqual(rows[0]['value'],'248:EF2A');self.assertEqual(rows[2]['section'],'stock_32_I_K');self.assertEqual(unknown,[])
 def test_unknown_not_silently_lost(self):
  rows,unknown=parse_links('[x]\nbadline\na=b=c\n');self.assertEqual(rows[0]['value'],'b=c');self.assertEqual(len(unknown),1)
if __name__=='__main__':unittest.main()
