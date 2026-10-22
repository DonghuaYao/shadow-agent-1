"""把界面树精简成一份给大模型看的元素列表。"""
import re
import xml.etree.ElementTree as ET

BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
IGNORE_PACKAGES = {"com.android.systemui"}  # 状态栏、导航栏，不是任务内容


def clean(s):
    """整理文字：合并空白、丢掉图片数据、截断过长的内容"""
    s = " ".join(s.split())
    if s.startswith(("svg+xml", "data:")):
        return ""
    return s[:80]


def get_box(attrs):
    m = BOUNDS.match(attrs.get("bounds", ""))
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def child_texts(node):
    """收集所有子孙节点上的文字"""
    found = []
    for child in node.iter("node"):
        if child is node:
            continue
        t = clean(child.attrib.get("text", "")) or clean(child.attrib.get("content-desc", ""))
        if t:
            found.append(t)
    return found


def walk(node, inside_clickable, elements):
    a = node.attrib
    if a.get("package") in IGNORE_PACKAGES:
        return

    clickable = a.get("clickable") == "true"
    editable = a.get("class", "").endswith("EditText")
    scrollable = a.get("scrollable") == "true"

    label = clean(a.get("text", "")) or clean(a.get("content-desc", ""))
    if clickable and not label:
        label = " / ".join(child_texts(node))[:80]  # 可点的容器借用里面的文字

    # 可操作的都留；纯文字只在不被可点容器包住时才留，避免重复
    keep = clickable or editable or scrollable or (label and not inside_clickable)
    box = get_box(a)
    if keep and box:
        x1, y1, x2, y2 = box
        elements.append({
            "kind": a.get("class", "").split(".")[-1],
            "label": label,
            "clickable": clickable,
            "editable": editable,
            "scrollable": scrollable,
            "checked": a.get("checked") == "true",
            "focused": a.get("focused") == "true",
            "x": (x1 + x2) // 2,
            "y": (y1 + y2) // 2,
        })

    for child in node:
        walk(child, inside_clickable or clickable, elements)


def parse(xml_text):
    """界面树 xml -> 元素列表，每个元素有编号 id"""
    root = ET.fromstring(xml_text)
    elements = []
    for child in root:
        walk(child, False, elements)
    for i, e in enumerate(elements):
        e["id"] = i
    return elements


def describe(elements):
    """元素列表 -> 给大模型看的文字，每行一个元素"""
    lines = []
    for e in elements:
        flags = [name for name in ("clickable", "editable", "scrollable", "checked", "focused") if e[name]]
        lines.append(f'[{e["id"]}] {e["kind"]} "{e["label"]}" {" ".join(flags)}'.rstrip())
    return "\n".join(lines)


def find(elements, text):
    """按文字找第一个匹配的元素（不区分大小写），找不到返回 None"""
    for e in elements:
        if text.lower() in e["label"].lower():
            return e
    return None
