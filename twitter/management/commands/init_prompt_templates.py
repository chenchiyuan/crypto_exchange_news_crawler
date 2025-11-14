"""
初始化 Prompt 模板数据

包括：
1. 通用分析模板（默认）
2. 项目机会分析模板（适用于 1939614372311302186）
3. 市场情绪分析模板（默认）
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from twitter.models import TwitterList, PromptTemplate


class Command(BaseCommand):
    help = '初始化 Prompt 模板数据'

    def handle(self, *args, **options):
        with transaction.atomic():
            # 1. 创建通用分析默认模板
            self.stdout.write('创建通用分析默认模板...')
            general_template = self._create_general_template()

            # 2. 创建项目机会分析模板
            self.stdout.write('创建项目机会分析模板...')
            opportunity_template = self._create_opportunity_template()

            # 3. 创建市场情绪分析模板
            self.stdout.write('创建市场情绪分析默认模板...')
            sentiment_template = self._create_sentiment_template()

            # 4. 关联 List 到对应的模板
            self.stdout.write('关联 Twitter List...')
            self._associate_lists(opportunity_template)

            self.stdout.write(self.style.SUCCESS('\n✓ 所有模板初始化完成！'))

    def _create_general_template(self):
        """创建通用分析默认模板"""
        template, created = PromptTemplate.objects.get_or_create(
            name='通用加密货币分析',
            analysis_type=PromptTemplate.ANALYSIS_TYPE_GENERAL,
            defaults={
                'description': '适用于一般性的加密货币推文分析，提供市场情绪、关键话题等基础分析',
                'template_content': open('twitter/templates/prompts/crypto_analysis.txt', 'r', encoding='utf-8').read(),
                'is_default': True,
                'status': PromptTemplate.STATUS_ACTIVE,
            }
        )

        if created:
            self.stdout.write(f'  ✓ 创建通用分析模板: {template.name}')
        else:
            self.stdout.write(f'  - 通用分析模板已存在: {template.name}')

        return template

    def _create_opportunity_template(self):
        """创建项目机会分析模板（用于 1939614372311302186）"""
        template_content = """你是资深加密投研员 + 量化交易员，请仅基于「推文原文区」内容完成下列任务，禁止凭空猜测或引用外部信息。

输出格式必须严格遵守「交付格式区」的分节、表格与字段顺序。

——————【推文原文区】——————

{tweet_content}

——————【分析要求区】——————

A. 目标资产：BTC、ETH、SOL、SUI、其他山寨（可自行细分）

B. 时间窗口：①观点统计——最近 7 天；②实盘操作——最近 48 小时

C. 逻辑深度：

观点须提取支撑论据，并形成「因→果→验证」闭环
操作须给出：建仓价、短/中期止盈止损、仓位规模（绝对值+占比）、杠杆倍数（若有）
判定"大资金"门槛：单笔 ≥1000 BTC / ≥1 万 ETH / ≥1000 万美元等值
D. 一致性统计：按资产分多空人数及仓位方向，给出占比%并列出主要理由
E. 建议输出：结合统计结果，给出你自己的「进场价区间 / 止盈止损 / 仓位建议（分三档：保守-平衡-激进）」

——————【交付格式区】——————

0️⃣ 多空一致性统计（优先展示结论）

| 资产 | 看多人数 | 看空人数 | 中立人数 | 多空差值(%) | 主流看法 & 核心理由 |

1️⃣ 观点提炼（闭环逻辑表）

| 发布时间 | KOL | 资产 | 观点方向 | 关键论据(摘录) | 推理链路(因→果→验证) | 可信度(高/中/低) |

2️⃣ 操作解析（大资金列表优先）

| 发生时间 | KOL | 资产 & 合约 | 建仓价 | 当前/平仓价 | 多空方向 | 杠杆 | 仓位规模 | 短期 TP/SL | 中期 TP/SL | 备注 |

3️⃣ 即时信号流（≤48h）

• [时间]—@user：方向【多/空/买入/卖出】，资产 XXX，价格 YYY，逻辑 …，置信度【高/中/低】

（按时间倒序罗列，最多 15 条关键信号）

4️⃣ 综合研判 & 交易计划（你的独立观点）

4.1 市场温度计：整体情绪（过热/中性/恐慌） + 资金流向

4.2 资产级别展望：

• BTC —— …

• ETH —— …

• SOL —— …

• SUI —— …

