"""本包明确约定的业务规则测试，不代表用户真实业务已确认。"""

from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest
from domain.order import EmptyOrder, InvalidOrderState, Money, Order, Status


class OrderTests(unittest.TestCase):
    def test_empty_order(self):
        """ORD-001：拒绝空订单，保持草稿。"""
        order = Order("O-1")
        with self.assertRaises(EmptyOrder):
            order.confirm()
        self.assertEqual(order.status, Status.DRAFT)
        self.assertEqual(order.items, ())

    def test_confirm(self):
        """ORD-002：合法确认只发生一次，确认后禁止修改。"""
        order = Order("O-1")
        order.add_item("P-1", 2, Money(Decimal("12.30")))
        order.confirm()
        self.assertEqual(order.status, Status.CONFIRMED)
        before = order.items
        with self.assertRaises(InvalidOrderState):
            order.confirm()
        with self.assertRaises(InvalidOrderState):
            order.add_item("P-2", 1, Money(Decimal("1")))
        self.assertEqual(order.items, before)

    def test_money(self):
        """ORD-003：有限非负金额，币种一致，十进制总额准确。"""
        for amount in ("-1", "NaN", "Infinity", "-Infinity"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                Money(Decimal(amount))
        with self.assertRaises(TypeError):
            Money(0.1)
        with self.assertRaises(ValueError):
            Money(Decimal(1), "cny")
        order = Order("O-1")
        order.add_item("P", 3, Money(Decimal("0.10")))
        self.assertEqual(order.total, Money(Decimal("0.30")))
        before = order.items
        with self.assertRaises(ValueError):
            order.add_item("P", 1, Money(Decimal("2"), "USD"))
        self.assertEqual(order.items, before)

    def test_quantity(self):
        """ORD-004：无效数量不留下部分修改；订单行不可变。"""
        order = Order("O-1")
        for quantity in (0, -1, True, 1.5):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                order.add_item("P", quantity, Money(Decimal(1)))
            self.assertEqual(order.items, ())
        order.add_item("P", 1, Money(Decimal(1)))
        with self.assertRaises(FrozenInstanceError):
            order.items[0].quantity = 99
        with self.assertRaises(FrozenInstanceError):
            order.items[0].price.amount = Decimal(99)

    def test_total_across_quantities(self):
        """ORD-003：有界输入组合验证总价性质，完全离线且可复现。"""
        for quantity in range(1, 21):
            for cents in (0, 1, 33, 100, 999):
                with self.subTest(quantity=quantity, cents=cents):
                    order = Order("O")
                    price = Decimal(cents) / 100
                    order.add_item("P", quantity, Money(price))
                    self.assertEqual(order.total.amount, price * quantity)
