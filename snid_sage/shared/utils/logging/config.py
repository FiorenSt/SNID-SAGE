"""
SNID SAGE Logging Configuration
==============================

Handles command-line argument parsing and environment-based
logging configuration for the SNID SAGE application.

Features:
- Standard command-line argument integration (--verbose, --debug, --quiet)
- Environment variable support (SNID_DEBUG, SNID_VERBOSE)
- Auto-detection of GUI vs CLI mode
- Integration with centralized logging system

Usage:
    # In a CLI script:
    import argparse
    from snid_sage.shared.utils.logging import add_logging_arguments, configure_from_args
    
    parser = argparse.ArgumentParser()
    add_logging_arguments(parser)
    args = parser.parse_args()
    configure_from_args(args, gui_mode=False)
    
    # In a GUI application:
    from snid_sage.shared.utils.logging import configure_from_environment
    configure_from_environment(gui_mode=True)
"""

import argparse
import os
from typing import Optional, Dict, Any
from pathlib import Path

from .snid_logger import SNIDLogger, VerbosityLevel


def add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add standard logging arguments to an argument parser
    
    Args:
        parser: ArgumentParser instance to add arguments to
    """
    log_group = parser.add_argument_group('logging options')
    
    # Verbosity control - mutually exclusive
    verbosity_group = log_group.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (detailed operation info)'
    )
    verbosity_group.add_argument(
        '--debug', '-d',
        action='store_true', 
        help='Enable debug output (full debugging information)'
    )
    # Convenience alias: -vv behaves like --debug
    verbosity_group.add_argument(
        '-vv',
        dest='debug',
        action='store_true',
        help='Very verbose (alias for --debug)'
    )
    verbosity_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet mode (errors and warnings only)'
    )
    verbosity_group.add_argument(
        '--silent',
        action='store_true',
        help='Silent mode (critical errors only)'
    )
    
    # Log file options
    log_group.add_argument(
        '--log-file',
        type=str,
        help='Write log output to specified file'
    )
    log_group.add_argument(
        '--log-dir',
        type=str,
        help='Directory for log files (auto-generates filename)'
    )


def configure_from_args(args: argparse.Namespace, 
                       gui_mode: bool = False,
                       default_verbosity: VerbosityLevel = VerbosityLevel.NORMAL) -> None:
    """
    Configure logging from parsed command line arguments
    
    Args:
        args: Parsed arguments from argparse
        gui_mode: Whether running in GUI mode
        default_verbosity: Default verbosity level if none specified
    """
    
    # Determine verbosity level from arguments
    if hasattr(args, 'debug') and args.debug:
        verbosity = VerbosityLevel.DEBUG
    elif hasattr(args, 'verbose') and args.verbose:
        verbosity = VerbosityLevel.VERBOSE
    elif hasattr(args, 'quiet') and args.quiet:
        verbosity = VerbosityLevel.QUIET
    elif hasattr(args, 'silent') and args.silent:
        verbosity = VerbosityLevel.SILENT
    else:
        # Check environment variables as fallback
        verbosity = _get_verbosity_from_environment(default_verbosity)
    
    # Get log file settings
    log_file = getattr(args, 'log_file', None)
    log_dir = getattr(args, 'log_dir', None)
    
    # Configure the logging system
    SNIDLogger.configure(
        verbosity=verbosity,
        gui_mode=gui_mode,
        log_file=log_file,
        log_dir=log_dir
    )


def configure_from_environment(gui_mode: bool = False,
                              default_verbosity: VerbosityLevel = VerbosityLevel.NORMAL,
                              log_dir: Optional[str] = None) -> None:
    """
    Configure logging from environment variables
    
    Args:
        gui_mode: Whether running in GUI mode
        default_verbosity: Default verbosity level
        log_dir: Optional log directory
        
    Environment Variables:
        SNID_DEBUG: Set to 1 to enable debug logging
        SNID_VERBOSE: Set to 1 to enable verbose logging
        SNID_QUIET: Set to 1 to enable quiet mode
        SNID_LOG_FILE: Path to log file
        SNID_LOG_DIR: Directory for log files
    """
    
    # Get verbosity from environment
    verbosity = _get_verbosity_from_environment(default_verbosity)
    
    # Get log file settings from environment
    log_file = os.environ.get('SNID_LOG_FILE')
    if not log_dir:
        log_dir = os.environ.get('SNID_LOG_DIR')
    
    # Configure the logging system
    SNIDLogger.configure(
        verbosity=verbosity,
        gui_mode=gui_mode,
        log_file=log_file,
        log_dir=log_dir
    )


def _get_verbosity_from_environment(default: VerbosityLevel) -> VerbosityLevel:
    """
    Get verbosity level from environment variables
    
    Args:
        default: Default verbosity level if no environment variables set
        
    Returns:
        VerbosityLevel determined from environment or default
    """
    
    # Check debug first (highest priority)
    if _env_var_is_true('SNID_DEBUG'):
        return VerbosityLevel.DEBUG
    
    # Check verbose
    if _env_var_is_true('SNID_VERBOSE'):
        return VerbosityLevel.VERBOSE
    
    # Check quiet
    if _env_var_is_true('SNID_QUIET'):
        return VerbosityLevel.QUIET
        
    # Check silent
    if _env_var_is_true('SNID_SILENT'):
        return VerbosityLevel.SILENT
    
    # Check general verbosity level
    verbosity_str = os.environ.get('SNID_VERBOSITY', '').lower()
    if verbosity_str:
        try:
            return VerbosityLevel.from_string(verbosity_str)
        except (KeyError, ValueError):
            pass
    
    return default


def _env_var_is_true(var_name: str) -> bool:
    """
    Check if an environment variable is set to a "true" value
    
    Args:
        var_name: Environment variable name
        
    Returns:
        True if variable is set to 1, true, yes, on (case insensitive)
    """
    value = os.environ.get(var_name, '').lower()
    return value in ('1', 'true', 'yes', 'on')


def get_default_log_dir() -> Path:
    """
    Get the default log directory for SNID SAGE
    
    Returns:
        Path to default log directory
    """
    # Try to find project root
    current_path = Path.cwd()
    
    # Look for project markers
    project_markers = ['snid', 'interfaces', 'shared', 'run_snid_gui.py']
    
    for path in [current_path] + list(current_path.parents):
        if any((path / marker).exists() for marker in project_markers):
            return path / 'logs'
    
    # Fallback to current directory
    return current_path / 'logs'


def configure_for_gui(verbosity: Optional[str] = None,
                     enable_file_logging: bool = False) -> None:
    """
    Convenience function to configure logging for GUI applications
    
    Args:
        verbosity: Verbosity level ('normal', 'verbose', 'debug', etc.)
        enable_file_logging: Whether to enable file logging
    """
    
    # Determine verbosity
    if verbosity:
        verbosity_level = VerbosityLevel.from_string(verbosity)
    else:
        verbosity_level = _get_verbosity_from_environment(VerbosityLevel.NORMAL)
    
    # Setup log directory if file logging requested
    log_dir = None
    if enable_file_logging:
        log_dir = get_default_log_dir()
    
    # Configure logging
    SNIDLogger.configure(
        verbosity=verbosity_level,
        gui_mode=True,
        log_dir=log_dir
    )


def configure_for_cli(args: Optional[argparse.Namespace] = None,
                     verbosity: Optional[str] = None) -> None:
    """
    Convenience function to configure logging for CLI applications
    
    Args:
        args: Parsed command line arguments (optional)
        verbosity: Verbosity level string (used if args not provided)
    """
    
    if args:
        configure_from_args(args, gui_mode=False)
    else:
        # Configure from environment or explicit verbosity
        if verbosity:
            verbosity_level = VerbosityLevel.from_string(verbosity)
        else:
            verbosity_level = _get_verbosity_from_environment(VerbosityLevel.NORMAL)
        
        SNIDLogger.configure(verbosity=verbosity_level, gui_mode=False)


def print_logging_status() -> None:
    """Print current logging configuration (for debugging)"""
    try:
        verbosity = SNIDLogger.get_verbosity()
        gui_mode = SNIDLogger.is_gui_mode()
        
        print(f"SNID SAGE Logging Status:")
        print(f"  Verbosity: {verbosity.name}")
        print(f"  GUI Mode: {gui_mode}")
        
        instance = SNIDLogger()
        if instance._log_file:
            print(f"  Log File: {instance._log_file}")
        else:
            print(f"  Log File: None")
            
    except Exception as e:
        print(f"Error getting logging status: {e}")


def get_logger_config() -> Dict[str, Any]:
    """Get current logger configuration as dictionary"""
    try:
        instance = SNIDLogger()
        return {
            'verbosity': instance._verbosity_level.name,
            'gui_mode': instance._gui_mode,
            'log_file': str(instance._log_file) if instance._log_file else None,
            'configured': instance._configured
        }
    except Exception:
        return {'error': 'Logger not configured'} 