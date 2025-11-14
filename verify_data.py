#!/usr/bin/env python
"""验证 Twitter 集成功能的数据统计"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from twitter.models import TwitterList, Tweet, TwitterAnalysisResult

# 统计信息
print('=' * 60)
print('数据统计')
print('=' * 60)
print(f'Twitter Lists: {TwitterList.objects.count()}')
print(f'Tweets: {Tweet.objects.count()}')
print(f'Analysis Results: {TwitterAnalysisResult.objects.count()}')

# 最近的分析结果
print('\n' + '=' * 60)
print('最近的分析结果')
print('=' * 60)
recent = TwitterAnalysisResult.objects.all()[:3]
for task in recent:
    print(f'任务 ID: {task.task_id}')
    print(f'  状态: {task.get_status_display()}')
    print(f'  推文数: {task.tweet_count}')
    print(f'  成本: ${task.cost_amount:.4f}')
    print(f'  时长: {task.processing_time:.2f}s')
    if task.analysis_result:
        sentiment = task.analysis_result.get('sentiment', {})
        print(f'  情绪: 多头 {sentiment.get("bullish", 0)} | 空头 {sentiment.get("bearish", 0)} | 中性 {sentiment.get("neutral", 0)}')
    print()

print('=' * 60)
