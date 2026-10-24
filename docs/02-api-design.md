# ors API 设计稿（v0.1）

状态：草案，pre-alpha。所有接口在 1.0 前可能变化。

---

## 1. 设计原则

1. **诊断是一等公民**：`diagnose()` 返回结构化对象，不是日志里的一行字。
2. **可验证**：每个"不可行/无界/最优"结论都能附带证书，证书可独立复核。
3. **不隐藏不确定性**：数值容差、"几乎可行"、"启发式 IIS 不保证最小"，都要显式标注。
4. **可组合**：后端可替换（HiGHS → 自研内核），诊断层不依赖特定求解器。
5. **Python 原生**：类型提示、可序列化、无全局状态、与 NumPy/Pandas 自然互操作。

---

## 2. 状态模型

```python
class Status(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    INF_OR_UNB = "infeasible_or_unbounded"   # 求解器无法区分
    TIME_LIMIT = "time_limit"
    ITERATION_LIMIT = "iteration_limit"
    NUMERICAL = "numerical"
    ERROR = "error"
```

约束：只有 `OPTIMAL` 才保证 `x` 是可行解；只有 `INFEASIBLE` 才允许调用 `diagnose()` 的 IIS 路径；
`INF_OR_UNB` 必须先做一次额外判定，不能直接下结论。

---

## 3. 建模层

```python
import ors

m = ors.Model("schedule")
x = m.add_var(lb=0, ub=10, name="x")
y = m.add_vars(3, lb=0, vtype="integer", name="y")   # 返回 list[Var]

m.add_constr(2 * x + y[0] <= 10, name="capacity")
m.add_constr(x - y[1] >= 2, name="demand")
m.add_constr(x.eq(3), name="fixed_x")                # 等式用 .eq()，避免覆盖 __eq__

m.set_objective(x + 2 * y[0] + 3 * y[1], sense="min")
```

### 3.1 `Var`

| 属性 | 类型 | 说明 |
|---|---|---|
| `index` | int | 在模型内的列索引 |
| `name` | str | 用户可见名 |
| `lb` / `ub` | float | 界，支持 `±inf` |
| `vtype` | `"continuous" \| "integer" \| "binary"` | 变量类型 |

运算符：`+ - * /`（仅常数）、`<=` `>=` 返回 `ConstraintSpec`，`.eq()` 返回等式。

### 3.2 `Model`

| 方法 | 说明 |
|---|---|
| `add_var(...) -> Var` | 添加变量 |
| `add_vars(n, ...) -> list[Var]` | 批量添加 |
| `add_constr(expr, name=None) -> Constraint` | 添加约束，expr 为 `<=`/`>=`/`.eq()` 的结果 |
| `set_objective(expr, sense="min")` | 设置目标 |
| `optimize(options=None) -> Result` | 求解 |
| `diagnose(options=None) -> Diagnosis` | 诊断（不可行时） |
| `write(path)` / `Model.read(path)` | MPS/LP 读写 |
| `to_highs()` | 导出底层模型（调试用） |
| `diff(other) -> ModelDiff` | 模型对比 |

### 3.3 互操作

- `Model.from_pyomo(pyomo_model, ...)`（可选依赖）
- `Model.from_mps(path)` / `from_lp(path)`
- `Model.to_json()` / `from_json()`：自有格式，便于存证和复现
- 未来：JuMP/MOI JSON 适配

---

## 4. 求解结果

```python
@dataclass(frozen=True)
class Result:
    status: Status
    objective: float | None
    x: dict[str, float] | None
    dual: dict[str, float] | None
    reduced_costs: dict[str, float] | None
    iterations: int
    runtime: float
    gap: float | None
    backend: str
    certificate: Certificate | None
```

`x` 用变量名索引，避免用户对着索引猜。重名变量自动加后缀并告警。

---

## 5. 诊断结果

