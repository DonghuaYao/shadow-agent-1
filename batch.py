"""连续跑 N 次任务并统计。用法: py batch.py 5"""
import json
import sys
from datetime import datetime
from pathlib import Path

import run_task

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
count = int(sys.argv[1]) if len(sys.argv) > 1 else 5

rows = []
for i in range(1, count + 1):
    print(f"\n===== 第 {i}/{count} 次 =====")
    r = run_task.run_once()
    r["ok"] = r["status"] == "done" and r["verified"]
    rows.append(r)
    print(f"结果: {'成功' if r['ok'] else '失败'} | agent 自称 {r['status']} | "
          f"独立验证 {'通过' if r['verified'] else '未通过'} | 步数 {r['steps']} | "
          f"用时 {r['seconds']} 秒 | 主屏变化 {r['main_changes']} 次")

good = [r for r in rows if r["ok"]]
false_claims = [r for r in rows if r["status"] == "done" and not r["verified"]]

print("\n================ 汇总 ================")
print(f"成功 {len(good)}/{count}")
print(f"谎报（自称完成但数据库里没有）: {len(false_claims)} 次")
if good:
    print(f"成功运行的平均步数: {sum(r['steps'] for r in good) / len(good):.1f}")
    print(f"成功运行的平均用时: {sum(r['seconds'] for r in good) / len(good):.0f} 秒")
print(f"所有运行里主屏被改动的总次数: {sum(r['main_changes'] for r in rows)}")
for i, r in enumerate(rows, 1):
    if not r["ok"]:
        print(f"第 {i} 次失败: {r['status']} - {r['detail']}  日志: {r['log']}")

Path("runs").mkdir(exist_ok=True)
out = Path("runs") / f"batch-{datetime.now():%Y%m%d-%H%M%S}.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print("详细结果已保存:", out)
