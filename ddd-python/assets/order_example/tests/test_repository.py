"""同一组黑盒契约约束内存与 SQLite 实现的可替换行为。"""

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from application.confirm_order import confirm_order
from domain.order import EmptyOrder, Money, Order, Status
from infrastructure.memory import MemoryOrderRepository
from infrastructure.sqlite import SQLiteOrderRepository


class RepositoryContract:
    def test_missing(self):
        """ORD-005：未知 ID 统一抛出 KeyError。"""
        with self.assertRaises(KeyError):
            self.repository.get("unknown")

    def test_snapshot_and_roundtrip(self):
        """ORD-005：修改加载对象不隐式持久化，显式保存才可见。"""
        order = Order("O-1")
        order.add_item("P", 1, Money(Decimal("2.50")))
        self.repository.save(order)
        order.confirm()
        loaded = self.repository.get("O-1")
        self.assertEqual(loaded.status, Status.DRAFT)
        self.assertEqual(loaded.total, Money(Decimal("2.50")))
        loaded.confirm()
        self.assertEqual(self.repository.get("O-1").status, Status.DRAFT)
        self.repository.save(loaded)
        self.assertEqual(self.repository.get("O-1").status, Status.CONFIRMED)

    def test_use_case(self):
        """ORD-005：用例依赖契约，两种仓储都能完成确认。"""
        order = Order("O-1")
        order.add_item("P", 1, Money(Decimal(1)))
        self.repository.save(order)
        confirm_order("O-1", self.repository)
        self.assertEqual(self.repository.get("O-1").status, Status.CONFIRMED)

    def test_rejected_use_case(self):
        """ORD-001：拒绝空订单后持久化状态不变。"""
        self.repository.save(Order("O-1"))
        with self.assertRaises(EmptyOrder):
            confirm_order("O-1", self.repository)
        self.assertEqual(self.repository.get("O-1").status, Status.DRAFT)


class MemoryContract(RepositoryContract, unittest.TestCase):
    def setUp(self):
        self.repository = MemoryOrderRepository()


class SQLiteContract(RepositoryContract, unittest.TestCase):
    def setUp(self):
        self.repository = SQLiteOrderRepository()

    def tearDown(self):
        self.repository.close()


class SQLiteIntegration(unittest.TestCase):
    def test_reopen(self):
        """ORD-005：关闭并重开真实本地数据库后快照仍存在。"""
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "orders.db")
            first = SQLiteOrderRepository(path)
            try:
                first.save(Order("O-1"))
            finally:
                first.close()
            second = SQLiteOrderRepository(path)
            try:
                self.assertEqual(second.get("O-1").status, Status.DRAFT)
            finally:
                second.close()
