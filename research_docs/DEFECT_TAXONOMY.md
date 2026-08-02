# RoleCheck 角色缺陷分类规范

**版本：** v0.1  
**日期：** 2026-08-01  
**标注形式：** 多标签；一个角色可同时具有多个缺陷。  
**重要原则：** 缺陷标签不等于反事实团队价值。

---

# 1. 总体结构

RoleCheck 将问题分为三层：

```text
A. 内在角色缺陷 Intrinsic Defects
B. 团队关系缺陷 Relational Defects
C. 系统价值结果 Value Outcomes
```

A、B 是可诊断缺陷；C 是通过团队干预定义的结果，不应仅靠静态审计直接标注。

---

# 2. 通用标注原则

## 2.1 多标签而非互斥分类

一个角色可能同时欠描述、与另一个角色冗余，并且输出格式与聚合器不兼容，因此必须使用多标签。

## 2.2 缺陷存在与严重度分离

每个缺陷记录：

```text
presence_probability
severity
evidence
affected_contract_fields
confidence
```

建议严重度：

- `0 none`：无证据；
- `1 minor`：不影响主要职责；
- `2 moderate`：可能降低协作效率；
- `3 major`：很可能破坏角色功能；
- `4 critical`：合同无法执行或直接破坏系统。

## 2.3 设计缺陷与模型失败分离

若合同清晰、接口正确，但绑定模型无法完成职责，优先标注 `CAPABILITY_MISMATCH` 或仅记录能力限制，而不是把 Prompt 自动判为欠描述。

## 2.4 缺陷标签不决定动作

- REDUNDANCY 不自动意味着 REMOVE；
- UNDERSPECIFICATION 不自动意味着 REWRITE；
- TASK_IRRELEVANCE 不自动意味着零贡献。

动作由反事实保留/修复价值与不确定性决定。

---

# 3. 内在角色缺陷

## D1. UNDERSPECIFICATION：欠描述

### 定义

角色合同未明确说明完成职责所需的关键目标、输入、输出、判断标准或失败处理，使执行行为存在较大歧义。

### 正例

```text
角色：Verifier
Prompt：Check the answer carefully.
```

缺少如何验证、读取什么输入、输出 verdict 还是新答案、错误时如何报告以及是否允许推翻 Solver。

### 反例

职责简短但接口清楚，不属于欠描述：

```text
Return a JSON verdict indicating whether candidate_solution passes all tests.
```

### 静态可判断性

高，但需结合协议判断哪些字段是关键。

### 证据

- responsibilities 为空或不可操作；
- required input 未声明；
- output 不可消费；
- success criteria 缺失；
- 大量模糊词，无可观察动作。

### 可能影响

行为漂移、角色间重复、输出不可解析、角色遵循率低、修复候选空间过大。

### 常用修复

补全职责、输入、输出、标准和失败格式；增加非目标和禁止行为；不得无故增加新的团队权限。

### 易混淆

- `CAPABILITY_MISMATCH`：合同清晰但模型做不到；
- `PROTOCOL_MISMATCH`：角色输出清晰，但与下游不兼容。

---

## D2. INTERNAL_CONFLICT：角色内部冲突

### 定义

同一角色合同中的目标、职责、权限或约束互相矛盾，无法同时满足。

### 正例

```text
Never change the Solver's answer.
Independently correct any answer you believe is wrong.
```

### 反例

“优先保持原答案，除非发现可验证错误”具有明确优先级，不属于冲突。

### 静态可判断性

中到高。

### 证据

- 同一对象同时要求执行与禁止；
- 两个目标无优先级且不可同时完成；
- success criteria 与 prohibited behavior 冲突；
- 输出格式要求相互排斥。

### 可能影响

随机遵循部分指令、输出不稳定、高方差、角色无法形成稳定行为画像。

### 常用修复

删除矛盾要求，引入优先级，缩小权限和决策范围，明确冲突解决规则。

### 易混淆

