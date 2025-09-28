"""
Intensity Map Processor - Professional SAR Processing Module
Extracted and refactored from the original test-2.py script
"""

import os
import logging
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime

# ESA SNAP imports
from esa_snappy import ProductIO, GPF, HashMap, jpy

# Internal imports
from ..config.settings import ProcessingConfig
from ..utils.validation import validate_file_exists, validate_output_dir

logger = logging.getLogger(__name__)

class IntensityProcessor:
    """Professional SAR intensity map processor based on your original workflow."""

    def __init__(self, config: ProcessingConfig):
        self.config = config
        logger.info("Intensity Processor initialized")

    def extract_date(self, zip_path: str) -> str:
        """
        Extract YYYY-MM-DD date string from Sentinel-1 ZIP filename.

        Args:
            zip_path: Path to Sentinel-1 SLC ZIP file

        Returns:
            Date string in YYYY-MM-DD format

        Example:
            S1A_IW_SLC__1SDV_20240720T004052... -> 2024-07-20
        """
        filename = os.path.basename(zip_path)
        parts = filename.split('_')

        # Look for 8-digit date followed by 'T'
        for part in parts:
            if len(part) >= 9 and part.startswith('2') and 'T' in part:
                date_str = part[:8]  # Extract YYYYMMDD
                try:
                    return datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
                except ValueError:
                    continue

        raise ValueError(f"Could not extract date from filename: {zip_path}")

    @validate_file_exists
    @validate_output_dir
    def generate_intensity_maps(self, input_zip_path: str, output_dir: str) -> Tuple[str, str]:
        """
        Generate pre-processed intensity maps from Sentinel-1 SLC data.

        Processing Pipeline:
        1. TOPSAR-Split (for IW2)
        2. Apply-Orbit-File
        3. ThermalNoiseRemoval
        4. Calibration (Radiometric)
        5. TOPSAR-Deburst
        6. Speckle Filtering
        7. Terrain Correction

        Args:
            input_zip_path: Path to Sentinel-1 SLC ZIP file
            output_dir: Output directory for processed files

        Returns:
            Tuple of (VV_path, VH_path) for generated intensity maps
        """
        logger.info(f"Starting intensity map generation for: {os.path.basename(input_zip_path)}")

        try:
            date_str = self.extract_date(input_zip_path)
            product = ProductIO.readProduct(input_zip_path)

            # 1. TOPSAR-Split for subswath IW2 and both polarizations
            logger.debug("Applying TOPSAR-Split...")
            split_params = HashMap()
            split_params.put("subswath", self.config.subswath)
            split_params.put("selectedPolarisations", ",".join(self.config.polarizations))
            product = GPF.createProduct("TOPSAR-Split", split_params, product)

            # 2. Apply orbit files
            logger.debug("Applying orbit files...")
            product = GPF.createProduct("Apply-Orbit-File", HashMap(), product)

            # 3. Thermal Noise Removal
            logger.debug("Removing thermal noise...")
            product = GPF.createProduct("ThermalNoiseRemoval", HashMap(), product)

            # 4. Calibration (Radiometric Calibration)
            logger.debug("Applying radiometric calibration...")
            calib_params = HashMap()
            calib_params.put("outputBetaBand", True)
            product = GPF.createProduct("Calibration", calib_params, product)

            # 5. TOPSAR-Deburst
            logger.debug("Applying TOPSAR-Deburst...")
            product = GPF.createProduct("TOPSAR-Deburst", HashMap(), product)

            # 6. Speckle Filtering
            logger.info("Applying Speckle Filter...")
            java_int_type = jpy.get_type('java.lang.Integer')
            speckle_params = HashMap()
            speckle_params.put("filter", "Refined Lee")
            speckle_params.put("filterSizeX", java_int_type(5))
            speckle_params.put("filterSizeY", java_int_type(5))
            product = GPF.createProduct("Speckle-Filter", speckle_params, product)
            logger.info("Speckle Filter complete")

            # 7. Terrain Correction
            logger.info("Applying Terrain Correction...")
            tc_params = HashMap()
            tc_params.put("demName", self.config.dem_name)
            tc_params.put("mapProjection", self.config.utm_projection)
            tc_params.put("pixelSpacingInMeter", self.config.pixel_spacing)
            product_final = GPF.createProduct("Terrain-Correction", tc_params, product)
            logger.info("Terrain Correction Applied")

            # Dynamic band selection and saving
            all_band_names = list(product_final.getBandNames())
            vv_name = None
            vh_name = None

            # Search for VV and VH intensity bands
            for name in all_band_names:
                if ('vv' in name.lower()) and ('beta0' in name.lower() or 'intensity' in name.lower()):
                    vv_name = name
                elif ('vh' in name.lower()) and ('beta0' in name.lower() or 'intensity' in name.lower()):
                    vh_name = name

            if vv_name is None or vh_name is None:
                raise RuntimeError(
                    f"Could not find VV or VH intensity bands. Available bands: {all_band_names}"
                )

            logger.debug(f"Found bands: VV='{vv_name}', VH='{vh_name}'")

            # Save VV band
            vv_select_params = HashMap()
            vv_select_params.put("sourceBands", jpy.array("java.lang.String", [vv_name]))
            vv_output_path = os.path.join(output_dir, f"{date_str}_vv.tif")
            vv_product = GPF.createProduct("BandSelect", vv_select_params, product_final)
            ProductIO.writeProduct(vv_product, vv_output_path, self.config.output_format)
            logger.info(f"✅ Intensity Map VV created: {vv_output_path}")

            # Save VH band
            vh_select_params = HashMap()
            vh_select_params.put("sourceBands", jpy.array("java.lang.String", [vh_name]))
            vh_output_path = os.path.join(output_dir, f"{date_str}_vh.tif")
            vh_product = GPF.createProduct("BandSelect", vh_select_params, product_final)
            ProductIO.writeProduct(vh_product, vh_output_path, self.config.output_format)
            logger.info(f"✅ Intensity Map VH created: {vh_output_path}")

            return vv_output_path, vh_output_path

        except Exception as e:
            logger.error(f"❌ Intensity map generation failed: {e}")
            raise

    def process_file(self, input_file: Path, output_dir: Path) -> Tuple[Path, Path]:
        """
        Process a single Sentinel-1 file for intensity maps.

        Args:
            input_file: Path to input Sentinel-1 SLC ZIP file
            output_dir: Output directory

        Returns:
            Tuple of output file paths (VV, VH)
        """
        vv_path, vh_path = self.generate_intensity_maps(str(input_file), str(output_dir))
        return Path(vv_path), Path(vh_path)
