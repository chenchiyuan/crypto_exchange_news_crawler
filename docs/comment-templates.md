# 项目文档化标准与注释模板

**版本**: v1.0.0
**创建日期**: 2025-12-25
**适用范围**: 迭代004及后续所有开发任务

---

## 1. 文档化标准

### 1.1 Python Docstrings规范

采用**PEP 257**标准，使用三重引号`"""`格式：

**模块级文档**:
```python
"""
模块名称

模块描述：简要说明模块的功能和用途

作者: [作者姓名]
版本: [版本号]
日期: [创建日期]
"""
```

**类文档**:
```python
class ClassName:
    """
    类名

    类描述：详细说明类的职责、功能和用途

    Attributes:
        attribute1 (类型): 属性描述
        attribute2 (类型): 属性描述

    Examples:
        >>> obj = ClassName()
        >>> obj.method()
    """
```

**函数/方法文档**:
```python
def function_name(param1: Type, param2: Type = default) -> ReturnType:
    """
    函数名称

    函数描述：简要说明函数的作用

    Args:
        param1 (Type): 参数1的描述，包括单位、约束、示例
        param2 (Type, optional): 参数2的描述，默认值为default

    Returns:
        ReturnType: 返回值的描述，包括类型和语义

    Raises:
        ExceptionType: 异常描述，包括触发条件和上下文

    Examples:
        >>> result = function_name('value1')
        >>> print(result)

    Note:
        重要说明或注意事项
    """
```

---

## 2. 接口契约注释模板

### 2.1 公共接口（类、函数、方法）

**标准模板**:
```python
def method_name(self, param1: Type, param2: Type) -> ReturnType:
    """
    @name method_name
    @description [业务价值或技术目的描述]

    @param {Type} param1 - [物理意义、单位、约束]
    @param {Type} param2 - [物理意义、单位、约束]
    @throws {[ExceptionType]} [抛出条件和上下文]
    @returns {[Type]} [返回值的类型和语义]
    @context 关联TASK-004-XXX和prd.md需求点
    @side-effects [副作用说明，如：修改全局状态、IO操作等]

    Examples:
        >>> result = method_name(value1, value2)
    """
```

### 2.2 复杂业务逻辑

**标准模板**:
```python
# === 业务上下文描述 ===
# 基于[规则/需求]，当[条件]时，执行[操作]
# 原因：[为什么这样做]
# 例如：基于风控规则4.2，如果用户在1分钟内重试超过3次，则触发熔断
```

---

## 3. 维护标记规范

### 3.1 标记格式

- **TODO**: [任务描述] (关联TASK-004-XXX)
- **FIXME**: [问题描述] (关联TASK-004-XXX)
- **NOTE**: [重要说明] (关联TASK-004-XXX)
- **WARNING**: [警告信息] (关联TASK-004-XXX)

### 3.2 示例

```python
# TODO: 实现数据校验逻辑 (TASK-004-001)
def validate_data(data):
    pass

# FIXME: 性能优化，当前实现复杂度O(n²) (TASK-004-002)
def inefficient_function():
    pass

# NOTE: 此处使用临时方案，后续需要重构 (TASK-004-003)
def temporary_solution():
    pass
```

---

## 4. 异常处理文档化

### 4.1 Fail-Fast异常文档

```python
def process_data(data: dict) -> str:
    """
    处理数据并返回结果

    @param {dict} data - 输入数据，必须包含'key'字段
    @throws {ValueError} 当data为空或缺少必需字段时抛出
    @throws {TypeError} 当data类型不是dict时抛出
    @returns {str} 处理结果

    Examples:
        >>> process_data({'key': 'value'})
        'processed'
    """
    # === 防御性编程：Guard Clauses ===
    if not data:
        raise ValueError("data不能为空")

    if 'key' not in data:
        raise ValueError("data必须包含'key'字段")

    # 主逻辑...
```

---

## 5. 质量保证检查清单

- [ ] 所有公共类/函数/方法都有完整的docstring
- [ ] docstring符合PEP 257标准
- [ ] 复杂业务逻辑有上下文注释
- [ ] 异常处理有明确的Fail-Fast文档
- [ ] 所有TODO/FIXME/NOTE都关联了任务ID
- [ ] 代码变更后同步更新了注释
- [ ] 通过了自动化文档检查工具验证

---

**变更历史**:
- v1.0.0 (2025-12-25): 初始版本，定义文档化标准
