# Shadow Agent：用户正常用手机，agent 同时在"副屏"里替你操作 App

一个能在**用户正常使用手机的同时**，通过操作真实 App 界面完成多步任务的 agent。
用户的主屏、焦点、键盘不被占用；agent 在另一块屏幕上干活，需要用户本人的步骤（登录、验证码）会发通知请用户接手。

> 本项目在 Android Studio 模拟器（Pixel 4，Android 13）上开发和验证。**没有在真机上测过**，真机落地方案见第 7 节，那一节里标明了哪些没验证过。

## 1. 核心思路

手机默认"一个人用一块屏"。我们让 Android 的**多显示屏**机制承担"两个使用者"：

- **Display 0（主屏）**：用户的手机，agent 不碰。
- **Display 2（副屏）**：agent 的工作区。App 被启动在副屏上（`am start --display 2`），点击和输入都指定屏幕（`input -d 2`）。不同的屏幕有各自的焦点和输入法，所以 agent 打字不会抢用户的键盘。

用户可以随时在副屏窗口里直接接管。

## 2. 架构

```
电脑 (Python)                                   模拟器 / 手机
┌──────────────────────────────┐   adb   ┌──────────────────────────────┐
│ loop.py   观察→决策→执行→校验  │ ──────► │ Display 0  用户的主屏          │
│ brain.py  调用大模型选下一步   │         │ Display 2  agent 的工作区       │
│ ui.py     界面树精简成短列表   │         │ Shadow Eye 无障碍服务(eye/)    │
│ eye.py    向 Shadow Eye 要界面 │ ◄────── │   读各屏幕所有窗口的界面树       │
│ device.py adb 操作(都带 -d 2)  │         └──────────────────────────────┘
│ handoff.py 交接：发通知并等待   │
└──────────────────────────────┘
```

每一步：读副屏界面树 → 精简成元素列表 → 大模型输出一个 JSON 动作（点击、输入、滑动、返回、等待、交接、完成）→ 执行 → 输入类动作回读核对 → 下一轮。

## 3. 技术选型与取舍

| 决策 | 选择 | 为什么不选别的 |
|---|---|---|
| 平台 | Android 模拟器的第二块屏 | iOS 没有后台操作其他 App 的机制；手头没有 Android 真机；云手机偏离"同一台手机" |
| "看" | 界面树（文字），不用截图 | 虚拟屏上 `screencap -d 2` 得到 0 字节，实测不能截图 |
| 读界面树 | 自己写的无障碍服务 Shadow Eye | `uiautomator dump` 在用户频繁操作主屏时读不到（见第 4 节） |
| 大模型 | 硅基流动的 DeepSeek-V3.2（OpenAI 兼容接口） | 开发机连不上 OpenAI 和 Google；国内直连；调用封装在 `brain.py` 一个文件里，可替换 |
| 结果验证 | 直接查系统联系人数据库 | agent 自称完成不算数，要有独立证据 |
| 权限 | 只用 adb，不 root、不改系统 | 方便在普通用户手机上落地 |

## 4. 实验中发现的关键事实

这些是开发中用实验证实的，也是方案演变的原因。

1. **虚拟屏不能用 `screencap -d` 截图**：返回 0 字节。所以 agent 读界面树文字。
2. **副屏有独立的焦点和输入法**：`am start --display 2` 启动的 App 一直留在副屏；`input -d 2 text` 输入时，`dumpsys input_method` 显示 `mCurTokenDisplayId=2`，键盘只出现在副屏；主屏的前台 App 全程没变。
3. **`uiautomator dump --display N` 的参数不生效**：用户刚操作过主屏时，`--display 2` 读到的是主屏内容，两条命令返回的内容完全一样。agent 曾因此对着主屏的弹窗乱点副屏。
4. **`uiautomator` 要等界面"空闲"**：主屏每 0.6 秒打一个字时，读取 8 次全部失败（`could not get idle state`），每次耗时约 12 秒；每 2 秒打一个字就全部成功。关掉我们自己的无障碍服务重测，结果相同。
5. **自写的无障碍服务 Shadow Eye 没有这个限制**：在主屏闲置、每 0.6 秒打字、每 0.2 秒打字、不停滑动四种条件下，各读 4 次，16/16 成功，每次 0.2 到 1.8 秒（`uiautomator` 要 2.5 到 3 秒）。同一次读取里两块屏幕分开返回，不受焦点影响。局限：用户操作是用 `adb input` 模拟的，副屏页面当时是静止的，样本小。

## 5. 结果（模拟器，诚实版）

测试任务：在联系人 App 里新建联系人（名字和电话），保存。每次运行前清空联系人和 App 数据。成功与否**只看系统数据库里是不是真的有这条联系人**。

| 条件 | 结果 |
|---|---|
| 主屏闲置 | 累计 12/12 成功（分布在 5 批运行、几个代码版本上），约 7 到 9 步，约 1 到 1.5 分钟 |
| 主屏有"用户"持续打字，同时 agent 跑任务 | **不稳定**：加验证闸门前 3/5（其中 2 次 agent 自称完成但数据库里没有）；加闸门后 2/5，最终没有谎报；之后模拟器状态变差，一轮 0/5 |

两点说明：

