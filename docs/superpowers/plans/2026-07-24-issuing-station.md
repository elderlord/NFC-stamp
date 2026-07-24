# 발급 스테이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 터미널에서 닉네임·인구통계를 받아 카드 UID를 식별번호로 하는 개인화 URL을 NTAG215에 NDEF로 굽고, 발급 로그를 남기는 발급 스테이션을 만든다.

**Architecture:** 뷰어와 동일한 "순수 로직 + 얇은 하드웨어 I/O" 분리. URL 조립·코드 검증·로그 포맷·**NDEF 인코딩/디코딩**은 하드웨어 없이 단위 테스트 가능한 `scripts/issue_logic.py`에 모으고, `scripts/pn532_issue.py`는 페이지 읽기/쓰기와 CLI만 담당한다.

**Tech Stack:** Python 3, adafruit-circuitpython-pn532 (이미 requirements.txt에 있음), 표준 라이브러리(`urllib.parse`, `csv`, `datetime`), 테스트는 `python -m unittest`.

## Global Constraints

- 새 외부 의존성 추가 금지. adafruit 라이브러리(설치됨) + 표준 라이브러리만.
- BASE 상수 = `https://elderlord.github.io/NFC-stamp/` (뷰어와 정확히 일치, 대문자 `NFC-stamp`).
- 카드에 굽는 URL 파라미터 집합 = `n`, `id`, `s` (뷰어 `parseParams` 계약). 발급 시 `s`는 빈값.
- `id` = UID 대문자 hex(구분자 없음).
- 성별 코드 = `m`/`f` 만. 연령대 코드 = 정수 `1`~`7` 만.
- 로그 CSV 컬럼(순서) = `issued_at, uid, nickname, gender, age_group`. 파일 없으면 헤더 먼저.
- 로그 파일 경로 = `data/issue_log.csv`. `data/`는 `.gitignore`에 추가(개인정보, 커밋 금지).
- 닉네임 최대 20자. 초과 시 거부.
- 순수 로직은 TDD(실패 테스트 먼저). 하드웨어 I/O(`pn532_issue.py`)는 자동 테스트 불가 → 수동 검증.

---

### Task 1: 순수 로직 코어 (issue_logic.py)

URL 조립·UID 포맷·코드 검증·로그 행 포맷. 하드웨어·I/O 없음.

**Files:**
- Create: `scripts/issue_logic.py`
- Test: `test/test_issue_logic.py`

**Interfaces:**
- Consumes: 없음 (표준 라이브러리 `urllib.parse.quote`)
- Produces:
  - `BASE: str`
  - `GENDERS: set[str]`, `AGE_GROUPS: set[int]`, `MAX_NICKNAME_LEN: int`, `LOG_HEADER: list[str]`
  - `class IssueError(ValueError)`
  - `format_uid(raw: bytes) -> str`
  - `is_valid_gender(code: str) -> bool`
  - `is_valid_age_group(n: int) -> bool`
  - `build_url(base: str, nickname: str, uid: str) -> str`
  - `log_fields(issued_at: str, uid: str, nickname: str, gender: str, age_group: int) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Create `test/test_issue_logic.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest test.test_issue_logic -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'issue_logic'`

- [ ] **Step 3: Write the implementation**

Create `scripts/issue_logic.py`:

```python
"""발급 스테이션 순수 로직 — 하드웨어·입출력 없음, 단위 테스트 대상."""

from urllib.parse import quote

BASE = "https://elderlord.github.io/NFC-stamp/"

GENDERS = {"m", "f"}
AGE_GROUPS = set(range(1, 8))  # 1..7
MAX_NICKNAME_LEN = 20

LOG_HEADER = ["issued_at", "uid", "nickname", "gender", "age_group"]

# 코드 범례 (참고용; 로그엔 코드값만 저장)
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


class IssueError(ValueError):
    """발급 로직 검증 실패."""


