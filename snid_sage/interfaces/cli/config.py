"""
SNID Config Command
==================

Read-oriented configuration CLI for inspecting the effective/default SNID SAGE
configuration values used by the current build.
"""

import argparse
import sys
import json
from typing import Dict, Any

from snid_sage.shared.utils.config.configuration_manager import ConfigurationManager


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments for the config command."""
    subparsers = parser.add_subparsers(
        dest="config_command", 
        help="Configuration commands",
        metavar="SUBCOMMAND"
    )
    
    # Show config command
    show_parser = subparsers.add_parser(
        'show', 
        help='Show current configuration'
    )
    show_parser.add_argument(
        '--format', 
        choices=['json', 'yaml', 'table'], 
        default='table',
        help='Output format'
    )
    
    # Get config command
    get_parser = subparsers.add_parser(
        'get', 
        help='Get configuration value'
    )
    get_parser.add_argument(
        'key', 
        help='Configuration key'
    )
    
def _format_config_table(config: Dict[str, Any], prefix: str = '') -> str:
    """Format configuration as a table (paths.*, analysis.*, etc.)."""
    lines = []
    for key, value in config.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            lines.extend(_format_config_table(value, full_key).split('\n'))
        else:
            lines.append(f"{full_key:<30} = {value}")
    return '\n'.join(lines)


def _get_nested_value(config: Dict[str, Any], key: str):
    parts = key.split('.')
    cur = config
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            raise KeyError(f"Configuration key '{key}' not found")
    return cur


def main(args: argparse.Namespace) -> int:
    """Main function for the config command (unified)."""
    try:
        cm = ConfigurationManager()
        if args.config_command == 'show':
            config = cm.load_config()
            if args.format == 'json':
                print(json.dumps(config, indent=2))
            elif args.format == 'yaml':
                try:
                    import yaml
                    print(yaml.dump(config, default_flow_style=False))
                except ImportError:
                    print("Error: PyYAML not installed. Use 'json' or 'table' format.", file=sys.stderr)
                    return 1
            else:
                print("SNID Configuration:")
                print("=" * 50)
                print(_format_config_table(config))
            return 0

        elif args.config_command == 'get':
            config = cm.load_config()
            try:
                print(_get_nested_value(config, args.key))
                return 0
            except KeyError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

        else:
            print("Error: No config subcommand specified.", file=sys.stderr)
            print("Use 'snid config --help' for available commands.", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error in config command: {e}", file=sys.stderr)
        return 1