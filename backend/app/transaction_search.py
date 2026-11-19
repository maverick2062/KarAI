import hashlib
import hmac
import re
from decimal import Decimal, InvalidOperation

from app.config import get_settings


_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def searchable_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    tokens: set[str] = set()
    for match in _TOKEN_PATTERN.findall(value.casefold()):
        if len(match) < 3:
            tokens.add(match)
            continue
        token = match[:5]
        tokens.update(token[:length] for length in range(3, len(token) + 1))
    return tokens


def search_term_hash(user_id: str, token: str) -> str:
    key = hashlib.sha256(get_settings().encryption_key.encode("utf-8")).digest()
    payload = f"transaction-search-v1:{user_id}:{token}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def query_search_hashes(user_id: str, query: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(query.casefold())
    prefixes = (token[:5] if len(token) >= 3 else token for token in tokens)
    return [search_term_hash(user_id, token) for token in dict.fromkeys(prefixes)]


def parse_amount_search(query: str) -> tuple[bool, Decimal | None]:
    normalized = query.replace(",", "").replace("₹", "").strip()
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return False, None
    if (
        not amount.is_finite()
        or abs(amount) >= Decimal("100000000000000")
        or amount.as_tuple().exponent < -2
    ):
        return True, None
    return True, amount
