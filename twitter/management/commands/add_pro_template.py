import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from twitter.models import PromptTemplate, TwitterList

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '添加专业投研分析模板'

    def handle(self, *args, **options):
        """创建专业投研分析模板"""

        # 专业投研分析模板内容
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

6️⃣ 附录：原始推文索引

(编号-推文链接)

输出格式必须是严格的 JSON 格式，不要包含任何其他文本或 Markdown 表格。"""

        try:
            with transaction.atomic():
                # 创建专业投研模板
                template, created = PromptTemplate.objects.update_or_create(
                    name='专业投研分析模板',
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_TRADING,
                    defaults={
                        'template_content': template_content,
                        'description': '专业加密投研分析模板，包含多空统计、观点提炼、操作解析、信号流、交易计划和风险提示',
                        'status': 'active',
                        'max_tweets_per_batch': 100,  # 减少批次大小以提高质量
                        'max_cost_per_analysis': 5.0000,  # 允许更高成本进行深度分析
                        'is_default': True  # 设为默认模板
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS('✅ 成功创建专业投研分析模板'))
                else:
                    self.stdout.write(self.style.SUCCESS('✅ 成功更新专业投研分析模板'))

                self.stdout.write(f'\n模板详情:')
                self.stdout.write(f'  名称: {template.name}')
                self.stdout.write(f'  类型: {template.get_analysis_type_display()}')
                self.stdout.write(f'  状态: {template.get_status_display()}')
                self.stdout.write(f'  默认模板: {template.is_default}')
                self.stdout.write(f'  批次大小: {template.max_tweets_per_batch}')
                self.stdout.write(f'  成本上限: ${template.max_cost_per_analysis}')

                # 关联到指定 List
                list_id = '1939614372311302186'
                twitter_list, _ = TwitterList.objects.get_or_create(
                    list_id=list_id,
                    defaults={
                        'name': f'List {list_id} - 专业投研',
                        'description': '专业投研分析 List',
                        'status': 'active'
                    }
                )

                # 添加关联
                template.twitter_lists.add(twitter_list)

                self.stdout.write(f'\n✅ 模板已关联到 List: {list_id}')
                self.stdout.write(self.style.SUCCESS('\n✨ 专业投研分析模板配置完成！'))

        except Exception as e:
            logger.exception('创建模板失败')
            self.stdout.write(self.style.ERROR(f'❌ 创建模板失败: {e}'))
            raise
