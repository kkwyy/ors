# ors

**让优化模型可解释。** 开源求解器只告诉你 `infeasible`，ors 告诉你*为什么*、*改哪里*、*凭什么*。

> 状态：pre-alpha（0.0.1）。API 不稳定，仅支持 LP 诊断，MILP 在路线图中。

## 它解决什么

```python
import ors

m = ors.Model("demo")
x = m.add_var(lb=0, name="x")
y = m.add_var(lb=0, name="y")

m.add_constr(x + y >= 10, name="demand")
m.add_constr(x + y <= 5, name="capacity")
m.set_objective(x + y, sense="min")

r = m.optimize()
print(r.status)        # Status.INFEASIBLE

d = m.diagnose()
print(d.summary())
# status: infeasible
# backend: highs
# elapsed: 0.004s
# IIS: 2 constraint(s) [deletion, 2 solves]
#   - demand: x + y >= 10
#   - capacity: x + y <= 5
```

## 安装

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[highs,dev]"
pytest
```

## 当前能力

| 能力 | 状态 |
|---|---|
| 线性建模（变量/约束/目标） | ✅ |
| HiGHS 后端求解 | ✅ |
| LP 的 IIS（删除过滤 / 加性方法） | ✅ |
| 模型体检（大系数、重复约束、矛盾界等） | ✅ |
| MPS 读取 | ✅ |
| Farkas 证书 + 验证 | 🚧 |
| 可行性松弛建议 | 🚧 |
| MILP 诊断 | 🚧 |
| 自然语言解释 | 🚧 |

## 文档

- [项目一页纸](docs/01-one-pager.md)
- [API 设计稿](docs/02-api-design.md)
- [90 天执行计划](docs/03-90-day-plan.md)

## 开发

```bash
pytest                      # 运行测试
python -m ors --help        # CLI
```

## 许可证

Apache-2.0，见 [LICENSE](LICENSE)。
