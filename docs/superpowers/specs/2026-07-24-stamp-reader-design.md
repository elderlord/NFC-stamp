# 설계: 도장 찍기 (전시관 리더) v1

작성일: 2026-07-24
상태: 승인 대기
브랜치: `claude/pn532-nfc-i2c-wiring-o9x7b1`

## 목적

전시관마다 놓인 리더(Pi)가 관람객 카드를 만나면, 카드에 저장된 개인화 URL을 읽어
`s`(방문 전시관 목록)에 **자기 전시관 번호**를 더해 다시 굽는다. 도장이 찍히는 것이
곧 URL이 갱신되는 것이다. 서버가 없고 모든 상태는 카드 URL에 있다.

발급 스테이션에서 만든 NDEF 코덱과 URL 계약을 그대로 재사용한다. 이 작업에서 그
공유 부분을 `card.py`로 추출한다.

## 범위

포함:
- 리더가 자기 전시관 번호를 설정 파일에서 읽음
- 카드 URL 읽기 → 우리 카드 판정 → `s`에 번호 추가 → 다시 쓰기 → 읽기 검증
- 재방문(이미 있는 번호), 우리 카드 아님(빈/남의 태그) 처리
- 미래의 물리 조명을 위한 피드백 인터페이스(v1은 터미널 프로그레스 바)
- 공유 카드/NDEF 로직을 `card.py`로 추출(발급·도장·향후 초기화가 공용)
- 순수 로직 단위 테스트

제외 (나중에 논의):
- 전시관 명단(이름·개수)의 중앙화 — 별도 스펙(`exhibits.json` 단일 진실원, 뷰어가 읽음)
- 물리 하우징·S자 라인 조명 하드웨어 (피드백 인터페이스만 준비)
- 카드 초기화 (별도 스펙)
- Supabase, 실시간 반응

## 아키텍처 / 파일 구성

공유 모듈 추출 + 리더 신규.

| 파일 | 역할 | 하드웨어 |
|---|---|---|
| `scripts/card.py` | **(신규, 추출)** BASE, format_uid, NDEF 코덱, CardError | 없음 |
| `scripts/issue_logic.py` | 발급 전용(build_url, 검증, log_fields, 라벨). 공유분은 card에서 import | 없음 |
| `scripts/stamp_logic.py` | **(신규)** is_our_url, add_stamp | 없음 |
| `scripts/pn532_stamp.py` | **(신규)** 리더 루프 + Feedback (하드웨어 I/O) | 있음 |
| `test/test_card.py` | **(신규)** NDEF 코덱 테스트(기존 test_issue_logic에서 이동) | — |
| `test/test_stamp_logic.py` | **(신규)** 도장 로직 테스트 | — |
| `test/test_issue_logic.py` | 발급 전용 테스트만 남김 | — |

### 공유 추출(card.py)

`card.py`가 소유: `BASE`, `format_uid`, `encode_ndef_uri`, `decode_ndef_uri`,
`has_ndef`, `pad_pages`, `CardError`(기존 IssueError를 대체).

`issue_logic.py`는 발급 전용(`build_url`, `is_valid_gender/age_group`, `log_fields`,
`GENDER_LABELS`/`AGE_LABELS`, `MAX_NICKNAME_LEN`, `LOG_HEADER`)만 유지하고, 필요한
공유 심볼은 `from card import ...`로 가져온다. 하위호환을 위해 `issue_logic`은
`IssueError = card.CardError` 별칭을 유지한다(기존 발급 코드·테스트가 `il.IssueError`를
그대로 참조할 수 있게). 발급 검증(`build_url`, `log_fields`)도 이 오류 타입을 쓴다.

**불변식**: 리팩터 후에도 기존 발급 동작·테스트가 전부 통과해야 한다. NDEF 코덱
테스트는 `test_card.py`로 이동하고, `test_issue_logic.py`는 발급 전용만 남긴다.
`pn532_issue.py`의 import는 새 위치에 맞춰 갱신한다.

## 데이터 계약 / stamp_logic 인터페이스 (순수)

- `is_our_url(url: str | None) -> bool`
  - `url`이 None이 아니고 `BASE`로 시작하며 `id` 파라미터가 비어있지 않으면 True
- `add_stamp(url: str, exhibit_id: int) -> tuple[str, bool]`
  - 쿼리를 파싱하되 **`n`·`id`는 원문 그대로 보존**(재인코딩하지 않음).
  - `s`는 순서를 유지한 채 중복을 제거한 정수 목록으로 다룬다.
  - `exhibit_id`가 이미 `s`에 있으면 `(url, False)` (변경 없음).
  - 없으면 목록 끝에 추가하고 `?n=<원문>&id=<원문>&s=<쉼표목록>`으로 재조립해
    `(new_url, True)` 반환.
  - `s`에 이미 있던 알 수 없는 번호도 보존한다(리더는 자기 번호만 추가).

