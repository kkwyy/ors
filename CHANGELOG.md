# Changelog

## 0.0.2 — 2026-10-25

Farkas 证书与独立验证。

- `Certificate` / `CertificateTerm` / `verify_certificate`：LP 不可行的可验证证明。
- 证书由辅助 LP 计算，验证过程不调用求解器，只做稀疏线性代数。
- 证书绑定模型指纹（sha256），防止张冠李戴。
- CLI：`ors diagnose --certificate cert.json`、`ors verify cert.json model.mps`。
- 修复：变量界矛盾（lb > ub）不再让后端报错，直接返回 infeasible。
- 测试：22 个，新增证书构建、JSON 往返、篡改拒绝、模型不匹配、纯界不可行、随机模型。

## 0.0.1 — 2026-10-24

首个可运行骨架（pre-alpha）。

- `Model` / `Var` / `Constraint` 轻量线性建模层，保留用户命名与表达式。
- HiGHS 后端：求解、对偶值、MPS 读取。
- LP 不可行诊断：删除过滤、加性方法、`auto` 策略。
- 模型体检：矛盾界、自由变量、空约束、大系数、极小系数、重复约束。
- `Diagnosis.report()`：HTML / JSON。
- CLI：`ors solve`、`ors diagnose`。
- 15 个测试；随机模型上验证 IIS 的“不可约”不变量。
