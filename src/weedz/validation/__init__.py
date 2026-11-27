"""Stage-by-stage validation of the pipeline on public human-labelled datasets.

Each check runs real pipeline code over a frozen split of a public dataset and
returns rates with Wilson intervals. `uv run main.py validate --help` lists them.
"""
