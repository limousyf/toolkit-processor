from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ==================== COMMON ====================

class ROI(BaseModel):
    """Region of Interest defining a tool slot location."""
    x: int = Field(..., description="X coordinate of top-left corner (pixels)")
    y: int = Field(..., description="Y coordinate of top-left corner (pixels)")
    width: int = Field(..., description="Width of ROI (pixels)")
    height: int = Field(..., description="Height of ROI (pixels)")


class FoamColor(str, Enum):
    """Supported foam colors for detection optimization."""
    DARK_GREY = "dark_grey"
    BLACK = "black"
    YELLOW = "yellow"
    RED = "red"
    BLUE = "blue"


class ToolStatus(str, Enum):
    """Status of a tool in the toolkit."""
    PRESENT = "present"
    MISSING = "missing"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"  # Never checked in


class ToolkitStatus(str, Enum):
    """Status of a toolkit instance."""
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    INCOMPLETE = "incomplete"  # Checked in but missing tools
    NEVER_CHECKED = "never_checked"


# ==================== TEMPLATE ====================

class ToolDefinition(BaseModel):
    """Definition of a tool slot in a template."""
    tool_id: str = Field(..., description="Unique identifier for this tool within the template")
    name: str = Field(..., description="Human-readable tool name")
    slot_index: int = Field(0, description="Position index in the toolkit (auto-generated)")
    roi: ROI = Field(..., description="Region of interest for this tool slot")
    description: Optional[str] = Field(None, description="Additional tool description")


class ArucoMarkerBounds(BaseModel):
    """ArUco marker positions defining the toolkit content area."""
    top_left: tuple[float, float] = Field(..., description="Top-left marker center (x, y)")
    top_right: tuple[float, float] = Field(..., description="Top-right marker center (x, y)")
    bottom_right: tuple[float, float] = Field(..., description="Bottom-right marker center (x, y)")
    bottom_left: tuple[float, float] = Field(..., description="Bottom-left marker center (x, y)")

    @property
    def content_width(self) -> float:
        """Width of the toolkit content area."""
        return ((self.top_right[0] - self.top_left[0]) + (self.bottom_right[0] - self.bottom_left[0])) / 2

    @property
    def content_height(self) -> float:
        """Height of the toolkit content area."""
        return ((self.bottom_left[1] - self.top_left[1]) + (self.bottom_right[1] - self.top_right[1])) / 2


class ToolkitTemplate(BaseModel):
    """Template defining the layout and tools of a toolkit type."""
    template_id: str = Field(..., description="Unique identifier for this template")
    name: str = Field(..., description="Human-readable template name")
    description: Optional[str] = Field(None, description="Template description")
    foam_color: FoamColor = Field(FoamColor.DARK_GREY, description="Color of the foam")
    image_width: Optional[int] = Field(None, description="Reference image width in pixels")
    image_height: Optional[int] = Field(None, description="Reference image height in pixels")
    tools: list[ToolDefinition] = Field(default_factory=list, description="List of tool definitions")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # ArUco marker bounds (auto-detected from reference image)
    aruco_bounds: Optional[ArucoMarkerBounds] = Field(None, description="ArUco marker positions in reference image")

    # Detection thresholds (optional overrides)
    brightness_threshold: Optional[int] = Field(None, description="Override default brightness threshold")
    occupied_ratio_threshold: Optional[float] = Field(None, description="Override default occupied ratio")


class CreateTemplateRequest(BaseModel):
    """Request model for creating a new template."""
    template_id: str
    name: str
    description: Optional[str] = None
    foam_color: FoamColor = FoamColor.DARK_GREY
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    tools: list[ToolDefinition] = Field(default_factory=list)


# ==================== TOOLKIT INSTANCE ====================

class ToolState(BaseModel):
    """Current state of a tool in a toolkit instance."""
    tool_id: str
    name: str
    status: ToolStatus = ToolStatus.UNKNOWN
    confidence: float = 0.0
    last_seen: Optional[datetime] = None


