"""Required public image credit, displayed as plain text rather than untrusted HTML."""


def photo_credit(
    attribution: str, media_license: str, metadata_license: str, source_url: str
) -> str:
    names = {
        "cc0": "CC0",
        "cc0-1.0": "CC0 1.0",
        "cc-by": "CC BY",
        "cc-by-3.0": "CC BY 3.0",
        "cc-by-4.0": "CC BY 4.0",
    }
    media = names.get(media_license.lower(), media_license)
    metadata = names.get(metadata_license.lower(), metadata_license)
    return (
        f"Photo: {attribution}. Media licence: {media} [{media_license}]. "
        f"Metadata licence: {metadata} [{metadata_license}]. Source: {source_url}. "
        "Normalized upright RGB PNG; metadata removed."
    )
