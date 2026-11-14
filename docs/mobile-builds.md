# Mobile artifacts from GitHub Actions

The **Mobile Builds** workflow builds Android development APKs and iOS simulator
apps for mobile-related pull requests and pushes to `main`. It preserves the
separate **Mobile Quality** analysis/test workflow. Open a workflow run and use
its **Artifacts** section:

- `weedz-android-development`: installable debug APK (development signing only).
- `weedz-ios-simulator`: ZIP of `Runner.app` for an Apple Silicon iOS simulator;
  it cannot install on an iPhone. Unzip and use `xcrun simctl install booted Runner.app`.

PR builds receive no secrets, including internal PRs. Trusted-main development
builds may embed `WEEDZ_INTAKE_BASE_URL` and `WEEDZ_DELETION_REQUEST_URL` from
Actions secrets. Without configuration the app's deployment-dependent features
remain unavailable; these builds do not invent a server address or deletion URL.
Both settings become public app contents, even though supplied through secrets.
Never put a submitter token in either URL or in a build define.

## Signed artifacts

Configure the exact secrets in the checklist on
[#114](https://github.com/gardner/weedz/issues/114). They may be repository secrets
or secrets in the `mobile-release` environment. Configure that environment's
required reviewers and deployment branch restriction to `main` if the repository
needs an additional human release gate. The workflow itself requires manual
`workflow_dispatch` on `main`; no pull request can start the signed jobs.

In **Actions → Mobile Builds → Run workflow**, select `main` and turn on
`signed_release`. Both platforms validate their own required settings:

- Android: final `ANDROID_APPLICATION_ID`, `ANDROID_KEYSTORE_BASE64`,
  `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`.
- iOS: final `IOS_BUNDLE_IDENTIFIER`, `APPLE_TEAM_ID`,
  `IOS_DISTRIBUTION_P12_BASE64`, `IOS_DISTRIBUTION_P12_PASSWORD`,
  `IOS_PROVISIONING_PROFILE_BASE64`.
- Both: HTTPS `WEEDZ_INTAKE_BASE_URL` and `WEEDZ_DELETION_REQUEST_URL`, without
  embedded credentials. Identifiers must belong to the publisher; template
  `org.example.*` values are refused.

The Android release task requires upload signing and never uses the debug key as
fallback. Apple signing needs an unexpired App Store distribution profile with an
explicit matching bundle/team, and a matching distribution identity with its
private key. No Apple account password, Google login, App Store Connect API key,
or Play service-account key is needed for these artifact builds. An Apple API key
could be used separately to automate provisioning after authorized access exists.

Download `weedz-android-release` (APK and AAB) and `weedz-ios-release` (IPA) from
the successful run. Artifacts expire after 14 days. The workflow does **not**
upload to either store. Version/build numbers currently come from
`mobile/pubspec.yaml`; increment them before a later store submission.

## Signing cleanup and troubleshooting

Signing material is decoded under the runner's temporary directory with private
permissions. iOS uses a temporary keychain and an installed temporary provisioning
profile in the Xcode 16+ `Library/Developer/Xcode/UserData/Provisioning Profiles`
directory. The always-run cleanup restores the previous keychain search list,
deletes the profile/keychain and removes temporary files, even when one cleanup
operation fails. Only the app artifacts listed above are uploaded: signing files,
configuration JSON, keychain files and archives are excluded.

Validation errors name the missing/invalid setting without echoing its value.
Apple tool stderr is suppressed because it can reveal signing details; check the
named setting and profile/certificate match if preparation fails. Hosted runners
are disposable. If adapting this workflow for self-hosted runners, a failed
cleanup requires operator attention before reusing the runner.

Issue #114 remains open until the owner configures signing credentials and both
signed platform builds have been verified. Development CI success proves the
native projects build; it does not verify signing or make the app store-ready.
