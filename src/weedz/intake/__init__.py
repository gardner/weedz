"""Intake of approved reports from devices (issue #57).

Only a report the person approved on their phone is sent, with a submitter token. A
cropped image comes only with explicit per-report consent and a licence, and keeps only
its pixels. Reports are stored apart from the discovery evidence, never published, and
can be withdrawn by the submitter.
"""
