"""供快速测试使用的快照内存仓储。"""

from copy import deepcopy
from typing import Dict
from domain.order import Order


class MemoryOrderRepository:
    """通过复制隔离加载和保存，匹配数据库仓储的显式保存契约。"""

    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}

    def save(self, order: Order) -> None:
        """保存独立快照。Rules: ORD-005"""
        self._orders[order.id] = deepcopy(order)

    def get(self, order_id: str) -> Order:
        """返回独立副本，不存在时抛出 KeyError。Rules: ORD-005"""
        return deepcopy(self._orders[order_id])
