"""Validate the documented ASR scene envelope before retaining caption identity."""


def segment_words(segments: object) -> list[dict]:
    if not isinstance(segments, list):
        raise ValueError("Transcript scenes require segments containing words lists")
    result = []
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("words"), list):
            raise ValueError("Transcript segments require words lists")
        words = segment["words"]
        if any(not isinstance(word, dict) for word in words):
            raise ValueError("Transcript words must be timestamped word objects")
        result.extend(words)
    return result


def flatten_transcript(measured: object) -> list[dict]:
    if not isinstance(measured, dict) or not isinstance(measured.get("scenes"), list):
        raise ValueError("Transcript requires a scenes array with scene and file identities")
    flattened, seen = [], set()
    for scene in measured["scenes"]:
        if not isinstance(scene, dict):
            raise ValueError("Transcript records require scene and file identities")
        number, filename = scene.get("scene"), scene.get("file")
        if (
            type(number) is not int
            or number < 1
            or number in seen
            or not isinstance(filename, str)
            or not filename.strip()
        ):
            raise ValueError(
                "Transcript scene must be a unique positive integer and file a nonempty string"
            )
        seen.add(number)
        flattened.append(
            {"scene": number, "file": filename, "words": segment_words(scene.get("segments"))}
        )
    return flattened
