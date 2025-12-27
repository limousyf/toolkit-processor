"""ArUco marker detection and perspective correction for toolkit registration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cv2
import numpy as np


class MarkerPosition(str, Enum):
    """Standard marker positions on toolkit."""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"


# Mapping from position to expected marker ID (global standard)
POSITION_TO_ID: dict[MarkerPosition, int] = {
    MarkerPosition.TOP_LEFT: 0,
    MarkerPosition.TOP_RIGHT: 1,
    MarkerPosition.BOTTOM_RIGHT: 2,
    MarkerPosition.BOTTOM_LEFT: 3,
}

ID_TO_POSITION: dict[int, MarkerPosition] = {v: k for k, v in POSITION_TO_ID.items()}


@dataclass
class MarkerDetectionResult:
    """Result of ArUco marker detection."""
    detected_ids: list[int] = field(default_factory=list)
    corners: dict[int, np.ndarray] = field(default_factory=dict)  # ID → 4 corner points
    centers: dict[int, tuple[float, float]] = field(default_factory=dict)  # ID → center point

    @property
    def all_found(self) -> bool:
        """True if all 4 expected markers were detected."""
        return len(self.detected_ids) == 4 and all(i in self.detected_ids for i in range(4))

    @property
    def count(self) -> int:
        """Number of markers detected."""
        return len(self.detected_ids)


@dataclass
class RegistrationResult:
    """Result of the full registration pipeline."""
    success: bool
    warped_image: Optional[np.ndarray] = None
    homography: Optional[np.ndarray] = None
    detected_markers: MarkerDetectionResult = field(default_factory=MarkerDetectionResult)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

    @property
    def markers_detected(self) -> int:
        """Number of markers that were detected."""
        return self.detected_markers.count


class ToolkitRegistration:
    """ArUco marker detection and perspective correction for toolkit images."""

    # Available ArUco dictionaries
    DICTIONARIES = {
        "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
        "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
        "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
        "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
        "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
        "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
        "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
    }

    def __init__(
        self,
        dictionary: str = "DICT_4X4_50",
        marker_ids: list[int] = None,
        canonical_size: tuple[int, int] = (1000, 800),
        min_markers_for_homography: int = 3,
    ):
        """Initialize the registration system.

        Args:
            dictionary: ArUco dictionary name (e.g., "DICT_4X4_50")
            marker_ids: Expected marker IDs [top-left, top-right, bottom-right, bottom-left]
            canonical_size: Output image size (width, height) after perspective correction
            min_markers_for_homography: Minimum markers needed for transformation
        """
        if marker_ids is None:
            marker_ids = [0, 1, 2, 3]

        self.marker_ids = marker_ids
        self.canonical_size = canonical_size
        self.min_markers = min_markers_for_homography

        # Initialize ArUco detector with parameters tuned for real-world photos
        dict_id = self.DICTIONARIES.get(dictionary, cv2.aruco.DICT_4X4_50)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        self.aruco_params = cv2.aruco.DetectorParameters()

        # Relaxed parameters for better detection of markers in angled/rotated photos
        self.aruco_params.adaptiveThreshWinSizeMin = 3
        self.aruco_params.adaptiveThreshWinSizeMax = 53
        self.aruco_params.adaptiveThreshWinSizeStep = 4
        self.aruco_params.minMarkerPerimeterRate = 0.01  # Allow smaller markers
        self.aruco_params.maxMarkerPerimeterRate = 4.0
        self.aruco_params.polygonalApproxAccuracyRate = 0.05
        self.aruco_params.minCornerDistanceRate = 0.01
        self.aruco_params.minMarkerDistanceRate = 0.01
        self.aruco_params.perspectiveRemovePixelPerCell = 8
        self.aruco_params.perspectiveRemoveIgnoredMarginPerCell = 0.2

        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)

        # Define canonical corner positions (where markers should map to)
        w, h = canonical_size
        self.canonical_corners = {
            self.marker_ids[0]: np.array([0, 0], dtype=np.float32),       # Top-left
            self.marker_ids[1]: np.array([w, 0], dtype=np.float32),       # Top-right
            self.marker_ids[2]: np.array([w, h], dtype=np.float32),       # Bottom-right
            self.marker_ids[3]: np.array([0, h], dtype=np.float32),       # Bottom-left
        }

    def detect_markers(self, image: np.ndarray) -> MarkerDetectionResult:
        """Detect ArUco markers in the image.

        Args:
            image: Input image (BGR format)

        Returns:
            MarkerDetectionResult with detected marker IDs and corners
        """
        # Convert to grayscale for detection
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Detect markers
        corners, ids, rejected = self.detector.detectMarkers(gray)

        result = MarkerDetectionResult()

        if ids is None:
            return result

        # Process detected markers (keep first detection for each expected ID)
        for i, marker_id in enumerate(ids.flatten()):
            marker_id = int(marker_id)
            if marker_id in self.marker_ids and marker_id not in result.corners:
                result.detected_ids.append(marker_id)
                # corners[i] has shape (1, 4, 2) - 4 corner points
                marker_corners = corners[i][0]
                result.corners[marker_id] = marker_corners
                # Calculate center as average of corners
                center = marker_corners.mean(axis=0)
                result.centers[marker_id] = (float(center[0]), float(center[1]))

        return result

    def compute_homography(
        self,
        detected_corners: dict[int, np.ndarray]
    ) -> Optional[np.ndarray]:
        """Compute homography matrix from detected markers to canonical space.

        Args:
            detected_corners: Dict mapping marker ID to corner points

        Returns:
            3x3 homography matrix, or None if insufficient markers
        """
        if len(detected_corners) < self.min_markers:
            return None

        # Build point correspondences
        src_points = []
        dst_points = []

        for marker_id, corners in detected_corners.items():
            if marker_id in self.canonical_corners:
                # Use the center of detected marker (average of 4 corners)
                center = corners.mean(axis=0)
                src_points.append(center)
                dst_points.append(self.canonical_corners[marker_id])

        if len(src_points) < self.min_markers:
            return None

        src = np.array(src_points, dtype=np.float32)
        dst = np.array(dst_points, dtype=np.float32)

        if len(src_points) >= 4:
            # Full homography (perspective transform)
            homography, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
            return homography
        elif len(src_points) == 3:
            # Affine transform (no perspective, but handles rotation/scale/shear)
            affine = cv2.getAffineTransform(src[:3], dst[:3])
            # Convert 2x3 affine to 3x3 homography
            homography = np.vstack([affine, [0, 0, 1]])
            return homography
        else:
            # Only 2 points - limited transform
            # Estimate scale and translation only
            scale_x = np.linalg.norm(dst[1] - dst[0]) / max(np.linalg.norm(src[1] - src[0]), 1e-6)
            scale_y = scale_x  # Assume uniform scaling

            # Simple translation to center
            src_center = src.mean(axis=0)
            dst_center = dst.mean(axis=0)

            homography = np.array([
                [scale_x, 0, dst_center[0] - scale_x * src_center[0]],
                [0, scale_y, dst_center[1] - scale_y * src_center[1]],
                [0, 0, 1]
            ], dtype=np.float32)
            return homography

    def warp_to_canonical(
        self,
        image: np.ndarray,
        homography: np.ndarray
    ) -> np.ndarray:
        """Apply perspective transformation to flatten toolkit view.

        Args:
            image: Input image (BGR format)
            homography: 3x3 transformation matrix

        Returns:
            Warped image of canonical_size dimensions
        """
        w, h = self.canonical_size
        warped = cv2.warpPerspective(
            image,
            homography,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )
        return warped

    def register(self, image: np.ndarray) -> RegistrationResult:
        """Full registration pipeline: detect → compute homography → warp.

        Args:
            image: Input image (BGR format)

        Returns:
            RegistrationResult with warped image (or original on fallback)
        """
        # Step 1: Detect markers
        markers = self.detect_markers(image)

        if markers.count == 0:
            return RegistrationResult(
                success=False,
                warped_image=image,
                detected_markers=markers,
                fallback_used=True,
                fallback_reason="No ArUco markers detected"
            )

        if markers.count < self.min_markers:
            return RegistrationResult(
                success=False,
                warped_image=image,
                detected_markers=markers,
                fallback_used=True,
                fallback_reason=f"Only {markers.count} markers detected (need {self.min_markers})"
            )

        # Step 2: Compute homography
        homography = self.compute_homography(markers.corners)

        if homography is None:
            return RegistrationResult(
                success=False,
                warped_image=image,
                detected_markers=markers,
                fallback_used=True,
                fallback_reason="Failed to compute homography"
            )

        # Step 3: Warp image
        warped = self.warp_to_canonical(image, homography)

        return RegistrationResult(
            success=True,
            warped_image=warped,
            homography=homography,
            detected_markers=markers,
            fallback_used=False
        )

    def draw_detected_markers(
        self,
        image: np.ndarray,
        markers: MarkerDetectionResult,
        draw_ids: bool = True,
        draw_axes: bool = False,
    ) -> np.ndarray:
        """Draw detected markers on image for debugging.

        Args:
            image: Input image (BGR format)
            markers: Detection result
            draw_ids: Whether to draw marker IDs
            draw_axes: Whether to draw coordinate axes

        Returns:
            Image with markers drawn
        """
        output = image.copy()

        for marker_id, corners in markers.corners.items():
            # Draw marker outline
            pts = corners.astype(np.int32).reshape((-1, 1, 2))
            cv2.polylines(output, [pts], True, (0, 255, 0), 2)

            # Draw corner points
            for i, corner in enumerate(corners):
                color = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)][i]
                cv2.circle(output, tuple(corner.astype(int)), 5, color, -1)

            # Draw marker ID
            if draw_ids:
                center = corners.mean(axis=0).astype(int)
                position_name = ID_TO_POSITION.get(marker_id, MarkerPosition.TOP_LEFT).value
                label = f"ID:{marker_id} ({position_name})"
                cv2.putText(
                    output, label,
                    (center[0] - 40, center[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2
                )
                cv2.putText(
                    output, label,
                    (center[0] - 40, center[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 128, 0), 1
                )

        return output