class Toolkit(BaseModel):
    """A physical toolkit instance."""
    toolkit_id: str = Field(..., description="Unique identifier for this toolkit (e.g., 'MKA-001')")
    template_id: str = Field(..., description="ID of the template this toolkit uses")
    name: str = Field(..., description="Human-readable name (e.g., 'Maintenance Kit A - Unit 1')")
    description: Optional[str] = Field(None)
    status: ToolkitStatus = Field(ToolkitStatus.NEVER_CHECKED)
    location: Optional[str] = Field(None, description="Current location or assignee")
    tool_states: list[ToolState] = Field(default_factory=list, description="Current state of each tool")
    last_checkin: Optional[datetime] = Field(None)
    last_checkout: Optional[datetime] = Field(None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CreateToolkitRequest(BaseModel):
    """Request model for creating a new toolkit instance."""
    toolkit_id: str = Field(..., description="Unique ID for this toolkit")
    template_id: str = Field(..., description="Template to base this toolkit on")
    name: str = Field(..., description="Display name")
    description: Optional[str] = None
    location: Optional[str] = None


# ==================== REGISTRATION ====================

class RegistrationInfo(BaseModel):
    """Registration metadata for check-in records."""
    markers_detected: int = Field(..., description="Number of ArUco markers detected")
    markers_expected: int = Field(4, description="Number of markers expected")
    homography_applied: bool = Field(..., description="Whether perspective correction was applied")
    fallback_reason: Optional[str] = Field(None, description="Reason if fallback to raw image was used")


# ==================== CHECK-IN ====================

class ToolCheckInResult(BaseModel):
    """Result of checking a single tool during check-in."""
    tool_id: str
    name: str
    status: ToolStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    debug_info: Optional[dict] = None


class CheckInSummary(BaseModel):
    """Summary statistics for a check-in."""
    total_tools: int
    present: int
    missing: int
    uncertain: int

    @property
    def is_complete(self) -> bool:
        return self.missing == 0 and self.uncertain == 0


class CheckInRecord(BaseModel):
    """Record of a toolkit check-in event."""
    checkin_id: str = Field(..., description="Unique ID for this check-in")
    toolkit_id: str
    template_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: ToolkitStatus
    tools: list[ToolCheckInResult] = Field(default_factory=list)
    summary: CheckInSummary
    registration: Optional[RegistrationInfo] = Field(None, description="ArUco registration info")
    checked_in_by: Optional[str] = Field(None, description="User who performed check-in")
    notes: Optional[str] = None
    thumbnail: Optional[str] = Field(None, description="Base64 data URL of thumbnail image")


class CheckInRequest(BaseModel):
    """Request model for check-in endpoint."""
    toolkit_id: str = Field(..., description="ID of toolkit to check in")
    notes: Optional[str] = None
    checked_in_by: Optional[str] = None


class CheckInResponse(BaseModel):
    """Response from check-in endpoint."""
    checkin_id: str
    toolkit_id: str
    toolkit_name: str
    template_name: str
    timestamp: datetime
    status: ToolkitStatus
    tools: list[ToolCheckInResult]
    summary: CheckInSummary
    registration: Optional[RegistrationInfo] = Field(None, description="ArUco registration info")
    image_annotated: Optional[str] = Field(None, description="Base64 encoded annotated image")


# ==================== LEGACY COMPATIBILITY ====================
# These maintain backwards compatibility with existing code

class ToolConfig(ToolDefinition):
    """Alias for backwards compatibility."""
    pass


class ToolkitConfig(BaseModel):
    """Legacy model - maps to template for CV processing."""
    toolkit_id: str
    name: str
    description: Optional[str] = None
    foam_color: FoamColor = FoamColor.DARK_GREY
    tools: list[ToolDefinition] = Field(default_factory=list)
    brightness_threshold: Optional[int] = None
    occupied_ratio_threshold: Optional[float] = None


class ToolAnalysisResult(ToolCheckInResult):
    """Alias for backwards compatibility."""
    slot_index: int = 0


class AnalysisSummary(CheckInSummary):
    """Alias for backwards compatibility."""
    pass


class AnalysisResult(BaseModel):
    """Legacy analysis result model."""
    toolkit_id: str
    toolkit_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str
    tools: list[ToolAnalysisResult] = Field(default_factory=list)
    summary: AnalysisSummary
    registration: Optional[RegistrationInfo] = None
    image_annotated: Optional[str] = None
    error: Optional[str] = None
