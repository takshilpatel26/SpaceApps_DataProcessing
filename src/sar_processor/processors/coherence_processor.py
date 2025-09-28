"""
Coherence Map Processor - Professional InSAR Processing Module
Extracted and refactored from the original test-2.py script
"""

import os
import logging
from pathlib import Path
from typing import Optional

# ESA SNAP imports
from esa_snappy import ProductIO, GPF, HashMap, jpy

# Internal imports
from ..config.settings import ProcessingConfig
from ..utils.validation import validate_file_exists, validate_output_dir
from .intensity_processor import IntensityProcessor

logger = logging.getLogger(__name__)


class CoherenceProcessor:
    """Professional SAR coherence map processor for InSAR analysis."""

    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.intensity_processor = IntensityProcessor(config)
        logger.info("Coherence Processor initialized")

    @validate_file_exists
    @validate_output_dir
    def generate_coherence_map(
            self,
            master_zip_path: str,
            slave_zip_path: str,
            output_dir: str,
            polarization: str = "VV"
    ) -> str:
        """
        Generate coherence map from two Sentinel-1 SLC acquisitions.

        Processing Pipeline:
        1. TOPSAR-Split (both images)
        2. Apply-Orbit-File (both images)
        3. Back-Geocoding (coregistration)
        4. Interferogram formation
        5. Band selection (coherence)
        6. TOPSAR-Deburst
        7. Terrain Correction

        Args:
            master_zip_path: Path to master SLC ZIP file
            slave_zip_path: Path to slave SLC ZIP file
            output_dir: Output directory
            polarization: Polarization to process (default: VV)

        Returns:
            Path to generated coherence map
        """
        logger.info("Starting coherence map generation (InSAR)")

        try:
            # Extract dates for filename
            date1_str = self.intensity_processor.extract_date(master_zip_path)
            date2_str = self.intensity_processor.extract_date(slave_zip_path)
            coherence_filename = f"{date1_str}_{date2_str}_coherence.tif"

            # Read input products
            logger.debug("Reading input products...")
            master = ProductIO.readProduct(master_zip_path)
            slave = ProductIO.readProduct(slave_zip_path)

            # Split subswath & polarization for both images
            logger.debug("Applying TOPSAR-Split...")
            split_params = HashMap()
            split_params.put("subswath", self.config.subswath)
            split_params.put("selectedPolarisations", polarization)

            master = GPF.createProduct("TOPSAR-Split", split_params, master)
            slave = GPF.createProduct("TOPSAR-Split", split_params, slave)

            # Apply orbit files
            logger.debug("Applying orbit files...")
            master = GPF.createProduct("Apply-Orbit-File", HashMap(), master)
            slave = GPF.createProduct("Apply-Orbit-File", HashMap(), slave)

            # Back-geocoding (Coregistration)
            logger.debug("Applying Back-Geocoding...")
            bg_params = HashMap()
            bg_params.put("demName", self.config.dem_name)
            bg_source_map = HashMap()
            bg_source_map.put("Master", master)
            bg_source_map.put("Slave", slave)

            product = GPF.createProduct("Back-Geocoding", bg_params, bg_source_map)
            logger.debug(f"Bands after Back-Geocoding: {list(product.getBandNames())}")

            # Interferogram formation and coherence estimation
            logger.debug("Creating interferogram...")
            product = GPF.createProduct("Interferogram", HashMap(), product)
            logger.debug(f"Bands after Interferogram: {list(product.getBandNames())}")

            # Find coherence band dynamically
            band_names = list(product.getBandNames())
            coherence_band_name = None

            for band_name in band_names:
                if "coh" in band_name.lower():
                    coherence_band_name = band_name
                    break

            if coherence_band_name is None:
                raise RuntimeError("No coherence band found in product!")

            logger.debug(f"Selected Coherence Band: {coherence_band_name}")

            # Band selection
            band_select_params = HashMap()
            bands_to_select = jpy.array("java.lang.String", [coherence_band_name])
            band_select_params.put("sourceBands", bands_to_select)
            product_clean = GPF.createProduct("BandSelect", band_select_params, product)
            logger.debug("BandSelect successful")

            # Debursting
            logger.info("Debursting...")
            product_deburst = GPF.createProduct("TOPSAR-Deburst", HashMap(), product_clean)
            logger.info("Deburst complete")

            # Terrain Correction
            logger.info("Applying Terrain Correction...")
            tc_params = HashMap()
            tc_params.put("demName", self.config.dem_name)
            tc_params.put("mapProjection", self.config.utm_projection)
            product_final = GPF.createProduct("Terrain-Correction", tc_params, product_deburst)
            logger.info("Terrain Correction Applied")

            # Save as GeoTIFF
            output_path = os.path.join(output_dir, coherence_filename)
            ProductIO.writeProduct(product_final, output_path, self.config.output_format)
            logger.info(f"✅ Coherence Map created: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"❌ Coherence map generation failed: {e}")
            raise

    def process_pair(
            self,
            master_file: Path,
            slave_file: Path,
            output_dir: Path
    ) -> Path:
        """
        Process a pair of Sentinel-1 files for coherence analysis.

        Args:
            master_file: Path to master SLC ZIP file
            slave_file: Path to slave SLC ZIP file
            output_dir: Output directory

        Returns:
            Path to generated coherence map
        """
        result_path = self.generate_coherence_map(
            str(master_file), str(slave_file), str(output_dir)
        )
        return Path(result_path)
