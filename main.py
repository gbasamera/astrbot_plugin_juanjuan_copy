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

import os
import re
import json

# 配置数据存储路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BAN_WORDS_FILE = os.path.join(DATA_DIR, "ban_words.json")
BAN_STATUS_FILE = os.path.join(DATA_DIR, "ban_status.json")

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
        "/banword unban群号 用户ID 处理解禁命令 \n" \
        "/banword t群号 用户ID 处理踢出命令 \n" \
        "/banword tl群号 用户ID 处理踢出并拉黑命令 \n" \
        "/banword list 添加查看违禁词列表功能 \n"

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
        
        try:
            if group_id not in self.ban_words:
                self.ban_words[group_id] = {}
            self.ban_words[group_id][word] = weight
            self._save_ban_words()

            yield event.plain_result(f"✅✅✅成功添加违禁词【{word}】，权重：{weight}")
        except Exception as e:
            logger.error(f"添加违禁词失败：{e}")
            yield event.plain_result("❌❌❌添加违禁词失败，请稍后重试。")

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
        
        # 检查功能状态 - 修复这里的逻辑错误
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

    async def terminate(self):
        """插件卸载"""
        logger.info("卸载卷卷违禁词插件")