"""同时测试。
用法:
  py concurrent_test.py user   只模拟主屏用户打字（对照组，不跑 agent）
  py concurrent_test.py both   主屏用户打字 + 副屏 agent 同时跑任务
"""
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import run_task
from agent import device, eye, ui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USER_DISPLAY = 0
PATTERN = "xyz"          # agent 要输入的文字里没有 x y z
INTERVAL = 1.0           # 模拟用户每 0.6 秒敲一个字符
USER_ONLY_SECONDS = 90  # 对照组持续时间


def field_text(raw, display):
    """取指定屏幕上第一个输入框里的文字；读取失败或没有输入框返回 None"""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    scope = root
    if root.tag == "displays":
        scope = next((d for d in root if d.attrib.get("id") == str(display)), None)
        if scope is None:
            return None
    for node in scope.iter("node"):
        if node.attrib.get("class", "").endswith("EditText"):
            return node.attrib.get("text", "")
    return None


def anr_dialogs():
    """系统里有没有 应用无响应 弹窗"""
    out = device.adb("dumpsys window windows", timeout=30)
    return [line.strip() for line in out.splitlines() if "Not Responding" in line]


def wait_main(check, seconds=15):
    """反复读，直到主屏满足条件；超时返回 None，并把原始数据存下来"""
    end = time.time() + seconds
    raw = ""
    while time.time() < end:
        try:
            raw = eye.dump()
            found = check(raw)
            if found:
                return found
        except Exception as e:
            print("  读取出错:", e)
        time.sleep(0.8)
    Path("runs").mkdir(exist_ok=True)
    Path("runs/setup_fail.xml").write_text(raw, encoding="utf-8")
    seen = ui.parse(raw, USER_DISPLAY) if raw else []
    print("  主屏等不到目标，主屏现在有:", sorted({e["package"] for e in seen}), [e["label"] for e in seen if e["label"]][:6])
    return None


def clear_anr():
    """主屏上如果有“无响应”弹窗，先点 Wait，让模拟器缓一缓"""
    for _ in range(5):
        try:
            main = ui.parse(eye.dump(), USER_DISPLAY)
        except Exception:
            return
        wait = ui.find(main, "Wait")
        if wait is None or not any("responding" in e["label"] for e in main):
            return
        print("  主屏上有无响应弹窗，先点 Wait 并等一等")
        device.adb(f"input -d {USER_DISPLAY} tap {wait['x']} {wait['y']}")
        time.sleep(6)


def setup_user_screen():
    clear_anr()
    """在主屏打开 Settings 的搜索页，让光标停在输入框里"""
    device.adb("am force-stop com.android.settings")
    device.adb("am force-stop com.google.android.settings.intelligence")
    device.adb(f"am start --display {USER_DISPLAY} -n com.android.settings/.Settings")
    box = wait_main(lambda raw: ui.find(ui.parse(raw, USER_DISPLAY), "Search settings"))
    if box is None:
        return False
    device.adb(f"input -d {USER_DISPLAY} tap {box['x']} {box['y']}")
    return bool(wait_main(lambda raw: field_text(raw, USER_DISPLAY) is not None, 8))


typed = []
stop = threading.Event()
first_anr = {}
begin = 0.0


def user_types():
    i = 0
    while not stop.is_set():
        chunk = "xyzxy"  # 一次敲 5 个字再停顿，像真人打字，也少启动几次 adb 进程
        device.adb(f"input -d {USER_DISPLAY} text {chunk}")
        typed.extend(chunk)
        i += 1
        if i % 40 == 0 and "chars" not in first_anr and anr_dialogs():
            first_anr["chars"] = len(typed)
            first_anr["seconds"] = round(time.time() - begin)
        time.sleep(INTERVAL)


mode = sys.argv[1] if len(sys.argv) > 1 else "both"
if mode not in ("user", "both"):
    print("用法: py concurrent_test.py user|both")
    sys.exit(1)

if not setup_user_screen():
    print("主屏准备失败：没找到搜索框或输入框。")
    sys.exit(1)

main_start = device.top_activity(USER_DISPLAY)
print("模式:", "对照组（只有模拟用户）" if mode == "user" else "主屏用户 + 副屏 agent")
print("主屏起始页面:", main_start, "\n")

begin = time.time()
thread = threading.Thread(target=user_types)
thread.start()
result = None
if mode == "both":
    result = run_task.run_once()
else:
    time.sleep(USER_ONLY_SECONDS)
stop.set()
thread.join()
seconds = round(time.time() - begin)

expected = "".join(typed)
actual = field_text(eye.dump(), USER_DISPLAY)
dialogs = anr_dialogs()
main_end = device.top_activity(USER_DISPLAY)

print("\n================ 结果 ================")
if result:
    ok = result["status"] == "done" and result["verified"]
    print("副屏任务:", "成功" if ok else "失败", "| agent 自称", result["status"],
          "| 独立验证", "通过" if result["verified"] else "未通过",
          "| 步数", result["steps"])
    print("   agent 自称完成但独立检查没通过的次数:", result.get("false_claims", 0))
    if not ok:
        print("   详情:", result["detail"])
if result and not result["verified"]:
    print("系统数据库里的联系人:", run_task.saved_contacts() or "（空）")
print("总用时:", seconds, "秒")
print("主屏页面 前后:", main_start, "->", main_end)
print("主屏 模拟用户共敲了", len(expected), "个字符")
if actual is None:
    print("主屏输入框内容: 读取失败（界面树里没有输入框，可能被弹窗盖住了）")
else:
    print("主屏输入框里读到", len(actual), "个字符（Shadow Eye 单个文字最多保留 200 个，只比较读到的部分）")
    print("主屏内容是否完整无误:", "是" if actual.lower() == expected[:len(actual)] else "否")
    if actual.lower() != expected[:len(actual)]:
        print("   丢失/多出的字符数:", abs(len(expected) - len(actual)))
        print("   期望末尾:", expected[-20:])
        print("   实际末尾:", actual[-20:])
print("无响应弹窗:", "有 -> " + dialogs[0] if dialogs else "没有")
if first_anr:
    print("   弹窗第一次被发现时：已敲", first_anr["chars"], "个字符，开始后", first_anr["seconds"], "秒")
