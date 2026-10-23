"""诊断：用户在主屏打字时，uiautomator dump 为什么读不到？"""
import subprocess
import sys
import threading
import time

from agent import device, ui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

state = {"interval": None}  # None 表示不打字


def typer():
    i = 0
    while True:
        interval = state["interval"]
        if interval is None:
            time.sleep(0.2)
            continue
        device.adb(f"input -d 0 text {'xyz'[i % 3]}")
        i += 1
        time.sleep(interval)


def timed_dump(windows):
    flag = "--windows " if windows else ""
    device.adb("rm -f /sdcard/diag.xml")
    start = time.time()
    try:
        msg = device.adb(f"uiautomator dump {flag}/sdcard/diag.xml", timeout=25)
    except subprocess.TimeoutExpired:
        return "超时（超过 25 秒）"
    took = round(time.time() - start, 1)
    size = device.adb("[ -f /sdcard/diag.xml ] && wc -c < /sdcard/diag.xml || echo 文件不存在")
    return f"{took} 秒 | 命令输出: {msg[:130]} | 文件大小: {size}"


def run_phase(title, interval, windows_times, plain_times):
    print(f"\n===== {title} =====")
    state["interval"] = interval
    time.sleep(2)
    for i in range(windows_times):
        print(f"  --windows #{i + 1}:", timed_dump(True))
    for i in range(plain_times):
        print(f"  普通 dump #{i + 1}:", timed_dump(False))
    state["interval"] = None


threading.Thread(target=typer, daemon=True).start()

try:
    device.stop_app("com.google.android.contacts")
    device.start_app("com.google.android.contacts")
    time.sleep(4)

    device.adb("am start --display 0 -n com.android.settings/.Settings")
    time.sleep(3)
    box = ui.find(ui.parse(device.dump_ui(), 0), "Search settings")
    if box is None:
        print("主屏准备失败：没找到搜索框")
        sys.exit(1)
    device.adb(f"input -d 0 tap {box['x']} {box['y']}")
    time.sleep(2)

    run_phase("阶段 1：主屏没人打字（基线）", None, 3, 0)
    run_phase("阶段 2：主屏每 0.6 秒打一个字", 0.6, 5, 3)
    run_phase("阶段 3：主屏每 2 秒打一个字", 2.0, 5, 3)
finally:
    state["interval"] = None
    device.adb("am force-stop com.android.settings")
    device.adb("am force-stop com.google.android.settings.intelligence")
    device.adb("input -d 0 keyevent KEYCODE_HOME")
    print("\n诊断结束，主屏已恢复")
