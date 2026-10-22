"""设备控制层：所有操作都只发给副屏 DISPLAY_ID，不碰主屏。"""
import os
import re
import subprocess
import time

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
DISPLAY_ID = 2  # agent 干活的副屏，主屏 0 留给用户


def adb(command, timeout=20):
    """在设备上执行一条 shell 命令，返回输出文字"""
    result = subprocess.run(
        [ADB, "shell", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return (result.stdout + result.stderr).strip()


def display_exists():
    """副屏是否存在"""
    return f"mDisplayId={DISPLAY_ID}" in adb("dumpsys display", timeout=30)


def start_app(package):
    """把 App 启动在副屏上"""
    out = adb(
        "cmd package resolve-activity --brief "
        "-a android.intent.action.MAIN -c android.intent.category.LAUNCHER "
        + package
    )
    component = out.splitlines()[-1].strip() if out else ""
    if "/" not in component:
        raise RuntimeError(f"找不到 {package} 的启动页面: {out}")
    return adb(f"am start --display {DISPLAY_ID} -n {component}")


def stop_app(package):
    adb(f"am force-stop {package}")


def top_activity(display_id):
    """某块屏幕当前最前面的页面，例如 com.android.settings/.Settings"""
    out = adb("dumpsys activity activities", timeout=30)
    current = None
    for line in out.splitlines():
        m = re.match(r"\s*Display #(\d+)", line)
        if m:
            current = int(m.group(1))
        elif current == display_id and "topResumedActivity" in line:
            m2 = re.search(r"u0 ([^\s}]+)", line)
            return m2.group(1) if m2 else line.strip()
    return None


def tap(x, y):
    adb(f"input -d {DISPLAY_ID} tap {x} {y}")


def swipe(x1, y1, x2, y2, duration_ms=300):
    adb(f"input -d {DISPLAY_ID} swipe {x1} {y1} {x2} {y2} {duration_ms}")


def press(key):
    """按键，例如 KEYCODE_BACK、KEYCODE_ENTER"""
    adb(f"input -d {DISPLAY_ID} keyevent {key}")


def back():
    press("KEYCODE_BACK")


def clear_text():
    """清空当前输入框：全选再删除"""
    adb(f"input -d {DISPLAY_ID} keycombination KEYCODE_CTRL_LEFT KEYCODE_A")
    press("KEYCODE_DEL")


def type_text(text):
    """往当前输入框打字。目前只支持英文、数字和常见符号。"""
    if not text.isascii():
        raise ValueError("input text 不支持中文，需要换别的输入方式")
    safe = text.replace(" ", "%s").replace("'", "'\\''")
    adb(f"input -d {DISPLAY_ID} text '{safe}'")


def dump_ui(retries=3):
    """读副屏的界面树，返回 xml 文字"""
    for _ in range(retries):
        adb("rm -f /sdcard/shadow_ui.xml")  # 先删旧文件，避免读到过期数据
        adb(f"uiautomator dump --display {DISPLAY_ID} /sdcard/shadow_ui.xml")
        raw = subprocess.run(
            [ADB, "exec-out", "cat", "/sdcard/shadow_ui.xml"],
            capture_output=True,
            timeout=20,
        ).stdout
        text = raw.decode("utf-8", errors="replace")
        if "<hierarchy" in text:
            return text
        time.sleep(1)
    raise RuntimeError("读取界面树失败")
