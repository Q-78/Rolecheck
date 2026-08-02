# RoleCheck 方法蓝图

**版本：** v0.1  
**日期：** 2026-08-01  
**性质：** 模块、接口、信息流与决策逻辑设计；不规定具体模型、数据集或代码框架。

---

# 1. 总体架构

```text
Task x
  +
Initializer Output C_raw
  +
Runtime/Protocol Metadata
        │
        ▼
┌─────────────────────────────┐
│ 1. Initializer Adapter      │
│ 框架专用输出 → 统一团队快照 │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 2. Role Contract Normalizer │
│ 角色 Prompt → 结构化合同    │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 3. Contract & Graph Auditor │
│ 内在/关系/协议缺陷诊断      │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 4. Keep-Value Predictor     │
│ Δ_keep, uncertainty, harm   │
└──────────────┬──────────────┘
               │
       suspicious / low-value roles
               ▼
┌─────────────────────────────┐
│ 5. Repair Candidate Generator│
│ 缺陷条件化有限候选          │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 6. Repair-Value Predictor   │
│ 每个候选 Δ_repair, σ        │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 7. Conservative Policy      │
│ KEEP / REWRITE / REMOVE     │
│ or ABSTAIN→KEEP             │
└──────────────┬──────────────┘
               ▼
        Revised Team C'
               │
               ▼
       Original MAS Runtime
```

---

# 2. 系统边界

## 2.1 RoleCheck 负责

- 读取任务和初始化团队；
- 角色合同归一化；
- 合同与团队关系审计；
- 预测角色保留价值；
- 生成有限修复候选；
- 预测修复候选价值；
- 选择最小干预；
- 输出审计报告和兼容团队配置。

## 2.2 RoleCheck 不负责

第一版不负责：

- 从零生成完整团队；
- 选择基础模型；
- 新增工具；
- 搜索拓扑；
- 训练完整 Agent 策略；
- 修改聚合器；
- 定位当前任务执行后的错误步骤；
- 自动证明严格因果效应。

---

# 3. 核心数据对象

## 3.1 TaskSpec

```yaml
task_id: string
task_text: string
task_type: string|null
public_metadata: object
sensitive_fields: []
```

当前任务执行前预测只允许使用公开字段。

## 3.2 CanonicalTeamConfig

```yaml
team_id: string
roles: [RoleContract]
edges: [CommunicationEdge]
execution_protocol: ExecutionProtocol
aggregation_protocol: AggregationProtocol
removal_protocol: RemovalProtocol
resource_constraints: object
source_initializer: string
```

## 3.3 RoleAuditReport

```yaml
role_id: string
contract_quality:
  parse_confidence: float
  missing_fields: [string]
defects:
  defect_type: probability
predicted_keep_value: float
keep_uncertainty: float
harmful_probability: float
repair_candidates: [RepairCandidateReport]
recommended_action: KEEP|REWRITE|REMOVE
abstained: bool
evidence: [string]
limitations: [string]
```

## 3.4 RepairCandidateReport

```yaml
repair_id: string
candidate_contract: RoleContract
target_defects: [string]
contract_diff: object
predicted_repair_value: float
repair_uncertainty: float
estimated_audit_and_runtime_cost: float
compatibility_passed: bool
```

---

# 4. 模块一：Initializer Adapter

## 4.1 目标

将不同初始化器导出的角色列表、Prompt、模型映射、工具、工作流节点、边、执行顺序和聚合方式转换为统一 `CanonicalTeamConfig`。

## 4.2 接口

\[
Adapter_k(C_{raw})\rightarrow (C_{canonical},W)
\]

其中 \(W\) 是警告列表：字段缺失、协议不可表达、适配器使用默认值，以及某些运行时语义不能保真映射。

## 4.3 不变量

- 不优化原角色；
- 不猜测无法确定的拓扑；
- 不吞掉未知字段；
- 原始配置可追溯；
- 所有默认值显式记录。

---

# 5. 模块二：Role Contract Normalizer

## 5.1 输入

- 原始系统 Prompt；
- 角色名；
- 框架配置；
- 工作流位置；
- 模型与工具元数据。

## 5.2 输出

