import sys
import os
import unittest
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import card
import stamp_logic as sl

URL0 = card.BASE + "?n=%EC%B2%A0%EC%88%98&id=04E14301544803&s="       # 철수, s 빈값
URL1 = card.BASE + "?n=%EC%B2%A0%EC%88%98&id=04E14301544803&s=1"      # 1 방문


class TestIsOurUrl(unittest.TestCase):
    def test_our_card(self):
        self.assertTrue(sl.is_our_url(URL0))

    def test_other_domain(self):
        self.assertFalse(sl.is_our_url("https://other.example.com/?id=x"))

    def test_none(self):
        self.assertFalse(sl.is_our_url(None))

    def test_missing_id(self):
        self.assertFalse(sl.is_our_url(card.BASE + "?n=x&s="))

    def test_empty_id(self):
        self.assertFalse(sl.is_our_url(card.BASE + "?n=x&id=&s="))


class TestAddStamp(unittest.TestCase):
    def test_add_to_empty(self):
        new_url, changed = sl.add_stamp(URL0, 1)
        self.assertTrue(changed)
        self.assertEqual(new_url, URL1)

    def test_already_present(self):
        new_url, changed = sl.add_stamp(URL1, 1)
        self.assertFalse(changed)
        self.assertEqual(new_url, URL1)

    def test_add_second(self):
        new_url, changed = sl.add_stamp(URL1, 2)
        self.assertTrue(changed)
        q = parse_qs(urlparse(new_url).query, keep_blank_values=True)
        self.assertEqual(q["s"], ["1,2"])

    def test_preserves_n_and_id_raw(self):
        new_url, _ = sl.add_stamp(URL0, 1)
        self.assertIn("n=%EC%B2%A0%EC%88%98", new_url)   # 재인코딩되지 않음
        self.assertIn("id=04E14301544803", new_url)

    def test_preserves_unknown_number(self):
        url = card.BASE + "?n=x&id=AB&s=1,99"
        new_url, changed = sl.add_stamp(url, 2)
        self.assertTrue(changed)
        q = parse_qs(urlparse(new_url).query, keep_blank_values=True)
        self.assertEqual(q["s"], ["1,99,2"])

    def test_non_decimal_token_ignored(self):
        # "²" is isdigit() True but isdecimal() False and int() would raise
        url = card.BASE + "?n=x&id=AB&s=1,²"
        new_url, changed = sl.add_stamp(url, 2)
        self.assertTrue(changed)
        q = parse_qs(urlparse(new_url).query, keep_blank_values=True)
        self.assertEqual(q["s"], ["1,2"])   # ² dropped, 2 appended


if __name__ == "__main__":
    unittest.main()