- **验证闸门**：agent 输出 `done` 后，代码立刻查数据库，没通过就把数据库现状告诉 agent 让它修正，最多两轮。加闸门后的 5 轮里拦下了 2 次想蒙混的 `done`，最终没有出现"自称完成却没成"。
- 同时测试里，**主屏上经常出现"应用无响应"**（Settings 搜索服务等）。没有 agent 的对照组：每 0.3 秒一个字符时也出现过无响应，改成每秒约 4 个字符（一次 5 个字再停顿）后两次对照都没出现；有 agent 时仍会出现。**真正原因没有证实**，怀疑是模拟器只配了 2 个核、2GB 内存，加上"模拟用户"每次要启动一个 adb 进程，比真人手指重很多。所以"用户同时操作时完全不被打扰"**目前没有被证明**。

## 6. 交接（需要用户本人的步骤）

遇到登录、验证码、支付，agent 用 `handoff`：在手机上发一条通知（不切前台），在副屏上停住等用户，用户处理完后继续。

演示：agent 在 Chrome 里打开百度，进入登录页后交接。完成边界是"**已到达百度登录页，并发出交接请求**"，验证不靠 agent 自述：交接那一刻直接读 Chrome 地址栏，网址含 `wappass.baidu.com` 才算。用户离开登录页（或在终端按回车）后 agent 继续。

- 截图里：通知出现在主屏通知栏，主屏前台仍是桌面。
- 已知问题：任务要求"只交接一次"，模型实际交接了 2 次；通知来源显示为 `Shell`（用 adb 命令发的），真机上应由自己的 App 发。

## 7. 权限与真机落地

本项目用到的权限（全部是普通开发者能拿到的，**没有 root、没有系统签名、没有改 ROM**）：

- adb shell：`am start --display`、`input -d`、`dumpsys`、`cmd notification`、`settings put secure`（开发时启用无障碍服务）。
- 仅测试用：`content query`（验证结果）、`pm clear`（重置状态）。
- Shadow Eye：无障碍服务，用户在设置里手动开启一次。

**在普通用户手机上怎么落地（设计思路，未实现、未验证）：**

- 副屏：模拟器自带第二块屏，真机没有。需要创建一块虚拟屏。设想用无线调试授权的 shell 身份（或 Shizuku）创建，开源工具 scrcpy 有类似功能，说明 adb 级权限可能够，但我们没有验证。
- 通知：由我们自己的 App 发，需要通知权限。
- 无障碍服务：与现在相同，用户开启一次。
- 不确定的地方：有些 App 可能不支持在副屏运行，或者会跳回主屏。我们只在系统设置、联系人、Chrome 上测过。

## 8. 已知局限

- 只在模拟器上测过，没有真机数据。
- "同时"的证据不充分：自动测试里主屏的"用户"是 adb 模拟的，且常触发无响应；没有拿真人长时间操作做统计。
- 只支持英文和数字输入（`input text` 不支持中文）。
- 任务只验证了"新建联系人"和"到登录页交接"两类，联系人是本地数据，没有登录 Google 账号（开发机连不上 Google）。
- 不同模型的稳定性没有对比。
- 每次读界面树的耗时和模型调用延迟让每步约 8 到 11 秒，效率一般。

## 9. 如何运行

环境：Windows，Python 3.13，Android Studio 模拟器（带第二块屏，Display 2），adb。

```powershell
py -m pip install openai
# 在本机用环境变量保存密钥，不要写进代码
$s = Read-Host "API key" -AsSecureString
[Environment]::SetEnvironmentVariable("SILICONFLOW_API_KEY", [System.Net.NetworkCredential]::new("", $s).Password, "User")
[Environment]::SetEnvironmentVariable("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3.2", "User")

powershell -File tools\build_eye.ps1   # 编译、安装 Shadow Eye 并启用（需要 Android Studio 自带 JDK）
py recover.py                          # 清掉残留的无响应弹窗
py run_task.py                         # 新建联系人任务，结束后查数据库验证
py run_handoff.py                      # 交接演示（到百度登录页，需要在终端按回车或在副屏点主页）
py batch.py 3                          # 连跑 3 次并统计
py concurrent_test.py both             # 主屏模拟用户打字 + 副屏 agent 同时跑
```

## 10. 仓库结构

```
agent/        device.py  adb 操作     eye.py   读界面树     ui.py    精简界面
              brain.py   大模型决策   loop.py  主循环       handoff.py 交接
eye/          Shadow Eye：Android 无障碍服务（Java，只做一件事：导出所有屏幕的界面树）
run_task.py   联系人任务 + 数据库验证    run_handoff.py  交接演示
batch.py      连跑并统计               concurrent_test.py  同时测试
recover.py    环境恢复                 tools/build_eye.ps1  编译安装
smoke_test.py explore.py focus_probe.py diag_dump.py diag_eye.py   实验脚本（第 4 节的证据来自这些）
```

## 11. AI 辅助开发过程

- 第一版由 ChatGPT 生成：一个固定点击序列的脚本（提交 `819665e`），在主屏操作，不满足题意，我评估后整体推翻。后来它又做了一个 WebView 网页自动化原型，因为不是真实第三方 App、步骤也是写死的，没有采用。
- 之后用 Claude 协作：每个结论先做小实验再采信，所有命令在 PowerShell 里运行，输出贴回来核对。第 4 节的发现多数是这样"推翻了前一个结论"得到的，例如一开始以为 `uiautomator --display 2` 能读副屏，后来发现它读的是焦点所在的屏。
- AI 写的代码也犯过错：例如写过不带 BOM 的脚本导致中文乱码、测试脚本漏改等待逻辑，都是靠运行输出发现并修正的。
- API key 只放环境变量，不进仓库。
