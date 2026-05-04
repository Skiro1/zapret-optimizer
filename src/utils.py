"""Utility functions for zapret optimizer."""

import subprocess
import sys
import os
from pathlib import Path


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def find_zapret_dir(start_dir: Path | None = None) -> Path | None:
    """Find zapret directory relative to current location."""
    search_paths = [
        start_dir or Path.cwd(),
        (start_dir or Path.cwd()).parent,
        (start_dir or Path.cwd()).parent.parent,
    ]

    for base in search_paths:
        zapret_path = base / "zapret"
        if zapret_path.exists() and (zapret_path / "bin" / "winws.exe").exists():
            return zapret_path

    return None


def check_curl() -> tuple[bool, str]:
    """Check if curl.exe is available."""
    try:
        result = subprocess.run(
            ["curl.exe", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.splitlines()[0] if result.stdout else "unknown"
            return True, version
        return False, "curl.exe returned error"
    except FileNotFoundError:
        return False, "curl.exe not found in PATH"
    except Exception as e:
        return False, f"Error checking curl: {e}"


def check_winws(zapret_dir: Path) -> tuple[bool, str]:
    """Check if winws.exe exists in zapret/bin."""
    winws_path = zapret_dir / "bin" / "winws.exe"
    if winws_path.exists():
        return True, str(winws_path)
    return False, f"winws.exe not found at {winws_path}"


def stop_winws() -> bool:
    """Stop any running winws.exe processes."""
    try:
        subprocess.run(
            ["taskkill", "/IM", "winws.exe", "/F"],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        return False


def get_default_targets() -> dict[str, str]:
    """Get default test targets (matching zapret test script)."""
    return {
        "DiscordMain": "https://discord.com",
        "DiscordGateway": "https://gateway.discord.gg",
        "DiscordCDN": "https://cdn.discordapp.com",
        "DiscordUpdates": "https://updates.discord.com",
        "YouTubeWeb": "https://www.youtube.com",
        "YouTubeShort": "https://youtu.be",
        "YouTubeImage": "https://i.ytimg.com",
        "YouTubeVideoRedirect": "https://redirector.googlevideo.com",
        "GoogleMain": "https://www.google.com",
        "GoogleGstatic": "https://www.gstatic.com",
        "CloudflareWeb": "https://www.cloudflare.com",
        "CloudflareCDN": "https://cdnjs.cloudflare.com",
        "CloudflareDNS1111": "PING:1.1.1.1",
        "CloudflareDNS1001": "PING:1.0.0.1",
        "GoogleDNS8888": "PING:8.8.8.8",
        "GoogleDNS8844": "PING:8.8.4.4",
        "Quad9DNS9999": "PING:9.9.9.9",
    }


def load_targets_from_file(zapret_dir: Path, custom_file: Path | None = None) -> dict[str, str]:
    """Load targets from file.

    Args:
        zapret_dir: Path to zapret directory (for default targets.txt)
        custom_file: Optional custom sites file path
    """
    targets_file = custom_file if custom_file else (zapret_dir / "utils" / "targets.txt")
    targets = {}

    if targets_file.exists():
        try:
            with open(targets_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Parse Key = "value" format
                        if "=" in line:
                            parts = line.split("=", 1)
                            key = parts[0].strip()
                            val = parts[1].strip().strip('"')
                            targets[key] = val
        except Exception as e:
            print(f"[WARN] Could not load targets from file: {e}")

    return targets


def print_colored(text: str, color: str = "white") -> None:
    """Print colored text to console. Uses Win32 API on Windows, ANSI on other platforms."""
    import sys

    if sys.platform != "win32":
        colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "cyan": "\033[96m",
            "white": "\033[0m",
            "gray": "\033[90m",
        }
        reset = "\033[0m"
        print(f"{colors.get(color, colors['white'])}{text}{reset}")
        return

    # Windows: use SetConsoleTextAttribute via ctypes
    import ctypes

    STD_OUTPUT_HANDLE = -11
    handle = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

    # Windows console color attributes (foreground only)
    # 0=Black 1=Blue 2=Green 3=Cyan 4=Red 5=Magenta 6=Yellow 7=White
    # 8=BrightBlack 9=BrightBlue 10=BrightGreen 11=BrightCyan
    # 12=BrightRed 13=BrightMagenta 14=BrightYellow 15=BrightWhite
    color_map = {
        "red": 12,      # BrightRed
        "green": 10,    # BrightGreen
        "yellow": 14,   # BrightYellow
        "cyan": 11,     # BrightCyan
        "white": 7,     # White
        "gray": 8,      # BrightBlack (gray)
    }

    attr = color_map.get(color, 7)
    ctypes.windll.kernel32.SetConsoleTextAttribute(handle, attr)
    print(text)
    ctypes.windll.kernel32.SetConsoleTextAttribute(handle, 7)  # Reset to white


class Logger:
    """Simple file logger for optimizer."""

    def __init__(self, base_dir: Path):
        self.log_path = base_dir / "optimizer.log"
        self._ensure_file()

    def _ensure_file(self) -> None:
        import datetime
        if not self.log_path.exists():
            self.log_path.write_text(
                f"# Zapret Optimizer Log\n# Started: {datetime.datetime.now().isoformat()}\n\n",
                encoding="utf-8"
            )

    def log(self, message: str, level: str = "INFO") -> None:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line)

    def info(self, message: str) -> None:
        self.log(message, "INFO")

    def warn(self, message: str) -> None:
        self.log(message, "WARN")

    def error(self, message: str) -> None:
        self.log(message, "ERROR")


def print_progress(current: int, total: int, width: int = 40) -> None:
    """Print a progress bar to console."""
    if total == 0:
        return
    percent = int((current / total) * 100)
    filled = int((current / total) * width)
    bar = "=" * filled + "-" * (width - filled)
    print(f"\r[{bar}] {percent}% ({current}/{total})", end="", flush=True)
    if current >= total:
        print()


def backup_zapret(zapret_dir: Path, backup_dir: Path | None = None) -> Path:
    """Create backup of zapret directory."""
    import shutil
    import datetime
    if backup_dir is None:
        backup_dir = zapret_dir.parent / "zapret_backups"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"zapret_backup_{timestamp}"
    backup_path = backup_dir / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)
    for bat_file in zapret_dir.glob("*.bat"):
        shutil.copy2(bat_file, backup_path / bat_file.name)
    for subdir in ["bin", "lists"]:
        src = zapret_dir / subdir
        if src.exists():
            dst = backup_path / subdir
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.exe", "*.dll"), dirs_exist_ok=True)
    return backup_path


def compare_configs(config1: Path, config2: Path) -> list[str]:
    """Compare two config files and return differences."""
    if not config1.exists() or not config2.exists():
        return ["[ERROR] One or both config files not found"]
    lines1 = config1.read_text(encoding="utf-8").splitlines()
    lines2 = config2.read_text(encoding="utf-8").splitlines()
    differences: list[str] = []
    max_lines = max(len(lines1), len(lines2))
    for i in range(max_lines):
        line1 = lines1[i] if i < len(lines1) else None
        line2 = lines2[i] if i < len(lines2) else None
        if line1 != line2:
            if line1 is None:
                differences.append(f"Line {i+1}: + {line2[:60]}...")
            elif line2 is None:
                differences.append(f"Line {i+1}: - {line1[:60]}...")
            else:
                differences.append(f"Line {i+1}: {line1[:40]}... -> {line2[:40]}...")
    return differences


def get_site_failures(results: list[dict]) -> dict[str, int]:
    """Analyze which sites fail most across all tests."""
    failures: dict[str, int] = {}
    for result in results:
        if "details" in result and "failed_sites" in result["details"]:
            for site in result["details"]["failed_sites"]:
                failures[site] = failures.get(site, 0) + 1
    return failures
