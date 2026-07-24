import sys, os, unittest
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import issue_logic as il


class TestFormatUid(unittest.TestCase):
    def test_bytes_to_upper_hex(self):
        raw = bytes([0x04, 0xA1, 0xB2, 0xC3, 0xD4, 0xE5, 0x80])
        self.assertEqual(il.format_uid(raw), "04A1B2C3D4E580")


class TestBuildUrl(unittest.TestCase):
    def test_basic(self):
        url = il.build_url(il.BASE, "철수", "04A1B2C3D4E580")
        self.assertTrue(url.startswith("https://elderlord.github.io/NFC-stamp/?"))

    def test_matches_viewer_contract(self):
        # 뷰어 parseParams가 읽는 n/id/s 계약과 정합해야 한다
        url = il.build_url(il.BASE, "철수", "04A1B2C3D4E580")
        q = parse_qs(urlparse(url).query, keep_blank_values=True)
        self.assertEqual(q["n"], ["철수"])          # URL 디코드 시 원문 복원
        self.assertEqual(q["id"], ["04A1B2C3D4E580"])
        self.assertEqual(q.get("s"), [""])           # 발급 시 도장 0개(빈값)

    def test_empty_nickname_rejected(self):
        with self.assertRaises(il.IssueError):
            il.build_url(il.BASE, "   ", "04A1B2C3D4E580")

    def test_too_long_nickname_rejected(self):
        with self.assertRaises(il.IssueError):
            il.build_url(il.BASE, "가" * 21, "04A1B2C3D4E580")


class TestCodeValidation(unittest.TestCase):
    def test_gender(self):
        self.assertTrue(il.is_valid_gender("m"))
        self.assertTrue(il.is_valid_gender("f"))
        self.assertFalse(il.is_valid_gender("x"))
        self.assertFalse(il.is_valid_gender("남"))

    def test_age_group(self):
        for n in range(1, 8):
            self.assertTrue(il.is_valid_age_group(n))
        self.assertFalse(il.is_valid_age_group(0))
        self.assertFalse(il.is_valid_age_group(8))


class TestLogFields(unittest.TestCase):
    def test_ok(self):
        row = il.log_fields("2026-07-24T10:00:00", "04A1B2C3D4E580", "철수", "m", 4)
        self.assertEqual(row, ["2026-07-24T10:00:00", "04A1B2C3D4E580", "철수", "m", "4"])

    def test_bad_gender(self):
        with self.assertRaises(il.IssueError):
            il.log_fields("t", "u", "n", "x", 4)

    def test_bad_age(self):
        with self.assertRaises(il.IssueError):
            il.log_fields("t", "u", "n", "m", 9)


class TestNdefCodec(unittest.TestCase):
    def test_encode_known_bytes(self):
        # prefix 0x04 = "https://"
        tlv = il.encode_ndef_uri("https://ex.com/a")
        rest = b"ex.com/a"
        payload = bytes([0x04]) + rest
        record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload
        expected = bytes([0x03, len(record)]) + record + bytes([0xFE])
        self.assertEqual(tlv, expected)

    def test_roundtrip_full_url(self):
        url = il.build_url(il.BASE, "철수", "04A1B2C3D4E580")
        tlv = il.encode_ndef_uri(url)
        self.assertEqual(il.decode_ndef_uri(tlv), url)

    def test_no_prefix_abbreviation(self):
        # https:// 접두사가 없으면 prefix 0x00, 전체 문자열 보존
        tlv = il.encode_ndef_uri("ftp://x")
        self.assertEqual(tlv[6], 0x00)  # record 시작 후 payload 첫 바이트(prefix code)
        self.assertEqual(il.decode_ndef_uri(tlv), "ftp://x")

    def test_decode_non_ndef_returns_none(self):
        self.assertIsNone(il.decode_ndef_uri(bytes([0x00, 0x00, 0x00, 0x00])))

    def test_has_ndef(self):
        tlv = il.encode_ndef_uri("https://ex.com/a")
        self.assertTrue(il.has_ndef(tlv))
        self.assertFalse(il.has_ndef(bytes([0x00, 0x00])))

    def test_pad_pages(self):
        self.assertEqual(len(il.pad_pages(b"12345")) % 4, 0)   # 5 -> 8
        self.assertEqual(il.pad_pages(b"1234"), b"1234")        # 이미 배수
        self.assertEqual(il.pad_pages(b"123"), b"123\x00")


if __name__ == "__main__":
    unittest.main()
