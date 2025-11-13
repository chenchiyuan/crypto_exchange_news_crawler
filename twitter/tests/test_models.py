from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from twitter.models import Tag, TwitterList, Tweet


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
