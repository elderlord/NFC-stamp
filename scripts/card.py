"""공유 카드/NDEF/URL 로직 — 발급·도장·초기화가 공통으로 쓴다. 하드웨어 없음."""

BASE = "https://elderlord.github.io/NFC-stamp/"


class CardError(ValueError):
    """카드/URL 처리 검증 실패."""


def format_uid(raw):
    """UID 바이트 → 대문자 hex 문자열(구분자 없음)."""
    return "".join(f"{b:02X}" for b in raw)


# --- NDEF URI 코덱 ---
_URI_PREFIXES = {
    0x00: "",
    0x01: "http://www.",
    0x02: "https://www.",
    0x03: "http://",
    0x04: "https://",
}
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
    if len(payload) > 250:
        raise CardError("URI가 너무 깁니다(단일 NDEF 레코드 한도 초과)")
    record = bytes([0xD1, 0x01, len(payload), 0x55]) + payload
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    return tlv


def decode_ndef_uri(data):
    """NTAG 사용자 메모리 바이트 → URI 문자열. NDEF URI 레코드가 아니면 None."""
    if len(data) < 2 or data[0] != 0x03:
        return None
    msg_len = data[1]
    record = data[2:2 + msg_len]
    if len(record) < 4 or record[3] != 0x55:
        return None
    payload_len = record[2]
    payload = record[4:4 + payload_len]
    if not payload:
        return None
    prefix = _URI_PREFIXES.get(payload[0], "")
    try:
        return prefix + payload[1:].decode("utf-8")
    except UnicodeDecodeError:
        # 손상된/반쯤 써진 카드: 유효한 UTF-8이 아니면 해독 불가로 처리
        return None


def has_ndef(data):
    """사용자 메모리 첫 바이트로 기존 NDEF 존재 판정."""
    return len(data) >= 2 and data[0] == 0x03 and data[1] > 0


def pad_pages(tlv):
    """4바이트 페이지 배수로 0x00 패딩."""
    return tlv + bytes((-len(tlv)) % 4)