- `AUTHORITY_CONFLICT` 是角色之间的冲突；
- `OVERLOAD` 是任务过多，不一定相互矛盾。

---

## D3. OVERLOAD：角色过载

### 定义

单个角色被要求承担过多、阶段跨度过大或相互竞争的职责，导致目标稀释、上下文过长或无法可靠执行。

### 正例

同一角色同时被要求规划需求、编写代码、执行测试、审查安全、做最终裁决并输出完整报告。

### 反例

一个角色完成紧密关联的“运行测试并根据失败修补代码”，未必过载。

### 静态可判断性

中等，需要结合模型、工具和资源限制。

### 证据

- 职责数量和异质性过高；
- 多个相互竞争的成功标准；
- 所需工具或能力跨度过大；
- 一个角色覆盖多个本应有清晰交接的阶段。

### 可能影响

忽略部分职责、高 Token 和延迟、职责执行顺序不稳定、难以归因。

### 常用修复

第一版不新增角色，因此只允许收缩职责、明确核心目标、删除非关键职责，或给出“需要拆分”的非执行建议。

### 易混淆

- `COVERAGE_GAP`：团队缺少职责；
- `CAPABILITY_MISMATCH`：职责合理但模型不具备能力。

---

## D4. CAPABILITY_MISMATCH：能力或资源不匹配

### 定义

角色职责明确且合理，但绑定模型、工具、权限或预算不足以完成要求。

### 正例

- 要求执行代码，但没有执行工具；
- 要求读取私有数据库，但没有权限；
- 要求长文档全局审查，但上下文窗口不足；
- 要求高级形式证明，但所用模型历史上几乎无法完成。

### 反例

模型偶尔犯错不等于能力不匹配。

### 静态可判断性

低到中；通常需要模型卡、工具配置或历史 Probe。

### 证据

- required capability 不在模型/工具能力标签中；
- 角色依赖不存在的工具；
- 资源限制低于最低输出要求；
- 历史上角色合同遵循率稳定极低。

### 可能影响

Prompt 被反复重写但性能不改善；将模型问题错误归因于角色设计；不必要修复。

### 常用修复

第一版通常不换模型或工具，因此标记不可由 Prompt 修复；KEEP 或 REMOVE 由价值策略决定，并输出升级模型或工具的非执行建议。

### 易混淆

UNDERSPECIFICATION、PROTOCOL_MISMATCH 和单次任务失败。

---

# 4. 团队关系缺陷

## D5. TASK_IRRELEVANCE：任务无关

### 定义

角色职责与当前任务完成所需能力和产物缺乏实质关联，且没有清晰的间接依赖路径。

### 正例

在纯数学证明任务中加入“市场趋势分析师”，且其输出不被任何节点使用。

### 反例

角色负责检查题目歧义或单位规范，可能具有间接价值，不能只凭角色名判定无关。

### 静态可判断性

中等。

### 证据

- 职责与任务需求语义距离高；
- 没有下游消费者；
- 输出不进入最终决策；
- 任务需求图中找不到对应职责。

### 可能影响

成本浪费、无关信息污染、增加聚合噪声。

### 常用修复

收缩为相关职责；若无法修复且保留价值为负，考虑 REMOVE。

### 易混淆

COVERAGE_GAP、REDUNDANCY，以及角色名无关但职责实际相关的情况。

---

## D6. REDUNDANCY：角色冗余

### 定义

该角色与现有成员在职责、输入、输出、决策方式或行为模式上高度重合，且缺乏明确互补性。

### 正例

两个角色都独立重做同一题，使用相同模型和 Prompt，输出同一格式，且无不同证据或方法要求。

### 反例

两个角色职责相似，但使用不同模型、不同工具、不同验证方法，或历史上具有显著错误互补，不能仅凭语义相似判定为有害冗余。

### 静态可判断性

中等；可靠判断通常需要行为或历史贡献信息。

### 证据

