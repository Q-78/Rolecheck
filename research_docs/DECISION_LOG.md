# RoleCheck 决策日志

**版本：** v0.1  
**日期：** 2026-08-02  
**状态：** Research Freeze

本日志记录会改变研究问题、动作空间、标签、信息边界或论文主张的决定。已冻结决定不得通过代码实现被隐式修改；若需变更，必须新增决策记录，而不是覆盖原记录。

## 状态定义

- `FROZEN`：第一版硬约束；
- `PROVISIONAL`：可在预实验后调整；
- `REJECTED`：已讨论但不采用；
- `SUPERSEDED`：被后续决策明确替代。

## 决策总览

| ID | 决策 | 状态 | 生效版本 |
|---|---|---|---|
| D-001 | 主任务是角色保留价值预测 | FROZEN | v0.2 |
| D-002 | 效用、成本、延迟分开建模 | FROZEN | v0.2 |
| D-003 | Strict 为主设置，Probe-assisted 为增强设置 | FROZEN | v0.2 |
| D-004 | 第一版仅修改角色合同/Prompt 与成员资格 | FROZEN | v0.2 |
| D-005 | 移除必须遵循预定义协议 | FROZEN | v0.2 |
| D-006 | Coverage Gap 独立建模 | FROZEN | v0.2 |
| D-007 | 每角色最多三个操作性不同的修复候选 | FROZEN | v0.2 |
| D-008 | Adapter 与核心审计逻辑分离 | FROZEN | v0.2 |
| D-009 | 三类不确定性分开表示 | FROZEN | v0.2 |
| D-010 | 第一版每轮最多干预一个角色 | FROZEN | v0.2 |
| D-011 | 当前阶段不实现真实实验逻辑 | FROZEN | repo-init |

---

## D-001：主任务是角色保留价值预测

- **状态：** FROZEN
- **决定：** 主任务为当前任务执行前的 `Keep Value` 预测；第二任务为有限修复候选价值排序；缺陷诊断只用于解释、特征与候选生成。
- **理由：** “角色是否有缺陷”与“保留该角色是否增加团队效用”不是同一问题；论文的核心科学价值应落在团队条件、协议条件的价值预测上。
- **排除方案：** 以缺陷分类准确率作为论文主目标；以自动 Prompt 重写作为第一主任务。
- **影响：** Benchmark、标签、基线和 Gate 2 均围绕保留价值设计。

## D-002：效用、成本、延迟分开建模

- **状态：** FROZEN
- **决定：** 分别记录和预测 `ΔU`、`ΔCost`、`ΔLatency`，只在决策层组合。
- **理由：** 不同实验和部署场景的预算偏好不同，提前合并会掩盖任务性能与系统成本的权衡。
- **排除方案：** 单一加权净效用标签。
- **影响：** Schema 和 Manifest 必须保留三个独立字段。

## D-003：Strict 为主设置

- **状态：** FROZEN
- **决定：** `Strict Task-Level Pre-Execution` 是主设置；`Probe-Assisted Pre-Deployment` 是增强设置。
- **Strict 禁止信息：** 当前任务角色输出、完整执行结果、Gold、当前任务移除/修复结果、当前任务轨迹。
- **Probe 额外允许：** 独立校准任务上的历史能力、格式遵循、共失败、历史贡献、Token 与延迟画像。
- **影响：** 任何特征管线必须标注来源；泄漏检查是正式实验的前置条件。

## D-004：第一版动作空间受限

- **状态：** FROZEN
- **决定：** 单角色动作仅为 `KEEP / REWRITE / REMOVE`。REWRITE 只允许修改角色合同及其序列化 Prompt；REMOVE 只改变成员资格。
- **禁止：** 更换模型、增删工具、改拓扑、改执行轮次、改聚合协议、改停止规则、新增角色。
- **影响：** `RepairCandidate` 必须保存 changed/preserved fields，并通过 forbidden-scope 校验。

## D-005：移除协议预定义

- **状态：** FROZEN
- **决定：** 并行独立团队使用 response-drop + fixed-other-responses + re-aggregation；顺序 DAG 只允许 schema-preserving bypass。
- **不可移除：** 最终聚合器、唯一裁决者、不可逆转换节点、移除后产生 Coverage Gap 的角色、下游依赖专属产物的角色。
- **影响：** 不可安全旁路时 `ABSTAIN=true` 且外部动作保持 `KEEP`。

## D-006：Coverage Gap 独立建模

- **状态：** FROZEN
- **决定：** Coverage Gap 是团队级风险，不等同于某个角色缺陷，也不自动触发新增角色。
- **影响：** 它可阻止 REMOVE、提高不确定性并生成非执行建议。

## D-007：修复候选最多三个

- **状态：** FROZEN
- **决定：** 每个角色最多三个修复候选；候选不包含 KEEP/REMOVE，且必须在操作类型、字段、边界、接口或关注范围上有实质差异。
- **影响：** `RoleAuditReport` 对候选数量进行 Schema 校验。

## D-008：Adapter 边界

- **状态：** FROZEN
- **决定：** Adapter 只做框架字段映射、抽取、声明、缺失标记和序列化回写；不得承载专用缺陷规则、价值阈值或测试集特化逻辑。
- **影响：** 核心 Schema、Auditor、Predictor、Taxonomy 和 Policy 必须位于框架无关包中。

## D-009：三类不确定性分开表示

- **状态：** FROZEN
- **决定：** 分开记录 `model_uncertainty`、`ood_risk`、`contract_parse_risk`。
- **理由：** 三者语义和应对策略不同，不能相加为不透明总分。
- **影响：** 高 OOD 或高合同解析风险必须支持 abstention。

## D-010：第一版单角色干预

- **状态：** FROZEN
- **决定：** 可同时审计多个角色，但每轮最多干预一个角色，之后必须重新审计。
- **影响：** 强耦合问题标记 `joint_intervention_required=true`；第一版不估计联合干预收益。

## D-011：仓库初始化阶段不实现真实实验逻辑

- **状态：** FROZEN
- **决定：** 当前仓库只包含规范、Schema、配置、日志、Manifest、Mock Runtime 和测试。
- **禁止：** 真实模型调用、Benchmark 下载、缺陷注入、Keep/Repair Predictor、修复器、AgentInit 适配、旧实验逻辑迁移。
- **退出条件：** 基础仓库通过 `ruff`、`mypy`、`pytest` 后，进入“受控执行协议 + Role Contract Normalizer”阶段。

---

## 决策变更模板

```text
ID:
日期:
状态:
变更内容:
触发证据:
替代方案:
对标签/实验/主张/代码的影响:
迁移计划:
批准人:
```
