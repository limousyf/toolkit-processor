from typing import Optional

import cv2
import numpy as np

from ..core.models import ToolAnalysisResult, ToolStatus, ROI


class ResultVisualizer:
    """Visualizes analysis results on images."""

    # Color scheme (BGR format)
    COLORS = {
        ToolStatus.PRESENT: (0, 200, 0),      # Green
        ToolStatus.MISSING: (0, 0, 220),      # Red
        ToolStatus.UNCERTAIN: (0, 165, 255),  # Orange
    }

    LABEL_BG_COLORS = {
        ToolStatus.PRESENT: (0, 150, 0),
        ToolStatus.MISSING: (0, 0, 180),
        ToolStatus.UNCERTAIN: (0, 130, 200),
    }

    def __init__(self, line_thickness: int = 3, font_scale: float = 0.7):
        """Initialize visualizer.

        Args:
            line_thickness: Thickness of bounding box lines
            font_scale: Scale factor for text labels
        """
        self.line_thickness = line_thickness
        self.font_scale = font_scale
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def draw_roi(
        self,
        image: np.ndarray,
        roi: ROI,
        status: ToolStatus,
        label: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> np.ndarray:
        """Draw a single ROI with status indicator.

        Args:
            image: Image to draw on (will be modified in place)
            roi: Region of interest coordinates
            status: Tool status for color coding
            label: Optional label text
            confidence: Optional confidence score to display

        Returns:
            Modified image
        """
        color = self.COLORS[status]
        bg_color = self.LABEL_BG_COLORS[status]

        # Draw rectangle
        x1, y1 = roi.x, roi.y
        x2, y2 = roi.x + roi.width, roi.y + roi.height
        cv2.rectangle(image, (x1, y1), (x2, y2), color, self.line_thickness)

        # Draw label if provided
        if label:
            # Build label text
            label_text = label
            if confidence is not None:
                label_text += f" ({confidence:.0%})"

            # Calculate text size
            (text_w, text_h), baseline = cv2.getTextSize(
                label_text, self.font, self.font_scale, 1
            )

            # Position label above the box (or below if near top edge)
            padding = 4
            if y1 > text_h + padding * 2 + 5:
                # Label above
                label_y1 = y1 - text_h - padding * 2
                label_y2 = y1
                text_y = y1 - padding
            else:
                # Label below
                label_y1 = y2
                label_y2 = y2 + text_h + padding * 2
                text_y = y2 + text_h + padding

            # Draw label background
            cv2.rectangle(
                image,
                (x1, label_y1),
                (x1 + text_w + padding * 2, label_y2),
                bg_color,
                -1,  # Filled
            )

            # Draw label text
            cv2.putText(
                image,
                label_text,
                (x1 + padding, text_y),
                self.font,
                self.font_scale,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return image

    def draw_status_icon(
        self,
        image: np.ndarray,
        roi: ROI,
        status: ToolStatus,
    ) -> np.ndarray:
        """Draw a status icon (checkmark or X) in the center of the ROI.

        Args:
            image: Image to draw on
            roi: Region of interest
            status: Tool status

        Returns:
            Modified image
        """
        color = self.COLORS[status]
        center_x = roi.x + roi.width // 2
        center_y = roi.y + roi.height // 2

        icon_size = min(roi.width, roi.height) // 4
        icon_size = max(10, min(icon_size, 30))  # Clamp size

        if status == ToolStatus.PRESENT:
            # Draw checkmark
            pts = np.array([
                [center_x - icon_size, center_y],
                [center_x - icon_size // 3, center_y + icon_size // 2],
                [center_x + icon_size, center_y - icon_size // 2],
            ], np.int32)
            cv2.polylines(image, [pts], False, color, 2, cv2.LINE_AA)
        elif status == ToolStatus.MISSING:
            # Draw X
            cv2.line(
                image,
                (center_x - icon_size, center_y - icon_size),
                (center_x + icon_size, center_y + icon_size),
                color, 2, cv2.LINE_AA
            )
            cv2.line(
                image,
                (center_x + icon_size, center_y - icon_size),
                (center_x - icon_size, center_y + icon_size),
                color, 2, cv2.LINE_AA
            )
        else:
            # Draw question mark for uncertain
            cv2.putText(
                image, "?",
                (center_x - icon_size // 2, center_y + icon_size // 2),
                self.font, 1.0, color, 2, cv2.LINE_AA
            )

        return image

    def annotate_image(
        self,
        image: np.ndarray,
        results: list[ToolAnalysisResult],
        rois: list[ROI],
        show_labels: bool = True,
        show_confidence: bool = True,
        show_icons: bool = True,
        show_debug: bool = True,
    ) -> np.ndarray:
        """Annotate an image with analysis results.

        Args:
            image: Original image
            results: List of tool analysis results
            rois: List of ROIs corresponding to results
            show_labels: Whether to show tool name labels
            show_confidence: Whether to show confidence scores
            show_icons: Whether to show status icons
            show_debug: Whether to show debug metrics (B/S/E scores)

        Returns:
            Annotated image copy
        """
        annotated = image.copy()

        for result, roi in zip(results, rois):
            # Draw ROI box with status color
            label = result.name if show_labels else None
            confidence = result.confidence if show_confidence else None

            self.draw_roi(annotated, roi, result.status, label, confidence)

            if show_icons:
                self.draw_status_icon(annotated, roi, result.status)

            # Draw debug metrics below the ROI box
            if show_debug and result.debug_info:
                self._draw_debug_metrics(annotated, roi, result.debug_info)

        return annotated

    def _draw_debug_metrics(
        self,
        image: np.ndarray,
        roi: ROI,
        debug_info: dict,
    ) -> None:
        """Draw debug metrics below the ROI box.

        Args:
            image: Image to draw on
            roi: Region of interest
            debug_info: Dictionary with brightness_ratio, saturation_ratio, edge_density, mean_brightness
        """
        x1 = roi.x
        y2 = roi.y + roi.height

        # Build debug text
        b = debug_info.get('brightness_ratio', 0) * 100
        s = debug_info.get('saturation_ratio', 0) * 100
        e = debug_info.get('edge_density', 0) * 100
        mb = debug_info.get('mean_brightness', 0)

        debug_text = f"B:{b:.0f}% S:{s:.0f}% E:{e:.0f}% uB:{mb:.0f}"

        # Calculate text size
        font_scale = 0.55
        (text_w, text_h), _ = cv2.getTextSize(debug_text, self.font, font_scale, 1)

        # Position below the box
        padding = 2
        label_y1 = y2 + 2
        label_y2 = label_y1 + text_h + padding * 2
        text_y = label_y2 - padding

        # Draw background
        cv2.rectangle(
            image,
            (x1, label_y1),
            (x1 + text_w + padding * 2, label_y2),
            (60, 60, 60),
            -1,
        )

        # Draw text
        cv2.putText(
            image,
            debug_text,
            (x1 + padding, text_y),
            self.font,
            font_scale,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

    def create_summary_overlay(
        self,
        image: np.ndarray,
        present: int,
        missing: int,
        uncertain: int,
    ) -> np.ndarray:
        """Add a summary overlay to the image.

        Args:
            image: Image to add overlay to
            present: Number of present tools
            missing: Number of missing tools
            uncertain: Number of uncertain tools

        Returns:
            Image with summary overlay
        """
        annotated = image.copy()
        h, w = annotated.shape[:2]

        # Create semi-transparent overlay box
        overlay_h = 80
        overlay = annotated[h - overlay_h:h, :].copy()
        cv2.rectangle(overlay, (0, 0), (w, overlay_h), (40, 40, 40), -1)
        cv2.addWeighted(overlay, 0.7, annotated[h - overlay_h:h, :], 0.3, 0, annotated[h - overlay_h:h, :])

        # Draw summary text
        total = present + missing + uncertain
        y_pos = h - overlay_h + 30

        # Status text
        if missing == 0 and uncertain == 0:
            status_text = "COMPLETE"
            status_color = self.COLORS[ToolStatus.PRESENT]
        else:
            status_text = "INCOMPLETE"
            status_color = self.COLORS[ToolStatus.MISSING]

        cv2.putText(
            annotated, status_text,
            (20, y_pos), self.font, 0.8, status_color, 2, cv2.LINE_AA
        )

        # Counts
        counts_text = f"Present: {present}  |  Missing: {missing}  |  Uncertain: {uncertain}  |  Total: {total}"
        cv2.putText(
            annotated, counts_text,
            (20, y_pos + 35), self.font, 0.5, (200, 200, 200), 1, cv2.LINE_AA
        )

        return annotated
