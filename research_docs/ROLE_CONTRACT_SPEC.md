# Role Contract 规范

**项目：** RoleCheck  
**版本：** v0.1  
**日期：** 2026-08-01

---

# 1. 目的

Role Contract 是 RoleCheck 的统一中间表示，用于把不同 MAS 初始化器和运行时中的自然语言角色、Agent 配置和工作流节点转换成可审计、可比较、可修改的结构化对象。

Role Contract 必须支持三个目标：

1. **语义保真：**保留原初始化器对角色的显式设定；
2. **框架无关：**隔离框架专用字段，使核心审计器不依赖某个运行时；
3. **可干预：**能够描述角色修复、移除和版本变化。

Role Contract 不是“更好的 Prompt”，归一化阶段不得自动优化原角色。

---

# 2. 设计原则

## 2.1 原始信息与推断信息分离

每个结构化字段必须标记来源：

- `explicit`：原配置明确给出；
- `parsed`：由确定性规则解析；
- `inferred`：由模型推断；
- `defaulted`：由适配器填入默认值；
- `unknown`：无法确定。

审计器不得把低置信推断字段当作确定事实。

## 2.2 角色与 Agent 实例分离

- `RoleContract`：职责、接口和权限规范；
- `AgentInstance`：具体模型、工具、采样参数和运行状态。

同一 Role Contract 可以绑定不同模型，产生不同 Agent 实例。角色设计缺陷和模型能力限制必须可区分。

## 2.3 角色级与团队级信息分离

角色合同描述单个角色；角色间依赖、拓扑和聚合协议由 Team Contract 描述，避免将团队逻辑重复写入每个角色。

## 2.4 可版本化和可回滚

任何修改都必须产生新版本，不覆盖原角色。每个版本保存：父版本、修改原因、缺陷标签、修改差异、生成器、时间和配置哈希。

---

# 3. RoleContract 核心字段

## 3.1 身份字段

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `role_id` | string | 是 | 团队内稳定唯一标识 |
| `role_name` | string | 是 | 人类可读角色名 |
| `role_version` | string | 是 | 角色合同版本 |
| `source_initializer` | string | 是 | 来源初始化器或人工模板 |
| `source_node_id` | string/null | 否 | 原工作流节点标识 |
| `raw_prompt` | string | 是 | 原始系统 Prompt，不得丢失 |
| `prompt_hash` | string | 是 | Prompt 内容哈希 |

## 3.2 目标与职责

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `goal` | string | 是 | 角色对团队的主要目标 |
| `responsibilities` | list[string] | 是 | 可观察、可执行的职责 |
| `success_criteria` | list[string] | 否 | 判断角色完成职责的标准 |
| `non_goals` | list[string] | 否 | 明确不负责的事项 |
| `prohibited_behaviors` | list[string] | 否 | 禁止行为 |
| `priority_rules` | list[string] | 否 | 多目标冲突时的优先级 |

职责应尽量使用动词和可验证对象，例如：

- “独立复算候选答案”；
- “定位首个不成立的推理步骤”；
- “输出结构化 verdict 和 corrected_answer”。

不推荐：“要聪明”“认真工作”“尽可能帮助团队”。

## 3.3 输入合同

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `required_inputs` | list[InputSpec] | 是 | 缺失则角色无法正常执行 |
| `optional_inputs` | list[InputSpec] | 否 | 有则使用、无则可继续 |
| `input_visibility` | enum | 是 | private/shared/upstream-only/global |
| `context_assumptions` | list[string] | 否 | 对输入完整性和格式的假设 |

`InputSpec` 示例：

```json
{
  "name": "candidate_solution",
  "semantic_type": "natural_language_solution",
  "producer_role_id": "solver",
  "required": true,
  "format": "plain_text",
  "schema_ref": null,
  "description": "Solver 提供的候选推理和最终答案"
}
```

## 3.4 输出合同

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `outputs` | list[OutputSpec] | 是 | 角色产生的可消费输出 |
| `output_visibility` | enum | 是 | private/shared/downstream-only/global |
| `failure_output` | OutputSpec/null | 否 | 无法完成职责时的显式输出 |
| `format_strictness` | enum | 是 | strict/preferred/freeform |

`OutputSpec` 示例：

```json
{
  "name": "verification_report",
  "semantic_type": "verdict_with_correction",
  "consumers": ["aggregator"],
  "format": "json",
  "schema_ref": "schemas/verifier_report_v1.json",
  "required_fields": ["verdict", "error_location", "corrected_answer"],
  "description": "供聚合器直接读取的验证结果"
}
```

