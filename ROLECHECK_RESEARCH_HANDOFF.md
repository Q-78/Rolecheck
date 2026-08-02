# RoleCheck 研究项目交接与后续对话上下文

**项目暂定名称：** RoleCheck  
**暂定英文题目：** *RoleCheck: Plug-and-Play Multi-Agent Initialization Auditing and Minimal Repair via Counterfactual Role-Value Prediction*  
**中文题目：** 基于反事实角色价值预测的可插拔 LLM 多智能体初始化审计与最小修复  
**整理日期：** 2026-08-01  
**用途：** 用于开启新聊天、向导师汇报、继续制定实验方案、指导 Codex 开发以及后续论文研究。

---

# 0. 新聊天使用说明

在新聊天中上传本文件，并输入：

> 请阅读这份 RoleCheck 项目交接文档。它记录了我当前已经冻结的课题方向、十项研究决策、方法框架和 16 周研究计划。请以此为唯一当前版本，不要回退到旧的“预算约束团队选择”方向。先总结你理解的研究问题、核心贡献和当前下一步，再继续回答我的问题。

如需让 Codex 开始搭建项目，可直接使用本文件第 15 节的第一阶段指令。

---

# 1. 课题演变与当前最终聚焦

## 1.1 最初方向

最初课题聚焦于：

> 在候选 Agent 尚未执行时，预测它加入当前团队后的边际增益，并在预算约束下决定是否加入。

核心公式为：

\[
\Delta(a\mid x,S,\pi)
=
U(x,S\cup\{a\},\pi)-U(x,S,\pi)
\]

该方向强调：

- 执行前预测；
- 任务条件；
- 当前团队条件；
- 聚合协议条件；
- 校准不确定性；
- 预算约束团队选择。

## 1.2 调整后的方向

后来将课题重新聚焦为“角色入职体检”：

> 已有初始化器负责生成团队和角色；RoleCheck 位于初始化器和执行框架之间，对已生成角色进行审计，预测每个角色是否值得保留、是否值得修复，并以最小干预方式选择 KEEP、REWRITE 或 REMOVE。

原来的反事实增益预测没有被删除，而是升级为新课题的核心算法：

- 从“候选 Agent 是否值得加入”；
- 转变为“已初始化角色是否值得保留”；
- 进一步扩展为“指定修复候选是否值得采用”。

## 1.3 当前冻结的一句话定义

> RoleCheck 是一个位于 MAS 初始化器与执行框架之间的角色审计层：它将不同初始化器生成的角色归一化为统一合同，在当前任务完整执行前，预测角色相对于当前任务、团队和协议的操作性反事实保留价值及有限修复候选价值，并通过不确定性感知的最小干预策略选择保留、重写或移除。

---

# 2. 研究对象与严格定义

## 2.1 初始化器

设已有初始化器为：

\[
\mathcal I(x)\rightarrow C
\]

其中：

- \(x\)：任务实例或任务描述；
- \(C\)：初始化后的团队配置。

RoleCheck 不替代初始化器，只审计其输出。

## 2.2 团队配置

团队定义为：

\[
C=(A,R,M,T,G,\pi)
\]

其中：

- \(A\)：Agent 实例集合；
- \(R\)：角色合同；
- \(M\)：基础模型配置；
- \(T\)：工具与权限；
- \(G\)：通信和依赖结构；
- \(\pi\)：执行、通信、聚合和停止协议。

第一版只允许修改角色合同和角色是否保留，但模型、工具、拓扑和协议必须作为上下文，因为角色价值依赖它们。

## 2.3 角色定义

角色不是角色名或一句 Prompt，而是：

\[
r_i=
(
name_i,
goal_i,
responsibilities_i,
prompt_i,
inputs_i,
outputs_i,
authority_i,
dependencies_i,
model_i,
tools_i
)
\]

角色质量不是固有属性：

\[
Q(r_i)
\]

而是关系属性：

\[
Q(r_i\mid x,C_{-i},\pi)
\]

同一个 Verifier 在不同任务、团队成员和聚合协议中可能具有完全不同的价值。

---

# 3. 两类操作性反事实价值

## 3.1 角色保留价值：主任务

对于团队中的角色 \(a_i\)：

