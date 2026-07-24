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
