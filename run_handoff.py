"""交接演示：agent 在 Chrome 里打开百度并进入登录页。
登录必须由用户本人完成，所以 agent 停下来，在手机上发通知，等用户处理。
完成边界：已到达百度登录页，并向用户发出了交接请求。
验证不靠 agent 自述：交接那一刻单独读 Chrome 的地址栏，看网址是不是百度登录页。
用法: py run_handoff.py"""
import sys
import time
import xml.etree.ElementTree as ET

from agent import device, eye, handoff, loop

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACKAGE = "com.android.chrome"
LOGIN_HOST = "wappass.baidu.com"
TASK = ("在 Chrome 里打开 m.baidu.com，点击页面上的“登录”，进入登录页面。"
        "登录需要用户本人的账号和验证码，你不能自己输入。"
        "到了登录页面后，只需要用 handoff 请求用户接手一次；"
        "用户处理完、回到你这里之后，直接输出 done，不要再次交接。")

evidence = {"handoffs": 0, "at_login": False}
original_request = handoff.request


def chrome_url():
    """独立读一次副屏上 Chrome 地址栏里的网址"""
    root = ET.fromstring(eye.dump(device.DISPLAY_ID))
    for node in root.iter("node"):
        if node.attrib.get("resource-id") == "com.android.chrome:id/url_bar":
            return node.attrib.get("text", "")
    return ""


def left_login_page():
    """用户处理完的条件：页面已经离开登录页"""
    return LOGIN_HOST not in chrome_url()


def request_with_check(reason, interactive, wait_seconds=300, until=None):
    url = chrome_url()
    evidence["handoffs"] += 1
    evidence["at_login"] = evidence["at_login"] or (LOGIN_HOST in url)
    print("     [独立检查] 交接时副屏 Chrome 地址栏:", url)
    print("     [独立检查] 是否百度登录页:", LOGIN_HOST in url)
    return original_request(reason, interactive, wait_seconds, until)


handoff.request = request_with_check


def check():
    if evidence["handoffs"] == 0:
        return False, "agent 没有请求交接"
    if not evidence["at_login"]:
        return False, "每次交接时 Chrome 地址栏都不是百度登录页"
    return True, "交接时地址栏确认是百度登录页"


device.adb("am force-stop com.android.chrome")
if "--fresh" in sys.argv:  # 只有加 --fresh 才清空 Chrome（会重新走首次启动流程，比较慢）
    device.adb("pm clear com.android.chrome")
time.sleep(2)

print("任务:", TASK, "\n")
result = loop.run(TASK, PACKAGE, verify=check, interactive=True, max_steps=18,
                  handoff_until=left_login_page)
print("\n运行结果:", result)
ok = result["status"] == "done" and evidence["at_login"]
print("agent 自称:", result["status"], "| 交接次数:", evidence["handoffs"],
      "| 交接时确实在登录页:", evidence["at_login"])
print("演示结论:", "通过" if ok else "未通过")
sys.exit(0 if ok else 1)
