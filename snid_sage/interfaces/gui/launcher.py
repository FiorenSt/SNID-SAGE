"""
SNID SAGE GUI Launcher
======================

This module provides the entry point for launching the SNID SAGE GUI.
Only supports PySide6/Qt backend for modern cross-platform interface.
"""

import os
import sys
import platform

# Only set environment variables here (launcher) to avoid side effects on import.
# Ensure PySide6 backend flag is present before any GUI imports happen
os.environ['SNID_SAGE_GUI_BACKEND'] = 'PySide6'

def _is_wsl() -> bool:
    """Return True if running inside WSL."""
    try:
        # Env var is reliable starting from WSL2
        if os.environ.get('WSL_DISTRO_NAME'):
            return True
        # Fallback detection via kernel release string
        return 'microsoft' in platform.uname().release.lower()
    except Exception:
        return False

def _should_force_software_gl() -> bool:
    """Determine whether to force software OpenGL rendering.

    Rules:
    - Explicit override via SNID_FORCE_SOFTWARE_OPENGL=1/true/yes
    - WSL environments (OpenGL often unreliable)
    - Otherwise, do not force (let Qt auto-select hardware when available)
    """
    force_env = os.environ.get('SNID_FORCE_SOFTWARE_OPENGL', '').strip().lower()
    if force_env in ('1', 'true', 'yes'):
        return True
    if sys.platform.startswith('linux') and _is_wsl():
        return True
    return False

def _configure_rendering_environment(verbose: bool = False) -> None:
    """Apply environment configuration for rendering based on platform and flags."""
    # Always keep Qt logging quiet unless explicitly requested
    base_rules = os.environ.get('QT_LOGGING_RULES', '')
    extra_rules = 'qt.qpa.gl.debug=false;qt.qpa.windows.debug=false;*.debug=false'
    os.environ['QT_LOGGING_RULES'] = (base_rules + ';' + extra_rules) if base_rules else extra_rules
    os.environ['QT_QUIET_WINDOWS_WARNINGS'] = '1'

    if _should_force_software_gl():
        # Configure comprehensive software rendering for maximum compatibility
        os.environ['QT_OPENGL'] = 'software'
        os.environ['QT_QUICK_BACKEND'] = 'software'
        os.environ['QT_XCB_FORCE_SOFTWARE_OPENGL'] = '1'
        os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
        os.environ['QT_DEBUG_PLUGINS'] = '0'
        if verbose:
            print('ℹ️ Forcing software rendering (WSL/flag detected)')
    else:
        # Do NOT force software; allow Qt to choose the best backend
        # Clean up overrides if present (do not unset user-provided values)
        for var in ('QT_OPENGL', 'QT_QUICK_BACKEND', 'QT_XCB_FORCE_SOFTWARE_OPENGL', 'LIBGL_ALWAYS_SOFTWARE'):
            if os.environ.get(var) == 'software' or os.environ.get(var) == '1':
                os.environ.pop(var, None)

import argparse

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="SNID SAGE GUI")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--debug", "-d", action="store_true", help="Debug output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
    parser.add_argument("--silent", "-s", action="store_true", help="Silent mode")
    # Allow selecting processing profile at launch (e.g., onir, optical)
    parser.add_argument("--profile", dest="profile_id", type=str, default=None, help="Active processing profile id (e.g. 'onir' or 'optical')")
    
    # Check environment variables for defaults
    args = parser.parse_args()
    
    if os.environ.get('SNID_DEBUG', '').lower() in ('1', 'true', 'yes'):
        args.debug = True
        args.verbose = True
    elif os.environ.get('SNID_VERBOSE', '').lower() in ('1', 'true', 'yes'):
        args.verbose = True
    elif os.environ.get('SNID_QUIET', '').lower() in ('1', 'true', 'yes'):
        args.quiet = True
    
    return args

def launch_pyside6_gui(args=None):
    """Launch PySide6 GUI"""
    try:
        verbose = bool(args and args.verbose)
        if verbose:
            print("Launching SNID SAGE PySide6 GUI...")

        # Configure environment BEFORE importing any Qt modules
        _configure_rendering_environment(verbose=verbose)
        
        # Import PySide6 GUI
        from snid_sage.interfaces.gui.pyside6_gui import main as pyside6_main
        
        if verbose:
            print("✅ PySide6 GUI loaded successfully")
        
        return pyside6_main(args)
        
    except ImportError as e:
        print(f"❌ PySide6 not available: {e}")
        print("💡 Install PySide6 with: pip install PySide6 pyqtgraph")
        return 1
    except Exception as e:
        print(f"❌ Error launching PySide6 GUI: {e}")
        return 1

def main():
    """
    Main entry point for snid-sage command
    
    Only supports PySide6 (modern Qt interface) for cross-platform compatibility.
    """
    args = parse_arguments()
    
    if args.verbose:
        print("🎯 Using PySide6/Qt GUI backend")
    
    return launch_pyside6_gui(args)

def main_with_args():
    """
    Alternative entry point that accepts command line arguments
    """
    try:
        return main()
        
    except Exception as e:
        print(f"❌ Error launching SNID SAGE GUI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 