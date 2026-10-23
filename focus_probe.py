"""焦点探测：用户在主屏操作时，--display 读到的到底是哪块屏的内容？"""
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from agent import device, ui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CONTACTS = "com.google.android.contacts"


def dump_to(display=None, windows=False, path="/sdcard/probe.xml"):
    """读界面树，返回 (命令输出, xml 文字)"""
    device.adb(f"rm -f {path}")
    flags = ("--windows " if windows else "") + (f"--display {display} " if display is not None else "")
    msg = device.adb(f"uiautomator dump {flags}{path}")
    raw = subprocess.run(
        [device.ADB, "exec-out", "cat", path], capture_output=True, timeout=20
    ).stdout.decode("utf-8", errors="replace")
    return msg, raw


def summarize(raw):
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return "读取失败"
    packages, texts = set(), []
    for node in root.iter("node"):
        a = node.attrib
        packages.add(a.get("package", ""))
        t = " ".join((a.get("text") or a.get("content-desc") or "").split())[:30]
        if t and len(texts) < 3:
            texts.append(t)
    packages.discard("com.android.systemui")
    return f"包名={sorted(packages)} 前几个文字={texts}"


def focus_info():
    out = device.adb('dumpsys window | grep -E "mTopFocusedDisplayId|mCurrentFocus="')
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return " | ".join(lines) if lines else "（没有匹配到焦点信息）"


def probe(title):
    print(f"\n--- {title}")
    print("  系统焦点:", focus_info())
    for display in (2, 0):
        _, raw = dump_to(display)
        print(f"  dump --display {display} ->", summarize(raw))


# 准备：联系人开在副屏，Settings 搜索框开在主屏
device.stop_app(CONTACTS)
device.start_app(CONTACTS)
time.sleep(4)

device.adb("am force-stop com.android.settings")
device.adb("am start --display 0 -n com.android.settings/.Settings")
time.sleep(3)
_, raw = dump_to(0)
box = ui.find(ui.parse(raw), "Search settings")
if box is None:
    print("主屏准备失败：没找到搜索框")
    sys.exit(1)
device.adb(f"input -d 0 tap {box['x']} {box['y']}")
time.sleep(2)

probe("A 最后一次操作：用户在主屏点了搜索框")

device.adb("input -d 0 text x")
time.sleep(1)
probe("B 最后一次操作：用户在主屏打了一个字")

device.adb("input -d 2 tap 5 5")
time.sleep(1)
probe("C 最后一次操作：agent 在副屏点了一下（左上角空白处）")

device.adb("input -d 0 tap 5 5")
time.sleep(1)
probe("D 最后一次操作：用户在主屏点了一下（左上角空白处）")

device.adb("input -d 2 tap 5 5")
time.sleep(1)
probe("E 最后一次操作：agent 又在副屏点了一下")

print("\n--- F 试试 uiautomator dump --windows（不一定支持）")
msg, raw = dump_to(windows=True, path="/sdcard/probe_w.xml")
print("  命令输出:", msg[:200])
print("  内容 ->", summarize(raw))

# 收尾
device.adb("am force-stop com.android.settings")
device.adb("am force-stop com.google.android.settings.intelligence")
device.adb("input -d 0 keyevent KEYCODE_HOME")
print("\n探测结束")
