"""Command-line interface for SAR processor."""

import argparse
import logging
import sys
from pathlib import Path

# Import from the package
from ..config.settings import ProcessingConfig, ProjectPaths
from ..config.logging_config import setup_logging
from ..processors.intensity_processor import IntensityProcessor
from ..processors.coherence_processor import CoherenceProcessor

def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Professional SAR Image Processing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--version', action='version', version='SAR Processor 0.1.0'
    )

    parser.add_argument(
        '--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO', help='Logging level'
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test configuration')

    # Complete processing pipeline
    process_parser = subparsers.add_parser('process-all', help='Run complete SAR processing pipeline')
    process_parser.add_argument('--pre-event', type=Path,
                               default=Path("Inputs/pre_event/S1A_IW_SLC__1SDV_20240720T004052_20240720T004119_054837_06AD9C_26F2pre-event.zip"),
                               help='Pre-event SLC ZIP file')
    process_parser.add_argument('--post-event', type=Path,
                               default=Path("Inputs/post_event/S1A_IW_SLC__1SDV_20240801T004052_20240801T004119_055012_06B3B7_C85Dpost-event.zip"),
                               help='Post-event SLC ZIP file')
    process_parser.add_argument('--output-dir', type=Path, default=Path("Output"),
                               help='Output directory')

    # Intensity maps only
    intensity_parser = subparsers.add_parser('intensity', help='Generate intensity maps')
    intensity_parser.add_argument('slc_file', type=Path, help='Sentinel-1 SLC ZIP file')
    intensity_parser.add_argument('--output-dir', type=Path, default=Path("Output"),
                                 help='Output directory')

    # Coherence map only
    coherence_parser = subparsers.add_parser('coherence', help='Generate coherence map')
    coherence_parser.add_argument('master_file', type=Path, help='Master SLC ZIP file')
    coherence_parser.add_argument('slave_file', type=Path, help='Slave SLC ZIP file')
    coherence_parser.add_argument('--output-dir', type=Path, default=Path("Output"),
                                 help='Output directory')

    return parser

def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize configuration
        config = ProcessingConfig()
        paths = ProjectPaths()

        logger.info("SAR Processor initialized successfully")

        if args.command == 'test':
            print("✅ Configuration test successful!")
            print(f"Base directory: {paths.base_dir}")
            print(f"Inputs directory: {paths.inputs_dir}")
            print(f"Outputs directory: {paths.outputs_dir}")

        elif args.command == 'process-all':
            logger.info("🚀 Starting complete SAR processing pipeline...")

            # Initialize processors
            intensity_proc = IntensityProcessor(config)
            coherence_proc = CoherenceProcessor(config)

            # Create output directory
            args.output_dir.mkdir(parents=True, exist_ok=True)

            # Process pre-event intensity maps
            if args.pre_event.exists():
                logger.info(f"Processing pre-event intensity: {args.pre_event.name}")
                vv1, vh1 = intensity_proc.process_file(args.pre_event, args.output_dir)
                logger.info(f"✅ Pre-event intensity maps: {vv1.name}, {vh1.name}")
            else:
                logger.error(f"Pre-event file not found: {args.pre_event}")
                return

            # Process post-event intensity maps
            if args.post_event.exists():
                logger.info(f"Processing post-event intensity: {args.post_event.name}")
                vv2, vh2 = intensity_proc.process_file(args.post_event, args.output_dir)
                logger.info(f"✅ Post-event intensity maps: {vv2.name}, {vh2.name}")
            else:
                logger.error(f"Post-event file not found: {args.post_event}")
                return

            # Process coherence map
            if args.pre_event.exists() and args.post_event.exists():
                logger.info("Processing coherence map...")
                coh_path = coherence_proc.process_pair(args.pre_event, args.post_event, args.output_dir)
                logger.info(f"✅ Coherence map: {coh_path.name}")

            logger.info("🎉 Complete SAR processing pipeline finished!")

        elif args.command == 'intensity':
            logger.info(f"Processing intensity maps for: {args.slc_file.name}")
            intensity_proc = IntensityProcessor(config)
            args.output_dir.mkdir(parents=True, exist_ok=True)
            vv, vh = intensity_proc.process_file(args.slc_file, args.output_dir)
            logger.info(f"✅ Intensity maps created: {vv.name}, {vh.name}")

        elif args.command == 'coherence':
            logger.info(f"Processing coherence map: {args.master_file.name} + {args.slave_file.name}")
            coherence_proc = CoherenceProcessor(config)
            args.output_dir.mkdir(parents=True, exist_ok=True)
            coh_path = coherence_proc.process_pair(args.master_file, args.slave_file, args.output_dir)
            logger.info(f"✅ Coherence map created: {coh_path.name}")

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
