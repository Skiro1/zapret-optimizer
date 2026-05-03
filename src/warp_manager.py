"""Manager for Cloudflare WARP/AmneziaVPN config generation."""

import base64
import json
import random
import secrets
import socket
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import print_colored


class WARPManager:
    """Generates Cloudflare WARP configuration for AmneziaVPN."""

    CONFIG_FILE = "warp.conf"
    STATE_FILE = "warp_state.json"

    # Cloudflare WARP endpoints
    # WARP endpoints - port 500 is alternative that works in some blocked regions
    WARP_ENDPOINTS = [
        "162.159.192.1:500",
        "162.159.193.1:500",
        "162.159.195.1:500",
        "engage.cloudflareclient.com:500",
    ]

    # WARP DNS servers
    WARP_DNS = ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]

    # Cloudflare API endpoints - use v0i1909051800 (tested working)
    API_BASES = ["https://api.cloudflareclient.com/v0i1909051800"]

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.config_file = base_dir / self.CONFIG_FILE
        self.state_file = base_dir / self.STATE_FILE

    def generate_keypair(self) -> tuple[str, str]:
        """Generate X25519 keypair for AmneziaVPN."""
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            from cryptography.hazmat.primitives import serialization

            private_key = X25519PrivateKey.generate()
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key = private_key.public_key()
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            private_b64 = base64.b64encode(private_bytes).decode('ascii')
            public_b64 = base64.b64encode(public_bytes).decode('ascii')
            return private_b64, public_b64
        except ImportError:
            pass

        # Fallback: use wireguard-go.exe if available nearby (legacy)
        try:
            import subprocess
            wg_candidates = [
                self.base_dir / "wireguard-go.exe",
                self.base_dir.parent / "wireguard-go.exe",
            ]
            wg = next((p for p in wg_candidates if p.exists()), None)
            if wg:
                result = subprocess.run(
                    [str(wg), "genkey"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    private_key = result.stdout.strip()
                    proc = subprocess.run(
                        [str(wg), "pubkey"],
                        input=private_key,
                        capture_output=True, text=True, timeout=5
                    )
                    if proc.returncode == 0:
                        return private_key, proc.stdout.strip()
        except Exception:
            pass

        # Last resort: random bytes (not a valid X25519 key, placeholder)
        private_bytes = secrets.token_bytes(32)
        private_b64 = base64.b64encode(private_bytes).decode('ascii')
        return private_b64, ""

    def _generate_reserved(self, install_id: str) -> str:
        """Generate WARP reserved bytes (client_id) from install_id."""
        try:
            # Take first 3 bytes of install_id hex, pad to 4 bytes with null
            hex_bytes = bytes.fromhex(install_id.replace('-', ''))[:3]
            padded = hex_bytes + b'\x00'
            return base64.b64encode(padded).decode('ascii')
        except Exception:
            return "AAAA"

    def register_via_api(self) -> dict[str, Any] | None:
        """Register device with Cloudflare WARP API."""
        private_key, public_key = self.generate_keypair()

        if not public_key:
            print_colored("[WARN] Could not generate valid keypair", "yellow")
            return None

        # Empty install_id and fcm_token as per working generators
        install_id = ""

        payload = {
            "install_id": install_id,
            "tos": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+00:00",
            "key": public_key,
            "fcm_token": "",
            "type": "ios",
            "locale": "en_US"
        }

        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/3.12.1"
        }

        for api_base in random.sample(self.API_BASES, len(self.API_BASES)):
            try:
                url = f"{api_base}/reg"
                data = json.dumps(payload).encode('utf-8')

                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    # API returns wrapped in 'result' key
                    result_data = result.get('result', result)

                    # PATCH request to enable WARP (critical step!)
                    if 'id' in result_data and 'token' in result_data:
                        device_id = result_data['id']
                        token = result_data['token']
                        patch_url = f"{api_base}/reg/{device_id}"
                        patch_data = json.dumps({"warp_enabled": True}).encode('utf-8')
                        patch_headers = {
                            **headers,
                            "Authorization": f"Bearer {token}"
                        }
                        patch_req = urllib.request.Request(patch_url, data=patch_data, headers=patch_headers, method="PATCH")
                        try:
                            with urllib.request.urlopen(patch_req, timeout=15) as patch_response:
                                patch_result = json.loads(patch_response.read().decode('utf-8'))
                                # PATCH response also wrapped in 'result'
                                result_data = patch_result.get('result', patch_result)
                        except Exception as e:
                            print_colored(f"[WARN] PATCH request failed: {e}", "yellow")

                    if 'config' in result_data:
                        config = result_data['config']
                        return {
                            "private_key": private_key,
                            "public_key": public_key,
                            "install_id": result_data.get('id', ''),
                            "device_token": result_data.get('token', ''),
                            "peer_endpoint": config.get('peers', [{}])[0].get('endpoint', {}).get('host', ''),  # type: ignore
                            "peer_public_key": config.get('peers', [{}])[0].get('public_key', ''),  # type: ignore
                            "reserved": result_data.get('client_id') or self._generate_reserved(result_data.get('id', '')),
                            "addresses": {
                                "v4": config.get('interface', {}).get('addresses', {}).get('v4', ''),
                                "v6": config.get('interface', {}).get('addresses', {}).get('v6', '')
                            },
                            "api_base": api_base
                        }
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(1)
                    continue
            except Exception:
                continue

        return None

    def generate_fallback_config(self) -> dict[str, Any]:
        """Generate WARP config using known endpoints (fallback mode)."""
        private_key, public_key = self.generate_keypair()
        warp_public_key = "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="

        return {
            "private_key": private_key,
            "public_key": public_key,
            "peer_endpoint": random.choice(self.WARP_ENDPOINTS),
            "peer_public_key": warp_public_key,
            "reserved": "AAAA",
            "addresses": {"v4": "", "v6": ""},
            "method": "fallback"
        }

    def generate_config(self, method: str = "api") -> bool:
        """Generate WARP AmneziaVPN configuration file."""
        print_colored(f"[INFO] Generating WARP config (method: {method})...", "gray")

        state: dict[str, Any] = {}

        if method == "api":
            result = self.register_via_api()
            if result:
                state = result
                state["method"] = "api"
                print_colored("[OK] Registered with Cloudflare API", "green")
            else:
                print_colored("[WARN] API registration failed, using fallback", "yellow")
                state = self.generate_fallback_config()
        else:
            state = self.generate_fallback_config()

        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

        # Use endpoint from API if available, otherwise fallback
        endpoint = state.get("peer_endpoint", "")
        if not endpoint or endpoint == "":
            endpoint = random.choice(self.WARP_ENDPOINTS)

        # Resolve engage.cloudflareclient.com to IP for better compatibility
        if "engage.cloudflareclient.com" in endpoint:
            try:
                resolved = socket.gethostbyname("engage.cloudflareclient.com")
                endpoint = endpoint.replace("engage.cloudflareclient.com", resolved)
            except Exception:
                endpoint = "162.159.192.1:2408"

        # Get addresses from API response
        v4_addr = state.get("addresses", {}).get("v4", "172.16.0.2")
        v6_addr = state.get("addresses", {}).get("v6", "")

        # Build address line
        addresses = f"{v4_addr}/32"
        if v6_addr:
            addresses += f", {v6_addr}/128"

        # Generate clean WireGuard config for AmneziaVPN
        # Note: Enable "WireGuard obfuscation" in AmneziaVPN settings after import
        config_lines = [
            "[Interface]",
            f"PrivateKey = {state['private_key']}",
            f"Address = {addresses}",
            f"DNS = {', '.join(self.WARP_DNS[:2])}",
            "MTU = 1280",
            "",
            "[Peer]",
            f"PublicKey = {state['peer_public_key']}",
            "AllowedIPs = 0.0.0.0/0, ::/0",
            f"Endpoint = {endpoint}",
            "PersistentKeepalive = 25",
        ]

        self.config_file.write_text("\n".join(config_lines), encoding="utf-8")

        print_colored(f"[OK] WARP config saved to {self.config_file}", "green")
        print_colored(f"     Endpoint: {endpoint}", "gray")
        return True

    def get_status(self) -> dict[str, Any]:
        """Get WARP config status (file existence only)."""
        config_exists = self.config_file.exists()
        state_exists = self.state_file.exists()

        status: dict[str, Any] = {
            "config_exists": config_exists,
            "state_exists": state_exists,
        }

        if state_exists:
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                status["method"] = state.get("method", "unknown")
                status["endpoint"] = state.get("peer_endpoint", "")
            except Exception:
                pass

        return status
