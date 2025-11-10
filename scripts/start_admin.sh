#!/bin/bash
# Django Admin 快速启动脚本

echo "=================================================="
echo "🎯 Django Admin 管理后台"
echo "=================================================="
echo ""

# 检查是否已创建超级用户
if [ ! -f ".admin_setup" ]; then
    echo "📝 首次使用，需要创建超级用户账号"
    echo ""
    python manage.py createsuperuser

    if [ $? -eq 0 ]; then
        touch .admin_setup
        echo ""
        echo "✅ 超级用户创建成功！"
    else
        echo ""
        echo "❌ 超级用户创建失败"
        exit 1
    fi
else
    echo "✓ 超级用户已存在"
fi

echo ""
echo "🚀 启动开发服务器..."
echo ""
echo "访问地址: http://127.0.0.1:8000/admin/"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "=================================================="
echo ""

python manage.py runserver
