import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from twitter.models import PromptTemplate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '更新专业投研模板，强制 JSON 输出'

    def handle(self, *args, **options):
        """更新专业投研模板，明确要求 JSON 输出"""

        # 专业投研分析模板内容（强制 JSON）
        template_content = """你是资深加密投研员 + 量化交易员，请仅基于「推文原文区」内容完成下列任务，禁止凭空猜测或引用外部信息。

【重要】：输出格式必须是严格的 JSON，不要包含任何 Markdown 表格或其他格式标记。

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

必须返回严格的 JSON 格式，包含以下键：

{
  "consensus_statistics": [
    {
      "asset": "资产名称",
      "bullish_count": 看多人数,
      "bearish_count": 看空人数,
      "neutral_count": 中立人数,
      "bullish_bearish_diff_percent": 多空差值百分比,
      "main_view": "主流看法",
      "core_reason": "核心理由"
    }
  ],
  "viewpoints": [
    {
      "publish_time": "发布时间",
      "kol": "KOL名称",
      "asset": "资产",
      "view_direction": "观点方向(多/空/中立)",
      "key_evidence": "关键论据",
      "reasoning_chain": "推理链路(因→果→验证)",
      "credibility": "可信度(高/中/低)"
    }
  ],
  "operations": [
    {
      "time": "发生时间",
      "kol": "KOL",
      "asset": "资产",
      "entry_price": "建仓价",
      "current_price": "当前价",
      "direction": "多空方向",
      "leverage": "杠杆倍数",
      "position_size": "仓位规模",
      "short_term_tp_sl": "短期止盈止损",
      "medium_term_tp_sl": "中期止盈止损",
      "note": "备注"
    }
  ],
  "signals": [
    {
      "time": "时间",
      "user": "@用户",
      "direction": "方向(多/空/买入/卖出)",
      "asset": "资产",
      "price": "价格",
      "logic": "逻辑",
      "confidence": "置信度(高/中/低)"
    }
  ],
  "comprehensive_analysis": {
    "market_thermometer": {
      "overall_sentiment": "整体情绪(过热/中性/恐慌)",
      "capital_flow": "资金流向"
    },
    "asset_outlook": {
      "BTC": "BTC分析",
      "ETH": "ETH分析",
      "SOL": "SOL分析",
      "SUI": "SUI分析",
      "altcoins": "山寨热点"
    },
    "action_plan": [
      {
        "tier": "档位(保守/平衡/激进)",
        "target_asset": "目标资产",
        "entry_range": "建议开仓区间",
        "stop_loss": "止损",
        "first_target": "第一目标位",
        "second_target": "第二目标位",
        "position_ratio": "建议仓位占比",
        "suitable_for": "适合人群"
      }
    ]
  },
  "risk_alerts": {
    "macro_risk": "宏观风险",
    "onchain_security": "链上安全",
    "liquidity_risk": "流动性风险"
  },
  "appendix": {
    "tweet_indexes": [
      "编号-推文链接"
    ]
  },
  "analysis_metadata": {
    "total_tweets": 推文总数,
    "analysis_timestamp": "分析时间戳",
    "time_range": "时间范围",
    "tokens_used": "使用的token数",
    "actual_cost": "实际成本",
    "processing_time_ms": "处理时间(毫秒)",
    "model": "使用的模型"
  }
}

输出必须是有效的 JSON，不要包含任何其他文本或格式。"""

        try:
            with transaction.atomic():
                # 获取并更新模板
                template = PromptTemplate.objects.get(
                    name='专业投研分析模板',
                    analysis_type=PromptTemplate.ANALYSIS_TYPE_TRADING
                )

                template.template_content = template_content
                template.save()

                self.stdout.write(self.style.SUCCESS('✅ 成功更新专业投研分析模板'))
                self.stdout.write(f'\n模板详情:')
                self.stdout.write(f'  名称: {template.name}')
                self.stdout.write(f'  类型: {template.get_analysis_type_display()}')
                self.stdout.write(f'  模板长度: {len(template_content)} 字符')
                self.stdout.write(self.style.SUCCESS('\n✨ 专业投研模板已更新为 JSON 格式！'))

        except Exception as e:
            logger.exception('更新模板失败')
            self.stdout.write(self.style.ERROR(f'❌ 更新失败: {e}'))
            raise
