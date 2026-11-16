"""Required public image credit, displayed as plain text rather than untrusted HTML."""

NAMES = {
    "cc0": "CC0",
    "cc0-1.0": "CC0 1.0",
    "cc-by": "CC BY",
    "cc-by-3.0": "CC BY 3.0",
    "cc-by-4.0": "CC BY 4.0",
    "cc-by-nc": "CC BY-NC",
    "cc-by-nc-3.0": "CC BY-NC 3.0",
    "cc-by-nc-4.0": "CC BY-NC 4.0",
}
LICENCE_URIS = {
    "cc0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "cc-by-3.0": "https://creativecommons.org/licenses/by/3.0/",
    "cc-by-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "cc-by-nc-3.0": "https://creativecommons.org/licenses/by-nc/3.0/",
    "cc-by-nc-4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
}


def _licence(raw: str) -> str:
    code = raw.lower()
    uri = LICENCE_URIS.get(code)
    return f"{NAMES.get(code, raw)} [{raw}]" + (f" ({uri})" if uri else "")


def photo_credit(
    attribution: str, media_license: str, metadata_license: str, source_url: str
) -> str:
    return (
        f"Photo: {attribution}. Media licence: {_licence(media_license)}. "
        f"Metadata licence: {_licence(metadata_license)}. Source: {source_url}. "
        "Normalized upright RGB PNG; metadata removed."
    )
