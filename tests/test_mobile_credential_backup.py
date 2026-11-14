"""Enrollment ciphertext and wrapped keys must not migrate without the device Keystore."""

import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID = Path(__file__).parents[1] / "mobile/android/app/src/main"
NAMESPACE = "{http://schemas.android.com/apk/res/android}"


def rules(application: ET.Element, attribute: str) -> ET.Element:
    reference = application.attrib[NAMESPACE + attribute]
    assert reference.startswith("@xml/")
    return ET.parse(ANDROID / "res/xml" / f"{reference.removeprefix('@xml/')}.xml").getroot()


def excludes_preferences(section: ET.Element) -> bool:
    return any(
        item.attrib == {"domain": "sharedpref", "path": "."} for item in section.findall("exclude")
    )


def test_device_enrollment_is_excluded_from_cloud_backup_and_device_transfer() -> None:
    application = ET.parse(ANDROID / "AndroidManifest.xml").getroot().find("application")
    assert application is not None
    assert application.attrib[NAMESPACE + "allowBackup"] == "false"
    legacy = rules(application, "fullBackupContent")
    assert legacy.tag == "full-backup-content"
    assert excludes_preferences(legacy)
    modern = rules(application, "dataExtractionRules")
    assert modern.tag == "data-extraction-rules"
    for mode in ("cloud-backup", "device-transfer"):
        section = modern.find(mode)
        assert section is not None, f"Missing exclusions enable all data for {mode}"
        assert excludes_preferences(section), f"Credential preferences can escape through {mode}"
