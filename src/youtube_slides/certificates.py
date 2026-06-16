from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def resolve_ca_bundle() -> str | None:
    """Return the bundled CA certificate bundle when available."""

    try:
        import certifi
    except Exception:
        return None

    try:
        ca_bundle = certifi.where()
    except Exception:
        return None

    return ca_bundle if Path(ca_bundle).is_file() else None


def certificate_env(ca_bundle: str | None = None) -> dict[str, str]:
    ca_bundle = ca_bundle or resolve_ca_bundle()
    if not ca_bundle:
        return {}
    return {
        "SSL_CERT_FILE": ca_bundle,
        "REQUESTS_CA_BUNDLE": ca_bundle,
    }


@contextmanager
def temporary_certificate_env(ca_bundle: str | None = None) -> Iterator[None]:
    updates = certificate_env(ca_bundle)
    if not updates:
        yield
        return

    original = {name: os.environ.get(name) for name in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
