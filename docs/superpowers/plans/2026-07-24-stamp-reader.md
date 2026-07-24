# 도장 찍기 (전시관 리더) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전시관 리더가 카드 URL을 읽어 `s`에 자기 전시관 번호를 더해 다시 굽는 도장 찍기 기능을 만든다.

**Architecture:** 발급 스테이션과 공유하는 카드/NDEF/URL 로직을 `scripts/card.py`로 추출하고(발급·도장·향후 초기화 공용), 도장 전용 순수 로직은 `scripts/stamp_logic.py`, 하드웨어 리더는 `scripts/pn532_stamp.py`에 둔다. 리더는 자기 번호만 설정 파일에서 읽고, 우리 카드가 아니거나 이미 방문한 곳이면 절대 쓰지 않는다.

**Tech Stack:** Python 3, adafruit-circuitpython-pn532(설치됨), 표준 라이브러리, 테스트는 `python -m unittest`.

## Global Constraints

- 새 외부 의존성 추가 금지. adafruit(설치됨) + 표준 라이브러리만.
- `BASE` = `https://elderlord.github.io/NFC-stamp/` (뷰어·발급과 정확히 일치).
- 카드 URL 파라미터 = `n`, `id`, `s` (뷰어 계약). 리더는 `s`에 자기 번호만 중복 없이 추가하고 **`n`·`id`는 원문 그대로 보존**한다.
- 리더는 우리 카드(BASE로 시작 + `id` 존재)에만 쓴다. 빈 카드·남의 태그엔 **절대 쓰지 않음**.
- 리더 전시관 번호 = `data/exhibit_id`(gitignore된 `data/` 안, 양의 정수).
- 리팩터 후 **기존 발급 동작·테스트가 전부 통과**해야 한다(회귀 금지).
- 순수 로직은 TDD. 하드웨어 I/O(`pn532_stamp.py`)는 자동 테스트 불가 → 수동 검증.

---

### Task 1: 공유 카드 모듈 추출 (card.py 리팩터)

`issue_logic.py`의 범용 부분을 `card.py`로 옮기고, 발급 코드·테스트가 그대로 통과하도록 재배선한다. 안전망은 기존 테스트다.

**Files:**
- Create: `scripts/card.py`
- Rewrite: `scripts/issue_logic.py`
- Create: `test/test_card.py`
- Rewrite: `test/test_issue_logic.py`
- (변경 없음) `scripts/pn532_issue.py` — `il.*` 재노출로 그대로 동작

**Interfaces:**
- Produces (card.py): `BASE`, `CardError`, `format_uid(raw)`, `encode_ndef_uri(url)`, `decode_ndef_uri(data)`, `has_ndef(data)`, `pad_pages(tlv)`
- Produces (issue_logic.py, 유지): `build_url`, `log_fields`, `is_valid_gender`, `is_valid_age_group`, `GENDERS`, `AGE_GROUPS`, `MAX_NICKNAME_LEN`, `LOG_HEADER`, `GENDER_LABELS`, `AGE_LABELS`, `IssueError`(= `card.CardError` 별칭), + card 재노출 심볼

- [ ] **Step 1: Create `scripts/card.py`**

```python
"""공유 카드/NDEF/URL 로직 — 발급·도장·초기화가 공통으로 쓴다. 하드웨어 없음."""

BASE = "https://elderlord.github.io/NFC-stamp/"


class CardError(ValueError):
    """카드/URL 처리 검증 실패."""


def format_uid(raw):
    """UID 바이트 → 대문자 hex 문자열(구분자 없음)."""
    return "".join(f"{b:02X}" for b in raw)


# --- NDEF URI 코덱 ---
_URI_PREFIXES = {
    0x00: "",
    0x01: "http://www.",
    0x02: "https://www.",
    0x03: "http://",
    0x04: "https://",
}
_PREFIX_MATCH = [
    (0x02, "https://www."),
    (0x01, "http://www."),
    (0x04, "https://"),
    (0x03, "http://"),
]


def encode_ndef_uri(url):
    """URI 문자열 → NTAG에 쓸 NDEF 메시지 TLV 바이트 (03 <len> <record> FE)."""
    prefix_code = 0x00
    rest = url
    for code, p in _PREFIX_MATCH:
        if url.startswith(p):
            prefix_code = code
            rest = url[len(p):]
            break
    payload = bytes([prefix_code]) + rest.encode("utf-8")
    if len(payload) > 250:
        raise CardError("URI가 너무 깁니다(단일 NDEF 레코드 한도 초과)")
    record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    return tlv


def decode_ndef_uri(data):
    """NTAG 사용자 메모리 바이트 → URI 문자열. NDEF URI 레코드가 아니면 None."""
    if len(data) < 2 or data[0] != 0x03:
        return None
    msg_len = data[1]
    record = data[2:2 + msg_len]
    if len(record) < 4 or record[3] != 0x55:
        return None
    payload_len = record[2]
    payload = record[4:4 + payload_len]
    if not payload:
        return None
    prefix = _URI_PREFIXES.get(payload[0], "")
    return prefix + payload[1:].decode("utf-8")


def has_ndef(data):
    """사용자 메모리 첫 바이트로 기존 NDEF 존재 판정."""
    return len(data) >= 2 and data[0] == 0x03 and data[1] > 0


def pad_pages(tlv):
    """4바이트 페이지 배수로 0x00 패딩."""
    return tlv + bytes((-len(tlv)) % 4)
```