统一合同字段：goal、responsibilities、inputs、outputs、authority、dependencies、non-goals、prohibited behavior 和 required capabilities。

## 5.3 两阶段解析

```text
Deterministic Parser
    ↓
未覆盖或歧义字段
    ↓
Structured LLM Extractor（可选）
    ↓
Schema Validator
```

## 5.4 置信与拒绝

若关键字段低置信：

- 不得激进修复；
- 缺陷审计中提高不确定性；
- 允许输出 `CONTRACT_INCOMPLETE` 警告；
- 策略默认 KEEP。

---

# 6. 模块三：Static Defect Auditor

## 6.1 任务需求表示

\[
Req(x)=\{q_1,\ldots,q_m\}
\]

每个需求包括所需职责、产物、验证要求、工具或能力，以及前后依赖。

## 6.2 角色自身特征

- 合同完整度；
- 内部矛盾；
- 职责数量与异质性；
- 输入/输出明确度；
- 能力匹配；
- 权限范围。

## 6.3 团队关系特征

- 职责相似；
- 输入输出兼容；
- 权限冲突；
- 依赖可达性；
- 团队覆盖；
- 角色输出到最终决策的路径；
- 模型与工具多样性。

## 6.4 输出

\[
d_i=[P(D_1),\ldots,P(D_K)]
\]

同时输出字段证据、图结构证据、语义证据和未知项。缺陷概率不能直接变成干预动作。

---

# 7. 模块四：Keep-Value Predictor

## 7.1 目标

\[
f_{keep}:(x,C,r_i,\pi,H)\mapsto(\widehat{\Delta}^{keep}_i,\sigma_i,p_i^{harm})
\]

## 7.2 允许信息

Strict 模式：任务文本、角色合同、团队结构、模型/工具元数据、协议和训练数据统计。

Probe-assisted 模式额外允许：独立校准任务上的角色画像、历史贡献、历史错误重合和历史成本。

## 7.3 禁止信息

- 当前任务上的角色输出；
- 当前任务真实团队效用；
- 当前任务 Gold；
- 当前任务实际移除结果；
- 当前任务修复结果。

## 7.4 输出语义

- `predicted_keep_value`：净效用差的点估计；
- `keep_uncertainty`：模型对该估计的不确定程度；
- `harmful_probability`：保留价值为负的概率；
- `out_of_support`：输入是否远离训练分布。

## 7.5 不确定性不等于装饰

不确定性必须能够驱动 abstention、风险阈值、低覆盖高可靠模式和未见初始化器的保守行为。

---

# 8. 模块五：Defect-Conditioned Repair Candidate Generator

## 8.1 候选生成原则

对每个角色只生成有限集合：

\[
\mathcal R_i=\{r'_{i1},\ldots,r'_{iK}\}
\]

候选类型应与缺陷对应。

## 8.2 修复操作原语

### 补全

- 明确职责；
- 明确输入；
- 明确输出；
- 明确成功标准。

### 去重

- 引入不同方法；
- 指定独特关注点；
- 禁止重复已有成员推理。

### 消冲突

- 明确优先级；
- 收缩权限；
- 指定冲突解决规则。

### 接口对齐

- 修改输出格式；
- 增加必要字段；
- 明确消费者。

### 收缩

- 删除非核心职责；
- 明确 non-goals；
- 降低过载。

第一版不自动执行换模型、加工具、改拓扑或新增角色。

## 8.3 候选质量门

候选进入价值预测前必须：

- 合同合法；
- 接口兼容；
- 未越权修改；
- 不引入新缺陷；
- 保留未受影响目标；
- 有清晰 diff。

---

# 9. 模块六：Repair-Value Predictor

## 9.1 接口

