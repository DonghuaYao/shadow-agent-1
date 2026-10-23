"""主循环：观察界面 -> 问大模型 -> 执行动作 -> 记录。"""
import json
import time
from datetime import datetime
from pathlib import Path

from agent import brain, device, ui

SCREEN_WIDTH = 720  # 副屏宽度，滑动时用
# 权限请求这类系统界面，在任何 App 的任务里都可能出现，算正常
SYSTEM_OK = {"com.google.android.permissioncontroller", "com.android.permissioncontroller"}


def run_action(action, elements):
    """执行模型给出的动作，返回一句话描述结果"""
    kind = action.get("action")

    if kind in ("tap", "type"):
        index = action.get("id")
        if not isinstance(index, int) or not 0 <= index < len(elements):
            return f"错误：没有编号为 {index} 的元素"
        target = elements[index]
        device.tap(target["x"], target["y"])
        if kind == "tap":
            return f'点击了 [{index}] "{target["label"]}"'
        time.sleep(0.8)
        device.clear_text()
        text = action.get("text", "")
        device.type_text(text)
        return f'在 [{index}] 输入了 "{text}"'

    if kind == "swipe":
        mid = SCREEN_WIDTH // 2
        if action.get("direction") == "down":
            device.swipe(mid, 400, mid, 900)
        else:
            device.swipe(mid, 900, mid, 400)
        return "滚动了页面"

    if kind == "back":
        device.back()
        return "按了返回键"

    if kind == "wait":
        time.sleep(2)
        return "等待了 2 秒"

    return f"错误：不认识的动作 {kind}"


def read_screen(allowed):
    """读副屏界面。读到的不是目标 App（或者是空的）就等一等再读，最多 3 次。
    返回 (元素列表, 看到的包名, 是否可信)"""
    elements, packages = [], set()
    for _ in range(3):
        elements = ui.parse(device.dump_ui())
        packages = {e["package"] for e in elements}
        if elements and packages & allowed:
            return elements, packages, True
        time.sleep(2)
    return elements, packages, False


def run(task, package, max_steps=15):
    client = brain.make_client()
    folder = Path("runs") / datetime.now().strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True)
    allowed = {package} | SYSTEM_OK

    device.stop_app(package)
    device.start_app(package)
    main_before = device.top_activity(0)

    history = []
    last_screen = None
    main_changes = 0
    step = 0
    status, detail = "max_steps", f"跑满 {max_steps} 步仍未结束"

    with open(folder / "steps.jsonl", "w", encoding="utf-8") as log:
        for step in range(1, max_steps + 1):
            time.sleep(1.5)  # 等页面稳定
            elements, packages, trusted = read_screen(allowed)
            screen = ui.describe(elements)
            record = {"step": step, "screen": screen, "model_reply": "", "result": ""}

            if not trusted:
                status = "wrong_screen"
                detail = f"副屏上读到的不是目标 App，包名: {sorted(packages)}"
                print("     !", detail)
                log.write(json.dumps(record, ensure_ascii=False) + "\n")
                break

            shown = screen
            if screen == last_screen:
                shown += "\n（注意：上一步之后界面没有任何变化）"
            last_screen = screen

            action, raw = brain.decide(client, task, history, shown)
            record["model_reply"] = raw
            kind = action.get("action")
            why = action.get("reason") or action.get("summary") or ""
            print(f"[{step}] {kind}: {why}")

            if kind in ("done", "fail"):
                status = kind
                detail = action.get("summary") or action.get("reason") or ""
                log.write(json.dumps(record, ensure_ascii=False) + "\n")
                break

            if kind == "handoff":
                print("     需要你来处理:", why)
                input("     处理完后按回车继续 ...")
                result = "用户已处理，继续"
            else:
                try:
                    result = run_action(action, elements)
                except Exception as e:
                    result = f"错误：{e}"
                print("     ->", result)

            main_now = device.top_activity(0)
            if main_now != main_before:
                print("     ! 主屏最前面变了:", main_before, "->", main_now)
                main_before = main_now
                main_changes += 1

            record["result"] = result
            log.write(json.dumps(record, ensure_ascii=False) + "\n")
            log.flush()
            history.append(f"{step}. {json.dumps(action, ensure_ascii=False)} -> {result}")

    return {"status": status, "detail": detail, "steps": step,
            "log": str(folder), "main_changes": main_changes}
