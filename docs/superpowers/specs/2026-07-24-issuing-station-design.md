# 설계: 발급 스테이션 v1

작성일: 2026-07-24
상태: 승인 대기
브랜치: `claude/pn532-nfc-i2c-wiring-o9x7b1`

## 목적

관람객에게 NFC 카드(NTAG215)를 발급한다. 운영자가 발급 데스크에서 닉네임과
인구통계(성별·연령대)를 입력하고 카드를 리더에 올려놓으면, 카드의 UID를 식별번호로
삼아 개인화 URL을 NDEF로 굽는다. 이 URL은 GitHub Pages 뷰어가 읽어 도장판을
그린다(뷰어는 이미 배포됨). 발급 시점의 인구통계는 Pi 로컬 CSV 로그에만 기록한다.

이 문서는 **발급 스테이션(카드에 쓰기 + 로그)** 하나만 다룬다. 도장 찍기(전시관
리더), 카드 초기화는 별도 스펙에서 다룬다. 셋은 여기서 정의한 데이터 계약을 공유한다.

## 범위

포함:
- 터미널(SSH)에서 닉네임·성별·연령대 입력
- 카드 UID 읽기 → 개인화 URL 조립 → NDEF 쓰기 → 읽기 검증
- 발급 로그 CSV append (성별·연령대 코드 포함)
- 이미 발급된 카드 덮어쓰기 시 2단계 확인
- 순수 로직(URL 조립·코드 검증·로그 포맷)의 단위 테스트

제외 (나중에 논의):
- 라즈베리파이 화면 UI (지금은 SSH 터미널; UI는 향후 추가)
- 도장 찍기·카드 초기화 (별도 스펙)
- 인구통계를 카드 URL/서버로 보내는 것 (Pi 로컬 로그에만 둠)
- Supabase 연동, NTAG 쓰기 비밀번호, 분실 자동 대응

## 아키텍처 / 파일 구성

뷰어와 동일한 "순수 로직 + 얇은 I/O" 패턴을 따른다.

| 파일 | 역할 | 하드웨어 |
|---|---|---|
| `scripts/issue_logic.py` | 순수 함수: URL 조립, UID 포맷, 코드 검증, 로그 행 포맷 | 없음 (테스트 가능) |
| `scripts/pn532_issue.py` | 얇은 CLI + 하드웨어 I/O: 입력, UID 읽기, NDEF 쓰기/검증, 로그 append | 있음 |
| `data/issue_log.csv` | Pi 로컬 append-only 발급 로그 | — (**gitignore**) |

`issue_logic.py`가 노출하는 주요 인터페이스:

- `BASE = "https://elderlord.github.io/NFC-stamp/"` — 뷰어와 일치하는 단일 상수
- `format_uid(raw: bytes) -> str` — 7바이트 → 대문자 hex(구분자 없음), 예 `"04A1B2C3D4E580"`
- `build_url(base: str, nickname: str, uid: str) -> str` — 닉네임 URL 인코딩, `?n=..&id=<uid>&s=`
- `GENDERS = {"m", "f"}`, `is_valid_gender(code) -> bool`
- `AGE_GROUPS = {1..7}`, `is_valid_age_group(n) -> bool`
- `log_fields(issued_at, uid, nickname, gender, age_group) -> list[str]` — CSV 한 행(값 리스트).
  실제 파일 기록은 파이썬 `csv` 모듈로 수행해 닉네임의 쉼표·따옴표를 안전하게 이스케이프.

## 데이터 계약

### 카드에 굽는 URL

```
https://elderlord.github.io/NFC-stamp/?n=<URL인코딩 닉네임>&id=<UID>&s=
```

- `id` = UID 대문자 hex(구분자 없음). UID는 칩마다 고유하므로 카운터·중복대조 불필요.
- `s` = 빈값(발급 시 도장 0개).
- 파라미터 집합(`n`, `id`, `s`)은 뷰어 `parseParams`가 읽는 계약과 정확히 일치.

### 발급 로그 CSV

컬럼: `issued_at, uid, nickname, gender, age_group`

| 컬럼 | 값 |
|---|---|
| `issued_at` | ISO 8601 로컬 시각 |
| `uid` | 대문자 hex UID |
| `nickname` | 원문 닉네임 |
| `gender` | `m` 또는 `f` |
| `age_group` | `1`~`7` (코드값) |

