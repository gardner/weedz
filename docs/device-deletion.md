# Delete a device's report data

The intake API supports `DELETE /submitter` with the device's usual bearer token.
No body or submitter id is sent. It erases every report and crop owned by that
credential and revokes the credential. It cannot act for another device.

The response is HTTP 200 with:

```json
{
  "status": "deleted",
  "requested_at": "2026-11-14T22:00:00.000000+00:00",
  "completed_at": "2026-11-14T22:00:01.000000+00:00"
}
```

A network failure or server error is **not** confirmation of deletion. Retry the
same request with the same token until the completion receipt arrives. The
original secret can authenticate this operation after revocation only when a
deletion was already requested. It cannot upload, read receipts, or withdraw
individual reports after revocation. A token revoked independently by the
operator cannot start a new deletion: use the verified operator procedure below.
Wrong secrets, reviewer tokens and missing tokens receive 401.

## Durability and retained data

The server first commits a deletion marker in the reports database, under the
same SQLite write lock used by uploads. Both admission and final storage check
that marker. An upload already authenticated, receiving its body, or decoding
its crop cannot store content after the marker commits. Reports already committed
are included in the erasure. Marked submitters are immediately hidden from the
specialist report reader, including during an interrupted erasure. A read already
materializing report bodies finishes its database snapshot before the deletion
marker commits. Objects returned by an earlier read cannot be revoked; consumers
must not keep stale snapshots as a substitute for current withdrawal state.

The server then revokes the credential, durably deletes crops, clears report
bodies, content hashes and consent records, removes the submitter's abuse-budget rows, sweeps
unreferenced crops left by crashed uploads under the reports write lock, and
records completion. Committed crops belonging to other devices are preserved. Existing report tombstones retain submitter/report ids and received
and withdrawn times. Earlier withdrawal times are preserved. A deletion marker
retains the submitter id and request/completion times to prevent resurrection and
make retries stable. The credential's existing hash, operator label and issue/
revocation times remain in the separate credentials database; the hash is needed
to authenticate a deletion retry. No token secret is stored or returned.

The marker is deliberately committed before erasure. If a later step fails, the
write barrier remains in force and the operation can resume safely. Startup
finishes pending deletions before serving requests. A completed response is
returned only after the durable erasure finishes. This does not erase independent
backups, exports or downstream copies; their handling belongs in the deployment's
retention and sharing policy.

## Lost-phone operator procedure

Provide a public deletion contact address or web form in the privacy policy and
store listing. The app now provides [deletion settings](mobile-device-settings.md); publishing
and verifying the real public route is still a release requirement tracked in
[#107](https://github.com/gardner/weedz/issues/107). This API does not publish it. The broader #101 remains open until
those requirements are met.

1. Verify the request against the operator's original enrollment records. A
   submitter number alone is not proof of ownership. Do not ask for or log the
   bearer token in email or a web form. If identity is uncertain, resolve it with
   the enrolled participant before erasing any data.
2. Find the correct enrollment with `uv run main.py intake list`.
3. Run `uv run main.py intake delete-submitter --id ID --intake-dir data/intake`.
   This works even if the lost device was already revoked. Check the success
   message; after an error, repeat the same command. Unknown ids are refused.
4. Tell the participant what was erased and which id/time records and credential
   records remain, using the retention policy above.

`intake revoke` continues to revoke access **without** deleting reports. It is
useful for a compromised credential, but is not a data-deletion operation.

## Mobile settings and deployment

[Mobile Settings](mobile-device-settings.md) implements secure pilot enrollment,
confirmation, durable pending intent, authenticated deletion and restart recovery.
The client retains the credential after errors and clears it only after a valid
completed receipt. It never modifies photo-library originals. There is no report
upload worker yet; that future worker must share the enrollment's deletion barrier
and stop uploads/retries while deletion is pending.

Configure the real HTTPS intake and public deletion request URLs through the
GitHub Actions secrets documented in [mobile builds](mobile-builds.md). A secret
containing a URL does not publish the route: the publisher must verify that the
public page reaches the operator procedure above and link it in the privacy policy
and store listing. Issue #107 remains open for actual deployment/public-route and
real-device secure-storage/deletion/accessibility verification.
