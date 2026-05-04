#!/usr/bin/env python3
"""Zapret Config Optimizer - CLI tool to find best zapret configurations."""

import argparse
import sys
from pathlib import Path

# Ensure src is in path when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))

from src.cli import OptimizerCLI


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="zapret-optimizer",
        description="Optimize zapret configurations for best site unblocking performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  init           Check environment (admin rights, zapret, curl) and initialize
  optimize       Run 3-cycle optimization (test → mutate → combine)
  run-best       Start the best configuration (requires completed optimize)
  status         Show current optimization status and results
  list           List all tested configurations sorted by score
  compare        Compare two configurations (show differences)

  install-proxy  Check/install tg-ws-proxy (Telegram proxy)
  start-proxy    Start tg-ws-proxy
  stop-proxy     Stop tg-ws-proxy
  status-proxy   Show tg-ws-proxy status
  configure-proxy  Configure tg-ws-proxy settings
  test-telegram  Test Telegram connection through proxy

  warp-generate  Generate WARP AmneziaVPN config file

  install-service   Install auto-start service for best config
  uninstall-service Remove auto-start service
  service-status    Check auto-start service status

  deps-status    Check which dependencies are installed
  download-deps  Download missing dependencies

Examples:
  %(prog)s init
  %(prog)s optimize
  %(prog)s status
  %(prog)s run-best
  %(prog)s compare cycle-1/general.bat cycle-2/mutant_general_1.bat
  %(prog)s install-proxy
  %(prog)s start-proxy
  %(prog)s start-proxy --port 8080
  %(prog)s status-proxy
  %(prog)s configure-proxy --port 8080
  %(prog)s test-telegram
  %(prog)s warp-generate --method api
  %(prog)s warp-generate --method fallback
  %(prog)s install-service
  %(prog)s uninstall-service
  %(prog)s service-status
  %(prog)s deps-status

  # Custom sites file
  %(prog)s optimize --sites-file my_sites.txt
  %(prog)s download-deps
  %(prog)s download-deps --force
        """.strip()
    )

    parser.add_argument(
        "command",
        choices=["init", "optimize", "run-best", "status", "list", "compare",
                 "install-proxy", "start-proxy", "stop-proxy", "status-proxy",
                 "configure-proxy", "test-telegram",
                 "warp-generate",
                 "install-service", "uninstall-service", "service-status",
                 "deps-status", "download-deps"],
        help="Command to execute"
    )

    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Base directory for optimizer files (default: current directory)"
    )

    # Proxy options
    proxy_group = parser.add_argument_group("tg-ws-proxy options")
    proxy_group.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for tg-ws-proxy (default: 1443)"
    )
    proxy_group.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host for tg-ws-proxy (default: 127.0.0.1)"
    )
    proxy_group.add_argument(
        "--secret",
        type=str,
        default=None,
        help="Custom secret for tg-ws-proxy"
    )

    # WARP options
    warp_group = parser.add_argument_group("WARP options")
    warp_group.add_argument(
        "--method",
        type=str,
        default="api",
        choices=["api", "fallback"],
        help="WARP config generation method (api or fallback)"
    )

    # Download dependencies options
    deps_group = parser.add_argument_group("download-deps options")
    deps_group.add_argument(
        "--proxy-only",
        action="store_true",
        help="Download only tg-ws-proxy"
    )
    deps_group.add_argument(
        "--zapret-only",
        action="store_true",
        help="Download only zapret"
    )

    # Optimization options
    opt_group = parser.add_argument_group("optimize options")
    opt_group.add_argument(
        "--sites-file",
        type=str,
        default=None,
        help="Custom sites file for testing (format: Key = \"URL\", one per line)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download / regenerate WARP config with new keys"
    )

    parser.add_argument(
        "config1",
        nargs="?",
        default=None,
        help="First config for compare command"
    )

    parser.add_argument(
        "config2",
        nargs="?",
        default=None,
        help="Second config for compare command"
    )

    args = parser.parse_args()

    # Create CLI instance
    sites_file = Path(args.sites_file) if args.sites_file else None
    cli = OptimizerCLI(base_dir=args.base_dir or Path.cwd(), sites_file=sites_file)

    # Execute command
    commands = {
        "init": cli.cmd_init,
        "optimize": cli.cmd_optimize,
        "run-best": cli.cmd_run_best,
        "status": cli.cmd_status,
        "list": cli.cmd_list,
        "compare": lambda: cli.cmd_compare(args.config1, args.config2) if args.config1 and args.config2 else (print("[ERROR] compare requires two config paths"), 1)[1],
        "install-proxy": cli.cmd_install_proxy,
        "start-proxy": lambda: cli.cmd_start_proxy(args.port, args.host),
        "stop-proxy": cli.cmd_stop_proxy,
        "status-proxy": cli.cmd_status_proxy,
        "configure-proxy": lambda: cli.cmd_configure_proxy(args.port, args.secret, None),
        "test-telegram": cli.cmd_test_telegram,
        "warp-generate": lambda: cli.cmd_warp_generate(args.method, args.force),
        "install-service": cli.cmd_install_service,
        "uninstall-service": cli.cmd_uninstall_service,
        "service-status": cli.cmd_service_status,
        "deps-status": cli.cmd_deps_status,
        "download-deps": lambda: cli.cmd_download_deps(
            categories=(
                ["proxy"] if args.proxy_only else
                ["zapret"] if args.zapret_only else
                None
            ),
            force=args.force
        ),
    }

    try:
        exit_code = commands[args.command]()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
