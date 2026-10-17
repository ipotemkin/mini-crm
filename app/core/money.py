"""Money helpers: kopecks <-> Decimal."""

from decimal import Decimal, ROUND_HALF_UP


def to_kopecks(value: Decimal | None) -> int | None:
    if value is None:
        return None
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(quantized * 100)


def from_kopecks(value: int | None) -> Decimal | None:
    if value is None:
        return None
    return (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"))
