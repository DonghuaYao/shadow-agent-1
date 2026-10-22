"""临时验证脚本：用新代码走一遍副屏启动、读界面树、点击、返回。"""
import sys
import time

from agent import device, ui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SUB = device.DISPLAY_ID

print("副屏存在:", device.display_exists())

device.stop_app("com.android.settings")
print("在副屏启动 Settings ...")
device.start_app("com.android.settings")
time.sleep(3)
print("副屏最前面:", device.top_activity(SUB))
print("主屏最前面:", device.top_activity(0))

elements = ui.parse(device.dump_ui())
print("\n界面元素数量:", len(elements))
print(ui.describe(elements))

target = ui.find(elements, "Network")
if target is None:
    print("\n没找到 Network，停止")
    sys.exit(1)

print("\n点击:", target["label"], (target["x"], target["y"]))
device.tap(target["x"], target["y"])
time.sleep(2)
print("点击后副屏:", device.top_activity(SUB))
print("点击后主屏:", device.top_activity(0))

device.back()
time.sleep(1.5)
print("返回后副屏:", device.top_activity(SUB))
print("返回后主屏:", device.top_activity(0))
