#!/usr/bin/env python3
"""PN532 I2C 통신 확인 스크립트.

라즈베리파이에 I2C로 연결된 PN532와 통신이 되는지 하나씩 검증한다.
  1. I2C 버스로 PN532를 연다
  2. 펌웨어 버전을 읽는다   (모듈이 살아 있는지)
  3. SAM을 설정한다         (카드 읽기 모드)
  4. 카드를 폴링해 UID를 읽는다

성공 판정:
  - 펌웨어 버전이 출력되면 → I2C 통신 성공
  - 카드를 대면 UID(7바이트)가 출력되면 → 카드 읽기 성공

사용법:
  source ~/pn532/bin/activate
  python scripts/pn532_i2c_test.py
"""

import time

import board
import busio
from adafruit_pn532.i2c import PN532_I2C


def open_pn532():
    """I2C 버스로 PN532를 열고 펌웨어 버전을 확인한다."""
    # board.SCL / board.SDA → Pi 물리 핀 5 / 3 (GPIO3 / GPIO2)
    i2c = busio.I2C(board.SCL, board.SDA)
    pn532 = PN532_I2C(i2c, debug=False)

    ic, ver, rev, support = pn532.firmware_version
    print(f"PN532 발견: 펌웨어 v{ver}.{rev}")

    # SAM(Security Access Module) 설정 — 일반 카드 읽기 모드로 둔다
    pn532.SAM_configuration()
    return pn532


def poll_cards(pn532):
    """카드를 대면 UID를 출력한다. Ctrl+C로 종료."""
    print("카드를 리더에 대세요… (종료: Ctrl+C)")
    last_uid = None
    while True:
        # timeout 안에 카드가 없으면 None 반환
        uid = pn532.read_passive_target(timeout=0.5)
        if uid is None:
            last_uid = None
            continue

        # 같은 카드가 계속 잡히면 한 번만 출력
        if uid != last_uid:
            hex_uid = ":".join(f"{b:02X}" for b in uid)
            print(f"카드 감지 — UID({len(uid)}바이트): {hex_uid}")
            last_uid = uid

        time.sleep(0.2)


def main():
    try:
        pn532 = open_pn532()
    except RuntimeError as exc:
        # 대개 배선 문제 또는 I2C 모드 미설정
        print(f"PN532를 열지 못했습니다: {exc}")
        print("확인: 3.3V 배선 / SDA(핀3)·SCL(핀5) / 모듈 I2C 모드 / i2cdetect -y 1 에서 0x24")
        raise SystemExit(1)

    try:
        poll_cards(pn532)
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
