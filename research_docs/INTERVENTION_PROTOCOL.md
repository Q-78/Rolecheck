# RoleCheck 单角色干预协议

**版本：** v0.1  
**日期：** 2026-08-02  
**适用范围：** 第一版单角色 `KEEP / REWRITE / REMOVE` 的操作性反事实标签与后续决策评估

## 1. 目的

本协议将“移除角色”与“替换角色”定义为可重放的系统操作，避免把未定义的删除或补偿行为误当作角色价值。所有价值都必须注明任务、团队、执行协议、干预协议和随机种子。

## 2. 不变量

任何单角色干预均不得：

- 更换基础模型；
- 增删工具或改变权限；
- 修改通信拓扑；
- 修改执行轮次；
- 修改聚合协议；
- 修改全局停止规则；
- 新增角色；
- 修改未被选中的角色合同或 Prompt；
- 同一轮干预多个角色。

若无法满足以上条件，干预无效，必须 `ABSTAIN → KEEP`。

## 3. 动作定义

### 3.1 KEEP

保持原团队配置不变。KEEP 也是以下情况的默认外部动作：

- 证据不足；
- OOD 风险高；
- 合同关键字段低置信；
- 移除不安全；
- 修复候选无正的保守收益；
- 需要联合多角色干预。

### 3.2 REWRITE

用一个具体 `RepairCandidate.candidate_contract` 替换目标角色的 Role Contract，保持该角色的 agent/model/tools/node position 不变。

允许变化字段：

- responsibilities；
- success criteria；
- non-goals；
- prohibited behaviors；
- required/optional input 的描述与格式声明；
- outputs 的字段、格式与描述；
- 与上述结构化字段一致的 raw prompt。

禁止变化字段：

- role identity 与团队节点身份；
- model_id、tool_ids、sampling config；
- authority 的系统级提升；
- execution/aggregation/removal/termination protocol；
- edges、execution order、team size。

每个候选必须保存父版本、变更字段、保留字段、合同 diff、目标缺陷、生成器版本和兼容性检查结果。

### 3.3 REMOVE

从当前团队执行中排除目标角色，但只能使用下述预定义协议之一。REMOVE 不等于任意删除工作流节点。

## 4. 协议 A：Parallel Aggregation Removal

### 4.1 适用条件

仅适用于：

- 目标角色与其他被保留角色在该轮独立执行；
- 目标角色不产生其他角色运行所需输入；
- 聚合器接受可变数量的同构响应，或已声明缺失响应处理规则；
- 目标角色不是最终聚合器、唯一裁决者或唯一 veto 角色。

### 4.2 基线执行

1. 固定 `task_id`、团队配置、协议版本和 seed；
2. 运行所有角色；
3. 保存各角色原始响应、响应哈希、Token、延迟和聚合结果；
4. 保存完整 Manifest。

### 4.3 移除重放

1. 不重新生成被保留角色响应；
2. 从基线响应集合中删除目标角色响应；
3. 使用同一聚合器版本、同一参数和同一确定性 seed 重新聚合；
4. 不添加“角色缺席”的补偿文本；
5. 记录聚合输入列表及其哈希。

此协议估计的是目标响应对固定其他响应下聚合结果的边际影响，不等价于重新运行一个更小团队的全部动态。

### 4.4 无效条件

- 聚合器要求固定数量输入且无声明的缺失处理；
- 聚合器自身具有随机性但无法重放；
- 其他角色的执行依赖目标角色；
- 删除后改变投票权定义而协议未预先规定。

## 5. 协议 B：Schema-Preserving Bypass

### 5.1 适用条件

仅适用于顺序 DAG 中的单节点，且：

- 目标角色只有可识别的上游输入和下游消费者；
- 上游产物的语义类型与下游 required input 兼容；
- 旁路不需要生成新内容、摘要、格式转换或缺省值；
- 不修改下游 Prompt；
- 不改变边以外的拓扑和协议语义；
- 旁路规则在看到实验结果前已注册。

### 5.2 旁路操作

