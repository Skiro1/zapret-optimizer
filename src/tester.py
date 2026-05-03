"""Config testing engine - runs configs and evaluates them."""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from .utils import stop_winws, load_targets_from_file, get_default_targets


@dataclass
class TestResult:
    """Result of testing a single config."""
    config_name: str
    score: float  # 0-100
    total_tests: int
    passed_tests: int
    response_times_ms: dict[str, float]  # Average response times per target
    details: dict[str, Any]


class ConfigTester:
    """Tests zapret configurations by running them and making HTTP/ping checks."""

    def __init__(self, zapret_dir: Path, timeout: int = 5, wait_after_start: int = 5):
        self.zapret_dir = zapret_dir
        self.timeout = timeout
        self.wait_after_start = wait_after_start
        self.targets = self._load_targets()

    def _load_targets(self) -> dict[str, str]:
        """Load test targets."""
        targets = load_targets_from_file(self.zapret_dir)
        if not targets:
            targets = get_default_targets()
        return targets

    def _test_url(self, url: str) -> dict[str, Any]:
        """Test a single URL with HTTP/1.1, TLS 1.2, and TLS 1.3."""
        results = {
            "http11": {"success": False, "code": None, "time_ms": 0},
            "tls12": {"success": False, "code": None, "time_ms": 0},
            "tls13": {"success": False, "code": None, "time_ms": 0},
        }

        test_specs = [
            ("http11", ["--http1.1"]),
            ("tls12", ["--tlsv1.2", "--tls-max", "1.2"]),
            ("tls13", ["--tlsv1.3", "--tls-max", "1.3"]),
        ]

        for test_name, extra_args in test_specs:
            start_time = time.time()
            try:
                result = subprocess.run(
                    [
                        "curl.exe",
                        "-I", "-s",
                        "-m", str(self.timeout),
                        "-o", "NUL",
                        "-w", "%{http_code}",
                        "--show-error"
                    ] + extra_args + [url],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout + 2
                )
                elapsed_ms = (time.time() - start_time) * 1000

                code_str = result.stdout.strip()
                # Check if we got a valid HTTP code (3 digits)
                if result.returncode == 0 and code_str.isdigit() and len(code_str) == 3:
                    results[test_name]["success"] = True
                    results[test_name]["code"] = int(code_str)
                    results[test_name]["time_ms"] = elapsed_ms
                else:
                    # Check for SSL/unsupported errors
                    stderr = result.stderr.lower()
                    if any(x in stderr for x in ["not supported", "unrecognized", "unknown option"]):
                        results[test_name]["code"] = "UNSUP"
                    elif any(x in stderr for x in ["certificate", "ssl"]):
                        results[test_name]["code"] = "SSL"
                    else:
                        results[test_name]["code"] = "ERR"

            except subprocess.TimeoutExpired:
                results[test_name]["code"] = "TIMEOUT"
            except Exception as e:
                results[test_name]["code"] = f"EXCEPTION: {e}"

        return results

    def _test_ping(self, host: str) -> dict[str, Any]:
        """Test ping to a host."""
        result = {
            "success": False,
            "avg_ms": 0,
            "lost": 0,
        }

        try:
            ping_result = subprocess.run(
                ["ping", "-n", "3", "-w", str(self.timeout * 1000), host],
                capture_output=True,
                text=True,
                timeout=self.timeout * 4
            )

            if ping_result.returncode == 0:
                # Parse ping output
                # Average = Xms or Average = X ms
                output = ping_result.stdout
                avg_match = __import__('re').search(r'Average\s*=\s*(\d+)\s*ms', output)
                lost_match = __import__('re').search(r'Lost\s*=\s*(\d+)', output)

                if avg_match:
                    result["success"] = True
                    result["avg_ms"] = int(avg_match.group(1))
                elif "Reply from" in output:
                    result["success"] = True
                    result["avg_ms"] = 50  # Estimate if no average

                if lost_match:
                    result["lost"] = int(lost_match.group(1))

        except subprocess.TimeoutExpired:
            result["avg_ms"] = "TIMEOUT"
        except Exception as e:
            result["avg_ms"] = f"ERROR: {e}"

        return result

    def test_config(self, bat_path: Path, config_name: str | None = None) -> TestResult:
        """Test a single config file."""
        name = config_name or bat_path.stem
        print(f"  [TEST] {name} - Starting...")

        # Stop any existing winws
        stop_winws()
        time.sleep(1)

        # Start the config
        try:
            # Copy bat to zapret dir temporarily if it's elsewhere
            if bat_path.parent != self.zapret_dir:
                temp_bat = self.zapret_dir / bat_path.name
                __import__('shutil').copy2(bat_path, temp_bat)
                run_bat = temp_bat
            else:
                run_bat = bat_path

            # Run the .bat file
            proc = subprocess.Popen(
                [str(run_bat)],
                cwd=str(self.zapret_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )

            # Wait for winws to initialize
            time.sleep(self.wait_after_start)

            # Check if winws is running
            check = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq winws.exe"],
                capture_output=True, text=True
            )
            if "winws.exe" not in check.stdout:
                print(f"    [WARN] winws.exe not running after start")

        except Exception as e:
            print(f"    [ERROR] Failed to start config: {e}")
            stop_winws()
            return TestResult(
                config_name=name,
                score=0,
                total_tests=0,
                passed_tests=0,
                response_times_ms={},
                details={"error": str(e)}
            )

        # Run tests
        total_tests = 0
        passed_tests = 0
        response_times = {}
        all_details = {}

        for target_name, target_value in self.targets.items():
            if target_value.startswith("PING:"):
                # Ping test
                host = target_value.replace("PING:", "").strip()
                ping_result = self._test_ping(host)
                total_tests += 1
                if ping_result["success"]:
                    passed_tests += 1
                response_times[target_name] = ping_result.get("avg_ms", 9999)
                all_details[target_name] = ping_result
            else:
                # HTTP/HTTPS test
                url = target_value
                url_results = self._test_url(url)

                for test_type, test_data in url_results.items():
                    total_tests += 1
                    if test_data["success"]:
                        passed_tests += 1

                response_times[target_name] = (
                    url_results["http11"]["time_ms"] +
                    url_results["tls12"]["time_ms"] +
                    url_results["tls13"]["time_ms"]
                ) / 3
                all_details[target_name] = url_results

        # Calculate score (percentage of successful tests)
        score = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Speed bonus: normalize response time penalty
        avg_response = sum(
            v for v in response_times.values()
            if isinstance(v, (int, float)) and v > 0
        ) / max(1, len([v for v in response_times.values() if isinstance(v, (int, float)) and v > 0]))

        # Penalize slow configs slightly (max 5 point penalty for very slow)
        speed_penalty = min(5, avg_response / 200)
        adjusted_score = max(0, score - speed_penalty)

        print(f"    Score: {adjusted_score:.1f} ({passed_tests}/{total_tests} tests, avg {avg_response:.0f}ms)")

        # Cleanup
        stop_winws()

        # Remove temp file if we copied it
        if bat_path.parent != self.zapret_dir and 'temp_bat' in dir() and temp_bat.exists():
            temp_bat.unlink()

        return TestResult(
            config_name=name,
            score=adjusted_score,
            total_tests=total_tests,
            passed_tests=passed_tests,
            response_times_ms=response_times,
            details=all_details
        )

    def test_configs(self, config_paths: list[Path]) -> list[TestResult]:
        """Test multiple configs and return results."""
        results = []
        for i, path in enumerate(config_paths, 1):
            print(f"[{i}/{len(config_paths)}] Testing {path.name}...")
            result = self.test_config(path)
            results.append(result)
            # Brief pause between tests
            time.sleep(2)

        return results
