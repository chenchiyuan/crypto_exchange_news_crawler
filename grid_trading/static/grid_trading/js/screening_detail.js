/**
 * 合约详情页 - K线图渲染逻辑
 * Feature: 007-contract-detail-page
 *
 * 采用分批渲染策略优化性能:
 * - Stage 1 (<500ms): 渲染K线蜡烛图
 * - Stage 2 (<1.5s): 叠加EMA均线
 * - Stage 3 (<2s): 叠加信号标记（如果有）
 */

(function() {
    'use strict';

    // 全局状态
    let chart = null;
    let candlestickSeries = null;
    let currentInterval = '4h';
    let chartData = null;

    // 从window获取合约数据
    const contractData = window.CONTRACT_DATA || {};
    const symbol = contractData.symbol;
    const date = contractData.date;
    const currentPrice = contractData.currentPrice;

    // DOM元素
    const chartContainer = document.getElementById('chart');
    const loadingEl = document.getElementById('chartLoading');
    const warningBanner = document.getElementById('warningBanner');
    const periodButtons = document.querySelectorAll('.period-btn');

    /**
     * 初始化图表
     */
    function initChart() {
        if (!chartContainer) {
            console.error('Chart container not found');
            return;
        }

        // 创建图表实例
        chart = LightweightCharts.createChart(chartContainer, {
            layout: {
                background: { color: '#0b0e11' },
                textColor: '#8492a6',
            },
            grid: {
                vertLines: { color: '#2b313a' },
                horzLines: { color: '#2b313a' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#2b313a',
            },
            timeScale: {
                borderColor: '#2b313a',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        // 创建蜡烛图系列（国际标准配色：绿涨红跌）
        candlestickSeries = chart.addCandlestickSeries({
            upColor: '#26a69a',        // 绿色（上涨）
            downColor: '#ef5350',      // 红色（下跌）
            borderUpColor: '#26a69a',
            borderDownColor: '#ef5350',
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        });

        // 响应式调整
        window.addEventListener('resize', () => {
            if (chart) {
                chart.applyOptions({
                    width: chartContainer.clientWidth
                });
            }
        });

        console.log('✓ Chart initialized');
    }

    /**
     * 显示警告横幅
     */
    function showWarning(message) {
        if (warningBanner) {
            warningBanner.textContent = message;
            warningBanner.style.display = 'block';
        }
    }

    /**
     * 隐藏警告横幅
     */
    function hideWarning() {
        if (warningBanner) {
            warningBanner.style.display = 'none';
        }
    }

    /**
     * 显示/隐藏加载指示器
     */
    function setLoading(isLoading) {
        if (loadingEl) {
            loadingEl.style.display = isLoading ? 'flex' : 'none';
        }
    }

    /**
     * 从API获取K线数据
     */
    async function fetchKlineData(interval, limit, includeSignals = true) {
        let url = `/api/screening/${date}/${symbol}/klines/?interval=${interval}`;
        if (limit) url += `&limit=${limit}`;
        if (includeSignals) url += `&include_signals=true`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`✓ Fetched ${data.klines?.length || 0} klines for ${interval}`);
            if (includeSignals && data.rule_signals) {
                console.log(`✓ Fetched ${data.rule_signals.length} rule signals`);
            }
            return data;
        } catch (error) {
            console.error('Failed to fetch kline data:', error);
            throw error;
        }
    }

    /**
     * Stage 1: 渲染K线蜡烛图 (<500ms)
     */
    async function renderStage1(data) {
        const startTime = performance.now();

        if (!data.klines || data.klines.length === 0) {
            throw new Error('No kline data available');
        }

        // 处理警告信息
        if (data.warnings && data.warnings.length > 0) {
            showWarning(data.warnings[0]);
        } else {
            hideWarning();
        }

        // 转换K线数据格式
        const candleData = data.klines.map(k => ({
            time: Math.floor(k.open_time / 1000), // 转换为秒级时间戳
            open: k.open,
            high: k.high,
            low: k.low,
            close: k.close,
        }));

        // 设置数据到蜡烛图系列
        candlestickSeries.setData(candleData);

        // 自动缩放到合适范围
        chart.timeScale().fitContent();

        const elapsed = performance.now() - startTime;
        console.log(`✓ Stage 1 completed in ${elapsed.toFixed(0)}ms (target: <500ms)`);

        return data;
    }

    /**
     * Stage 2: 叠加EMA均线 (<1.5s cumulative)
     */
    async function renderStage2(data) {
        const startTime = performance.now();

        if (!data.ema99 || !data.ema20) {
            console.warn('EMA data not available');
            return;
        }

        // EMA99均线（蓝色）
        const ema99Series = chart.addLineSeries({
            color: '#2196F3',
            lineWidth: 2,
            title: 'EMA99',
            priceLineVisible: false,
            lastValueVisible: false,
        });

        const ema99Data = data.klines.map((k, i) => ({
            time: Math.floor(k.open_time / 1000),
            value: data.ema99[i]
        })).filter(d => d.value !== null && d.value !== undefined);

        ema99Series.setData(ema99Data);

        // EMA20均线（橙色）
        const ema20Series = chart.addLineSeries({
            color: '#FF9800',
            lineWidth: 2,
            title: 'EMA20',
            priceLineVisible: false,
            lastValueVisible: false,
        });

        const ema20Data = data.klines.map((k, i) => ({
            time: Math.floor(k.open_time / 1000),
            value: data.ema20[i]
        })).filter(d => d.value !== null && d.value !== undefined);

        ema20Series.setData(ema20Data);

        // 标注当前价格水平线
        if (currentPrice) {
            candlestickSeries.createPriceLine({
                price: currentPrice,
                color: '#2962FF',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: '当前价格',
            });
        }

        const elapsed = performance.now() - startTime;
        console.log(`✓ Stage 2 completed in ${elapsed.toFixed(0)}ms (target: <1000ms for stage 2 alone)`);
    }

    /**
     * Stage 3: 叠加VPA信号和规则标记 (<2s cumulative)
     * Feature: 007-contract-detail-page, US4
     * Tasks: T039-T042
     */
    async function renderStage3(data) {
        const startTime = performance.now();

        if (!data.rule_signals && !data.vpa_signals) {
            console.log('✓ Stage 3 skipped (no signals data)');
            return;
        }

        // T039-T040: 渲染VPA信号标记
        if (data.vpa_signals && data.vpa_signals.length > 0) {
            const vpaMarkers = data.vpa_signals.map(signal => {
                // 根据信号类型设置图标和颜色
                const markerConfig = getVPAMarkerConfig(signal.type);

                return {
                    time: signal.time,
                    position: signal.position || 'belowBar',  // 'belowBar' 或 'aboveBar'
                    color: markerConfig.color,
                    shape: markerConfig.shape,  // 'circle', 'square', 'arrowUp', 'arrowDown'
                    text: markerConfig.text,
                    size: 1,
                };
            });

            candlestickSeries.setMarkers(vpaMarkers);
            console.log(`✓ Rendered ${vpaMarkers.length} VPA signals`);
        }

        // T041-T042: 渲染规则6/7触发标记
        if (data.rule_signals && data.rule_signals.length > 0) {
            const ruleMarkers = data.rule_signals.map(signal => {
                const markerConfig = getRuleMarkerConfig(signal.rule_id, signal);

                return {
                    time: signal.time,
                    position: markerConfig.position,
                    color: markerConfig.color,
                    shape: markerConfig.shape,
                    text: getRuleTooltipText(signal),
                    size: 2,  // 规则信号更大更显眼
                };
            });

            // 如果已有VPA标记，需要合并
            if (data.vpa_signals && data.vpa_signals.length > 0) {
                const existingMarkers = candlestickSeries.markers();
                const allMarkers = [...existingMarkers, ...ruleMarkers];
                candlestickSeries.setMarkers(allMarkers);
            } else {
                candlestickSeries.setMarkers(ruleMarkers);
            }

            console.log(`✓ Rendered ${ruleMarkers.length} rule signals`);
        }

        const elapsed = performance.now() - startTime;
        console.log(`✓ Stage 3 completed in ${elapsed.toFixed(0)}ms`);
    }

    /**
     * 获取VPA信号的Marker配置
     * T040: VPA模式图标样式
     */
    function getVPAMarkerConfig(vpaType) {
        const configs = {
            'stopping_volume': {
                color: '#FFA726',  // 橙色
                shape: 'circle',
                text: '急刹车'
            },
            'golden_needle': {
                color: '#FFD54F',  // 金色
                shape: 'circle',
                text: '金针探底'
            },
            'battering_ram': {
                color: '#EF5350',  // 红色
                shape: 'circle',
                text: '攻城锤'
            },
            'bullish_engulfing': {
                color: '#FF7043',  // 深橙色
                shape: 'circle',
                text: '阳包阴'
            }
        };

        return configs[vpaType] || {
            color: '#9E9E9E',
            shape: 'circle',
            text: 'VPA'
        };
    }

    /**
     * 获取规则信号的Marker配置
     * T041: 规则6/7标记样式
     */
    function getRuleMarkerConfig(ruleId, signal) {
        if (ruleId === 6) {
            // 规则6: 止盈信号 - 绿色向上箭头
            return {
                position: 'belowBar',
                color: '#26a69a',  // 绿色（做多止盈）
                shape: 'arrowUp',
                text: `[6] 止盈: ${signal.vpa_signal}+${signal.tech_signal}`
            };
        } else if (ruleId === 7) {
            // 规则7: 止损信号 - 红色向下箭头
            return {
                position: 'aboveBar',
                color: '#ef5350',  // 红色（做空止损）
                shape: 'arrowDown',
                text: `[7] 止损: ${signal.vpa_signal}+${signal.tech_signal}`
            };
        } else {
            // 其他规则 - 蓝色方块
            return {
                position: 'inBar',
                color: '#2962FF',
                shape: 'square',
                text: `[${ruleId}] ${signal.rule_name}`
            };
        }
    }

    /**
     * 生成规则信号的Tooltip文本
     * T042: Marker Tooltip详细信息
     */
    function getRuleTooltipText(signal) {
        const parts = [];

        // 规则编号和名称
        parts.push(`[${signal.rule_id}] ${signal.rule_name}`);

        // 规则6/7的详细信息
        if (signal.rule_id === 6) {
            parts.push(`VPA: ${signal.vpa_signal}`);
            parts.push(`技术: ${signal.tech_signal}`);
            if (signal.rsi_value) {
                parts.push(`RSI=${signal.rsi_value.toFixed(1)}`);
            }
            parts.push(`周期: ${signal.timeframe}`);
        } else if (signal.rule_id === 7) {
            parts.push(`VPA: ${signal.vpa_signal}`);
            parts.push(`技术: ${signal.tech_signal}`);
            if (signal.rsi_value) {
                parts.push(`RSI=${signal.rsi_value.toFixed(1)}`);
            }
            if (signal.rsi_slope) {
                parts.push(`斜率=${signal.rsi_slope.toFixed(2)}`);
            }
            parts.push(`周期: ${signal.timeframe}`);
        }

        return parts.join(' | ');
    }

    /**
     * 完整渲染流程：分批执行3个阶段
     */
    async function renderChart(interval) {
        try {
            setLoading(true);

            // 获取K线数据
            const data = await fetchKlineData(interval);
            chartData = data;

            // Stage 1: 渲染K线（优先级最高）
            await renderStage1(data);

            // Stage 2: 叠加均线（延迟渲染，让用户先看到K线）
            setTimeout(async () => {
                await renderStage2(data);
            }, 50);

            // Stage 3: 叠加信号（最后渲染）
            setTimeout(async () => {
                await renderStage3(data);
            }, 100);

            setLoading(false);

        } catch (error) {
            console.error('Chart rendering failed:', error);
            setLoading(false);

            // 显示错误信息
            if (chartContainer) {
                chartContainer.innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #ef5350;">
                        <div style="font-size: 18px; margin-bottom: 8px;">⚠ K线图加载失败</div>
                        <div style="font-size: 14px; color: #8492a6;">${error.message}</div>
                        <button onclick="location.reload()" style="margin-top: 16px; padding: 8px 16px; background: #2962ff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                            刷新页面重试
                        </button>
                    </div>
                `;
            }
        }
    }

    /**
     * 切换时间周期
     */
    function switchInterval(interval) {
        if (interval === currentInterval) return;

        currentInterval = interval;

        // 更新按钮状态
        periodButtons.forEach(btn => {
            if (btn.dataset.interval === interval) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 清空当前图表数据
        if (chart) {
            chart.remove();
            chart = null;
            candlestickSeries = null;
        }

        // 重新初始化并渲染
        initChart();
        renderChart(interval);

        console.log(`✓ Switched to ${interval} interval`);
    }

    /**
     * 绑定周期切换按钮事件
     */
    function bindEvents() {
        periodButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const interval = btn.dataset.interval;
                switchInterval(interval);
            });
        });
    }

    /**
     * 页面加载完成后初始化
     */
    function init() {
        console.log('=== Screening Detail Chart Init ===');
        console.log('Symbol:', symbol);
        console.log('Date:', date);
        console.log('Current Price:', currentPrice);

        if (!symbol || !date) {
            console.error('Missing contract data');
            return;
        }

        // 初始化图表
        initChart();

        // 绑定事件
        bindEvents();

        // 渲染默认周期（4h）
        renderChart(currentInterval);
    }

    // 等待DOM加载完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
