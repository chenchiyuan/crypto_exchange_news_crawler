# 🚀 调试功能快速使用指南

## ⚡ 一分钟快速开始

### 1. 运行分析并保存调试信息

```bash
python manage.py run_analysis 1939614372311302186 --hours 24 --save-prompt
```

### 2. 查看保存的文件

```bash
# 找到最新的调试文件
ls -lt debug_prompts/ | head -1

# 查看文件内容
cat debug_prompts/prompt_*.txt
```

### 3. 验证保存的内容

查看文件是否包含三个部分：

```
【1. 提示词模板】     ✓
【2. 推文原文内容】   ✓
【3. 最终发送给AI的完整Prompt】  ✓
```

## 🎯 实际调试示例

### 场景：AI返回多空统计为0，但实际有观点

```bash
# 1. 运行分析保存调试
python manage.py run_analysis 1939614372311302186 --save-prompt

# 2. 查看推文原文
grep -A 5 "推文6.*@NachoTrades" debug_prompts/prompt_*.txt

# 3. 查看提示词的数据一致性要求
grep -A 3 "数据一致性要求" debug_prompts/prompt_*.txt

# 4. 查看AI返回的即时信号流
grep -A 10 "即时信号流" debug_prompts/prompt_*.txt
```

### 快速检查关键内容

```bash
# 检查推文数量
grep "推文数量:" debug_prompts/prompt_*.txt

# 检查提示词长度
wc -l debug_prompts/prompt_*.txt

# 查看特定推文内容
sed -n '/推文6/,/推文7/p' debug_prompts/prompt_*.txt

# 检查数据一致性要求是否在提示词中
grep -c "数据一致性要求" debug_prompts/prompt_*.txt
```

## 📊 文件结构说明

```
debug_prompts/
└── prompt_{task_id}_{timestamp}.txt

文件内容:
├── 文件头 (Task ID, 保存时间)
├── 【1. 提示词模板】
│   ├── 角色设定
│   ├── 分析要求 (A-F)
│   └── 交付格式 (0️⃣-6️⃣)
├── 【2. 推文原文内容】
│   ├── 推文1: @user (时间)
│   │   内容: ...
│   │   互动: 👍🔄💬
│   │   Tweet ID: ...
│   └── 推文2: ...
└── 【3. 最终发送给AI的完整Prompt】
    ├── 完整提示词模板
    ├── 完整推文内容
    └── AI返回的JSON结果
```

## 🔍 常见问题诊断

### 问题1：AI遗漏观点

**检查**：
```bash
# 查看推文原文是否有明确观点
grep -i "shorting\|buy\|sell\|看多\|看空" debug_prompts/prompt_*.txt

# 检查提示词是否要求统计
grep -A 5 "0️⃣ 多空一致性统计" debug_prompts/prompt_*.txt
```

### 问题2：数据不一致

**检查**：
```bash
# 查看提示词是否包含数据一致性要求
grep "数据一致性要求" debug_prompts/prompt_*.txt

# 查看AI返回的各部分数据
jq '.["0️⃣ 多空一致性统计"]' (从文件提取JSON部分)
jq '.["3️⃣ 即时信号流"]' (从文件提取JSON部分)
```

### 问题3：推文内容缺失

**检查**：
```bash
# 查看推文数量
grep "^[0-9]\+\. \[@\]" debug_prompts/prompt_*.txt | wc -l

# 查看特定推文是否存在
grep "推文6.*@NachoTrades" debug_prompts/prompt_*.txt
```

## 🛠️ 实用命令

### 查看最新调试文件
```bash
# 最新的文件
latest_file=$(ls -t debug_prompts/prompt_*.txt | head -1)
cat $latest_file
```

### 对比两次分析
```bash
# 获取两个文件
file1=$(ls -t debug_prompts/prompt_*.txt | sed -n '2p')
file2=$(ls -t debug_prompts/prompt_*.txt | sed -n '1p')

# 对比提示词
diff <(sed -n '/【1. 提示词模板】/,/【2. 推文原文内容】/p' $file1) \
     <(sed -n '/【1. 提示词模板】/,/【2. 推文原文内容】/p' $file2)

# 对比推文数量
diff <(grep "^[0-9]\+\. \[@\]" $file1) \
     <(grep "^[0-9]\+\. \[@\]" $file2)
```

### 提取AI返回的JSON
```bash
# 从调试文件提取JSON结果
sed -n '/^{/,/^}/p' debug_prompts/prompt_*.txt > /tmp/result.json
cat /tmp/result.json | jq .
```

## 💡 调试技巧

1. **先看提示词**：确认数据一致性要求是否存在
2. **再看推文**：确认推文包含明确观点
3. **后看结果**：对比AI返回与预期
4. **对比分析**：多次运行对比差异

## ⚠️ 注意事项

1. 文件会占用空间，记得定期清理：
   ```bash
   find debug_prompts/ -name "*.txt" -mtime +7 -delete
   ```

2. 包含敏感信息，不要分享调试文件

3. 干跑模式更适合调试：
   ```bash
   python manage.py run_analysis <id> --dry-run --save-prompt
   ```

---

**快速检查清单**：
- [ ] 提示词包含数据一致性要求
- [ ] 推文原文格式化正确
- [ ] AI返回格式符合预期
- [ ] 多空统计数据不为0（如果有观点）