def format_uid(raw):
    """UID 바이트 → 대문자 hex 문자열(구분자 없음)."""
    return "".join(f"{b:02X}" for b in raw)


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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest test.test_issue_logic -v`
Expected: PASS (모든 테스트)

- [ ] **Step 5: Commit**

```bash
git add scripts/issue_logic.py test/test_issue_logic.py
git commit -m "Add issuing-station pure logic (url build, uid, validation, log)"
```

---

### Task 2: NDEF URI 코덱 (issue_logic.py에 추가)

NTAG에 쓸 NDEF 메시지 바이트 인코딩/디코딩. 순수 바이트 연산이라 하드웨어 없이 테스트한다.

**Files:**
- Modify: `scripts/issue_logic.py` (함수 추가)
- Modify: `test/test_issue_logic.py` (테스트 추가)

**Interfaces:**
- Consumes: Task 1의 `IssueError`
- Produces:
  - `encode_ndef_uri(url: str) -> bytes`  (NDEF 메시지 TLV: `03 <len> <record> FE`)
  - `decode_ndef_uri(data: bytes) -> str | None`
  - `has_ndef(data: bytes) -> bool`
  - `pad_pages(tlv: bytes) -> bytes`  (4바이트 페이지 배수로 0x00 패딩)

- [ ] **Step 1: Write the failing tests**

Append to `test/test_issue_logic.py` (before the `if __name__` block):

```python
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
        self.assertEqual(tlv[4], 0x00)  # record 시작 후 payload 첫 바이트(prefix code)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest test.test_issue_logic.TestNdefCodec -v`
Expected: FAIL — `AttributeError: module 'issue_logic' has no attribute 'encode_ndef_uri'`

- [ ] **Step 3: Write the implementation**

Append to `scripts/issue_logic.py`:

```python
# --- NDEF URI 코덱 ---------------------------------------------------------

# NDEF URI 접두사 코드 (필요한 것만)
_URI_PREFIXES = {
    0x00: "",
    0x01: "http://www.",
    0x02: "https://www.",
    0x03: "http://",
    0x04: "https://",
}
# 인코딩 시 긴 접두사부터 매칭
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
    if len(payload) > 255:
        raise IssueError("URI가 너무 깁니다(단일 NDEF 레코드 한도 초과)")
    record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload  # SR URI 레코드
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    return tlv


def decode_ndef_uri(data):
    """NTAG 사용자 메모리 바이트 → URI 문자열. NDEF URI 레코드가 아니면 None."""
    if len(data) < 2 or data[0] != 0x03:
        return None
    msg_len = data[1]
    record = data[2:2 + msg_len]
    if len(record) < 4 or record[3] != 0x55:  # 'U' 타입
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest test.test_issue_logic -v`
Expected: PASS (Task 1 + Task 2 전체)

- [ ] **Step 5: Commit**

```bash
git add scripts/issue_logic.py test/test_issue_logic.py
git commit -m "Add NDEF URI codec to issuing-station logic"
```

---

### Task 3: 하드웨어 CLI (pn532_issue.py) + .gitignore

터미널 입력 → UID 읽기 → 기존 NDEF 2단계 확인 → NDEF 쓰기 → 읽기 검증 → 로그 append. 하드웨어라 자동 테스트 불가 → 수동 검증.

**Files:**
- Create: `scripts/pn532_issue.py`
- Modify: `.gitignore` (add `data/`)

**Interfaces:**
- Consumes: `issue_logic`의 `BASE, format_uid, build_url, log_fields, encode_ndef_uri, decode_ndef_uri, has_ndef, pad_pages, LOG_HEADER, IssueError`
- Consumes (하드웨어): `adafruit_pn532.i2c.PN532_I2C`의 `read_passive_target(timeout)`, `ntag2xx_read_block(block)`(4바이트 반환), `ntag2xx_write_block(block, data)`(4바이트), `SAM_configuration()`
- Produces: 실행형 스크립트(라이브러리 아님)

- [ ] **Step 1: Add `data/` to .gitignore**

Append to `.gitignore`:

```
# 발급 로그 (개인정보 — 커밋 금지)
data/
```

- [ ] **Step 2: Write the CLI script**

Create `scripts/pn532_issue.py`:

