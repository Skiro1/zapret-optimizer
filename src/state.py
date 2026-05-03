"""State management for optimizer - tracks cycles, configs, and results."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class OptimizerState:
    """Manages optimizer_state.json persistence."""

    STATE_FILE = "optimizer_state.json"
    CONFIGS_DIR = "configs"

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.state_path = self.base_dir / self.STATE_FILE
        self.configs_dir = self.base_dir / self.CONFIGS_DIR
        self._data: dict[str, Any] = self._load()
        self._ensure_dirs()

    def _load(self) -> dict[str, Any]:
        """Load state from JSON or create default."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[WARN] Failed to load state: {e}, creating fresh state")

        return self._default_state()

    def _default_state(self) -> dict[str, Any]:
        """Create default state structure."""
        return {
            "initialized": False,
            "init_check": {},
            "cycles_completed": 0,
            "cycles": {
                "1": {"configs_tested": [], "best_config": None},
                "2": {"configs_tested": [], "best_config": None},
                "3": {"configs_tested": [], "best_config": None},
            },
            "all_configs": [],  # List of all tested configs with scores
            "best_config": None,  # Absolute best after all cycles
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }

    def _ensure_dirs(self) -> None:
        """Ensure config directories exist."""
        for i in [1, 2, 3]:
            (self.configs_dir / f"cycle-{i}").mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Persist current state to JSON."""
        self._data["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[ERROR] Failed to save state: {e}")

    def is_initialized(self) -> bool:
        return self._data.get("initialized", False)

    def set_initialized(self, init_check: dict) -> None:
        self._data["initialized"] = True
        self._data["init_check"] = init_check
        self.save()

    def get_cycles_completed(self) -> int:
        return self._data.get("cycles_completed", 0)

    def set_cycles_completed(self, count: int) -> None:
        self._data["cycles_completed"] = count
        self.save()

    def add_config_result(self, cycle: int, config_name: str, score: float, details: dict) -> None:
        """Add a config test result."""
        result = {
            "name": config_name,
            "cycle": cycle,
            "score": score,
            "tested_at": datetime.now().isoformat(),
            "details": details,
        }

        # Add to cycle results
        cycle_key = str(cycle)
        if cycle_key in self._data["cycles"]:
            self._data["cycles"][cycle_key]["configs_tested"].append(result)

        # Add to global list
        self._data["all_configs"].append(result)

        # Update best for this cycle
        cycle_best = self._data["cycles"][cycle_key].get("best_config")
        if cycle_best is None or score > cycle_best["score"]:
            self._data["cycles"][cycle_key]["best_config"] = result

        self.save()

    def get_cycle_results(self, cycle: int) -> list[dict]:
        """Get all results for a specific cycle."""
        return self._data["cycles"].get(str(cycle), {}).get("configs_tested", [])

    def get_best_config(self) -> dict | None:
        """Get the absolute best config after all cycles."""
        return self._data.get("best_config")

    def set_best_config(self, config: dict) -> None:
        """Set the final best config."""
        self._data["best_config"] = config
        self.save()

    def get_all_configs_sorted(self) -> list[dict]:
        """Get all configs sorted by score descending."""
        return sorted(
            self._data.get("all_configs", []),
            key=lambda x: x.get("score", 0),
            reverse=True
        )

    def get_config_dir(self, cycle: int) -> Path:
        """Get directory path for a cycle's configs."""
        return self.configs_dir / f"cycle-{cycle}"

    def can_run_best(self) -> tuple[bool, str]:
        """Check if run-best command is allowed. Returns (allowed, reason)."""
        if not self.is_initialized():
            return False, "Optimizer not initialized. Run 'init' first."

        cycles = self.get_cycles_completed()
        if cycles < 3:
            return False, f"Optimization not complete. Only {cycles}/3 cycles finished. Run 'optimize' first."

        best = self.get_best_config()
        if best is None:
            return False, "No best config found despite 3 cycles. This is unexpected."

        return True, "OK"

    def get_state_summary(self) -> dict:
        """Get summary of current state for display."""
        return {
            "initialized": self.is_initialized(),
            "cycles_completed": self.get_cycles_completed(),
            "total_configs_tested": len(self._data.get("all_configs", [])),
            "best_config": self.get_best_config(),
            "cycle_summaries": {
                str(i): {
                    "tested": len(self._data["cycles"][str(i)]["configs_tested"]),
                    "best": self._data["cycles"][str(i)].get("best_config"),
                }
                for i in [1, 2, 3]
            }
        }
