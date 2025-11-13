from django.db import models
from typing import List, Dict
from .soft_delete import SoftDeleteModel
from .twitter_list import TwitterList


class Tweet(SoftDeleteModel):
    """
    推文模型

    存储从 Twitter List 获取的推文数据，支持去重和关联查询。
    """

    tweet_id = models.CharField(
        max_length=50,
        primary_key=True,
        verbose_name='推文 ID',
        help_text='Twitter 推文的唯一标识符'
    )
    twitter_list = models.ForeignKey(
        TwitterList,
        on_delete=models.CASCADE,
        related_name='tweets',
        db_index=True,
        verbose_name='Twitter List',
        help_text='推文所属的 Twitter List'
    )
    user_id = models.CharField(
        max_length=50,
        db_index=True,
        default='',
        verbose_name='用户 ID',
        help_text='推文作者的 Twitter 用户 ID'
    )
    screen_name = models.CharField(
        max_length=100,
        db_index=True,
        default='unknown',
        verbose_name='用户名',
        help_text='推文作者的 Twitter 用户名 (@xxx)'
    )
    user_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='显示名称',
        help_text='推文作者的显示名称'
    )
    content = models.TextField(
        verbose_name='推文内容',
        help_text='推文的完整文本内容'
    )
    tweet_created_at = models.DateTimeField(
        db_index=True,
        verbose_name='推文发布时间',
        help_text='推文在 Twitter 上的发布时间'
    )
    retweet_count = models.IntegerField(
        default=0,
        verbose_name='转发数',
        help_text='推文的转发次数'
    )
    favorite_count = models.IntegerField(
        default=0,
        verbose_name='点赞数',
        help_text='推文的点赞次数'
    )
    reply_count = models.IntegerField(
        default=0,
        verbose_name='回复数',
        help_text='推文的回复次数'
    )

    class Meta:
        db_table = 'twitter_tweets'
        ordering = ['-tweet_created_at']
        verbose_name = '推文'
        verbose_name_plural = '推文'
        indexes = [
            models.Index(fields=['twitter_list', 'tweet_created_at'], name='twitter_tweet_list_time_idx'),
            models.Index(fields=['user_id'], name='twitter_tweet_user_id_idx'),
            models.Index(fields=['screen_name'], name='twitter_tweet_screen_name_idx'),
            models.Index(fields=['tweet_created_at'], name='twitter_tweet_created_at_idx'),
        ]

    def __str__(self):
        return f"Tweet {self.tweet_id} by @{self.screen_name}"

    @classmethod
    def get_tweets_in_range(cls, twitter_list, start_time, end_time):
        """获取指定时间范围内的推文"""
        return cls.objects.filter(
            twitter_list=twitter_list,
            tweet_created_at__gte=start_time,
            tweet_created_at__lte=end_time
        ).order_by('tweet_created_at')

    @classmethod
    def bulk_create_tweets(cls, tweet_data_list: List[Dict]) -> int:
        """
        批量创建推文，自动去重

        Args:
            tweet_data_list: 推文数据字典列表

        Returns:
            int: 成功创建的推文数量
        """
        tweet_objects = [cls(**data) for data in tweet_data_list]
        # ignore_conflicts=True 会忽略主键冲突，实现自动去重
        cls.objects.bulk_create(tweet_objects, ignore_conflicts=True)
        # 返回成功创建的数量（需要查询确认）
        created_ids = [obj.tweet_id for obj in tweet_objects]
        return cls.objects.filter(tweet_id__in=created_ids).count()

    def get_engagement_rate(self):
        """
        计算推文的互动率

        Returns:
            float: 互动率 (转发+点赞+回复)
        """
        return self.retweet_count + self.favorite_count + self.reply_count

    def is_popular(self, threshold=100):
        """
        判断推文是否热门

        Args:
            threshold: 互动数阈值

        Returns:
            bool: 是否热门
        """
        return self.get_engagement_rate() >= threshold
