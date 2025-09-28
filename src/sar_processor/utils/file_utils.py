"""File operation utilities"""

import logging
import numpy as np
import rasterio
from pathlib import Path
from typing import List, Dict, Optional, Any
import glob
import os

logger = logging.getLogger(_name_)


def find_files_by_pattern(input_dir: Path, pattern: str) -> List[Path]:
    """
    Find files matching a pattern in directory

    Args:
        input_dir: Directory to search
        pattern: File pattern (with wildcards)

    Returns:
        List of matching file paths
    """
    search_pattern = str(input_dir / pattern)
    matches = glob.glob(search_pattern, recursive=True)
    file_paths = [Path(match) for match in matches]

    logger.info(f"Pattern '{pattern}': found {len(file_paths)} files")
    return file_paths


def find_file_by_pattern(input_dir: Path, pattern: str) -> Optional[Path]:
    """
    Find single file matching pattern

    Args:
        input_dir: Directory to search
        pattern: File pattern

    Returns:
        Path to first matching file, None if not found
    """
    matches = find_files_by_pattern(input_dir, pattern)

    if len(matches) == 0:
        logger.warning(f"No files found matching pattern: {pattern}")
        return None
    elif len(matches) > 1:
        logger.warning(f"Multiple files found for pattern {pattern}, using first: {matches[0].name}")

    return matches[0]


def save_geotiff(data: np.ndarray,
                 profile: rasterio.profiles.Profile,
                 output_path: Path,
                 compress: str = 'lzw',
                 nodata: Optional[float] = None) -> None:
    """
    Save numpy array as GeoTIFF with proper compression

    Args:
        data: Data array to save
        profile: Rasterio profile with georeferencing info
        output_path: Output file path
        compress: Compression method ('lzw', 'deflate', 'packbits', None)
        nodata: NoData value
    """
    logger.info(f"Saving GeoTIFF: {output_path.name}")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Update profile
    profile = profile.copy()
    profile.update({
        'dtype': data.dtype,
        'count': 1,
        'compress': compress,
        'tiled': True,
        'blockxsize': 512,
        'blockysize': 512
    })

    if nodata is not None:
        profile['nodata'] = nodata

    # Handle different data dimensions
    if data.ndim == 3:
        profile['count'] = data.shape[0]
        write_data = data
    else:
        write_data = data[np.newaxis, :]  # Add band dimension

    try:
        with rasterio.open(output_path, 'w', **profile) as dst:
            if data.ndim == 3:
                for i in range(data.shape[0]):
                    dst.write(write_data[i], i + 1)
            else:
                dst.write(write_data[0], 1)

        # Log file info
        file_size = output_path.stat().st_size / 1024 / 1024  # MB
        logger.info(f"✅ Saved: {output_path.name} ({file_size:.1f} MB)")

    except Exception as e:
        logger.error(f"Failed to save GeoTIFF: {e}")
        raise


def create_output_structure(base_dir: Path) -> Dict[str, Path]:
    """
    Create standardized output directory structure

    Args:
        base_dir: Base output directory

    Returns:
        Dictionary of created directory paths
    """
    logger.info(f"Creating output structure in: {base_dir}")

    directories = {
        'sar_processed': base_dir / 'sar_processed',
        'features': base_dir / 'features',
        'terrain': base_dir / 'terrain',
        'change_detection': base_dir / 'change_detection',
        'candidates': base_dir / 'candidates',
        'validation': base_dir / 'validation',
        'intermediate': base_dir / 'intermediate'
    }

    # Create directories
    for name, path in directories.items():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created: {name} -> {path}")

    return directories


def cleanup_intermediate_files(intermediate_dir: Path,
                               keep_patterns: Optional[List[str]] = None) -> None:
    """
    Clean up intermediate processing files

    Args:
        intermediate_dir: Directory containing intermediate files
        keep_patterns: List of filename patterns to keep
    """
    if not intermediate_dir.exists():
        return

    keep_patterns = keep_patterns or []
    logger.info(f"Cleaning up intermediate files in: {intermediate_dir}")

    removed_count = 0
    total_size = 0

    for file_path in intermediate_dir.rglob('*'):
        if file_path.is_file():
            # Check if file should be kept
            keep_file = any(pattern in file_path.name for pattern in keep_patterns)

            if not keep_file:
                file_size = file_path.stat().st_size
                total_size += file_size
                file_path.unlink()
                removed_count += 1

    logger.info(f"Removed {removed_count} intermediate files "
                f"({total_size / 1024 / 1024:.1f} MB freed)")


def get_disk_usage(directory: Path) -> Dict[str, float]:
    """
    Get disk usage information for directory

    Args:
        directory: Directory to analyze

    Returns:
        Dictionary with usage statistics in MB
    """
    if not directory.exists():
        return {'total_mb': 0, 'file_count': 0}

    total_size = 0
    file_count = 0

    for file_path in directory.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
            file_count += 1

    return {
        'total_mb': total_size / 1024 / 1024,
        'file_count': file_count
    }