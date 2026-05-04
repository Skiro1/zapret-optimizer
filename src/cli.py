"""CLI commands implementation for zapret optimizer."""

import sys
import time
from pathlib import Path
from typing import Any

from .state import OptimizerState
from .utils import (
    is_admin, find_zapret_dir, check_curl, check_winws,
    stop_winws, print_colored, Logger, print_progress,
    backup_zapret, compare_configs, get_site_failures
)
from .config_parser import find_all_configs, parse_all_configs, ZapretConfig
from .tester import ConfigTester, TestResult
from .mutator import ConfigMutator
from .tg_proxy_manager import TgProxyManager
from .warp_manager import WARPManager
from .dependency_manager import DependencyManager


class OptimizerCLI:
    """Main CLI controller for zapret optimizer."""

    def __init__(self, base_dir: Path | None = None, sites_file: Path | None = None):
        self.base_dir = base_dir or Path.cwd()
        self.sites_file = sites_file
        self.state = OptimizerState(self.base_dir)
        self.zapret_dir: Path | None = None
        self.tester: ConfigTester | None = None
        self.logger = Logger(self.base_dir)
        self.tg_proxy = TgProxyManager(self.base_dir)
        self.warp = WARPManager(self.base_dir)
        self.deps = DependencyManager(self.base_dir)

    def cmd_init(self) -> int:
        """Initialize optimizer - check environment."""
        print_colored("=== Zapret Optimizer Initialization ===", "cyan")

        # Check admin rights
        if not is_admin():
            print_colored("[FAIL] Administrator rights required", "red")
            print_colored("       Please run as Administrator", "yellow")
            return 1
        print_colored("[OK] Running as Administrator", "green")

        # Find zapret directory
        self.zapret_dir = find_zapret_dir(self.base_dir)
        if not self.zapret_dir:
            print_colored("[FAIL] Zapret directory not found", "red")
            print_colored("       Expected 'zapret/' folder with bin/winws.exe", "yellow")
            return 1
        print_colored(f"[OK] Found zapret at: {self.zapret_dir}", "green")

        # Check curl
        curl_ok, curl_msg = check_curl()
        if not curl_ok:
            print_colored(f"[FAIL] curl check failed: {curl_msg}", "red")
            return 1
        print_colored(f"[OK] curl available: {curl_msg.split()[0]}...", "green")

        # Check winws
        winws_ok, winws_path = check_winws(self.zapret_dir)
        if not winws_ok:
            print_colored(f"[FAIL] winws.exe not found: {winws_path}", "red")
            return 1
        print_colored(f"[OK] winws.exe found", "green")

        # Count existing configs
        existing_configs = find_all_configs(self.zapret_dir)
        print_colored(f"[OK] Found {len(existing_configs)} existing configs", "green")

        # Save init state
        init_check = {
            "admin": True,
            "zapret_dir": str(self.zapret_dir),
            "curl": curl_msg,
            "winws": winws_path,
            "existing_configs": len(existing_configs),
        }
        self.state.set_initialized(init_check)

        print_colored("\n[OK] Initialization complete!", "green")
        print_colored("     Run 'optimize' to start optimization.", "gray")

        return 0

    def _ensure_ready(self) -> bool:
        """Check if optimizer is ready to run."""
        if not self.state.is_initialized():
            print_colored("[ERROR] Optimizer not initialized. Run 'init' first.", "red")
            return False

        if not self.zapret_dir:
            self.zapret_dir = find_zapret_dir(self.base_dir)

        if not self.zapret_dir or not self.zapret_dir.exists():
            print_colored("[ERROR] Zapret directory not found.", "red")
            return False

        if not self.tester:
            self.tester = ConfigTester(self.zapret_dir, sites_file=self.sites_file)

        return True

    def _run_cycle_1(self) -> bool:
        """Run cycle 1: Test all existing configs."""
        print_colored("\n=== Cycle 1: Testing existing configs ===", "cyan")

        config_paths = find_all_configs(self.zapret_dir)
        if not config_paths:
            print_colored("[ERROR] No configs found to test", "red")
            return False

        print_colored(f"Testing {len(config_paths)} existing configurations...", "gray")

        output_dir = self.state.get_config_dir(1)
        output_dir.mkdir(parents=True, exist_ok=True)
        tested = []

        for i, config_path in enumerate(config_paths, 1):
            print_colored(f"\n[{i}/{len(config_paths)}] Testing {config_path.name}...", "cyan")

            # Copy config to cycle-1 folder
            try:
                config = ZapretConfig.from_bat_file(config_path)
                config.copy_original(output_dir)
                dest_path = output_dir / config_path.name
            except Exception as e:
                print_colored(f"  [WARN] Could not copy config: {e}", "yellow")
                dest_path = config_path

            # Test the copied config (not original)
            result = self.tester.test_config(dest_path, dest_path.stem)

            # Save result
            self.state.add_config_result(
                cycle=1,
                config_name=result.config_name,
                score=result.score,
                details={
                    "total_tests": result.total_tests,
                    "passed_tests": result.passed_tests,
                    "path": str(dest_path),
                    "avg_response": sum(result.response_times_ms.values()) / max(1, len(result.response_times_ms)),
                    "download_speed": result.details.get("download_speed", {}).get("speed_mbps", 0),
                }
            )
            tested.append(result)

        # Show summary
        if tested:
            best = max(tested, key=lambda r: r.score)
            print_colored(f"\nCycle 1 complete! Best config: {best.config_name} (score: {best.score:.1f})", "green")

        return True

    def _run_cycle_2(self) -> bool:
        """Run cycle 2: Mutate best configs from cycle 1."""
        print_colored("\n=== Cycle 2: Mutating best configs ===", "cyan")

        # Get best configs from cycle 1
        cycle1_results = self.state.get_cycle_results(1)
        if not cycle1_results:
            print_colored("[ERROR] No results from cycle 1", "red")
            return False

        # Sort by score (descending), then by avg_response (ascending) as tie-breaker
        sorted_results = sorted(
            cycle1_results,
            key=lambda r: (r["score"], -r.get("details", {}).get("avg_response", float('inf'))),
            reverse=True
        )
        top_count = max(3, len(sorted_results) // 2)
        top_results = sorted_results[:top_count]

        print_colored(f"Taking top {len(top_results)} configs from cycle 1 for mutation...", "gray")

        # Parse top configs
        configs_to_mutate = []
        scores = {}
        for result in top_results:
            try:
                config_path = Path(result["details"]["path"])
                if config_path.exists():
                    config = ZapretConfig.from_bat_file(config_path)
                    configs_to_mutate.append(config)
                    scores[config.name] = result["score"]
            except Exception as e:
                print_colored(f"  [WARN] Could not load {result['name']}: {e}", "yellow")

        if not configs_to_mutate:
            print_colored("[WARN] No valid configs to mutate, using originals", "yellow")
            configs_to_mutate = parse_all_configs(self.zapret_dir)[:5]

        # Generate mutations
        mutator = ConfigMutator()
        num_to_generate = min(20, len(configs_to_mutate) * 3)
        variants = mutator.generate_from_best(configs_to_mutate, scores, num_to_generate, cycle=2)

        print_colored(f"Generated {len(variants)} variants, testing...", "gray")

        # Test variants
        output_dir = self.state.get_config_dir(2)
        output_dir.mkdir(parents=True, exist_ok=True)
        # Add cycle prefix to avoid name collisions
        for v in variants:
            v.name = f"c2_{v.name}"
        bat_paths = mutator.create_variant_bat_files(variants, output_dir)

        for i, bat_path in enumerate(bat_paths, 1):
            print_colored(f"\n[{i}/{len(bat_paths)}] Testing {bat_path.name}...", "cyan")
            result = self.tester.test_config(bat_path)
            self.state.add_config_result(
                cycle=2,
                config_name=result.config_name,
                score=result.score,
                details={
                    "total_tests": result.total_tests,
                    "passed_tests": result.passed_tests,
                    "path": str(bat_path),
                    "avg_response": sum(result.response_times_ms.values()) / max(1, len(result.response_times_ms)),
                    "download_speed": result.details.get("download_speed", {}).get("speed_mbps", 0),
                }
            )

        print_colored(f"\nCycle 2 complete!", "green")
        return True

    def _run_cycle_3(self) -> bool:
        """Run cycle 3: Combine best configs."""
        print_colored("\n=== Cycle 3: Combining best configs ===", "cyan")

        # Get best from all previous cycles
        all_results = self.state.get_all_configs_sorted()
        if len(all_results) < 2:
            print_colored("[WARN] Not enough results for combination, using mutations", "yellow")
            return self._run_cycle_2()  # Fallback

        # Take top configs
        top_results = all_results[:max(4, len(all_results) // 3)]
        print_colored(f"Taking top {len(top_results)} configs for combination...", "gray")

        # Parse configs
        configs = []
        scores = {}
        for result in top_results:
            try:
                path = Path(result["details"]["path"])
                if path.exists():
                    config = ZapretConfig.from_bat_file(path)
                    configs.append(config)
                    scores[config.name] = result["score"]
            except Exception as e:
                print_colored(f"  [WARN] Could not load {result['name']}: {e}", "yellow")

        if len(configs) < 2:
            print_colored("[WARN] Not enough configs for hybrid, using mutations", "yellow")
            mutator = ConfigMutator()
            variants = mutator.mutate_config(configs[0] if configs else parse_all_configs(self.zapret_dir)[0], num_variants=10)
        else:
            # Generate hybrids
            mutator = ConfigMutator()
            variants = mutator.generate_from_best(configs, scores, num_to_generate=15, cycle=3)

        print_colored(f"Generated {len(variants)} hybrids, testing...", "gray")

        # Test hybrids
        output_dir = self.state.get_config_dir(3)
        output_dir.mkdir(parents=True, exist_ok=True)
        # Add cycle prefix to avoid name collisions
        for v in variants:
            v.name = f"c3_{v.name}"
        bat_paths = mutator.create_variant_bat_files(variants, output_dir)

        for i, bat_path in enumerate(bat_paths, 1):
            print_colored(f"\n[{i}/{len(bat_paths)}] Testing {bat_path.name}...", "cyan")
            result = self.tester.test_config(bat_path)
            self.state.add_config_result(
                cycle=3,
                config_name=result.config_name,
                score=result.score,
                details={
                    "total_tests": result.total_tests,
                    "passed_tests": result.passed_tests,
                    "path": str(bat_path),
                    "avg_response": sum(result.response_times_ms.values()) / max(1, len(result.response_times_ms)),
                    "download_speed": result.details.get("download_speed", {}).get("speed_mbps", 0),
                }
            )

        return True

    def _select_best(self) -> None:
        """Select the absolute best config from all cycles."""
        all_results = self.state.get_all_configs_sorted()

        if not all_results:
            print_colored("[ERROR] No test results to select best from", "red")
            return

        best = all_results[0]
        print_colored(f"\n=== Best Config Selected ===", "green")
        print_colored(f"Name: {best['name']}", "cyan")
        print_colored(f"Score: {best['score']:.1f}", "cyan")
        print_colored(f"Path: {best['details'].get('path', 'N/A')}", "cyan")

        # Copy best config to best.bat
        try:
            source_path = Path(best["details"]["path"])
            if source_path.exists():
                best_path = self.state.configs_dir / "best.bat"
                import shutil
                shutil.copy2(source_path, best_path)
                print_colored(f"Copied to: {best_path}", "green")
        except Exception as e:
            print_colored(f"[WARN] Could not copy best config: {e}", "yellow")

        self.state.set_best_config(best)

    def cmd_optimize(self) -> int:
        """Run 3-cycle optimization."""
        if not self._ensure_ready():
            return 1

        self.logger.info("Starting optimization")

        # Create backup before optimization
        if self.zapret_dir:
            print_colored("[INFO] Creating backup of zapret directory...", "gray")
            backup_path = backup_zapret(self.zapret_dir)
            print_colored(f"[OK] Backup saved to: {backup_path.name}", "green")
            self.logger.info(f"Backup created: {backup_path}")

        cycles_completed = self.state.get_cycles_completed()

        if cycles_completed >= 3:
            print_colored("[INFO] All 3 cycles already completed.", "yellow")
            print_colored("      Run 'status' to see results or 'run-best' to use best config.", "gray")
            return 0

        # Cycle 1
        if cycles_completed < 1:
            if not self._run_cycle_1():
                return 1
            self.state.set_cycles_completed(1)

        # Cycle 2
        if cycles_completed < 2:
            if not self._run_cycle_2():
                return 1
            self.state.set_cycles_completed(2)

        # Cycle 3
        if cycles_completed < 3:
            if not self._run_cycle_3():
                return 1
            self.state.set_cycles_completed(3)

        # Select best
        self._select_best()

        print_colored("\n=== Optimization Complete ===", "green")
        print_colored("Run 'status' to see full results.", "gray")
        print_colored("Run 'run-best' to start the best configuration.", "gray")

        return 0

    def cmd_run_best(self) -> int:
        """Run the best configuration."""
        if not self._ensure_ready():
            return 1

        allowed, reason = self.state.can_run_best()
        if not allowed:
            print_colored(f"[ERROR] {reason}", "red")
            return 1

        best_path = self.state.configs_dir / "best.bat"
        if not best_path.exists():
            # Try to find best config path from state
            best = self.state.get_best_config()
            if best and "path" in best.get("details", {}):
                best_path = Path(best["details"]["path"])

        if not best_path or not best_path.exists():
            print_colored("[ERROR] Best config file not found", "red")
            return 1

        print_colored(f"Starting best config: {best_path.name}", "green")
        print_colored("Press Ctrl+C to stop", "gray")

        # Stop any existing winws
        stop_winws()

        # Copy to zapret dir if needed - paths in .bat expect to be in zapret dir
        import shutil
        run_path = best_path
        if self.zapret_dir and best_path.parent != self.zapret_dir:
            run_path = self.zapret_dir / "best_runner.bat"
            shutil.copy2(best_path, run_path)

        try:
            # Run the config and wait
            import subprocess
            proc = subprocess.Popen(
                [str(run_path)],
                cwd=str(self.zapret_dir) if self.zapret_dir else None,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            proc.wait()
        except KeyboardInterrupt:
            print_colored("\nStopping...", "yellow")
            stop_winws()
        finally:
            # Cleanup temp copy
            if run_path != best_path and run_path.exists():
                try:
                    run_path.unlink()
                except Exception:
                    pass

        return 0

    def cmd_status(self) -> int:
        """Show current status."""
        summary = self.state.get_state_summary()

        print_colored("=== Zapret Optimizer Status ===", "cyan")
        print_colored(f"Initialized: {'Yes' if summary['initialized'] else 'No'}", "white")
        print_colored(f"Cycles completed: {summary['cycles_completed']}/3", "white")
        print_colored(f"Total configs tested: {summary['total_configs_tested']}", "white")

        if summary["best_config"]:
            best = summary["best_config"]
            print_colored(f"\nBest config: {best['name']}", "green")
            print_colored(f"  Score: {best['score']:.1f}", "green")

        print_colored("\nCycle summaries:", "cyan")
        for cycle, info in summary["cycle_summaries"].items():
            tested = info["tested"]
            best_name = info["best"]["name"] if info["best"] else "N/A"
            best_score = info["best"]["score"] if info["best"] else 0
            print_colored(f"  Cycle {cycle}: {tested} configs, best: {best_name} ({best_score:.1f})", "gray")

        return 0

    def cmd_list(self) -> int:
        """List all tested configs."""
        configs = self.state.get_all_configs_sorted()

        if not configs:
            print_colored("[INFO] No configs tested yet. Run 'optimize' first.", "yellow")
            return 0

        print_colored("=== All Tested Configs (by score) ===", "cyan")
        print_colored(f"{'Rank':<4}{'Name':<24}{'Score':<7}{'Tests':<7}{'Ping':<8}{'Speed':<10}{'Cyc':<4}", "gray")
        print_colored("-" * 70, "gray")

        for i, config in enumerate(configs[:30], 1):  # Show top 30
            name = config["name"][:22]
            score = f"{config['score']:.1f}"
            cycle = config.get("cycle", "?")
            details = config.get("details", {})
            passed = details.get("passed_tests", 0)
            total = details.get("total_tests", 0)
            avg_resp = details.get("avg_response", 0)
            dl_speed = details.get("download_speed", 0)
            tests_str = f"{passed}/{total}" if total > 0 else "N/A"
            ping_str = f"{avg_resp:.0f}ms" if avg_resp > 0 else "N/A"
            speed_str = f"{dl_speed:.1f}M" if dl_speed > 0 else "N/A"
            marker = " *" if i == 1 else ""
            print_colored(f"{i:<4}{name:<24}{score:<7}{tests_str:<7}{ping_str:<8}{speed_str:<10}{cycle:<4}{marker}", "white")

        if len(configs) > 30:
            print_colored(f"... and {len(configs) - 30} more", "gray")

        return 0

    def cmd_compare(self, config1: str, config2: str) -> int:
        """Compare two configurations."""
        if not self._ensure_ready():
            return 1
        path1 = self.base_dir / "configs" / config1
        path2 = self.base_dir / "configs" / config2
        if not path1.exists():
            path1 = Path(config1)
        if not path2.exists():
            path2 = Path(config2)
        print_colored("=== Comparing configs ===", "cyan")
        print_colored(f"Config 1: {path1.name}", "gray")
        print_colored(f"Config 2: {path2.name}", "gray")
        print_colored("-" * 50, "gray")
        diffs = compare_configs(path1, path2)
        for diff in diffs[:20]:
            print_colored(diff, "white")
        if len(diffs) > 20:
            print_colored(f"... and {len(diffs) - 20} more differences", "gray")
        return 0

    def cmd_install_proxy(self) -> int:
        """Check/install tg-ws-proxy."""
        print_colored("=== TG WS Proxy Installation ===", "cyan")

        exe = self.tg_proxy.find_proxy_exe()
        if exe:
            print_colored(f"[OK] Found tg-ws-proxy: {exe}", "green")
            if exe.suffix == ".exe":
                print_colored(f"     Executable: {exe.name}", "gray")
            else:
                print_colored(f"     Python source: {exe}", "gray")
        else:
            print_colored("[WARN] tg-ws-proxy not found", "yellow")
            print_colored("       Expected locations:", "gray")
            print_colored("       - TgWsProxy_windows.exe (same folder)", "gray")
            print_colored("       - tg-ws-proxy/TgWsProxy_windows.exe", "gray")
            print_colored("       - tg-ws-proxy/windows.py (source)", "gray")
            print_colored("\nDownload from: https://github.com/Flowseal/tg-ws-proxy/releases", "cyan")
            return 1

        # Ensure config exists
        config = self.tg_proxy.get_config()
        print_colored(f"\n[OK] Configuration ready", "green")
        print_colored(f"     Port: {config['port']}", "gray")
        print_colored(f"     Host: {config['host']}", "gray")
        print_colored(f"\nRun 'start-proxy' to launch the proxy", "white")
        return 0

    def cmd_start_proxy(self, port: int | None = None, host: str | None = None) -> int:
        """Start tg-ws-proxy."""
        print_colored("=== Starting TG WS Proxy ===", "cyan")

        if self.tg_proxy.is_running():
            print_colored("[INFO] Proxy is already running", "yellow")
            self.cmd_status_proxy()
            return 0

        if not self.tg_proxy.find_proxy_exe():
            print_colored("[ERROR] tg-ws-proxy not found. Run 'install-proxy' first", "red")
            return 1

        if self.tg_proxy.start(port, host):
            time.sleep(1)
            self.cmd_status_proxy()
            return 0
        return 1

    def cmd_stop_proxy(self) -> int:
        """Stop tg-ws-proxy."""
        print_colored("=== Stopping TG WS Proxy ===", "cyan")

        if not self.tg_proxy.is_running():
            print_colored("[INFO] Proxy is not running", "gray")
            return 0

        if self.tg_proxy.stop():
            return 0
        return 1

    def cmd_status_proxy(self) -> int:
        """Show tg-ws-proxy status."""
        print_colored("=== TG WS Proxy Status ===", "cyan")

        status = self.tg_proxy.get_status()

        if status["running"]:
            print_colored("[OK] Proxy is RUNNING", "green")
            print_colored(f"     Host: {status['host']}", "white")
            print_colored(f"     Port: {status['port']}", "white")
            print_colored(f"     Secret: {status['secret'][:16]}...", "gray")

            # Show connection link
            link = self.tg_proxy.get_connect_link()
            print_colored(f"\n[LINK] {link}", "cyan")
            print_colored("       Click or copy to Telegram to connect", "gray")

            # Test connection
            if self.tg_proxy.test_connection():
                print_colored("\n[OK] Port is responding", "green")
            else:
                print_colored("\n[WARN] Port not responding", "yellow")
        else:
            print_colored("[INFO] Proxy is NOT running", "gray")

        if not status["exe_found"]:
            print_colored("\n[WARN] Proxy executable not found", "yellow")
            print_colored("       Run 'install-proxy' to check", "gray")

        return 0

    def cmd_configure_proxy(self, port: int | None = None, secret: str | None = None,
                           dc_ip: list[str] | None = None) -> int:
        """Configure tg-ws-proxy settings."""
        print_colored("=== Configure TG WS Proxy ===", "cyan")

        old_config = self.tg_proxy.get_config()

        if port is not None:
            print_colored(f"[INFO] Setting port: {port}", "gray")
        if secret is not None:
            print_colored(f"[INFO] Setting custom secret", "gray")
        if dc_ip is not None:
            print_colored(f"[INFO] Setting DC-IP mappings", "gray")

        self.tg_proxy.configure(port=port, secret=secret, dc_ip=dc_ip)

        new_config = self.tg_proxy.get_config()
        print_colored(f"\n[OK] Configuration updated", "green")
        print_colored(f"     Port: {new_config['port']}", "gray")
        if port != old_config.get('port'):
            print_colored(f"     (changed from {old_config.get('port')})", "yellow")

        return 0

    def cmd_test_telegram(self) -> int:
        """Test Telegram connectivity through proxy."""
        print_colored("=== Testing Telegram Connection ===", "cyan")

        if not self.tg_proxy.is_running():
            print_colored("[ERROR] Proxy is not running. Start it first with 'start-proxy'", "red")
            return 1

        print_colored("[TEST] Checking proxy port...", "gray")
        if self.tg_proxy.test_connection():
            print_colored("[OK] Proxy is responding on port", "green")
        else:
            print_colored("[FAIL] Proxy not responding", "red")
            return 1

        config = self.tg_proxy.get_config()
        print_colored(f"\n[OK] Telegram proxy ready", "green")
        print_colored(f"     Server: {config['host']}:{config['port']}", "white")
        print_colored(f"     Type: MTProto", "white")
        print_colored(f"     Secret: {config['secret'][:16]}...", "gray")

        print_colored("\n[LINK] Click to connect in Telegram:", "cyan")
        print_colored(f"       {self.tg_proxy.get_connect_link()}", "white")

        return 0

    # === Auto-start Service Commands ===

    def _get_service_bat_path(self) -> Path:
        """Get path for auto-start service bat file."""
        return self.base_dir / "zapret-service.bat"

    def _get_registry_key(self) -> str:
        """Get registry key path for auto-start."""
        return r"Software\Microsoft\Windows\CurrentVersion\Run"

    def cmd_install_service(self) -> int:
        """Install auto-start service for best config."""
        print_colored("=== Install Auto-Start Service ===", "cyan")

        # Check if optimization was run
        if not self.state.can_run_best()[0]:
            print_colored("[ERROR] No best config found. Run 'optimize' first.", "red")
            return 1

        # Check admin rights
        if not is_admin():
            print_colored("[WARN] Admin rights recommended for service installation", "yellow")

        service_bat = self._get_service_bat_path()

        # Create service bat file
        service_content = f'''@echo off
:: Auto-start service for zapret-optimizer
cd /d "{self.base_dir}"
echo [%date% %time%] Starting zapret service... >> service.log 2>&1
call "{self.base_dir / "configs" / "cycle-3" / "best.bat"}" >> service.log 2>&1
'''
        try:
            service_bat.write_text(service_content, encoding="utf-8")
            print_colored(f"[OK] Created service file: {service_bat}", "green")
        except Exception as e:
            print_colored(f"[ERROR] Failed to create service file: {e}", "red")
            return 1

        # Add to registry auto-start
        try:
            import winreg
            key_path = self._get_registry_key()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "ZapretOptimizer", 0, winreg.REG_SZ, f'"{service_bat}"')
            print_colored("[OK] Added to Windows auto-start (Current User)", "green")
        except Exception as e:
            print_colored(f"[WARN] Could not add to registry: {e}", "yellow")
            print_colored("     Service file created but not added to auto-start.", "gray")
            print_colored(f"     Run manually: {service_bat}", "gray")
            return 0

        print_colored("\n[OK] Service installed successfully!", "green")
        print_colored("     Best config will auto-start on Windows login.", "gray")
        return 0

    def cmd_uninstall_service(self) -> int:
        """Remove auto-start service."""
        print_colored("=== Uninstall Auto-Start Service ===", "cyan")

        service_bat = self._get_service_bat_path()

        # Remove from registry
        removed_registry = False
        try:
            import winreg
            key_path = self._get_registry_key()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, "ZapretOptimizer")
                    print_colored("[OK] Removed from Windows auto-start", "green")
                    removed_registry = True
                except FileNotFoundError:
                    print_colored("[INFO] Service was not in auto-start", "gray")
        except Exception as e:
            print_colored(f"[WARN] Could not remove from registry: {e}", "yellow")

        # Remove service bat file
        if service_bat.exists():
            try:
                service_bat.unlink()
                print_colored(f"[OK] Removed service file: {service_bat}", "green")
            except Exception as e:
                print_colored(f"[WARN] Could not remove service file: {e}", "yellow")
        else:
            print_colored("[INFO] Service file not found", "gray")

        if removed_registry:
            print_colored("\n[OK] Service uninstalled successfully!", "green")
        return 0

    def cmd_service_status(self) -> int:
        """Check auto-start service status."""
        print_colored("=== Auto-Start Service Status ===", "cyan")

        service_bat = self._get_service_bat_path()

        # Check service file
        if service_bat.exists():
            print_colored(f"[OK] Service file exists: {service_bat}", "green")
        else:
            print_colored("[INFO] Service file not found", "gray")

        # Check registry
        try:
            import winreg
            key_path = self._get_registry_key()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, "ZapretOptimizer")
                    print_colored("[OK] Registered for auto-start", "green")
                    print_colored(f"     Command: {value}", "gray")
                except FileNotFoundError:
                    print_colored("[INFO] Not registered for auto-start", "gray")
        except Exception as e:
            print_colored(f"[WARN] Could not check registry: {e}", "yellow")

        # Check if best config exists
        best_bat = self.base_dir / "configs" / "cycle-3" / "best.bat"
        if best_bat.exists():
            print_colored(f"[OK] Best config exists: {best_bat}", "green")
        else:
            print_colored("[WARN] Best config not found. Run 'optimize' first.", "yellow")

        return 0

    # === WARP Config Generation ===

    def cmd_warp_generate(self, method: str = "api", force: bool = False) -> int:
        """Generate WARP AmneziaVPN configuration file."""
        print_colored("=== Generate WARP Config ===", "cyan")

        if self.warp.config_file.exists() and not force:
            print_colored("[WARN] Config already exists", "yellow")
            print_colored(f"       {self.warp.config_file}", "gray")
            print_colored("       Use --force to regenerate with new keys", "gray")
            return 0

        # Remove old state to generate new registration
        if force and self.warp.state_file.exists():
            self.warp.state_file.unlink()

        if self.warp.generate_config(method):
            return 0
        return 1

    # === Download Dependencies Commands ===

    def cmd_deps_status(self) -> int:
        """Show dependency status."""
        return 0 if self.deps.print_status() else 1

    def cmd_download_deps(self, categories: list[str] | None = None, force: bool = False) -> int:
        """Download all dependencies."""
        success = self.deps.download_all(force=force, categories=categories)
        return 0 if success else 1
