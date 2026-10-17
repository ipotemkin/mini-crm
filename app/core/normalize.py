"""Search text normalization (casefold, ё→е, phone digits)."""

import re

_PHONE_RE = re.compile(r"\D+")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().casefold().replace("ё", "е")
    return " ".join(text.split())


def digits_only(value: str | None) -> str:
    if not value:
        return ""
    return _PHONE_RE.sub("", value)


def build_client_search_text(
    name: str,
    contact_person: str | None,
    email: str | None,
    phone: str | None,
    source: str | None,
    notes: str | None,
) -> str:
    parts = [
        normalize_text(name),
        normalize_text(contact_person),
        normalize_text(email),
        digits_only(phone),
        normalize_text(source),
        normalize_text(notes),
    ]
    return " ".join(p for p in parts if p)


def build_deal_search_text(
    title: str,
    description: str | None,
    client_name: str | None,
) -> str:
    parts = [
        normalize_text(title),
        normalize_text(description),
        normalize_text(client_name),
    ]
    return " ".join(p for p in parts if p)


def search_tokens(query: str) -> list[str]:
    normalized = normalize_text(query)
    if not normalized:
        return []
    tokens = normalized.split()
    phone = digits_only(query)
    if phone and phone not in tokens:
        tokens.append(phone)
    return tokens