리더 상태 셋: **NEW / ALREADY / FOREIGN**.

## 리더 흐름 (한 번의 태그)

1. **시작**: `data/exhibit_id`(gitignore)를 읽어 양의 정수로 파싱. 없거나 정수가
   아니면 안내 후 종료(`echo 1 > data/exhibit_id`).
2. **루프**: 카드 감지까지 대기.
3. 사용자 메모리 읽기 → `decode_ndef_uri` → `url`.
4. `is_our_url(url)`이 False → **FOREIGN**: `우리 카드가 아니에요` (**쓰기 없음**).
5. `add_stamp(url, exhibit_id)`의 `changed`가 False → **ALREADY**:
   `이미 방문한 전시관이에요` (**쓰기 없음**).
6. `changed`가 True → **NEW**: `new_url`을 NDEF로 쓰기 → 읽기 검증(다시 읽어 일치
   확인) → 성공 시 피드백 연출(begin→update로 바 채움 ~1.5초→done) +
   `도장 완료 (전시관 N)`. 쓰기/검증 실패 → 에러 + 재시도 안내(로그·성공 주장 없음).
7. **카드 제거 대기** 후 다음 루프(같은 올려둠에 중복 처리 방지).

리더는 전역 전시관 명단(Python)을 두지 않는다. 자기 번호만 설정에서 읽고, 피드백은
"전시관 N"으로 표시한다. 예쁜 이름은 뷰어가 보여주므로 뷰어(JS) 명단과의 이중 관리를
피한다.

## 피드백 인터페이스 (미래 물리 조명 대비)

- `Feedback` 인터페이스: `begin(exhibit_id)`, `update(fraction: float)`,
  `done(exhibit_id)`, `already(exhibit_id)`, `foreign()`.
- v1 `TerminalFeedback`: `\r`(캐리지 리턴)로 채워지는 프로그레스 바
  (예 `[■■■■■□□□] 전시관 1`)를 약 1.5초 렌더한 뒤 `도장 완료 (전시관 1)`.
  already/foreign은 한 줄 메시지.
- 미래: 같은 인터페이스에 물리 구현(`LedFeedback`, 네모난 S자 라인 조명이
  프로그레스처럼 차오르는 연출)을 끼우면 리더 로직은 바뀌지 않는다.

## 에러 / 엣지 처리

| 상황 | 처리 |
|---|---|
| `data/exhibit_id` 없음/비정수/음수 | 시작 시 안내 후 종료 |
| 우리 카드 아님 / 빈 카드 / 남의 태그 | **절대 쓰지 않음** (판정: BASE로 시작 + id 존재) |
| 이미 방문한 전시관 | 쓰기 없이 안내 |
| NDEF 쓰기/검증 실패(카드 이탈 등) | 에러 + 재시도 안내. NTAG 다중 페이지 쓰기라 완전 원자성은 없어, 읽기 검증으로 최종 상태를 판정하고 실패 시 다시 대면 복구(같은 번호 재기록은 멱등). 이 리스크는 문서로 남긴다 |
| 루프 중 예외 | per-card catch-all로 리더 생존(발급과 동일 패턴) |

## 테스트

- 러너: `python -m unittest`(의존성 없음). 순수 로직만.
- `test/test_card.py` — NDEF 코덱(기존 test_issue_logic에서 이동): encode 바이트,
  round-trip, 접두사 없음, 비-NDEF None, has_ndef, pad_pages, 길이 가드.
- `test/test_stamp_logic.py`:
  - `is_our_url`: BASE+id True / 다른 URL False / None False
  - `add_stamp`: 빈 `s`에 추가(`s=1`, changed True) / 이미 있음(unchanged, False) /
    다른 번호 추가(`s=1,2`) / **`n`·`id` 원문 보존**(재인코딩 안 함) /
    기존 알 수 없는 번호 보존 / 뷰어 계약 정합(파싱 시 n·id·s 기대대로)
- `test/test_issue_logic.py` — 발급 전용만, 회귀 없음(리팩터 후 통과).
- `pn532_stamp.py` — Pi 수동 검증: 발급된 카드 → 리더에 대기 → 아이폰에서 `s`가
  채워져 도장판에 반영 / 재탭 "이미 방문" / 남의 태그·빈 카드 무시.

## 열린 질문 / 이후 작업

- **전시관 명단 중앙화** — `exhibits.json` 단일 진실원을 뷰어가 읽도록(다음 스펙).
- 물리 하우징 + S자 라인 조명 — `Feedback`에 `LedFeedback` 구현 추가.
- NDEF 쓰기 원자성의 한계는 읽기 검증 + 재시도로 완화(위 참조).
