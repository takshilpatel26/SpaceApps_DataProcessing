"""Enhanced DEM and terrain analysis processing with error handling."""

import logging
from pathlib import Path
from typing import Tuple, Optional, Union
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

from ..config.settings import ProcessingConfig
from ..utils.validation import validate_file_exists, validate_output_dir

# Configure GDAL availability
try:
    from osgeo import gdal

    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    logging.warning("GDAL not available - using rasterio fallback")

logger = logging.getLogger(__name__)


class DEMProcessor:
    """Advanced DEM processing with enhanced error handling and logging."""

    def __init__(self, config: ProcessingConfig):
        self.config = config
        logger.info("Initialized DEM processor")

    @validate_file_exists
    @validate_output_dir
    def calculate_slope(self, dem_file: Path, output_dir: Path) -> Path:
        """Calculate slope angle from DEM with comprehensive error handling."""
        logger.info(f"Starting slope calculation for: {dem_file.name}")

        try:
            if GDAL_AVAILABLE:
                return self._calculate_slope_gdal(dem_file, output_dir)
            else:
                return self._calculate_slope_rasterio(dem_file, output_dir)
        except Exception as e:
            logger.error(f"Slope calculation failed for {dem_file.name}: {str(e)}")
            raise

    def _calculate_slope_gdal(self, dem_file: Path, output_dir: Path) -> Path:
        """Calculate slope using GDAL with proper resource management."""
        slope_out = output_dir / f"slope_{dem_file.stem}.tif"
        temp_dem = None

        try:
            # Reproject to UTM for accurate calculations
            temp_dem = output_dir / f"temp_utm_{dem_file.stem}.tif"
            logger.debug("Reprojecting DEM to UTM...")

            gdal.Warp(
                str(temp_dem),
                str(dem_file),
                dstSRS=self.config.utm_projection,
                resampleAlg=gdal.GRA_Bilinear,
                format='GTiff'
            )

            # Calculate slope
            logger.debug("Computing slope...")
            gdal.DEMProcessing(
                str(slope_out),
                str(temp_dem),
                'slope',
                format='GTiff',
                slopeFormat=self.config.slope_calculation_method,
                computeEdges=True,
                alg='Horn'
            )

            logger.info(f"✅ Slope calculation complete: {slope_out}")
            return slope_out

        except Exception as e:
            logger.error(f"❌ GDAL slope calculation failed: {e}")
            raise
        finally:
            # Clean up temporary files
            if temp_dem and temp_dem.exists():
                temp_dem.unlink()
                logger.debug(f"Cleaned up temporary file: {temp_dem}")

    # Enhanced error handling for other methods...
