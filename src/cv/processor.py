from typing import Optional

import numpy as np

from ..core.models import (
    ToolkitConfig,
    ToolAnalysisResult,
    AnalysisResult,
    AnalysisSummary,
    ToolStatus,
    ROI,
)
from ..utils.image_utils import encode_image_base64
from .detection import ToolDetector
from .visualization import ResultVisualizer


class ToolkitProcessor:
    """Main processor for analyzing toolkit images."""

    def __init__(
        self,
        detector: Optional[ToolDetector] = None,
        visualizer: Optional[ResultVisualizer] = None,
    ):
        """Initialize the processor.

        Args:
            detector: Tool detector instance (creates default if None)
            visualizer: Result visualizer instance (creates default if None)
        """
        self.detector = detector or ToolDetector()
        self.visualizer = visualizer or ResultVisualizer()

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
        # Create detector with toolkit-specific thresholds if provided
        detector = ToolDetector(
            brightness_threshold=toolkit_config.brightness_threshold,
            occupied_ratio_threshold=toolkit_config.occupied_ratio_threshold,
        )

        tool_results: list[ToolAnalysisResult] = []
        rois: list[ROI] = []

        # Process each tool slot
        for tool in toolkit_config.tools:
            detection = detector.detect(image, tool.roi)

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
                image, tool_results, rois,
                show_labels=True,
                show_confidence=True,
                show_icons=True,
            )
            annotated = self.visualizer.create_summary_overlay(
                annotated, present, missing, uncertain
            )
            annotated_image_b64 = encode_image_base64(annotated)

        return AnalysisResult(
            toolkit_id=toolkit_config.toolkit_id,
            toolkit_name=toolkit_config.name,
            status=status,
            tools=tool_results,
            summary=summary,
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
