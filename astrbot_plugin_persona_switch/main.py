import asyncio

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr

DEFAULT_PERSONA_ID = "default"


class PersonaSwitchPlugin(Star):
    """在 QQ 里随时切换当前会话使用的人格。

    用法（私聊或群聊都行）：
      /人格              列出所有人格
      /人格 <名字>        把当前会话切换成该人格（管理员）
      /人格 默认          恢复默认人格（管理员）
    """

    def __init__(self, context: Context):
        super().__init__(context)

    # ---------- 工具 ----------
    async def _all_personas(self):
        try:
            return await self.context.persona_manager.get_all_personas()
        except Exception as e:
            logger.warning(f"[persona] 读取人格列表失败: {e}")
            return []

    @staticmethod
    def _umo(event: AstrMessageEvent) -> str:
        try:
            return str(event.unified_msg_origin)
        except Exception:
            return ""

    async def _current_persona(self, umo: str) -> str:
        try:
            cid = await self.context.conversation_manager.get_curr_conversation_id(umo)
            if not cid:
                return ""
            conv = await self.context.conversation_manager.get_conversation(umo, cid)
            return str(getattr(conv, "persona_id", "") or "")
        except Exception:
            return ""

    # ---------- 列表（谁都能看）----------
    @filter.command("人格列表")
    async def list_personas(self, event: AstrMessageEvent):
        personas = await self._all_personas()
        if not personas:
            yield event.plain_result("还没创建过人格。")
            return
        names = [str(getattr(p, "persona_id", "") or "") for p in personas]
        names = [n for n in names if n]
        cur = await self._current_persona(self._umo(event))
        lines = ["可用人格：" + "、".join(names)]
        if cur:
            lines.append(f"当前会话使用：{cur}")
        yield event.plain_result("\n".join(lines))

    # ---------- 切换（管理员）----------
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("人格")
    async def switch_persona(self, event: AstrMessageEvent, target: GreedyStr = ""):
        umo = self._umo(event)
        if not umo:
            yield event.plain_result("拿不到当前会话信息，切换失败。")
            return

        name = str(target or "").strip()
        personas = await self._all_personas()
        ids = [str(getattr(p, "persona_id", "") or "") for p in personas]

        # 没给参数 → 当查询用
        if not name:
            cur = await self._current_persona(umo)
            yield event.plain_result(
                "当前人格：" + (cur or "(未设置)")
                + "\n用法：/人格 <名字> 切换，/人格 默认 恢复。"
                + "\n可选：" + "、".join([i for i in ids if i])
            )
            return

        if name in ("默认", "default", "恢复"):
            name = DEFAULT_PERSONA_ID

        if name not in ids:
            yield event.plain_result(
                f"没有叫「{name}」的人格。可选：" + "、".join([i for i in ids if i])
            )
            return

        try:
            await self.context.conversation_manager.update_conversation_persona_id(umo, name)
        except Exception as e:
            logger.error(f"[persona] 切换失败: {e}")
            yield event.plain_result(f"切换失败：{e}")
            return

        # 给一点缓冲，确保写入生效
        await asyncio.sleep(0.2)
        now = await self._current_persona(umo)
        yield event.plain_result(f"已切换人格为「{now or name}」。下一条消息生效。")
