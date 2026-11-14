# Hosting device report intake

The intake supports concurrent processes on **one POSIX host with local storage**.
All processes and operator commands must use the same resolved `--intake-dir` and
run as its owner. SQLite databases, crops and lock files belong on that host's
local filesystem. Do not put them on NFS or another network filesystem or share
this directory between hosts. Multi-host service needs a server database and
coordinated crop storage; this SQLite implementation does not provide it.

`uv run main.py intake serve` starts one process. Several independently started
processes can share the directory, using different ports behind the HTTPS proxy:

```sh
uv run main.py intake serve --intake-dir data/intake --port 8300
uv run main.py intake serve --intake-dir data/intake --port 8301
```

Run those commands in separate terminals or a service manager. Both listeners
are loopback-only by default. Devices must connect through HTTPS, never directly
to the development listeners.

## Ordering and interruption

Each submitter has an owner-only advisory lock file in `turns/`. API uploads hold
its lock from before reading the body through image processing and storage.
API withdrawals and operator `intake withdraw` use the same lock. Other
submitters can proceed independently. Waiting API requests sleep on the event
loop rather than occupying a database worker. Process death releases a lock;
lock files must never be removed while any server or operator process is running.
Cancelling a request waits for an already-running storage worker to finish before
releasing the lock.

Before opening lock files, each process admits at most two operations for one
submitter (including any local owner), and 64 operations in total. Further requests
get retryable 503 responses immediately, without reading their bodies. Local
capacity is released on completion, timeout, cancellation or an open failure;
idle submitter entries are removed. These admission bounds multiply with the
number of processes, while the advisory lock still serializes each submitter
across those processes.

SQLite write transactions still enforce ownership, budgets and withdrawal
barriers. Startup crop cleanup takes the same write transaction as crop creation,
so a second process cannot delete another process's uncommitted upload crop.

A report withdrawal first commits its `withdrawn_at` barrier, hiding the report
from specialist reads and refusing late uploads. It then deletes and fsyncs the
crop and erases content and its hash. A successful `DELETE` response confirms
that physical erasure finished. If the process stops between those steps, the
report remains logically withdrawn and its receipt exposes no crop. Startup or a
repeated `DELETE` finishes the physical erasure. A small pending-erasure record
keeps even unknown-id withdrawals retryable if orphan cleanup fails; it is removed
only after the writer-locked sweep succeeds. Completed retries skip the sweep. A previously returned specialist
snapshot cannot be recalled; callers must not cache report content beyond its use.

An upload interrupted after admission can reuse its unexpired daily budget
reservation only with the same content. Different content under that id gets
409. Completed decoding refusals still cost budget; repeatedly retrying an invalid
image is not free. Temporary admission hashes disappear on successful storage,
refusal, report withdrawal or bulk device deletion, or when their budget window expires during subsequent
admission. Existing report withdrawals and withdrawal retries remain possible
when the daily budget is full.

## Configurable pilot limits

These are operational starting values, not measured production capacity or
agreed phone budgets. `intake serve --help` lists their command-line flags.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--body-idle-seconds` | 30 | Longest gap between body chunks |
| `--body-total-seconds` | 120 | Total body receiving time, including steady uploads |
| `--submitter-wait-seconds` | 130 | Wait for the preceding operation by that submitter |
| `--sqlite-busy-seconds` | 5 | Wait for a database lock |
| `--auth-requests-per-second` | 100 | Process-wide HTTP request refill rate before authentication |
| `--auth-burst` | 200 | Process-wide HTTP request burst before authentication |
| `--reports-per-day` | 100 | New reports and new withdrawal ids per submitter per rolling day |
| `--image-bytes-per-day` | 50000000 | Stored crop bytes per submitter per rolling day |

A body deadline returns 408. Submitter-lock or database contention returns 503
with `Retry-After: 1`; clients retry under the same report id. Daily budgets and
the pre-authentication request budget return 429 with `Retry-After`. Neither a
network error nor a 429/503 confirms withdrawal.

The pre-authentication limiter holds one token bucket, never an address or token
map, and applies to valid and invalid credentials alike. It therefore bounds
lookup noise without retaining IP addresses or trusting forwarding headers. Its
allowance is **per process**, so two workers have twice the aggregate allowance.
The HTTPS proxy should additionally set deployment-wide connection and request
limits to protect the listeners. Choose those limits for the actual network and
worker count; the application bucket does not replace a proxy's connection limit.
