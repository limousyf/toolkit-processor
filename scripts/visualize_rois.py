#!/usr/bin/env python3
"""
Visualize ROIs on an image for toolkit configuration tuning.

Usage:
    python scripts/visualize_rois.py <toolkit_id> [image_path] [--output output.png]

This script draws the configured ROIs on an image to help with fine-tuning coordinates.
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings


def load_toolkit_config(toolkit_id: str) -> dict:
    """Load a toolkit configuration from JSON."""
    config_path = settings.toolkit_config_dir / f"{toolkit_id}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Toolkit config not found: {config_path}")

    with open(config_path) as f:
        return json.load(f)


def draw_rois(image: np.ndarray, config: dict, show_labels: bool = True) -> np.ndarray:
    """Draw ROI rectangles on an image."""
    result = image.copy()

    # Colors for different slots (cycling through)
    colors = [
        (0, 255, 0),    # Green
        (255, 0, 0),    # Blue
        (0, 0, 255),    # Red
        (255, 255, 0),  # Cyan
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Yellow
        (128, 0, 255),  # Purple
        (0, 128, 255),  # Orange
        (255, 128, 0),  # Light Blue
    ]

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    thickness = 4

    for i, tool in enumerate(config.get("tools", [])):
        roi = tool.get("roi", {})
        x = roi.get("x", 0)
        y = roi.get("y", 0)
        w = roi.get("width", 0)
        h = roi.get("height", 0)

        color = colors[i % len(colors)]

        # Draw rectangle
        cv2.rectangle(result, (x, y), (x + w, y + h), color, thickness)

        if show_labels:
            # Draw label
            label = f"{tool['slot_index']}: {tool['name']}"
            label_size = cv2.getTextSize(label, font, font_scale, 2)[0]

            # Background for label
            cv2.rectangle(
                result,
                (x, y - label_size[1] - 20),
                (x + label_size[0] + 10, y),
                color,
                -1
            )

            # Label text
            cv2.putText(
                result, label,
                (x + 5, y - 10),
                font, font_scale, (255, 255, 255), 2, cv2.LINE_AA
            )

            # Draw ROI info at bottom of box
            roi_info = f"({x}, {y}) {w}x{h}"
            cv2.putText(
                result, roi_info,
                (x + 5, y + h - 10),
                font, 0.8, color, 2, cv2.LINE_AA
            )

    return result


def main():
    parser = argparse.ArgumentParser(description="Visualize toolkit ROIs on an image")
    parser.add_argument("toolkit_id", help="Toolkit configuration ID")
    parser.add_argument("image_path", nargs="?", help="Path to image (uses reference_image from config if not provided)")
    parser.add_argument("--output", "-o", help="Output image path (default: img/roi_preview.png)")
    parser.add_argument("--no-labels", action="store_true", help="Hide labels")
    parser.add_argument("--scale", type=float, default=0.5, help="Scale factor for output (default: 0.5)")

    args = parser.parse_args()

    # Load config
    print(f"Loading toolkit config: {args.toolkit_id}")
    config = load_toolkit_config(args.toolkit_id)

    # Determine image path
    image_path = args.image_path
    if not image_path:
        image_path = config.get("reference_image")
    if not image_path:
        print("Error: No image path provided and no reference_image in config")
        sys.exit(1)

    # Make path absolute if relative
    image_path = Path(image_path)
    if not image_path.is_absolute():
        image_path = settings.base_dir / image_path

    print(f"Loading image: {image_path}")
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        sys.exit(1)

    print(f"Image size: {image.shape[1]}x{image.shape[0]}")
    print(f"Found {len(config.get('tools', []))} tool slots")

    # Draw ROIs
    result = draw_rois(image, config, show_labels=not args.no_labels)

    # Scale if needed
    if args.scale != 1.0:
        new_size = (int(result.shape[1] * args.scale), int(result.shape[0] * args.scale))
        result = cv2.resize(result, new_size, interpolation=cv2.INTER_AREA)
        print(f"Scaled to: {new_size[0]}x{new_size[1]}")

    # Save result
    output_path = args.output or "img/roi_preview.png"
    output_path = Path(output_path)
    if not output_path.is_absolute():
        output_path = settings.base_dir / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), result)
    print(f"Saved preview to: {output_path}")

    # Print tool summary
    print("\nTool slots:")
    for tool in config.get("tools", []):
        roi = tool.get("roi", {})
        print(f"  {tool['slot_index']:2d}. {tool['name']:30s} @ ({roi['x']:4d}, {roi['y']:4d}) {roi['width']:4d}x{roi['height']:4d}")


if __name__ == "__main__":
    main()
