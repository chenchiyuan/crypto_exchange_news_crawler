"""
HTML报告生成器 - 简化筛选结果网页展示
"""

from typing import List
from datetime import datetime
from pathlib import Path

from grid_trading.services.simple_scoring import SimpleScore


class HTMLReportGenerator:
    """简化筛选结果HTML报告生成器"""

    def __init__(self):
        self.template = self._get_template()

    def _get_template(self) -> str:
        """获取HTML模板"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>做空网格标的筛选报告 - 简化版</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 32px;
            margin-bottom: 10px;
            font-weight: 700;
        }

        .header p {
            font-size: 16px;
            opacity: 0.9;
        }

        .info-bar {
            background: #f8f9fa;
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #e9ecef;
        }

        .info-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .info-label {
            font-weight: 600;
            color: #495057;
        }

        .info-value {
            color: #667eea;
            font-weight: 700;
        }

        .filter-panel {
            background: #e7f3ff;
            padding: 20px 40px;
            border-left: 4px solid #007bff;
            margin: 20px 40px;
            border-radius: 8px;
        }

        .filter-panel h3 {
            color: #004085;
            margin-bottom: 15px;
            font-size: 18px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .filter-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }

        .filter-item {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .filter-item label {
            font-weight: 600;
            color: #004085;
            font-size: 14px;
        }

        .filter-item input {
            padding: 8px 12px;
            border: 2px solid #b8daff;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.2s;
        }

        .filter-item input:focus {
            outline: none;
            border-color: #007bff;
        }

        .filter-item input::placeholder {
            color: #6c757d;
        }

        .filter-actions {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: #007bff;
            color: white;
        }

        .btn-primary:hover {
            background: #0056b3;
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .btn-secondary:hover {
            background: #545b62;
        }

        .filter-stats {
            color: #004085;
            font-size: 14px;
            font-weight: 600;
        }

        .legend {
            background: #fff3cd;
            padding: 20px 40px;
            border-left: 4px solid #ffc107;
            margin: 20px 40px;
            border-radius: 8px;
        }

        .legend h3 {
            color: #856404;
            margin-bottom: 15px;
            font-size: 18px;
        }

        .legend-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }

        .legend-item {
            background: white;
            padding: 12px;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .legend-item strong {
            color: #667eea;
            display: block;
            margin-bottom: 5px;
        }

        .legend-item small {
            color: #6c757d;
            line-height: 1.4;
        }

        .table-container {
            padding: 40px;
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }

        thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        th {
            padding: 16px 12px;
            text-align: left;
            font-weight: 600;
            white-space: nowrap;
        }

        th.sortable {
            cursor: pointer;
            user-select: none;
            position: relative;
            padding-right: 20px;
        }

        th.sortable:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        th.sortable::after {
            content: '⇅';
            position: absolute;
            right: 5px;
            opacity: 0.5;
        }

        tbody tr {
            border-bottom: 1px solid #e9ecef;
            transition: background-color 0.2s;
        }

        tbody tr:hover {
            background-color: #f8f9fa;
        }

        tbody tr.rank-top3 {
            background: linear-gradient(90deg, #fff3cd 0%, white 100%);
        }

        td {
            padding: 14px 12px;
        }

        .rank-cell {
            font-weight: 700;
            font-size: 18px;
            color: #667eea;
        }

        .rank-top3 .rank-cell {
            color: #ffc107;
            font-size: 20px;
        }

        .symbol-cell {
            font-weight: 700;
            color: #212529;
            font-size: 15px;
        }

        .price-cell {
            color: #495057;
            font-family: 'Courier New', monospace;
        }

        .metric-cell {
            font-family: 'Courier New', monospace;
            text-align: right;
        }

        .score-cell {
            font-weight: 600;
            text-align: right;
        }

        .score-high {
            color: #28a745;
        }

        .score-medium {
            color: #ffc107;
        }

        .score-low {
            color: #dc3545;
        }

        .index-cell {
            font-weight: 700;
            font-size: 16px;
            text-align: right;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .cvd-yes {
            color: #28a745;
            font-weight: 700;
        }

        .cvd-no {
            color: #6c757d;
        }

        .grid-cell {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            color: #6c757d;
        }

        .footer {
            background: #f8f9fa;
            padding: 30px 40px;
            text-align: center;
            color: #6c757d;
            border-top: 1px solid #e9ecef;
        }

        .footer p {
            margin-bottom: 10px;
        }

        .footer .timestamp {
            font-family: 'Courier New', monospace;
            color: #495057;
            font-weight: 600;
        }

        /* 响应式设计 */
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }

            .header {
                padding: 20px;
            }

            .header h1 {
                font-size: 24px;
            }

            .info-bar {
                flex-direction: column;
                gap: 10px;
            }

            .table-container {
                padding: 20px;
            }

            table {
                font-size: 12px;
            }

            th, td {
                padding: 8px 6px;
            }
        }

        /* 打印样式 */
        @media print {
            body {
                background: white;
                padding: 0;
            }

            .container {
                box-shadow: none;
            }

            tbody tr:hover {
                background-color: transparent;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 做空网格标的筛选报告</h1>
            <p>基于VDR、KER、OVR、CVD四维指标的简化评分模型</p>
        </div>

        <div class="info-bar">
            <div class="info-item">
                <span class="info-label">生成时间:</span>
                <span class="info-value timestamp">{{timestamp}}</span>
            </div>
            <div class="info-item">
                <span class="info-label">候选标的:</span>
                <span class="info-value">{{total_count}} 个</span>
            </div>
            <div class="info-item">
                <span class="info-label">评分模型:</span>
                <span class="info-value">简化4维指标</span>
            </div>
        </div>

        <div class="filter-panel">
            <h3>🔍 实时筛选</h3>
            <div class="filter-grid">
                <div class="filter-item">
                    <label for="filterVdr">VDR (波动率-位移比) ≥</label>
                    <input type="number" id="filterVdr" placeholder="例如: 10" step="0.1">
                </div>
                <div class="filter-item">
                    <label for="filterKer">KER (考夫曼效率比) ≤</label>
                    <input type="number" id="filterKer" placeholder="例如: 0.3" step="0.01" min="0" max="1">
                </div>
                <div class="filter-item">
                    <label for="filterAmplitude">15分钟振幅(%) ≥</label>
                    <input type="number" id="filterAmplitude" placeholder="例如: 300" step="10">
                </div>
                <div class="filter-item">
                    <label for="filterFunding">年化资金费率(%) ≥</label>
                    <input type="number" id="filterFunding" placeholder="例如: 50" step="5">
                </div>
            </div>
            <div class="filter-actions">
                <button class="btn btn-primary" onclick="applyFilters()">应用筛选</button>
                <button class="btn btn-secondary" onclick="resetFilters()">重置</button>
                <span class="filter-stats" id="filterStats">显示 {{total_count}} / {{total_count}} 个标的</span>
            </div>
        </div>

        <div class="legend">
            <h3>📊 指标说明</h3>
            <div class="legend-grid">
                <div class="legend-item">
                    <strong>VDR (波动率-位移比)</strong>
                    <small>震荡性纯净度。VDR越高，价格越是在区间内反复波动。理想值 >10 表示完美震荡。</small>
                </div>
                <div class="legend-item">
                    <strong>KER (考夫曼效率比)</strong>
                    <small>趋势vs震荡判断。KER越低，震荡性越强。理想值 <0.3 表示低效率波动，适合网格。</small>
                </div>
                <div class="legend-item">
                    <strong>OVR (持仓/成交比)</strong>
                    <small>杠杆拥挤度。理想值0.5-1.5，过高(>2.0)表示杠杆过度拥挤，清算风险大。</small>
                </div>
                <div class="legend-item">
                    <strong>CVD (背离检测)</strong>
                    <small>资金面信号。✓表示检测到熊市背离(价格上涨但买盘减弱)，是做空的优势信号。</small>
                </div>
                <div class="legend-item">
                    <strong>15m振幅(%)</strong>
                    <small>短期波动强度。最近100根15分钟K线的振幅百分比累加。数值越大表示短期波动越频繁激烈。</small>
                </div>
                <div class="legend-item">
                    <strong>年化资金费率(%)</strong>
                    <small>基于过去24小时平均资金费率年化。正值表示做空有利(多头支付给空头)，负值表示做空不利(空头支付给多头)。</small>
                </div>
                <div class="legend-item">
                    <strong>综合指数 (Composite Index)</strong>
                    <small>加权评分 = VDR(40%) + KER(30%) + OVR(20%) + CVD(10%)。越接近1.0越适合做空网格。</small>
                </div>
            </div>
        </div>

        <div class="table-container">
            <table id="resultsTable">
                <thead>
                    <tr>
                        <th class="sortable" data-sort="rank">排名</th>
                        <th class="sortable" data-sort="symbol">标的</th>
                        <th class="sortable" data-sort="price">当前价格</th>
                        <th class="sortable" data-sort="vdr">VDR</th>
                        <th class="sortable" data-sort="vdr_score">VDR得分</th>
                        <th class="sortable" data-sort="ker">KER</th>
                        <th class="sortable" data-sort="ker_score">KER得分</th>
                        <th class="sortable" data-sort="ovr">OVR</th>
                        <th class="sortable" data-sort="ovr_score">OVR得分</th>
                        <th class="sortable" data-sort="cvd">CVD背离</th>
                        <th class="sortable" data-sort="cvd_score">CVD得分</th>
                        <th class="sortable" data-sort="amplitude">15m振幅(%)</th>
                        <th class="sortable" data-sort="annual_funding">年化资金费率(%)</th>
                        <th class="sortable" data-sort="open_interest">OI(USDT)</th>
                        <th class="sortable" data-sort="fdv">FDV(USD)</th>
                        <th class="sortable" data-sort="oi_fdv_ratio">OI/FDV(%)</th>
                        <th class="sortable" data-sort="has_spot">有现货</th>
                        <th class="sortable" data-sort="money_flow_large_net">大单净流入</th>
                        <th class="sortable" data-sort="money_flow_strength">资金流强度</th>
                        <th class="sortable" data-sort="money_flow_large_dominance">大单主导度</th>
                        <th class="sortable" data-sort="index">综合指数</th>
                        <th>推荐网格上限</th>
                        <th>推荐网格下限</th>
                    </tr>
                </thead>
                <tbody>
                    {{table_rows}}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p><strong>评分规则:</strong></p>
            <p>VDR得分: ≥10满分 | KER得分: ≤0.1满分 | OVR得分: 0.5-1.5满分 | CVD得分: 有背离满分</p>
            <p class="timestamp">Generated by Grid Trading Screening System</p>
        </div>
    </div>

    <script>
        // 表格排序功能
        const table = document.getElementById('resultsTable');
        const headers = table.querySelectorAll('th.sortable');
        let currentSort = { column: 'index', direction: 'desc' };

        headers.forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.sort;
                const direction = currentSort.column === column && currentSort.direction === 'desc' ? 'asc' : 'desc';
                sortTable(column, direction);
                currentSort = { column, direction };
            });
        });

        function sortTable(column, direction) {
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            rows.sort((a, b) => {
                let aVal = getCellValue(a, column);
                let bVal = getCellValue(b, column);

                if (column === 'symbol') {
                    return direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                } else {
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                    return direction === 'asc' ? aVal - bVal : bVal - aVal;
                }
            });

            rows.forEach(row => tbody.appendChild(row));
        }

        function getCellValue(row, column) {
            const columnIndex = {
                'rank': 0,
                'symbol': 1,
                'price': 2,
                'vdr': 3,
                'vdr_score': 4,
                'ker': 5,
                'ker_score': 6,
                'ovr': 7,
                'ovr_score': 8,
                'cvd': 9,
                'cvd_score': 10,
                'amplitude': 11,
                'annual_funding': 12,
                'open_interest': 13,
                'fdv': 14,
                'oi_fdv_ratio': 15,
                'has_spot': 16,
                'index': 17,
            };

            const cell = row.cells[columnIndex[column]];
            return cell.textContent.replace(/[^0-9.-]/g, '');
        }

        // 筛选功能
        function applyFilters() {
            const vdrFilter = parseFloat(document.getElementById('filterVdr').value);
            const kerFilter = parseFloat(document.getElementById('filterKer').value);
            const amplitudeFilter = parseFloat(document.getElementById('filterAmplitude').value);
            const fundingFilter = parseFloat(document.getElementById('filterFunding').value);

            const tbody = table.querySelector('tbody');
            const rows = tbody.querySelectorAll('tr');

            let visibleCount = 0;
            const totalCount = rows.length;

            rows.forEach(row => {
                // 获取各列的值
                const vdr = parseFloat(row.cells[3].textContent);
                const ker = parseFloat(row.cells[5].textContent);
                const amplitude = parseFloat(row.cells[11].textContent.replace('%', ''));
                const funding = parseFloat(row.cells[12].textContent.replace('%', ''));

                // 应用筛选条件 (VDR/振幅/费率用>=，KER用<=)
                let shouldShow = true;

                if (!isNaN(vdrFilter) && vdr < vdrFilter) {
                    shouldShow = false;
                }

                // KER使用<=逻辑（KER越低越好）
                if (!isNaN(kerFilter) && ker > kerFilter) {
                    shouldShow = false;
                }

                if (!isNaN(amplitudeFilter) && amplitude < amplitudeFilter) {
                    shouldShow = false;
                }

                if (!isNaN(fundingFilter) && funding < fundingFilter) {
                    shouldShow = false;
                }

                // 显示/隐藏行
                if (shouldShow) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            // 更新统计信息
            document.getElementById('filterStats').textContent = `显示 ${visibleCount} / ${totalCount} 个标的`;
        }

        function resetFilters() {
            // 清空输入框
            document.getElementById('filterVdr').value = '';
            document.getElementById('filterKer').value = '';
            document.getElementById('filterAmplitude').value = '';
            document.getElementById('filterFunding').value = '';

            // 显示所有行
            const tbody = table.querySelector('tbody');
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {
                row.style.display = '';
            });

            // 更新统计信息
            document.getElementById('filterStats').textContent = `显示 ${rows.length} / ${rows.length} 个标的`;
        }

        // 支持回车键触发筛选
        document.addEventListener('DOMContentLoaded', function() {
            const filterInputs = document.querySelectorAll('.filter-item input');
            filterInputs.forEach(input => {
                input.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        applyFilters();
                    }
                });
            });
        });
    </script>
</body>
</html>"""

    def _generate_table_row(self, rank: int, score: SimpleScore) -> str:
        """生成表格行HTML"""
        data = score.to_dict()

        # 判断得分等级
        def score_class(score_val):
            if score_val >= 70:
                return 'score-high'
            elif score_val >= 50:
                return 'score-medium'
            else:
                return 'score-low'

        # Top3标记
        row_class = 'rank-top3' if rank <= 3 else ''

        return f"""
                    <tr class="{row_class}">
                        <td class="rank-cell">{rank}</td>
                        <td class="symbol-cell">{data['symbol']}</td>
                        <td class="price-cell">${data['price']:,.2f}</td>
                        <td class="metric-cell">{data['vdr']}</td>
                        <td class="score-cell {score_class(data['vdr_score'])}">{data['vdr_score']}</td>
                        <td class="metric-cell">{data['ker']}</td>
                        <td class="score-cell {score_class(data['ker_score'])}">{data['ker_score']}</td>
                        <td class="metric-cell">{data['ovr']}</td>
                        <td class="score-cell {score_class(data['ovr_score'])}">{data['ovr_score']}</td>
                        <td class="metric-cell {'cvd-yes' if data['cvd'] == '✓' else 'cvd-no'}">{data['cvd']}</td>
                        <td class="score-cell {score_class(data['cvd_score'])}">{data['cvd_score']}</td>
                        <td class="metric-cell">{data['amplitude_sum_15m']:.2f}%</td>
                        <td class="metric-cell" style="color: {'#28a745' if data['annual_funding_rate'] > 0 else '#dc3545'};">{data['annual_funding_rate']:.2f}%</td>
                        <td class="metric-cell">${data['open_interest'] / 1000000:.2f}M</td>
                        <td class="metric-cell">{'$' + f"{data['fdv'] / 1000000:.2f}" + 'M' if data['fdv'] > 0 else '-'}</td>
                        <td class="metric-cell">{f"{data['oi_fdv_ratio']:.2f}%" if data['oi_fdv_ratio'] > 0 else '-'}</td>
                        <td class="metric-cell {'cvd-yes' if data['has_spot'] else 'cvd-no'}">{'✓' if data['has_spot'] else '✗'}</td>
                        <td class="metric-cell" style="color: {'#28a745' if data['money_flow_large_net'] > 0 else '#dc3545'};">${data['money_flow_large_net'] / 1000:.1f}K</td>
                        <td class="metric-cell" style="color: {'#28a745' if data['money_flow_strength'] > 0.55 else ('#dc3545' if data['money_flow_strength'] < 0.45 else '#6c757d')};">{data['money_flow_strength']:.3f}</td>
                        <td class="metric-cell">{data['money_flow_large_dominance']:.3f}</td>
                        <td class="index-cell">{data['composite_index']:.4f}</td>
                        <td class="grid-cell">${data['grid_upper']:,.2f}</td>
                        <td class="grid-cell">${data['grid_lower']:,.2f}</td>
                    </tr>"""

    def generate_report(
        self,
        results: List[SimpleScore],
        output_path: str,
    ) -> str:
        """
        生成HTML报告

        Args:
            results: 评分结果列表(已按综合指数降序排列)
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        # 生成表格行
        table_rows = []
        for rank, score in enumerate(results, 1):
            table_rows.append(self._generate_table_row(rank, score))

        # 填充模板
        html = self.template.replace('{{timestamp}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        html = html.replace('{{total_count}}', str(len(results)))
        html = html.replace('{{table_rows}}', '\n'.join(table_rows))

        # 写入文件
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html, encoding='utf-8')

        return str(output_file)
