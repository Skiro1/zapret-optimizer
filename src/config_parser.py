"""Parser and generator for zapret .bat config files."""

import re
import shutil
from pathlib import Path
from typing import Any


class ZapretRule:
    """Represents a single filter rule (--filter-tcp or --filter-udp block)."""

    def __init__(self, filter_type: str, filter_value: str, params: dict[str, Any]):
        self.filter_type = filter_type  # "tcp" or "udp"
        self.filter_value = filter_value  # e.g., "443" or "80,443"
        self.params = params  # Dict of param_name -> value or list of values

    def to_args_list(self) -> list[str]:
        """Convert rule back to list of argument strings."""
        args = [f"--filter-{self.filter_type}={self.filter_value}"]

        for key, val in self.params.items():
            if isinstance(val, list):
                for v in val:
                    args.append(f"--{key}={v}")
            else:
                args.append(f"--{key}={val}")

        return args


class ZapretConfig:
    """Represents a complete zapret configuration."""

    # Default header template for generated configs
    HEADER_TEMPLATE = '''@echo off
chcp 65001 > nul
:: 65001 - UTF-8

cd /d "%~dp0"
call service.bat status_zapret
call service.bat check_updates
call service.bat load_game_filter
call service.bat load_user_lists
echo:

set "BIN=%~dp0bin\\"
set "LISTS=%~dp0lists\\"
cd /d %BIN%
'''

    # WinDivert filter ports (standard for most configs)
    WF_TCP_PORTS = "80,443,2053,2083,2087,2096,8443,%GameFilterTCP%"
    WF_UDP_PORTS = "443,19294-19344,50000-50100,%GameFilterUDP%"

    def __init__(self, name: str, rules: list[ZapretRule], source_path: Path | None = None):
        self.name = name
        self.rules = rules
        self.source_path = source_path

    @classmethod
    def from_bat_file(cls, bat_path: Path) -> "ZapretConfig":
        """Parse a .bat file into a ZapretConfig."""
        content = bat_path.read_text(encoding="utf-8", errors="ignore")

        # Find the winws.exe invocation
        winws_match = re.search(
            r'start\s+"[^"]*"\s+/min\s+"%BIN%winws\.exe"\s+(.*?)(?:\n\n|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if not winws_match:
            raise ValueError(f"Could not find winws.exe invocation in {bat_path}")

        args_line = winws_match.group(1)
        # Remove line continuation and normalize
        args_line = args_line.replace("^\n", " ").replace("\n", " ")

        # Split into rules by --new
        rule_blocks = re.split(r'\s+--new\s+', args_line)

        # Parse global WF args from first block
        wf_tcp = cls.WF_TCP_PORTS
        wf_udp = cls.WF_UDP_PORTS
        wf_match = re.search(r'--wf-tcp=([^\s]+)', rule_blocks[0])
        if wf_match:
            wf_tcp = wf_match.group(1)
        wf_match = re.search(r'--wf-udp=([^\s]+)', rule_blocks[0])
        if wf_match:
            wf_udp = wf_match.group(1)

        rules = []
        for block in rule_blocks:
            block = block.strip()
            if not block:
                continue

            # Skip WF args block (no filter-*)
            if "--filter-" not in block:
                continue

            # Parse filter type and value
            filter_match = re.search(r'--filter-(tcp|udp)=([^\s]+)', block)
            if not filter_match:
                continue

            filter_type = filter_match.group(1)
            filter_value = filter_match.group(2)

            # Parse all other params
            params: dict[str, Any] = {}
            param_pattern = r'--([\w-]+)="([^"]*)"|--([\w-]+)=([^\s]+)'

            for match in re.finditer(param_pattern, block):
                if match.group(1):  # Quoted value
                    key = match.group(1)
                    val = match.group(2)
                else:  # Unquoted value
                    key = match.group(3)
                    val = match.group(4)

                # Handle duplicate params (like --dpi-desync-fake-tls appearing twice)
                if key in params:
                    if not isinstance(params[key], list):
                        params[key] = [params[key]]
                    params[key].append(val)
                else:
                    params[key] = val

            rules.append(ZapretRule(filter_type, filter_value, params))

        return cls(bat_path.stem, rules, bat_path)

    def to_bat_content(self) -> str:
        """Generate .bat file content from this config."""
        lines = [self.HEADER_TEMPLATE]

        # Build winws args
        args_parts = [
            f'--wf-tcp={self.WF_TCP_PORTS}',
            f'--wf-udp={self.WF_UDP_PORTS}'
        ]

        for i, rule in enumerate(self.rules):
            if i > 0:
                args_parts.append("--new")
            args_parts.extend(rule.to_args_list())

        # Format with proper line continuation
        max_line_len = 120
        current_line = f'start "zapret: {self.name}" /min "%BIN%winws.exe"'

        for part in args_parts:
            if len(current_line) + len(part) + 1 > max_line_len:
                lines.append(current_line + " ^")
                current_line = " " * 4 + part
            else:
                current_line += " " + part

        lines.append(current_line)
        return "\n".join(lines)

    def write_bat(self, output_path: Path) -> None:
        """Write this config to a .bat file."""
        output_path.write_text(self.to_bat_content(), encoding="utf-8")

    def copy_original(self, output_dir: Path, new_name: str | None = None) -> Path:
        """Copy the original .bat file to output dir."""
        if not self.source_path:
            raise ValueError("No source path to copy from")

        dest_name = new_name or self.source_path.name
        if not dest_name.endswith(".bat"):
            dest_name += ".bat"

        dest_path = output_dir / dest_name
        shutil.copy2(self.source_path, dest_path)
        return dest_path


def find_all_configs(zapret_dir: Path) -> list[Path]:
    """Find all .bat config files in zapret directory (excluding service*)."""
    bat_files = []

    for bat_path in zapret_dir.glob("*.bat"):
        # Exclude service.bat and service_install.bat, etc.
        if bat_path.name.lower().startswith("service"):
            continue
        bat_files.append(bat_path)

    # Sort naturally (general, general (ALT), general (ALT2), etc.)
    def natural_sort_key(p: Path) -> str:
        name = p.stem
        # Extract number if present
        match = re.search(r'\d+', name)
        if match:
            num = int(match.group())
            prefix = name[:match.start()]
            return f"{prefix}{num:08d}"
        return name

    return sorted(bat_files, key=natural_sort_key)


def parse_all_configs(zapret_dir: Path) -> list[ZapretConfig]:
    """Parse all available configs from zapret directory."""
    configs = []

    for bat_path in find_all_configs(zapret_dir):
        try:
            config = ZapretConfig.from_bat_file(bat_path)
            configs.append(config)
        except Exception as e:
            print(f"[WARN] Failed to parse {bat_path.name}: {e}")

    return configs
