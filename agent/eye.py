"""通过手机上的 Shadow Eye 无障碍服务读取所有屏幕的界面树。
和 uiautomator 不同，它不用等界面空闲，用户在主屏频繁操作时也能读。"""
import subprocess
import time

from agent.device import ADB, adb

PACKAGE = "com.shadowagent.eye"
SERVICE = f"{PACKAGE}/{PACKAGE}.EyeService"


def is_enabled():
    return SERVICE in adb("settings get secure enabled_accessibility_services")


def read_file():
    raw = subprocess.run(
        [ADB, "exec-out", "run-as", PACKAGE, "cat", "files/ui.xml"],
        capture_output=True,
        timeout=15,
    ).stdout
    return raw.decode("utf-8", errors="replace")


def dump(display=None, timeout=6.0):
    """请求一次界面导出，等到手机写出对应编号的文件后返回 xml 文字"""
    request_id = str(int(time.time() * 1000))
    extra = f" --es display {display}" if display is not None else ""
    adb(f"am broadcast -a {PACKAGE}.DUMP -p {PACKAGE} --es id {request_id}{extra}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = read_file()
        if f'req="{request_id}"' in text and text.rstrip().endswith("</displays>"):
            return text
        time.sleep(0.15)
    raise RuntimeError("Shadow Eye 没有在时限内返回界面")