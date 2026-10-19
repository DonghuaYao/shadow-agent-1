
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_bounds(bounds):
    """Convert Android bounds into center coordinates."""
    numbers = list(map(int, re.findall(r"\d+", bounds)))

    if len(numbers) != 4:
        return None

    x1, y1, x2, y2 = numbers

    return {
        "x": (x1 + x2) // 2,
        "y": (y1 + y2) // 2,
    }


def observe_ui(xml_path="window.xml"):
    """Read Android UI elements from XML."""
    path = Path(xml_path)

    if not path.exists():
        raise FileNotFoundError(f"UI file not found: {path}")

    tree = ET.parse(path)
    root = tree.getroot()

    elements = []

    for node in root.iter("node"):
        text = node.get("text", "")
        description = node.get("content-desc", "")
        clickable = node.get("clickable", "false") == "true"
        bounds = node.get("bounds", "")

        if not (text or description or clickable):
            continue

        elements.append({
            "text": text,
            "description": description,
            "clickable": clickable,
            "center": parse_bounds(bounds),
        })

    return elements


if __name__ == "__main__":
    elements = observe_ui()

    print(f"Found {len(elements)} UI elements:\n")

    for element in elements:
        print(element)