- [ ] **Step 2: Rewrite `scripts/issue_logic.py`** (발급 전용만 남기고 공유분은 card에서 import)

```python
"""발급 스테이션 전용 로직 — 공유분은 card.py에서 가져온다. 하드웨어 없음."""

from urllib.parse import quote

from card import (  # noqa: F401  발급 코드·테스트 하위호환을 위한 재노출
    BASE,
    CardError,
    format_uid,
    encode_ndef_uri,
    decode_ndef_uri,
    has_ndef,
    pad_pages,
)

# 하위호환 별칭: 기존 발급 코드·테스트가 il.IssueError를 참조
IssueError = CardError

GENDERS = {"m", "f"}
AGE_GROUPS = set(range(1, 8))  # 1..7
MAX_NICKNAME_LEN = 20

LOG_HEADER = ["issued_at", "uid", "nickname", "gender", "age_group"]

GENDER_LABELS = {"m": "남", "f": "여"}
AGE_LABELS = {
    1: "초등 저학년(1~3)",
    2: "초등 고학년(4~6)",
    3: "10대(중학생 이상)",
    4: "20대",
    5: "30대",
    6: "40대",
    7: "50대 이상",
}


def is_valid_gender(code):
    return code in GENDERS


def is_valid_age_group(n):
    return n in AGE_GROUPS


def build_url(base, nickname, uid):
    """개인화 URL 조립. 발급 시 s는 빈값(도장 0개)."""
    nickname = nickname.strip()
    if not nickname:
        raise IssueError("닉네임이 비어 있습니다")
    if len(nickname) > MAX_NICKNAME_LEN:
        raise IssueError(f"닉네임이 너무 깁니다(최대 {MAX_NICKNAME_LEN}자)")
    return f"{base}?n={quote(nickname)}&id={uid}&s="


def log_fields(issued_at, uid, nickname, gender, age_group):
    """로그 CSV 한 행의 값 리스트. 파일 기록은 csv 모듈이 이스케이프."""
    if not is_valid_gender(gender):
        raise IssueError(f"잘못된 성별 코드: {gender}")
    if not is_valid_age_group(age_group):
        raise IssueError(f"잘못된 연령대 코드: {age_group}")
    return [issued_at, uid, nickname, gender, str(age_group)]
```

- [ ] **Step 3: Create `test/test_card.py`** (기존 test_issue_logic의 UID·NDEF 테스트를 여기로 이동)

```python
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
```

- [ ] **Step 4: Rewrite `test/test_issue_logic.py`** (발급 전용 테스트만 남김 — UID·NDEF 테스트는 test_card로 이동됨)

