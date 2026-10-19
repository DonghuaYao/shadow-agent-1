
import time

from agent.adb_controller import capture_ui
from agent.action import tap_element
from agent.observer import observe_ui


print("Step 1: Observing current UI...")
capture_ui()

print("Step 2: Finding and tapping Chrome...")
tap_element("Chrome")

time.sleep(3)

print("Step 3: Observing UI after action...")
capture_ui()

elements = observe_ui()

print("\nCurrent visible UI elements:")
for element in elements:
    if element["text"] or element["description"]:
        print(element["text"], element["description"])
