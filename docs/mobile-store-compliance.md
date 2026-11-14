# Mobile app store compliance

Draft, 14 November 2026, for issue [#62](https://github.com/gardner/weedz/issues/62).
Nothing here is legal advice. Treat the privacy policy outline and the store
declarations as **drafts pending legal review**. Re-check each store rule
against the linked source before submitting, because both stores change their
policies several times a year.

This document covers what the Flutter app (Android and iOS, decided in
[#50](https://github.com/gardner/weedz/issues/50)) must declare to Apple and
Google, and why. The app's architecture will be described in `docs/mobile.md`,
and its code will live in `mobile/` **(pending #50; neither exists yet)**. This
file only covers what the stores and the NZ Privacy Act require of that design.

## What the app does, for the purposes of review

| Step | Where it happens | Leaves the phone? |
| --- | --- | --- |
| Read the whole photo library | Device | No |
| Read each photo's EXIF location and capture time | Device | No |
| Screen photos for watchlist weeds with the on-device model | Device | No |
| Prepare candidate reports and show them to the person | Device | No |
| The person approves one report, seeing its exact map point and accuracy | Device | Not yet |
| Upload the approved report: taxon, score, model ids, capture time, **exact coordinates and accuracy**, consent, optional credit name | Server ([#57](https://github.com/gardner/weedz/issues/57), PR [#85](https://github.com/gardner/weedz/pull/85)) | **Yes** |
| Optionally upload a cropped image, with its own consent and a licence (CC0, CC BY or CC BY-NC) | Server (#57) | **Yes, if the person opts in** |
| Download a signed model and watchlist bundle | Server to device ([#59](https://github.com/gardner/weedz/issues/59), in progress) | No personal data is sent; see below |

**Exact locations are the point of the app.** A weed record is useful to science
and to control work because it says exactly where the plant was seen
([#61](https://github.com/gardner/weedz/issues/61)). The declarations below say
this plainly. Do not soften "precise location" to "approximate" on any form to
make review easier. An inaccurate declaration is itself grounds for removal.

Facts that depend on unmerged work are marked **(pending #n)**:

- **#57 / PR #85**: the intake API and report schema version 1.
- **#61** (merged): exact locations are shared by default, and obscured points
  never leak. It did **not** add a separate location-consent field. A location is
  sent only when it is in a report the person approved, after seeing it on the
  approval screen. They can remove it with "Remove location" (`docs/mobile.md`,
  pending #50).
- **#59**: the model bundle format, and what (if anything) the device sends when
  it checks for updates.
- **[#60](https://github.com/gardner/weedz/issues/60)**: what the project may do
  with a contributed crop and with report data (specialist review, evidence,
  sharing with agencies, training), and how people are credited.

## Permissions, with justifications and draft purpose strings

### iOS

| Key / API | Requested? | Why | Draft purpose string |
| --- | --- | --- | --- |
| `NSPhotoLibraryUsageDescription` (PhotoKit read access, full or limited) | **Yes** | Core function. The app looks through your photos on the phone for weeds you may have photographed by accident. The location in each photo's metadata (`PHAsset.location`) comes with photo access. | "Weedz looks through your photos on this phone for invasive weeds you may have photographed without noticing. Photos are checked on the phone and are never uploaded unless you approve a report. An approved report includes the exact place the photo was taken." |
| `NSPhotoLibraryAddUsageDescription` | No | The app never saves to the library. | — |
| `NSLocationWhenInUseUsageDescription` / Core Location | **No** | Location comes from the photo's own metadata, not from the phone's current position. Not asking for it keeps the app off the location-permission prompt and limits what it can collect. Photos without a location are handled by [#54](https://github.com/gardner/weedz/issues/54). | — (if a future "use my current location" feature is added: "Weedz uses your current location only to place a report you are writing now, when the photo has no location of its own.") |
| `NSCameraUsageDescription` | No (not in v1) | The app scans existing photos. It does not take them. | — |
| `PHPhotoLibraryPreventAutomaticLimitedAccessAlert` = `YES` | Yes | When the person grants limited access, the app shows its own "add more photos" button (`presentLimitedLibraryPicker`) rather than the system re-prompting each launch. | — |
| `BGTaskSchedulerPermittedIdentifiers` + `UIBackgroundModes: processing` | Yes, if background scanning ships | Lets the OS run a scan while the phone is charging and idle (`BGProcessingTask`). The OS decides when, and the in-app scan is the baseline ([#53](https://github.com/gardner/weedz/issues/53)). | — |
| `ITSAppUsesNonExemptEncryption` = `NO` | Yes | Only HTTPS and signature checking of the bundle (#59). Both are exempt from export filing. | — |
| Push notifications | Not in v1 | — | — |

**Limited Photos access.** Apple expects apps to work with limited access
(Guideline 5.1.1(iii) and (iv): use the picker where possible, and do not force
consent). With limited access, Weedz scans only the photos the person selected
and says so on the scan screen ("Scanning 37 photos you chose. Add more…").
Refusing photo access entirely still leaves the app usable: the person can see
the watchlist and pick single photos through `PHPickerViewController`. That
picker needs no permission. Note that iOS 17 and later let the person turn off
location in the picker's options, so a picked photo may arrive without one.

### Android

The target is API 36 (Android 16). Google Play has required this for new apps and
updates since 31 August 2026.

| Permission | Requested? | Why | Runtime rationale text (draft) |
| --- | --- | --- | --- |
| `READ_MEDIA_IMAGES` (API 33+) | **Yes, default flavour** (subject to Play approval; see below) | Core function: passive discovery across the whole library. | "Weedz checks the photos on your phone for invasive weeds you may have photographed without noticing. Checking happens on your phone. Nothing is uploaded unless you approve a report." |
| `READ_MEDIA_VISUAL_USER_SELECTED` (API 34+) | Yes | Must be declared so "Allow limited access" works. With partial access, the app scans only the selected photos (the same behaviour as limited access on iOS). | — |
| `READ_EXTERNAL_STORAGE` with `maxSdkVersion="32"` | Yes | The equivalent permission on Android 12 and earlier. | Same as above |
| `ACCESS_MEDIA_LOCATION` | **Yes** | Without it, Android redacts GPS from photo EXIF (Android 10+), and a report could not say where the weed was. Reading the original bytes also needs `MediaStore.setRequireOriginal()`. | "Weedz reads the location saved in each photo so a report can say exactly where the weed was. Locations stay on your phone unless you approve a report." |
| `INTERNET` | Yes | Upload approved reports and download the model bundle. | — (normal permission) |
| `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO` | **No, explicitly removed** | Flutter media plugins may add these through manifest merge. Remove them with `tools:node="remove"` and check the merged manifest, because Play asks for a declaration for every media permission present. | — |
| `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` / `ACCESS_BACKGROUND_LOCATION` | **No** | As on iOS, location comes from photo metadata. Keeping these out also keeps the app out of Play's location-permissions policy. | — |
| `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_MEDIA_PROCESSING` | **Only if WorkManager proves too slow** | The default is WorkManager with `requiresCharging` and `requiresDeviceIdle` constraints, plus the in-app scan. `docs/mobile.md` (pending #50) keeps a `mediaProcessing` foreground service as the option for long scans. If it ships, Play needs a foreground-service-type declaration in the Console, with a video of the visible notification, and Android 15+ limits `mediaProcessing` to 6 hours in 24. | Notification: "Checking your photos for weeds on this phone. Nothing is uploaded." |
| `POST_NOTIFICATIONS` | Optional, later | Only to say "3 possible weeds are ready to review" after a background scan. Asked for when the person turns that on, not at first launch. | "Weedz can tell you when a background check finds a possible weed for you to review." |
| `CAMERA` | No (not in v1) | — | — |

## Prominent disclosure and consent (both stores)

Google Play's User Data policy requires an **in-app** disclosure, shown
immediately before the runtime permission prompt, and an affirmative action to
continue. Backing out or dismissing the screen is not consent. Apple asks for the
same thing through 5.1.1(ii) and 5.1.5. One onboarding flow serves both:

1. **Screen 1, "How Weedz works."** Your photos are checked on this phone. Nothing
   is uploaded automatically. You approve each report.
2. **Screen 2, "What a report shares"** (shown before any photo permission). If you
   approve a report, Weedz sends the suspected weed, the model that suggested it,
   when the photo was taken, and **the exact place the photo was taken, with its
   accuracy**. Exact places are what make a weed report useful. A photo crop is
   sent only if you tick "include photo" on that report and choose a licence.
   Buttons: **[Continue]** (then the OS prompt) and **[Not now]** (the app works
   with single photos you pick).
3. **Per-report approval** ([#56](https://github.com/gardner/weedz/issues/56)).
   The app shows a map pin and accuracy circle for the exact point. It has
   a "Remove location" control, which takes the location out of the report and
   sends it back for approval. It also has an "include photo crop" control
   (`consent.image`, with a licence) and an optional credit name. The consent wording version is recorded in the report (#57).

The same wording, in short form, goes in the purpose strings above, so the OS
prompt never says less than the screen before it.

## Full-library access on Google Play

### Justification (for the Play Console "Photo and video permissions" declaration)

> Weedz finds invasive weeds that people photographed by accident, for example in
> the background of holiday or garden photos. The person doesn't know which photos
> contain a weed, so they can't pick them. Finding them requires checking every
> photo in the library on the device. This passive discovery is the app's core and
> only main function. A screening model runs on the device; no photo leaves the
> phone unless the person reviews and approves a specific report. The Android Photo
> Picker can't serve this use, because it returns only items the person chooses,
> and the person can't choose photos they don't know are relevant. When partial
> access is granted, the app scans only the selected photos. If access is declined,
> the app offers the photo picker for single reports.

Attach a short screen recording to the declaration, showing onboarding, the
disclosure, the scan, and per-report approval.

**Risk: medium to high.** Google's examples of permitted use are mainly gallery,
photo-editing and backup apps. "Scan everything for one kind of object" is
plausible core use, but reviewers may read it as a feature that the picker could
serve. The August 2026 photo picker update weakens one of our arguments: the
picker can now return location metadata with the person's consent (see the
fallback below). Our remaining argument is that the person cannot know which
photos to pick. Plan for refusal.

### Fallback if Google refuses: a picker-only build

A `picker` product flavour drops `READ_MEDIA_IMAGES`, `READ_MEDIA_VISUAL_USER_SELECTED`
and `READ_EXTERNAL_STORAGE` from the manifest:

- **"Check a batch"**: the person opens the Android Photo Picker and selects many
  photos at once, for example a day's walk or an album. The app screens them on the
  device exactly as before.
- **Locations**: request location metadata through the photo picker's
  location-metadata opt-in. This is **not** in `androidx.activity`'s
  `PickVisualMediaRequest`. It is `setLocationMetadataAccessRequested` on the
  separate `androidx.photopicker:photopicker-activity` artefact (1.0.0-alpha03 at
  the time of writing), and its contract replaces the `androidx.activity` one. It
  needs a small Kotlin call behind a pigeon interface, because Flutter plugins don't
  expose it yet. The picker side is delivered through the August 2026 Google Play
  system update. The person sees an
  "Include location info?" prompt. On devices without that update, the picker
  removes GPS, and the report needs a location placed by hand (#54). This flavour
  also drops `ACCESS_MEDIA_LOCATION`. It can't recover GPS from picker results, and
  declaring it makes Android add `READ_MEDIA_VISUAL_USER_SELECTED`.
  Verify both the API and the policy before shipping.
- **What is lost**: passive discovery. The app becomes "check photos you suspect".
  Say this honestly in the Play listing.
- The same build is a useful **F-Droid / direct APK** baseline whatever Play decides.

The iOS build keeps full or limited library access. Apple has no equivalent
core-use gate, though 5.1.1(iii) still prefers the picker. The justification is
the purpose string and the limited-access behaviour above.

## Background work

- **Android**: WorkManager periodic work with charging and idle constraints, done in
  chunks that can resume. A `mediaProcessing` foreground service is used only if
  that proves too slow, with the extra declarations in the permission table. The OS may delay or skip runs
  (Doze, App Standby buckets). The scan screen shows progress and lets the person
  run the scan in the foreground on demand. See #53.
- **iOS**: `BGProcessingTaskRequest` with `requiresExternalPower = true`, resumable.
  iOS gives no guarantee of when (or whether) it runs. On iOS 26, a
  `BGContinuedProcessingTask` that the person starts can keep a visible scan going
  after they leave the app. Its identifier must also be listed in
  `BGTaskSchedulerPermittedIdentifiers`. The in-app scan is the baseline.
- **Neither platform uploads in the background without approval.** Approved reports
  may be queued and retried in the background. The `PUT /reports/{uuid}` call is
  idempotent (#57).

## Apple privacy nutrition label (draft)

Apple counts data as "collected" when it leaves the device and the developer can
read it for longer than it takes to serve a request in real time. On-device
screening of the library is **not** collected. Approved reports are.

| Apple data type | Collected? | Linked to the user? | Used for tracking? | Purposes | Notes |
| --- | --- | --- | --- | --- | --- |
| Location: **Precise Location** | **Yes** | **Yes**: linked to the device's submitter token | No | App Functionality | Exact coordinates and accuracy of the photo, in approved reports only. Do not tick "Coarse" instead. |
| User Content: **Photos or Videos** | Yes (optional) | Yes | No | App Functionality | A cropped image, only when the person ticks "include photo" for that report. |
| User Content: **Other User Content** | Yes | Yes | No | App Functionality | The report itself: suspected taxon, score, capture time, consent choices. |
| Contact Info: **Name** | Yes (optional) | Yes | No | App Functionality | The optional credit name. Remove this row if #60 drops credit names. |
| Identifiers: **User ID** | Yes | Yes | No | App Functionality | The submitter token (`weedzsub_…`). The server keeps only a hash, but it links reports to one submitter. |
| Identifiers: Device ID | No | — | — | — | No IDFA, IDFV or hardware IDs are sent. |
| Diagnostics, Usage Data, Contacts, Health, Financial, Browsing, Search | No | — | — | — | Re-check if a crash reporter or analytics is ever added. None are planned. |

**Why the submitter token is a User ID, not a Device ID.** The token is installed
on one device, but it is not a device identifier. It is not derived from the
hardware or the OS, and the device doesn't generate it. An operator issues it
to an enrolled participant from the CLI (#57). The operator knows who the
participant is, and can revoke the token or withdraw that participant's
reports. That makes it an assigned account-level ID. Apple's User ID covers
an "assigned user ID", and Play's User IDs covers identifiers that "relate to
an identifiable person, such as an account ID". Apple's Device ID and Play's
Device or other IDs are meant for advertising IDs, IDFV, IMEI, Android ID and
similar, none of which are sent. If enrolment ever becomes anonymous
self-service, so that no one can link the token to a person, review this
choice. Settle the category before submitting, rather than ticking both: the
stores require declarations to be accurate, and ticking both would wrongly
claim a device ID is collected.

**Consent choices are report content, not product interaction.** Each report
records the consent wording version, whether a location and a crop are
included, and the crop's licence (#57, #61). These are attributes of what the
person chose to publish, like a licence on a post. They go with Other User
Content (Play: Other user-generated content). They are not Apple's Product
Interaction or Play's "Other actions", which describe behaviour and usage
(taps, launches, gameplay). The app records no such behaviour. Revisit this if
the app ever uploads a log of what people tapped or declined.

Apple has no "scientific research" purpose. App Functionality is the closest fit,
as long as reports serve the app's stated purpose. If #60 lets the project use
crops to train models, that counts as "Other Purposes"
(`NSPrivacyCollectedDataTypePurposeOther`) on the Photos or Videos row and its
manifest entry. It is not "Product Personalization", which Apple limits to
customising what the person sees. Add it **(pending #60)**. "Linked to you" is correct even though no
name or email is collected, because every report carries a stable submitter
identity. Choosing "Not linked" would understate it.

**Tracking: No.** There is no ATT prompt and no `NSPrivacyTracking`.

## Apple privacy manifest (`ios/Runner/PrivacyInfo.xcprivacy`, draft)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>NSPrivacyTracking</key>
  <false/>
  <key>NSPrivacyTrackingDomains</key>
  <array/>
  <key>NSPrivacyCollectedDataTypes</key>
  <array>
    <dict>
      <key>NSPrivacyCollectedDataType</key>
      <string>NSPrivacyCollectedDataTypePreciseLocation</string>
      <key>NSPrivacyCollectedDataTypeLinked</key>
      <true/>
      <key>NSPrivacyCollectedDataTypeTracking</key>
      <false/>
      <key>NSPrivacyCollectedDataTypePurposes</key>
      <array><string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string></array>
    </dict>
    <dict>
      <key>NSPrivacyCollectedDataType</key>
      <string>NSPrivacyCollectedDataTypePhotosorVideos</string>
      <key>NSPrivacyCollectedDataTypeLinked</key>
      <true/>
      <key>NSPrivacyCollectedDataTypeTracking</key>
      <false/>
      <key>NSPrivacyCollectedDataTypePurposes</key>
      <array><string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string></array>
    </dict>
    <dict>
      <key>NSPrivacyCollectedDataType</key>
      <string>NSPrivacyCollectedDataTypeOtherUserContent</string>
      <key>NSPrivacyCollectedDataTypeLinked</key>
      <true/>
      <key>NSPrivacyCollectedDataTypeTracking</key>
      <false/>
      <key>NSPrivacyCollectedDataTypePurposes</key>
      <array><string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string></array>
    </dict>
    <dict>
      <key>NSPrivacyCollectedDataType</key>
      <string>NSPrivacyCollectedDataTypeName</string>
      <key>NSPrivacyCollectedDataTypeLinked</key>
      <true/>
      <key>NSPrivacyCollectedDataTypeTracking</key>
      <false/>
      <key>NSPrivacyCollectedDataTypePurposes</key>
      <array><string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string></array>
    </dict>
    <dict>
      <key>NSPrivacyCollectedDataType</key>
      <string>NSPrivacyCollectedDataTypeUserID</string>
      <key>NSPrivacyCollectedDataTypeLinked</key>
      <true/>
      <key>NSPrivacyCollectedDataTypeTracking</key>
      <false/>
      <key>NSPrivacyCollectedDataTypePurposes</key>
      <array><string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string></array>
    </dict>
  </array>
  <key>NSPrivacyAccessedAPITypes</key>
  <array>
    <dict>
      <!-- Settings and scan progress kept by the app itself (e.g. shared_preferences). -->
      <key>NSPrivacyAccessedAPIType</key>
      <string>NSPrivacyAccessedAPICategoryUserDefaults</string>
      <key>NSPrivacyAccessedAPITypeReasons</key>
      <array><string>CA92.1</string></array>
    </dict>
    <dict>
      <!-- Timestamps of files in the app's own container (model bundle cache). -->
      <key>NSPrivacyAccessedAPIType</key>
      <string>NSPrivacyAccessedAPICategoryFileTimestamp</string>
      <key>NSPrivacyAccessedAPITypeReasons</key>
      <array><string>C617.1</string></array>
    </dict>
    <dict>
      <!-- Check free space before downloading the model bundle (#59). -->
      <key>NSPrivacyAccessedAPIType</key>
      <string>NSPrivacyAccessedAPICategoryDiskSpace</string>
      <key>NSPrivacyAccessedAPITypeReasons</key>
      <array><string>E174.1</string></array>
    </dict>
  </array>
</dict>
</plist>
```

Notes:

- The manifest must match the label above. Keep both in step with the report
  schema: adding a field to the schema means checking both.
- **Required-reason APIs**: list only the categories our own Dart and Swift code
  actually reaches. The three above are the likely ones. Remove any that the
  Xcode privacy report doesn't show. The reason codes are from Apple's current
  list (UserDefaults `CA92.1`, file timestamp `C617.1`, disk space `E174.1`).
  Check them against
  [Describing use of required reason API](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api)
  at submission.
- **Flutter and plugins**: `Flutter.framework` ships its own privacy manifest, as
  do current versions of the first-party plugins (for example
  `shared_preferences`). Each third-party plugin (photo library, background tasks,
  inference runtime) must ship its own `PrivacyInfo.xcprivacy` in its own bundle.
  Declaring a plugin's required-reason calls in the Runner manifest is **not** a
  valid substitute, because Apple says an SDK can't rely on the app's manifest. If
  a plugin lacks a manifest, upgrade it, patch it (a fork or a CocoaPods/SwiftPM
  resource), or replace it. Apple rejects apps that use
  listed "commonly used SDKs" without a manifest and signature. Before each
  submission, run **Product → Archive → Generate Privacy Report** in Xcode, and
  read the merged report rather than trusting this list.

## Google Play Data safety answers (draft)

Google counts data as **collected** when it is sent off the device. Processing
that happens only on the device, such as screening the library, reading EXIF and
preparing reports, is not collected and is not declared as such.

**Top-level questions**

| Question | Answer |
| --- | --- |
| Does your app collect or share any of the required user data types? | **Yes** |
| Is all of the user data collected by your app encrypted in transit? | **Yes** (HTTPS only; cleartext disabled with `usesCleartextTraffic="false"`) |
| Do you provide a way for users to request that their data is deleted? | **Yes**: withdraw any report in the app (`DELETE /reports/{uuid}`, #57). Account and data deletion is covered below. |
| Independent security review (MASA) | No (optional) |

**Data types**

| Play data type | Collected | Shared | Optional? | Processed ephemerally? | Purposes | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Location: **Precise location** | **Yes** | **See note** | Yes: per report, the person chooses | No | App functionality | Exact EXIF coordinates and accuracy of the photo. |
| Photos and videos: **Photos** | Yes | See note | Yes | No | App functionality | Cropped image only, with consent and a licence. |
| Personal info: **Name** | Yes | See note | Yes | No | App functionality | Optional credit name. |
| Personal info: **User IDs** | Yes | No | Yes: sent only with an approved report | No | App functionality, Account management, Fraud prevention, security and compliance | Submitter token: authentication (Account management covers verifying credentials), revocation, per-submitter abuse limits. See the Apple section for why this is not a device ID. |
| App activity: **Other user-generated content** | Yes | See note | Yes: sent only when a report is approved | No | App functionality | The report: taxon, score, capture time, model ids, consent. |
| App info and performance | No | — | — | — | — | No crash or analytics SDK. Re-check if one is added. |
| Device or other IDs | No | — | — | — | — | — |

Every collected row is **optional** in Play's sense. A person can scan, browse
candidates and use the app indefinitely without approving a report. Nothing
leaves the device until they approve one.

**"Shared"** means transferred to a third party. On Play, a transfer the user
initiates and expects, or one to a service provider acting for us (hosting), is
not "sharing". Passing reports to weed agencies or publishing them as open
occurrence data **is sharing** under both stores' definitions. Whether and how that
happens is decided in **#60** and #58. Until then, answer "No" to sharing and do
not share. Update both forms **before** any sharing starts.

**Model bundle download (pending #59).** If the update check sends only an app
version and region and the server doesn't log it per device, nothing is
collected. If it sends the submitter token or the server logs IPs against
devices, consider declaring "App info and performance" or "Device or other IDs".
Settle this when #59 is designed.

## Account and data deletion

- **Apple 5.1.1(v)**: an app that lets people create an account must let them
  delete it from inside the app. **Google Play** has the same rule, plus a
  **web link** where deletion can be requested without the app.
- Today (#57) an operator issues device tokens from the CLI, so the app has no
  self-service sign-up. A token issued that way arguably isn't "account creation in
  the app". If the app ever **enrols itself** (requests its own token), both rules
  apply in full.
- **Recommended either way**, because it costs little and removes the question:
  a **"Delete my data"** action in settings that withdraws every report sent from
  this device and then asks the server to revoke the token. A web form (or a
  documented email address) does the same for a lost phone, through the operator's
  `intake withdraw`. **Gap**: #57 has per-report withdrawal but no "withdraw all and
  revoke myself" endpoint. Track this as follow-up work on the intake API.
- The store listing and privacy policy describe what remains after withdrawal: a
  tombstone of ids and received and withdrawn times, so a retry can't bring a
  report back (#57).

## GPL-3.0-or-later and the App Store: risk and options

**The tension.** The repository is GPL-3.0-or-later
([#32](https://github.com/gardner/weedz/issues/32)). GPL section 10 forbids
imposing "further restrictions" on recipients. Apple's App Store terms (the
Usage Rules in the Apple Media Services Terms) limit how a downloaded app may be
used and copied: on Apple-branded devices you own or control, under Apple's DRM.
In 2010 the FSF, enforcing its own copyright in GNU Go, found these terms
incompatible with the GPL
([FSF, 2010](https://www.fsf.org/news/2010-05-app-store-compliance)). Apple
removed the app rather than change its terms. In January 2011 Apple also removed
VLC after a VideoLAN copyright holder complained. VLC returned in 2013, after
VideoLAN relicensed libVLC under LGPL-2.1-or-later and dual-licensed the iOS app
(GPL-2.0 and MPL-2.0).
Apple's terms have not changed in substance. GPLv3 also adds "Installation
Information" duties for consumer devices (section 6), which iOS signing makes
awkward.

A copyright holder isn't bound by its own licence. So while the project owns all
the copyright in `mobile/`, it **can** publish to the App Store. Once outside
contributions arrive under inbound = outbound GPL (with a DCO sign-off, as `CONTRIBUTING.md` requires since #32 merged),
any one contributor can object, and forks can't publish to the App Store at all.

**Google Play** is generally considered compatible. Play's terms don't restrict
redistribution of the APK in the same way, and source can be offered alongside.
F-Droid is GPL-friendly and needs a fully free build: no proprietary SDKs, which
suits an app with no analytics.

**Options** (a decision for the project owner, best made **before** outside
contributions to `mobile/`):

1. **Add an App Store exception to the GPL (GPLv3 section 7 additional permission)**
   covering `mobile/`, for example: "As an additional permission, you may distribute
   this program through an app store whose terms impose restrictions that would
   otherwise conflict with this licence, provided the corresponding source remains
   available under this licence." This is cheap and keeps copyleft. It must be in
   place before contributions arrive, or be agreed by every contributor. Downstream
   recipients may remove it.
2. **License `mobile/` separately** under a permissive or weak-copyleft licence
   (MPL-2.0 or Apache-2.0) while the server stays GPL. The app talks to the server
   over HTTP, so it is a separate work. MPL-2.0 keeps file-level copyleft and is
   App Store-friendly. Check that no GPL Dart or Swift dependency is pulled in.
3. **Contributor licence agreement** assigning or licensing rights to the
   publisher, so it can distribute under extra terms. It works, but it puts off
   contributors and needs a legal entity to hold the rights.
4. **No App Store build**: Android only (Play, F-Droid, direct APK). It removes
   the risk but leaves out iPhone users, who are a large share of NZ phones.
5. **Do nothing and rely on sole ownership for now.** This works until the first
   outside contribution, then becomes options 1 to 4 under time pressure. Not
   recommended.

The lowest-friction path that keeps the project's open-source stance is probably
option 1 or 2, decided before the first outside contribution to `mobile/`. **Risk if ignored: high**
for iOS distribution once outside contributions arrive.

## Privacy policy outline (draft, pending legal review)

The policy must be at a public URL, linked in App Store Connect, the Play Console
and **inside the app** (settings, and the onboarding disclosure). Both stores
require this. The structure below follows the NZ Privacy Act 2020 information
privacy principles (IPPs). IPP 3A (notice when information is collected
indirectly) has applied since 1 May 2026. It also follows Apple 5.1.1(i) and
Play's User Data policy.

1. **Who we are** (IPP 3(1)(d)): the publisher's legal name and address, and the
   privacy officer's contact (s 201). **[Decision: publisher entity, contact.]**
2. **What the app does on your phone and never collects** (IPP 1, IPP 4): the whole
   library is read and screened on the device, and EXIF location and time are read
   on the device. None of this is sent. No analytics, advertising or tracking.
3. **What we collect, and only when you approve a report** (IPP 3(1)(a)): the
   suspected weed and score, model and app version, capture time, **the exact
   location and its accuracy** (shown on the approval screen, and left out if you
   remove it), the consent wording version and your choices, an optional credit name, an
   optional cropped photo (re-encoded on the server with all metadata removed,
   #57), and the device's submitter identity. No free text, contacts, account
   email or advertising IDs.
4. **Why** (IPP 1, IPP 3(1)(b)): to find and confirm invasive weeds, for
   specialist review, and for weed-control and scientific records. State plainly
   that exact locations are collected because a weed record is only useful with
   them. **(Uses beyond specialist review pending #60.)**
5. **Who sees it** (IPP 3(1)(c), IPP 11): project staff and invited specialist
   reviewers (#31, #58), and service providers acting for us (hosting). Any
   disclosure to regional councils, DOC, MPI or open biodiversity databases (GBIF,
   iNaturalist) and under what licence: **pending #60**. Crops are shared only
   under the licence you chose.
6. **Overseas** (IPP 12): where data is hosted, and the safeguards. **[Decision:
   hosting region.]**
7. **Voluntary, and what happens if you decline** (IPP 3(1)(f)): every report is optional, and so is every
   photo crop. Declining photo access still lets you check single photos.
8. **How long we keep it** (IPP 9): reports and crops for **[decision: retention
   period]**. Withdrawal deletes the crop and erases the report's content at once,
   leaving a tombstone of ids and times (#57). Abuse-limit records are deleted after
   24 hours (#57).
9. **Your rights** (IPP 6, IPP 7, IPP 3(1)(g)): access, correction, and withdrawal
   of any report in the app. Delete everything sent from this device (see account
   deletion). Request through the privacy officer. Complaints go to the Office of
   the Privacy Commissioner.
10. **Security** (IPP 5): HTTPS only, hashed device tokens, owner-only storage,
    metadata stripping, and reports stored apart from other data and never served
    publicly (#57). We notify the Commissioner and affected people of a serious
    privacy breach (Part 6).
11. **Children**: the app isn't directed at children. State the age rating chosen in
    both stores' questionnaires.
12. **Locations obscured by others** (#61): the app never reveals a location that a
    source or contributor has obscured.
13. **Third parties** (Apple 5.1.1(i)): list each SDK that handles user data. The
    target is none beyond the OS and Flutter. Say that any future processor will
    give the same protection.
14. **Changes**: how changes are announced, with a version and date.

## Pre-submission checklist

**Both stores**

- [ ] Publisher entity chosen; developer accounts opened in its name. Organisation
      accounts need a D-U-N-S number. Apple 5.1.1(ix) expects apps handling sensitive
      data to be submitted by a legal entity.
- [ ] Privacy policy published at a stable URL, reviewed by a lawyer, linked in the app
      and both consoles.
- [ ] Privacy officer and contact email in place. Retention period and hosting region
      decided and written into the policy.
- [ ] GPL and App Store option chosen and recorded in the repo before outside
      contributions to `mobile/`.
- [ ] #60 (rights) merged. The schema, label, Data safety
      form and policy all match.
- [ ] Onboarding disclosure screens implemented before any permission prompt, and the
      wording matches the purpose strings.
- [ ] Per-report approval shows the exact map point and accuracy, with a "Remove
      location" control and separate photo consent (#56).
- [ ] "Delete my data" in settings and a web or email deletion route, with the intake
      endpoint for bulk withdrawal and self-revocation added.
- [ ] Reviewer notes and a demo: how to get a test token, a sample photo library with a
      known weed, and a screen recording.
- [ ] Content rating questionnaires done in both consoles.
- [ ] Store listing text says photos are checked on the phone, reports are sent only
      when approved, and approved reports include exact locations.

**Apple**

- [ ] Built with Xcode 26 and the iOS 26 SDK (required for uploads since April 2026).
- [ ] `NSPhotoLibraryUsageDescription` final, with no Core Location keys present.
      `PHPhotoLibraryPreventAutomaticLimitedAccessAlert` set, and limited access tested.
- [ ] `PrivacyInfo.xcprivacy` matches the label. The Xcode privacy report has been read,
      and every plugin has a manifest.
- [ ] App Privacy answers in App Store Connect match the draft label.
- [ ] `ITSAppUsesNonExemptEncryption = NO`.
- [ ] App usable with photo access denied (pick single photos) and with limited access.
- [ ] Background tasks registered, and the app behaves when they never run.

**Google Play**

- [ ] `targetSdkVersion` 36.
- [ ] Merged manifest checked: no `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO`,
      `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` or `ACCESS_BACKGROUND_LOCATION`.
      Default flavour: `ACCESS_MEDIA_LOCATION` **stays**, because it is how the app reads
      a photo's GPS. Picker flavour: no `ACCESS_MEDIA_LOCATION`, `READ_MEDIA_IMAGES`,
      `READ_MEDIA_VISUAL_USER_SELECTED` or `READ_EXTERNAL_STORAGE`.
- [ ] Foreground service: either none is present, or `FOREGROUND_SERVICE_MEDIA_PROCESSING`
      is declared in the Play Console with a video.
- [ ] Photo and video permissions declaration submitted with the justification and
      video. The picker-only flavour is ready if it is refused.
- [ ] Default flavour: `ACCESS_MEDIA_LOCATION` and `setRequireOriginal()` tested on
      Android 10, 13, 14 and 16, and partial access (`READ_MEDIA_VISUAL_USER_SELECTED`)
      tested.
- [ ] Picker flavour: the photo picker's location opt-in and the manual-placement path
      (#54) tested.
- [ ] Data safety form matches the draft. Deletion URL provided.
- [ ] Closed test run, if the account is a new personal account (12 testers, 14 days).
- [ ] App registered for Android developer verification in the Play Console.

## Sources

- Apple: [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
  (5.1.1, 5.1.2, 5.1.5), [App privacy details](https://developer.apple.com/app-store/app-privacy-details/),
  [Privacy manifest files](https://developer.apple.com/documentation/bundleresources/privacy-manifest-files),
  [Required reason API](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api),
  [Delivering an enhanced privacy experience in your photos app](https://developer.apple.com/documentation/photokit/delivering-an-enhanced-privacy-experience-in-your-photos-app),
  [Upcoming requirements](https://developer.apple.com/news/upcoming-requirements/),
  [Offering account deletion](https://developer.apple.com/support/offering-account-deletion-in-your-app/).
- Google Play: [Photo and video permissions](https://support.google.com/googleplay/android-developer/answer/14115180),
  [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469),
  [User Data, prominent disclosure](https://support.google.com/googleplay/android-developer/answer/10144311),
  [Account deletion](https://support.google.com/googleplay/android-developer/answer/13327111),
  [Target API level](https://developer.android.com/google/play/requirements/target-sdk),
  [Photo picker](https://developer.android.com/training/data-storage/shared/photopicker),
  [Media location](https://developer.android.com/training/data-storage/shared/media#location-info-photos),
  [Photo picker location metadata (Android Authority, Aug 2026)](https://www.androidauthority.com/android-photo-picker-location-sharing-release-3704689/).
- NZ: [Privacy Act 2020](https://www.legislation.govt.nz/act/public/2020/0031/latest/),
  [Information privacy principles](https://www.privacy.org.nz/privacy-principles/),
  [IPP 3A guidance](https://www.privacy.org.nz/resources-and-learning/a-z-topics/ipp3a/),
  [Privacy Amendment Act 2025](https://www.legislation.govt.nz/act/public/2025/53/en/latest/).
- GPL: [FSF on the App Store and GNU Go (2010)](https://www.fsf.org/news/2010-05-app-store-compliance),
  [GPLv3 sections 6, 7 and 10](https://www.gnu.org/licenses/gpl-3.0.html),
  [GPL FAQ: additional permissions](https://www.gnu.org/licenses/gpl-faq.html#GPLIncompatibleLibs).
