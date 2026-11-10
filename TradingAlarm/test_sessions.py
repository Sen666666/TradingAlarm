import base64
import tempfile
import plistlib
import struct
import unittest
from datetime import datetime
from pathlib import Path
from sessions import SessionManager,SessionUnavailable,HandshakeRejected,validate_handshake_reply,TZ,build_local_passport

NOW=datetime(2026,10,17,12,tzinfo=TZ).timestamp()
def wire(expiry='2026121106',suffix=''):
    passport=base64.b64encode(('signvalid='+expiry+'\r\n'+suffix).encode())
    body=b'A\0\npassport64='+passport+b'\nVersion=test\n'
    return b'\xfd'*4+f'{len(body):08x}'.encode()+b'\x09'+body

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'session.bin';self.path.write_bytes(wire())
        self.now=NOW;self.session=SessionManager(self.path,clock=lambda:self.now)

    def test_expiry_blocks_network_before_connection(self):
        self.assertEqual(self.session.status()['state'],'ready')
        self.now=datetime(2026,12,11,6,tzinfo=TZ).timestamp()
        with self.assertRaises(SessionUnavailable):self.session.prepare()
        self.assertEqual(self.session.status()['state'],'expired')

    def test_rejection_latches_until_ticket_rotates(self):
        self.session.prepare();self.session.failed(rejected=True)
        self.now+=10000
        self.assertEqual(self.session.status()['state'],'rejected')
        self.path.write_bytes(wire(suffix='new-generation'))
        self.assertEqual(self.session.status()['state'],'ready')
        self.assertEqual(self.session.generation,2)

    def test_network_backoff_bounded(self):
        self.session.prepare()
        for expected in (30,60,120,240,480,900,900):
            self.session.failed();self.assertEqual(self.session.status()['retryAfterSeconds'],expected)
            with self.assertRaises(SessionUnavailable):self.session.prepare()
            self.now+=expected
            self.assertEqual(self.session.status()['state'],'ready')
        self.session.success();self.assertEqual(self.session.failures,0)

    def test_missing_then_same_file_restored(self):
        self.session.prepare();self.path.unlink()
        self.assertEqual(self.session.status()['state'],'missing')
        self.path.write_bytes(wire())
        self.assertEqual(self.session.prepare(),wire())

    def test_handshake_reply_require_explicit_success(self):
        self.assertEqual(validate_handshake_reply(b'A\0Reply=login\r\nVerifyCode=0\r\nTime=1792130916\r\n'),1792130916)
        for body in (b'Reply=login\r\nVerifyCode=1\r\n',b'garbage',b'Reply=unknown\r\nVerifyCode=0\r\n'):
            with self.assertRaises(HandshakeRejected):validate_handshake_reply(body)

    def test_sanitized_success_response_without_network(self):
        # Synthetic fixture retains protocol fields; excludes original account/IP.
        body=b'A\0Reply=login\r\nVerifyCode=0\r\nTime=1792130916\r\n'
        self.assertEqual(validate_handshake_reply(body),1792130916)

    def test_preference_rotation_and_account_binding(self):
        def passport(account='same-account',expiry='2026121106'):
            return 'signhost=test|signdate=2026101700|signvalid='+expiry+'|account='+account+'|signlength=2|ignored'
        initial=build_local_passport(passport(),'BA')
        self.assertEqual(initial[5],1)  # A-P alphabet, low nibble first.
        self.assertEqual(struct.unpack_from('<HBH',initial),(len(initial),45,1))
        body=b'A\0\npassport64='+base64.b64encode(initial)+b'\nVersion=test\n'
        self.path.write_bytes(b'\xfd'*4+f'{len(body):08x}'.encode()+b'\x09'+body)
        prefs=Path(self.temp.name)/'prefs.plist'
        prefs.write_bytes(plistlib.dumps({'HXPassport':passport(),'HXSignature':'BA'}))
        manager=SessionManager(self.path,clock=lambda:self.now,preferences_path=prefs)
        self.assertEqual(manager.status()['state'],'ready')
        manager.failed(rejected=True)
        prefs.write_bytes(plistlib.dumps({'HXPassport':passport(),'HXSignature':'BA','unrelated':True}))
        self.assertEqual(manager.status()['state'],'rejected')
        prefs.write_bytes(plistlib.dumps({'HXPassport':passport(expiry='2026121206'),'HXSignature':'CA'}))
        self.assertEqual(manager.status()['state'],'ready')
        self.assertEqual(manager.generation,2)
        prefs.write_bytes(plistlib.dumps({'HXPassport':passport(account='different-account'),'HXSignature':'CA'}))
        with self.assertRaises(SessionUnavailable):manager.prepare()
        self.assertEqual(manager.status()['state'],'missing')

    def test_status_does_not_contain_credentials(self):
        self.path.write_bytes(wire(suffix='account=synthetic-private-user'))
        status=str(self.session.status());self.assertNotIn('synthetic-private-user',status);self.assertNotIn('passport64',status)

if __name__=='__main__':unittest.main()
