"""任务：在联系人 App 里新建一个联系人，结束后用系统数据库独立验证。"""
import re
import sys

from agent import device, loop

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NAME = "Test Alice"
PHONE = "5551234567"
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


if has_contact(saved_contacts()):
    print(f"{NAME} 已经存在，请先在联系人里手动删除再运行。")
    sys.exit(1)

print("任务:", TASK, "\n")
result = loop.run(TASK, "com.google.android.contacts")
print("\n运行结果:", result)

after = saved_contacts()
print("\n--- 系统数据库里的联系人 ---")
print(after)
verified = has_contact(after)
print("\nagent 自称:", result["status"], "| 独立验证:", "通过" if verified else "未通过")
