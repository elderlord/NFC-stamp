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

## 도장 찍기 (전시관 리더)

전시관마다 놓인 리더가 카드를 만나면, 카드 URL의 `s`에 자기 전시관 번호를 더해
다시 굽는다. 우리 카드가 아니거나 이미 방문한 곳이면 쓰지 않는다.

- 전시관 번호 지정(리더마다 1회): `mkdir -p data && echo 1 > data/exhibit_id`
- 실행: `source ~/pn532/bin/activate && python scripts/pn532_stamp.py`
- 로직 테스트: `python -m unittest discover -s test`
- 상태 셋: 새 도장(연출) / 이미 방문 / 우리 카드 아님(무시)
- 피드백은 지금 터미널 프로그레스 바이며, 미래에 물리 조명으로 교체 가능한
  인터페이스로 분리돼 있다.

## 카드 초기화

회수한 카드를 빈 상태로 되돌려 재발급할 수 있게 한다. 카드를 올려놓으면 현재 내용을
보여주고, 2단계 확인 후 사용자 메모리를 완전히 소거한다. 손상된 카드 복구도 겸한다.

- 실행: `source ~/pn532/bin/activate && python scripts/pn532_reset.py`
- 로직 테스트: `python -m unittest discover -s test`
- 흐름: 카드 올려놓기 → 현재 내용 표시 → `y` → UID 뒷 4자리 → 초기화 완료
- 소거 후 발급 스테이션이 빈 카드로 인식해 확인 없이 재발급된다.

## 웹 뷰어 (GitHub Pages)

카드에 굽는 URL이 가리키는 개인화 도장판 페이지.

- 소스: `docs/` (GitHub Pages를 `main` 브랜치 `/docs`로 설정)
- 배포 주소: `https://elderlord.github.io/NFC-stamp/`
- 로컬 확인: `cd docs && python3 -m http.server 8000` 후
  `http://localhost:8000/?n=철수&id=2026-0001&s=1` 열기
- 로직 테스트: `node --test`

### GitHub Pages 켜기 (최초 1회, 병합 후)

저장소 Settings → Pages → Source를 **Deploy from a branch**,
Branch를 **`main` / `/docs`**로 지정. 저장하면 위 주소로 배포된다.

## 로드맵

- [x] PN532 I2C 통신 확립 ← **현재 브랜치**
- [x] 발급 스테이션 (닉네임 입력 → 카드에 URL NDEF 쓰기)
- [x] GitHub Pages 뷰어 (URL 파라미터 → 개인화 화면)
- [x] 도장 찍기 (전시관 리더: URL 읽어 `s`에 번호 추가 후 다시 쓰기)
- [x] 카드 초기화 (확인 팝업 포함)

### 나중으로 미룬 것

Supabase 연동, 사용자 인증, 리더 실시간 반응, NTAG 쓰기 비밀번호, 분실 대응 자동화.
