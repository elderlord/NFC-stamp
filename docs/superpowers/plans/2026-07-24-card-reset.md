# 카드 초기화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 회수한 카드를 2단계 확인 후 완전히 소거해 재발급할 수 있게 하는 초기화 도구를 만든다.

**Architecture:** 발급·도장과 같은 "순수 로직 + 얇은 I/O" 패턴. 공유 `card.py`에 빈 상태 상수 `EMPTY_NDEF`를 추가하고, 현재 내용 요약은 순수 함수 `reset_logic.describe_card`로, 하드웨어 소거 루프는 `pn532_reset.py`에 둔다.

**Tech Stack:** Python 3, adafruit-circuitpython-pn532(설치됨), 표준 라이브러리, 테스트는 `python -m unittest`.

## Global Constraints

- 새 외부 의존성 추가 금지. adafruit(설치됨) + 표준 라이브러리만.
- 카드 URL 파라미터 = `n`, `id`, `s` (뷰어 계약). 초기화는 카드를 소거만 하며 URL을 새로 쓰지 않는다.
- `EMPTY_NDEF = bytes([0x03, 0x00, 0xFE, 0x00])` — 빈 NDEF 메시지. `decode_ndef_uri(EMPTY_NDEF)`는 `None`, `has_ndef(EMPTY_NDEF)`는 `False`여야 한다.
- 2단계 확인: `y` → UID 뒷 4자리 일치. 둘 다 통과해야 소거.
- 완전 소거: 사용자 페이지 `4`~`69`를 0으로 쓴 뒤 페이지 4에 `EMPTY_NDEF`. CC(3)·UID(0~1)·잠금(2)은 건드리지 않는다.
- 페이지 쓰기는 재시도(최대 4회). 검증은 다시 읽어 `decode_ndef_uri`가 `None`.
- 순수 로직은 TDD. 하드웨어 I/O(`pn532_reset.py`)는 자동 테스트 불가 → 수동 검증.

---

### Task 1: 순수 로직 (EMPTY_NDEF + describe_card)

**Files:**
- Modify: `scripts/card.py` (상수 추가)
- Modify: `test/test_card.py` (EMPTY_NDEF 테스트 추가)
- Create: `scripts/reset_logic.py`
- Test: `test/test_reset_logic.py`

**Interfaces:**
- Consumes: `card.BASE`, `card.decode_ndef_uri`, `card.has_ndef`, `stamp_logic.is_our_url`
- Produces:
  - `card.EMPTY_NDEF: bytes`
  - `reset_logic.describe_card(url: str | None) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `test/test_card.py` — add this method to the `TestNdefCodec` class (before the `if __name__` block):

```python
    def test_empty_ndef_reads_as_empty(self):
        self.assertIsNone(card.decode_ndef_uri(card.EMPTY_NDEF))
        self.assertFalse(card.has_ndef(card.EMPTY_NDEF))
```

Create `test/test_reset_logic.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest test.test_reset_logic -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'reset_logic'`

- [ ] **Step 3: Add `EMPTY_NDEF` to `scripts/card.py`**

Append after the `pad_pages` function:

```python
# 빈 NDEF 메시지(내용 없음). 소거 후 이 상태로 남긴다.
EMPTY_NDEF = bytes([0x03, 0x00, 0xFE, 0x00])
```

- [ ] **Step 4: Create `scripts/reset_logic.py`**

```python
"""카드 초기화 순수 로직 — 하드웨어 없음, 단위 테스트 대상."""

from urllib.parse import urlparse, parse_qs

from stamp_logic import is_our_url


def describe_card(url):
    """카드 현재 내용을 사람이 읽을 한 줄 요약으로. 카드에 쓰지 않는다."""
    if url is None:
        return "빈 카드 또는 해독 불가"
    if not is_our_url(url):
        return "우리 카드 아님"
    q = parse_qs(urlparse(url).query, keep_blank_values=True)
    nickname = q.get("n", [""])[0]      # parse_qs가 퍼센트 인코딩을 디코드
    card_id = q.get("id", [""])[0]
    visits = q.get("s", [""])[0] or "없음"
    return f"닉네임: {nickname} · ID: {card_id} · 방문: {visits}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest discover -s test -v`
Expected: PASS — 전체 통과(기존 29 + 새 EMPTY_NDEF 1 + describe_card 4 = 34).

- [ ] **Step 6: Commit**

```bash
git add scripts/card.py scripts/reset_logic.py test/test_card.py test/test_reset_logic.py
git commit -m "Add card reset pure logic (EMPTY_NDEF, describe_card)"
```

---

### Task 2: 하드웨어 CLI (pn532_reset.py)

읽기 → 요약 → 2단계 확인 → 완전 소거 → 검증 → 반복. 하드웨어라 자동 테스트 불가 → 수동 검증.

**Files:**
- Create: `scripts/pn532_reset.py`

**Interfaces:**
- Consumes: `card`(format_uid, decode_ndef_uri, EMPTY_NDEF), `reset_logic`(describe_card)
- Consumes (하드웨어): `PN532_I2C`의 `read_passive_target`, `ntag2xx_read_block`, `ntag2xx_write_block`, `SAM_configuration`
- Produces: 실행형 스크립트

- [ ] **Step 1: Write the CLI script**

Create `scripts/pn532_reset.py`:

