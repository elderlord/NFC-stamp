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


# --- NDEF URI 코덱 ---------------------------------------------------------

# NDEF URI 접두사 코드 (필요한 것만)
_URI_PREFIXES = {
    0x00: "",
    0x01: "http://www.",
    0x02: "https://www.",
    0x03: "http://",
    0x04: "https://",
}
# 인코딩 시 긴 접두사부터 매칭
_PREFIX_MATCH = [
    (0x02, "https://www."),
    (0x01, "http://www."),
    (0x04, "https://"),
    (0x03, "http://"),
]


def encode_ndef_uri(url):
    """URI 문자열 → NTAG에 쓸 NDEF 메시지 TLV 바이트 (03 <len> <record> FE)."""
    prefix_code = 0x00
    rest = url
    for code, p in _PREFIX_MATCH:
        if url.startswith(p):
            prefix_code = code
            rest = url[len(p):]
            break
    payload = bytes([prefix_code]) + rest.encode("utf-8")
    if len(payload) > 255:
        raise IssueError("URI가 너무 깁니다(단일 NDEF 레코드 한도 초과)")
    record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload  # SR URI 레코드
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    return tlv


def decode_ndef_uri(data):
    """NTAG 사용자 메모리 바이트 → URI 문자열. NDEF URI 레코드가 아니면 None."""
    if len(data) < 2 or data[0] != 0x03:
        return None
    msg_len = data[1]
    record = data[2:2 + msg_len]
    if len(record) < 4 or record[3] != 0x55:  # 'U' 타입
        return None
    payload_len = record[2]
    payload = record[4:4 + payload_len]
    if not payload:
        return None
    prefix = _URI_PREFIXES.get(payload[0], "")
    return prefix + payload[1:].decode("utf-8")


def has_ndef(data):
    """사용자 메모리 첫 바이트로 기존 NDEF 존재 판정."""
    return len(data) >= 2 and data[0] == 0x03 and data[1] > 0


def pad_pages(tlv):
    """4바이트 페이지 배수로 0x00 패딩."""
    return tlv + bytes((-len(tlv)) % 4)
