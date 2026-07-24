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
    except OSError:
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
    try:
        url = card.decode_ndef_uri(read_user_memory(pn532))

        if not stamp_logic.is_our_url(url):
            feedback.foreign()
            return

        new_url, changed = stamp_logic.add_stamp(url, exhibit_id)
        if not changed:
            feedback.already(exhibit_id)
            return

        try:
            write_ndef(pn532, new_url)
        except (RuntimeError, card.CardError) as exc:
            print(f"\n쓰기 실패: {exc} — 카드를 다시 대주세요.")
            return

        if card.decode_ndef_uri(read_user_memory(pn532)) != new_url:
            print("\n검증 실패(읽은 값이 다름) — 카드를 다시 대주세요.")
            return

        play_progress(feedback, exhibit_id)
    finally:
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
