# nfc-stamp

라즈베리파이 + PN532로 만드는 **서버 없는 NFC 도장 투어** 시스템.

관람객에게 NFC 카드(NTAG215)를 발급하고, 전시관마다 놓인 리더에 카드를 대면
"도장"이 찍힙니다. 모든 상태는 **카드에 저장된 URL 안에** 들어가고, GitHub Pages가
그 URL 파라미터를 읽어 개인화된 화면을 그립니다. 백엔드 서버가 없습니다.

```
https://<github-pages>/?n=철수&id=2026-0001&s=3,7
                        └닉네임  └식별번호    └다녀간 전시관 목록
```

이 브랜치(`pn532-nfc-i2c-wiring`)는 그 첫 단계 — **PN532와 I2C로 통신을 확립**하는
부분을 다룹니다.

---

## 하드웨어

| 항목 | 내용 |
|---|---|
| 보드 | Raspberry Pi 3 / 5 (40핀 헤더 동일) |
| NFC 모듈 | PN532 파란색 브레이크아웃 (I2C 모드) |
| 카드 | NTAG215 (사용자 메모리 504바이트, UID 7바이트) |
| I2C 주소 | `0x24` (PN532 표준 7비트 주소) |

### PN532 모드 설정

파란 보드는 뒷면 점퍼/스위치로 I2C / SPI / HSU 중 하나를 고릅니다.
**I2C 모드**로 두어야 합니다. (보드마다 라벨이 다르지만, 흔한 조합은
`SET0=H`, `SET1=L`.) 모드가 안 맞으면 배선이 완벽해도 `i2cdetect`에 아무것도
안 뜹니다.

### 배선 (I2C, 4선)

| PN532 | Raspberry Pi 물리 핀 | 비고 |
|---|---|---|
| VCC | **3.3V** (핀 1 또는 17) | ⚠️ 5V 아님 |
| GND | GND (핀 6, 9 …) | |
| SDA | GPIO2 / SDA1 (핀 3) | |
| SCL | GPIO3 / SCL1 (핀 5) | |
| (선택) IRQ | 임의 GPIO | 인터럽트 읽기용, 지금은 생략 |
| (선택) RSTPD_N | 임의 GPIO | 하드웨어 리셋용, 지금은 생략 |

> **왜 5V가 아니라 3.3V인가**
> Pi의 SDA/SCL은 3.3V이고 5V를 견디지 못합니다. 대부분의 PN532 브레이크아웃은
> 보드에 I2C 풀업 저항이 내장되어 있어, VCC를 5V로 주면 풀업이 I2C 라인을 5V로
> 끌어올려 Pi의 GPIO를 손상시킬 수 있습니다. VCC를 3.3V로 주면 풀업 기준도
> 3.3V가 되어 안전합니다.

---

## 셋업

### 1. Pi에서 I2C 활성화

```bash
sudo raspi-config      # Interface Options → I2C → Enable
sudo reboot
```

### 2. 물리 연결 확인

```bash
sudo apt install -y i2c-tools
i2cdetect -y 1
```

`0x24`가 뜨면 물리 연결 성공입니다.

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
20:          -- 24 -- -- -- -- -- -- -- -- -- -- --
```

### 3. 파이썬 환경

```bash
python3 -m venv ~/pn532
source ~/pn532/bin/activate
pip install -r requirements.txt
```

### 4. 통신 테스트

```bash
python scripts/pn532_i2c_test.py
```

펌웨어 버전이 출력되고, 카드를 대면 UID가 찍히면 I2C 통신 완료입니다.

---

## 저장소 구조

```
scripts/
  pn532_i2c_test.py    # I2C 연결 + 펌웨어 확인 + UID 읽기 (이 단계)
requirements.txt
README.md
```

## 로드맵

- [x] PN532 I2C 통신 확립 ← **현재 브랜치**
- [ ] 발급 스테이션 (닉네임 입력 → 카드에 URL NDEF 쓰기)
- [ ] GitHub Pages (URL 파라미터 → 개인화 화면)
- [ ] 도장 찍기 (전시관 리더: URL 읽어 `s`에 번호 추가 후 다시 쓰기)
- [ ] 카드 초기화 (확인 팝업 포함)

### 나중으로 미룬 것

Supabase 연동, 사용자 인증, 리더 실시간 반응, NTAG 쓰기 비밀번호, 분실 대응 자동화.
