
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_bounds(bounds):
    numbers = list(map(int, re.findall(r"\d+", bounds)))
    if len(numbers) != 4:
        return None

    x1, y1, x2, y2 = numbers

    return {
        "x": (x1 + x2) // 2,
        "y": (y1 + y2) // 2,
    }


def observe_ui(xml_path="window.xml"):
    path = Path(xml_path)

    if not path.exists():
        raise FileNotFoundError(
            f"UI file not found: {path}"
        )

    root = ET.parse(path).getroot()
    elements = []

    def walk(node, clickable_parent=None):
        clickable = node.get("clickable", "false") == "true"
        center = parse_bounds(node.get("bounds", ""))

        # The nearest clickable ancestor
        if clickable and center:
            clickable_parent = center

        if node.tag == "node":
            text = node.get("text", "")
            description = node.get("content-desc", "")

            if text or description or clickable:
                elements.append({
                    "text": text,
                    "description": description,
                    "clickable": clickable,
                    "center": center,
                    "tap_center": clickable_parent,
                })

        for child in node:
            walk(child, clickable_parent)

    walk(root)
    return elements


if __name__ == "__main__":
    elements = observe_ui()

    print(f"Found {len(elements)} UI elements:\n")

    for element in elements:
        print(element)
