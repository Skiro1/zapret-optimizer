"""Manager for downloading and verifying dependencies."""

import hashlib
import json
import os
import ssl
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from .utils import print_colored, print_progress


class DependencyManager:
    """Manages downloading and verification of external dependencies."""

    # Known SHA256 hashes for verification
    DEPENDENCIES: dict[str, dict[str, Any]] = {
        "tg-ws-proxy": {
            "name": "TG WS Proxy (Telegram proxy)",
            "url": "https://github.com/Flowseal/tg-ws-proxy/releases/download/v1.6.5/TgWsProxy_windows.exe",
            "sha256": None,
            "filename": "TgWsProxy_windows.exe",
            "archive": False,
            "manual_download": False,
            "manual_url": "https://github.com/Flowseal/tg-ws-proxy/releases",
        },
        "zapret": {
            "name": "Zapret (bypass DPI)",
            "url": "https://github.com/Flowseal/zapret-discord-youtube/archive/refs/heads/main.zip",
            "sha256": None,
            "filename": "zapret",  # Extracted folder
            "archive": True,
            "archive_internal_path": "zapret-discord-youtube-main/",
            "extract_all": True,  # Extract entire archive
        },
    }

    def __init__(self, base_dir: Path | None = None):
        """Initialize with base directory for downloads."""
        self.base_dir = base_dir or Path.cwd()
        self.downloaded_count = 0
        self.skipped_count = 0
        self.failed_count = 0

    def _download_file(self, url: str, output_path: Path, show_progress: bool = True) -> bool:
        """Download file from URL with progress bar."""
        try:
            # Create SSL context that doesn't require cert verification for some sites
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/octet-stream,application/zip,*/*',
            })

            with urllib.request.urlopen(req, timeout=60, context=ssl_context) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192

                with open(output_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if show_progress and total_size > 0:
                            print_progress(downloaded, total_size, 30)

            if show_progress:
                print()  # New line after progress
            return True

        except Exception as e:
            if show_progress:
                print()
            print_colored(f"[ERROR] Download failed: {e}", "red")
            return False

    def _verify_sha256(self, filepath: Path, expected_hash: str | None) -> bool:
        """Verify file SHA256 hash."""
        if not expected_hash:
            return True  # No hash to verify

        try:
            sha256 = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
            actual_hash = sha256.hexdigest().lower()
            expected = expected_hash.lower()

            if actual_hash != expected:
                print_colored(f"[ERROR] SHA256 mismatch!", "red")
                print_colored(f"        Expected: {expected}", "gray")
                print_colored(f"        Actual:   {actual_hash}", "gray")
                return False
            return True
        except Exception as e:
            print_colored(f"[ERROR] Failed to verify hash: {e}", "red")
            return False

    def _extract_from_zip(self, zip_path: Path, internal_path: str, output_path: Path) -> bool:
        """Extract file from zip archive."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                if internal_path not in zf.namelist():
                    # Try case-insensitive match
                    found = False
                    for name in zf.namelist():
                        if name.lower() == internal_path.lower():
                            internal_path = name
                            found = True
                            break
                    if not found:
                        print_colored(f"[ERROR] File not found in archive: {internal_path}", "red")
                        print_colored(f"        Available files: {', '.join(zf.namelist()[:10])}", "gray")
                        return False

                # Extract to temp location first
                temp_extract = zip_path.parent / f"_temp_{internal_path.replace('/', '_')}"
                with zf.open(internal_path) as src, open(temp_extract, 'wb') as dst:
                    dst.write(src.read())

                # Move to final location
                temp_extract.replace(output_path)
                return True

        except Exception as e:
            print_colored(f"[ERROR] Failed to extract: {e}", "red")
            return False

    def _extract_all_from_zip(self, zip_path: Path, internal_prefix: str, output_dir: Path) -> bool:
        """Extract all files from zip archive starting with prefix."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                members = [name for name in zf.namelist() if name.startswith(internal_prefix)]
                if not members:
                    print_colored(f"[ERROR] Prefix not found in archive: {internal_prefix}", "red")
                    return False

                output_dir.mkdir(parents=True, exist_ok=True)

                for member in members:
                    # Skip directories
                    if member.endswith('/'):
                        continue

                    # Calculate relative path
                    rel_path = member[len(internal_prefix):].lstrip('/')
                    if not rel_path:
                        continue

                    output_file = output_dir / rel_path
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                    with zf.open(member) as src, open(output_file, 'wb') as dst:
                        dst.write(src.read())

                return True

        except Exception as e:
            print_colored(f"[ERROR] Failed to extract: {e}", "red")
            return False

    def download_dependency(self, name: str, force: bool = False) -> bool:
        """Download and verify a single dependency."""
        if name not in self.DEPENDENCIES:
            print_colored(f"[ERROR] Unknown dependency: {name}", "red")
            return False

        dep = self.DEPENDENCIES[name]

        # Check if manual download required
        if dep.get("manual_download"):
            print_colored(f"[INFO] {dep['name']} requires manual download", "yellow")
            print_colored(f"       Please download from: {dep.get('manual_url', 'See documentation')}", "cyan")
            if dep.get("filename"):
                print_colored(f"       Place {dep['filename']} in: {self.base_dir}", "gray")
            return False

        # Check if URL available
        if not dep.get("url"):
            print_colored(f"[ERROR] No download URL for {name}", "red")
            return False

        output_path = self.base_dir / dep["filename"]

        # Check if already exists
        if output_path.exists() and not force:
            print_colored(f"[SKIP] {dep['name']} already exists", "gray")
            print_colored(f"       Use --force to re-download", "gray")
            self.skipped_count += 1
            return True

        print_colored(f"[DOWNLOAD] {dep['name']}", "cyan")
        print_colored(f"           From: {dep['url']}", "gray")

        # Download to temp file
        temp_path = self.base_dir / f"_{name}_download.tmp"

        if not self._download_file(dep["url"], temp_path):
            if temp_path.exists():
                temp_path.unlink()
            self.failed_count += 1
            return False

        # Verify archive hash if applicable
        if dep.get("archive") and dep.get("sha256"):
            print_colored(f"[VERIFY] Checking archive SHA256...", "gray")
            if not self._verify_sha256(temp_path, dep["sha256"]):
                temp_path.unlink()
                self.failed_count += 1
                return False

        # Handle archive extraction
        if dep.get("archive"):
            if dep.get("extract_all"):
                # Extract entire folder (for zapret)
                print_colored(f"[EXTRACT] {dep['filename']} folder from archive...", "gray")
                if not self._extract_all_from_zip(temp_path, dep["archive_internal_path"], output_path):
                    temp_path.unlink()
                    self.failed_count += 1
                    return False
            else:
                # Extract single file
                print_colored(f"[EXTRACT] {dep['filename']} from archive...", "gray")
                if not self._extract_from_zip(temp_path, dep["archive_internal_path"], output_path):
                    temp_path.unlink()
                    self.failed_count += 1
                    return False
            # Clean up archive
            temp_path.unlink()
        else:
            # Just rename temp file
            if output_path.exists():
                output_path.unlink()
            temp_path.replace(output_path)

        # For non-archive files, verify hash of the final file
        if not dep.get("archive") and dep.get("sha256"):
            print_colored(f"[VERIFY] Checking SHA256...", "gray")
            if not self._verify_sha256(output_path, dep["sha256"]):
                output_path.unlink()
                self.failed_count += 1
                return False

        print_colored(f"[OK] {dep['name']} downloaded successfully", "green")
        print_colored(f"     Location: {output_path}", "gray")
        self.downloaded_count += 1
        return True

    def download_all(self, force: bool = False, categories: list[str] | None = None) -> bool:
        """Download all or selected dependencies."""
        print_colored("=== Download Dependencies ===", "cyan")
        print()

        # Determine which to download
        if categories:
            to_download = []
            if "proxy" in categories:
                to_download.append("tg-ws-proxy")
            if "zapret" in categories:
                to_download.append("zapret")
        else:
            to_download = list(self.DEPENDENCIES.keys())

        self.downloaded_count = 0
        self.skipped_count = 0
        self.failed_count = 0

        for name in to_download:
            print()
            self.download_dependency(name, force)

        # Summary
        print()
        print_colored("=== Summary ===", "cyan")
        print_colored(f"Downloaded: {self.downloaded_count}", "green" if self.downloaded_count > 0 else "gray")
        print_colored(f"Skipped (existing): {self.skipped_count}", "yellow" if self.skipped_count > 0 else "gray")
        print_colored(f"Failed: {self.failed_count}", "red" if self.failed_count > 0 else "gray")

        if self.failed_count > 0:
            print()
            print_colored("[NOTE] Some dependencies failed to download", "yellow")

        return self.failed_count == 0

    def check_all(self) -> dict[str, bool]:
        """Check which dependencies are present."""
        results = {}
        for name, dep in self.DEPENDENCIES.items():
            if dep.get("extract_all"):
                # Check folder existence (for zapret)
                path = self.base_dir / dep["filename"]
                results[name] = path.exists() and path.is_dir()
            elif dep.get("filename"):
                path = self.base_dir / dep["filename"]
                results[name] = path.exists()
            else:
                results[name] = False
        return results

    def print_status(self):
        """Print current dependency status."""
        print_colored("=== Dependency Status ===", "cyan")
        print()

        status = self.check_all()

        for name, dep in self.DEPENDENCIES.items():
            present = status.get(name, False)
            symbol = "[OK]" if present else "[MISSING]"
            color = "green" if present else "red"
            print_colored(f"{symbol} {dep['name']}", color)
            if dep.get("extract_all"):
                path = self.base_dir / dep["filename"]
                print_colored(f"     {path}/", "gray" if present else "dark_gray")
            elif dep.get("filename"):
                path = self.base_dir / dep["filename"]
                print_colored(f"     {path}", "gray" if present else "dark_gray")

        print()

        all_present = all(status.values())
        if all_present:
            print_colored("[OK] All dependencies ready!", "green")
        else:
            print_colored("[INFO] Run 'download-deps' to get missing dependencies", "yellow")

        return all_present
