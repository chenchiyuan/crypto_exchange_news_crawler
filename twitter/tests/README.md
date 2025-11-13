# Twitter 应用测试

本目录包含 Twitter 应用的所有测试用例。

## 测试结构

```
twitter/tests/
├── __init__.py
├── test_models.py          # 模型单元测试
├── test_services.py        # 服务层单元测试
└── test_commands.py        # 命令集成测试
```

## 运行测试

```bash
# 运行所有测试
pytest twitter/tests/

# 运行特定测试文件
pytest twitter/tests/test_models.py

# 运行特定测试类
pytest twitter/tests/test_models.py::TestTweetModel

# 运行特定测试方法
pytest twitter/tests/test_models.py::TestTweetModel::test_bulk_create_tweets
```

## 测试覆盖率

```bash
# 生成覆盖率报告
pytest --cov=twitter --cov-report=html twitter/tests/

# 查看覆盖率报告
open htmlcov/index.html
```

## 测试数据

测试使用 Django 的测试数据库（独立于开发数据库），测试完成后自动清理。
