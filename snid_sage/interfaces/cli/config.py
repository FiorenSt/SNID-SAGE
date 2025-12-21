"""
SNID Config Command
==================

Unified configuration management CLI backed by the shared ConfigurationManager
used by both GUI and CLI. Stores config at a single platform-appropriate path
and uses a common schema (e.g., paths.templates_dir, analysis.lapmin).
"""

import argparse
import sys
import json
from pathlib import Path
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
    
    # Set config command
    set_parser = subparsers.add_parser(
        'set', 
        help='Set configuration value'
    )
    set_parser.add_argument(
        'key', 
        help="Configuration key (e.g., paths.templates_dir)"
    )
    set_parser.add_argument(
        'value', 
        help='Configuration value'
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
    
    # Reset config command
    reset_parser = subparsers.add_parser(
        'reset', 
        help='Reset configuration to defaults'
    )
    reset_parser.add_argument(
        '--confirm', 
        action='store_true',
        help='Confirm reset without prompting'
    )
    
    # Init config command
    init_parser = subparsers.add_parser(
        'init', 
        help='Initialize configuration file'
    )
    init_parser.add_argument(
        '--force', 
        action='store_true', 
        help='Overwrite existing configuration'
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


def _set_nested_value(config: Dict[str, Any], key: str, value: str) -> None:
    parts = key.split('.')
    cur = config
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    leaf = parts[-1]
    try:
        cur[leaf] = json.loads(value)
    except json.JSONDecodeError:
        cur[leaf] = value


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

        elif args.config_command == 'set':
            config = cm.load_config()
            try:
                _set_nested_value(config, args.key, args.value)
                # Validate and save via manager
                cm.save_config(config)
                print(f"Set {args.key} = {args.value}")
                return 0
            except Exception as e:
                print(f"Error setting configuration: {e}", file=sys.stderr)
                return 1

        elif args.config_command == 'reset':
            import os
            is_noninteractive = (
                not sys.stdin.isatty() or os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS') or os.environ.get('RUNNER_OS') or os.environ.get('SNID_NONINTERACTIVE')
            )
            if not args.confirm:
                if is_noninteractive:
                    print("Warning: Running in non-interactive environment. Use --confirm to reset configuration.")
                    return 1
                response = input("This will reset all configuration to defaults. Continue? (y/N): ")
                if response.lower() != 'y':
                    print("Reset cancelled.")
                    return 0
            config = cm.reset_to_defaults()
            cm.save_config(config)
            print("Configuration reset to defaults.")
            return 0

        elif args.config_command == 'init':
            cfg_path = cm.default_config_file
            if cfg_path.exists() and not args.force:
                print(f"Configuration file already exists at {cfg_path}")
                print("Use --force to overwrite.")
                return 1
            config = cm.get_default_config()
            cm.save_config(config)
            print(f"Configuration initialized at {cfg_path}")
            return 0

        else:
            print("Error: No config subcommand specified.", file=sys.stderr)
            print("Use 'snid config --help' for available commands.", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error in config command: {e}", file=sys.stderr)
        return 1