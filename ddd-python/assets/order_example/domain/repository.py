"""订单存取契约由领域用途定义，适配器提供具体持久化。"""

from typing import Protocol
from domain.order import Order


class OrderRepository(Protocol):
    """保存快照、按 ID 加载；两种实现必须遵守同一行为契约。"""

    def save(self, order: Order) -> None:
        """保存或替换订单快照；后续对象修改不隐式改变存储。Rules: ORD-005"""
        ...

    def get(self, order_id: str) -> Order:
        """加载独立订单对象；不存在时抛出 KeyError。Rules: ORD-005"""
        ...