- responsibility 高相似；
- required inputs 和 outputs 一致；
- 模型、工具和方法约束一致；
- 历史答案一致率和共失败率高；
- 移除后团队效用不变。

### 可能影响

Token 和延迟浪费、多数投票放大共同错误、团队规模虚增。

### 常用修复

强制使用不同方法或关注不同错误类型；明确不重复已有推理；若不可修复且价值低，考虑 REMOVE。

### 易混淆

重复角色可能提供独立采样价值；还需与 TASK_IRRELEVANCE 和多模型 Ensemble 区分。

---

## D7. AUTHORITY_CONFLICT：权限冲突

### 定义

两个或多个角色对同一决策拥有相互不兼容的最终、否决或覆盖权限，且协议没有明确解决规则。

### 正例

- Verifier 和 Aggregator 都被声明为最终裁决者；
- 两个 Reviewer 均可无条件 veto；
- Solver 必须坚持答案，Critic 必须推翻答案。

### 反例

多个角色投票，协议明确多数决，不属于权限冲突。

### 静态可判断性

高。

### 证据

- 多个 `authority_level=final`；
- can_override 形成循环；
- 冲突解决规则缺失；
- Prompt 权限与工作流权限不一致。

### 可能影响

决策循环、最终答案不稳定、角色忽略其他成员、运行时依赖框架默认行为。

### 常用修复

收缩权限、改为 advisory、明确优先级或聚合规则；若必须改全局协议，则 abstain。

### 易混淆

INTERNAL_CONFLICT、正常 debate 和多数投票。

---

## D8. DEPENDENCY_GAP：依赖缺口

### 定义

角色执行所需输入、工具结果或上游产物没有生产者，或不能在正确时间到达。

### 正例

Verifier 要求 `candidate_solution`，但工作流中 Solver 输出未连接到 Verifier。

### 反例

输入可从全局任务上下文直接获得，不需要专门上游。

### 静态可判断性

高。

### 证据

- required input 无生产者；
- 上游在下游之后执行；
- 依赖角色被移除但无 fallback；
- 角色没有所需可见性。

### 可能影响

角色凭空假设输入、重复求解、空输出或运行时失败。

### 常用修复

若允许，调整合同中的输入假设或使用全局可见输入；第一版不改拓扑时，无法修复的依赖缺口应标记为协议外问题。

### 易混淆

PROTOCOL_MISMATCH、UNDERSPECIFICATION 和工具权限问题。

---

## D9. PROTOCOL_MISMATCH：协议不匹配

### 定义

角色合同与团队通信、聚合、停止或数据格式协议不兼容，导致角色的输出无法被正确利用。

### 正例

- Verifier 输出长自然语言报告，而聚合器只读取一个选项字母；
- 角色有 advisory 权限，但 Prompt 以 final 决策方式输出；
- 角色期望多轮反馈，协议只运行一轮；
- 下游期待 JSON，角色输出自由文本。

### 反例

输出格式不同但有确定性适配器，不属于不匹配。

### 静态可判断性

高。

### 证据

- 输出/输入 Schema 不兼容；
- 权限与聚合逻辑不一致；
- 交互轮次不满足角色职责；
- 终止信号无人读取。

### 可能影响

正确信息无法改变团队结果、格式错误、角色贡献被协议遮蔽、测得的保留价值为零或负。

### 常用修复

修改输出合同和 Prompt，明确可消费字段，收缩角色权限；若必须修改协议才能解决，则标记超出第一版修复范围。

### 易混淆

DEPENDENCY_GAP、AUTHORITY_CONFLICT 和聚合器本身设计缺陷。

---

## D10. COVERAGE_GAP：团队职责覆盖缺口

### 定义

团队整体缺少完成任务所需的关键职责。该标签是团队级缺陷，不应简单归属于某个角色。

### 正例

代码工作流只有 Planner 和 Coder，没有任何测试或验证职责。

### 反例

