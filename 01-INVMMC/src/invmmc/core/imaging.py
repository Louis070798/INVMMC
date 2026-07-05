"""Hash anh phuc vu phat hien chung tu gui trung.

- SHA-256: trung tuyet doi tung byte (forward/gui lai cung file).
- dHash (difference hash 64-bit): trung thi giac khi Telegram nen lai anh;
  nguong hamming <= DHASH_DUPLICATE_THRESHOLD la trung.
  Nguong de chat (6/64) vi bien lai ngan hang cung app co layout rat giong nhau,
  nguong rong se bao trung nham giua cac giao dich khac nhau.
"""

from pathlib import Path

DHASH_DUPLICATE_THRESHOLD = 6
_DHASH_SIZE = 8


def dhash_hex(image_path: str | Path) -> str | None:
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            gray = img.convert("L").resize((_DHASH_SIZE + 1, _DHASH_SIZE), Image.LANCZOS)
            pixels = list(gray.getdata())
    except Exception:
        return None

    bits = 0
    width = _DHASH_SIZE + 1
    for row in range(_DHASH_SIZE):
        for col in range(_DHASH_SIZE):
            left = pixels[row * width + col]
            right = pixels[row * width + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return format(bits, "016x")


def hamming_hex(hash_a: str | None, hash_b: str | None) -> int | None:
    if not hash_a or not hash_b:
        return None
    try:
        return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")
    except ValueError:
        return None
