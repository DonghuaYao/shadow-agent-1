
import subprocess
import time

from agent.adb_controller import ADB, capture_ui
from agent.observer import observe_ui
from agent.planner import plan_next_action
from agent.verifier import verify_app_opened


def is_network_settings_page(elements):
    """Check whether we reached Network & internet settings."""
    visible_set = {
        element["text"].strip().lower()
        for element in elements
        if element["text"]
    }

    expected_items = {
        "internet",
        "airplane mode",
        "hotspot & tethering",
        "private dns",
    }

    matched = expected_items & visible_set

    if len(matched) >= 3:
        print("VERIFY SUCCESS: Network settings page detected")
        print(f"Matched items: {sorted(matched)}")
        return True

    return False


def run_navigation():
    print("Goal: Navigate to Network & internet")

    # Open Android Settings
    subprocess.run(
        [
            str(ADB),
            "shell",
            "am",
            "start",
            "-a",
            "android.settings.SETTINGS",
        ],
        check=True,
    )

    time.sleep(2)

    if not verify_app_opened("com.android.settings"):
        print("Failed to open Settings")
        return False

    goals = ["Network & internet", "Network and internet"]

    for step in range(1, 5):
        print(f"\n--- Step {step} ---")

        # Observe
        capture_ui()
        elements = observe_ui()

        # Check if the goal is already completed
        if is_network_settings_page(elements):
            return True

        # Decide
        decision = plan_next_action(elements, goals)
        print(f"Decision: {decision}")

        if decision["action"] != "tap":
            print("Target not found. Stopping safely.")
            return False

        center = decision["center"]

        # Act
        subprocess.run(
            [
                str(ADB),
                "shell",
                "input",
                "tap",
                str(center["x"]),
                str(center["y"]),
            ],
            check=True,
        )

        time.sleep(2)

        # Verify after action
        capture_ui()
        updated_elements = observe_ui()

        visible_text = [
            element["text"]
            for element in updated_elements
            if element["text"]
        ]

        print("Visible UI:", visible_text[:20])

        if is_network_settings_page(updated_elements):
            return True

    print("Maximum steps reached.")
    return False


if __name__ == "__main__":
    success = run_navigation()
    print(f"\nNavigation completed: {success}")
