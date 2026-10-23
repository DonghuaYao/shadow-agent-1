"""验证 Shadow Eye：用户在主屏高频操作时，还能不能稳定读到副屏界面？"""
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from agent import device, eye, ui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONTACTS = "com.google.android.contacts"
state = {"mode": None, "interval": 0.6}  # mode: None 不操作 / type 打字 / swipe 滑动
failures = [0]


def user_worker():
    """模拟主屏上的用户"""
    i = 0
    while True:
        mode = state["mode"]
        if mode == "type":
            device.adb(f"input -d 0 text {'xyz'[i % 3]}")
            time.sleep(state["interval"])
        elif mode == "swipe":
            if i % 2 == 0:
                device.adb("input -d 0 swipe 540 1700 540 700 200")
            else:
                device.adb("input -d 0 swipe 540 700 540 1700 200")
        else:
            time.sleep(0.2)
        i += 1


def read_both():
    """读一次，返回 (耗时, 副屏元素, 主屏元素, 原始xml)"""
    start = time.time()
    xml = eye.dump()
    took = round(time.time() - start, 2)
    return took, ui.parse(xml, 2), ui.parse(xml, 0), xml


def structure(xml):
    """每块屏幕上有哪些窗口、几个节点（排错用）"""
    lines = []
    for d in ET.fromstring(xml):
        for w in d:
            nodes = list(w.iter("node"))
            pkgs = sorted({n.attrib.get("package", "") for n in nodes})
            lines.append(f"    屏幕 {d.attrib.get('id')} | {w.attrib.get('type')} | {len(nodes)} 个节点 | {pkgs}")
    return "\n".join(lines) or "    （没有任何窗口）"


def wait_for(display, text, seconds=12):
    """反复读，直到指定屏幕上出现带这段文字的元素；超时就把原始数据存下来"""
    end = time.time() + seconds
    xml = ""
    while time.time() < end:
        try:
            _, sub, main, xml = read_both()
            found = ui.find(sub if display == 2 else main, text)
            if found:
                return found
        except Exception as e:
            print("  读取出错:", e)
        time.sleep(0.8)
    failures[0] += 1
    path = Path("runs") / f"eye_fail_{failures[0]}.xml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    print(f"  找不到 '{text}'（屏幕 {display}），原始数据已存到 {path}，窗口结构:")
    print(structure(xml) if xml else "    （一次都没读到）")
    return None


def prepare_main(open_search):
    """主屏打开 Settings；需要的话点进搜索框，让光标停在输入框里"""
    device.adb("am force-stop com.android.settings")
    device.adb("am force-stop com.google.android.settings.intelligence")
    device.adb("am start --display 0 -n com.android.settings/.Settings")
    box = wait_for(0, "Search settings")
    if box is None:
        raise RuntimeError("主屏没找到搜索框")
    if open_search:
        device.adb(f"input -d 0 tap {box['x']} {box['y']}")
        time.sleep(2)


def click_test():
    """用 Shadow Eye 读到的坐标去点，验证坐标系对不对"""
    print("===== 点击坐标验证（主屏闲置）=====")
    device.stop_app("com.android.settings")
    device.start_app("com.android.settings")
    target = wait_for(2, "Network")
    if target is None:
        return False
    print("点击", target["label"], (target["x"], target["y"]))
    device.tap(target["x"], target["y"])
    time.sleep(2)
    after = device.top_activity(2)
    print("点击后副屏:", after, "| 主屏:", device.top_activity(0))
    device.back()
    time.sleep(1)
    return bool(after) and "SubSettings" in after


def run_phase(title, mode, interval, times=4):
    print(f"\n===== {title} =====")
    state["mode"], state["interval"] = mode, interval
    time.sleep(2)
    good = 0
    for n in range(1, times + 1):
        try:
            took, sub, main, _ = read_both()
            pkgs = sorted({e["package"] for e in sub})
            texts = [e["label"] for e in main if e["label"]][:2]
            ok = bool(sub) and CONTACTS in pkgs
            good += ok
            print(f"  #{n} {took} 秒 | 副屏 {len(sub)} 个元素 包名={pkgs} | 主屏 {len(main)} 个元素 文字={texts}")
        except Exception as e:
            print(f"  #{n} 失败: {e}")
    state["mode"] = None
    print(f"  -> 副屏读到联系人界面 {good}/{times} 次")
    return f"{good}/{times}"


def attempt(name, func):
    """跑一个步骤，出错就记下来，不影响后面的步骤"""
    try:
        results[name] = func()
    except Exception as e:
        results[name] = f"出错: {e}"
        print("  !", name, "出错:", e)


if not eye.is_enabled():
    print("Shadow Eye 没有启用，先运行 tools\\build_eye.ps1")
    sys.exit(1)

threading.Thread(target=user_worker, daemon=True).start()
results = {}
try:
    attempt("点击坐标验证", lambda: "通过" if click_test() else "未通过")

    device.stop_app(CONTACTS)
    device.start_app(CONTACTS)
    time.sleep(4)

    def phase(title, mode, interval, open_search):
        prepare_main(open_search)
        return run_phase(title, mode, interval)

    attempt("阶段1 主屏闲置", lambda: phase("阶段 1：主屏没人操作", None, 0, False))
    attempt("阶段2 每0.6秒打字", lambda: phase("阶段 2：主屏每 0.6 秒打一个字", "type", 0.6, True))
    attempt("阶段3 每0.2秒打字", lambda: phase("阶段 3：主屏每 0.2 秒打一个字（比真人还快）", "type", 0.2, True))
    attempt("阶段4 不停滑动", lambda: phase("阶段 4：主屏不停上下滑动（像刷信息流）", "swipe", 0, False))
finally:
    state["mode"] = None
    time.sleep(0.5)
    device.adb("am force-stop com.android.settings")
    device.adb("am force-stop com.google.android.settings.intelligence")
    device.adb("input -d 0 keyevent KEYCODE_HOME")

print("\n================ 汇总 ================")
for name, value in results.items():
    print(f"{name}: {value}")
print("对比：uiautomator 在阶段 2 是 0/4")