\[
\Delta_i^{keep}
=
U(x,C,\pi)
-
U(x,C\setminus\{a_i\},\pi_{-i})
\]

它回答：

> 在预先定义的移除协议下，保留这个角色相比移除它，为团队带来了多少价值？

解释：

- \(\Delta_i^{keep}>0\)：角色有正贡献；
- \(\Delta_i^{keep}\approx0\)：角色可能冗余或当前任务未发挥作用；
- \(\Delta_i^{keep}<0\)：角色可能干扰团队或成本无效。

## 3.2 修复候选价值：第二任务

针对角色 \(r_i\) 的具体候选修复 \(r'_{ik}\)：

\[
\Delta_{ik}^{repair}
=
U(x,C_{i\leftarrow r'_{ik}},\pi)
-
U(x,C,\pi)
\]

它回答：

> 用这个具体修复版本替换原角色，是否会改善团队？

不能预测抽象的“修复后的价值”，必须绑定有限候选：

\[
\mathcal R_i=
\{r'_{i1},r'_{i2},r'_{i3}\}
\]

## 3.3 为什么称为“操作性反事实”

本课题不声称识别普遍因果效应，而是比较受控的可执行配置：

- 同一个任务；
- 同一个模型；
- 同一个工具集合；
- 同一个协议；
- 除目标角色干预外尽可能保持其他配置不变。

因此使用更稳妥的术语：

> Operational Counterfactual Role Value  
> 操作性反事实角色价值

---

# 4. 课题主次关系

必须始终保持以下主次：

## 核心算法贡献

**当前任务执行前的反事实角色保留价值预测。**

## 第二任务

**有限修复候选的价值预测与排序。**

## 辅助模块

**角色缺陷诊断。**

作用是：

- 解释角色为什么可能有问题；
- 提供价值预测特征；
- 生成定向修复候选。

缺陷概率不能直接等价于团队价值：

\[
DefectProbability\neq CounterfactualValue
\]

## 下游系统应用

**KEEP / REWRITE / REMOVE 的最小干预策略。**

---

# 5. 十项已经冻结的研究决策

## 决策 1：主任务

- 主任务：角色保留价值预测；
- 第二任务：修复候选价值排序；
- 推进顺序：先证明“谁值得保留”可预测，再研究“怎么修更好”。

## 决策 2：效用与成本

不把准确率、Token 和延迟一开始混成一个标签。

分别建模：

\[
\Delta U_i,\quad
\Delta Cost_i,\quad
\Delta Latency_i
\]

在决策层组合：

\[
Score_i
=
LCB(\Delta U_i)
-\lambda_c\Delta Cost_i
-\lambda_l\Delta Latency_i
\]

这样可以适配不同预算偏好。

## 决策 3：两种执行前设置

### 主设置：Strict Task-Level Pre-Execution

当前任务上禁止使用：

- 角色输出；
- 当前团队真实结果；
- Gold 答案；
- 当前任务移除结果；
- 当前任务修复结果；
- 当前任务执行轨迹。

### 增强设置：Probe-Assisted Pre-Deployment

可以使用独立校准任务上的：

- 历史能力；
- 格式遵循；
- 历史共失败；
- 历史贡献；
- Token 和延迟画像。

但仍不允许使用当前测试任务输出。

## 决策 4：允许修改的范围

允许修改：

- responsibilities；
- success criteria；
- non-goals；
- prohibited behaviors；
- 输入描述；
- 输出字段和格式；
- 对应的自然语言 Prompt。

不允许修改：

- 基础模型；
- 工具集合；
- 通信拓扑；
- 执行轮次；
- 聚合协议；
- 全局停止规则；
- 团队中新增角色。

Role Contract 是事实来源，Prompt 是序列化形式。

## 决策 5：移除协议

### 并行独立团队

- 删除该角色响应；
- 固定其他响应；
- 按预定义规则重新聚合。

### 顺序 DAG

只允许 **Schema-preserving bypass**：

- 上游输出可直接被下游消费；
- 不生成补偿消息；
- 不修改其他角色 Prompt；
- 不修改全局协议。

### 不可安全旁路

以下情况禁止自动 REMOVE：

- 最终聚合器；
- 唯一裁决者；
- 不可逆转换节点；
- 移除后产生职责覆盖缺口；
- 下游依赖其专属产物。

此时只能 abstain，并默认 KEEP。

## 决策 6：团队职责覆盖缺口

必须显式建模 Coverage Gap，用于：

- 阻止危险移除；
- 提高不确定性；
- 发现初始化器遗漏职责；
- 输出非执行建议。

第一版不自动新增角色，也不强行将缺失职责塞给其他角色。

## 决策 7：修复候选数量

每个角色最多生成 3 个候选，不含 KEEP 和 REMOVE。

候选必须在操作层面不同，而不是纯措辞改写。多样性至少体现在：

- 修复操作类型；
- 修改字段；
- 角色关注范围；
- 输出接口；
- 职责边界。

## 决策 8：Adapter 边界

Adapter 只允许：

- 字段映射；
- Prompt、角色、边和执行顺序抽取；
- 协议声明；
- 缺失字段标记；
- 修复合同序列化回原框架。

Adapter 不允许：

- 框架专用缺陷规则；
- 框架专用价值阈值；
- 手工指定角色应删除；
- 使用测试结果写专用逻辑。

核心 Auditor、Predictor、Taxonomy 和 Policy 必须与 Adapter 分离。

## 决策 9：不确定性

分别表示三类风险：

1. **模型不确定性** \(\sigma_{\text{model}}\)：预测模型对训练数据扰动的敏感性；
2. **分布外风险** \(s_{\text{OOD}}\)：任务、角色、团队或协议是否超出训练支持；
3. **合同解析风险** \(q_{\text{contract}}\)：Role Contract 或 Adapter 是否缺失、低置信或不完整。

三者不能强行相加成一个模糊分数。

策略示例：

```text
OOD 风险高 → ABSTAIN → KEEP
合同关键字段不可靠 → ABSTAIN → KEEP
修复候选保守收益为正 → REWRITE
保留价值置信上界仍为负且可安全旁路 → REMOVE
其他情况 → KEEP
```

## 决策 10：多角色缺陷

- 一个角色可以有多个缺陷标签；
- 多个角色可以同时被审计；
- 第一版每轮最多实际干预一个角色；
- 重新审计后才能继续下一轮；
- 强耦合多角色问题标记 `joint_intervention_required=true`；
- 第一版不进行联合多角色修复。

---

# 6. 角色缺陷分类

缺陷分为三层。

## 6.1 内在角色缺陷

1. **UNDERSPECIFICATION**：职责、输入、输出或成功标准不清楚；
2. **INTERNAL_CONFLICT**：Prompt 内部要求相互矛盾；
3. **OVERLOAD**：一个角色承担过多异质职责；
4. **CAPABILITY_MISMATCH**：模型、工具或资源不足以完成清晰职责。

## 6.2 团队关系缺陷

5. **TASK_IRRELEVANCE**：角色与当前任务缺少实质联系；
6. **REDUNDANCY**：职责和行为与现有成员高度重叠且缺乏互补；
7. **AUTHORITY_CONFLICT**：多个角色拥有冲突的最终或否决权；
8. **DEPENDENCY_GAP**：角色所需输入没有生产者或不能按时到达；
9. **PROTOCOL_MISMATCH**：角色输出、权限或交互要求与运行协议不兼容；
10. **COVERAGE_GAP**：团队整体缺少关键职责。

## 6.3 系统价值结果

这些不是静态缺陷，而是反事实结果：

- NON_CONTRIBUTORY；
- COUNTERPRODUCTIVE；
- REPAIRABLE；
- UNREPAIRABLE_UNDER_ACTION_SPACE；
- COST_INEFFECTIVE。

特别注意：

- 冗余不自动等于 REMOVE；
- 欠描述不自动等于 REWRITE；
- 低个体能力不自动等于低团队贡献；
- 低贡献不一定能通过 Prompt 修复。

---

# 7. Role Contract 统一表示

RoleCheck 的可插拔性建立在统一 Role Contract 上。

每个角色至少包含：

```text
role_id
role_name
role_version
source_initializer
raw_prompt
prompt_hash
goal
responsibilities
success_criteria
non_goals
prohibited_behaviors
required_inputs
optional_inputs
outputs
authority_level
dependencies
interaction_mode
model_id
tool_ids
required_capabilities
resource_limits
provenance
parse_confidence
```

关键原则：

- 原始 Prompt 必须保留；
- 显式字段与模型推断字段分开；
- 低置信字段必须标记；
- 任何修复产生新版本，不能覆盖原版本；
- 角色合同与 Agent 实例分离；
- 团队级拓扑和聚合规则保存在 Team Contract 中。

---

# 8. 方法蓝图

完整方法包含七个模块。

## 8.1 Initializer Adapter

将框架特有输出映射到统一团队配置。

## 8.2 Role Contract Normalizer

从自然语言 Prompt 和配置中抽取：

- 目标；
- 职责；
- 输入；
- 输出；
- 权限；
- 依赖；
- 能力要求。

归一化阶段不得优化原角色。

## 8.3 Static Role Defect Auditor

输出多标签缺陷概率和证据：

\[
P(d_k\mid x,C,r_i,\pi)
\]

## 8.4 Keep-Value Predictor

\[
f_{keep}(x,C,r_i,\pi,H)
\rightarrow
(
\widehat{\Delta}^{keep}_i,
\sigma_i,
P(\Delta_i^{keep}<0)
)
\]

这是论文核心。

## 8.5 Defect-Conditioned Repair Generator

针对具体缺陷生成最多三个结构化候选。

## 8.6 Repair-Value Predictor

\[
f_{repair}(x,C,r_i,r'_{ik},\pi,H)
\rightarrow
(
\widehat{\Delta}^{repair}_{ik},
\sigma_{ik}
)
\]

## 8.7 Conservative Intervention Policy

推荐逻辑：

\[
LCB_{ik}^{repair}
=
\widehat{\Delta}_{ik}^{repair}
-\beta\sigma_{ik}
-\lambda_c Cost_{ik}
\]

若最佳候选 LCB 为正，则 REWRITE。

\[
UCB_i^{keep}
=
\widehat{\Delta}_i^{keep}
+\beta\sigma_i
\]

若 UCB 仍可靠为负，且角色可安全旁路，则 REMOVE。

其余情况 KEEP；高风险时 abstain 并 KEEP。

---

# 9. 五个研究问题与六个核心假设

## 9.1 研究问题

### RQ1

角色价值是否具有明显的任务、团队和协议条件性？

### RQ2

能否在当前角色尚未执行当前任务时预测其保留价值？

### RQ3

能否预测并排序有限修复候选的真实价值？

### RQ4

不确定性感知的最小干预能否减少有害修改和健康角色误改？

### RQ5

同一个核心审计器能否跨初始化器复用？

## 9.2 核心假设

### H1 关系性价值

Task + Role + Team + Protocol 优于 Role-only 和 Capability-only。

### H2 缺陷—价值不等价

缺陷概率与真实团队价值相关，但不能互相替代。

### H3 贡献—可修复性不等价

低贡献角色中只有部分可以通过 Prompt 或合同修复。

### H4 选择性修复优于普遍重写

价值驱动的定向修复应优于随机修复和全部重写。

### H5 不确定性抑制过度治疗

保守置信界和 abstention 应降低有害干预。

### H6 共享审计空间

不同初始化器输出可以映射到共享 Role Contract 和团队关系空间。

---

# 10. 明确的研究边界

## 第一版做

- 审计初始化器已生成的角色；
- 结构化 Role Contract；
- 缺陷多标签诊断；
- 保留价值预测；
- 有限修复候选排序；
- KEEP / REWRITE / REMOVE；
- 高不确定性时 abstain；
- 单角色干预；
- 性能、成本和延迟分别建模。

## 第一版不做

- 新增角色；
- 更换模型；
- 新增工具；
- 修改拓扑；
- 修改通信轮次；
- 修改聚合器；
- 联合重写全团队；
- 强化学习训练完整编排器；
- 当前任务执行后的长轨迹失败定位；
- 宣称严格因果效应；
- 宣称适用于所有 MAS。

---

# 11. 相关工作定位

需要重点阅读和持续核验的论文分为四类。

## 11.1 初始化与团队生成

- AgentInit；
- ARG-Designer；
- MaAS。

核心区别：

> 它们生成或搜索团队；RoleCheck 审计已经生成的角色。

## 11.2 Prompt 与系统设计优化

- MASS；
- MASPO；
- MAPRO；
- MAS-PromptBench；
- Textual Feedback MAS Optimization。

核心区别：

> 它们重点解决如何优化 Prompt 或系统；RoleCheck 重点预测谁值得改、何时改、哪个候选值得采用、什么时候不要改。

## 11.3 执行后失败定位与贡献归因

- AgenTracer；
- AgentLocate；
- Agents that Matter。

核心区别：

> 它们依赖已完成执行或显式干预测量；RoleCheck 的目标是在当前任务完整执行前预测。

## 11.4 反事实信用与编排训练

- CCPO；
- C3；
- LEMON。

核心区别：

> 它们将反事实信用用于策略或编排器训练；RoleCheck 是外部审计和最小干预层。

---

# 12. 16 周研究计划

## 第 1 周：冻结研究规范

完成：

- `RESEARCH_SPEC_v0.2.md`；
- `DECISION_LOG.md`；
- `RISK_REGISTER.md`；
- `INTERVENTION_PROTOCOL.md`；
- `CLAIM_EVIDENCE_MAP.md`。

验收：

- 十项决策已写入规范；
- 移除协议清楚；
- 主张与证据一一对应；
- 所有非研究范围明确。

## 第 2 周：精读相关工作

按三条线阅读：

- 初始化和系统设计；
- 反事实贡献归因；
- 失败诊断和角色修复。

每篇论文输出一页笔记，最终形成：

- `RELATED_WORK_SYNTHESIS.md`；
- 更新后的 `RELATED_WORK_MATRIX.csv`。

## 第 3 周：新建独立仓库

推荐目录：

```text
rolecheck/
├── docs/
├── configs/
├── prompts/
├── schemas/
├── data/
│   ├── tasks/
│   ├── teams/
│   ├── contracts/
│   ├── executions/
│   ├── interventions/
│   ├── defects/
│   ├── labels/
│   └── features/
├── outputs/
├── src/rolecheck/
│   ├── adapters/
│   ├── contracts/
│   ├── protocols/
│   ├── runtimes/
│   ├── defects/
│   ├── interventions/
│   ├── features/
│   ├── predictors/
│   ├── repair/
│   ├── policy/
│   └── evaluation/
├── scripts/
└── tests/
```

先实现 Schema、配置、日志、Manifest、Mock Runtime，不调用真实模型。

## 第 4 周：实现两个受控协议

### 协议 A

独立并行回答 + 确定性聚合。

用于构造干净 Leave-One-Out 标签。

### 协议 B

顺序 DAG 工作流。

只允许 Schema-preserving bypass。

先以协议 A 为主，协议 B 作为外部有效性扩展。

## 第 5 周：确定开发任务族

建议双轨：

### 推理轨道

- MATH-500；
- 后续 MMLU-Pro；
- Solver / Decomposer / Critic / Verifier。

### 代码轨道

- MBPP+ 或 HumanEval+；
- Planner / Coder / Reviewer / Tester。

MVP 先使用：

- 40 道推理任务；
- 40 道代码任务；
- 一个手工健康团队；
- 一个简单 LLM 初始化器。

## 第 6 周：建立缺陷注入系统

第一批只实现：

1. UNDERSPECIFICATION；
2. REDUNDANCY；
3. PROTOCOL_MISMATCH。

之后再考虑：

- TASK_IRRELEVANCE；
- INTERNAL_CONFLICT；
- OVERLOAD。

暂缓自动修复：

- CAPABILITY_MISMATCH；
- AUTHORITY_CONFLICT；
- DEPENDENCY_GAP；
- COVERAGE_GAP。

## 第 7 周：构造保留价值标签

对于并行团队计算：

- 完整团队；
- 分别移除每个可移除角色；
- 记录效用、成本和延迟变化。

同一任务的健康、缺陷、移除和修复版本必须进入同一个 Split。

## Gate 1：数据是否有效

继续训练前至少满足：

- 至少两类缺陷稳定影响性能；
- 数据中存在正、零和负保留价值；
- 缺陷与真实价值不完全等价；
- 标签对 Seed 足够稳定；
- 非零样本数量足够。

如果 Gate 1 不通过，先重做任务、团队或协议，不训练复杂模型。

## 第 8 周：建立 Static Auditor

基线：

- 规则；
- Embedding 相似度；
- LLM 结构化判断；
- 轻量分类器。

只负责诊断和解释，不直接决定干预。

## 第 9 周：建立 Keep-Value Predictor

Strict 特征：

- 任务；
- Role Contract；
- 团队关系；
- 协议；
- 模型和工具元数据；
- 缺陷概率。

Probe-assisted 额外使用历史画像。

严格禁止当前任务执行信息泄漏。

## 第 10 周：模型、基线和消融

基线：

- Random；
- Role Prior；
- Individual Capability；
- Task-Role Similarity；
- Static Defect Score；
- Historical Mean Contribution；
- LLM Static Judge；
- Logistic Regression；
- XGBoost；
- Full Team-Conditioned Predictor。

关键消融：

```text
Role only
Task + Role
Task + Role + Team
Task + Role + Team + Protocol
Full + Probe History
```

## 第 11 周：不确定性和拒绝判断

分别实现：

- Bootstrap 模型不确定性；
- OOD 风险；
- 合同解析风险；
- Risk-Coverage；
- Abstention。

## Gate 2：保留价值是否可预测

继续修复任务前应满足：

- Full 稳定优于 Capability-only；
- Full 稳定优于 Static Defect Score；
- 团队条件消融后显著下降；
- 有害角色识别优于随机；
- 高置信预测明显更可靠；
- Strict 设置至少存在信号；
- Probe-assisted 进一步提升。

如果失败，转向角色审计 Benchmark 和缺陷—价值关系分析，不强行继续修复器。

## 第 12 周：生成修复候选

只针对三类可控缺陷生成最多三个候选。

必须保存：

- target defects；
- changed fields；
- preserved fields；
- contract diff；
- edit rationale；
- compatibility result；
- prompt version。

## 第 13 周：Repair-Value Predictor

基线：

- Random Candidate；
- Shortest Edit；
- Highest Defect Coverage；
- Generic LLM Rewrite；
- LLM Direct Choice；
- Static Auditor Choice；
- Value Predictor；
- Oracle Candidate。

评价：

- Top-1；
- NDCG；
- Spearman；
- Regret；
- Repair Success Rate；
- Harmful Repair Rate。

## Gate 3：修复价值是否可预测

至少满足：

- 优于随机候选；
- 优于简单编辑规则；
- 优于通用 LLM 重写；
- 不确定性降低有害修复；
- 健康团队误改率可控；
- 至少两类缺陷可稳定修复。

如果失败，保留 Core-A，把修复降为案例分析。

## 第 14 周：接入第一个代表性初始化器

优先 AgentInit。

Adapter 只做字段和格式转换，不改核心逻辑。

## 第 15 周：跨初始化器验证

设置：

1. In-Domain；
2. Cross-Initializer Zero-Shot；
3. Calibration-Only。

不同结果对应不同强度的“可插拔”主张。

## 第 16 周：综合评价与论文材料

比较：

- Base Initializer；
- Random Rewrite；
- Rewrite All；
- Generic LLM Rewrite；
- Static Auditor；
- Keep Predictor without uncertainty；
- Full RoleCheck；
- Oracle Intervention。

报告：

- 性能；
- Token；
- 延迟；
- 审计成本；
- 修复生成成本；
- 修改角色数；
- Harmful Intervention Rate；
- Unnecessary Modification Rate；
- Abstention Rate；
- 净效用；
- 性能—成本 Pareto 曲线。

---

# 13. 三个关键 Go / No-Go

## Gate 1：Benchmark 有效性

问题：

> 是否真的存在可诊断、可干预且具有正/零/负价值差异的角色？

若否，不训练预测器。

## Gate 2：Keep Value 可预测性

问题：

> 当前任务执行前的信息是否包含比角色个体能力和静态缺陷更强的团队价值信号？

若否，课题转向 Benchmark 和分析。

## Gate 3：Repair Value 可预测性

问题：

> 能否在多个候选中提前选择真正有效且安全的修复？

若否，保留角色准入和保留价值预测，不强行主张修复。

---

# 14. 论文主张梯度

不能直接从定义跳到“增强多个初始化器”。

## Level 0：问题定义

- 提出角色审计问题；
- 定义保留价值和修复价值；
- 设计 Role Contract。

## Level 1：描述性发现

- 初始化角色存在缺陷；
- 缺陷和真实团队价值不等价。

## Level 2：预测性发现

- 执行前信息可预测角色价值；
- 团队和协议条件有额外贡献。

## Level 3：决策性发现

- 价值预测降低错误干预；
- 修复候选排序优于简单规则。

## Level 4：系统性发现

- 计入完整成本后改善性能—成本前沿；
- 核心逻辑可跨初始化器复用。

---

# 15. 当前立即执行的第一步

现在不要运行大规模模型实验。先让 Codex 完成研究冻结和基础仓库初始化。

可直接发送：

```text
请阅读项目中的以下文档：

- ONE_PAGE_PITCH.md
- RESEARCH_SPEC.md
- ROLE_CONTRACT_SPEC.md
- DEFECT_TAXONOMY.md
- CLAIMS_AND_NONCLAIMS.md
- METHOD_BLUEPRINT.md
- RELATED_WORK_MATRIX.csv
- ROLECHECK_RESEARCH_HANDOFF.md

现在只完成 RoleCheck 的研究冻结与基础仓库初始化，
不要调用真实模型，不要下载 Benchmark，不要实现预测器。

任务：

1. 将已确定的十项研究决策写入 RESEARCH_SPEC_v0.2.md；
2. 创建 DECISION_LOG.md；
3. 创建 RISK_REGISTER.md；
4. 创建 INTERVENTION_PROTOCOL.md，详细定义：
   - parallel aggregation removal；
   - schema-preserving bypass；
   - non-removable roles；
   - random seed 与重放规则；
5. 创建 CLAIM_EVIDENCE_MAP.md，将每个预期主张映射到所需实验；
6. 创建基础 Python 3.11 项目结构；
7. 实现以下 Pydantic Schema：
   TaskSpec、
   RoleContract、
   AgentInstance、
   CanonicalTeamConfig、
   ExecutionProtocol、
   RemovalProtocol、
   ExecutionRecord、
   InterventionRecord、
   KeepValueRecord、
   RepairCandidate、
   RepairValueRecord、
   RoleAuditReport；
8. 实现配置加载、日志、Manifest 和 Mock Runtime；
9. 创建 Schema 和配置测试；
10. 运行 ruff、mypy 和 pytest；
11. 不迁移旧项目中的实验逻辑；
12. 不实现 AgentInit、缺陷注入、价值预测或修复器；
13. 完成后按以下格式报告：
    完成内容、修改文件、测试结果、
    尚未解决的问题、下一阶段建议。
```

这一阶段通过后，下一步才是：

> 实现两个受控执行协议与 Role Contract Normalizer。

---

# 16. 每周工作节奏

建议固定为：

## 周一

冻结本周唯一阶段目标。

## 周二至周四

实现、运行和调试。

## 周五

执行：

```text
ruff
mypy
pytest
数据完整性检查
泄漏检查
重复记录检查
配置哈希检查
```

## 周六

分析：

- 高置信错误；
- 健康角色误改；
- 修复后下降；
- 缺陷与价值冲突案例；
- 合同解析失败；
- OOD 样本。

## 周日

更新：

- `DECISION_LOG.md`；
- `EXPERIMENT_LOG.md`；
- `RISK_REGISTER.md`；
- `CLAIM_EVIDENCE_MAP.md`。

每周只能增加有证据支持的新主张。

---

# 17. 文件和实验管理规范

每次实验保存：

```text
experiment_id
git_commit
timestamp
dataset_revision
task_split_hash
initializer_id
runtime_id
protocol_id
removal_protocol_id
model_versions
prompt_hashes
role_contract_hashes
seed
predictor_config
calibration_config
decision_thresholds
```

建议目录：

```text
outputs/runs/<experiment_id>/
├── manifest.json
├── config.yaml
├── logs/
├── predictions.parquet
├── metrics.json
├── figures/
└── errors.parquet
```

禁止覆盖旧结果。

---

# 18. 当前已有研究文档

已完成七份文档：

1. `ONE_PAGE_PITCH.md`
2. `RESEARCH_SPEC.md`
3. `RELATED_WORK_MATRIX.csv`
4. `ROLE_CONTRACT_SPEC.md`
5. `DEFECT_TAXONOMY.md`
6. `CLAIMS_AND_NONCLAIMS.md`
7. `METHOD_BLUEPRINT.md`

建议使用顺序：

```text
ONE_PAGE_PITCH
→ RESEARCH_SPEC
→ CLAIMS_AND_NONCLAIMS
→ RELATED_WORK_MATRIX
→ ROLE_CONTRACT_SPEC
→ DEFECT_TAXONOMY
→ METHOD_BLUEPRINT
→ 本交接文档
```

本交接文档用于快速恢复上下文；正式定义仍以冻结后的 `RESEARCH_SPEC_v0.2.md` 为准。

---

# 19. 当前最重要的风险

1. Strict 执行前信息不足以预测任务级贡献；
2. 修复候选质量可能主导修复结果；
3. 低贡献主要来自模型能力而非角色设计；
4. 零增益标签可能严重占多数；
5. 聚合器可能遮蔽角色的真实信息价值；
6. 顺序工作流中移除角色会改变后续上下文；
7. 跨初始化器可能需要重新训练；
8. 合同抽取错误可能被误认为角色缺陷；
9. 过度治疗可能破坏健康团队；
10. “可插拔”容易被夸大为宣传性表述。

---

# 20. 当前可以和不可以说的话

## 可以说

- 初始化后、当前任务执行前的角色审计；
- 操作性反事实角色保留价值；
- 指定修复候选价值；
- 团队和协议条件角色价值；
- 选择性最小修复；
- 不确定性感知和 abstention；
- 统一 Role Contract；
- 设计为可插拔的审计层。

## 需要实验后才能说

- 角色保留价值可预测；
- 团队特征显著优于个体能力；
- 修复候选价值可预测；
- 不确定性减少有害干预；
- 核心审计器可跨初始化器迁移；
- 改善性能—成本前沿。

## 暂时不能说

- 首个角色优化方法；
- 首个反事实 Agent 贡献方法；
- 识别严格因果效应；
- 解决完整 MAS 初始化；
- 适用于所有 MAS；
- 完全无需执行数据；
- 找到全局最优 Prompt；
- 保证修复后不下降。

---

# 21. 给未来助手的注意事项

未来回答和研究设计必须：

1. 以 RoleCheck 当前版本为准；
2. 不回退为单纯预算约束选队；
3. 不把课题退化为普通 Prompt 优化；
4. 不把缺陷分数直接当作团队价值；
5. 主任务优先于修复系统；
6. 先完成 Gate 1，再训练价值预测器；
7. Gate 2 失败时停止扩展修复；
8. 所有“反事实”都必须绑定干预协议；
9. 所有“可插拔”都必须说明 Adapter 边界；
10. 明确区分聊天中的概念规划、未来实验假设和已经取得的结果。

---

# 22. 新聊天的推荐开场提示词

```text
请阅读我上传的 RoleCheck 研究项目交接文档和七份研究规范。

当前课题为：
RoleCheck: Plug-and-Play Multi-Agent Initialization Auditing
and Minimal Repair via Counterfactual Role-Value Prediction。

请注意：
1. 主任务是当前任务执行前的角色保留价值预测；
2. 修复候选价值排序是第二任务；
3. 缺陷诊断用于解释和候选生成，不能替代价值预测；
4. 第一版只允许单角色 KEEP / REWRITE / REMOVE；
5. 不改模型、工具、拓扑和协议；
6. Strict Pre-Execution 是主设置；
7. Probe-assisted 是增强设置；
8. 当前阶段是研究冻结与基础仓库初始化，尚未开始正式实验。

先用你的话复述：
- 研究问题；
- 核心公式；
- 十项冻结决策；
- 方法模块；
- 三个 Go/No-Go；
- 当前下一步。

复述准确后，再继续回答我的后续问题。
```
