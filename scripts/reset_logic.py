"""카드 초기화 순수 로직 — 하드웨어 없음, 단위 테스트 대상."""

from urllib.parse import urlparse, parse_qs

from stamp_logic import is_our_url


def describe_card(url):
    """카드 현재 내용을 사람이 읽을 한 줄 요약으로. 카드에 쓰지 않는다."""
    if url is None:
        return "빈 카드 또는 해독 불가"
    if not is_our_url(url):
        return "우리 카드 아님"
    q = parse_qs(urlparse(url).query, keep_blank_values=True)
    nickname = q.get("n", [""])[0]      # parse_qs가 퍼센트 인코딩을 디코드
    card_id = q.get("id", [""])[0]
    visits = q.get("s", [""])[0] or "없음"
    return f"닉네임: {nickname} · ID: {card_id} · 방문: {visits}"
