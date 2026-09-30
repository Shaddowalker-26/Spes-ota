import json
import os
import subprocess

# =========================================================
# CONFIGURATION
# =========================================================

REPO_OWNER = "Shaddowalker-26"
OTA_REPO_NAME = "spes-ota"
DEVICE_CODENAME = "spes"

# OTA repo path on server
OTA_REPO_PATH = "/home/ubuntu/android/lineage/spes-ota"

# Lineage build output path
BUILD_OUTPUT_DIR = "/home/ubuntu/android/lineage/out/target/product/spes"

# Build.prop path
BUILD_PROP_PATH = os.path.join(
    BUILD_OUTPUT_DIR,
    "system/build.prop"
)

# OTA v2 JSON
OTA_V2_PATH = os.path.join(
    OTA_REPO_PATH,
    "ota-v2.json"
)

# Keep one OTA per Lineage version
MAX_VERSIONS = 2

# =========================================================


def find_latest_zip():
    zips = [
        f for f in os.listdir(BUILD_OUTPUT_DIR)
        if (
            f.endswith(".zip")
            and "ota" not in f.lower()
            and "incremental" not in f.lower()
        )
    ]

    if not zips:
        raise FileNotFoundError(
            "No ROM zip found!"
        )

    zips.sort(
        key=lambda x: os.path.getmtime(
            os.path.join(
                BUILD_OUTPUT_DIR,
                x
            )
        )
    )

    return os.path.join(
        BUILD_OUTPUT_DIR,
        zips[-1]
    )


# =========================================================
# BUILD PROPERTIES
# =========================================================


def get_build_property(property_name):

    with open(BUILD_PROP_PATH, "r") as f:

        for line in f:

            if line.startswith(
                property_name + "="
            ):

                return line.strip().split(
                    "=",
                    1
                )[1]

    raise RuntimeError(
        f"Failed to find {property_name} "
        f"in build.prop"
    )


def get_build_timestamp():

    return int(
        get_build_property(
            "ro.build.date.utc"
        )
    )


def get_sdk_level():

    return int(
        get_build_property(
            "ro.build.version.sdk"
        )
    )


def get_lineage_version():

    return get_build_property(
        "ro.lineage.build.version"
    )


def get_release_type():

    try:

        return get_build_property(
            "ro.lineage.releasetype"
        )

    except RuntimeError:

        return "UNOFFICIAL"


# =========================================================
# FILE INFORMATION
# =========================================================


def get_file_info(path):

    sha256 = subprocess.check_output(
        ["sha256sum", path]
    ).decode().split()[0]

    size = os.path.getsize(path)

    timestamp = get_build_timestamp()

    return sha256, size, timestamp


# =========================================================
# OTA JSON
# =========================================================


def create_ota_entry(
    rom_zip_path,
    sha256,
    size,
    timestamp,
    download_url,
    sdk_level,
    version,
    release_type,
):

    filename = os.path.basename(
        rom_zip_path
    )

    return {
        "datetime": timestamp,

        "files": [
            {
                "filename": filename,
                "os_sdk_level": sdk_level,
                "sha256": sha256,
                "size": size,
                "url": download_url,
            }
        ],

        "type": release_type,

        "version": version,
    }


def update_ota_json(
    rom_zip_path,
    sha256,
    size,
    timestamp,
    download_url,
    sdk_level,
    version,
    release_type,
):

    # -----------------------------------------------------
    # Read existing OTA v2 JSON
    # -----------------------------------------------------

    if os.path.exists(OTA_V2_PATH):

        try:

            with open(
                OTA_V2_PATH,
                "r"
            ) as f:

                existing_data = json.load(f)

            if not isinstance(
                existing_data,
                list
            ):

                existing_data = []

        except (
            json.JSONDecodeError,
            OSError
        ):

            existing_data = []

    else:

        existing_data = []

    # -----------------------------------------------------
    # Remove previous OTA for this Lineage version
    # -----------------------------------------------------

    existing_data = [
        entry
        for entry in existing_data
        if entry.get("version") != version
    ]

    # -----------------------------------------------------
    # Create new OTA entry
    # -----------------------------------------------------

    new_entry = create_ota_entry(
        rom_zip_path,
        sha256,
        size,
        timestamp,
        download_url,
        sdk_level,
        version,
        release_type,
    )

    # Put newest build first
    existing_data.insert(
        0,
        new_entry
    )

    # -----------------------------------------------------
    # Keep latest OTA for each supported version
    # -----------------------------------------------------

    versions_seen = set()
    final_data = []

    for entry in existing_data:

        entry_version = entry.get(
            "version"
        )

        if entry_version in versions_seen:
            continue

        versions_seen.add(
            entry_version
        )

        final_data.append(
            entry
        )

        if len(final_data) >= MAX_VERSIONS:
            break

    # -----------------------------------------------------
    # Write ota-v2.json
    # -----------------------------------------------------

    with open(
        OTA_V2_PATH,
        "w"
    ) as f:

        json.dump(
            final_data,
            f,
            indent=2
        )

        f.write("\n")

    print(
        "✅ Updated ota-v2.json"
    )

    print(
        f"📱 Android SDK: {sdk_level}"
    )

    print(
        f"📦 Lineage version: {version}"
    )

    print(
        f"🔖 Release type: {release_type}"
    )


