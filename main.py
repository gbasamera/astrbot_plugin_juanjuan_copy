from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.platform.astr_message_event import *
from astrbot.core.message.message_event_result import *
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.filter.event_message_type import EventMessageType


import sys
import os
import re
import json
from typing import Dict, Tuple, Optional
import time
from datetime import datetime
from typing import Dict, Tuple, Optional
import json
import os


# 配置数据存储路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BAN_WORDS_FILE = os.path.join(DATA_DIR, "ban_words.json")
BAN_STATUS_FILE = os.path.join(DATA_DIR, "ban_status.json")
USER_SCORE_FILE = os.path.join(DATA_DIR, "user_scores.json")

# 本来想把这个类放到单独的文件里，但不知道为什么死活导不进去，只能放这里了
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
    
    def generate_recall_and_ban_message(self, user_id: str, current_score: int, 
                                    detected_words: Dict[str, int], original_message: str, 
                                    highlighted_message: str, duration: int = 600) -> str:
        """
        生成撤回并禁言提示消息
        
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
        message_parts.append("🚫 消息撤回+禁言处理")
        message_parts.append("═" * 35)
        message_parts.append(f"🕐 处理时间：{current_time}")
        message_parts.append(f"👤 违规用户：{user_id}")
        message_parts.append(f"📊 累计分数：{current_score}/{self.threshold}")
        message_parts.append(f"⏰ 禁言时长：{duration}秒")
        message_parts.append("")
        
        # 违禁词详情
        if detected_words:
            message_parts.append("📋 检测到的违禁词：")
            for word, count in detected_words.items():
                message_parts.append(f"  • {word} × {count}")
            message_parts.append("")
        
        message_parts.append("💬 原始消息内容：")
        # 处理长消息，避免消息过长
        if len(original_message) > 200:
            message_parts.append(f"   {original_message[:200]}...（消息过长已截断）")
        else:
            message_parts.append(f"   {original_message}")
        
        message_parts.append("")
        message_parts.append("🔍 违规词汇高亮：")
        if len(highlighted_message) > 200:
            message_parts.append(f"   {highlighted_message[:200]}...（消息过长已截断）")
        else:
            message_parts.append(f"   {highlighted_message}")
        
        message_parts.append("═" * 35)
        message_parts.append("💡 消息已自动撤回，请遵守群规文明发言")
        
        return "\n".join(message_parts)

    def generate_recall_warning_message(self, user_id: str, current_score: int, 
                                    detected_words: Dict[str, int], weight: int, 
                                    original_message: str) -> str:
        """
        生成撤回警告消息（未达到禁言阈值时）
        """
        current_time = self.get_current_time()
        
        message_parts = []
        message_parts.append("⚠️ 消息撤回警告")
        message_parts.append("─" * 28)
        message_parts.append(f"🕐 时间：{current_time}")
        message_parts.append(f"👤 用户：{user_id}")
        message_parts.append(f"📊 当前分数：{current_score}/{self.threshold} (+{weight})")
        message_parts.append("")
        
        if detected_words:
            message_parts.append("📋 违规词汇：")
            for word, count in detected_words.items():
                message_parts.append(f"  • {word} × {count}")
            message_parts.append("")
        
        message_parts.append("💬 撤回的消息：")
        if len(original_message) > 150:
            message_parts.append(f"   {original_message[:150]}...")
        else:
            message_parts.append(f"   {original_message}")
        
        message_parts.append("─" * 28)
        message_parts.append("💡 消息已撤回，请注意发言内容")
        
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





@register("juanjuan_copy", "gbasamera", "功能来源于卷卷机器人", "1.0.0")
class JuanJuan_Copy(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 初始化违禁词和状态存储
        self.banword_status = {}
        self.context = context
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        # 初始化违禁词和状态文件
        self._init_ban_words_file()
        self._init_ban_status_file()
        # 加载违禁词和状态
        self.ban_words = self._load_ban_words()
        self.banword_status = self._load_ban_status()

        self.detector = get_detector()
        self.detector.set_ban_words(self.ban_words)
        self.detector.set_threshold(10)  # 可以设置为可配置的

    def _init_ban_status_file(self):
        """初始化功能开关状态文件"""
        if not os.path.exists(BAN_STATUS_FILE):
            with open(BAN_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False)
            logger.info(f"新建功能开关存储文件：{BAN_STATUS_FILE}")

    def _load_ban_status(self):
        """加载开关状态"""
        try:
            with open(BAN_STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载功能开关失败：{e}")
            return {}

    def _save_ban_status(self):
        """保存开关状态"""
        try:
            with open(BAN_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.banword_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存功能开关失败：{e}")

    def _init_ban_words_file(self):
        """初始化违禁词文件"""
        if not os.path.exists(BAN_WORDS_FILE):
            with open(BAN_WORDS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False)
            logger.info(f"新建违禁词存储文件：{BAN_WORDS_FILE}")

    def _load_ban_words(self):
        """从文件加载违禁词数据"""
        try:
            with open(BAN_WORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载违禁词文件失败：{e}")
            return {}

    def _save_ban_words(self):
        """保存违禁词数据"""
        try:
            with open(BAN_WORDS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.ban_words, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存违禁词失败：{e}")

    def _get_group_status(self, group_id: str) -> bool:
        """获取指定群的开关状态"""
        # 如果群不在状态字典中，默认返回False（关闭状态）
        return self.banword_status.get(group_id, False)

    async def initialize(self):
        """插件初始化"""
        pass

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def handle_message(self, event: AiocqhttpMessageEvent) -> Optional[MessageEventResult]:
        """处理群消息，进行违禁词检测"""
        try:
            # 只处理群消息
            group_id = event.get_group_id()
            if not group_id:
                return None
            
            # 检查功能是否开启
            if not self._get_group_status(group_id):
                return None
            
            # 忽略管理员的消息
            if event.is_admin():
                return None
            
            # 获取用户ID和消息内容
            user_id = event.get_sender_id()
            message = event.message_str.strip()
            assert isinstance(event, AiocqhttpMessageEvent)
            message_id = event.message_obj.message_id  # 获取消息ID用于撤回
            
            if not message:
                return None
            

            
            # 使用检测器进行违禁词检测
            weight, detected_words, highlighted_message = detector.detect_ban_words(
                message, group_id, user_id
            )
            
            # 如果没有检测到违禁词，直接返回
            if weight <= 0:
                return None
            
            # 在检测到违禁词后，执行禁言/警告前添加撤回逻辑
            if weight > 0:  # 检测到违禁词
                try:
                    # 撤回消息
                    await event.bot.delete_msg(message_id=int(message_id))
                    logger.info(f"✅ 已撤回用户 {user_id} 的违规消息")
                    recall_success = True
                except Exception as e:
                    logger.error(f"❌ 撤回消息失败：{e}")
                    recall_success = False
            
            # 更新用户分数并检查是否触发禁言
            current_score, trigger_ban = detector.update_user_score(group_id, user_id, weight)
            
            if trigger_ban:
                # 触发禁言
                ban_duration = 600  # 10分钟
                
                try:
                    # 执行禁言
                    await event.bot.set_group_ban(
                        group_id=int(group_id),
                        user_id=int(user_id),
                        duration=ban_duration
                    )
                    
                    # 生成并发送禁言提示消息
                    ban_message = detector.generate_ban_message(
                        user_id, current_score, detected_words, 
                        message, highlighted_message, ban_duration
                    )
                    
                    # 重置用户分数
                    detector.reset_user_score(group_id, user_id)
                    
                    return event.plain_result(ban_message)
                    
                except Exception as e:
                    logger.error(f"禁言用户失败：{e}")
                    error_msg = f"❌ 检测到违禁词但禁言操作失败：{e}"
                    return event.plain_result(error_msg)
            
            else:
                # 仅警告，不禁言
                warning_message = detector.generate_warning_message(
                    user_id, current_score, detected_words, weight
                )
                
                return event.plain_result(warning_message)
        
        except Exception as e:
            logger.error(f"处理消息时发生错误：{e}")
        
        return None


    @filter.command_group("banword", alias={"bw"})
    def banword(self):
        """违禁词相关指令"""
        pass

    @banword.command("help")
    async def help(self, event: AstrMessageEvent):
        """指令说明"""
        help_message = "违禁词指令如下：\n" \
        "/banword 可以改为 /bw 进行简化操作 \n" \
        "/banword help 查看帮助信息 \n" \
        "/banword status 查看功能开关状态 \n" \
        "/banword on 开启违禁词功能 \n" \
        "/banword off 关闭违禁词功能 \n" \
        "/banword add <违禁词> <权重> 添加违禁词 \n" \
        "/banword remove（或rm） <违禁词> 移除违禁词 \n" \
        "/banword unban 用户ID 解除禁言 \n" \
        "/banword t 用户ID 踢出用户 \n" \
        "/banword tl 用户ID 踢出并拉黑用户 \n" \
        "/banword list 查看违禁词列表功能 \n" \
        "/banword score [用户ID] 查询用户当前违禁词分数（管理员可查询他人） \n" \
        "/banword reset_score 用户ID 重置用户分数（仅管理员可用） \n"

        yield event.plain_result(help_message)

    @banword.command("status")
    async def status(self, event: AstrMessageEvent):
        """查看功能开关状态（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return

        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限对BanWords功能进行操作,请联系管理员。")
            return

        # 获取当前群的状态
        current_status = self._get_group_status(group_id)
        status_text = "✅✅✅BanWords功能处于开启状态" if current_status else "🚫🚫🚫BanWords功能处于关闭状态"
        yield event.plain_result(f"{status_text}")

    @banword.command("on")
    async def turn_on(self, event: AstrMessageEvent):
        """开启违禁词功能（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return

        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限开启功能，请联系管理员。")
            return

        # 开启功能
        self.banword_status[group_id] = True
        self._save_ban_status()
        yield event.plain_result("✅✅✅BanWords功能已开启")

    @banword.command("off")
    async def turn_off(self, event: AstrMessageEvent):
        """关闭违禁词功能（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return

        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限关闭功能，请联系管理员。")
            return

        # 关闭功能
        self.banword_status[group_id] = False
        self._save_ban_status()
        yield event.plain_result("🚫🚫🚫BanWords功能已关闭")

    @banword.command("add")
    async def add(self, event: AstrMessageEvent, word: str, weight: int):
        """添加违禁词（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return
        
        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限对BanWords功能进行操作,请联系管理员。")
            return
        
        # 检查功能状态
        current_status = self._get_group_status(group_id)
        if not current_status:
            yield event.plain_result("🚫🚫🚫BanWords功能已关闭，添加操作失败")
            return
        
        plain_text = event.message_str.strip()
        args = plain_text.split()

        word = args[2]
        try:
            weight = int(args[3])
            if weight <= 0:
                yield event.plain_result("❌❌❌权重必须为正整数！")
                return
        except ValueError:
            yield event.plain_result("❌❌❌权重必须为整数！")
            return
            
        if len(args) < 4:
            yield event.plain_result("❌ 格式错误，应为：/banword add <违禁词> <权重>")
            return


        try:
            if group_id not in self.ban_words:
                self.ban_words[group_id] = {}
            self.ban_words[group_id][word] = weight
            self._save_ban_words()

            yield event.plain_result(f"✅✅✅成功添加违禁词【{word}】，权重：{weight}")
        except Exception as e:
            logger.error(f"添加违禁词失败：{e}")
            yield event.plain_result("❌❌❌添加违禁词失败，请稍后重试。")

        # 更新检测器中的违禁词数据
        self.detector.set_ban_words(self.ban_words)

    @banword.command("remove", alias={"rm"})
    async def remove(self, event: AstrMessageEvent):
        """移除违禁词（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return
        
        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限对BanWords功能进行操作,请联系管理员。")
            return
        
        # 检查功能状态
        current_status = self._get_group_status(group_id)
        if not current_status:
            yield event.plain_result("🚫🚫🚫BanWords功能已关闭，移除操作失败")
            return
        
        plain_text = event.message_str.strip()
        args = plain_text.split()

        word = args[2]
        
        try:
            if group_id in self.ban_words and word in self.ban_words[group_id]:
                del self.ban_words[group_id][word]
                self._save_ban_words()
                yield event.plain_result(f"✅✅✅成功移除违禁词【{word}】")
            else:
                yield event.plain_result(f"❌❌❌违禁词【{word}】不存在。")
        except Exception as e:
            logger.error(f"移除违禁词失败：{e}")
            yield event.plain_result("❌❌❌移除违禁词失败，请稍后重试。")

        # 更新检测器中的违禁词数据
        self.detector.set_ban_words(self.ban_words)

    @banword.command("list")
    async def list_ban_words(self, event: AiocqhttpMessageEvent):
        """查看当前群违禁词列表（仅管理员可用）"""
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return

        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限查看违禁词列表，请联系管理员。")
            return
        
        # 检查功能状态
        current_status = self._get_group_status(group_id)
        if not current_status:
            yield event.plain_result("🚫🚫🚫BanWords功能已关闭，无法查看列表")
            return

        # 获取当前群的违禁词
        group_ban_words = self.ban_words.get(group_id, {})
        if not group_ban_words:
            yield event.plain_result("✅✅✅当前群暂无违禁词。")
            return

        # 发送私聊消息给管理员
        admin_id = event.get_sender_id()
        if not admin_id:
            yield event.plain_result("❌❌❌无法获取你的用户信息，无法发送私聊。")
            return

        try:
            # 构建纯文本消息内容
            message_lines = [f"群{group_id}违禁词列表:"]
            message_lines.append("----------------------")
            message_lines.append("违禁词 | 权重")
            message_lines.append("------------------------------------------")
            
            for word, w in group_ban_words.items():
                message_lines.append(f"{word} | {w}")
            
            message_lines.append("----------------------")
            message_lines.append(f"共{len(group_ban_words)}个违禁词")
            
            message_content = "\n".join(message_lines)
            
            # 发送私聊消息
            await event.bot.send_private_msg(
                user_id=int(admin_id),
                message=message_content
            )
            
            yield event.plain_result("✅✅✅违禁词列表已发送，请查看私聊消息。")
            
        except Exception as e:
            logger.error(f"向用户{admin_id}发送私聊失败：{e}")
            yield event.plain_result("❌❌❌私聊发送失败，请稍后重试。")

    @banword.command("unban")
    async def unban(self, event: AiocqhttpMessageEvent, user_id: str):
        """解除禁言（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return
        
        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限对BanWords功能进行操作,请联系管理员。")
            return
        
        try:
            await event.bot.set_group_ban(
                group_id=int(group_id),
                user_id=int(user_id),
                duration=0
            )
            yield event.plain_result(f"✅✅✅已成功解禁用户{user_id}。")
        except Exception as e:
            logger.error(f"解禁用户失败：{e}")
            yield event.plain_result("❌❌❌解禁用户失败，请稍后重试。")

    @banword.command("t")
    async def kick(self, event: AiocqhttpMessageEvent, user_id: str):
        """踢出用户（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return
        
        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限对BanWords功能进行操作,请联系管理员。")
            return
        
        try:
            await event.bot.set_group_kick(
                group_id=int(group_id),
                user_id=int(user_id),
                reject_add_request=False
            )
            yield event.plain_result(f"✅✅✅已成功踢出用户{user_id}。")
        except Exception as e:
            logger.error(f"踢出用户失败：{e}")
            yield event.plain_result("❌❌❌踢出用户失败，请稍后重试。")


    @banword.command("tl")
    async def kick_and_ban(self, event: AiocqhttpMessageEvent, user : str):
        """踢出并拉黑用户（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return
        
        if not event.is_admin():
            yield event.plain_result("❌❌❌你没有权限对BanWords功能进行操作,请联系管理员。")
            return
        
        try:
            await event.bot.set_group_kick(
                group_id=int(group_id),
                user_id=int(user),
                reject_add_request=True
            )
            yield event.plain_result(f"✅✅✅已成功踢出并拉黑用户{user}。")
        except Exception as e:
            logger.error(f"踢出并拉黑用户失败：{e}")
            yield event.plain_result("❌❌❌踢出并拉黑用户失败，请稍后重试。")

    @banword.command("score")
    async def check_score(self, event: AstrMessageEvent, target_user: str):
        """查询用户当前违禁词分数（管理员可查询他人）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return
        
        # 确定要查询的用户
        if target_user and event.is_admin():
            # 管理员查询指定用户
            user_id = target_user
        else:
            # 普通用户查询自己
            user_id = event.get_sender_id()
        
        current_score = self.detector.get_user_score(group_id, user_id)
        threshold = self.detector.threshold
        
        yield event.plain_result(f"👤 用户 {user_id} 当前违禁词分数：{current_score}/{threshold}")

    @banword.command("reset_score")
    async def reset_score(self, event: AstrMessageEvent, target_user: str):
        """重置用户分数（仅管理员可用）"""
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用。")
            return
        
        if not event.is_admin():
            yield event.plain_result("❌ 你没有权限执行此操作。")
            return
        
        self.detector.reset_user_score(group_id, target_user)
        yield event.plain_result(f"✅ 已重置用户 {target_user} 的违禁词分数")

    async def terminate(self):
        """插件卸载"""
        logger.info("卸载卷卷违禁词插件")

