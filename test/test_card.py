import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import card


class TestFormatUid(unittest.TestCase):
    def test_bytes_to_upper_hex(self):
        raw = bytes([0x04, 0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0x80])
        self.assertEqual(card.format_uid(raw), "04A1B2C3D4E580")


class TestNdefCodec(unittest.TestCase):
    def test_encode_known_bytes(self):
        tlv = card.encode_ndef_uri("https://ex.com/a")
        payload = bytes([0x04]) + b"ex.com/a"
        record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload
        expected = bytes([0x03, len(record)]) + record + bytes([0xFE])
        self.assertEqual(tlv, expected)

    def test_roundtrip_full_url(self):
        url = card.BASE + "?n=%EC%B2%A0%EC%88%98&id=04A1B2C3D4E580&s="
        self.assertEqual(card.decode_ndef_uri(card.encode_ndef_uri(url)), url)

    def test_no_prefix_abbreviation(self):
        tlv = card.encode_ndef_uri("ftp://x")
        self.assertEqual(tlv[6], 0x00)  # payload 첫 바이트(prefix code)
        self.assertEqual(card.decode_ndef_uri(tlv), "ftp://x")

    def test_decode_non_ndef_returns_none(self):
        self.assertIsNone(card.decode_ndef_uri(bytes([0x00, 0x00, 0x00, 0x00])))

    def test_decode_corrupted_utf8_returns_none(self):
        # 반쯤 써진 카드: URI 레코드지만 payload에 유효하지 않은 UTF-8(0xFE)
        data = bytes([0x03, 0x06, 0xD1, 0x01, 0x02, 0x55, 0x04, 0xFE, 0xFE])
        self.assertIsNone(card.decode_ndef_uri(data))

    def test_has_ndef(self):
        self.assertTrue(card.has_ndef(card.encode_ndef_uri("https://ex.com/a")))
        self.assertFalse(card.has_ndef(bytes([0x00, 0x00])))

    def test_pad_pages(self):
        self.assertEqual(len(card.pad_pages(b"12345")) % 4, 0)
        self.assertEqual(card.pad_pages(b"1234"), b"1234")
        self.assertEqual(card.pad_pages(b"123"), b"123\x00")

    def test_oversized_uri_raises(self):
        with self.assertRaises(card.CardError):
            card.encode_ndef_uri("x" * 252)   # payload 253 > 250 → raise
        card.encode_ndef_uri("x" * 249)        # payload 250, record 254 → OK


if __name__ == "__main__":
    unittest.main()
