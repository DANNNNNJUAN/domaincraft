"""确认订单用例通过领域契约协调加载、业务行为与保存。"""

from domain.repository import OrderRepository


def confirm_order(order_id: str, repository: OrderRepository) -> None:
    """确认后保存；领域拒绝时不调用 save。

    Rules: ORD-001, ORD-002, ORD-005
    """
    order = repository.get(order_id)
    order.confirm()
    repository.save(order)
