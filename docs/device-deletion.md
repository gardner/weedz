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
specialist report reader, including during an interrupted erasure.

The server then revokes the credential, durably deletes crops, clears report
bodies and content hashes, removes the submitter's abuse-budget rows, and records
completion. Existing report tombstones retain submitter/report ids and received
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
store listing. That public route and the mobile settings screen are still release
requirements tracked in [#107](https://github.com/gardner/weedz/issues/107);
this API does not by itself provide them. The broader #101 remains open until
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

## Mobile integration contract

The future settings action should ask the person to confirm deletion, stop upload
retries, call `DELETE /submitter`, and retain the credential privately until the
completion receipt is confirmed. Show a recoverable pending state after a failed
request; do not claim success because uploads now receive 401. After confirmation,
clear the credential and local submitted-report receipts as the mobile privacy
design requires. Local photo-library originals are never deleted by this API.
