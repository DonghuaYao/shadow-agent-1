
import subprocess
import time

from agent.adb_controller import ADB, capture_ui
from agent.observer import observe_ui
from agent.planner import plan_next_action
from agent.verifier import verify_app_opened


TASK = {
    "name": "Open Internet settings",
    "package": "com.android.settings",
    "start_action": "android.settings.SETTINGS",
    "steps": [
        {
            "target": [
                "Network & internet",
                "Network and internet",
            ],
            "page_title": "Network & internet",
            "required_elements": [
                "Airplane mode",
                "Hotspot & tethering",
                "Private DNS",
            ],
            "min_matches": 2,
        },
        {
            "target": ["Internet"],
            "page_title": "Internet",
            "required_elements": [
                "Add network",
                "Network preferences",
                "Saved networks",
            ],
            "min_matches": 2,
        },
    ],
}


def adb_command(*args):
    result = subprocess.run(
        [str(ADB), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


def observe():
    capture_ui()
    return observe_ui()


def verify_step(elements, step):
    expected_title = step["page_title"].strip().lower()

    # Page titles in Android Settings are exposed
    # through content-description, not text.
    title_found = any(
        element.get("description", "").strip().lower()
        == expected_title
        and not element.get("clickable", False)
        for element in elements
    )

    visible_texts = {
        element.get("text", "").strip().lower()
        for element in elements
        if element.get("text")
    }

    expected_elements = {
        item.strip().lower()
        for item in step["required_elements"]
    }

    matched = sorted(visible_texts & expected_elements)

    enough_matches = (
        len(matched) >= step.get("min_matches", 1)
    )

    success = title_found and enough_matches

    return success, matched, title_found


def execute_tap(center):
    x = center["x"]
    y = center["y"]

    print(f"ACTION: tap ({x}, {y})")

    adb_command(
        "shell",
        "input",
        "tap",
        str(x),
        str(y),
    )

    time.sleep(2)


def run_task(task, max_attempts=3):
    print("=" * 50)
    print(f"TASK: {task['name']}")
    print("=" * 50)

    print("\nStarting application...")

    # For this emulator test, reset Settings to its
    # main screen to ensure a reproducible start.
    # This is foreground automation, not background mode.
    adb_command(
        "shell",
        "am",
        "start",
        "-S",
        "-a",
        task["start_action"],
    )

    time.sleep(2)

    if not verify_app_opened(task["package"]):
        print("TASK FAILED: Settings did not open")
        return False

    for step_index, step in enumerate(task["steps"], start=1):
        print(f"\n--- STEP {step_index} ---")
        print(f"TARGET: {step['target']}")
        print(f"EXPECTED PAGE: {step['page_title']}")

        completed = False

        for attempt in range(1, max_attempts + 1):
            print(f"\nAttempt {attempt}/{max_attempts}")

            # OBSERVE
            elements = observe()

            # VERIFY current page before acting
            success, matched, title_found = verify_step(
                elements, step
            )

            if success:
                print(
                    f"VERIFY: already on target page "
                    f"({step['page_title']})"
                )
                completed = True
                break

            # PLAN
            decision = plan_next_action(
                elements,
                step["target"],
            )

            print(f"PLAN: {decision}")

            if decision["action"] != "tap":
                print("Target not found. Stopping safely.")
                break

            # ACT
            execute_tap(decision["center"])

            # VERIFY after action
            updated_elements = observe()

            success, matched, title_found = verify_step(
                updated_elements, step
            )

            print(f"PAGE TITLE MATCH: {title_found}")
            print(f"MATCHED ELEMENTS: {matched}")

            if success:
                print(
                    f"VERIFY SUCCESS: "
                    f"{step['page_title']}"
                )
                completed = True
                break

            print("VERIFY FAILED: retrying observation")

        if not completed:
            print(f"\nTASK FAILED at step {step_index}")
            return False

    print("\n" + "=" * 50)
    print("TASK COMPLETED SUCCESSFULLY")
    print("=" * 50)

    return True


if __name__ == "__main__":
    try:
        result = run_task(TASK)
        print(f"\nFinal result: {result}")

    except subprocess.CalledProcessError as error:
        print(f"\nADB COMMAND FAILED: {error}")

    except subprocess.TimeoutExpired as error:
        print(f"\nADB TIMEOUT: {error}")

    except Exception as error:
        print(f"\nUNEXPECTED ERROR: {error}")