• 山寨热点 —— …

4.3 行动建议（分档位）

| 档位 | 目标资产 | 建议开仓区间 | 止损 | 第一目标位 | 第二目标位 | 建议仓位占比 | 适合人群 |

5️⃣ 风险提示

• 宏观风险 …

• 链上安全 …

• 流动性风险 …

6️⃣ 附录：原始推文索引"""

        template, created = PromptTemplate.objects.get_or_create(
            name='项目机会分析',
            analysis_type=PromptTemplate.ANALYSIS_TYPE_OPPORTUNITY,
            defaults={
                'description': '专为分析项目机会设计的模板，深度挖掘投资机会和交易信号，适用于项目调研和机会发现',
                'template_content': template_content,
                'is_default': True,
                'status': PromptTemplate.STATUS_ACTIVE,
                'max_tweets_per_batch': 50,  # 项目机会分析需要更精细的处理
                'max_cost_per_analysis': 15.0000,  # 允许更高的成本以获得更深入的分析
            }
        )

        if created:
            self.stdout.write(f'  ✓ 创建项目机会分析模板: {template.name}')
        else:
            self.stdout.write(f'  - 项目机会分析模板已存在: {template.name}')

        return template

    def _create_sentiment_template(self):
        """创建市场情绪分析默认模板"""
        template_content = """你是一位专业的加密货币市场情绪分析师，专注于分析推文中的市场情绪和投资者心理。

请分析以下推文内容，重点关注：

1. **情绪指标**：
   - 恐惧贪婪指数
   - 多空比例
   - 恐慌程度

2. **情绪分类**：
   - 极度恐慌（0-25）
   - 恐慌（26-45）
   - 中性（46-55）
   - 贪婪（56-75）
   - 极度贪婪（76-100）

3. **关键信号**：
   - 市场转折点信号
   - 情绪极端化指标
   - 社交媒体热度变化

请按照以下 JSON 格式输出：
{{
  "sentiment_score": 分数(0-100),
  "sentiment_label": "情绪标签",
  "emotional_indicators": {{
    "fear_greed_index": 指数,
    "bull_bear_ratio": "多空比例",
    "panic_level": "恐慌程度"
  }},
  "key_signals": [
    {{
      "signal_type": "信号类型",
      "description": "信号描述",
      "importance": "高/中/低"
    }}
  ],
  "market_mood_analysis": "市场情绪分析文本",
  "trading_implications": {{
    "short_term": "短期交易启示",
    "medium_term": "中期交易启示",
    "long_term": "长期交易启示"
  }}
}}

请开始分析以下推文：
{tweet_content}"""

        template, created = PromptTemplate.objects.get_or_create(
            name='市场情绪分析',
            analysis_type=PromptTemplate.ANALYSIS_TYPE_SENTIMENT,
            defaults={
                'description': '专注于市场情绪和投资者心理分析，提供情绪指标和交易启示',
                'template_content': template_content,
                'is_default': True,
                'status': PromptTemplate.STATUS_ACTIVE,
                'max_tweets_per_batch': 200,  # 情绪分析可以处理更多数据
                'max_cost_per_analysis': 8.0000,
            }
        )

        if created:
            self.stdout.write(f'  ✓ 创建市场情绪分析模板: {template.name}')
        else:
            self.stdout.write(f'  - 市场情绪分析模板已存在: {template.name}')

        return template

    def _associate_lists(self, opportunity_template):
        """关联 List 到对应的模板"""

        # 项目机会分析 List
        list_id = '1939614372311302186'

        try:
            twitter_list = TwitterList.objects.get(list_id=list_id)
            opportunity_template.twitter_lists.add(twitter_list)
            self.stdout.write(f'  ✓ 已关联 List {list_id} 到项目机会分析模板')
        except TwitterList.DoesNotExist:
            # 如果 List 不存在，先创建
            twitter_list, created = TwitterList.objects.get_or_create(
                list_id=list_id,
                defaults={
                    'name': f'List {list_id} - 项目机会分析',
                    'description': '用于分析项目机会的 Twitter List',
                    'status': 'active'
                }
            )
            opportunity_template.twitter_lists.add(twitter_list)

            if created:
                self.stdout.write(f'  ✓ 创建并关联 List {list_id} 到项目机会分析模板')
            else:
                self.stdout.write(f'  ✓ 已关联 List {list_id} 到项目机会分析模板')