```python
import sys
import os
import unittest
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import issue_logic as il


class TestBuildUrl(unittest.TestCase):
    def test_basic(self):
        url = il.build_url(il.BASE, "철수", "04A1B2C3D4E580")
        self.assertTrue(url.startswith("https://elderlord.github.io/NFC-stamp/?"))

    def test_matches_viewer_contract(self):
        url = il.build_url(il.BASE, "철수", "04A1B2C3D4E580")
        q = parse_qs(urlparse(url).query, keep_blank_values=True)
        self.assertEqual(q["n"], ["철수"])
        self.assertEqual(q["id"], ["04A1B2C3D4E580"])
        self.assertEqual(q.get("s"), [""])

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Run the full suite — no regression**

Run: `python -m unittest discover -s test -v`
Expected: PASS, 17 tests total (test_card 8 + test_issue_logic 9).

- [ ] **Step 6: Confirm issue CLI still resolves its symbols**

Run:
```bash
python -m py_compile scripts/pn532_issue.py
python -c "import sys; sys.path.insert(0,'scripts'); import issue_logic as il; [getattr(il,n) for n in ['BASE','format_uid','encode_ndef_uri','decode_ndef_uri','has_ndef','pad_pages','IssueError','build_url','log_fields','LOG_HEADER','MAX_NICKNAME_LEN','is_valid_age_group']]; print('symbols ok')"
```
Expected: `symbols ok` (재노출로 pn532_issue.py의 `il.*`가 전부 해결됨).

- [ ] **Step 7: Commit**

```bash
git add scripts/card.py scripts/issue_logic.py test/test_card.py test/test_issue_logic.py
git commit -m "Extract shared card/NDEF logic into card.py"
```

---

### Task 2: 도장 순수 로직 (stamp_logic.py)

**Files:**
- Create: `scripts/stamp_logic.py`
- Test: `test/test_stamp_logic.py`

**Interfaces:**
- Consumes: `card.BASE`
- Produces:
  - `is_our_url(url: str | None) -> bool`
  - `add_stamp(url: str, exhibit_id: int) -> tuple[str, bool]`

- [ ] **Step 1: Write the failing tests**

Create `test/test_stamp_logic.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest test.test_stamp_logic -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'stamp_logic'`

- [ ] **Step 3: Write the implementation**

Create `scripts/stamp_logic.py`:

```python
"""도장 리더 순수 로직 — 하드웨어 없음, 단위 테스트 대상."""

from urllib.parse import urlparse, parse_qs

from card import BASE


def is_our_url(url):
    """우리 카드 URL인지: BASE로 시작 + id 파라미터가 비어있지 않음."""
    if not url or not url.startswith(BASE):
        return False
    q = parse_qs(urlparse(url).query, keep_blank_values=True)
    return bool(q.get("id", [""])[0])


def _split_query(url):
    """URL을 (물음표 앞부분, [(key, raw_value), ...])로 나눈다. 값 원문 보존."""
    base, _, query = url.partition("?")
    pairs = []
    if query:
        for part in query.split("&"):
            key, _, val = part.partition("=")
            pairs.append((key, val))
    return base, pairs


def add_stamp(url, exhibit_id):
    """s에 exhibit_id를 중복 없이 추가. (new_url, changed) 반환. n·id 원문 보존."""
    base, pairs = _split_query(url)
    s_raw = ""
    for key, val in pairs:
        if key == "s":
            s_raw = val

    seen = []
    for tok in s_raw.split(","):
        tok = tok.strip()
        if tok.isdigit() and int(tok) not in seen:
            seen.append(int(tok))

    if exhibit_id in seen:
        return url, False

    seen.append(exhibit_id)
    new_s = ",".join(str(x) for x in seen)

    new_pairs = []
    replaced = False
    for key, val in pairs:
        if key == "s":
            new_pairs.append((key, new_s))
            replaced = True
        else:
            new_pairs.append((key, val))
    if not replaced:
        new_pairs.append(("s", new_s))

    new_query = "&".join(f"{k}={v}" for k, v in new_pairs)
    return f"{base}?{new_query}", True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest test.test_stamp_logic -v`
Expected: PASS (전체)

- [ ] **Step 5: Commit**

```bash
git add scripts/stamp_logic.py test/test_stamp_logic.py
git commit -m "Add stamp reader pure logic (is_our_url, add_stamp)"
```

---

### Task 3: 하드웨어 리더 CLI (pn532_stamp.py)

터미널 프로그레스 피드백 + 카드 읽기/판정/쓰기/검증 루프. 하드웨어라 자동 테스트 불가 → 수동 검증.

**Files:**
- Create: `scripts/pn532_stamp.py`

**Interfaces:**
- Consumes: `card`(BASE, encode/decode_ndef_uri, pad_pages, has_ndef, CardError), `stamp_logic`(is_our_url, add_stamp)
- Consumes (하드웨어): `PN532_I2C`의 `read_passive_target`, `ntag2xx_read_block`, `ntag2xx_write_block`, `SAM_configuration`
- Produces: 실행형 스크립트

- [ ] **Step 1: Write the CLI script**

Create `scripts/pn532_stamp.py`:

```python
#!/usr/bin/env python3
"""도장 찍기 — 전시관 리더.

data/exhibit_id 에서 자기 전시관 번호를 읽고, 카드를 만나면 URL을 읽어 s에 번호를
더해 다시 쓴다. 우리 카드가 아니거나 이미 방문한 곳이면 쓰지 않는다.

사용법:
  mkdir -p data && echo 1 > data/exhibit_id   # 최초 1회, 이 리더의 전시관 번호
  source ~/pn532/bin/activate
  python scripts/pn532_stamp.py
"""

