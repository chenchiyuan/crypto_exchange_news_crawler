"""
提示词加载服务

负责从文件加载提示词模板，支持 List ID 与提示词文件的映射配置
"""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class PromptLoader:
    """
    提示词加载器

    功能：
    1. 从配置文件读取 List ID 到提示词文件的映射
    2. 从文件加载提示词内容
    3. 支持动态更新配置
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化提示词加载器

        Args:
            config_path: 配置文件路径，默认使用 twitter/prompts/prompt_mappings.json
        """
        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent.parent
        self.config_path = config_path or str(self.project_root / 'twitter' / 'prompts' / 'prompt_mappings.json')
        self.prompts_dir = self.project_root / 'twitter' / 'prompts'
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"✅ 提示词配置已加载: {self.config_path}")
        except Exception as e:
            logger.error(f"❌ 加载提示词配置失败: {e}")
            self.config = {"mappings": {}, "default": {}}

    def get_prompt_for_list(self, list_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 List ID 获取提示词配置

        Args:
            list_id: Twitter List ID

        Returns:
            提示词配置字典，包含 prompt_file、description、analysis_type 等信息
        """
        # 首先检查直接映射
        if list_id in self.config.get('mappings', {}):
            mapping = self.config['mappings'][list_id]
            logger.info(f"✅ 找到 List {list_id} 的提示词配置: {mapping['prompt_file']}")
            return mapping

        # 使用默认配置
        default_config = self.config.get('default', {})
        if default_config:
            logger.info(f"ℹ️ List {list_id} 未配置，使用默认提示词: {default_config.get('prompt_file', 'general_analysis.txt')}")
            return default_config

        logger.warning(f"⚠️ List {list_id} 未找到提示词配置")
        return None

    def load_prompt_content(self, prompt_file: str) -> Optional[str]:
        """
        从文件加载提示词内容

        Args:
            prompt_file: 提示词文件名（如 "pro_investment_analysis.txt"）

        Returns:
            提示词内容字符串
        """
        prompt_path = self.prompts_dir / prompt_file

        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"✅ 提示词已加载: {prompt_file} ({len(content)} 字符)")
            return content
        except FileNotFoundError:
            logger.error(f"❌ 提示词文件未找到: {prompt_file}")
            return None
        except Exception as e:
            logger.error(f"❌ 加载提示词文件失败 {prompt_file}: {e}")
            return None

    def get_prompt_for_list_with_content(self, list_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 List ID 获取提示词配置和内容

        Args:
            list_id: Twitter List ID

        Returns:
            字典，包含配置和提示词内容
        """
        config = self.get_prompt_for_list(list_id)
        if not config:
            return None

        prompt_file = config.get('prompt_file')
        if not prompt_file:
            logger.error(f"❌ List {list_id} 的配置中缺少 prompt_file")
            return None

        content = self.load_prompt_content(prompt_file)
        if not content:
            return None

        # 返回完整信息
        result = config.copy()
        result['prompt_file'] = prompt_file
        result['content'] = content
        result['list_id'] = list_id

        logger.info(f"✅ List {list_id} 提示词准备完成: {prompt_file}")
        return result

    def list_available_prompts(self) -> Dict[str, Any]:
        """
        列出所有可用的提示词

        Returns:
            可用提示词列表
        """
        prompts = {}
        for list_id, config in self.config.get('mappings', {}).items():
            prompts[list_id] = {
                'prompt_file': config.get('prompt_file'),
                'description': config.get('description', ''),
                'analysis_type': config.get('analysis_type', ''),
                'cost_limit': config.get('cost_limit', 0),
                'batch_size': config.get('batch_size', 0)
            }

        # 添加默认配置
        default = self.config.get('default', {})
        if default:
            prompts['default'] = {
                'prompt_file': default.get('prompt_file'),
                'description': default.get('description', ''),
                'analysis_type': default.get('analysis_type', ''),
                'cost_limit': default.get('cost_limit', 0),
                'batch_size': default.get('batch_size', 0)
            }

        return prompts

    def reload_config(self):
        """重新加载配置文件"""
        logger.info("🔄 重新加载提示词配置...")
        self._load_config()
        logger.info("✅ 提示词配置已更新")


# 全局实例
_prompt_loader = None


def get_prompt_loader() -> PromptLoader:
    """
    获取全局提示词加载器实例

    Returns:
        PromptLoader 实例
    """
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader


def get_prompt_for_list(list_id: str) -> Optional[str]:
    """
    获取指定 List 的提示词内容

    Args:
        list_id: Twitter List ID

    Returns:
        提示词内容字符串
    """
    loader = get_prompt_loader()
    result = loader.get_prompt_for_list_with_content(list_id)
    return result.get('content') if result else None


def get_prompt_config_for_list(list_id: str) -> Optional[Dict[str, Any]]:
    """
    获取指定 List 的提示词配置

    Args:
        list_id: Twitter List ID

    Returns:
        配置字典
    """
    loader = get_prompt_loader()
    return loader.get_prompt_for_list_with_content(list_id)