没有名为 Tester 的角色，但 Coder 合同明确包含可执行测试职责，则未必存在缺口。

### 静态可判断性

中等，依赖任务需求抽取。

### 证据

- 任务需求图存在无人承担的关键节点；
- 所有角色 non-goals 排除了某项必要职责；
- 最终产物缺少必要检查阶段。

### 可能影响

系统性错误无人发现；修复某个已有角色可能引入过载；仅 REMOVE/REWRITE 动作无法完整解决。

### 常用修复

第一版不新增角色，因此可将相邻角色轻量扩展，但必须检查是否造成 OVERLOAD；或输出“需要新增角色”的非执行建议。

### 易混淆

TASK_IRRELEVANCE、OVERLOAD，以及角色名与职责不一致。

---

# 5. 系统价值结果

以下标签来自反事实干预或其预测，不是静态缺陷。

## V1. NON_CONTRIBUTORY：无可观测贡献

\[
\Delta^{keep}\approx 0
\]

角色移除前后团队净效用无显著变化。它不代表角色设计一定有缺陷，可能是任务过于简单、聚合器未利用输出，或角色只提供安全冗余。

## V2. COUNTERPRODUCTIVE：有害

\[
\Delta^{keep}<0
\]

移除角色后团队更好。可能来自错误意见、成本、延迟或协议干扰。

## V3. REPAIRABLE：可修复

至少一个指定修复候选具有可靠正修复价值：

\[
LCB(\Delta^{repair})>\tau
\]

## V4. UNREPAIRABLE_UNDER_ACTION_SPACE：当前动作空间内不可修复

所有允许的修复候选收益均不可靠或非正。必须写成“在当前候选和允许动作空间下不可修复”，不能声称绝对不可修复。

## V5. COST_INEFFECTIVE：成本无效

任务效用有小幅提升，但不足以覆盖审计、推理、延迟或资源成本。

---

# 6. 缺陷与动作的非确定性映射

| 缺陷 | 可能 KEEP | 可能 REWRITE | 可能 REMOVE |
|---|---:|---:|---:|
| UNDERSPECIFICATION | 是 | 是 | 少见 |
| INTERNAL_CONFLICT | 少见 | 是 | 是 |
| OVERLOAD | 是 | 是 | 是 |
| CAPABILITY_MISMATCH | 是 | 有限 | 是 |
| TASK_IRRELEVANCE | 是 | 是 | 是 |
| REDUNDANCY | 是 | 是 | 是 |
| AUTHORITY_CONFLICT | 是 | 是 | 是 |
| DEPENDENCY_GAP | 是 | 有限 | 是 |
| PROTOCOL_MISMATCH | 是 | 是 | 是 |
| COVERAGE_GAP | 不适用 | 有限 | 不适用 |

最终动作由价值与不确定性决定，而不是由该表自动决定。

---

# 7. 标注记录模板

```yaml
role_id: verifier
defects:
  - defect_type: UNDERSPECIFICATION
    probability: 0.83
    severity: 3
    affected_fields:
      - responsibilities
      - outputs
    evidence:
      - "Prompt only says 'Check the answer carefully.'"
    confidence: 0.88
  - defect_type: PROTOCOL_MISMATCH
    probability: 0.72
    severity: 3
    affected_fields:
      - outputs
      - authority_level
    evidence:
      - "Aggregator expects verdict JSON, role outputs free text."
    confidence: 0.80
value_status:
  observed_or_predicted: predicted
  keep_value: -0.04
  uncertainty: 0.09
recommended_action: KEEP
action_reason: "Evidence of harm is insufficient under conservative threshold."
```

---

# 8. 分类规范的边界

本分类不包含单次事实错误、单条推理步骤错误、工具调用的具体运行时异常、恶意 Prompt Injection、内存污染、长轨迹中的责任步骤、基础模型所有能力维度或完整工作流拓扑缺陷。这些问题可与 RoleCheck 关联，但不是第一版角色缺陷本体。
