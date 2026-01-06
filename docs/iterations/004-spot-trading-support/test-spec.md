# 测试规格设计

**迭代编号**: 004
**创建日期**: 2025-12-25
**生命周期阶段**: P6 - 开发实现
**参考文档**: tasks.md, architecture.md

---

## 测试规格清单

| 测试点 ID | 关联需求 (prd.md) | 关联架构 (architecture.md) | 任务ID (tasks.md) | 测试策略 | 可量化成功标准 |
|----------|------------------|---------------------------|------------------|---------|--------------|
| **TC-001** | P0-3 | SpotContract模型 | TASK-004-001 | 单元测试 | SpotContract.objects.create()成功创建记录 |
| **TC-002** | P0-3 | SpotContract模型 | TASK-004-001 | 异常测试 | 重复(exchange, symbol)时抛出IntegrityError |
| **TC-003** | P0-2 | KLine模型扩展 | TASK-004-002 | 集成测试 | 现有数据自动标记为market_type='futures' |
| **TC-004** | P0-2 | KLine模型扩展 | TASK-004-002 | 异常测试 | 无效market_type时抛出ValidationError |
| **TC-005** | P0-1 | BinanceSpotClient | TASK-004-003 | 单元测试 | _normalize_symbol()正确转换符号格式 |
| **TC-006** | P0-1 | BinanceSpotClient | TASK-004-003 | 集成测试 | fetch_contracts()返回现货交易对列表 |
| **TC-007** | P0-1 | fetch_spot_contracts命令 | TASK-004-004 | 集成测试 | 命令成功同步现货交易对到数据库 |
| **TC-008** | P0-4 | 状态机适配 | TASK-004-005 | 集成测试 | 现货异常检测流程正常执行 |
| **TC-009** | P0-5 | MonitorListAPI扩展 | TASK-004-006 | API测试 | market_type='spot'筛选现货记录 |
| **TC-010** | P0-5 | MonitorListAPI扩展 | TASK-004-006 | API测试 | 无效market_type返回400错误 |

---

## 详细测试用例

### TC-001: SpotContract模型创建
- **测试目标**: 验证SpotContract模型可以正确创建现货交易对记录
- **测试步骤**:
  1. 创建Exchange记录（如果不存在）
  2. 使用SpotContract.objects.create()创建现货交易对
  3. 验证记录创建成功
  4. 验证字段值正确
- **预期结果**: 
  - SpotContract记录创建成功
  - 所有字段值正确设置
  - 可以通过objects.get()查询到记录

### TC-002: SpotContract唯一性约束
- **测试目标**: 验证(exchange, symbol)的唯一性约束
- **测试步骤**:
  1. 创建SpotContract记录A
  2. 尝试创建相同(exchange, symbol)的记录B
- **预期结果**: 
  - 抛出IntegrityError异常
  - 数据库中没有重复记录

### TC-003: KLine模型数据迁移
- **测试目标**: 验证现有KLine数据自动标记为market_type='futures'
- **测试步骤**:
  1. 创建测试KLine记录（不指定market_type）
  2. 执行数据迁移
  3. 验证market_type='futures'
- **预期结果**: 
  - 所有现有记录market_type='futures'
  - 新记录可以指定market_type='spot'

### TC-004: KLine模型市场类型验证
- **测试目标**: 验证market_type字段的合法性检查
- **测试步骤**:
  1. 尝试创建market_type='invalid'的KLine记录
- **预期结果**: 
  - 抛出ValidationError异常
  - 记录未创建

### TC-005: BinanceSpotClient符号标准化
- **测试目标**: 验证符号标准化逻辑
- **测试步骤**:
  1. 调用_normalize_symbol('BTCUSDT')
  2. 调用_normalize_symbol('ETHUSDT')
- **预期结果**: 
  - 'BTCUSDT' → 'BTCUSDT'
  - 'ETHUSDT' → 'ETHUSDT'

### TC-006: BinanceSpotClient获取现货交易对
- **测试目标**: 验证fetch_contracts()功能
- **测试步骤**:
  1. 创建BinanceSpotClient实例
  2. 调用fetch_contracts()
  3. 验证返回结果格式
- **预期结果**: 
  - 返回List[Dict]格式
  - 每个Dict包含symbol、current_price等字段