```python
@dataclass
class Diagnosis:
    status: DiagStatus                  # infeasible / unbounded / ok / numerical
    iis: IIS | None
    relaxation: Relaxation | None
    certificate: Certificate | None
    findings: list[Finding]
    explanation: str | None             # LLM 生成，可能为 None
    elapsed: float
    backend: str

    def summary(self) -> str: ...
    def why(self, ref: str | Constraint) -> Explanation: ...
    def report(self, path: str, format: str = "html") -> None: ...
```

### 5.1 IIS

```python
@dataclass
class IIS:
    constraints: list[ConstraintRef]    # 原始约束引用，含名字和表达式
    bounds: list[BoundRef]              # 参与冲突的变量界
    minimal: bool                       # 启发式结果可能不保证最小
    method: str                         # "deletion" | "additive" | "elastic"
    solves: int
```

`ConstraintRef` 保留：原始名字、原始表达式字符串、标准形行号、presolve 溯源链。

### 5.2 松弛建议

```python
@dataclass
class Relaxation:
    changes: list[Change]               # (ref, 方向, 最小改动量, 单位成本)
    total_violation: float
    objective_penalty: float
    method: str                         # "elastic" | "min_edit"
```

语义：**在保持其余约束不变的前提下，最小化总违反量**。不承诺"业务上最合理"，只承诺"数学上最小"。

### 5.3 证书

```python
@dataclass
class Certificate:
    kind: Literal["farkas", "unbounded_ray", "optimal", "none"]
    vector: list[float]
    residual: float                     # 验证残差
    verified: bool
    checker: str                        # 例如 "ors.verify.farkas@1"
    model_hash: str
```

JSON 形式（存证用）：

```json
{
  "kind": "farkas",
  "version": 1,
  "model_hash": "sha256:...",
  "vector": [0.0, 1.0, -0.5],
  "residual": 1.2e-12,
  "verified": true,
  "checker": "ors.verify.farkas@1"
}
```

### 5.4 模型体检

```python
@dataclass
class Finding:
    severity: Literal["error", "warning", "info"]
    code: str          # "BIG_M" | "DUPLICATE_ROW" | "TINY_COEF" | "FREE_VAR" | ...
    message: str
    refs: list[Ref]
```

首批检查项：大系数、big-M、重复约束、自由变量、空约束、矛盾界、极小系数、退化提示。

---

## 6. 选项

```python
@dataclass
class DiagnoseOptions:
    method: Literal["auto", "deletion", "additive", "elastic"] = "auto"
    max_time: float = 60.0
    max_solves: int = 1000
    include_bounds: bool = True
    explain: bool = False
    explain_model: str | None = None     # "local" | "cloud" | 具体模型名
    tolerance: float = 1e-9
```

`method="auto"`：小模型用删除过滤（结果最干净），大模型用加性方法（更快）。

---

## 7. 命令行

```bash
ors solve model.mps --time-limit 60
ors diagnose model.mps --report report.html --explain
ors diagnose model.mps --format json
ors diff old.mps new.mps
ors verify cert.json model.mps
```

退出码：`0` 成功，`1` 不可行，`2` 无界，`3` 数值问题，`4` 用法错误。

---

## 8. 报告格式

`report.html` 结构：

1. **结论**：状态、目标值、耗时。
2. **冲突摘要**：IIS 约束列表（按业务重要性排序），每条带原始表达式。
3. **建议修改**：松弛量、代价、备选方案。
4. **证书**：Farkas 向量、残差、验证结果。
5. **模型体检**：warning 列表。
6. **AI 解释**（可选）：自然语言段落，标注"AI 生成"。

同时支持 `--format json`，便于集成 CI。

---

## 9. 错误处理

- `ors.BackendNotAvailable`：未安装 highspy 且未指定后端。
- `ors.ModelError`：建模错误（重复名、非法界、空表达式）。
- `ors.DiagnosisError`：模型不是不可行，却调用了 IIS 路径。
- 所有异常带 `hint` 字段，给出修复建议。

---

## 10. 兼容性策略

- 1.0 前：`0.x`，接口可变，但每次破坏性变更写 CHANGELOG。
- 1.0 后：semver；废弃接口保留两个 minor 版本。
- 证书格式带 `version` 字段，验证器向后兼容。
