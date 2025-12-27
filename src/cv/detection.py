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
    # Reference comparison metrics (when reference image available)
    ssim_score: Optional[float] = None
    histogram_correlation: Optional[float] = None
    normalized_diff: Optional[float] = None


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

        For polygon ROIs, returns the bounding box crop.
        Use extract_roi_masked() for masked polygon extraction.

        Args:
            image: Full image (BGR format)
            roi: Region of interest coordinates

        Returns:
            Cropped ROI region (bounding box)
        """
        h, w = image.shape[:2]
        x, y, roi_w, roi_h = roi.bounding_box

        # Clamp ROI to image bounds
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w, x + roi_w)
        y2 = min(h, y + roi_h)

        return image[y1:y2, x1:x2]

    def extract_roi_masked(self, image: np.ndarray, roi: ROI) -> tuple[np.ndarray, np.ndarray]:
        """Extract region of interest with polygon mask.

        For polygon ROIs, creates a mask that excludes pixels outside the polygon.
        For rectangle ROIs, the mask covers the entire bounding box.

        Args:
            image: Full image (BGR format)
            roi: Region of interest coordinates (rectangle or polygon)

        Returns:
            Tuple of (cropped ROI region, binary mask where 255=inside polygon)
        """
        h, w = image.shape[:2]
        x, y, roi_w, roi_h = roi.bounding_box

        # Clamp ROI to image bounds
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w, x + roi_w)
        y2 = min(h, y + roi_h)

        # Extract bounding box region
        roi_image = image[y1:y2, x1:x2]

        if roi_image.size == 0:
            return roi_image, np.array([])

        # Create mask
        mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)

        if roi.is_polygon:
            # Create polygon mask, translating points to local coordinates
            local_points = np.array([(p[0] - x1, p[1] - y1) for p in roi.points], dtype=np.int32)
            cv2.fillPoly(mask, [local_points], 255)
        else:
            # Rectangle: entire region is valid
            mask[:] = 255

        return roi_image, mask

    def normalize_histogram(self, source: np.ndarray, reference: np.ndarray) -> np.ndarray:
        """Normalize source image histogram to match reference (histogram matching).

        This reduces the impact of lighting variations between images.

        Args:
            source: Source image to normalize (grayscale)
            reference: Reference image to match (grayscale)

        Returns:
            Normalized source image
        """
        # Calculate histograms
        src_hist, _ = np.histogram(source.flatten(), 256, [0, 256])
        ref_hist, _ = np.histogram(reference.flatten(), 256, [0, 256])

        # Calculate CDFs
        src_cdf = src_hist.cumsum()
        ref_cdf = ref_hist.cumsum()

        # Normalize CDFs
        src_cdf = src_cdf / src_cdf[-1]
        ref_cdf = ref_cdf / ref_cdf[-1]

        # Create lookup table
        lookup = np.zeros(256, dtype=np.uint8)
        for i in range(256):
            # Find the intensity in reference that has the same CDF value
            j = np.searchsorted(ref_cdf, src_cdf[i])
            lookup[i] = min(255, j)

        # Apply lookup table
        return lookup[source]

    def compute_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Compute Structural Similarity Index between two images.

        Args:
            img1: First image (grayscale)
            img2: Second image (grayscale)

        Returns:
            SSIM score between -1 and 1 (1 = identical)
        """
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        img1 = img1.astype(np.float64)
        img2 = img2.astype(np.float64)

        mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
        mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)

        mu1_sq = mu1 ** 2
        mu2_sq = mu2 ** 2
        mu1_mu2 = mu1 * mu2

        sigma1_sq = cv2.GaussianBlur(img1 ** 2, (11, 11), 1.5) - mu1_sq
        sigma2_sq = cv2.GaussianBlur(img2 ** 2, (11, 11), 1.5) - mu2_sq
        sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2

        ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / \
                   ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

        return float(np.mean(ssim_map))

    def compute_histogram_correlation(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Compute histogram correlation between two images.

        Args:
            img1: First image (grayscale)
            img2: Second image (grayscale)

        Returns:
            Correlation value between -1 and 1 (1 = identical histograms)
        """
        hist1 = cv2.calcHist([img1], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([img2], [0], None, [256], [0, 256])

        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)

        return float(cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL))

    def compute_normalized_difference(self, current: np.ndarray, reference: np.ndarray) -> float:
        """Compute normalized absolute difference between images.

        Args:
            current: Current image (grayscale)
            reference: Reference image (grayscale)

        Returns:
            Normalized difference (0 = identical, 1 = completely different)
        """
        diff = cv2.absdiff(current, reference)
        return float(np.mean(diff) / 255.0)

    def compare_to_reference(
        self,
        current_roi: np.ndarray,
        reference_roi: np.ndarray,
        mask: Optional[np.ndarray] = None,
    ) -> tuple[float, float, float]:
        """Compare current ROI to reference ROI using multiple metrics.

        Args:
            current_roi: Current check-in ROI (BGR format)
            reference_roi: Reference template ROI (BGR format)
            mask: Optional binary mask for polygon ROIs (255=inside, 0=outside)

        Returns:
            Tuple of (ssim_score, histogram_correlation, normalized_diff)
        """
        if current_roi.size == 0 or reference_roi.size == 0:
            return 0.0, 0.0, 1.0

        # Resize current to match reference if needed
        if current_roi.shape[:2] != reference_roi.shape[:2]:
            current_roi = cv2.resize(
                current_roi,
                (reference_roi.shape[1], reference_roi.shape[0]),
                interpolation=cv2.INTER_LINEAR
            )
            # Resize mask if provided
            if mask is not None:
                mask = cv2.resize(
                    mask,
                    (reference_roi.shape[1], reference_roi.shape[0]),
                    interpolation=cv2.INTER_NEAREST
                )

        # Convert to grayscale
        current_gray = cv2.cvtColor(current_roi, cv2.COLOR_BGR2GRAY)
        reference_gray = cv2.cvtColor(reference_roi, cv2.COLOR_BGR2GRAY)

        # Apply mask if provided - set masked-out regions to same value in both images
        if mask is not None and mask.size > 0:
            # Set pixels outside mask to 0 in both images
            current_gray = cv2.bitwise_and(current_gray, mask)
            reference_gray = cv2.bitwise_and(reference_gray, mask)

        # Option 3: Histogram normalization - match current histogram to reference
        current_normalized = self.normalize_histogram(current_gray, reference_gray)

        # Option 1: SSIM comparison (on normalized image)
        ssim_score = self.compute_ssim(current_normalized, reference_gray)

        # Option 2: Histogram correlation (on original images)
        hist_corr = self.compute_histogram_correlation(current_gray, reference_gray)

        # Normalized difference (on normalized image)
        norm_diff = self.compute_normalized_difference(current_normalized, reference_gray)

        return ssim_score, hist_corr, norm_diff

    def compute_metrics(self, roi_image: np.ndarray, mask: Optional[np.ndarray] = None) -> DetectionMetrics:
        """Compute detection metrics for an ROI.

        Args:
            roi_image: Cropped ROI region (BGR format)
            mask: Optional binary mask (255=inside ROI, 0=outside). If None, uses entire image.

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

        # Apply mask if provided
        if mask is not None and mask.size > 0:
            # Count only masked pixels
            total_pixels = np.sum(mask > 0)
            if total_pixels == 0:
                return DetectionMetrics(
                    brightness_ratio=0.0,
                    saturation_ratio=0.0,
                    edge_density=0.0,
                    mean_brightness=0.0,
                    mean_saturation=0.0,
                )

            # Apply mask to grayscale
            gray_masked = gray[mask > 0]
            bright_pixels = np.sum(gray_masked > self.brightness_threshold)
            brightness_ratio = bright_pixels / total_pixels
            mean_brightness = np.mean(gray_masked)

            # Apply mask to saturation
            saturation = hsv[:, :, 1]
            saturation_masked = saturation[mask > 0]
            saturated_pixels = np.sum(saturation_masked > self.saturation_threshold)
            saturation_ratio = saturated_pixels / total_pixels
            mean_saturation = np.mean(saturation_masked)

            # Edge detection (apply mask after Canny)
            edges = cv2.Canny(gray, 50, 150)
            edges_masked = edges[mask > 0]
            edge_pixels = np.sum(edges_masked > 0)
            edge_density = edge_pixels / total_pixels
        else:
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

    def detect(
        self,
        image: np.ndarray,
        roi: ROI,
        reference_image: Optional[np.ndarray] = None,
    ) -> DetectionResult:
        """Detect if a tool is present in the given ROI.

        When reference_image is provided, uses SSIM and histogram comparison
        for more robust detection under varying lighting conditions.

        Supports both rectangle and polygon ROIs. For polygons, only pixels
        inside the polygon are considered in the analysis.

        Args:
            image: Full image (BGR format)
            roi: Region of interest for the tool slot (rectangle or polygon)
            reference_image: Optional reference image for comparison-based detection

        Returns:
            DetectionResult with status, confidence, and metrics
        """
        # Extract ROI with mask for polygon support
        roi_image, mask = self.extract_roi_masked(image, roi)
        metrics = self.compute_metrics(roi_image, mask if roi.is_polygon else None)

        # If reference image provided, use comparison-based detection
        if reference_image is not None:
            ref_roi_image, ref_mask = self.extract_roi_masked(reference_image, roi)

            if ref_roi_image.size > 0:
                ssim_score, hist_corr, norm_diff = self.compare_to_reference(
                    roi_image, ref_roi_image, mask if roi.is_polygon else None
                )
                metrics.ssim_score = ssim_score
                metrics.histogram_correlation = hist_corr
                metrics.normalized_diff = norm_diff

                # Reference-based detection logic
                # High SSIM = current looks like reference = tool PRESENT
                # Low SSIM = current looks different = tool MISSING (showing foam)
                #
                # Thresholds tuned for real-world toolkit photos:
                # - SSIM >= 0.13: Tool likely present (real photos have lower SSIM due to lighting)
                # - SSIM <= 0.08: Tool likely missing (foam visible instead of tool)
                # - Histogram correlation helps disambiguate edge cases

                SSIM_PRESENT = 0.13
                SSIM_MISSING = 0.08
                HIST_CORR_PRESENT = 0.30
                HIST_CORR_MISSING = 0.15
                NORM_DIFF_MISSING = 0.30

                # Combine metrics for robust decision
                if ssim_score >= SSIM_PRESENT and hist_corr >= HIST_CORR_PRESENT:
                    # Strong match - tool present
                    status = ToolStatus.PRESENT
                    confidence = min(0.99, 0.75 + ssim_score * 0.3)

                elif ssim_score <= SSIM_MISSING or norm_diff >= NORM_DIFF_MISSING:
                    # Poor match or high difference - tool missing
                    status = ToolStatus.MISSING
                    confidence = min(0.99, 0.70 + (SSIM_MISSING - ssim_score) * 0.5)

                elif ssim_score >= SSIM_PRESENT:
                    # Good SSIM but lower histogram correlation
                    status = ToolStatus.PRESENT
                    confidence = 0.75

                elif hist_corr <= HIST_CORR_MISSING:
                    # Poor histogram match
                    status = ToolStatus.MISSING
                    confidence = 0.70

                else:
                    # Uncertain zone - use combined score
                    combined_score = (ssim_score + hist_corr) / 2
                    if combined_score >= 0.55:
                        status = ToolStatus.PRESENT
                        confidence = 0.65
                    elif combined_score <= 0.40:
                        status = ToolStatus.MISSING
                        confidence = 0.65
                    else:
                        status = ToolStatus.UNCERTAIN
                        confidence = 0.50

                return DetectionResult(
                    status=status,
                    confidence=round(confidence, 3),
                    metrics=metrics,
                )

        # Fallback: brightness-based detection (no reference available)
        # Mean brightness thresholds (primary discriminator)
        MEAN_BRIGHT_PRESENT = 54.0
        MEAN_BRIGHT_MISSING = 44.0
        HIGH_SATURATION_THRESHOLD = 0.70

        if metrics.mean_brightness >= MEAN_BRIGHT_PRESENT:
            status = ToolStatus.PRESENT
            base_confidence = 0.80 + (metrics.mean_brightness - MEAN_BRIGHT_PRESENT) / 150
            if metrics.saturation_ratio >= HIGH_SATURATION_THRESHOLD:
                base_confidence += 0.10
            confidence = min(0.99, base_confidence)

        elif metrics.mean_brightness <= MEAN_BRIGHT_MISSING:
            status = ToolStatus.MISSING
            confidence = min(0.99, 0.75 + (MEAN_BRIGHT_MISSING - metrics.mean_brightness) / 50)

        else:
            # Uncertain band
            if metrics.saturation_ratio >= HIGH_SATURATION_THRESHOLD:
                status = ToolStatus.PRESENT
                confidence = 0.85
            elif metrics.edge_density > 0.30:
                status = ToolStatus.MISSING
                confidence = 0.75
            elif metrics.brightness_ratio < 0.35 and metrics.saturation_ratio < 0.50:
                status = ToolStatus.MISSING
                confidence = 0.70
            else:
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
