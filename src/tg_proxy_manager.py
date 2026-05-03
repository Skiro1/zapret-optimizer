"""Manager for tg-ws-proxy integration."""

import json
import os
import random
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from .utils import print_colored


class TgProxyManager:
    """Manages tg-ws-proxy lifecycle and configuration."""

    DEFAULT_PORT = 1443
    DEFAULT_HOST = "127.0.0.1"
    PID_FILE = "tg_proxy.pid"
    CONFIG_FILE = "tg_proxy_config.json"

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pid_file = base_dir / self.PID_FILE
        self.config_file = base_dir / self.CONFIG_FILE
        self.proxy_exe: Path | None = None

    def find_proxy_exe(self) -> Path | None:
        """Find tg-ws-proxy executable or source."""
        # Check common locations
        search_paths = [
            self.base_dir.parent / "TgWsProxy_windows.exe",
            self.base_dir.parent / "tg-ws-proxy" / "TgWsProxy_windows.exe",
            self.base_dir / "TgWsProxy_windows.exe",
        ]

        for path in search_paths:
            if path.exists():
                self.proxy_exe = path
                return path

        # Check for Python source version
        py_proxy = self.base_dir.parent / "tg-ws-proxy" / "windows.py"
        if py_proxy.exists():
            return py_proxy

        return None

    def get_config(self) -> dict[str, Any]:
        """Load proxy configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default_config()

    def _default_config(self) -> dict[str, Any]:
        """Generate default configuration."""
        # Generate random 32-char hex secret
        secret = "".join(random.choices("0123456789abcdef", k=32))
        return {
            "host": self.DEFAULT_HOST,
            "port": self.DEFAULT_PORT,
            "secret": secret,
            "dc_ip": [
                "2:149.154.167.220",
                "4:149.154.167.220"
            ],
            "verbose": False,
            "buf_kb": 256,
            "pool_size": 4,
            "cfproxy": True,
        }

    def save_config(self, config: dict[str, Any]) -> None:
        """Save proxy configuration."""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def is_running(self) -> bool:
        """Check if proxy process is running."""
        if not self.pid_file.exists():
            # Also check by process name
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq TgWsProxy_windows.exe"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return "TgWsProxy_windows.exe" in result.stdout
            except Exception:
                return False

        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return str(pid) in result.stdout
        except Exception:
            return False

    def is_port_available(self, port: int) -> bool:
        """Check if port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.DEFAULT_HOST, port))
                return True
        except OSError:
            return False

    def start(self, port: int | None = None, host: str | None = None) -> bool:
        """Start tg-ws-proxy."""
        if self.is_running():
            print_colored("[WARN] Proxy is already running", "yellow")
            return False

        exe = self.find_proxy_exe()
        if not exe:
            print_colored("[ERROR] TgWsProxy_windows.exe not found", "red")
            print_colored("        Run 'install-proxy' to check/setup", "gray")
            return False

        config = self.get_config()
        if port:
            config["port"] = port
        if host:
            config["host"] = host

        # Check port availability
        if not self.is_port_available(config["port"]):
            print_colored(f"[ERROR] Port {config['port']} is already in use", "red")
            return False

        # Build command
        if exe.suffix == ".exe":
            cmd = [str(exe)]
            # For .exe version, use config file approach or command line args
            cmd.extend(["--port", str(config["port"])])
            cmd.extend(["--host", config["host"]])
            cmd.extend(["--secret", config["secret"]])
            for dc_ip in config.get("dc_ip", []):
                cmd.extend(["--dc-ip", dc_ip])
        else:
            # Python source version
            cmd = ["python", str(exe)]
            cmd.extend(["--port", str(config["port"])])
            cmd.extend(["--host", config["host"]])
            cmd.extend(["--secret", config["secret"]])

        try:
            # Start process
            if exe.suffix == ".exe":
                # For .exe, use CREATE_NEW_PROCESS_GROUP to allow clean termination
                import ctypes
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                proc = subprocess.Popen(
                    cmd,
                    creationflags=creation_flags,
                    cwd=str(exe.parent) if exe.suffix == ".exe" else str(self.base_dir.parent / "tg-ws-proxy")
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.base_dir.parent / "tg-ws-proxy")
                )

            # Save PID
            self.pid_file.write_text(str(proc.pid))

            # Wait a bit and verify it started
            time.sleep(1)
            if self.is_running():
                print_colored(f"[OK] Proxy started on {config['host']}:{config['port']}", "green")
                self.save_config(config)
                return True
            else:
                print_colored("[ERROR] Proxy failed to start", "red")
                return False

        except Exception as e:
            print_colored(f"[ERROR] Failed to start proxy: {e}", "red")
            return False

    def stop(self) -> bool:
        """Stop tg-ws-proxy."""
        if not self.is_running():
            print_colored("[INFO] Proxy is not running", "gray")
            return True

        try:
            # Try to stop by PID first
            if self.pid_file.exists():
                pid = int(self.pid_file.read_text().strip())
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/F"],
                        capture_output=True,
                        timeout=10
                    )
                except Exception:
                    pass

            # Also try by process name
            try:
                subprocess.run(
                    ["taskkill", "/IM", "TgWsProxy_windows.exe", "/F"],
                    capture_output=True,
                    timeout=10
                )
            except Exception:
                pass

            # Clean up PID file
            if self.pid_file.exists():
                self.pid_file.unlink()

            print_colored("[OK] Proxy stopped", "green")
            return True

        except Exception as e:
            print_colored(f"[ERROR] Failed to stop proxy: {e}", "red")
            return False

    def get_status(self) -> dict[str, Any]:
        """Get proxy status."""
        config = self.get_config()
        running = self.is_running()

        status = {
            "running": running,
            "host": config.get("host", self.DEFAULT_HOST),
            "port": config.get("port", self.DEFAULT_PORT),
            "secret": config.get("secret", ""),
            "exe_found": self.find_proxy_exe() is not None,
        }

        return status

    def get_connect_link(self) -> str:
        """Generate tg://proxy connection link."""
        config = self.get_config()
        host = config.get("host", self.DEFAULT_HOST)
        port = config.get("port", self.DEFAULT_PORT)
        secret = config.get("secret", "")

        # If host is 127.0.0.1 or localhost, use dd prefix for local proxy
        # Otherwise it's a direct connection
        if host in ("127.0.0.1", "localhost"):
            return f"tg://proxy?server={host}&port={port}&secret=dd{secret}"
        else:
            return f"tg://proxy?server={host}&port={port}&secret=dd{secret}"

    def test_connection(self) -> bool:
        """Test if proxy is accepting connections."""
        config = self.get_config()
        host = config.get("host", self.DEFAULT_HOST)
        port = config.get("port", self.DEFAULT_PORT)

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((host, port))
                return True
        except Exception:
            return False

    def configure(self, port: int | None = None, secret: str | None = None,
                  dc_ip: list[str] | None = None, **kwargs) -> bool:
        """Update proxy configuration."""
        config = self.get_config()

        if port is not None:
            config["port"] = port
        if secret is not None:
            config["secret"] = secret
        if dc_ip is not None:
            config["dc_ip"] = dc_ip

        # Update any other kwargs
        for key, value in kwargs.items():
            if value is not None:
                config[key] = value

        self.save_config(config)
        print_colored("[OK] Configuration saved", "green")
        return True
