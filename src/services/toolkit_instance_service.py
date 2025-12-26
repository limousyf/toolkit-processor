import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from ..core.config import settings
from ..core.models import (
    Toolkit,
    ToolkitStatus,
    ToolState,
    ToolStatus,
    CreateToolkitRequest,
    CheckInRecord,
    CheckInSummary,
    ToolCheckInResult,
    CheckInResponse,
    ToolkitConfig,
    ToolDefinition,
    ROI,
)
from .template_service import template_service
from ..cv.processor import ToolkitProcessor
from ..utils.image_utils import encode_image_base64, create_thumbnail


class ToolkitInstanceService:
    """Service for managing toolkit instances and check-ins."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or settings.toolkit_config_dir / "toolkits"
        self.checkins_dir = settings.toolkit_config_dir / "checkins"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.checkins_dir.mkdir(parents=True, exist_ok=True)
        self.processor = ToolkitProcessor()

    def _get_toolkit_path(self, toolkit_id: str) -> Path:
        return self.data_dir / f"{toolkit_id}.json"

    def _get_checkin_path(self, checkin_id: str) -> Path:
        return self.checkins_dir / f"{checkin_id}.json"

    # ==================== TOOLKIT CRUD ====================

    def list_toolkits(self) -> list[Toolkit]:
        """List all toolkit instances."""
        toolkits = []
        for toolkit_file in self.data_dir.glob("*.json"):
            try:
                toolkit = self.get_toolkit(toolkit_file.stem)
                if toolkit:
                    toolkits.append(toolkit)
            except Exception:
                continue
        return sorted(toolkits, key=lambda t: t.name)

    def get_toolkit(self, toolkit_id: str) -> Optional[Toolkit]:
        """Get a specific toolkit by ID."""
        toolkit_path = self._get_toolkit_path(toolkit_id)
        if not toolkit_path.exists():
            return None

        with open(toolkit_path, "r") as f:
            data = json.load(f)
            return Toolkit(**data)

    def create_toolkit(self, request: CreateToolkitRequest) -> Toolkit:
        """Create a new toolkit instance."""
        # Validate template exists
        template = template_service.get_template(request.template_id)
        if not template:
            raise ValueError(f"Template '{request.template_id}' not found")

        # Check toolkit ID doesn't exist
        toolkit_path = self._get_toolkit_path(request.toolkit_id)
        if toolkit_path.exists():
            raise ValueError(f"Toolkit '{request.toolkit_id}' already exists")

        # Initialize tool states from template
        tool_states = [
            ToolState(
                tool_id=tool.tool_id,
                name=tool.name,
                status=ToolStatus.UNKNOWN,
                confidence=0.0,
            )
            for tool in template.tools
        ]

        now = datetime.utcnow()
        toolkit = Toolkit(
            toolkit_id=request.toolkit_id,
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            location=request.location,
            status=ToolkitStatus.NEVER_CHECKED,
            tool_states=tool_states,
            created_at=now,
            updated_at=now,
        )

        self._save_toolkit(toolkit)
        return toolkit

    def update_toolkit(self, toolkit: Toolkit) -> Toolkit:
        """Update a toolkit instance."""
        toolkit_path = self._get_toolkit_path(toolkit.toolkit_id)
        if not toolkit_path.exists():
            raise ValueError(f"Toolkit '{toolkit.toolkit_id}' not found")

        toolkit.updated_at = datetime.utcnow()
        self._save_toolkit(toolkit)
        return toolkit

    def delete_toolkit(self, toolkit_id: str) -> bool:
        """Delete a toolkit instance."""
        toolkit_path = self._get_toolkit_path(toolkit_id)
        if not toolkit_path.exists():
            return False

        toolkit_path.unlink()
        return True

    def _save_toolkit(self, toolkit: Toolkit) -> Path:
        """Save toolkit to disk."""
        toolkit_path = self._get_toolkit_path(toolkit.toolkit_id)
        with open(toolkit_path, "w") as f:
            json.dump(toolkit.model_dump(mode="json"), f, indent=2, default=str)
        return toolkit_path

    # ==================== CHECK-IN ====================

    def check_in(
        self,
        toolkit_id: str,
        image: np.ndarray,
        notes: Optional[str] = None,
        checked_in_by: Optional[str] = None,
    ) -> CheckInResponse:
        """Perform a check-in for a toolkit."""
        # Get toolkit and template
        toolkit = self.get_toolkit(toolkit_id)
        if not toolkit:
            raise ValueError(f"Toolkit '{toolkit_id}' not found")

        template = template_service.get_template(toolkit.template_id)
        if not template:
            raise ValueError(f"Template '{toolkit.template_id}' not found")

        # Get check-in image dimensions (OpenCV: height, width, channels)
        img_height, img_width = image.shape[:2]

        # Scale ROIs if template has stored dimensions and they differ from check-in image
        tools_to_use = template.tools
        if template.image_width and template.image_height:
            scale_x = img_width / template.image_width
            scale_y = img_height / template.image_height

            # Only scale if dimensions differ significantly (more than 1% difference)
            if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
                scaled_tools = []
                for tool in template.tools:
                    scaled_roi = ROI(
                        x=int(tool.roi.x * scale_x),
                        y=int(tool.roi.y * scale_y),
                        width=int(tool.roi.width * scale_x),
                        height=int(tool.roi.height * scale_y),
                    )
                    scaled_tool = ToolDefinition(
                        tool_id=tool.tool_id,
                        name=tool.name,
                        slot_index=tool.slot_index,
                        roi=scaled_roi,
                        description=tool.description,
                    )
                    scaled_tools.append(scaled_tool)
                tools_to_use = scaled_tools

        # Convert template to legacy ToolkitConfig for CV processing
        toolkit_config = ToolkitConfig(
            toolkit_id=template.template_id,
            name=template.name,
            description=template.description,
            foam_color=template.foam_color,
            tools=tools_to_use,
            brightness_threshold=template.brightness_threshold,
            occupied_ratio_threshold=template.occupied_ratio_threshold,
        )

        # Run CV analysis (debug enabled to diagnose detection issues)
        analysis = self.processor.analyze(
            image=image,
            toolkit_config=toolkit_config,
            include_annotated_image=True,
            include_debug_info=True,
        )

        # Convert results (include debug info for diagnostics)
        tool_results = [
            ToolCheckInResult(
                tool_id=r.tool_id,
                name=r.name,
                status=r.status,
                confidence=r.confidence,
                debug_info=r.debug_info,
            )
            for r in analysis.tools
        ]

        summary = CheckInSummary(
            total_tools=analysis.summary.total_tools,
            present=analysis.summary.present,
            missing=analysis.summary.missing,
            uncertain=analysis.summary.uncertain,
        )

        # Determine toolkit status
        if summary.missing > 0:
            new_status = ToolkitStatus.INCOMPLETE
        elif summary.uncertain > 0:
            new_status = ToolkitStatus.INCOMPLETE
        else:
            new_status = ToolkitStatus.CHECKED_IN

        # Update toolkit state
        now = datetime.utcnow()
        toolkit.status = new_status
        toolkit.last_checkin = now
        toolkit.updated_at = now

        # Update tool states
        for result in tool_results:
            for tool_state in toolkit.tool_states:
                if tool_state.tool_id == result.tool_id:
                    tool_state.status = result.status
                    tool_state.confidence = result.confidence
                    if result.status == ToolStatus.PRESENT:
                        tool_state.last_seen = now
                    break

        self._save_toolkit(toolkit)

        # Create check-in record with thumbnail
        checkin_id = f"ci_{toolkit_id}_{now.strftime('%Y%m%d_%H%M%S')}"
        thumbnail = None
        if analysis.image_annotated:
            try:
                thumbnail = create_thumbnail(analysis.image_annotated, max_width=150)
            except Exception:
                pass  # Thumbnail is optional, continue without it

        checkin_record = CheckInRecord(
            checkin_id=checkin_id,
            toolkit_id=toolkit_id,
            template_id=toolkit.template_id,
            timestamp=now,
            status=new_status,
            tools=tool_results,
            summary=summary,
            checked_in_by=checked_in_by,
            notes=notes,
            thumbnail=thumbnail,
        )
        self._save_checkin(checkin_record)

        return CheckInResponse(
            checkin_id=checkin_id,
            toolkit_id=toolkit_id,
            toolkit_name=toolkit.name,
            template_name=template.name,
            timestamp=now,
            status=new_status,
            tools=tool_results,
            summary=summary,
            image_annotated=analysis.image_annotated,
        )

    def checkout(self, toolkit_id: str, location: Optional[str] = None) -> Toolkit:
        """Mark a toolkit as checked out."""
        toolkit = self.get_toolkit(toolkit_id)
        if not toolkit:
            raise ValueError(f"Toolkit '{toolkit_id}' not found")

        now = datetime.utcnow()
        toolkit.status = ToolkitStatus.CHECKED_OUT
        toolkit.last_checkout = now
        toolkit.updated_at = now
        if location:
            toolkit.location = location

        self._save_toolkit(toolkit)
        return toolkit

    def _save_checkin(self, record: CheckInRecord) -> Path:
        """Save check-in record to disk."""
        checkin_path = self._get_checkin_path(record.checkin_id)
        with open(checkin_path, "w") as f:
            json.dump(record.model_dump(mode="json"), f, indent=2, default=str)
        return checkin_path

    def get_checkin_history(self, toolkit_id: str, limit: int = 10) -> list[CheckInRecord]:
        """Get check-in history for a toolkit."""
        records = []
        for checkin_file in self.checkins_dir.glob(f"ci_{toolkit_id}_*.json"):
            try:
                with open(checkin_file, "r") as f:
                    data = json.load(f)
                    records.append(CheckInRecord(**data))
            except Exception:
                continue

        # Sort by timestamp descending
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]


# Singleton instance
toolkit_instance_service = ToolkitInstanceService()