## 3.5 权限与决策边界

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `authority_level` | enum | 是 | advisory/voting/veto/final/execution |
| `can_override` | list[string] | 否 | 可覆盖哪些角色或决定 |
| `requires_approval_from` | list[string] | 否 | 动作需哪些角色批准 |
| `decision_scope` | list[string] | 否 | 权限只适用于哪些事项 |
| `conflict_resolution_rule` | string/null | 否 | 与其他角色冲突时如何处理 |

权限必须与协议一致。一个 Prompt 声称拥有最终裁决权，而聚合器只进行多数投票，应被标记为潜在协议不匹配。

## 3.6 依赖与交互

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `upstream_dependencies` | list[DependencySpec] | 否 | 依赖哪些角色和数据 |
| `downstream_consumers` | list[string] | 否 | 输出供哪些角色消费 |
| `interaction_mode` | enum | 是 | independent/sequential/debate/review/tool-mediated |
| `max_interaction_rounds` | int/null | 否 | 角色可参与的最大轮次 |
| `termination_signal` | string/null | 否 | 角色发出的终止信号 |
| `handoff_conditions` | list[string] | 否 | 何时转交下游 |

`DependencySpec` 示例：

```json
{
  "role_id": "solver",
  "artifact": "candidate_solution",
  "required": true,
  "timing": "before_execution",
  "fallback": null
}
```

## 3.7 能力、模型和工具上下文

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `model_id` | string | 是 | 绑定基础模型 |
| `model_capability_tags` | list[string] | 否 | 已知或历史能力标签 |
| `tool_ids` | list[string] | 否 | 可用工具 |
| `required_capabilities` | list[string] | 否 | 履职所需能力 |
| `resource_limits` | object | 否 | Token、时间和工具预算 |
| `sampling_config_ref` | string/null | 否 | 采样配置引用 |

该部分用于区分角色规范设计问题、模型能力不匹配、工具缺失和资源限制。

## 3.8 来源与置信度

每个可推断字段支持：

```json
{
  "value": ["independently verify the proposed solution"],
  "source_type": "inferred",
  "source_span": "Check the answer carefully.",
  "confidence": 0.71,
  "extractor": "contract_parser_v1"
}
```

在实现中可采用字段值与 provenance 分离的双表结构，避免 Schema 过度嵌套。

---

# 4. TeamContract 核心字段

RoleCheck 还需要团队级合同：

```json
{
  "team_id": "team_001",
  "task_scope": "mathematical_reasoning",
  "roles": ["solver", "critic", "verifier"],
  "edges": [
    {"from": "solver", "to": "critic", "artifact": "candidate_solution"},
    {"from": "critic", "to": "verifier", "artifact": "reviewed_solution"}
  ],
  "execution_order": ["solver", "critic", "verifier", "aggregator"],
  "communication_protocol": "sequential",
  "aggregation_protocol": "verifier_advisory_then_vote",
  "termination_protocol": "fixed_rounds",
  "removal_protocol": "bypass_single_node",
  "global_constraints": {"max_tokens": null, "max_latency_ms": null}
}
```

必须显式包含节点和边、数据或消息类型、执行顺序、聚合与权限、移除角色时的图修复规则，以及角色输出被谁消费。

---

# 5. 规范化流程

```text
Raw Initializer Output
    ↓
Framework Adapter
    ↓
Raw Team Snapshot
    ↓
Deterministic Parsing
    ↓
LLM-Assisted Structured Extraction（可选）
    ↓
Schema Validation
    ↓
Cross-Contract Consistency Check
    ↓
Canonical RoleContract + TeamContract
```

## 5.1 不得在规范化阶段执行的操作

- 不得重写 Prompt；
- 不得添加职责；
- 不得移除角色；
- 不得根据性能修改合同；
- 不得把审计判断写回原合同；
- 不得隐藏未知或矛盾字段。

## 5.2 规范化失败

若必需字段无法确定，应标记 `unknown`、保留原始内容、输出解析置信度、允许审计器 abstain，并且不得凭空补全后当作显式设计。

---

# 6. 合同一致性检查

## 6.1 角色内检查

- goal 与 responsibilities 是否矛盾；
- required_inputs 是否有定义；
- outputs 是否满足 success_criteria；
- authority 是否过宽；
- prohibited_behaviors 与职责是否冲突；
- required_capabilities 是否与 model/tools 匹配。