### TC-007: fetch_spot_contracts命令执行
- **测试目标**: 验证命令成功同步现货交易对
- **测试步骤**:
  1. 执行python manage.py fetch_spot_contracts --exchange binance
  2. 验证SpotContract表中新增记录
- **预期结果**: 
  - 命令执行成功
  - SpotContract表有新增记录
  - 返回同步统计信息

### TC-008: 现货异常检测流程
- **测试目标**: 验证现货异常检测状态机流程
- **测试步骤**:
  1. 创建现货监控记录
  2. 执行scan_volume_traps --market-type spot
  3. 验证状态机流转
- **预期结果**: 
  - 现货监控记录正确处理
  - 状态机流转正常

### TC-009: API市场类型筛选
- **测试目标**: 验证API的market_type筛选功能
- **测试步骤**:
  1. 创建现货和合约监控记录
  2. 发起GET /api/volume-trap/monitors/?market_type=spot
  3. 验证只返回现货记录
- **预期结果**: 
  - API返回200状态码
  - 只包含market_type='spot'的记录

### TC-010: API参数验证
- **测试目标**: 验证API对无效market_type的处理
- **测试步骤**:
  1. 发起GET /api/volume-trap/monitors/?market_type=invalid
- **预期结果**: 
  - 返回400 Bad Request状态码
  - 包含错误信息

---

## 测试执行策略

### 单元测试（Unit Test）
- 目标：验证单个组件的功能
- 覆盖率要求：≥80%
- 执行频率：每次代码变更后

### 集成测试（Integration Test）
- 目标：验证多个组件协同工作
- 覆盖率要求：≥70%
- 执行频率：每日构建

### API测试（API Test）
- 目标：验证API接口的正确性
- 覆盖率要求：100%（所有API端点）
- 执行频率：每次部署前

### 异常测试（Fail-Fast Test）
- 目标：验证异常处理和边界条件
- 覆盖率要求：100%（所有P0功能）
- 执行频率：每次代码变更后

---

## 测试工具与配置

### Django测试框架
```python
# 使用Django的TestCase
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

class SpotContractTest(TestCase):
    """SpotContract模型测试"""
    
    def test_create_spot_contract(self):
        """测试创建现货交易对"""
        # 测试实现...
        
    def test_unique_constraint(self):
        """测试唯一性约束"""
        # 测试实现...
```

### 测试数据准备
```python
# 使用Django的fixtures或factory_boy
from django.contrib.auth import get_user_model

def setup_test_data():
    """设置测试数据"""
    exchange = Exchange.objects.create(
        code='binance',
        name='Binance'
    )
    return exchange
```

### Mock外部依赖
```python
# 使用unittest.mock
from unittest.mock import patch, Mock

@patch('monitor.api_clients.binance.requests.get')
def test_fetch_contracts(mock_get):
    """测试获取现货交易对"""
    mock_response = Mock()
    mock_response.json.return_value = {
        'symbols': [
            {'symbol': 'BTCUSDT', 'status': 'TRADING'},
        ]
    }
    mock_get.return_value = mock_response
    
    client = BinanceSpotClient()
    contracts = client.fetch_contracts()
    
    assert len(contracts) > 0
```

---

## 测试覆盖率要求

| 测试类型 | 覆盖率要求 | 检查点 |
|---------|-----------|-------|
| 单元测试 | ≥80% | 所有类和方法 |
| 集成测试 | ≥70% | 关键业务流程 |
| API测试 | 100% | 所有API端点 |
| 异常测试 | 100% | 所有P0功能的异常路径 |

---

## 测试验收标准

### P0功能测试标准
- [ ] 所有测试用例通过
- [ ] 代码覆盖率达标
- [ ] 异常路径测试覆盖
- [ ] 性能测试达标

### 文档化标准
- [ ] 测试代码有清晰注释
- [ ] 测试用例名称描述清晰
- [ ] 测试数据准备合理

### Fail-Fast验证
- [ ] 无效输入立即抛出异常
- [ ] 异常信息清晰可定位
- [ ] 无静默失败或错误返回

---

**变更历史**:
- v1.0.0 (2025-12-25): 初始版本，完成测试规格设计
