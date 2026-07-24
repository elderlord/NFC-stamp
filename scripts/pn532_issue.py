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
READ_PAGES = 70            # 검증/기존감지용. 최대 단일 NDEF 레코드(~258B, 65페이지)를 여유 있게 커버
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
    except (RuntimeError, il.IssueError) as exc:
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
    while True:
        try:
            issue_one(pn532)
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as exc:
            print(f"오류로 이번 발급을 건너뜁니다: {exc}\n")


if __name__ == "__main__":
    main()
