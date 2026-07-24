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
