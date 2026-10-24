"""主循环：观察界面 -> 问大模型 -> 执行动作 -> 记录。"""
import json
import time
from datetime import datetime
from pathlib import Path

from agent import brain, device, handoff, ui

SCREEN_WIDTH = 720  # 副屏宽度，滑动时用
# 权限请求这类系统界面，在任何 App 的任务里都可能出现，算正常
SYSTEM_OK = {"com.google.android.permissioncontroller", "com.android.permissioncontroller", "android"}


def norm(s):
    """比较文字时忽略空格、括号、横线和大小写"""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def read_back(target, typed):
    """输入后重新读一遍副屏，返回刚输入的那个输入框里显示的文字；找不到返回 None"""
    try:
        elements = ui.parse(device.dump_ui())
    except Exception:
        return None
    fields = [e for e in elements if e["editable"]]
    if not fields:
        return None
    best = min(fields, key=lambda e: abs(e["x"] - target["x"]) + abs(e["y"] - target["y"]))
    return best["label"]


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
        shown = None
        for attempt in range(3):
            if attempt:  # 内容不一致：重新点进输入框，清空后重输
                device.tap(target["x"], target["y"])
                time.sleep(0.5)
                device.clear_text()
            device.type_text(text)
            time.sleep(1.0)
            shown = read_back(target, text)
            if shown is None or norm(shown) == norm(text):
                break  # 读不到输入框时不重试（可能有弹窗，乱点会点到弹窗按钮）
        if action.get("enter"):
            device.press("KEYCODE_ENTER")
            time.sleep(1.0)
        note = ""
        if shown is not None and norm(shown) != norm(text):
            note = f"（注意：输入框里实际显示的是 {shown!r}，和要输入的不一致，需要重新输入）"
        return f'在 [{index}] 输入了 "{text}"，界面显示 {shown!r}{note}'

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


def run(task, package, max_steps=20, verify=None, max_verify_rounds=2, interactive=False, handoff_until=None):
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
    false_claims = 0
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

            try:
                action, raw = brain.decide(client, task, history, shown)
            except Exception as e:
                action, raw = {"action": "wait", "reason": "模型接口没有响应，稍后重试"}, repr(e)
            record["model_reply"] = raw
            kind = action.get("action")
            why = action.get("reason") or action.get("summary") or ""
            print(f"[{step}] {kind}: {why}")

            if kind == "done" and verify is not None:
                passed, info = verify()
                if not passed:
                    false_claims += 1
                    result = f"独立检查未通过：{info}。保存的内容有错或缺失，请修正后再 done"
                    print("     ! 自称完成，但独立检查没通过:", info)
                    record["result"] = result
                    log.write(json.dumps(record, ensure_ascii=False) + "\n")
                    log.flush()
                    if false_claims > max_verify_rounds:
                        status = "unverified"
                        detail = f"自称完成，但独立检查多次未通过：{info}"
                        break
                    history.append(f"{step}. done -> {result}")
                    continue

            if kind in ("done", "fail"):
                status = kind
                detail = action.get("summary") or action.get("reason") or ""
                log.write(json.dumps(record, ensure_ascii=False) + "\n")
                break

            if kind == "handoff":
                print("     需要你来处理:", why)
                result = handoff.request(why, interactive, until=handoff_until)
                print("     ->", result)
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
            "log": str(folder), "main_changes": main_changes,
            "false_claims": false_claims}
