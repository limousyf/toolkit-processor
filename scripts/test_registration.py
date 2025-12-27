#!/usr/bin/env python3
"""
Test ArUco marker detection and registration.

Usage:
    python scripts/test_registration.py <image_path> [--output output.png]
    python scripts/test_registration.py --generate-markers [--output markers.png]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np

from src.core.config import settings
from src.cv.registration import ToolkitRegistration, MarkerPosition, POSITION_TO_ID


def generate_marker_sheet(output_path: Path, marker_size: int = 200, border: int = 50):
    """Generate a printable sheet with ArUco markers for all 4 corners."""
    markers = []

    # Get the ArUco dictionary
    dict_name = settings.aruco_dictionary
    dict_id = ToolkitRegistration.DICTIONARIES.get(dict_name, cv2.aruco.DICT_4X4_50)
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)

    # Generate each marker
    for position, marker_id in POSITION_TO_ID.items():
        marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)
        markers.append((position.value, marker_id, marker))

    # Create the output sheet (2x2 grid)
    cell_size = marker_size + 2 * border
    sheet = np.ones((cell_size * 2, cell_size * 2), dtype=np.uint8) * 255

    positions = [
        (0, 0),      # Top-left
        (0, 1),      # Top-right
        (1, 1),      # Bottom-right
        (1, 0),      # Bottom-left
    ]

    for (position_name, marker_id, marker), (row, col) in zip(markers, positions):
        y = row * cell_size + border
        x = col * cell_size + border
        sheet[y:y + marker_size, x:x + marker_size] = marker

        # Add label
        label = f"ID:{marker_id} ({position_name})"
        cv2.putText(
            sheet, label,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,), 1
        )

    cv2.imwrite(str(output_path), sheet)
    print(f"Marker sheet saved to: {output_path}")
    print(f"Dictionary: {dict_name}")
    print(f"Marker IDs: {settings.aruco_marker_ids}")
    print("\nPrint this sheet and cut out the markers.")
    print("Place them at the corners of your toolkit:")
    print("  - ID 0: Top-left")
    print("  - ID 1: Top-right")
    print("  - ID 2: Bottom-right")
    print("  - ID 3: Bottom-left")


def test_registration(image_path: Path, output_path: Path = None):
    """Test ArUco marker detection on an image."""
    print(f"Loading image: {image_path}")
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Error: Could not load image '{image_path}'")
        sys.exit(1)

    print(f"Image size: {image.shape[1]}x{image.shape[0]}")

    # Create registration instance
    registration = ToolkitRegistration(
        dictionary=settings.aruco_dictionary,
        marker_ids=settings.aruco_marker_ids,
        canonical_size=(settings.aruco_canonical_width, settings.aruco_canonical_height),
        min_markers_for_homography=settings.aruco_min_markers,
    )

    print(f"\nUsing dictionary: {settings.aruco_dictionary}")
    print(f"Expected marker IDs: {settings.aruco_marker_ids}")
    print(f"Canonical size: {settings.aruco_canonical_width}x{settings.aruco_canonical_height}")
    print(f"Min markers for homography: {settings.aruco_min_markers}")

    # Run registration
    print("\nDetecting markers...")
    result = registration.register(image)

    # Print results
    print(f"\n{'='*60}")
    print("REGISTRATION RESULTS")
    print(f"{'='*60}")
    print(f"Success: {result.success}")
    print(f"Markers detected: {result.markers_detected}/4")
    print(f"Fallback used: {result.fallback_used}")
    if result.fallback_reason:
        print(f"Fallback reason: {result.fallback_reason}")

    if result.detected_markers.detected_ids:
        print(f"\nDetected marker IDs: {result.detected_markers.detected_ids}")
        for marker_id, center in result.detected_markers.centers.items():
            position = MarkerPosition.TOP_LEFT
            for pos, mid in POSITION_TO_ID.items():
                if mid == marker_id:
                    position = pos
                    break
            print(f"  ID {marker_id} ({position.value}): center at ({center[0]:.0f}, {center[1]:.0f})")

    # Save output images
    if output_path or result.detected_markers.detected_ids:
        output_base = output_path or Path("img/registration_test.png")

        # Draw markers on original image
        annotated = registration.draw_detected_markers(image, result.detected_markers)
        annotated_path = output_base.with_suffix(".annotated.png")
        cv2.imwrite(str(annotated_path), annotated)
        print(f"\nAnnotated image saved to: {annotated_path}")

        # Save warped image if successful
        if result.success and result.warped_image is not None:
            warped_path = output_base.with_suffix(".warped.png")
            cv2.imwrite(str(warped_path), result.warped_image)
            print(f"Warped image saved to: {warped_path}")


def main():
    parser = argparse.ArgumentParser(description="Test ArUco marker registration")
    parser.add_argument("image_path", nargs="?", help="Path to image to test")
    parser.add_argument("--output", "-o", help="Output image path")
    parser.add_argument(
        "--generate-markers", "-g",
        action="store_true",
        help="Generate printable marker sheet instead of testing"
    )

    args = parser.parse_args()

    if args.generate_markers:
        output_path = Path(args.output) if args.output else Path("img/aruco_markers.png")
        generate_marker_sheet(output_path)
    elif args.image_path:
        image_path = Path(args.image_path)
        output_path = Path(args.output) if args.output else None
        test_registration(image_path, output_path)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/test_registration.py --generate-markers")
        print("  python scripts/test_registration.py img/toolkit_photo.jpg")
        sys.exit(1)


if __name__ == "__main__":
    main()
