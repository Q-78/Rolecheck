# RoleCheck：可主张与不可主张事项

**版本：** v0.1  
**日期：** 2026-08-01  
**用途：** 约束论文、组会、项目主页和实验报告中的措辞，避免伪创新、过度因果解释和范围膨胀。

---

# 1. 核心定位

推荐统一表述：

> RoleCheck 是一个位于 LLM 多智能体初始化器与执行框架之间的角色审计层。它将初始化角色归一化为统一合同，在当前任务完整执行前预测角色相对于任务、团队和协议的操作性反事实保留价值及有限修复候选价值，并通过不确定性感知的最小干预策略选择保留、重写或移除。

---

# 2. 当前设计层面可以主张的内容

## C1. 研究阶段

可以说：

- “研究初始化后、当前任务完整执行前的角色审计。”
- “组件位于初始化器和执行运行时之间。”
- “区别于执行后失败归因和长轨迹故障定位。”

不能说：

- “完全不使用任何执行数据。”

若使用历史 Probe，应说：

- “不使用当前测试任务的角色输出，可使用独立校准任务上的历史画像。”

## C2. 研究对象

可以说：

- “审计的是角色配置，而不仅是角色名称。”
- “角色合同包含职责、输入、输出、权限、依赖、模型和工具上下文。”
- “第一版主要干预 Prompt/合同和角色成员资格。”

不能说：

- “优化整个 MAS 初始化。”

因为第一版不生成新角色、不改模型、不改工具、不改拓扑和协议。

## C3. 反事实术语

可以说：

- “操作性反事实角色价值。”
- “在预先定义的角色移除或替换协议下比较两个可执行团队配置。”
- “协议条件的边际效用。”

不能说：

- “识别了角色的真实因果效应。”
- “该角色的普遍因果贡献为某个数值。”
- “去除了所有混杂因素。”

除非未来提供严格因果识别假设与证明。

## C4. 最小修复

可以说：

- “只对具有可靠正修复价值的候选实施修改。”
- “高不确定性时默认保留。”
- “尽量不改变无关团队结构。”

不能说：

- “得到全局最优角色 Prompt。”
- “找到最佳团队。”
- “保证修复后不下降。”

## C5. 可插拔

可以说：

- “方法通过统一 Role Contract 设计为框架无关。”
- “核心模块不要求访问初始化器内部梯度。”

在没有跨系统证据前，应说 “designed to be plug-and-play”，不要说 “is universally plug-and-play”。

---

# 3. 必须由实验支持后才能主张的内容

## E1. 执行前价值可预测

只有当测试结果支持后才能说：

- “角色保留价值在当前任务执行前具有可预测信号。”
- “团队条件特征优于个体能力或角色语义基线。”
- “预测可以识别有害角色。”

不能仅凭训练集拟合或案例分析主张。

## E2. 修复价值可预测

必须证明对未见任务或未见团队的候选排序有效，才能说：

- “RoleCheck 能提前选择更有价值的修复候选。”

若只证明生成后的 Prompt 更好，应说：

- “修复生成器产生了有效候选”，而不是“修复价值可预测”。

## E3. 不确定性有价值

只有证明风险—覆盖、有害修复率或健康角色误改率改善后，才能说：

- “不确定性感知减少过度治疗。”

仅使用 Bootstrap 或输出方差不等于该不确定性有决策价值。

## E4. 可插拔性

至少需要跨不同初始化来源，并保持核心审计逻辑基本不变，才能说：

- “RoleCheck 能增强多个代表性初始化器。”

若每个系统需专用重写规则，应限制为：

- “RoleCheck 提供统一接口，但适配仍具有框架依赖。”

## E5. 性能提升

必须计入审计成本、Probe 成本、修复候选生成成本、修改后团队执行成本和延迟，才能说：

- “RoleCheck 改善性能—成本前沿”；
- “RoleCheck 产生正净收益”。

只报告准确率提升应表述为：

- “任务性能提高，但未包含完整审计成本。”

---

# 4. 明确不可主张的内容

## N1. “首个角色优化方法”

已有 MAS Prompt 优化、文本反馈角色优化、贡献引导优化和系统搜索工作。

## N2. “首个反事实 Agent 贡献方法”

已有 removal-based attribution、counterfactual credit assignment、counterfactual replay 和 counterfactual orchestration learning。

## N3. “解决了完整 MAS 初始化”

RoleCheck 审计已有初始化结果，不从零生成完整团队。

## N4. “适用于所有多智能体系统”

价值依赖任务、协议、模型、工具和运行时。

## N5. “角色语义异常必然导致负贡献”

缺陷诊断和反事实价值不等价。

## N6. “低贡献角色都能通过 Prompt 修复”

低贡献可能来自模型、工具、拓扑和协议限制。

## N7. “移除实验得到角色的固有价值”

得到的是指定团队、任务分布和移除协议下的价值。

## N8. “预测器没有数据泄漏”

必须由特征审计和任务级划分证明，不能自行宣称。

## N9. “可校准”

只有概率校准指标与可靠性分析支持后才能使用 “calibrated”。

## N10. “零成本插件”

