#!/usr/bin/env python
"""创建超级用户脚本"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from django.contrib.auth.models import User

username = 'admin'
email = 'admin@example.com'
password = 'admin123'

# 检查用户是否已存在
if User.objects.filter(username=username).exists():
    print(f'用户 {username} 已存在')
    user = User.objects.get(username=username)
    user.set_password(password)
    user.save()
    print(f'已更新用户密码')
else:
    user = User.objects.create_superuser(username=username, email=email, password=password)
    print(f'已创建超级用户: {username}')
    print(f'密码: {password}')
    print(f'邮箱: {email}')

print('\n请访问 http://localhost:8000/admin/ 使用以上凭据登录')
