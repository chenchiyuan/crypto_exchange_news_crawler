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
    async function fetchKlineData(interval, limit) {
        const url = `/grid_trading/api/screening/${date}/${symbol}/klines/?interval=${interval}${limit ? '&limit=' + limit : ''}`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`✓ Fetched ${data.klines?.length || 0} klines for ${interval}`);
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
     * 当前版本为占位符，US4阶段实现
     */
    async function renderStage3(data) {
        const startTime = performance.now();

        // TODO: 实现VPA信号和规则6/7标记（US4）
        // if (data.vpa_signals) { ... }
        // if (data.rule_signals) { ... }

        const elapsed = performance.now() - startTime;
        console.log(`✓ Stage 3 completed in ${elapsed.toFixed(0)}ms (placeholder)`);
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
