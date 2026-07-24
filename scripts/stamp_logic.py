"""도장 리더 순수 로직 — 하드웨어 없음, 단위 테스트 대상."""

from urllib.parse import urlparse, parse_qs

from card import BASE


def is_our_url(url):
    """우리 카드 URL인지: BASE로 시작 + id 파라미터가 비어있지 않음."""
    if not url or not url.startswith(BASE):
        return False
    q = parse_qs(urlparse(url).query, keep_blank_values=True)
    return bool(q.get("id", [""])[0])


def _split_query(url):
    """URL을 (물음표 앞부분, [(key, raw_value), ...])로 나눈다. 값 원문 보존."""
    base, _, query = url.partition("?")
    pairs = []
    if query:
        for part in query.split("&"):
            key, _, val = part.partition("=")
            pairs.append((key, val))
    return base, pairs


def add_stamp(url, exhibit_id):
    """s에 exhibit_id를 중복 없이 추가. (new_url, changed) 반환. n·id 원문 보존."""
    base, pairs = _split_query(url)
    s_raw = ""
    for key, val in pairs:
        if key == "s":
            s_raw = val

    seen = []
    for tok in s_raw.split(","):
        tok = tok.strip()
        if tok.isdecimal() and int(tok) not in seen:
            seen.append(int(tok))

    if exhibit_id in seen:
        return url, False

    seen.append(exhibit_id)
    new_s = ",".join(str(x) for x in seen)

    new_pairs = []
    replaced = False
    for key, val in pairs:
        if key == "s":
            new_pairs.append((key, new_s))
            replaced = True
        else:
            new_pairs.append((key, val))
    if not replaced:
        new_pairs.append(("s", new_s))

    new_query = "&".join(f"{k}={v}" for k, v in new_pairs)
    return f"{base}?{new_query}", True
