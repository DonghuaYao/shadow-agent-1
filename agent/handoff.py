"""交接：遇到必须由用户本人完成的步骤（登录、验证码、支付）时，
不抢屏、不阻塞：在手机上发一条通知，然后等用户处理。"""
import time

from agent import device, eye, ui

try:
    import msvcrt  # Windows：不阻塞地检查有没有按键
except ImportError:
    msvcrt = None

QUIET_SECONDS = 10  # 没有明确的处理完了条件时，用户操作后界面安静这么久才继续


def notify():
    """在手机上发一条通知，返回命令输出"""
    return device.adb(
        "cmd notification post -t 'Shadow Agent' shadow_handoff "
        "'Needs your help: please finish one step on the agent screen'"
    )


def screen_signature():
    try:
        elements = ui.parse(eye.dump(device.DISPLAY_ID), device.DISPLAY_ID)
        return ui.describe(elements)
    except Exception:
        return ""


def request(reason, interactive, wait_seconds=300, until=None):
    """请求用户接手，返回一句话描述结果。
    until：可选，返回 True 表示用户已经处理完（比如页面离开了登录页）。"""
    if not interactive:
        return ("自动测试模式：没有人可以接手。handoff 只用于登录、验证码、支付，"
                "其他情况不要用，请继续自己完成。")
    print("     通知结果:", notify() or "已发送")
    print("     请在副屏窗口里完成这一步；处理完后在终端按回车，或者等我检测到处理完成。")
    last = screen_signature()
    changed_at = None
    end = time.time() + wait_seconds
    while time.time() < end:
        if msvcrt and msvcrt.kbhit():
            msvcrt.getwch()
            return "用户按回车确认已处理，继续"
        time.sleep(1.5)
        if until is not None:
            try:
                if until():
                    time.sleep(2)
                    return "检测到用户已处理完，继续"
            except Exception:
                pass
            continue
        sig = screen_signature()
        if sig != last:
            last, changed_at = sig, time.time()
        elif changed_at and time.time() - changed_at >= QUIET_SECONDS:
            return "检测到用户操作后界面已稳定，继续"
    return "等了很久用户没有处理，停止等待"