1. 移除目标角色节点的执行；
2. 将预先声明的上游 artifact 原样传递给预先声明的下游 input；
3. 只允许必要的字段名映射，不允许语义变换；
4. 保存输入/输出 schema、artifact hash 和映射表；
5. 其余节点使用相同配置与 seed 执行。

### 5.3 Schema 兼容判定

旁路必须同时满足：

- required fields 被上游完整提供；
- semantic type 相同或存在预注册的等价关系；
- serialization format 兼容；
- visibility/permission 允许下游读取；
- 不跨越不可逆变换；
- 不产生 Coverage Gap。

### 5.4 禁止的“伪旁路”

- 使用 LLM 生成补偿消息；
- 自动总结、翻译、修正或转换上游输出；
- 将目标职责临时分配给其他角色；
- 修改下游 Prompt 使其适应缺失节点；
- 根据结果好坏选择不同旁路路径。

## 6. Non-Removable Roles

下列角色自动标记 `removable=false`：

1. 最终聚合器；
2. 唯一裁决者或唯一 veto 角色；
3. 执行不可逆转换的节点；
4. 唯一生产某个下游 required artifact 的节点，且无 schema-preserving bypass；
5. 移除后导致任务必要职责 Coverage Gap 的角色；
6. 负责安全、权限或合规门控且协议无替代路径的角色；
7. 合同或拓扑解析置信不足，无法证明安全旁路的角色。

“预测为负价值”不能覆盖不可移除约束。

## 7. 单角色与重新审计规则

- 一次 `InterventionRecord` 只能包含一个 `target_role_id`；
- 干预后生成新 `team_version`；
- 若继续干预，必须对新团队重新归一化、审计和预测；
- 不得将第一次审计分数直接用于第二次干预；
- 强耦合问题标记 `joint_intervention_required=true`，第一版不执行。

## 8. 随机种子与重放规则

### 8.1 Seed 层级

每次运行至少记录：

- `experiment_seed`：实验级种子；
- `task_seed`：任务实例级种子；
- `role_seed[role_id]`：角色生成种子；
- `aggregation_seed`：聚合器种子；
- `repair_generation_seed`：候选生成种子（未来阶段）；
- `predictor_seed`：训练/推理种子（未来阶段）。

推荐由稳定哈希派生：

```text
child_seed = uint32(sha256(parent_seed | namespace | stable_id))
```

不得依赖 Python 进程级随机哈希。

### 8.2 配对执行

- 基线与反事实必须共享相同任务版本、模型版本、Prompt 版本、协议版本和 seed 集；
- 并行 removal 使用固定其他响应，不重新采样；
- 顺序 bypass 对未受干预且输入不变的节点应重放相同结果；输入变化的下游节点可重新执行，但必须保持相同 role seed；
- 所有重放必须记录哪些节点复用、哪些节点重新执行及原因。

### 8.3 多 Seed 标签

正式标签可对预注册 seed 集求均值与方差，但必须同时保存逐 seed 记录。若价值符号在 seed 间不稳定，应提高标签不确定性或标记为 ambiguous，不得只保留有利 seed。

## 9. 记录要求

每个反事实比较至少保存：

```text
experiment_id
baseline_run_id
counterfactual_run_id
task_id
team_id/team_version
target_role_id
action
repair_id (REWRITE only)
execution_protocol_id
removal_protocol_id
seed hierarchy
model/tool/prompt/contract hashes
reused artifacts and hashes
re-executed nodes
baseline utility/cost/latency
counterfactual utility/cost/latency
delta utility/cost/latency
bypass compatibility evidence
coverage-gap result
validity status and invalid reason
```

## 10. 协议有效性检查表

执行 REMOVE 前必须全部回答“是”：

- 是否只干预一个角色？
- 是否没有改变模型、工具、拓扑语义或协议？
- 是否已在实验前声明对应 removal strategy？
- 是否不是 non-removable role？
- 是否通过 Coverage Gap 检查？
- 是否可重放并记录全部 seed/hash？
- 是否没有生成补偿内容？
- 是否能明确解释哪些输出被固定、哪些节点被重跑？

任一项为“否”时，REMOVE 无效并回退 KEEP。
