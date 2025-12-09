"""
价格预警通知服务
Price Alert Notifier Service

封装AlertPushService，提供价格监控专用的消息格式化和推送功能
Feature: 001-price-alert-monitor
"""
import logging
import requests
from typing import Dict, Optional
from decimal import Decimal
from django.utils import timezone
from grid_trading.django_models import SystemConfig

logger = logging.getLogger("grid_trading")


class PriceAlertNotifier:
    """
    价格预警通知服务
    封装汇成推送接口，提供价格监控专用的消息格式化
    """

    # 规则ID到名称的映射
    RULE_NAMES = {
        1: "7天价格新高",
        2: "7天价格新低",
        3: "价格触及MA20",
        4: "价格触及MA99",
        5: "价格达到分布区间极值"
    }

    def __init__(self, token: Optional[str] = None, channel: Optional[str] = None):
        """
        初始化价格预警通知服务

        Args:
            token: 汇成推送Token，如果不提供则从SystemConfig读取
            channel: 推送渠道，如果不提供则从SystemConfig读取
        """
        self.api_url = "https://huicheng.powerby.com.cn/api/simple/alert/"

        # 从SystemConfig读取配置
        self.token = token or SystemConfig.get_value(
            'huicheng_push_token',
            '6020867bc6334c609d4f348c22f90f14'
        )
        self.channel = channel or SystemConfig.get_value(
            'huicheng_push_channel',
            'price_monitor'
        )

    def format_price(self, price: Decimal) -> str:
        """
        格式化价格显示

        Args:
            price: 价格(Decimal类型)

        Returns:
            格式化后的价格字符串，如"$45,123.45"
        """
        return f"${float(price):,.2f}"

    def send_price_alert(
        self,
        symbol: str,
        rule_id: int,
        current_price: Decimal,
        extra_info: Optional[Dict] = None
    ) -> bool:
        """
        发送价格触发告警

        Args:
            symbol: 合约代码(如BTCUSDT)
            rule_id: 规则ID (1-5)
            current_price: 当前价格
            extra_info: 额外信息字典，可包含:
                - ma20: MA20值
                - ma99: MA99值
                - high_7d: 7天最高价
                - low_7d: 7天最低价
                - percentile_upper: 90%分位上限
                - percentile_lower: 90%分位下限
                - kline_link: K线图链接

        Returns:
            True: 推送成功
            False: 推送失败

        Example:
            notifier = PriceAlertNotifier()
            success = notifier.send_price_alert(
                symbol='BTCUSDT',
                rule_id=1,
                current_price=Decimal('45000.50'),
                extra_info={'high_7d': '44800.00', 'low_7d': '42000.00'}
            )
        """
        rule_name = self.RULE_NAMES.get(rule_id, f"规则{rule_id}")
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

        # 格式化标题
        title = f"🔔 价格触发预警 - {symbol}"

        # 格式化内容
        content_lines = [
            f"合约: {symbol}",
            f"触发规则: {rule_name}",
            f"当前价格: {self.format_price(current_price)}",
            f"触发时间: {timestamp}",
        ]

        # 添加额外信息
        if extra_info:
            content_lines.append("")  # 空行分隔

            # MA相关信息
            if 'ma20' in extra_info:
                ma20 = extra_info['ma20']
                content_lines.append(f"MA20: {self.format_price(Decimal(str(ma20)))}")

            if 'ma99' in extra_info:
                ma99 = extra_info['ma99']
                content_lines.append(f"MA99: {self.format_price(Decimal(str(ma99)))}")

            # 7天高低价
            if 'high_7d' in extra_info:
                high_7d = extra_info['high_7d']
                content_lines.append(f"7天最高: {self.format_price(Decimal(str(high_7d)))}")

            if 'low_7d' in extra_info:
                low_7d = extra_info['low_7d']
                content_lines.append(f"7天最低: {self.format_price(Decimal(str(low_7d)))}")

            # 价格分布区间
            if 'percentile_upper' in extra_info and 'percentile_lower' in extra_info:
                upper = extra_info['percentile_upper']
                lower = extra_info['percentile_lower']
                content_lines.append("")
                content_lines.append(f"价格分布区间(90%):")
                content_lines.append(f"  上限: {self.format_price(Decimal(str(upper)))}")
                content_lines.append(f"  下限: {self.format_price(Decimal(str(lower)))}")

            # K线图链接
            if 'kline_link' in extra_info:
                content_lines.append("")
                content_lines.append(f"K线图: {extra_info['kline_link']}")

        content = "\n".join(content_lines)

        # 发送推送
        return self._send_request(title, content)

    def _send_request(self, title: str, content: str) -> bool:
        """
        发送HTTP请求到汇成推送接口

        Args:
            title: 推送标题
            content: 推送内容

        Returns:
            True: 推送成功
            False: 推送失败
        """
        try:
            # 构建payload
            payload = {
                "token": self.token,
                "title": title,
                "content": content,
                "channel": self.channel
            }

            # 发送POST请求
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=5
            )

            # 检查响应
            if response.status_code == 200:
                result = response.json()
                # 汇成API返回格式: {"errcode": 0, "msg": "", "data": {"is_successful": true}}
                if result.get('errcode') == 0:
                    logger.info(f"✓ 推送成功: {title}")
                    return True
                else:
                    error_msg = result.get('msg', 'Unknown error')
                    logger.error(f"✗ 推送失败: {error_msg}")
                    return False
            else:
                logger.error(f"✗ 推送失败: HTTP {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            logger.error(f"✗ 推送超时: {title}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ 推送异常: {title}, 错误: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ 推送未知错误: {title}, 错误: {e}")
            return False

    def test_connection(self) -> bool:
        """
        测试推送服务连接

        Returns:
            True: 连接正常
            False: 连接失败

        Example:
            notifier = PriceAlertNotifier()
            if notifier.test_connection():
                print("推送服务连接正常")
        """
        test_title = "🔧 价格监控系统测试"
        test_content = f"这是一条测试消息\n测试时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"

        logger.info("发送测试推送...")
        return self._send_request(test_title, test_content)

    def send_batch_alert(self, alerts: Dict[str, list]) -> bool:
        """
        批量发送价格告警（按合约汇总）

        Args:
            alerts: 按合约汇总的告警字典，格式:
                {
                    'BTCUSDT': [
                        {'rule_id': 1, 'rule_name': '...', 'price': Decimal('...'), 'extra_info': {...}, 'volatility': 5.2},
                        {'rule_id': 2, 'rule_name': '...', 'price': Decimal('...'), 'extra_info': {...}, 'volatility': 5.2}
                    ],
                    'ETHUSDT': [...]
                }

        Returns:
            True: 推送成功
            False: 推送失败
        """
        if not alerts:
            logger.warning("批量推送: 无告警数据")
            return False

        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

        # 统计信息
        total_contracts = len(alerts)
        total_triggers = sum(len(triggers) for triggers in alerts.values())

        # 按波动率排序（从高到低）
        sorted_alerts = sorted(
            alerts.items(),
            key=lambda x: x[1][0].get('volatility', 0),
            reverse=True
        )

        # 分类合约：上涨触发 vs 下跌触发
        uptrend_alerts = {}
        downtrend_alerts = {}

        for symbol, triggers in sorted_alerts:
            # 判断触发类型：包含规则1(新高)或规则3/4(MA)且不含规则2(新低) -> 上涨
            has_high = any(t['rule_id'] in [1, 3, 4] for t in triggers)
            has_low = any(t['rule_id'] == 2 for t in triggers)

            # 检查规则5的极值类型
            rule5_triggers = [t for t in triggers if t['rule_id'] == 5]
            rule5_is_high = False
            if rule5_triggers:
                extra_info = rule5_triggers[0].get('extra_info', {})
                current_price = rule5_triggers[0]['price']
                percentile_upper = extra_info.get('percentile_upper')
                if percentile_upper:
                    rule5_is_high = float(current_price) >= float(percentile_upper)

            # 分类逻辑：优先看规则1/2，其次看规则5
            if has_high and not has_low:
                uptrend_alerts[symbol] = triggers
            elif has_low:
                downtrend_alerts[symbol] = triggers
            elif rule5_triggers:
                if rule5_is_high:
                    uptrend_alerts[symbol] = triggers
                else:
                    downtrend_alerts[symbol] = triggers

        # 格式化标题: 监控: allo📈-mon📉-{hour-min}
        # 提取上涨和下跌合约的代币名（去掉USDT后缀）
        up_tokens = [symbol.replace('USDT', '').lower() for symbol in uptrend_alerts.keys()]
        down_tokens = [symbol.replace('USDT', '').lower() for symbol in downtrend_alerts.keys()]

        # 拼接代币名（最多3个，超过用...）
        up_str = "-".join(up_tokens[:3])
        if len(up_tokens) > 3:
            up_str += "..."

        down_str = "-".join(down_tokens[:3])
        if len(down_tokens) > 3:
            down_str += "..."

        # 获取当前时间（小时:分钟）
        time_str = timezone.now().strftime('%H:%M')

        # 组合标题
        title_parts = []
        if up_str:
            title_parts.append(f"{up_str}📈")
        if down_str:
            title_parts.append(f"{down_str}📉")

        tokens_str = "-".join(title_parts) if title_parts else "无触发"
        title = f"监控: {tokens_str}-{time_str}"

        # 格式化内容
        content_lines = [f"检测时间：{timestamp}", ""]

        # ========== 上涨触发部分 ==========
        if uptrend_alerts:
            content_lines.append("🟢↑ 上涨触发（突破/接近上沿）")

            # 统计波动率分布
            high_vol_count = sum(1 for _, t in uptrend_alerts.items() if t[0].get('volatility', 0) >= 100)
            med_vol_count = len(uptrend_alerts) - high_vol_count

            if high_vol_count > 0:
                content_lines.append("涨势合约集中在高波动区，注意追涨风险与回踩确认。")
            else:
                content_lines.append("涨势合约波动适中，关注量能与趋势延续性。")
            content_lines.append("")

            for symbol, triggers in uptrend_alerts.items():
                volatility = triggers[0].get('volatility', 0)

                # 波动率标记
                if volatility >= 100.0:
                    vol_mark = "🔥"
                elif volatility >= 70.0:
                    vol_mark = "⚡"
                else:
                    vol_mark = "📊"

                content_lines.append(f"{vol_mark} {symbol}（波动率 {volatility:.2f}%）")
                content_lines.append(f"当前价：{self.format_price(triggers[0]['price'])}")
                content_lines.append("触发：")

                # 格式化触发规则
                rule_lines, quick_judge = self._format_triggers(triggers, "up")
                content_lines.extend(rule_lines)

                # 快速判断
                content_lines.append(f"快速判断：{quick_judge}")
                content_lines.append("")

        # ========== 下跌触发部分 ==========
        if downtrend_alerts:
            content_lines.append("🔴↓ 下跌触发（破位/接近下沿）")

            # 统计波动率分布
            high_vol_count = sum(1 for _, t in downtrend_alerts.items() if t[0].get('volatility', 0) >= 100)

            if high_vol_count > 0:
                content_lines.append("下跌合约部分高波动，警惕加速下行风险。")
            else:
                content_lines.append("下跌合约集中在中波动区，优先考虑风险控制与反弹确认。")
            content_lines.append("")

            for symbol, triggers in downtrend_alerts.items():
                volatility = triggers[0].get('volatility', 0)

                # 波动率标记
                if volatility >= 100.0:
                    vol_mark = "🔥"
                elif volatility >= 70.0:
                    vol_mark = "⚡"
                else:
                    vol_mark = "📊"

                content_lines.append(f"{vol_mark} {symbol}（波动率 {volatility:.2f}%）")
                content_lines.append(f"当前价：{self.format_price(triggers[0]['price'])}")
                content_lines.append("触发：")

                # 格式化触发规则
                rule_lines, quick_judge = self._format_triggers(triggers, "down")
                content_lines.extend(rule_lines)

                # 快速判断
                content_lines.append(f"快速判断：{quick_judge}")
                content_lines.append("")

        # ========== 速览提示 ==========
        content_lines.append("✅ 速览提示")

        if uptrend_alerts:
            up_symbols = "、".join(list(uptrend_alerts.keys())[:3])
            if len(uptrend_alerts) > 3:
                up_symbols += f"等{len(uptrend_alerts)}个"
            content_lines.append(f"上涨：{up_symbols}（接近或突破上沿，留意回踩与量能）")

        if downtrend_alerts:
            down_symbols = "、".join(list(downtrend_alerts.keys())[:3])
            if len(downtrend_alerts) > 3:
                down_symbols += f"等{len(downtrend_alerts)}个"
            content_lines.append(f"下跌：{down_symbols}（触及下沿并创新低，控制风险为先）")

        content_lines.append("通用动作：强势看延续，弱势看止跌；极值处交易需缩短决策周期与加严风控范围。")

        content = "\n".join(content_lines)

        # 发送推送
        return self._send_request(title, content)

    def _format_triggers(self, triggers: list, direction: str) -> tuple:
        """
        格式化触发规则并生成快速判断

        Args:
            triggers: 触发规则列表
            direction: 方向 ('up' 或 'down')

        Returns:
            (rule_lines, quick_judge): 规则行列表和快速判断文本
        """
        rule_lines = []
        judgments = []

        for trigger in triggers:
            rule_id = trigger['rule_id']
            extra_info = trigger.get('extra_info', {})
            current_price = trigger['price']

            if rule_id == 1:
                # 7天价格新高
                high_7d = extra_info.get('high_7d', '')
                low_7d = extra_info.get('low_7d', '')
                rule_lines.append(
                    f"[1] 7天价格新高（4h）｜7天高 {self.format_price(Decimal(str(high_7d)))}｜低 {self.format_price(Decimal(str(low_7d)))}"
                )
                judgments.append("创7日新高")

            elif rule_id == 2:
                # 7天价格新低
                high_7d = extra_info.get('high_7d', '')
                low_7d = extra_info.get('low_7d', '')
                rule_lines.append(
                    f"[2] 7天价格新低（4h）｜7天高 {self.format_price(Decimal(str(high_7d)))}｜低 {self.format_price(Decimal(str(low_7d)))}"
                )
                judgments.append("创7日新低")

            elif rule_id == 3:
                # MA20
                ma20 = extra_info.get('ma20', '')
                rule_lines.append(
                    f"[3] 触及MA20｜MA20 {self.format_price(Decimal(str(ma20)))}"
                )
                judgments.append("触及MA20")

            elif rule_id == 4:
                # MA99
                ma99 = extra_info.get('ma99', '')
                rule_lines.append(
                    f"[4] 触及MA99｜MA99 {self.format_price(Decimal(str(ma99)))}"
                )
                judgments.append("触及MA99")

            elif rule_id == 5:
                # 价格分布极值
                percentile_upper = extra_info.get('percentile_upper')
                percentile_lower = extra_info.get('percentile_lower')

                if percentile_upper and percentile_lower:
                    upper = Decimal(str(percentile_upper))
                    lower = Decimal(str(percentile_lower))

                    # 判断极值类型
                    if current_price >= upper:
                        extreme_type = "极高"
                        judgments.append("处分布尾部")
                    else:
                        extreme_type = "极低"
                        judgments.append("处下沿")

                    rule_lines.append(
                        f"[5] 分布区间90%极值（{extreme_type}）｜区间 {self.format_price(lower)}–{self.format_price(upper)}"
                    )

        # 生成快速判断
        if direction == "up":
            if "创7日新高" in judgments and "处分布尾部" in judgments:
                quick_judge = "位于上沿并创7日新高，动能强但处分布尾部，谨防回落。"
            elif "处分布尾部" in judgments:
                quick_judge = "接近上沿极值，波动大，关注是否放量延续。"
            elif "创7日新高" in judgments:
                quick_judge = "突破7日高点，关注量能配合与回踩支撑。"
            elif "触及MA20" in judgments or "触及MA99" in judgments:
                quick_judge = "触及均线，观察是否有效突破。"
            else:
                quick_judge = "接近阻力位，关注突破确认。"
        else:  # down
            if "创7日新低" in judgments and "处下沿" in judgments:
                quick_judge = "创7日新低并处下沿，短线承压，谨慎抄底。"
            elif "创7日新低" in judgments:
                quick_judge = "贴近下沿且破位，新低后易出现弱反弹或续跌。"
            elif "处下沿" in judgments:
                quick_judge = "下沿与新低共振，优先防守，等待止跌结构。"
            elif "触及MA20" in judgments or "触及MA99" in judgments:
                quick_judge = "触及均线支撑，观察能否企稳。"
            else:
                quick_judge = "接近支撑位，关注止跌信号。"

        return rule_lines, quick_judge


def send_alert(
    symbol: str,
    rule_id: int,
    current_price: Decimal,
    extra_info: Optional[Dict] = None
) -> bool:
    """
    便捷函数: 发送价格告警

    这是一个便捷的模块级函数，内部创建PriceAlertNotifier实例

    Args:
        symbol: 合约代码
        rule_id: 规则ID
        current_price: 当前价格
        extra_info: 额外信息

    Returns:
        True: 推送成功
        False: 推送失败

    Example:
        from grid_trading.services.alert_notifier import send_alert

        send_alert(
            symbol='BTCUSDT',
            rule_id=1,
            current_price=Decimal('45000.50')
        )
    """
    notifier = PriceAlertNotifier()
    return notifier.send_price_alert(symbol, rule_id, current_price, extra_info)
