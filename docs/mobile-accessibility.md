# Mobile accessibility checks

This is the manual procedure and evidence record for [#63](https://github.com/gardner/weedz/issues/63),
not a claim that the app has passed a device audit. No real-device results are recorded here.
Widget tests, browser captures and simulator builds do not establish native screen-reader,
permission-dialog, secure-storage or background-execution behavior.

## Scope and readiness

Use the exact candidate build on physical Android and iOS devices. Record its commit and
artifact hash; do not substitute a fixture screen or browser demo for an unreachable flow.
The current main route opens Settings but does not connect native scanning, report approval
or uploading. Mark those journeys **blocked**, with their integration issue, until reachable.
[#125](https://github.com/gardner/weedz/pull/125) changes approval to **Report sighting**;
apply that scenario only to a build containing the change. Scan integration and device
validation remain [#128](https://github.com/gardner/weedz/issues/128) and
[#51](https://github.com/gardner/weedz/issues/51).

Use an isolated test enrollment/service and photos the tester can share. Record only
non-sensitive descriptions in evidence: redact tokens, exact private locations, personal
photos and Keychain/Keystore values. The App Store distribution signing-check IPA is not
a directly installable device test build. Obtain an appropriate authorized installable
build; a successful signing check alone does not satisfy this checklist.

## Device and settings matrix

Create a separate evidence record for each device/build combination. Do not infer an iOS
pass from Android, or an OS screen-reader pass from a web screen reader.

| Dimension | Android run | iOS run |
|---|---|---|
| Hardware | Physical handset, model and usable viewport recorded | Physical iPhone, model and usable viewport recorded |
| OS coverage | Record actual OS version; test oldest supported and current supported versions when available | Same; list unsupported/unavailable combinations explicitly |
| Speech navigation | TalkBack enabled; record version, language and verbosity | VoiceOver enabled; record language and verbosity |
| Alternative input | Switch Access or supported keyboard navigation; record actual input method | Switch Control or supported keyboard navigation; record actual input method |
| Display | Default, largest font, largest display size, bold text, light/dark, available contrast/outline mode | Default, largest accessibility text size, display zoom where supported, Bold Text, Increase Contrast, light/dark |
| Motion | Default and reduced/removed animations | Default and Reduce Motion |
| Interruption | Offline/online, background/resume, force-stop/reopen | Offline/online, background/resume, force-close/reopen |

Run extreme text and display settings together as well as individually. Record the actual
OS setting, not an assumed linear Flutter multiplier. The existing 2.0 widget test is not
proof of the largest native Dynamic Type or Android display-scaling combination.
Android setting names vary by device/OS; Android 16 uses outline text where earlier
versions offer high-contrast text. See [Android display settings](https://support.google.com/accessibility/answer/11183305?hl=en).
Enable the platform features through [Android accessibility settings](https://support.google.com/accessibility/android/answer/16323943?hl=en)
or [Apple accessibility features](https://www.apple.com/accessibility/features/);
[Apple's VoiceOver practice guide](https://support.apple.com/en-ie/guide/iphone/iph3e2e415f/ios)
explains its navigation gestures.

## Shared manual checks

Repeat these checks in every reachable journey below, including error and confirmation states.

1. Navigate forward and backward using speech navigation, then explore by touch. Check
   meaningful reading order, one useful name per control, its role/value/expanded state,
   headings, and no duplicate reading of decorative icons or the location diagram.
2. Activate each action without relying on its visual position. Expanded details must be
   discoverable and announce their state. Collapsed content must not trap focus.
3. Open and cancel each dialog: focus enters it, its purpose and consequences are read,
   focus stays in the dialog while open, and cancel restores focus to a useful control.
   After confirmation, focus lands on the resulting status/action rather than a removed button.
4. Listen through pending, success and error transitions. Status changes are discoverable
   without scanning the whole screen; progress does not repeatedly interrupt speech or steal
   focus. Reduced motion still communicates progress and outcome.
5. At the largest combined display/text settings, reach every control by scrolling. Check
   no clipped text, hidden confirmation action, overlapping labels, inaccessible field error
   or keyboard obstruction. Repeat with the keyboard open and after rotation where supported.
6. Check controls using the alternative input method. Focus is visible, ordered and escapable;
   no required action depends on a drag, tiny target or gesture with no alternative.
7. Check text and controls in light/dark and the available contrast/bold settings. Meaning
   survives grayscale and reduced motion. Small labels and disabled explanations stay readable.
   Use platform inspection/scanning tools for measurements; record actual findings rather
   than treating visual judgment as a numerical contrast result. The app's design baseline
   is 48 logical-pixel targets; automated and platform checks complement physical use.

[Flutter's release checklist](https://docs.flutter.dev/ui/accessibility) calls for screen-reader
and large-scale usability checks. Its [testing guide](https://docs.flutter.dev/ui/accessibility/accessibility-testing)
describes Android Accessibility Scanner and Xcode Accessibility Inspector; their reports
are supporting evidence, not replacements for the speech and interaction walkthrough.

## Journey matrix

| ID | Exercise on the candidate build | Expected evidence | Current reachability |
|---|---|---|---|
| A1 | Open Settings, enrollment fields, keyboard, validation, Connection details and Help | Clear labels/errors; saved enrollment is not called authenticated/connected; token is not exposed in recordings or spoken summaries | Settings reachable; native service/storage validation not yet recorded |
| A2 | Read suggested species, raw score, capture time and exact recorded location/accuracy before reporting | Suggestion stays unchecked; score is not a probability; exact point/accuracy is understandable without the diagram; About this score expands accessibly | Native approval route blocked by integration |
| A3 | In a #125 build, report without a photo; remove location, leave/reopen draft, then report | No licence answers required; visible location opt-out survives; one Report sighting action submits the reviewed choices; no report leaves before that action | Native approval/upload route blocked |
| A4 | Opt into photo; choose licence; remove photo; exercise an unreadable crop | Licence controls appear only on opt-in; preview is understandable; unreadable crop cannot attach; no-photo reporting remains possible | Native approval route blocked |
| A5 | Report, fail immediately offline, retry, reopen after lost response, then withdraw/cancel withdrawal | Status announced; settled failure restores retry and withdrawal; retries keep the same id/content; dialog focus and resulting status are usable | Native upload route blocked |
| A6 | Decline; revise refused report; reopen frozen/received/withdrawn report | Consequences are read; frozen content cannot be edited; revision is distinguished from retry; final states do not offer invalid actions | Native approval/upload route blocked |
| D1 | Open Delete my data, read expanded retention details, cancel, reopen and confirm | Shared sightings/access consequences and originals retained on phone are clear; full retention/backup limits read before confirmation; no deletion on cancel | Settings UI reachable; use only isolated service for execution |
| D2 | Interrupt deletion, reopen offline, retry online, receive 401/malformed response, finally confirm valid completion | Pending/error is announced and recoverable; credentials remain until confirmed completion; no premature success; restart state survives real native storage | Requires native test enrollment/service; not yet verified |
| D3 | Open configured public request page and return | Link purpose is announced; browser handoff/back works; missing configuration is explained without a misleading active link | Operational public route remains #107/#114 |
| S1 | Request library access; deny, limit selection, expand selection, revoke in system settings and resume | Native dialog and app explanation are navigable; app reports actual scope and remains usable after denial/revocation | Native scan screen/permission integration blocked (#128) |
| S2 | Start, pause, cancel and resume a scan; include cloud-only, unreadable and location-redacted photos | Counts/status distinguish examined, skipped and inaccessible assets; partial coverage is never called the whole library; no invented GPS/accuracy | Native scan/runtime integration blocked (#128/#51) |
| S3 | Background/lock, resume, interrupt process, change permissions mid-scan | Focus/status recover; stop/pause remains reachable; OS-limited work is explained; interrupted work is not reported complete | Native background/device validation blocked (#128) |

Do not fabricate a native permission dialog, background result or upload to fill a blocked
row. A widget harness may diagnose a screen independently; label it as such and keep the
end-to-end device row blocked. File actionable failures against the owning integration issue.

## Automated coverage already present

Paths below are relative to `mobile/`. Record the CI run for the exact candidate separately;
this table describes assertions in source, not a new execution or a device pass.

| Source | What it checks | What it does not prove |
|---|---|---|
| `test/ui/approval/approval_accessibility_test.dart` | Four Flutter guidelines across approval states; heading/location/status semantics; reduced-motion indicator; 2.0 text on 360×640 | Actual VoiceOver/TalkBack speech, focus routing, OS text scaling or a reachable native approval journey |
| `test/ui/approval/approval_flow_test.dart`, `approval_states_test.dart`, `approval_edges_test.dart`, `shown_is_sent_test.dart` | Sharing transitions, frozen retry content, confirmation guards and exact visible details | A native transport, persistent outbox, real library metadata or a manual reading-order audit |
| `test/ui/device_settings_test.dart`, `settings_clarity_test.dart` | Confirm/cancel, pending/retry/completion UI, semantics/large text, collapsed details and truthful saved-state wording | Device Keychain/Keystore durability, browser handoff, real deletion service or spoken focus changes |
| `test/device/deletion_test.dart`, `deletion_http_test.dart`, `secure_record_store_test.dart` | Controller/HTTP failure handling, credential retention and native-acknowledgement contract using fakes/mocks | Actual OS storage, network deployment, force-stop durability or screen-reader operation |
| `test/metadata/` | Missing/redacted/unknown-accuracy location and capture-time rules using supplied metadata | What the OS/plugin actually returns under each permission/library state |

The one-action report regressions are `test/ui/approval/one_action_test.dart`,
`preview_failure_test.dart`, `reopened_choices_test.dart`, `fast_retry_test.dart`,
`photo_credit_test.dart` and `compact_score_test.dart` in the same approval test directory.
They cover outgoing sharing choices and model details, unreadable previews, reopened
choices/attribution and coalesced retry settlement. Widget fixtures remain automated
screen evidence, not native-device validation.

## Evidence record

Copy this record for each device/build, and add a row for **every** applicable journey ID.
Use `pass`, `fail`, `blocked` or `not run`; explain every blocked/not-run result. A screenshot
alone does not establish spoken output or successful alternative-input operation.

```text
Date/time (UTC):
Tester and test/release owner:
Commit / app version / build mode / artifact SHA-256:
Install method / service environment (no credentials):
Physical device / OS / viewport / orientation:
Speech feature + version / speech language:
Alternative input device/method:
Font/display size / bold / contrast / theme / motion settings:
Journey ID / initial state / exact actions:
Observed spoken words, focus movement and visual result:
Result / blocked reason / owning issue:
Evidence location (redacted recording, screenshots, scanner report):
Regression issue and retest commit/result:
```

No tester or release owner has been assigned in this document. Before declaring a release
validated, record who ran each physical-device case and who accepts any remaining blockers.
Open decisions on #63 remain: the release-by-release manual test responsibility, supported
languages including te reo Māori, and automated coverage above 2.0 text scale. This checklist
includes the largest available native text settings for manual investigation; it does not
silently establish a new supported-language or maximum-scale policy. Keep #63 open until
actual evidence and those decisions are recorded.