import os
import sys
import time

import board
import busio
from adafruit_pn532.i2c import PN532_I2C

sys.path.insert(0, os.path.dirname(__file__))
import card
import stamp_logic

EXHIBIT_ID_PATH = "data/exhibit_id"
USER_MEM_START = 4          # NTAG215 사용자 메모리 시작 페이지
READ_PAGES = 70             # 검증/판정용으로 읽을 페이지 수
POLL = 0.5                  # 카드 폴링 간격(초)
BAR_SECONDS = 1.5           # 프로그레스 연출 시간
BAR_SLOTS = 8


def load_exhibit_id():
    try:
        with open(EXHIBIT_ID_PATH, encoding="utf-8") as f:
            raw = f.read().strip()
    except FileNotFoundError:
        raise SystemExit(
            f"전시관 번호 설정이 없습니다. 먼저: mkdir -p data && echo 1 > {EXHIBIT_ID_PATH}"
        )
    if not raw.isdigit() or int(raw) < 1:
        raise SystemExit(f"전시관 번호가 올바르지 않습니다: {raw!r} (양의 정수여야 함)")
    return int(raw)


# --- 피드백 인터페이스 (미래 S자 라인 조명으로 교체 가능) ---

class Feedback:
    def begin(self, exhibit_id): ...
    def update(self, fraction): ...
    def done(self, exhibit_id): ...
    def already(self, exhibit_id): ...
    def foreign(self): ...


class TerminalFeedback(Feedback):
    def begin(self, exhibit_id):
        self._name = f"전시관 {exhibit_id}"
        self.update(0.0)

    def update(self, fraction):
        filled = int(round(fraction * BAR_SLOTS))
        bar = "■" * filled + "□" * (BAR_SLOTS - filled)
        print(f"\r[{bar}] {self._name}", end="", flush=True)

    def done(self, exhibit_id):
        print(f"\r도장 완료 (전시관 {exhibit_id})          ")

    def already(self, exhibit_id):
        print(f"이미 방문한 전시관이에요 (전시관 {exhibit_id})")

    def foreign(self):
        print("우리 카드가 아니에요. 건너뜁니다.")


def play_progress(feedback, exhibit_id):
    feedback.begin(exhibit_id)
    steps = 20
    for i in range(1, steps + 1):
        time.sleep(BAR_SECONDS / steps)
        feedback.update(i / steps)
    feedback.done(exhibit_id)


# --- 카드 I/O (발급 스크립트와 동일 방식) ---

def open_pn532():
    i2c = busio.I2C(board.SCL, board.SDA)
    pn532 = PN532_I2C(i2c, debug=False)
    ic, ver, rev, support = pn532.firmware_version
    print(f"PN532 준비 완료 (펌웨어 v{ver}.{rev})")
    pn532.SAM_configuration()
    return pn532


def wait_for_card(pn532):
    while True:
        uid = pn532.read_passive_target(timeout=POLL)
        if uid:
            return bytes(uid)


def wait_for_removal(pn532):
    while pn532.read_passive_target(timeout=POLL):
        pass


def read_user_memory(pn532, num_pages=READ_PAGES):
    data = bytearray()
    for i in range(num_pages):
        block = pn532.ntag2xx_read_block(USER_MEM_START + i)
        if block is None:
            break
        data.extend(block[:4])
    return bytes(data)


def write_ndef(pn532, url):
    pages = card.pad_pages(card.encode_ndef_uri(url))
    for i in range(0, len(pages), 4):
        block = USER_MEM_START + i // 4
        if not pn532.ntag2xx_write_block(block, pages[i:i + 4]):
            raise RuntimeError(f"페이지 {block} 쓰기 실패")


# --- 한 번의 태그 ---

def stamp_one(pn532, exhibit_id, feedback):
    wait_for_card(pn532)
    url = card.decode_ndef_uri(read_user_memory(pn532))

    if not stamp_logic.is_our_url(url):
        feedback.foreign()
        wait_for_removal(pn532)
        return

    new_url, changed = stamp_logic.add_stamp(url, exhibit_id)
    if not changed:
        feedback.already(exhibit_id)
        wait_for_removal(pn532)
        return

    try:
        write_ndef(pn532, new_url)
    except (RuntimeError, card.CardError) as exc:
        print(f"\n쓰기 실패: {exc} — 카드를 다시 대주세요.")
        wait_for_removal(pn532)
        return

    if card.decode_ndef_uri(read_user_memory(pn532)) != new_url:
        print("\n검증 실패(읽은 값이 다름) — 카드를 다시 대주세요.")
        wait_for_removal(pn532)
        return

    play_progress(feedback, exhibit_id)
    wait_for_removal(pn532)


