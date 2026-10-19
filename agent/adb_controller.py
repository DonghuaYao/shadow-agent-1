
import subprocess
from pathlib import Path

ADB = (
    Path.home()
    / "AppData"
    / "Local"
    / "Android"
    / "Sdk"
    / "platform-tools"
    / "adb.exe"
)


def run_adb(*args):
    """Execute an ADB command."""
    result = subprocess.run(
        [str(ADB), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return result.stdout


def check_device():
    """Check connected Android devices."""
    output = run_adb("devices", "-l")
    print("Connected devices:")
    print(output)


def capture_ui():
    """Export the current Android UI hierarchy."""
    output = run_adb(
        "shell",
        "uiautomator",
        "dump",
        "/sdcard/window.xml",
    )
    print(output)

    run_adb(
        "pull",
        "/sdcard/window.xml",
        "window.xml",
    )

    print("UI hierarchy saved to window.xml")


if __name__ == "__main__":
    check_device()
    capture_ui()
