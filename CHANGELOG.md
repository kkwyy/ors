# Changelog

## 0.0.1 — 2026-10-24

首个可运行骨架（pre-alpha）。

- `Model` / `Var` / `Constraint` 轻量线性建模层，保留用户命名与表达式。
- HiGHS 后端：求解、对偶值、MPS 读取。
- LP 不可行诊断：删除过滤、加性方法、`auto` 策略。
- 模型体检：矛盾界、自由变量、空约束、大系数、极小系数、重复约束。
- `Diagnosis.report()`：HTML / JSON。
- CLI：`ors solve`、`ors diagnose`。
- 15 个测试；随机模型上验证 IIS 的“不可约”不变量。
