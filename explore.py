"""看一个 App 在副屏上长什么样：启动它，打印元素列表。
用法: py explore.py 包名
"""
import sys
import time

from agent import device, ui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

package = sys.argv[1]
before = device.top_activity(0)

device.start_app(package)
time.sleep(4)

print("副屏最前面:", device.top_activity(device.DISPLAY_ID))
print("主屏 启动前:", before)
print("主屏 启动后:", device.top_activity(0))

elements = ui.parse(device.dump_ui())
print("\n元素数量:", len(elements))
print(ui.describe(elements))
