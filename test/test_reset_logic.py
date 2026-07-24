import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import card
import reset_logic as rl


class TestDescribeCard(unittest.TestCase):
    def test_our_card(self):
        url = card.BASE + "?n=%EC%B2%A0%EC%88%98&id=04E14301544803&s=1,2"
        d = rl.describe_card(url)
        self.assertIn("철수", d)          # parse_qs가 %EC..를 디코드
        self.assertIn("04E14301544803", d)
        self.assertIn("1,2", d)

    def test_no_visits(self):
        url = card.BASE + "?n=%EC%B2%A0%EC%88%98&id=04E14301544803&s="
        self.assertIn("없음", rl.describe_card(url))

    def test_none(self):
        self.assertEqual(rl.describe_card(None), "빈 카드 또는 해독 불가")

    def test_foreign(self):
        self.assertEqual(
            rl.describe_card("https://other.example.com/?id=x"), "우리 카드 아님"
        )


if __name__ == "__main__":
    unittest.main()
