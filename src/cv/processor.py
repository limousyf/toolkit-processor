from typing import Optional

import numpy as np

from ..core.config import settings
from ..core.models import (
    ToolkitConfig,
    ToolAnalysisResult,
    AnalysisResult,
    AnalysisSummary,
    ToolStatus,
    ROI,
    RegistrationInfo,
)
from ..utils.image_utils import encode_image_base64
from .detection import ToolDetector
from .registration import ToolkitRegistration, RegistrationResult
from .visualization import ResultVisualizer


class ToolkitProcessor:
    """Main processor for analyzing toolkit images."""

    def __init__(
        self,
        detector: Optional[ToolDetector] = None,
        visualizer: Optional[ResultVisualizer] = None,
        registration: Optional[ToolkitRegistration] = None,
    ):
        """Initialize the processor.

        Args:
            detector: Tool detector instance (creates default if None)
            visualizer: Result visualizer instance (creates default if None)
            registration: Registration instance for ArUco marker detection (creates default if None)
        """
        self.detector = detector or ToolDetector()
        self.visualizer = visualizer or ResultVisualizer()

        # Initialize registration with global settings
        if registration is not None:
            self.registration = registration
        elif settings.aruco_enabled:
            self.registration = ToolkitRegistration(
                dictionary=settings.aruco_dictionary,
                marker_ids=settings.aruco_marker_ids,
                canonical_size=(settings.aruco_canonical_width, settings.aruco_canonical_height),
                min_markers_for_homography=settings.aruco_min_markers,
            )
        else:
            self.registration = None

    def analyze(
        self,
        image: np.ndarray,
        toolkit_config: ToolkitConfig,
        include_annotated_image: bool = True,
        include_debug_info: bool = False,
    ) -> AnalysisResult:
        """Analyze an image against a toolkit configuration.

        Args:
            image: Input image (BGR format from OpenCV)
            toolkit_config: Toolkit configuration with tool ROIs
            include_annotated_image: Whether to include annotated image in result
            include_debug_info: Whether to include detection metrics in result

        Returns:
            AnalysisResult with tool statuses and summary
        """
        # Step 1: Registration (ArUco marker detection and perspective correction)
        registration_info: Optional[RegistrationInfo] = None
        reg_result: Optional[RegistrationResult] = None
        working_image = image

        if self.registration is not None:
            reg_result = self.registration.register(image)
            working_image = reg_result.warped_image if reg_result.warped_image is not None else image
            registration_info = RegistrationInfo(
                markers_detected=reg_result.markers_detected,
                markers_expected=4,
                homography_applied=reg_result.success,
                fallback_reason=reg_result.fallback_reason,
            )

        # Step 2: Create detector with toolkit-specific thresholds if provided
        detector = ToolDetector(
            brightness_threshold=toolkit_config.brightness_threshold,
            occupied_ratio_threshold=toolkit_config.occupied_ratio_threshold,
        )

        tool_results: list[ToolAnalysisResult] = []
        rois: list[ROI] = []

        # Step 3: Process each tool slot
        for tool in toolkit_config.tools:
            detection = detector.detect(working_image, tool.roi)

            debug_info = None
            if include_debug_info:
                debug_info = {
                    "brightness_ratio": round(detection.metrics.brightness_ratio, 4),
                    "saturation_ratio": round(detection.metrics.saturation_ratio, 4),
                    "edge_density": round(detection.metrics.edge_density, 4),
                    "mean_brightness": round(detection.metrics.mean_brightness, 2),
                    "mean_saturation": round(detection.metrics.mean_saturation, 2),
                }

            tool_results.append(ToolAnalysisResult(
                tool_id=tool.tool_id,
                name=tool.name,
                slot_index=tool.slot_index,
                status=detection.status,
                confidence=detection.confidence,
                debug_info=debug_info,
            ))
            rois.append(tool.roi)

        # Calculate summary
        present = sum(1 for r in tool_results if r.status == ToolStatus.PRESENT)
        missing = sum(1 for r in tool_results if r.status == ToolStatus.MISSING)
        uncertain = sum(1 for r in tool_results if r.status == ToolStatus.UNCERTAIN)

        summary = AnalysisSummary(
            total_tools=len(tool_results),
            present=present,
            missing=missing,
            uncertain=uncertain,
        )

        # Determine overall status
        if missing == 0 and uncertain == 0:
            status = "complete"
        elif missing > 0 or uncertain > 0:
            status = "incomplete"
        else:
            status = "unknown"

        # Generate annotated image
        annotated_image_b64 = None
        if include_annotated_image:
            annotated = self.visualizer.annotate_image(
                working_image, tool_results, rois,
                show_labels=True,
                show_confidence=True,
                show_icons=True,
            )
            annotated = self.visualizer.create_summary_overlay(
                annotated, present, missing, uncertain
            )

            # Draw registration debug info if enabled
            if settings.aruco_debug and reg_result is not None:
                annotated = self.registration.draw_detected_markers(
                    annotated, reg_result.detected_markers
                )

            annotated_image_b64 = encode_image_base64(annotated)

        return AnalysisResult(
            toolkit_id=toolkit_config.toolkit_id,
            toolkit_name=toolkit_config.name,
            status=status,
            tools=tool_results,
            summary=summary,
            registration=registration_info,
            image_annotated=annotated_image_b64,
        )

    def analyze_with_reference(
        self,
        current_image: np.ndarray,
        reference_image: np.ndarray,
        toolkit_config: ToolkitConfig,
    ) -> AnalysisResult:
        """Analyze an image by comparing to a reference image.

        This is a placeholder for future "digital twin" comparison approach.
        Currently delegates to standard analysis.

        Args:
            current_image: Current state image
            reference_image: Reference "golden" image
            toolkit_config: Toolkit configuration

        Returns:
            AnalysisResult
        """
        # TODO: Implement SSIM or absdiff comparison per ROI
        # For now, just use standard detection
        return self.analyze(current_image, toolkit_config)
