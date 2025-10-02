"""Position tracking with SQLite persistence."""

import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class Position:
    """Represents a trading position."""

    def __init__(
        self,
        symbol: str,
        quantity: Decimal,
        entry_price: Decimal,
        entry_time: datetime,
        order_id: str,
        position_id: Optional[int] = None,
        exit_price: Optional[Decimal] = None,
        exit_time: Optional[datetime] = None,
        pnl: Optional[Decimal] = None,
        status: str = "OPEN",
    ) -> None:
        """Initialize position."""
        self.id = position_id
        self.symbol = symbol
        self.quantity = quantity
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.pnl = pnl
        self.status = status
        self.order_id = order_id

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Position(symbol={self.symbol}, qty={self.quantity}, "
            f"entry={self.entry_price}, status={self.status})"
        )


class PositionTracker:
    """Track trading positions with SQLite persistence."""

    def __init__(self, db_path: str = "data/positions.db") -> None:
        """
        Initialize position tracker.

        Args:
            db_path: Path to SQLite database file
        """
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._init_db()
        logger.info(f"PositionTracker initialized with db: {db_path}")

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_price REAL,
                    exit_time TEXT,
                    pnl REAL,
                    status TEXT NOT NULL CHECK(status IN ('OPEN', 'CLOSED')),
                    order_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Index for fast lookups
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_symbol_status " "ON positions(symbol, status)"
            )
            conn.commit()

    def open_position(
        self,
        symbol: str,
        quantity: Decimal,
        entry_price: Decimal,
        order_id: str,
    ) -> Position:
        """
        Open a new position.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            quantity: Position size in base currency
            entry_price: Entry price in quote currency
            order_id: Exchange order ID

        Returns:
            Created Position object

        Raises:
            ValueError: If position already exists for symbol
        """
        # Check for existing open position
        if self.has_open_position(symbol):
            raise ValueError(f"Open position already exists for {symbol}")

        entry_time = datetime.utcnow()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO positions
                (symbol, quantity, entry_price, entry_time, status, order_id)
                VALUES (?, ?, ?, ?, 'OPEN', ?)
                """,
                (
                    symbol,
                    float(quantity),
                    float(entry_price),
                    entry_time.isoformat(),
                    order_id,
                ),
            )
            position_id = cursor.lastrowid
            conn.commit()

        position = Position(
            position_id=position_id,
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=entry_time,
            order_id=order_id,
            status="OPEN",
        )

        logger.info(f"Opened position: {position}")
        return position

    def close_position(
        self,
        symbol: str,
        exit_price: Decimal,
        exit_order_id: str,
    ) -> Optional[Position]:
        """
        Close an open position.

        Args:
            symbol: Trading pair
            exit_price: Exit price in quote currency
            exit_order_id: Exchange order ID for exit

        Returns:
            Updated Position object, or None if no open position

        Raises:
            ValueError: If no open position exists
        """
        position = self.get_open_position(symbol)
        if not position:
            raise ValueError(f"No open position found for {symbol}")

        exit_time = datetime.utcnow()

        # Calculate PnL (assuming LONG position)
        # PnL = (exit_price - entry_price) * quantity
        pnl = (exit_price - position.entry_price) * position.quantity

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE positions
                SET exit_price = ?, exit_time = ?, pnl = ?, status = 'CLOSED'
                WHERE id = ?
                """,
                (float(exit_price), exit_time.isoformat(), float(pnl), position.id),
            )
            conn.commit()

        position.exit_price = exit_price
        position.exit_time = exit_time
        position.pnl = pnl
        position.status = "CLOSED"

        logger.info(f"Closed position: {position} | PnL: {pnl:.2f}")
        return position

    def get_open_position(self, symbol: str) -> Optional[Position]:
        """
        Get open position for symbol.

        Args:
            symbol: Trading pair

        Returns:
            Position object or None if no open position
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM positions
                WHERE symbol = ? AND status = 'OPEN'
                LIMIT 1
                """,
                (symbol,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return Position(
            position_id=row["id"],
            symbol=row["symbol"],
            quantity=Decimal(str(row["quantity"])),
            entry_price=Decimal(str(row["entry_price"])),
            entry_time=datetime.fromisoformat(row["entry_time"]),
            exit_price=Decimal(str(row["exit_price"])) if row["exit_price"] else None,
            exit_time=datetime.fromisoformat(row["exit_time"]) if row["exit_time"] else None,
            pnl=Decimal(str(row["pnl"])) if row["pnl"] else None,
            status=row["status"],
            order_id=row["order_id"],
        )

    def get_all_open_positions(self) -> list[Position]:
        """
        Get all open positions.

        Returns:
            List of Position objects
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM positions WHERE status = 'OPEN' ORDER BY entry_time DESC"
            )
            rows = cursor.fetchall()

        positions = []
        for row in rows:
            positions.append(
                Position(
                    position_id=row["id"],
                    symbol=row["symbol"],
                    quantity=Decimal(str(row["quantity"])),
                    entry_price=Decimal(str(row["entry_price"])),
                    entry_time=datetime.fromisoformat(row["entry_time"]),
                    order_id=row["order_id"],
                    status=row["status"],
                )
            )

        return positions

    def has_open_position(self, symbol: str) -> bool:
        """
        Check if open position exists for symbol.

        Args:
            symbol: Trading pair

        Returns:
            True if open position exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM positions WHERE symbol = ? AND status = 'OPEN'",
                (symbol,),
            )
            count = cursor.fetchone()[0]

        return count > 0

    def calculate_unrealized_pnl(self, symbol: str, current_price: Decimal) -> Optional[Decimal]:
        """
        Calculate unrealized PnL for open position.

        Args:
            symbol: Trading pair
            current_price: Current market price

        Returns:
            Unrealized PnL or None if no open position
        """
        position = self.get_open_position(symbol)
        if not position:
            return None

        # Unrealized PnL = (current_price - entry_price) * quantity
        unrealized_pnl = (current_price - position.entry_price) * position.quantity
        return unrealized_pnl

    def get_total_pnl(self) -> Decimal:
        """
        Get total realized PnL from all closed positions.

        Returns:
            Total PnL
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM positions WHERE status = 'CLOSED'"
            )
            total = cursor.fetchone()[0]

        return Decimal(str(total))

    def get_position_history(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> list[Position]:
        """
        Get position history (closed positions).

        Args:
            symbol: Optional symbol filter
            limit: Maximum number of results

        Returns:
            List of closed Position objects
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if symbol:
                cursor = conn.execute(
                    """
                    SELECT * FROM positions
                    WHERE symbol = ? AND status = 'CLOSED'
                    ORDER BY exit_time DESC
                    LIMIT ?
                    """,
                    (symbol, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM positions
                    WHERE status = 'CLOSED'
                    ORDER BY exit_time DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()

        positions = []
        for row in rows:
            positions.append(
                Position(
                    position_id=row["id"],
                    symbol=row["symbol"],
                    quantity=Decimal(str(row["quantity"])),
                    entry_price=Decimal(str(row["entry_price"])),
                    entry_time=datetime.fromisoformat(row["entry_time"]),
                    exit_price=Decimal(str(row["exit_price"])) if row["exit_price"] else None,
                    exit_time=(
                        datetime.fromisoformat(row["exit_time"]) if row["exit_time"] else None
                    ),
                    pnl=Decimal(str(row["pnl"])) if row["pnl"] else None,
                    status=row["status"],
                    order_id=row["order_id"],
                )
            )

        return positions
