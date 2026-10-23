"""环境恢复：点掉系统“无响应”弹窗，停掉测试用的 App，回到桌面。
每次自动测试前运行一次。用法: py recover.py"""
import sys
import time

from agent import device, eye, ui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def anr_windows():
    out = device.adb("dumpsys window windows", timeout=30)
    return [l.strip() for l in out.splitlines()
            if l.strip().startswith("Window #") and "Not Responding" in l]


def recover():
    for attempt in range(1, 7):
        found = anr_windows()
        if not found:
            break
        print(f"  [恢复] 系统里有 {len(found)} 个无响应弹窗，点 Wait（第 {attempt} 次）")
        try:
            xml = eye.dump()
            for display in (0, 2):
                elements = ui.parse(xml, display)
                wait = ui.find(elements, "Wait")
                if wait and any("responding" in e["label"] for e in elements):
                    device.adb(f"input -d {display} tap {wait['x']} {wait['y']}")
        except Exception as e:
            print("  [恢复] 读取界面失败:", e)
        time.sleep(10)
    for pkg in ("com.android.settings", "com.google.android.settings.intelligence",
                "com.google.android.contacts"):
        device.adb(f"am force-stop {pkg}")
    device.adb("input -d 0 keyevent KEYCODE_HOME")
    time.sleep(3)
    left = len(anr_windows())
    print(f"  [恢复] 完成：剩余无响应弹窗 {left} 个，主屏 {device.top_activity(0)}")
    return left == 0


if __name__ == "__main__":
    sys.exit(0 if recover() else 1)
