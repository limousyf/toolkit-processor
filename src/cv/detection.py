from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from ..core.config import settings
from ..core.models import ROI, ToolStatus


@dataclass
class DetectionMetrics:
    """Metrics computed during tool detection."""
    brightness_ratio: float  # Ratio of bright pixels
    saturation_ratio: float  # Ratio of saturated (colored) pixels
    edge_density: float  # Edge pixel density
    mean_brightness: float  # Average brightness in ROI
    mean_saturation: float  # Average saturation in ROI


@dataclass
class DetectionResult:
    """Result of detecting a single tool slot."""
    status: ToolStatus
    confidence: float
    metrics: DetectionMetrics


class ToolDetector:
    """Detects tool presence/absence in ROI regions using color and edge analysis."""

    def __init__(
        self,
        brightness_threshold: Optional[int] = None,
        occupied_ratio_threshold: Optional[float] = None,
        saturation_threshold: Optional[int] = None,
        color_ratio_threshold: Optional[float] = None,
    ):
        """Initialize detector with thresholds.

        Args:
            brightness_threshold: Pixels above this value (0-255) are "bright"
            occupied_ratio_threshold: Ratio of bright pixels to consider slot occupied
            saturation_threshold: Minimum saturation to consider pixel "colored"
            color_ratio_threshold: Ratio of colored pixels contributing to detection
        """
        self.brightness_threshold = brightness_threshold or settings.brightness_threshold
        self.occupied_ratio_threshold = occupied_ratio_threshold or settings.occupied_ratio_threshold
        self.saturation_threshold = saturation_threshold or settings.saturation_threshold
        self.color_ratio_threshold = color_ratio_threshold or settings.color_ratio_threshold

    def extract_roi(self, image: np.ndarray, roi: ROI) -> np.ndarray:
        """Extract region of interest from image.

        Args:
            image: Full image (BGR format)
            roi: Region of interest coordinates

        Returns:
            Cropped ROI region
        """
        h, w = image.shape[:2]

        # Clamp ROI to image bounds
        x1 = max(0, roi.x)
        y1 = max(0, roi.y)
        x2 = min(w, roi.x + roi.width)
        y2 = min(h, roi.y + roi.height)

        return image[y1:y2, x1:x2]

    def compute_metrics(self, roi_image: np.ndarray) -> DetectionMetrics:
        """Compute detection metrics for an ROI.

        Args:
            roi_image: Cropped ROI region (BGR format)

        Returns:
            DetectionMetrics with computed values
        """
        if roi_image.size == 0:
            return DetectionMetrics(
                brightness_ratio=0.0,
                saturation_ratio=0.0,
                edge_density=0.0,
                mean_brightness=0.0,
                mean_saturation=0.0,
            )

        # Convert to different color spaces
        gray = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(roi_image, cv2.COLOR_BGR2HSV)

        total_pixels = gray.size

        # Brightness analysis (using grayscale)
        bright_pixels = np.sum(gray > self.brightness_threshold)
        brightness_ratio = bright_pixels / total_pixels
        mean_brightness = np.mean(gray)

        # Saturation analysis (for colored tools like red handles)
        saturation = hsv[:, :, 1]
        saturated_pixels = np.sum(saturation > self.saturation_threshold)
        saturation_ratio = saturated_pixels / total_pixels
        mean_saturation = np.mean(saturation)

        # Edge detection (metallic tools have distinct edges)
        edges = cv2.Canny(gray, 50, 150)
        edge_pixels = np.sum(edges > 0)
        edge_density = edge_pixels / total_pixels

        return DetectionMetrics(
            brightness_ratio=brightness_ratio,
            saturation_ratio=saturation_ratio,
            edge_density=edge_density,
            mean_brightness=mean_brightness,
            mean_saturation=mean_saturation,
        )

    def detect(self, image: np.ndarray, roi: ROI) -> DetectionResult:
        """Detect if a tool is present in the given ROI.

        For dark foam backgrounds:
        - Empty slot: mostly dark pixels (foam visible)
        - Occupied slot: bright pixels (metallic) and/or colored pixels (handles)

        Args:
            image: Full image (BGR format)
            roi: Region of interest for the tool slot

        Returns:
            DetectionResult with status, confidence, and metrics
        """
        roi_image = self.extract_roi(image, roi)
        metrics = self.compute_metrics(roi_image)

        # Decision logic for dark foam with mixed surface/cutout visibility
        # When tool is missing, ROI shows mix of surface foam (light) and cutout shadow (dark)
        # When tool is present, ROI shows the tool surface (typically brighter overall)
        #
        # Key insight: Mean brightness is the best discriminator
        # - Present tools: μB typically 50-100
        # - Missing (empty cutout + surface): μB typically 35-50

        # Mean brightness thresholds (primary discriminator)
        # Based on real data: missing tool μB=41-50, present tools μB=57+
        MEAN_BRIGHT_PRESENT = 54.0   # Above this strongly suggests present
        MEAN_BRIGHT_MISSING = 44.0   # Below this strongly suggests missing

        # High saturation (colored handles/tools) is a strong presence indicator
        HIGH_SATURATION_THRESHOLD = 0.70  # 70% saturation ratio

        # Check mean brightness first - it's the strongest signal
        if metrics.mean_brightness >= MEAN_BRIGHT_PRESENT:
            # Above threshold - likely present
            status = ToolStatus.PRESENT

            # Confidence based on how far above threshold + saturation boost
            base_confidence = 0.80 + (metrics.mean_brightness - MEAN_BRIGHT_PRESENT) / 150
            # Boost confidence if high saturation (colored tool visible)
            if metrics.saturation_ratio >= HIGH_SATURATION_THRESHOLD:
                base_confidence += 0.10
            confidence = min(0.99, base_confidence)

        elif metrics.mean_brightness <= MEAN_BRIGHT_MISSING:
            # Low mean brightness - likely missing
            status = ToolStatus.MISSING
            # Lower μB = higher confidence it's missing
            confidence = min(0.99, 0.75 + (MEAN_BRIGHT_MISSING - metrics.mean_brightness) / 50)

        else:
            # In uncertain band (44-54) - be conservative, default to UNCERTAIN/MISSING
            # High saturation (colored tool handles) is strong evidence of presence
            if metrics.saturation_ratio >= HIGH_SATURATION_THRESHOLD:
                status = ToolStatus.PRESENT
                confidence = 0.85
            # High edge density (>30%) often indicates empty cutout edges, not a tool
            elif metrics.edge_density > 0.30:
                status = ToolStatus.MISSING
                confidence = 0.75
            # Low brightness ratio with low saturation suggests empty
            elif metrics.brightness_ratio < 0.35 and metrics.saturation_ratio < 0.50:
                status = ToolStatus.MISSING
                confidence = 0.70
            else:
                # Genuinely uncertain - use mean brightness to tip the scale
                mb_normalized = (metrics.mean_brightness - MEAN_BRIGHT_MISSING) / (MEAN_BRIGHT_PRESENT - MEAN_BRIGHT_MISSING)
                if mb_normalized >= 0.7:
                    status = ToolStatus.PRESENT
                    confidence = 0.70
                elif mb_normalized <= 0.3:
                    status = ToolStatus.MISSING
                    confidence = 0.70
                else:
                    status = ToolStatus.UNCERTAIN
                    confidence = 0.55

        return DetectionResult(
            status=status,
            confidence=round(confidence, 3),
            metrics=metrics,
        )

    def detect_batch(
        self, image: np.ndarray, rois: list[ROI]
    ) -> list[DetectionResult]:
        """Detect tool presence for multiple ROIs.

        Args:
            image: Full image (BGR format)
            rois: List of regions of interest

        Returns:
            List of DetectionResults in same order as input ROIs
        """
        return [self.detect(image, roi) for roi in rois]
