from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from twitter.models import Tag, TwitterList, Tweet, TwitterAnalysisResult


class TestTagModel(TestCase):
    """Tag 模型测试"""

    def setUp(self):
        self.tag = Tag.objects.create(name='Crypto', description='Cryptocurrency related')

    def test_tag_creation(self):
        """测试标签创建"""
        self.assertEqual(self.tag.name, 'Crypto')
        self.assertFalse(self.tag.is_deleted)

    def test_tag_soft_delete(self):
        """测试软删除"""
        self.tag.delete()
        self.assertTrue(self.tag.is_deleted)
        self.assertIsNotNone(self.tag.deleted_at)

    def test_tag_unique_constraint(self):
        """测试唯一约束"""
        with self.assertRaises(Exception):
            Tag.objects.create(name='Crypto')


class TestTwitterListModel(TestCase):
    """TwitterList 模型测试"""

    def setUp(self):
        self.twitter_list = TwitterList.objects.create(
            list_id='1234567890',
            name='Test List',
            description='Test Description',
            status='active'
        )

    def test_twitter_list_creation(self):
        """测试 TwitterList 创建"""
        self.assertEqual(self.twitter_list.list_id, '1234567890')
        self.assertEqual(self.twitter_list.status, 'active')

    def test_get_active_lists(self):
        """测试获取活跃列表"""
        active_lists = TwitterList.get_active_lists()
        self.assertEqual(active_lists.count(), 1)

    def test_create_or_update_list(self):
        """测试创建或更新列表"""
        twitter_list, created = TwitterList.create_or_update_list(
            list_id='9876543210',
            name='New List',
            description='New Description'
        )
        self.assertTrue(created)
        self.assertEqual(twitter_list.list_id, '9876543210')


class TestTweetModel(TestCase):
    """Tweet 模型测试"""

    def setUp(self):
        self.twitter_list = TwitterList.objects.create(
            list_id='1234567890',
            name='Test List'
        )
        self.tweet = Tweet.objects.create(
            tweet_id='tweet123',
            twitter_list=self.twitter_list,
            user_id='user123',
            screen_name='testuser',
            content='Test tweet content',
            tweet_created_at=timezone.now()
        )

    def test_tweet_creation(self):
        """测试推文创建"""
        self.assertEqual(self.tweet.tweet_id, 'tweet123')
        self.assertEqual(self.tweet.screen_name, 'testuser')

    def test_tweet_primary_key_deduplication(self):
        """测试主键去重"""
        with self.assertRaises(Exception):
            Tweet.objects.create(
                tweet_id='tweet123',  # 重复的 tweet_id
                twitter_list=self.twitter_list,
                content='Duplicate tweet',
                tweet_created_at=timezone.now()
            )

    def test_bulk_create_tweets(self):
        """测试批量创建推文"""
        tweet_data_list = [
            {
                'tweet_id': f'tweet{i}',
                'twitter_list': self.twitter_list,
                'user_id': f'user{i}',
                'screen_name': f'user{i}',
                'content': f'Tweet content {i}',
                'tweet_created_at': timezone.now()
            }
            for i in range(10)
        ]

        created_count = Tweet.bulk_create_tweets(tweet_data_list)
        self.assertEqual(created_count, 10)

    def test_get_tweets_in_range(self):
        """测试按时间范围获取推文"""
        now = timezone.now()
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)

        tweets = Tweet.get_tweets_in_range(self.twitter_list, start_time, end_time)
        self.assertEqual(tweets.count(), 1)

    def test_get_engagement_rate(self):
        """测试互动率计算"""
        self.tweet.retweet_count = 10
        self.tweet.favorite_count = 20
        self.tweet.reply_count = 5
        self.tweet.save()

        engagement_rate = self.tweet.get_engagement_rate()
        self.assertEqual(engagement_rate, 35)


class TestTwitterAnalysisResultModel(TestCase):
    """TwitterAnalysisResult 模型测试"""

    def setUp(self):
        self.twitter_list = TwitterList.objects.create(
            list_id='1234567890',
            name='Test List'
        )
        self.task = TwitterAnalysisResult.objects.create(
            twitter_list=self.twitter_list,
            start_time=timezone.now() - timedelta(hours=24),
            end_time=timezone.now(),
            prompt_template='Test prompt template',
            tweet_count=100
        )

    def test_analysis_result_creation(self):
        """测试分析结果创建"""
        self.assertEqual(self.task.twitter_list, self.twitter_list)
        self.assertEqual(self.task.status, TwitterAnalysisResult.STATUS_PENDING)
        self.assertEqual(self.task.tweet_count, 100)
        self.assertIsNotNone(self.task.task_id)

    def test_status_transitions(self):
        """测试状态转换"""
        # pending -> running
        self.task.mark_as_running()
        self.assertEqual(self.task.status, TwitterAnalysisResult.STATUS_RUNNING)

        # running -> completed
        analysis_result = {'sentiment': {'bullish': 50}}
        cost = Decimal('2.5')
        processing_time = 30.5

        self.task.mark_as_completed(analysis_result, cost, processing_time)
        self.assertEqual(self.task.status, TwitterAnalysisResult.STATUS_COMPLETED)
        self.assertEqual(self.task.analysis_result, analysis_result)
        self.assertEqual(self.task.cost_amount, cost)
        self.assertEqual(self.task.processing_time, processing_time)

    def test_mark_as_failed(self):
        """测试标记为失败"""
        error_msg = 'API call failed'
        self.task.mark_as_failed(error_msg, processing_time=10.0)

        self.assertEqual(self.task.status, TwitterAnalysisResult.STATUS_FAILED)
        self.assertEqual(self.task.error_message, error_msg)
        self.assertEqual(self.task.processing_time, 10.0)

    def test_is_terminal_state(self):
        """测试终态判断"""
        self.assertFalse(self.task.is_terminal_state())

        self.task.mark_as_completed({}, Decimal('1.0'), 10.0)
        self.assertTrue(self.task.is_terminal_state())

    def test_can_be_cancelled(self):
        """测试可取消判断"""
        # pending 状态可以取消
        self.assertTrue(self.task.can_be_cancelled())

        # running 状态可以取消
        self.task.mark_as_running()
        self.assertTrue(self.task.can_be_cancelled())

        # completed 状态不可取消
        self.task.mark_as_completed({}, Decimal('1.0'), 10.0)
        self.assertFalse(self.task.can_be_cancelled())

    def test_get_pending_tasks(self):
        """测试获取待处理任务"""
        pending_tasks = TwitterAnalysisResult.get_pending_tasks()
        self.assertEqual(pending_tasks.count(), 1)

        self.task.mark_as_running()
        pending_tasks = TwitterAnalysisResult.get_pending_tasks()
        self.assertEqual(pending_tasks.count(), 0)

    def test_get_completed_tasks(self):
        """测试获取已完成任务"""
        self.task.mark_as_completed({}, Decimal('1.0'), 10.0)

        completed_tasks = TwitterAnalysisResult.get_completed_tasks()
        self.assertEqual(completed_tasks.count(), 1)

        # 测试按 List 筛选
        completed_tasks = TwitterAnalysisResult.get_completed_tasks(
            twitter_list=self.twitter_list
        )
        self.assertEqual(completed_tasks.count(), 1)