```python
#!/usr/bin/env python3
"""발급 스테이션 — 터미널에서 카드를 발급한다.

흐름(1건):
  닉네임·성별·연령대 입력 → "카드를 올려놓으세요" → UID 읽기 →
  (기존 NDEF면 2단계 확인) → NDEF 쓰기 → 읽기 검증 → 로그 append → 반복.

사용법:
  source ~/pn532/bin/activate
  python scripts/pn532_issue.py
"""

import csv
import os
import sys
import time
from datetime import datetime

import board
import busio
from adafruit_pn532.i2c import PN532_I2C

sys.path.insert(0, os.path.dirname(__file__))
import issue_logic as il

LOG_PATH = "data/issue_log.csv"
USER_MEM_START = 4          # NTAG215 사용자 메모리 시작 페이지
READ_PAGES = 40             # 검증·기존감지용으로 읽을 페이지 수(160B, URL 충분)
CARD_TIMEOUT = 30           # 카드 대기 초


def open_pn532():
    i2c = busio.I2C(board.SCL, board.SDA)
    pn532 = PN532_I2C(i2c, debug=False)
    ic, ver, rev, support = pn532.firmware_version
    print(f"PN532 준비 완료 (펌웨어 v{ver}.{rev})")
    pn532.SAM_configuration()
    return pn532


# --- 입력 ---------------------------------------------------------------

def prompt_nickname():
    while True:
        v = input("닉네임: ").strip()
        if not v:
            print("  비어 있습니다. 다시 입력하세요.")
            continue
        if len(v) > il.MAX_NICKNAME_LEN:
            print(f"  너무 깁니다(최대 {il.MAX_NICKNAME_LEN}자).")
            continue
        return v


def prompt_gender():
    while True:
        v = input("성별 [1]남 [2]여: ").strip()
        if v == "1":
            return "m"
        if v == "2":
            return "f"
        print("  1 또는 2를 입력하세요.")


def prompt_age_group():
    print("연령대: 1)초등 저학년 2)초등 고학년 3)10대 4)20대 5)30대 6)40대 7)50대+")
    while True:
        v = input("연령대 [1-7]: ").strip()
        if v.isdigit() and il.is_valid_age_group(int(v)):
            return int(v)
        print("  1~7 중에서 입력하세요.")


# --- 카드 I/O -----------------------------------------------------------

def wait_for_card(pn532, timeout=CARD_TIMEOUT):
    print("카드를 리더에 올려놓으세요…")
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        uid = pn532.read_passive_target(timeout=0.5)
        if uid:
            return bytes(uid)
    return None


def read_user_memory(pn532, num_pages=READ_PAGES):
    """사용자 메모리를 페이지 단위로 읽어 이어붙인다."""
    data = bytearray()
    for i in range(num_pages):
        block = pn532.ntag2xx_read_block(USER_MEM_START + i)
        if block is None:
            break
        data.extend(block[:4])
    return bytes(data)


def write_ndef(pn532, url):
    """URL을 NDEF로 인코딩해 사용자 메모리에 페이지 단위로 쓴다."""
    pages = il.pad_pages(il.encode_ndef_uri(url))
    for i in range(0, len(pages), 4):
        block = USER_MEM_START + i // 4
        if not pn532.ntag2xx_write_block(block, pages[i:i + 4]):
            raise RuntimeError(f"페이지 {block} 쓰기 실패")


# --- 로그 ---------------------------------------------------------------

def append_log(fields):
    new = not os.path.exists(LOG_PATH)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(il.LOG_HEADER)
        w.writerow(fields)


# --- 발급 1건 -----------------------------------------------------------

def issue_one(pn532):
    nickname = prompt_nickname()
    gender = prompt_gender()
    age = prompt_age_group()

    uid_bytes = wait_for_card(pn532)
    if uid_bytes is None:
        print("시간 초과 — 이번 발급을 취소합니다.\n")
        return
    uid = il.format_uid(uid_bytes)

    existing = read_user_memory(pn532)
    if il.has_ndef(existing):
        if input(f"이 카드에 이미 데이터가 있습니다. 덮어쓸까요? (y/N) ").strip().lower() != "y":
            print("취소했습니다.\n")
            return
        if input(f"확인: UID 뒷 4자리({uid[-4:]}) 입력: ").strip().upper() != uid[-4:]:
            print("확인 불일치 — 취소했습니다.\n")
            return

    url = il.build_url(il.BASE, nickname, uid)
    try:
        write_ndef(pn532, url)
    except RuntimeError as exc:
        print(f"쓰기 실패: {exc} — 로그를 남기지 않습니다.\n")
        return

    readback = il.decode_ndef_uri(read_user_memory(pn532))
    if readback != url:
        print("검증 실패(읽은 값이 다름) — 로그를 남기지 않습니다.\n")
        return

    issued_at = datetime.now().isoformat(timespec="seconds")
    append_log(il.log_fields(issued_at, uid, nickname, gender, age))
    print(f"발급 완료: {uid}. 카드를 치우세요.\n")


def main():
    try:
        pn532 = open_pn532()
    except RuntimeError as exc:
        print(f"PN532를 열지 못했습니다: {exc}")
        raise SystemExit(1)
    print("발급 스테이션 시작 (종료: Ctrl+C)\n")
    try:
        while True:
            issue_one(pn532)
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 문법 검사**

Run: `python -m py_compile scripts/pn532_issue.py`
Expected: 에러 없음 (하드웨어 모듈 import는 실행 시점이라 컴파일엔 영향 없음)

- [ ] **Step 4: 수동 하드웨어 검증 (Pi에서)**

체크리스트 (실제 NTAG215 카드 필요):
1. `python scripts/pn532_issue.py` 실행 → "PN532 준비 완료" 출력
2. 닉네임 `철수`, 성별 `1`, 연령대 `4` 입력 → 빈 카드 올려놓기
3. `발급 완료: <UID>` 출력 확인
4. 아이폰으로 그 카드 태그 → `https://elderlord.github.io/NFC-stamp/?n=철수&id=<UID>&s=` 열림
5. 뷰어에 "철수님, 환영합니다 / 0 / 2 방문" 표시 확인
6. `cat data/issue_log.csv` → 헤더 + `...,<UID>,철수,m,4` 행 확인
7. **덮어쓰기**: 같은(발급된) 카드를 다시 올려 재발급 시도 → 2단계 확인(y → UID 뒷4자리) 통과해야 진행되는지 확인
8. `git status` → `data/`가 추적되지 않는지(gitignore) 확인

