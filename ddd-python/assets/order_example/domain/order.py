"""订单上下文：聚合维护确认与修改规则，Money 维护金额语义。"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import re
from typing import Tuple


class EmptyOrder(ValueError):
    """空订单无法进入履约流程。"""


class InvalidOrderState(ValueError):
    """当前订单状态不接受该业务操作。"""


@dataclass(frozen=True)
class Money:
    """非负有限金额；币种使用三位大写代码。Rules: ORD-003"""

    amount: Decimal
    currency: str = "CNY"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("Use Decimal for money")
        if not self.amount.is_finite() or self.amount < 0:
            raise ValueError("Amount must be finite and non-negative")
        if not isinstance(self.currency, str) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("Invalid currency")


@dataclass(frozen=True)
class OrderLine:
    """不可变订单行，避免调用方绕过聚合修改商品。Rules: ORD-004"""

    product: str
    quantity: int
    price: Money

    def __post_init__(self) -> None:
        if not isinstance(self.product, str) or not self.product.strip():
            raise ValueError("Product is required")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        if not isinstance(self.price, Money):
            raise TypeError("Price must be Money")


class Status(Enum):
    """本例只覆盖草稿与已确认两个业务状态。"""

    DRAFT = "draft"
    CONFIRMED = "confirmed"


class Order:
    """订单聚合根，唯一公开修改入口保护订单不变量。"""

    def __init__(self, order_id: str, currency: str = "CNY") -> None:
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("Order ID is required")
        Money(Decimal(0), currency)
        self._id = order_id
        self._currency = currency
        self._status = Status.DRAFT
        self._items: Tuple[OrderLine, ...] = ()

    @property
    def id(self) -> str:
        """返回稳定业务标识。"""
        return self._id

    @property
    def currency(self) -> str:
        """返回订单统一币种。"""
        return self._currency

    @property
    def status(self) -> Status:
        """返回状态，调用方不能通过此属性修改它。"""
        return self._status

    @property
    def items(self) -> Tuple[OrderLine, ...]:
        """返回由不可变行组成的只读快照。"""
        return self._items

    @property
    def total(self) -> Money:
        """按数量汇总同币种金额。Rules: ORD-003"""
        return Money(sum((line.price.amount * line.quantity for line in self._items), Decimal(0)), self.currency)

    def add_item(self, product: str, quantity: int, price: Money) -> None:
        """向草稿添加有效同币种商品；拒绝时保持原状态。

        Rules: ORD-002, ORD-003, ORD-004
        Args:
            product: 商品业务标识。
            quantity: 正整数数量。
            price: 与订单币种一致的单价。
        Raises:
            InvalidOrderState: 订单已确认。
            ValueError: 数量、商品或币种不合法。
        """
        self._ensure_draft()
        line = OrderLine(product, quantity, price)
        if price.currency != self.currency:
            raise ValueError("Currency mismatch")
        # 所有校验完成后一次替换，拒绝请求不得留下半条订单行。
        self._items = self._items + (line,)

    def confirm(self) -> None:
        """确认非空草稿订单；拒绝时状态保持不变。

        Rules: ORD-001, ORD-002
        Raises:
            EmptyOrder: 没有可履约商品。
            InvalidOrderState: 订单已经确认。
        """
        self._ensure_draft()
        if not self._items:
            raise EmptyOrder(self.id)
        self._status = Status.CONFIRMED

    def _ensure_draft(self) -> None:
        if self.status is not Status.DRAFT:
            raise InvalidOrderState(self.id)
