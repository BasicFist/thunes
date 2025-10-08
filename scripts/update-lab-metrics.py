#!/usr/bin/env python3
"""Update LAB infrastructure metrics for Prometheus.

This script updates MCP server health and worktree status metrics
by querying the LAB workspace infrastructure.

Run periodically (e.g., every 30s) to keep Grafana dashboard current.
"""

import sys
import subprocess
from pathlib import Path

# Add src to path for prometheus_metrics import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring import prometheus_metrics


# MCP servers configured in ~/LAB/.mcp.json
MCP_SERVERS = [
    "filesystem",
    "fetch",
    "sqlite",
    "git",
    "github",
    "playwright",
    "jupyter",
    "openapi",
    "context7",
    "perplexity",
    "sequential",
    "cloudflare-browser",
    "cloudflare-radar",
    "cloudflare-container",
    "cloudflare-docs",
    "cloudflare-bindings",
    "cloudflare-observability",
    "rag-query",
]

# Worktree paths and names
WORKTREES = {
    "main": Path.home() / "LAB",
    "dev": Path.home() / "LAB" / "worktrees" / "dev",
    "experimental": Path.home() / "LAB" / "worktrees" / "experimental",
    "cloudflare": Path.home() / "LAB" / "worktrees" / "cloudflare",
    "thunes": Path.home() / "LAB" / "worktrees" / "thunes",
}


def check_mcp_health(server_name: str) -> str:
    """Check MCP server health via health check script.

    Args:
        server_name: MCP server name (e.g., "rag-query")

    Returns:
        Health status: "up", "down", or "not_configured"
    """
    health_script = Path.home() / "LAB" / "bin" / f"mcp-{server_name}-health"

    # Check if health script exists
    if not health_script.exists():
        return "not_configured"

    # Run health check (exit code: 0=OK, 1=failed, 2=not configured)
    try:
        result = subprocess.run(
            [str(health_script)],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return "up"
        elif result.returncode == 2:
            return "not_configured"
        else:
            return "down"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "down"


def read_worktree_metadata(worktree_path: Path) -> tuple[str, str]:
    """Read worktree metadata from .worktree file.

    Args:
        worktree_path: Path to worktree directory

    Returns:
        Tuple of (status, test_status)
    """
    worktree_file = worktree_path / ".worktree"

    # Default values if file doesn't exist
    if not worktree_file.exists():
        return ("working", "unknown")

    # Read and parse .worktree file (bash-sourceable format)
    status = "working"
    test_status = "unknown"

    try:
        with open(worktree_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("status="):
                    status = line.split("=", 1)[1].strip('"')
                elif line.startswith("test_status="):
                    test_status = line.split("=", 1)[1].strip('"')
    except Exception:
        pass

    return (status, test_status)


def update_all_metrics() -> None:
    """Update all LAB infrastructure metrics."""
    print("Updating LAB infrastructure metrics...")

    # Update MCP server health
    print(f"\nChecking {len(MCP_SERVERS)} MCP servers:")
    for server_name in MCP_SERVERS:
        health = check_mcp_health(server_name)
        prometheus_metrics.update_mcp_health(server_name, health)
        symbol = "✓" if health == "up" else ("⚠" if health == "not_configured" else "✗")
        print(f"  {symbol} {server_name}: {health}")

    # Update worktree status
    print(f"\nReading {len(WORKTREES)} worktree metadata:")
    for worktree_name, worktree_path in WORKTREES.items():
        status, test_status = read_worktree_metadata(worktree_path)
        prometheus_metrics.update_worktree_status(worktree_name, status)
        prometheus_metrics.update_worktree_test_status(worktree_name, test_status)
        print(f"  • {worktree_name}: status={status}, tests={test_status}")

    print("\n✓ LAB metrics updated")


if __name__ == "__main__":
    update_all_metrics()