审计、结构化抽取、候选生成和预测均有成本。

---

# 5. 推荐术语

| 推荐 | 避免 |
|---|---|
| operational counterfactual role value | true causal contribution |
| protocol-conditioned utility | intrinsic role value |
| pre-execution on the current task | never executed |
| probe-assisted pre-deployment | zero-shot auditing（若使用 Probe） |
| selective minimal repair | globally optimal prompt |
| framework-agnostic representation | universally framework-independent |
| harmful probability | guaranteed harmful |
| abstention / conservative default | complete automation |
| candidate repair ranking | optimal repair generation |

---

# 6. 贡献声明模板

在证据尚未完成时，可使用假设式版本：

1. **Problem formulation.** We formulate post-initialization, pre-execution role auditing as predicting protocol-conditioned operational counterfactual role value.
2. **Dual-level auditing.** We separate interpretable role-defect diagnosis from team-utility estimation.
3. **Value-guided intervention.** We design a conservative policy that ranks finite repair candidates and abstains when expected benefit is uncertain.
4. **Interoperability design.** We introduce a canonical Role Contract intended to decouple the auditor from initializer-specific representations.

实验完成且结果支持后，再将 “formulate/design/intended” 替换为更强结果性语言。

---

# 7. 与相邻工作的标准差异表述

## 对 AgentInit / ARG-Designer

推荐：

> These methods construct task-specific teams, whereas RoleCheck audits the roles already produced by an initializer and estimates whether retaining or minimally repairing each role is beneficial under the downstream protocol.

避免：

> Existing initialization methods ignore role quality.

因为它们已经考虑相关性、专业性、多样性或拓扑质量。

## 对 MASS / MASPO / MAPRO

推荐：

> Prompt-search methods optimize prompts or system design globally. RoleCheck focuses on deciding which initialized role should be preserved, repaired, or removed based on predicted team-level marginal utility.

避免：

> Existing methods rewrite all prompts blindly.

不同工作机制并不相同，不能一概而论。

## 对文本反馈优化

推荐：

> Textual-feedback optimization uses observed execution feedback to locate and rewrite underperforming agents. RoleCheck targets prospective, current-task value estimation and conservative candidate selection.

避免：

> No prior work identifies which role to rewrite.

## 对 AgenTracer / AgentLocate

推荐：

> Failure localization analyzes completed failed trajectories and attributes responsibility to an agent or step. RoleCheck operates before the current task’s full execution and predicts potential role value rather than explaining an observed failure.

## 对 Agents that Matter

推荐：

> Removal-based attribution measures contribution by running explicit interventions. RoleCheck uses such operational quantities as supervision or an oracle target, while its core goal is prospective prediction.

## 对 CCPO / LEMON

推荐：

> Counterfactual credit methods optimize policies or orchestration generators using execution rewards. RoleCheck is an external auditing and intervention layer over an already initialized team.

---

# 8. 结果不理想时的诚实表述

## 情况 A：只能预测平均贡献

> Role value exhibits distribution-level predictability, but task-instance prediction remains limited.

## 情况 B：静态审计有效，反事实预测无增益

> Most detectable defects are captured by contract-level compatibility checks; team-value prediction did not provide consistent additional benefit.

## 情况 C：价值预测有效，修复排序无效

> Prospective role admission is feasible, while repair-candidate value remains difficult to estimate.

## 情况 D：只能在同一初始化器内有效

> The auditor is initializer-specific under the present representation; stronger cross-initializer normalization is needed.

## 情况 E：定向修复不优于通用重写

> Localization alone did not yield superior repair outcomes, suggesting that candidate-generation quality dominates intervention selection.

这些结论仍可形成有价值的分析论文，不应掩盖。

---

# 9. Claim Ladder

论文主张应按以下层级递进。

## Level 0：定义

- 提出角色审计问题；
- 定义保留价值与修复候选价值；
- 设计统一角色合同。

## Level 1：描述性发现

- 初始化角色存在可观察缺陷；
- 缺陷与团队价值并非完全一致。

## Level 2：预测性发现

- 执行前特征能预测保留价值；
- 团队条件特征有额外贡献。

## Level 3：决策性发现

- 价值预测能降低错误干预；
- 修复候选排序优于简单规则。

## Level 4：系统性发现

- 计入成本后改善性能—成本前沿；
- 在多个初始化来源上复用。

不能跳过低层证据直接宣称 Level 4。

---

# 10. 摘要写作安全模板

> Existing LLM multi-agent initializers can generate task-specific roles and collaboration structures, yet an initialized role that appears semantically appropriate may still be redundant, protocol-incompatible, or counterproductive in its downstream team. We study post-initialization, pre-execution role auditing. We define operational counterfactual keep value through a controlled role-removal protocol and candidate-specific repair value through role replacement. RoleCheck normalizes roles into framework-independent contracts, diagnoses interpretable defects, predicts team-conditioned role value and uncertainty, and applies a conservative KEEP/REWRITE/REMOVE policy. The empirical claims regarding predictability, repair effectiveness, calibration, and cross-initializer transfer must be instantiated only after evaluation.

最后一句在正式摘要中应替换为真实实验结果。