# =========================================================
# UPLOAD AND PUSH
# =========================================================


def upload_and_push():

    # -----------------------------------------------------
    # Find ROM
    # -----------------------------------------------------

    rom_zip_path = find_latest_zip()

    boot_img_path = os.path.join(
        BUILD_OUTPUT_DIR,
        "boot.img"
    )

    filename = os.path.basename(
        rom_zip_path
    )

    tag = filename.replace(
        ".zip",
        ""
    )

    print(
        f"📦 Latest ROM: {filename}"
    )

    # -----------------------------------------------------
    # Read build information
    # -----------------------------------------------------

    sdk_level = get_sdk_level()

    version = get_lineage_version()

    release_type = get_release_type()

    print(
        f"📱 Android SDK: {sdk_level}"
    )

    print(
        f"📦 Lineage version: {version}"
    )

    print(
        f"🔖 Release type: {release_type}"
    )

    # -----------------------------------------------------
    # Safety checks
    # -----------------------------------------------------

    if version == "23.2" and sdk_level != 36:

        raise RuntimeError(
            "LineageOS 23.2 must use "
            f"SDK 36, detected SDK {sdk_level}"
        )

    if version == "24.0" and sdk_level != 37:

        raise RuntimeError(
            "LineageOS 24.0 must use "
            f"SDK 37, detected SDK {sdk_level}"
        )

    # -----------------------------------------------------
    # Upload GitHub Release
    # -----------------------------------------------------

    print(
        "🚀 Uploading to GitHub Releases..."
    )

    upload_cmd = [
        "gh",
        "release",
        "create",
        tag,
        rom_zip_path,
        boot_img_path,
        "--repo",
        f"{REPO_OWNER}/{OTA_REPO_NAME}",
        "--title",
        tag,
        "--notes",
        (
            f"Automatic OTA release "
            f"for {DEVICE_CODENAME}"
        ),
    ]

    subprocess.run(
        upload_cmd,
        check=True
    )

    # -----------------------------------------------------
    # Generate download URL
    # -----------------------------------------------------

    download_url = (
        f"https://github.com/"
        f"{REPO_OWNER}/"
        f"{OTA_REPO_NAME}/"
        f"releases/download/"
        f"{tag}/"
        f"{filename}"
    )

    # -----------------------------------------------------
    # Get file information
    # -----------------------------------------------------

    sha256, size, timestamp = get_file_info(
        rom_zip_path
    )

    # -----------------------------------------------------
    # Update OTA v2 JSON
    # -----------------------------------------------------

    update_ota_json(
        rom_zip_path,
        sha256,
        size,
        timestamp,
        download_url,
        sdk_level,
        version,
        release_type,
    )

    # -----------------------------------------------------
    # Push OTA JSON
    # -----------------------------------------------------

    print(
        "📤 Pushing OTA JSON..."
    )

    os.chdir(
        OTA_REPO_PATH
    )

    subprocess.run(
        [
            "git",
            "checkout",
            "main"
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "add",
            "ota-v2.json"
        ],
        check=True,
    )

    commit_message = (
        f"OTA update: {tag}"
    )

    commit_result = subprocess.run(
        [
            "git",
            "commit",
            "-m",
            commit_message
        ]
    )

    if commit_result.returncode != 0:

        print(
            "ℹ️ Nothing new to commit."
        )

    subprocess.run(
        [
            "git",
            "push"
        ],
        check=True,
    )

    print(
        "✅ OTA update complete!"
    )


# =========================================================

if __name__ == "__main__":

    upload_and_push()
