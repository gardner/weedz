# Mobile enrollment and deletion settings

Settings provides a deletion-only intake client. It does not upload reports or
photos. Approval and scanning do not need to wait for this client; the future
uploader must use the same enrollment and refuse to start or retry when deletion
is pending. There are no persisted submitted-report receipts on the phone yet.
The flow never modifies or deletes photo-library originals.

## Deployment configuration

Supply these public URLs through the corresponding GitHub Actions secrets and
pass them to Flutter as compile-time defines:

```sh
flutter build appbundle \
  --dart-define="WEEDZ_INTAKE_BASE_URL=$WEEDZ_INTAKE_BASE_URL" \
  --dart-define="WEEDZ_DELETION_REQUEST_URL=$WEEDZ_DELETION_REQUEST_URL"
```

- `WEEDZ_INTAKE_BASE_URL`: the operator's real HTTPS intake base address. A path
  prefix is supported; `/submitter` is appended within that prefix. Query strings,
  fragments and credentials in this URL are refused. This pre-fills pilot
  enrollment; the operator can supply a different HTTPS address if needed.
- `WEEDZ_DELETION_REQUEST_URL`: a publicly reachable HTTPS deletion request page
  or form, operated by the publisher and linked in the privacy policy and store
  listing. The app opens exactly that URL externally, without appending tokens or
  enrollment identifiers. The route must lead to the verified lost-phone operator
  procedure in [device-deletion.md](device-deletion.md). Never request bearer
  secrets in this channel.

These values become public in the app binary even when supplied as CI secrets.
**Never put a submitter token in a build define, GitHub secret, URL, or log.**
A build without a valid public deletion route explicitly says it is not ready for
store release. Configuration alone does not publish the route: verify its actual
availability and the operator response procedure before submitting to a store.
Issue #107 remains open for that operational verification and real-device checks.

## Pilot enrollment

The operator issues a submitter credential for this installation with
`uv run main.py intake add --label "Pilot phone"`. In Settings, enter the intake
address and that credential. The token field is obscured, with suggestions and
keyboard learning disabled. Saving enrollment is described as a local save, not
proof of server access; it sends nothing. A saved enrollment cannot be silently
replaced while its reports might still exist. Delete it successfully first.

The HTTPS service address is stored together with the token, so later build
configuration changes cannot accidentally send an old credential to a different
service. Enrollment and pending-deletion state use one encrypted secure-storage
value. iOS uses non-synchronizing, device-only Keychain access while unlocked.
Android uses the platform Keystore-backed cipher, a dedicated storage namespace,
`resetOnError: false`, and disabled Android backup. No plaintext token is stored in
app preferences. Storage errors preserve the record and block replacement.

`flutter_secure_storage` 11.2 acknowledges Android writes after `apply()`. A small
background native method then calls synchronous `commit()` for the dedicated
ciphertext, wrapped-key and configuration preferences before Dart acknowledges the
write. This disk barrier is required before starting DELETE and before showing
credential removal as complete. Recheck that adapter against the plugin whenever
its locked version changes. iOS secure writes use the synchronous Keychain API.

## Deletion and recovery

1. Settings explains report/crop deletion, revocation and the retained records.
   The person must confirm; cancelling sends nothing.
2. The client blocks uploads for this enrollment and saves pending intent securely
   before `DELETE /submitter`. A failed secure write starts no request and leaves
   a recoverable pending state in this session.
3. It sends the saved token only in the Authorization header to its saved HTTPS
   service. Redirects are refused. The request is bounded by a 30-second timeout;
   response bodies are bounded to 4096 bytes.
4. Only HTTP 200 with `status: deleted` and valid ordered request/completion
   timestamps confirms deletion. A network/server failure, 401, pending status or
   malformed receipt never clears the token or claims completion. Retry the same
   operation; reopening Settings resumes a securely saved pending request after a
   restart. An independently revoked credential needs the public operator route.
5. After a valid receipt, replace the secure value with a credential-free
   completion timestamp. If saving that completion fails, retain pending state and
   retry with the original token. The server's stable receipt makes this safe.

Retained server records and the limits on erasing backups, exports, downstream
copies and trained models are explained on the confirmation screen and in
[device-deletion.md](device-deletion.md). The app does not claim to recall them.

## Verification

Dart tests cover restart recovery, secure-write failures, token retention,
malformed/oversize receipts, 401/redirect/server refusal, timeouts, bounded requests,
URL configuration, and the native commit barrier's acknowledgement contract.
Widget tests exercise cancel/confirm, pending/retry/completion, accessible labels,
large text and the configured public request link.

Before release, test real Android Keystore and iOS Keychain persistence after
force-stop/restart and device reboot; run deletion against the configured service,
including an interrupted request and an independently revoked credential; verify
the public request route and VoiceOver/TalkBack navigation. Mocked plugin and HTTP
tests do not establish those device/deployment properties.
