"""
Simple Template Discovery Utility
=================================

Simplified template finder for both GitHub installations and installed packages.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from snid_sage.shared.utils.logging import get_logger

logger = get_logger('simple_template_finder')


def find_templates_directory() -> Optional[Path]:
    """
    Find the templates directory.

    New behavior:
    - Prefer the centralized templates manager (lazy download into user cache).
    - Fall back to the previous discovery strategies only for dev setups.
    """
    # Strategy 0: centralized manager (preferred)
    try:
        from snid_sage.shared.templates_manager import get_templates_dir

        managed_dir = get_templates_dir()
        if _validate_templates_directory(Path(managed_dir)):
            logger.debug(f"✅ Found templates via templates_manager: {managed_dir}")
            return Path(managed_dir)
    except Exception as e:
        logger.debug(f"templates_manager resolution failed: {e}")

    # Legacy strategies retained for development/edge cases -------------------
    try:
        import importlib.resources as pkg_resources

        # For Python 3.9+ with improved traversable API
        if hasattr(pkg_resources, "files"):
            try:
                templates_package = pkg_resources.files("snid_sage") / "templates"
                if templates_package.exists():
                    templates_dir = Path(str(templates_package))
                    if _validate_templates_directory(templates_dir):
                        logger.debug(
                            f"✅ Found templates in installed package (files API): {templates_dir}"
                        )
                        return templates_dir
            except Exception as e:
                logger.debug(f"Files API with snid_sage failed: {e}")

        # Fallback for older Python versions or if files API fails
        for pkg_structure in [
            ("snid_sage", "templates/template_index.json"),
            ("snid_sage.templates", "template_index.json"),
        ]:
            try:
                pkg_name, resource_path = pkg_structure
                with pkg_resources.path(pkg_name, resource_path) as template_path:
                    templates_dir = template_path.parent
                    if _validate_templates_directory(templates_dir):
                        logger.debug(
                            f"✅ Found templates in package {pkg_name} (path API): {templates_dir}"
                        )
                        return templates_dir
            except Exception as e:
                logger.debug(f"Path API with {pkg_structure} failed: {e}")

    except ImportError:
        logger.debug("importlib.resources not available")

    # Strategy: Check current working directory and project-relative locations
    cwd = Path.cwd()
    for candidate in [
        cwd / "templates",
        cwd / "snid_sage" / "templates",
    ]:
        if _validate_templates_directory(candidate):
            logger.debug(f"✅ Found templates in local path: {candidate}")
            return candidate

    # Strategy: Walk up for project root
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if any((current / marker).exists() for marker in ["pyproject.toml", "setup.py", "README.md"]):
            for candidate in [
                current / "snid_sage" / "templates",
                current / "templates",
            ]:
                if _validate_templates_directory(candidate):
                    logger.debug(f"✅ Found templates relative to project root: {candidate}")
                    return candidate
        current = current.parent
        if current == current.parent:
            break

    logger.warning("No valid templates directory found")
    return None


def _validate_templates_directory(templates_dir: Path) -> bool:
    """
    Validate that a directory contains valid SNID templates.
    
    OPTIMIZED: Only checks for template_index.json instead of scanning all HDF5 files
    to avoid startup delays. Full validation happens during analysis when needed.
    
    Args:
        templates_dir: Path to check
        
    Returns:
        True if directory contains valid templates
    """
    try:
        if not templates_dir.exists() or not templates_dir.is_dir():
            return False
        
        # FAST CHECK: Only look for template index file (preferred for HDF5 storage)
        index_file = templates_dir / 'template_index.json'
        if index_file.exists():
            logger.debug(f"Found template index file in {templates_dir}")
            return True
        
        # FAST FALLBACK: Quick check for any template-like files without full enumeration
        # Check if directory has potential template files without listing all
        has_hdf5 = any(templates_dir.glob('templates_*.hdf5'))
        if has_hdf5:
            logger.debug(f"Found HDF5 template files in {templates_dir}")
            return True
        
        logger.debug(f"No template files found in {templates_dir}")
        return False
        
    except Exception as e:
        logger.debug(f"Error validating templates directory {templates_dir}: {e}")
        return False


def find_templates_directory_or_raise() -> Path:
    """
    Find templates directory or raise an exception.
    
    Returns:
        Path to templates directory
        
    Raises:
        FileNotFoundError: If templates directory cannot be found
    """
    templates_dir = find_templates_directory()
    if templates_dir is None:
        raise FileNotFoundError(
            "Could not find SNID templates directory.\n"
            "\n"
            "By default, SNID SAGE lazily downloads the managed templates bank\n"
            "from the GitHub Release into a per-user cache the first time it is\n"
            "needed. You can trigger this explicitly with:\n"
            "  snid-sage-download-templates\n"
            "\n"
            "If you are working from a Git checkout or custom install, make sure\n"
            "the templates archive can be downloaded (see README) or that a\n"
            "valid templates directory is available."
        )
    return templates_dir


def find_images_directory() -> Optional[Path]:
    """
    Find the images directory for both GitHub installations and installed packages.
    Now always prioritizes snid_sage/images/ as the canonical location.
    """
    # Strategy 1: Check if we're in an installed package using importlib.resources
    try:
        import importlib.resources as pkg_resources
        if hasattr(pkg_resources, 'files'):
            try:
                images_package = pkg_resources.files('snid_sage') / 'images'
                if images_package.exists():
                    images_dir = Path(str(images_package))
                    if _validate_images_directory(images_dir):
                        logger.info(f"✅ Found images in installed package (files API): {images_dir}")
                        return images_dir
            except Exception as e:
                logger.debug(f"Files API with snid_sage images failed: {e}")
    except ImportError:
        logger.debug("importlib.resources not available")

    # Strategy 2: Check site-packages for installed package
    try:
        for path in sys.path:
            if 'site-packages' in path:
                site_packages = Path(path)
                for pkg_name in ['snid_sage', 'snid-sage', 'SNID_SAGE']:
                    pkg_dir = site_packages / pkg_name
                    if pkg_dir.exists():
                        images_dir = pkg_dir / 'images'
                        if _validate_images_directory(images_dir):
                            logger.info(f"✅ Found images in site-packages: {images_dir}")
                            return images_dir
    except Exception as e:
        logger.debug(f"Site-packages search for images failed: {e}")

    # Strategy 3: Check snid_sage/images in current working directory
    cwd = Path.cwd()
    images_dir = cwd / 'snid_sage' / 'images'
    if _validate_images_directory(images_dir):
        logger.info(f"✅ Found images in current directory snid_sage package: {images_dir}")
        return images_dir

    # Strategy 4: Check relative to snid_sage package in current directory
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if any((current / marker).exists() for marker in ['pyproject.toml', 'setup.py', 'README.md']):
            images_dir = current / 'snid_sage' / 'images'
            if _validate_images_directory(images_dir):
                logger.info(f"✅ Found images in project snid_sage package: {images_dir}")
                return images_dir
        current = current.parent
        if current == current.parent:
            break

    # Strategy 5: Check relative to module location (go up directories)
    current = Path(__file__).resolve().parent
    for _ in range(10):
        images_dir = current / 'snid_sage' / 'images'
        if _validate_images_directory(images_dir):
            logger.info(f"✅ Found images in snid_sage package relative to module: {images_dir}")
            return images_dir
        current = current.parent
        if current == current.parent:
            break

    logger.warning("No valid images directory found")
    return None


def _validate_images_directory(images_dir: Path) -> bool:
    """
    Validate that a directory contains valid image files.
    
    Args:
        images_dir: Path to check
        
    Returns:
        True if directory contains valid images
    """
    try:
        if not images_dir.exists() or not images_dir.is_dir():
            return False

        # Check for common image files (include SVG for QSS icons)
        image_extensions = ['*.png', '*.ico', '*.icns', '*.jpg', '*.jpeg', '*.svg']
        image_files = []
        for ext in image_extensions:
            image_files.extend(list(images_dir.glob(ext)))

        if image_files:
            logger.debug(f"Found {len(image_files)} image files in {images_dir}")
            return True

        logger.debug(f"No image files found in {images_dir}")
        return False

    except Exception as e:
        logger.debug(f"Error validating images directory {images_dir}: {e}")
        return False


if __name__ == "__main__":
    logger.info("SNID Simple Template Directory Finder")
    logger.info("=" * 50)
    
    templates_dir = find_templates_directory()
    if templates_dir:
        logger.info(f"✅ Templates found: {templates_dir}")
        
        # Show what's in the directory
        hdf5_files = list(templates_dir.glob('templates_*.hdf5'))
        
        if hdf5_files:
            logger.info(f"   📁 HDF5 template files: {len(hdf5_files)}")
            for hdf5_file in hdf5_files[:5]:  # Show first 5
                logger.info(f"      - {hdf5_file.name}")
            if len(hdf5_files) > 5:
                logger.info(f"      ... and {len(hdf5_files) - 5} more")
    else:
        logger.error("❌ No templates directory found")
        logger.error("Ensure you have cloned the full SNID-SAGE repository from GitHub")
        logger.error("or that templates were included in your pip installation") 