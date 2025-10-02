"""Tests for position tracking functionality."""

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from src.models.position import PositionTracker


@pytest.fixture
def temp_db() -> str:
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def tracker(temp_db: str) -> PositionTracker:
    """Create a PositionTracker instance with temporary database."""
    return PositionTracker(db_path=temp_db)


def test_position_tracker_initialization(temp_db: str) -> None:
    """Test PositionTracker initialization."""
    tracker = PositionTracker(db_path=temp_db)
    assert tracker.db_path == temp_db
    assert Path(temp_db).exists()


def test_open_position(tracker: PositionTracker) -> None:
    """Test opening a new position."""
    position = tracker.open_position(
        symbol="BTCUSDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.00"),
        order_id="123456",
    )

    assert position.id is not None
    assert position.symbol == "BTCUSDT"
    assert position.quantity == Decimal("0.1")
    assert position.entry_price == Decimal("50000.00")
    assert position.status == "OPEN"
    assert position.order_id == "123456"


def test_cannot_open_duplicate_position(tracker: PositionTracker) -> None:
    """Test that opening duplicate position raises error."""
    tracker.open_position(
        symbol="BTCUSDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.00"),
        order_id="123456",
    )

    with pytest.raises(ValueError, match="Open position already exists"):
        tracker.open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.2"),
            entry_price=Decimal("51000.00"),
            order_id="789012",
        )


def test_get_open_position(tracker: PositionTracker) -> None:
    """Test retrieving an open position."""
    original = tracker.open_position(
        symbol="ETHUSDT",
        quantity=Decimal("1.5"),
        entry_price=Decimal("3000.00"),
        order_id="111222",
    )

    retrieved = tracker.get_open_position("ETHUSDT")

    assert retrieved is not None
    assert retrieved.id == original.id
    assert retrieved.symbol == original.symbol
    assert retrieved.quantity == original.quantity
    assert retrieved.entry_price == original.entry_price


def test_get_nonexistent_position(tracker: PositionTracker) -> None:
    """Test getting position that doesn't exist."""
    position = tracker.get_open_position("BTCUSDT")
    assert position is None


def test_close_position(tracker: PositionTracker) -> None:
    """Test closing an open position."""
    tracker.open_position(
        symbol="BTCUSDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.00"),
        order_id="123456",
    )

    closed = tracker.close_position(
        symbol="BTCUSDT",
        exit_price=Decimal("52000.00"),
        exit_order_id="654321",
    )

    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.exit_price == Decimal("52000.00")
    assert closed.pnl is not None
    # PnL = (52000 - 50000) * 0.1 = 200
    assert closed.pnl == Decimal("200.00")


def test_cannot_close_nonexistent_position(tracker: PositionTracker) -> None:
    """Test that closing non-existent position raises error."""
    with pytest.raises(ValueError, match="No open position found"):
        tracker.close_position(
            symbol="BTCUSDT",
            exit_price=Decimal("52000.00"),
            exit_order_id="654321",
        )


def test_has_open_position(tracker: PositionTracker) -> None:
    """Test checking for open position existence."""
    assert not tracker.has_open_position("BTCUSDT")

    tracker.open_position(
        symbol="BTCUSDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.00"),
        order_id="123456",
    )

    assert tracker.has_open_position("BTCUSDT")

    tracker.close_position(
        symbol="BTCUSDT",
        exit_price=Decimal("52000.00"),
        exit_order_id="654321",
    )

    assert not tracker.has_open_position("BTCUSDT")


def test_get_all_open_positions(tracker: PositionTracker) -> None:
    """Test retrieving all open positions."""
    tracker.open_position(
        symbol="BTCUSDT", quantity=Decimal("0.1"), entry_price=Decimal("50000"), order_id="1"
    )
    tracker.open_position(
        symbol="ETHUSDT", quantity=Decimal("1.0"), entry_price=Decimal("3000"), order_id="2"
    )
    tracker.open_position(
        symbol="BNBUSDT", quantity=Decimal("5.0"), entry_price=Decimal("300"), order_id="3"
    )

    positions = tracker.get_all_open_positions()

    assert len(positions) == 3
    symbols = {p.symbol for p in positions}
    assert symbols == {"BTCUSDT", "ETHUSDT", "BNBUSDT"}


def test_calculate_unrealized_pnl(tracker: PositionTracker) -> None:
    """Test unrealized PnL calculation."""
    tracker.open_position(
        symbol="BTCUSDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.00"),
        order_id="123456",
    )

    # Current price higher than entry
    pnl = tracker.calculate_unrealized_pnl("BTCUSDT", Decimal("55000.00"))
    assert pnl == Decimal("500.00")  # (55000 - 50000) * 0.1

    # Current price lower than entry
    pnl = tracker.calculate_unrealized_pnl("BTCUSDT", Decimal("48000.00"))
    assert pnl == Decimal("-200.00")  # (48000 - 50000) * 0.1


def test_calculate_unrealized_pnl_no_position(tracker: PositionTracker) -> None:
    """Test unrealized PnL for non-existent position."""
    pnl = tracker.calculate_unrealized_pnl("BTCUSDT", Decimal("50000.00"))
    assert pnl is None


def test_get_total_pnl(tracker: PositionTracker) -> None:
    """Test total PnL calculation from closed positions."""
    # Open and close first position (profit)
    tracker.open_position(
        symbol="BTCUSDT",
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.00"),
        order_id="1",
    )
    tracker.close_position(symbol="BTCUSDT", exit_price=Decimal("52000.00"), exit_order_id="2")

    # Open and close second position (loss)
    tracker.open_position(
        symbol="ETHUSDT",
        quantity=Decimal("1.0"),
        entry_price=Decimal("3000.00"),
        order_id="3",
    )
    tracker.close_position(symbol="ETHUSDT", exit_price=Decimal("2800.00"), exit_order_id="4")

    total_pnl = tracker.get_total_pnl()
    # (52000-50000)*0.1 + (2800-3000)*1.0 = 200 - 200 = 0
    assert total_pnl == Decimal("0.00")


def test_get_position_history(tracker: PositionTracker) -> None:
    """Test retrieving position history."""
    # Open and close multiple positions
    for i in range(3):
        tracker.open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            order_id=f"entry_{i}",
        )
        tracker.close_position(
            symbol="BTCUSDT",
            exit_price=Decimal("51000.00"),
            exit_order_id=f"exit_{i}",
        )

    history = tracker.get_position_history(symbol="BTCUSDT", limit=10)

    assert len(history) == 3
    assert all(p.status == "CLOSED" for p in history)
    assert all(p.symbol == "BTCUSDT" for p in history)