**코드 범례** (issue_logic.py 및 README에 명시):

- 성별: `m` = 남, `f` = 여
- 연령대:
  1. 초등학교 저학년(초1~3)
  2. 초등학교 고학년(초4~6)
  3. 10대(중학생 이상)
  4. 20대
  5. 30대
  6. 40대
  7. 50대 이상

로그 파일이 없으면 헤더 행(`issued_at,uid,nickname,gender,age_group`)을 먼저 쓴 뒤
데이터 행을 append 한다. 로그는 개인정보를 담으므로 저장소에 커밋하지 않는다
(`.gitignore`에 `data/`).

## 조작 흐름 (발급 1건, 반복 루프)

1. **입력**: 닉네임(빈값 불가) → 성별(남/여 선택 → `m`/`f`) → 연령대(1~7 메뉴 선택)
2. `"카드를 리더에 올려놓으세요"` 출력 → 카드가 감지될 때까지 폴링 대기
   (PN532 패시브 폴링. 카드를 올려둔 상태에서 읽기·쓰기·검증까지 진행)
3. **UID 읽기** → `format_uid` → `build_url(BASE, 닉네임, UID)`
4. **기존 NDEF 감지**: 카드에 이미 NDEF 데이터가 있으면 **2단계 확인** —
   (a) `"덮어쓸까요? (y/N)"` → `y`, (b) `"확인: UID 뒷 4자리 입력"` → 일치 —
   둘 다 통과해야 덮어씀. 빈 카드면 바로 진행.
5. **NDEF 쓰기** → **읽기 검증**: 카드를 다시 읽어 기록된 URL이 조립한 URL과 일치하는지 확인.
6. 검증 성공 시에만 **로그 append**(`csv` 모듈) →
   `"발급 완료: <UID>. 카드를 치우세요."` → 루프 상단으로(다음 사람).

## 에러 / 엣지 처리

| 상황 | 처리 |
|---|---|
| 닉네임 빈값/공백만 | 재입력 요구 |
| 성별·연령대 오입력 | 재입력 요구 |
| 카드 감지 타임아웃(기본 30초) | 이번 건 취소, 루프 상단으로 (Ctrl+C로 프로그램 종료) |
| NDEF 쓰기 실패 / 검증 불일치 | 에러 출력, **로그 미기록**, 재시도 안내 |
| URL이 NTAG215 사용자 메모리(504B) 초과 위험 | `build_url`에서 닉네임 길이 가드(최대 20자). 초과 시 거부·재입력 |
| 이미 발급된 카드 | 2단계 확인 후에만 덮어쓰기 |
| 같은 카드 재발급(동일 UID) | 로그에 새 행 추가(재발급 기록으로 남김) |

## 테스트

- 러너: 파이썬 내장 `python -m unittest` (의존성 불필요). 순수 로직만 대상.
- 파일: `test/test_issue_logic.py` — `scripts/issue_logic.py`를 import.
- 케이스:
  - `format_uid`: `bytes([0x04,0xA1,0xB2,0xC3,0xD4,0xE5,0x80])` → `"04A1B2C3D4E580"`
  - `build_url`: 한글 닉네임 URL 인코딩, `id=<uid>`, `s` 빈값, BASE 정확
  - **뷰어 계약 정합**: 조립한 URL을 `urllib.parse`로 파싱해 `n`·`id`·`s` 키가
    기대대로(닉네임 디코드 일치, id=uid, s 빈 문자열)인지
  - 코드 검증: `is_valid_gender`(m/f 참, 그 외 거짓), `is_valid_age_group`(1~7 참, 0·8 거짓)
  - `log_fields` + `csv` 기록: 닉네임에 `,`·`"` 포함 시 이스케이프 결과가 되읽혔을 때 원문과 일치
  - 닉네임 길이 가드: 20자 초과 거부
- 하드웨어 I/O(`pn532_issue.py`)는 실제 NTAG215 카드로 수동 검증(쓰기→아이폰 인식→뷰어 표시).

## 열린 질문 / 이후 작업

- 라즈베리파이 화면 UI(터미널 대체) — 향후 별도 작업.
- 도장 찍기 스펙에서 동일 URL 계약(`s`에 번호 추가)을 그대로 사용.
- 발급 로그를 이용한 인구통계 집계 리포트 — 필요 시 별도 유틸.
