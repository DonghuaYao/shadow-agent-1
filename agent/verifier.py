
from agent.adb_controller import run_adb


def get_foreground_app():
    """Get information about the current foreground app."""
    output = run_adb(
        "shell", "dumpsys", "activity", "activities"
    )

    for line in output.splitlines():
        if "topResumedActivity=" in line:
            return line.strip()

    return None


def verify_app_opened(package_name):
    """Check whether the expected app is in foreground."""
    foreground = get_foreground_app()

    if not foreground:
        print("VERIFY: Unable to determine foreground app")
        return False

    if package_name in foreground:
        print(f"VERIFY SUCCESS: {package_name} is foreground")
        return True

    print("VERIFY FAILED: Unexpected foreground app")
    print(foreground)
    return False


if __name__ == "__main__":
    verify_app_opened("com.android.chrome")
