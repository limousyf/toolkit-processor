#!/usr/bin/env python3
"""
Test the analysis pipeline directly without the web server.

Usage:
    python scripts/test_analysis.py <toolkit_id> <image_path> [--output output.png]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2

from src.core.config import settings
from src.services.toolkit_service import toolkit_service
from src.cv.processor import ToolkitProcessor
from src.utils.image_utils import load_image, decode_image_base64


def main():
    parser = argparse.ArgumentParser(description="Test toolkit analysis")
    parser.add_argument("toolkit_id", help="Toolkit configuration ID")
    parser.add_argument("image_path", help="Path to image to analyze")
    parser.add_argument("--output", "-o", help="Output annotated image path")
    parser.add_argument("--debug", "-d", action="store_true", help="Include debug info")

    args = parser.parse_args()

    # Load toolkit config
    print(f"Loading toolkit: {args.toolkit_id}")
    toolkit = toolkit_service.get_toolkit(args.toolkit_id)
    if not toolkit:
        print(f"Error: Toolkit '{args.toolkit_id}' not found")
        sys.exit(1)

    print(f"Toolkit: {toolkit.name}")
    print(f"Tools: {len(toolkit.tools)}")

    # Load image
    print(f"\nLoading image: {args.image_path}")
    image = load_image(args.image_path)
    print(f"Image size: {image.shape[1]}x{image.shape[0]}")

    # Run analysis
    print("\nRunning analysis...")
    processor = ToolkitProcessor()
    result = processor.analyze(
        image=image,
        toolkit_config=toolkit,
        include_annotated_image=True,
        include_debug_info=args.debug,
    )

    # Print results
    print(f"\n{'='*60}")
    print(f"ANALYSIS RESULTS")
    print(f"{'='*60}")
    print(f"Status: {result.status.upper()}")
    print(f"Timestamp: {result.timestamp}")
    print(f"\nSummary:")
    print(f"  Total tools: {result.summary.total_tools}")
    print(f"  Present:     {result.summary.present}")
    print(f"  Missing:     {result.summary.missing}")
    print(f"  Uncertain:   {result.summary.uncertain}")

    print(f"\n{'='*60}")
    print("TOOL DETAILS")
    print(f"{'='*60}")

    # Group by status
    for status in ["missing", "uncertain", "present"]:
        tools = [t for t in result.tools if t.status == status]
        if tools:
            print(f"\n{status.upper()}:")
            for tool in tools:
                print(f"  - {tool.name} ({tool.tool_id})")
                print(f"    Confidence: {tool.confidence:.1%}")
                if args.debug and tool.debug_info:
                    print(f"    Brightness ratio: {tool.debug_info['brightness_ratio']:.3f}")
                    print(f"    Saturation ratio: {tool.debug_info['saturation_ratio']:.3f}")
                    print(f"    Mean brightness:  {tool.debug_info['mean_brightness']:.1f}")

    # Save annotated image
    if result.image_annotated:
        output_path = args.output or "img/analysis_result.png"
        output_path = Path(output_path)
        if not output_path.is_absolute():
            output_path = settings.base_dir / output_path

        annotated = decode_image_base64(result.image_annotated)
        cv2.imwrite(str(output_path), annotated)
        print(f"\nAnnotated image saved to: {output_path}")


if __name__ == "__main__":
    main()