def main():
    exhibit_id = load_exhibit_id()
    try:
        pn532 = open_pn532()
    except RuntimeError as exc:
        raise SystemExit(f"PN532를 열지 못했습니다: {exc}")
    print(f"도장 리더 시작 — 전시관 {exhibit_id} (종료: Ctrl+C)\n")
    feedback = TerminalFeedback()
    while True:
        try:
            stamp_one(pn532, exhibit_id, feedback)
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as exc:
            print(f"오류로 이번 태그를 건너뜁니다: {exc}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 문법 검사**

Run: `python -m py_compile scripts/pn532_stamp.py`
Expected: 에러 없음.

- [ ] **Step 3: 수동 하드웨어 검증 (Pi에서)**

체크리스트 (발급된 실제 카드 필요):
1. `mkdir -p data && echo 1 > data/exhibit_id`
2. `python scripts/pn532_stamp.py` → `도장 리더 시작 — 전시관 1`
3. **발급된 카드**를 올려놓기 → 프로그레스 바가 차오르고 `도장 완료 (전시관 1)`
4. 아이폰으로 그 카드 태그 → 뷰어에서 **우주관 ⬤** (1/2 방문)로 바뀜
5. 같은 카드를 다시 올려놓기 → `이미 방문한 전시관이에요`
6. `echo 2 > data/exhibit_id` 후 재실행 → 같은 카드 → `도장 완료 (전시관 2)` → 아이폰에서 2/2
7. **빈 카드** 또는 다른 NFC 태그 올려놓기 → `우리 카드가 아니에요. 건너뜁니다.` (쓰기 없음)
8. Ctrl+C → `종료합니다.`

- [ ] **Step 4: Commit**

```bash
git add scripts/pn532_stamp.py
git commit -m "Add stamp reader hardware CLI with terminal feedback"
```

---

### Task 4: README 문서 + 로드맵

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: 없음
- Produces: 없음

- [ ] **Step 1: README에 도장 찍기 섹션 추가**

`## 웹 뷰어 (GitHub Pages)` 섹션 바로 앞에 다음을 삽입:

```markdown
## 도장 찍기 (전시관 리더)

전시관마다 놓인 리더가 카드를 만나면, 카드 URL의 `s`에 자기 전시관 번호를 더해
다시 굽는다. 우리 카드가 아니거나 이미 방문한 곳이면 쓰지 않는다.

- 전시관 번호 지정(리더마다 1회): `mkdir -p data && echo 1 > data/exhibit_id`
- 실행: `source ~/pn532/bin/activate && python scripts/pn532_stamp.py`
- 로직 테스트: `python -m unittest discover -s test`
- 상태 셋: 새 도장(연출) / 이미 방문 / 우리 카드 아님(무시)
- 피드백은 지금 터미널 프로그레스 바이며, 미래에 물리 조명으로 교체 가능한
  인터페이스로 분리돼 있다.
```

- [ ] **Step 2: 로드맵 체크박스 갱신**

`README.md` 로드맵에서 도장 찍기 줄을 완료로 변경:

```markdown
- [x] 도장 찍기 (전시관 리더: URL 읽어 `s`에 번호 추가 후 다시 쓰기)
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document stamp reader and update roadmap"
```

---

## Self-Review 결과

- **Spec coverage:** 공유 추출(card.py) → Task 1; is_our_url/add_stamp(n·id 보존, 중복제거, 미지번호 보존) → Task 2; 리더 흐름·3상태·설정파일·피드백·에러처리 → Task 3; 문서 → Task 4. 리팩터 불변식(기존 테스트 통과) → Task 1 Step 5-6. 누락 없음.
- **Placeholder scan:** 모든 코드/테스트/명령 실체 포함. 플레이스홀더 없음. (`Feedback` 기반 클래스의 `...` 본문은 의도된 추상 메서드 스텁으로, 구현은 `TerminalFeedback`에 있음.)
- **Type consistency:** `is_our_url`, `add_stamp`(→ `(str, bool)`), `card.encode_ndef_uri`/`decode_ndef_uri`/`pad_pages`/`has_ndef`/`CardError`/`BASE`, `il.IssueError`(=CardError 별칭) 명칭이 Task 간 일관.