- [ ] **Step 5: Commit**

```bash
git add scripts/pn532_issue.py .gitignore
git commit -m "Add issuing-station hardware CLI and gitignore data/"
```

---

### Task 4: README 문서 + 로드맵

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: 없음
- Produces: 없음

- [ ] **Step 1: README에 발급 스테이션 섹션 추가**

`## 웹 뷰어 (GitHub Pages)` 섹션 바로 앞에 다음 섹션을 삽입:

```markdown
## 발급 스테이션

관람객에게 카드를 발급한다. 터미널(SSH)에서 닉네임·성별·연령대를 입력하고 카드를
리더에 올려놓으면, 카드 UID를 식별번호로 하는 개인화 URL을 NDEF로 굽는다.

- 실행: `source ~/pn532/bin/activate && python scripts/pn532_issue.py`
- 로직 테스트: `python -m unittest discover -s test`
- 카드에 굽는 URL: `https://elderlord.github.io/NFC-stamp/?n=<닉네임>&id=<UID>&s=`
- 발급 로그: `data/issue_log.csv` (개인정보 — gitignore, 커밋 안 함)

**로그 코드 범례**

- 성별: `m` = 남, `f` = 여
- 연령대: `1`=초등 저학년(1~3) · `2`=초등 고학년(4~6) · `3`=10대(중학생↑) ·
  `4`=20대 · `5`=30대 · `6`=40대 · `7`=50대 이상
```

- [ ] **Step 2: 로드맵 체크박스 갱신**

`README.md` 로드맵에서 발급 스테이션 줄을 완료로 변경:

```markdown
- [x] 발급 스테이션 (닉네임 입력 → 카드에 URL NDEF 쓰기)
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document issuing station and update roadmap"
```

---

## Self-Review 결과

- **Spec coverage:** 데이터 계약(URL·로그) → Task 1/2, 조작 흐름·2단계 확인·검증 → Task 3, 에러/엣지(빈 닉네임·오입력·타임아웃·쓰기실패·용량가드·기존카드) → Task 1(가드·검증) + Task 3(입력·타임아웃·덮어쓰기), 테스트 → Task 1/2(자동)·Task 3(수동), 문서/범례/gitignore → Task 3/4. 누락 없음.
- **Placeholder scan:** 모든 코드/테스트/명령 실체 포함. 플레이스홀더 없음.
- **Type consistency:** `build_url`, `format_uid`, `log_fields`, `encode_ndef_uri`, `decode_ndef_uri`, `has_ndef`, `pad_pages`, `LOG_HEADER` 명칭이 Task 1~3에서 일관.
