"""任务：在联系人 App 里新建一个联系人，结束后用系统数据库独立验证。
单次运行: py run_task.py
"""
import re
import sys
import time

from agent import device, loop

NAME = "Test Alice"
PHONE = "5551234567"
PACKAGE = "com.google.android.contacts"
TASK = f"在联系人 App 里新建一个联系人，名字填 {NAME}，电话填 {PHONE}，保存。"


def saved_contacts():
    """直接查系统的联系人数据库，返回原始输出"""
    return device.adb(
        "content query --uri content://com.android.contacts/data/phones "
        "--projection display_name:data1"
    )


def has_contact(rows):
    for line in rows.splitlines():
        name = re.search(r"display_name=(.*?), data1=", line)
        number = re.search(r"data1=(.*)$", line)
        if name and number:
            if name.group(1).strip() == NAME and PHONE in re.sub(r"\D", "", number.group(1)):
                return True
    return False


def reset():
    """删掉测试联系人，并让联系人 App 回到全新状态（引导页、权限弹窗都会重来）"""
    uri = "content://com.android.contacts/raw_contacts?caller_is_syncadapter=true"
    where = f"display_name='{NAME}'"
    device.adb(f'content delete --uri "{uri}" --where "{where}"')
    if has_contact(saved_contacts()):
        # 兜底：直接清空联系人数据库
        device.adb("pm clear com.android.providers.contacts")
        time.sleep(2)
    device.adb(f"pm clear {PACKAGE}")
    time.sleep(1)
    return not has_contact(saved_contacts())


def run_once():
    """重置 -> 跑任务 -> 独立验证，返回一份结果字典"""
    if not reset():
        return {"status": "reset_failed", "verified": False, "steps": 0, "seconds": 0,
                "main_changes": 0, "detail": "重置失败，联系人仍然存在", "log": ""}
    start = time.time()
    result = loop.run(TASK, PACKAGE)
    result["seconds"] = round(time.time() - start)
    result["verified"] = has_contact(saved_contacts())
    return result


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("任务:", TASK, "\n")
    result = run_once()
    print("\n运行结果:", result)
    print("agent 自称:", result["status"], "| 独立验证:", "通过" if result["verified"] else "未通过")