## 6.2 角色间检查

- 每个 required input 是否有生产者；
- 输出格式与消费者输入格式是否兼容；
- 上游是否在下游之前执行；
- 是否存在无法满足的循环依赖；
- 多个角色是否拥有冲突的 final/veto 权限；
- 聚合器是否读取角色关键输出；
- 角色移除后是否有明确旁路或失败策略。

---

# 7. 修复版本规范

修复候选不得只保存新的 Prompt。必须保存：

```json
{
  "repair_id": "repair_001",
  "target_role_id": "verifier",
  "parent_role_version": "v1",
  "new_role_version": "v1-r1",
  "target_defects": ["underspecification", "protocol_mismatch"],
  "changed_fields": ["responsibilities", "outputs", "raw_prompt"],
  "preserved_fields": ["goal", "authority_level", "model_id", "tool_ids"],
  "edit_rationale": "补全独立验证职责并输出聚合器可消费的结构化字段",
  "generator_id": "defect_repairer_v1",
  "candidate_rank_before_value_prediction": 2,
  "contract_diff": {}
}
```

修复候选必须通过 Schema 验证、团队接口兼容检查、权限一致性检查、禁止范围检查和版本完整性检查。

---

# 8. 完整示例

```json
{
  "role_id": "verifier",
  "role_name": "Independent Verifier",
  "role_version": "v1",
  "source_initializer": "initializer_A",
  "source_node_id": "node_3",
  "raw_prompt": "Check the answer carefully.",
  "prompt_hash": "sha256:...",
  "goal": "Detect errors in the candidate solution before aggregation.",
  "responsibilities": [
    "Independently recompute the key result.",
    "Identify the earliest unsupported or incorrect step.",
    "Return a corrected answer when the candidate is invalid."
  ],
  "success_criteria": [
    "A verdict is returned.",
    "The corrected answer is machine-readable when the verdict is incorrect."
  ],
  "non_goals": [
    "Do not generate the initial solution.",
    "Do not decide the final team answer alone."
  ],
  "prohibited_behaviors": ["Do not merely repeat the solver reasoning."],
  "priority_rules": ["Correctness has priority over agreement with the solver."],
  "required_inputs": [
    {
      "name": "task",
      "semantic_type": "task_specification",
      "producer_role_id": null,
      "required": true,
      "format": "plain_text"
    },
    {
      "name": "candidate_solution",
      "semantic_type": "reasoned_answer",
      "producer_role_id": "solver",
      "required": true,
      "format": "plain_text"
    }
  ],
  "optional_inputs": [],
  "input_visibility": "upstream-only",
  "outputs": [
    {
      "name": "verification_report",
      "semantic_type": "verdict_with_correction",
      "consumers": ["aggregator"],
      "format": "json",
      "schema_ref": "verifier_report_v1",
      "required_fields": ["verdict", "error_location", "corrected_answer"]
    }
  ],
  "output_visibility": "downstream-only",
  "format_strictness": "strict",
  "authority_level": "advisory",
  "can_override": [],
  "requires_approval_from": [],
  "decision_scope": ["solution_validity"],
  "upstream_dependencies": [
    {
      "role_id": "solver",
      "artifact": "candidate_solution",
      "required": true,
      "timing": "before_execution"
    }
  ],
  "downstream_consumers": ["aggregator"],
  "interaction_mode": "review",
  "model_id": "model_x",
  "model_capability_tags": ["reasoning"],
  "tool_ids": [],
  "required_capabilities": ["independent_reasoning", "error_detection"],
  "resource_limits": {"max_output_tokens": 1024}
}
```

---

# 9. 最小验证规则

一个合同至少需要满足：

1. `role_id` 唯一；
2. `raw_prompt` 可追溯；
3. `goal` 非空；
4. 至少一个 responsibility；
5. required input 有定义；
6. 至少一个 output；
7. authority 为合法枚举；
8. dependencies 指向存在角色；
9. model_id 存在；
10. prompt_hash 与内容一致；
11. 所有推断字段带 provenance；
12. 修改版本可回滚。

---

# 10. 非目标

本规范不定义 Prompt 的最佳写法、基础模型能力评测方法、通用工具协议、所有 MAS 框架的完整抽象、严格形式化的软件类型系统或最终实验数据格式。它只定义 RoleCheck 所需的最小、可扩展审计接口。
