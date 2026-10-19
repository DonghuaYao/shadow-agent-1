
import subprocess

from agent.adb_controller import ADB
from agent.observer import observe_ui


def tap_element(target_text, xml_path="window.xml"):
    """Find a clickable UI element and tap its center."""
    elements = observe_ui(xml_path)

    matches = [
        element
        for element in elements
        if element["clickable"]
        and element["center"]
        and (
            element["text"].lower() == target_text.lower()
            or element["description"].lower() == target_text.lower()
        )
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected one clickable '{target_text}', "
            f"found {len(matches)}"
        )

    center = matches[0]["center"]
    x, y = center["x"], center["y"]

    print(f"Found {target_text} at ({x}, {y})")

    subprocess.run(
        [str(ADB), "shell", "input", "tap", str(x), str(y)],
        check=True,
        timeout=15,
    )

    print(f"Tapped {target_text}")


if __name__ == "__main__":
    tap_element("Chrome")
