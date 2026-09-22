"""SQLite 本地仓储，JSON 映射位于适配器内部。"""

from decimal import Decimal
import json
import sqlite3
from domain.order import Money, Order, Status


class SQLiteOrderRepository:
    """显式保存快照；数据库路径由装配方指定。"""

    def __init__(self, path: str = ":memory:") -> None:
        self._connection = sqlite3.connect(path)
        self._connection.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def save(self, order: Order) -> None:
        """在本地事务中保存快照。Rules: ORD-005"""
        payload = json.dumps({
            "currency": order.currency,
            "status": order.status.value,
            "items": [[line.product, line.quantity, str(line.price.amount)] for line in order.items],
        })
        with self._connection:
            self._connection.execute("INSERT OR REPLACE INTO orders VALUES (?, ?)", (order.id, payload))

    def get(self, order_id: str) -> Order:
        """重建有效独立对象；不存在时抛出 KeyError。Rules: ORD-005"""
        row = self._connection.execute("SELECT payload FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise KeyError(order_id)
        record = json.loads(row[0])
        order = Order(order_id, record["currency"])
        for product, quantity, amount in record["items"]:
            order.add_item(product, quantity, Money(Decimal(amount), record["currency"]))
        if Status(record["status"]) is Status.CONFIRMED:
            order.confirm()
        return order

    def close(self) -> None:
        """释放本适配器拥有的连接。"""
        self._connection.close()
