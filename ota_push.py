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

# OTA JSON file
JSON_FILE_PATH = os.path.join(OTA_REPO_PATH, "ota.json")

# Build.prop path
BUILD_PROP_PATH = os.path.join(
    BUILD_OUTPUT_DIR,
    "system/build.prop"
)

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
        raise FileNotFoundError("No ROM zip found!")

    zips.sort(
        key=lambda x: os.path.getmtime(
            os.path.join(BUILD_OUTPUT_DIR, x)
        )
    )

    latest = zips[-1]

    return os.path.join(BUILD_OUTPUT_DIR, latest)


def get_build_timestamp():
    with open(BUILD_PROP_PATH, "r") as f:
        for line in f:
            if line.startswith("ro.build.date.utc="):
                return int(line.strip().split("=")[1])

    raise RuntimeError(
        "Failed to find ro.build.date.utc in build.prop"
    )


def get_file_info(path):

    sha256 = subprocess.check_output(
        ["sha256sum", path]
    ).decode().split()[0]

    size = os.path.getsize(path)

    timestamp = get_build_timestamp()

    return sha256, size, timestamp


def update_json(
    rom_zip_path,
    sha256,
    size,
    timestamp,
    download_url,
):

    filename = os.path.basename(rom_zip_path)

    version = filename.split("-")[1]

    old_data = {
        "response": [
            {
                "datetime": timestamp,
                "filename": filename,
                "id": sha256,
                "romtype": "UNOFFICIAL",
                "size": size,
                "url": download_url,
                "version": version,
                "changelog": (
                    f"https://raw.githubusercontent.com/"
                    f"{REPO_OWNER}/{OTA_REPO_NAME}/main/changelog.md"
                ),
            }
        ]
    }

    new_data = [
        {
            "datetime": timestamp,
            "files": [
                {
                    "filename": filename,
                    "sha256": sha256,
                    "size": size,
                    "url": download_url,
                }
            ],
            "type": "UNOFFICIAL",
            "version": version,
        }
    ]

    with open("ota.json", "w") as f:
        json.dump(old_data, f, indent=2)

    with open("ota-v2.json", "w") as f:
        json.dump(new_data, f, indent=2)

    print("✅ Updated ota.json")
    print("✅ Updated ota-v2.json")

def upload_and_push():

    rom_zip_path = find_latest_zip()

    filename = os.path.basename(rom_zip_path)

    tag = filename.replace(".zip", "")

    print(f"📦 Latest ROM: {filename}")

    # =====================================================
    # Upload GitHub Release
    # =====================================================

    print("🚀 Uploading to GitHub Releases...")

    upload_cmd = [
        "gh",
        "release",
        "create",
        tag,
        rom_zip_path,
        "--repo",
        f"{REPO_OWNER}/{OTA_REPO_NAME}",
        "--title",
        tag,
        "--notes",
        f"Automatic OTA release for {DEVICE_CODENAME}",
    ]

    subprocess.run(upload_cmd, check=True)

    # =====================================================
    # Generate OTA Download URL
    # =====================================================

    download_url = (
        f"https://github.com/"
        f"{REPO_OWNER}/{OTA_REPO_NAME}/"
        f"releases/download/{tag}/{filename}"
    )

    # =====================================================
    # Generate OTA JSON
    # =====================================================

    sha256, size, timestamp = get_file_info(
        rom_zip_path
    )

    update_json(
        rom_zip_path,
        sha256,
        size,
        timestamp,
        download_url,
    )

    # =====================================================
    # Push OTA JSON
    # =====================================================

    print("📤 Pushing OTA JSON update...")

    os.chdir(OTA_REPO_PATH)
    
    subprocess.run(
    ["git", "checkout", "main"],
    check=True,
   )


    subprocess.run(
        ["git", "add", "ota.json", "ota-v2.json"],
        check=True,
    )

    commit_message = f"OTA update: {tag}"

    commit_result = subprocess.run(
        ["git", "commit", "-m", commit_message]
    )

    if commit_result.returncode != 0:
        print("ℹ️ Nothing new to commit.")

    subprocess.run(
        ["git", "push"],
        check=True,
    )

    print("✅ OTA update complete!")


if __name__ == "__main__":
    upload_and_push()
