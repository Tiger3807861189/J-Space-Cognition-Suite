# J-Space Cognition Suite SV1

[English](README.md)

[![Concept DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21971181.svg)](https://doi.org/10.5281/zenodo.21971181)

J-Space 是面向复杂推理、大型仓库工程、子代理协作与授权安全分析的推理时工作空间和控制套件。
它以一个 Skill 封装，通过按需加载模块、持久状态和证据检查，让长任务中的理解、修改、验证与恢复保持连接。

十三个模块共享一个核心前提和一个路由入口。Python 标准库脚本负责保存状态、实际重读原文、检测过期地图与证据，并在必要条件不满足时返回阻断结果。宿主提供工具与代理运行能力。

## 快速开始

需要能加载本地 `SKILL.md` 并读取配套文件的宿主。执行控制器和安装校验需要 Python 3.10+；
low/medium 可采用文档中的纯文本回退方式。不需要 pip 依赖或后台服务。

1. 将完整的 [`j-space/`](j-space/) 复制到宿主配置指定的 Skills 目录；各宿主没有统一安装位置或调用语法。
   保持 `SKILL.md`、`modules/`、`references/`、`scripts/` 的相对结构，避免多套一层 `j-space/j-space/`。
   单独分发技能时，将 `LICENSE` 和 `THIRD_PARTY_NOTICES.md` 一起复制到已安装的 `SKILL.md` 旁。
   使用空的目标目录，避免不同安装内容混合。
2. 使用 Python 3.10 或更高版本检查安装内容：

   ```text
   <python-command> <skill-root>/scripts/verify_suite.py
   ```

3. 如果宿主只在启动时发现技能，请重新加载，并通过技能选择器选中 `j-space`。
   只有宿主文档支持时才用 `$j-space` 或 `/j-space`；否则明确要求读取已安装的 `SKILL.md`。
   确认宿主能读取一个路由模块；需要严格门禁时，还应能执行安装目录中控制器的 `--help`。
4. 给出任务和验收条件：

   ```text
   请使用 j-space 修改这个仓库。先检查现有契约，维护有源码依据的地图，在有独立工作时使用子代理，并验证最终行为。
   ```

`<python-command>` 可替换为可用的 `python`、`python3` 或 `py -3`。`<skill-root>` 是实际安装目录。
以任务目录作为当前目录，或在控制器子命令前添加 `--root TASK_DIRECTORY`。

Bash 中对带空格的路径加引号：

```bash
python3 "/path with spaces/j-space/scripts/control.py" --root "/task directory" status
```

PowerShell 中引用解释器路径时使用调用运算符：

```powershell
& "C:\Python313\python.exe" "C:\Skills\j-space\scripts\control.py" --root "D:\Task Directory" status
```

请先初始化任务再运行 `status`。UTF-8 输入支持中文、英文任务内容；交付物遵循用户要求的语言。
在目标项目的任务目录运行控制器，不要在技能安装目录运行。复制文件不会自动注册钩子、启动代理或授予工具权限。

> **敬告：适用范围。** 本套件面向具有契约、依赖、验证和恢复需求的真实工程及生产项目，
> 不以“鹈鹕骑自行车”之类的玩具演示为目标。面向严肃工程是设计定位，不意味着未经验证的部署已具备生产就绪保证。

## 运行级别

| 级别 | 适用任务 | 控制方式 |
|---|---|---|
| `low` | 一眼可以核验的直接结果 | fast；无需建立持久状态 |
| `medium` | 少量相互依赖的步骤、边界明确的交付物 | full；按需模块与交付审查 |
| `high` | 多文件、多阶段、跨会话任务 | loop；共享状态、原文刷新、证据检查 |
| `xhigh` | 需要团队处理的复杂集成与竞争方案 | loop 加有界子代理协作、二次思考与独立复核 |

`media` 可作为 `medium` 的输入别名。任务的不确定性或依赖增加时提高级别；独立工作能够抵消协调成本时主动使用子代理。
宿主没有代理能力时，记录限制并执行顺序检查。

## 四个挡位的简单教程

先选择技能。下列命令中的 `<python-command>` 和 `<skill-root>` 应替换为实际解释器与技能安装目录，
路径含空格时加引号，并以目标任务目录作为当前目录。示例工件应来自实际工作和检查，不要为通过门禁制造空文件或虚假证据。

### low：工程任务中的单点检查

可以说：“使用 j-space 的 low 挡，检查这项配置变更是否保持超时单位一致。给出结论与依据，不扩大任务。”
读取相关输入、核验一个约束并返回结果，无需初始化状态。若发现跨文件依赖或未解决的不确定性，再升档。

### medium：有少量依赖步骤的小型交付

可以说：“使用 j-space 的 medium 挡，更新这个 API 示例，并对照实现验证参数。简短记录目标、不确定性和实际检查结果。”
可选择轻量账本：

```text
<python-command> <skill-root>/scripts/jspace.py note --goal "API example matches implementation" --next "Inspect the endpoint"
<python-command> <skill-root>/scripts/jspace.py note --open "Does the example cover required inputs?" --settled-by "Inspect the endpoint and run the example"
<python-command> <skill-root>/scripts/jspace.py seam
```

检查并运行示例后，用 `note --check "Observed result" --by "manual inspection of each input and execution of the reported case" --close 1`
记录真实结论，参数文字可改为中文。写好 `answer.md` 后运行 `jspace.py ship answer.md`。
它只做启发式文本审查，发现为提示；不可读或超大输入会被拒绝。它不能证明 API 行为正确。
同一个任务不要同时维护轻量账本和严格控制器两套状态。

### high：从仓库检查到最终交付

可以说：“使用 j-space 的 high 挡修复这个仓库问题。保持公开契约，维护有源码依据的地图，执行相关测试，逐项提供验收证据。”
先按下文“共享控制”初始化、读取源文、创建并同步和查看地图，再通过工作门禁。
完成修改，将真实验证写入 `evidence/root.txt`，逐项验收清单另写入 `evidence/completion.txt`。
只有 `src/router.py` 确实是重要源码依赖时才保留下列路径；请替换为实际文件，必要时重复 `--source`。

```text
<python-command> <skill-root>/scripts/control.py pulse --event checkpoint
<python-command> <skill-root>/scripts/control.py report --agent root --round 1 --summary "Observed repair and coverage" --evidence evidence/root.txt --completion evidence/completion.txt --source src/router.py --next "Deliver checked result"
<python-command> <skill-root>/scripts/control.py repo sync --map repo-map.json
<python-command> <skill-root>/scripts/control.py repo view --agent root
<python-command> <skill-root>/scripts/control.py repo check
<python-command> <skill-root>/scripts/control.py check --stage ship
```

最终同步前先更新地图的语义内容。新增报告或验收清单也会改变文件清单。交付前解决开放问题和安全候选。
退出码 0 允许交付，非零表示存在未满足条件；先修复该条件再检查，证据没有变化时反复重试不是恢复。

### xhigh：真实独立工作与集成

可以说：“使用 j-space 的 xhigh 挡完成这项集成。由真实子代理独立审查契约，再进行二次审视；复现重要发现，并保留分歧直到有区分力的检查将其解决。”
从已初始化的 high 任务开始，在为当前范围创建报告之前切换路由：

```text
<python-command> <skill-root>/scripts/control.py route --level xhigh --module modules/repository.md --reason "Independent integration review"
<python-command> <skill-root>/scripts/control.py read --agent root
<python-command> <skill-root>/scripts/control.py agent add --id reviewer --parent root --task "Inspect the integration contract" --owns src
<python-command> <skill-root>/scripts/control.py pulse --event resume --agent reviewer
<python-command> <skill-root>/scripts/control.py repo view --agent reviewer
<python-command> <skill-root>/scripts/control.py check --stage work --agent reviewer
```

宿主必须真实启动子代理，并把该代理自己的 pulse 输出送入它的上下文；注册 ID 不等于独立模型。
子代理经过两次实质检查，分别写出 `evidence/review-1.txt` 和 `evidence/review-2.txt`，再用
`report --agent reviewer --round 1` 与 `--round 2` 分别提交，每次都提供 `--summary`、`--evidence`、`--source` 和 `--next`。
主代理独立核验发现，把审核证据另写入 `evidence/acceptance.txt`：

```text
<python-command> <skill-root>/scripts/control.py review --agent root --target reviewer --verdict accepted --evidence evidence/acceptance.txt
```

主代理按 high 流程写入并提交自己的报告与验收清单。所有工件稳定后，更新并同步地图，
让**每个活跃代理**分别执行自己的 `read` 和 `repo view`，再执行主代理交付门禁。
目标、核心约束或路由变更后，必须重新完成报告轮次和审核。丢失的子代理用 `agent retire` 记录原因和活跃接收者，
随后由主代理重新核验完成状态。宿主确实没有代理能力时，通过
`note --solo-reason "具体缺失能力及由此产生的审核限制"` 记录降级；不要一人驱动两个身份来伪装独立性。

## 共享控制

初始化仓库任务并加载相应模块：

```text
<python-command> <skill-root>/scripts/control.py init --goal "验收条件" --next "检查入口" --level high --module modules/repository.md
<python-command> <skill-root>/scripts/control.py read --agent root
```

在任务目录中维护语义地图，例如 `repo-map.json`：

```json
{
  "summary": "服务边界与验证路由",
  "areas": [{"path": "src", "purpose": "请求处理与业务规则"}],
  "facts": [{"claim": "请求通过路由器进入", "evidence": "src/router.py"}],
  "dependencies": [{"from": "src/router.py", "to": "src/service.py", "contract": "已校验请求"}],
  "tests": [{"path": "tests", "covers": "请求校验与服务行为"}],
  "unknowns": [{"question": "重试如何影响写入？", "settled_by": "检查事务边界并测试重复请求"}]
}
```

请把示例路径和结论替换为实际检查过的源码，然后运行：

```text
<python-command> <skill-root>/scripts/control.py repo sync --map repo-map.json
<python-command> <skill-root>/scripts/control.py repo view --agent root
<python-command> <skill-root>/scripts/control.py check --stage work --agent root
<python-command> <skill-root>/scripts/control.py pulse --event tool --agent root
<python-command> <skill-root>/scripts/control.py note --next "验证修改后的行为"
```

修改前读地图和相关源码；修改并验证后更新语义内容，再同步地图、刷新读取。
指纹用于检查新鲜度，源码检查和测试用于判断内容是否正确。
控制器使用进程锁维护唯一状态 `.jspace/control.json`，并生成共享可读视图 `.jspace/CONTROL.md`。

| 能力 | 实际运行行为 |
|---|---|
| 原文刷新 | 从磁盘读取入口和活动模块，输出真实文本，为每个代理分别记录哈希与时间 |
| 循环调度 | 按恢复、阶段事件、调用次数或时间间隔触发刷新 |
| 仓库记忆 | 保存语义地图、内容清单，检测变化并记录地图读取 |
| 持久协作 | 记录有界分工、交付轮次、证据指纹与独立复核 |
| 安全证据 | 使用复现与负对照，维护候选、确认、否定、修复状态 |
| 工作与交付门禁 | 必需状态、原文读取、地图或证据缺失、过期时返回非零 |

完整命令、结构、证据要求、预算语义与恢复方式见[控制器参考](j-space/references/controller.md)。
可选的 [`jspace.py`](j-space/scripts/jspace.py) 提供适合有限任务的小型账本与启发式文本审查。
它的 `ship` 结果是提示；严格门禁使用 `control.py`。

通过 `route --level xhigh --module modules/repository.md --reason "集成需要独立复核"` 可在保留任务状态的同时升档或切换可选活动模块。
检查点使用 `note --check "结论" --by "方法与覆盖范围" --evidence PATH`。已有检查点、问题或核心锚点时修改目标，须加 `--inherit`（同一任务改写，保留）或 `--new-task` 并附 `--next`（归档旧状态后重新开始）。
交付前，主代理通过 `report` 的 `--completion PATH` 提交逐项验收证据；每个子代理提交交付与独立复核。
随后运行 `check --stage ship`。完整参数顺序见控制器参考。

## 宿主接入与刷新

要自动执行，请将宿主事件接入 [`host_bridge.py`](j-space/scripts/host_bridge.py)，把返回上下文送给对应代理，并执行 `allow` 决策。
[宿主接入说明](j-space/references/host-integration.md)包含 JSON 契约、事件映射、最小适配示例与连接验证方法。

默认每五个工具事件或十分钟触发原文刷新，在相关阶段和恢复事件立即刷新。这是可配置的工程起点；应依据宿主中的漂移和输入成本调整。
时间条件在下一次事件到来时检查；脚本不会自行向空闲模型注入内容。

没有原生事件接口时，在相同边界显式调用命令，并标明采用协作式控制。
没有 Python 或文件系统时，重述对话账本，并通过可用工具实际检索原文；明确记录缺失的执行保障。

## 子代理、仓库与安全

- [子代理协作](j-space/modules/orchestration.md)：每个子代理获得完整 Skill，注册归属与父代理，独立读取原文。
  结果进入共同维护的记录；同一个子代理针对薄弱点二次思考，再由其他代理或主代理复核证据。用测试处理分歧，保留不同意见。
- [仓库](j-space/modules/repository.md)：维护契约、入口、依赖、测试路由和未知区域。修改前读、验证后同步。
  多个候选方案需要修改相同路径时使用隔离工作副本。
- [安全](j-space/modules/cyber.md)：在授权环境中，从可控输入追踪至违反的属性。
  保留复现、预期与实际行为、负对照、结论依据，并在根本约束处验证修复。
- [知识与未知](j-space/modules/epistemics.md)：区分观察、推断和未解决问题，发现隐含约束，将新暴露的空白转为具体检查。

原有的内省、定向注意、推理桥接、广播、容量、监控、简写、标记和经验验证共同路由至工程模块。
一次保持一到两个活动概念，其余内容持久保存；子代理可访问完整套件，同时按阶段选择加载。

## 验证与评估

在仓库根目录运行：

```text
<python-command> j-space/scripts/verify_suite.py
<python-command> -m unittest discover -s tests -v
```

CI 配置 Windows、Linux、macOS。完整性检查覆盖入口、共同前提、模块结构、路由、本地链接和 Python 语法。
回归测试覆盖状态、输入校验、Unicode、持久化、新鲜度、协作与宿主事件。

仓库门禁会校验地图明确引用的文件，包括位于清单排除目录中的文件。每个活跃参与者必须查看最终地图；
目标、核心约束或路由变更后，需要重新提交报告并审核。可用 `agent retire` 保留废弃注册的历史和交接记录，
由 root 重新核验完成状态。大型目录应按实测门禁耗时配置宿主可信参数 `--timeout-seconds`，并同步增加外层宿主超时。
逐文件内容哈希仍然生效，详见[控制器契约](j-space/references/controller.md)。

测试证明其覆盖范围内的实现行为，不能证明通用模型性能增益，也不能保证宿主遵循协议。
请检查拟使用的具体提交和运行环境对应的 CI 结果。

## 项目结构

```text
J-Space Cognition Suite SV1/
├── .github/workflows/verify.yml
├── .gitignore
├── CITATION.cff
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── README.zh-CN.md
├── THIRD_PARTY_NOTICES.md
├── tests/
└── j-space/
    ├── SKILL.md
    ├── modules/                  # 十三个按需加载的协议
    ├── references/               # 科学资料、证据、示例与运行契约
    └── scripts/
        ├── control.py            # 持久门禁、地图、代理与证据
        ├── host_bridge.py        # 通用事件与上下文适配
        ├── jspace.py             # 独立轻量账本与文本审查
        ├── workspace-ledger.md   # 轻量账本契约
        └── verify_suite.py       # 编写期完整性检查
```

## 研究依据与能力边界

[工程证据](j-space/references/engineering-evidence.md)列出 J-space、四类已知/未知、LLM-as-a-Verifier、协作决策、仓库 Wiki 和重读的一手来源。
[科学参考](j-space/references/j-space-science.md)保留研究术语与来源摘录。

套件通过指令、工具、外部状态和宿主事件发挥作用，不修改模型权重，不测量神经工作空间大小，也不保证激活不同 MoE 专家。
选择性路由、全面审查和保留反证属于工程方法；其价值需要通过实际结果检验。

SV1 是一次架构升级。SV1 的数据与结论以自身记载的测量口径为准，不承接任何历史版本。

## 贡献者与许可

社区贡献者包括 [@forever-ivy](https://github.com/forever-ivy)、[@lanting200](https://github.com/lanting200)、[@afeer123](https://github.com/afeer123)、[@ShaneLau2](https://github.com/ShaneLau2)、[@menoxz](https://github.com/menoxz) 和 [@raelldottin](https://github.com/raelldottin)。

项目采用 [Apache License 2.0](LICENSE)。保留归属与[第三方声明](THIRD_PARTY_NOTICES.md)，外部材料遵循各自条款。
只分发 `j-space/` 时也应附带这两个文件。概念 DOI 用于整个项目；SV1 的版本 DOI 在归档时由 Zenodo 生成。