\[
f_{repair}:(x,C,r_i,r'_{ik},\pi,H)\mapsto(\widehat{\Delta}^{repair}_{ik},\sigma_{ik})
\]

## 9.2 候选特征

除 Keep Predictor 信息外，可使用：

- 修改字段；
- 缺陷—修复匹配；
- 职责变化；
- 接口兼容变化；
- 语义编辑幅度；
- 预计输出长度变化；
- 预计角色遵循变化；
- 历史同类修复效果。

## 9.3 必须区分

- 候选质量；
- 候选价值；
- 预测置信。

一个写得更清楚的 Prompt 不一定提高团队效用。

---

# 10. 模块七：Conservative Intervention Policy

## 10.1 候选净保守收益

\[
Score_{ik}^{rewrite}=\widehat{\Delta}_{ik}^{repair}-\beta\sigma_{ik}^{repair}-\lambda_c Cost_{ik}^{repair}-\lambda_e EditPenalty_{ik}
\]

## 10.2 移除条件

\[
UCB_i^{keep}=\widehat{\Delta}_i^{keep}+\beta\sigma_i^{keep}
\]

仅当：

\[
UCB_i^{keep}< -\tau_{remove}
\]

且移除后合同与依赖仍可执行，才可 REMOVE。

## 10.3 重写条件

若：

\[
\max_k Score_{ik}^{rewrite}>\tau_{rewrite}
\]

且候选兼容，则选择最佳候选 REWRITE。

## 10.4 默认策略

其余情况 KEEP。若输入超出支持范围、合同不完整或多个强耦合角色同时异常：

```text
ABSTAIN = true
ACTION = KEEP
```

ABSTAIN 是策略状态，不一定是第四个外部动作。

---

# 11. 多角色耦合处理

第一版以单角色干预为基本单位。对于以下情况必须 abstain 或标记扩展：

- 两个角色职责互相定义；
- 同时修改才可能改善；
- 移除一个会使另一个失效；
- 多个角色共享同一最终权限；
- 团队覆盖缺口需要新增角色。

禁止将多角色联合变化的收益归因于某一个角色。

---

# 12. 审计报告示例

```json
{
  "team_id": "team_001",
  "role_id": "verifier",
  "contract_parse_confidence": 0.94,
  "defect_probabilities": {
    "UNDERSPECIFICATION": 0.81,
    "REDUNDANCY": 0.58,
    "PROTOCOL_MISMATCH": 0.76
  },
  "predicted_keep_value": -0.03,
  "keep_uncertainty": 0.11,
  "harmful_probability": 0.61,
  "repair_candidates": [
    {
      "repair_id": "r1",
      "target_defects": ["UNDERSPECIFICATION", "PROTOCOL_MISMATCH"],
      "predicted_repair_value": 0.17,
      "repair_uncertainty": 0.04,
      "estimated_cost": 0.02,
      "compatibility_passed": true
    },
    {
      "repair_id": "r2",
      "target_defects": ["REDUNDANCY"],
      "predicted_repair_value": 0.09,
      "repair_uncertainty": 0.12,
      "estimated_cost": 0.01,
      "compatibility_passed": true
    }
  ],
  "recommended_action": "REWRITE",
  "selected_repair_id": "r1",
  "abstained": false,
  "explanation": [
    "The current output is not consumable by the aggregator.",
    "Candidate r1 has the highest positive conservative repair value."
  ],
  "limitations": [
    "Prediction is conditioned on the declared aggregation protocol."
  ]
}
```

---

# 13. 方法不变量

任何具体实现都必须保持：

1. 当前任务输出不可泄漏到执行前预测；
2. 缺陷诊断不直接替代价值预测；
3. 修复价值绑定具体候选；
4. 高不确定性默认不修改；
5. 原合同可追溯和回滚；
6. 不修改超出动作空间的配置；
7. 插件特有逻辑与框架 Adapter 分离；
8. 移除协议预先定义；
9. 价值始终注明任务、团队和协议条件；
10. 所有成本可计量。

---

# 14. 可能的简化版本

## Core-A：仅保留价值预测

```text
Role Contract
→ Defect Features
→ Keep-Value Prediction
→ KEEP/REMOVE
```

这是最小且完整的核心科学问题。

## Core-B：保留价值 + 修复候选排序

```text
Core-A
→ 规则生成有限修复候选
→ Repair-Value Ranking
→ KEEP/REWRITE/REMOVE
```

## Full：可插拔审计与最小修复

```text
多个 Initializer Adapter
→ 完整 RoleCheck
→ 跨系统复用
```

论文推进时应先保证 Core-A 成立，再增加 Core-B 和 Full。
