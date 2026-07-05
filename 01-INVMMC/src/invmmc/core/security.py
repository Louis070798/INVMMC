import hmac


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def verify_shared_secret(received: str | None, expected: str) -> bool:
    if not expected:
        return True
    if not received:
        return False
    return constant_time_equals(received, expected)
