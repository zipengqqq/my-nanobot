"""用于解耦 channel 与 agent 通信的异步消息队列。"""

import asyncio

from nanobot.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    用于将聊天渠道与 agent 核心解耦的异步消息总线。

    各个 channel 把消息写入入站队列，agent 消费后再把响应写入出站队列。
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """把来自 channel 的消息发布给 agent。"""
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """消费下一条入站消息；若队列为空则阻塞等待。"""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """把 agent 的响应发布给各个 channel。"""
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """消费下一条出站消息；若队列为空则阻塞等待。"""
        return await self.outbound.get()

    @property
    def inbound_size(self) -> int:
        """当前待处理的入站消息数量。"""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """当前待发送的出站消息数量。"""
        return self.outbound.qsize()
