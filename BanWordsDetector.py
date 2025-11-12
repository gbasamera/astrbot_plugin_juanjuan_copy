# BanWordsDetector.py
import re
import time
from datetime import datetime
from typing import Dict, Tuple, Optional
import json
import os

# 配置数据存储路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BAN_WORDS_FILE = os.path.join(DATA_DIR, "ban_words.json")
USER_SCORE_FILE = os.path.join(DATA_DIR, "user_scores.json")

class BanWordsDetector:
    def __init__(self):
        self.ban_words = {}
        self.user_scores = {}  # 存储用户累计权重分数
        self.threshold = 10    # 默认阈值，达到此分数触发禁言
        
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # 加载数据
        self._load_data()
    
    def _load_data(self):
        """加载违禁词和用户分数数据"""
        try:
            # 加载违禁词
            if os.path.exists(BAN_WORDS_FILE):
                with open(BAN_WORDS_FILE, "r", encoding="utf-8") as f:
                    self.ban_words = json.load(f)
            
            # 加载用户分数
            if os.path.exists(USER_SCORE_FILE):
                with open(USER_SCORE_FILE, "r", encoding="utf-8") as f:
                    self.user_scores = json.load(f)
        except Exception as e:
            print(f"加载数据失败：{e}")
    
    def _save_user_scores(self):
        """保存用户分数数据"""
        try:
            with open(USER_SCORE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.user_scores, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户分数失败：{e}")
    
    def set_ban_words(self, ban_words: Dict):
        """设置违禁词数据"""
        self.ban_words = ban_words
    
    def set_threshold(self, threshold: int):
        """设置触发阈值"""
        self.threshold = threshold
    
    def detect_ban_words(self, message: str, group_id: str, user_id: str) -> Tuple[int, Dict[str, int], str]:
        """
        检测消息中的违禁词
        
        Args:
            message: 用户消息
            group_id: 群组ID
            user_id: 用户ID
        
        Returns:
            Tuple[总权重, 检测到的违禁词字典, 高亮消息]
        """
        if group_id not in self.ban_words:
            return 0, {}, message
        
        group_ban_words = self.ban_words[group_id]
        total_weight = 0
        detected_words = {}
        highlighted_message = message
        
        # 检测每个违禁词
        for word, weight in group_ban_words.items():
            # 使用正则表达式进行匹配（忽略大小写）
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            matches = pattern.findall(message)
            
            if matches:
                count = len(matches)
                detected_words[word] = count
                total_weight += weight * count
                
                # 高亮显示违禁词
                highlighted_message = pattern.sub(f"【{word}】", highlighted_message)
        
        return total_weight, detected_words, highlighted_message
    
    def update_user_score(self, group_id: str, user_id: str, weight: int) -> Tuple[int, bool]:
        """
        更新用户分数并检查是否触发禁言
        
        Args:
            group_id: 群组ID
            user_id: 用户ID
            weight: 本次违规权重
        
        Returns:
            Tuple[当前总分数, 是否触发禁言]
        """
        # 生成用户唯一标识
        user_key = f"{group_id}_{user_id}"
        
        # 获取当前分数
        current_score = self.user_scores.get(user_key, 0)
        
        # 更新分数（可考虑添加衰减机制）
        new_score = current_score + weight
        self.user_scores[user_key] = new_score
        
        # 保存分数
        self._save_user_scores()
        
        # 检查是否触发禁言
        trigger_ban = new_score >= self.threshold
        
        return new_score, trigger_ban
    
    def reset_user_score(self, group_id: str, user_id: str):
        """重置用户分数"""
        user_key = f"{group_id}_{user_id}"
        if user_key in self.user_scores:
            self.user_scores[user_key] = 0
            self._save_user_scores()
    
    def get_user_score(self, group_id: str, user_id: str) -> int:
        """获取用户当前分数"""
        user_key = f"{group_id}_{user_id}"
        return self.user_scores.get(user_key, 0)
    
    def get_current_time(self) -> str:
        """获取当前格式化时间"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_ban_message(self, user_id: str, current_score: int, 
                           detected_words: Dict[str, int], original_message: str, 
                           highlighted_message: str, duration: int = 600) -> str:
        """
        生成禁言提示消息
        
        Args:
            user_id: 用户ID
            current_score: 当前总分数
            detected_words: 检测到的违禁词
            original_message: 原始消息
            highlighted_message: 高亮消息
            duration: 禁言时长（秒）
        
        Returns:
            格式化提示消息
        """
        current_time = self.get_current_time()
        
        # 构建消息
        message_parts = []
        message_parts.append("🚫 违禁词检测触发禁言")
        message_parts.append("═" * 30)
        message_parts.append(f"🕐 时间：{current_time}")
        message_parts.append(f"👤 用户：{user_id}")
        message_parts.append(f"📊 累计分数：{current_score}/{self.threshold}")
        message_parts.append(f"⏰ 禁言时长：{duration}秒")
        message_parts.append("")
        
        # 违禁词详情
        if detected_words:
            message_parts.append("📋 检测到的违禁词：")
            for word, count in detected_words.items():
                message_parts.append(f"  • {word} × {count}")
            message_parts.append("")
        
        message_parts.append("💬 原始消息：")
        message_parts.append(f"   {original_message}")
        message_parts.append("")
        message_parts.append("🔍 高亮显示：")
        message_parts.append(f"   {highlighted_message}")
        message_parts.append("═" * 30)
        message_parts.append("💡 请遵守群规，文明发言")
        
        return "\n".join(message_parts)
    
    def generate_warning_message(self, user_id: str, current_score: int, 
                               detected_words: Dict[str, int], weight: int) -> str:
        """
        生成警告消息（未达到禁言阈值时）
        """
        current_time = self.get_current_time()
        
        message_parts = []
        message_parts.append("⚠️ 违禁词警告")
        message_parts.append("─" * 25)
        message_parts.append(f"🕐 时间：{current_time}")
        message_parts.append(f"👤 用户：{user_id}")
        message_parts.append(f"📊 当前分数：{current_score}/{self.threshold} (+{weight})")
        message_parts.append("")
        
        if detected_words:
            message_parts.append("📋 违规词汇：")
            for word, count in detected_words.items():
                message_parts.append(f"  • {word} × {count}")
        
        message_parts.append("─" * 25)
        message_parts.append("💡 请注意发言内容，达到阈值将自动禁言")
        
        return "\n".join(message_parts)

# 全局检测器实例
detector = BanWordsDetector()

def get_detector() -> BanWordsDetector:
    """获取全局检测器实例"""
    return detector