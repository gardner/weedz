"""Signed model bundles for phones (issue #59).

A bundle is a manifest plus content-addressed artefacts: the image tower, the fixed
prompts' text embeddings, the regional watchlist and lookalikes, and the versions a
report must carry. The manifest is canonical JSON in an Ed25519-signed DSSE envelope, so a
phone checks who published it before parsing it, and checks every artefact by hash.
"""