```python
#!/usr/bin/env python3
"""카드 초기화 — 회수한 카드를 빈 상태로 되돌린다.

카드를 올려놓으면 현재 내용을 보여주고, 2단계 확인 후 사용자 메모리를 완전히
소거한다(재발급 대비, 손상 카드 복구 겸용).

사용법:
  source ~/pn532/bin/activate
  python scripts/pn532_reset.py
"""

import os
import sys
import time

import board
import busio
from adafruit_pn532.i2c import PN532_I2C

sys.path.insert(0, os.path.dirname(__file__))
import card
import reset_logic

USER_MEM_START = 4      # NTAG215 사용자 메모리 시작 페이지
ERASE_END = 69          # 소거할 마지막 사용자 페이지(4~69가 최대 URL을 덮음)
READ_PAGES = 70
POLL = 0.5
WRITE_RETRIES = 4


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


def write_block(pn532, block, chunk):
    for _ in range(WRITE_RETRIES):
        if pn532.ntag2xx_write_block(block, chunk):
            return
        time.sleep(0.02)
    raise RuntimeError(f"페이지 {block} 쓰기 실패 ({WRITE_RETRIES}회 재시도)")


def erase_card(pn532):
    zero = bytes([0, 0, 0, 0])
    for block in range(USER_MEM_START, ERASE_END + 1):
        write_block(pn532, block, zero)
    # 페이지 4를 빈 NDEF 메시지로 마무리
    write_block(pn532, USER_MEM_START, card.EMPTY_NDEF)


def reset_one(pn532):
    uid = card.format_uid(wait_for_card(pn532))
    try:
        url = card.decode_ndef_uri(read_user_memory(pn532))
        print(f"현재 내용: {reset_logic.describe_card(url)}")

        if input("초기화할까요? (y/N) ").strip().lower() != "y":
            print("취소했습니다.\n")
            return
        if input(f"확인: UID 뒷 4자리({uid[-4:]}) 입력: ").strip().upper() != uid[-4:]:
            print("확인 불일치 — 취소했습니다.\n")
            return

        try:
            erase_card(pn532)
        except RuntimeError as exc:
            print(f"소거 실패: {exc} — 다시 시도하세요.\n")
            return

        if card.decode_ndef_uri(read_user_memory(pn532)) is not None:
            print("검증 실패(빈 상태가 아님) — 다시 시도하세요.\n")
            return

        print(f"초기화 완료: {uid}. 카드를 치우세요.\n")
    finally:
        wait_for_removal(pn532)


def main():
    try:
        pn532 = open_pn532()
    except RuntimeError as exc:
        raise SystemExit(f"PN532를 열지 못했습니다: {exc}")
    print("카드 초기화 시작 (종료: Ctrl+C)\n")
    while True:
        try:
            reset_one(pn532)
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as exc:
            print(f"오류로 이번 초기화를 건너뜁니다: {exc}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 문법 검사**

Run: `python -m py_compile scripts/pn532_reset.py`
Expected: 에러 없음.

- [ ] **Step 3: 수동 하드웨어 검증 (Pi에서)**

체크리스트 (발급된 카드 필요):
1. `python scripts/pn532_reset.py` → `카드 초기화 시작`
2. **발급된 카드** 올려놓기 → `현재 내용: 닉네임: 철수 · ID: ... · 방문: ...` 표시
3. `y` → UID 뒷 4자리 입력 → `초기화 완료: <UID>`
4. 아이폰으로 그 카드 태그 → **URL이 안 열림**(빈 카드)
5. `python scripts/pn532_issue.py`로 그 카드 재발급 → **"이미 데이터..." 확인 없이 바로 발급**되는지(빈 카드로 인식)
6. 초기화 중 `y` 대신 `n` 또는 뒷4자리 틀리게 → `취소` 되고 카드 안 바뀌는지
7. Ctrl+C → `종료합니다.`

- [ ] **Step 4: Commit**

```bash
git add scripts/pn532_reset.py
git commit -m "Add card reset hardware CLI with 2-step confirm"
```

---

### Task 3: README 문서 + 로드맵

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: 없음
- Produces: 없음

- [ ] **Step 1: README에 카드 초기화 섹션 추가**

`## 웹 뷰어 (GitHub Pages)` 섹션 바로 앞에 다음을 삽입:

```markdown
## 카드 초기화

회수한 카드를 빈 상태로 되돌려 재발급할 수 있게 한다. 카드를 올려놓으면 현재 내용을
보여주고, 2단계 확인 후 사용자 메모리를 완전히 소거한다. 손상된 카드 복구도 겸한다.

- 실행: `source ~/pn532/bin/activate && python scripts/pn532_reset.py`
- 로직 테스트: `python -m unittest discover -s test`
- 흐름: 카드 올려놓기 → 현재 내용 표시 → `y` → UID 뒷 4자리 → 초기화 완료
- 소거 후 발급 스테이션이 빈 카드로 인식해 확인 없이 재발급된다.
```

- [ ] **Step 2: 로드맵 체크박스 갱신**

`README.md` 로드맵에서 카드 초기화 줄을 완료로 변경:

```markdown
- [x] 카드 초기화 (확인 팝업 포함)
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document card reset and update roadmap"
```

---

## Self-Review 결과

- **Spec coverage:** EMPTY_NDEF + describe_card → Task 1; 흐름·2단계 확인·완전 소거(4~69)·검증 → Task 2; 문서 → Task 3. 손상 복구는 Task 2 흐름(어떤 카드든 요약 후 소거)로 커버. 누락 없음.
- **Placeholder scan:** 모든 코드/테스트/명령 실체 포함. 플레이스홀더 없음.
- **Type consistency:** `EMPTY_NDEF`, `describe_card(url)->str`, `card.format_uid`, `erase_card`, `write_block` 명칭이 Task 간 일관. `describe_card`는 `stamp_logic.is_our_url`와 `parse_qs`만 사용(카드에 쓰지 않음).
