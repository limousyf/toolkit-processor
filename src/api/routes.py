from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..core.models import (
    ToolkitTemplate,
    CreateTemplateRequest,
    Toolkit,
    CreateToolkitRequest,
    ToolkitStatus,
    CheckInResponse,
    CheckInRecord,
)
from ..services.template_service import template_service
from ..services.toolkit_instance_service import toolkit_instance_service
from ..utils.image_utils import load_image

router = APIRouter(prefix="/api", tags=["api"])


# ==================== HEALTH ====================

class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="1.0.0")


# ==================== TEMPLATES ====================

class TemplateListResponse(BaseModel):
    templates: list[ToolkitTemplate]
    count: int


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates():
    """List all toolkit templates."""
    templates = template_service.list_templates()
    return TemplateListResponse(templates=templates, count=len(templates))


@router.get("/templates/{template_id}", response_model=ToolkitTemplate)
async def get_template(template_id: str):
    """Get a specific template."""
    template = template_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return template


@router.post("/templates", response_model=ToolkitTemplate, status_code=201)
async def create_template(request: CreateTemplateRequest):
    """Create a new toolkit template."""
    try:
        template = template_service.create_template(request)
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/templates/{template_id}", response_model=ToolkitTemplate)
async def update_template(template_id: str, template: ToolkitTemplate):
    """Update an existing template."""
    if template_id != template.template_id:
        raise HTTPException(status_code=400, detail="template_id in URL must match template_id in body")
    try:
        updated = template_service.update_template(template)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template."""
    deleted = template_service.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return {"message": f"Template '{template_id}' deleted"}


@router.post("/templates/{template_id}/image")
async def upload_template_image(
    template_id: str,
    file: UploadFile = File(..., description="Reference image for the template"),
):
    """Upload or update a template's reference image."""
    template = template_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        contents = await file.read()
        template_service.save_image(template_id, contents)
        return {"message": "Image uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")


@router.get("/templates/{template_id}/image")
async def get_template_image(template_id: str):
    """Get a template's reference image."""
    image_path = template_service.get_image_path(template_id)
    if not image_path:
        raise HTTPException(status_code=404, detail=f"No image found for template '{template_id}'")

    return FileResponse(image_path, media_type="image/png")


@router.get("/templates/{template_id}/has-image")
async def check_template_image(template_id: str):
    """Check if a template has a reference image."""
    return {"has_image": template_service.has_image(template_id)}


@router.get("/templates/{template_id}/aruco-markers")
async def detect_template_aruco_markers(template_id: str):
    """Detect ArUco markers in a template's reference image."""
    from ..cv.registration import ToolkitRegistration
    from ..core.config import settings

    image_path = template_service.get_image_path(template_id)
    if not image_path:
        raise HTTPException(status_code=404, detail=f"No image found for template '{template_id}'")

    try:
        image = load_image(str(image_path))
        registration = ToolkitRegistration(
            dictionary=settings.aruco_dictionary,
            marker_ids=settings.aruco_marker_ids,
            canonical_size=(settings.aruco_canonical_width, settings.aruco_canonical_height),
        )
        markers = registration.detect_markers(image)

        return {
            "detected": markers.count > 0,
            "count": markers.count,
            "markers": [
                {
                    "id": marker_id,
                    "center": {"x": center[0], "y": center[1]},
                    "corners": corners.tolist() if marker_id in markers.corners else None
                }
                for marker_id, center in markers.centers.items()
                for corners in [markers.corners.get(marker_id)]
            ],
            "all_found": markers.all_found,
            "canonical_size": {
                "width": settings.aruco_canonical_width,
                "height": settings.aruco_canonical_height
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect markers: {e}")


# ==================== TOOLKITS ====================

class ToolkitListResponse(BaseModel):
    toolkits: list[Toolkit]
    count: int


class ToolkitWithTemplate(BaseModel):
    toolkit: Toolkit
    template: Optional[ToolkitTemplate] = None


@router.get("/toolkits", response_model=ToolkitListResponse)
async def list_toolkits():
    """List all toolkit instances."""
    toolkits = toolkit_instance_service.list_toolkits()
    return ToolkitListResponse(toolkits=toolkits, count=len(toolkits))


@router.get("/toolkits/{toolkit_id}", response_model=ToolkitWithTemplate)
async def get_toolkit(toolkit_id: str):
    """Get a specific toolkit with its template."""
    toolkit = toolkit_instance_service.get_toolkit(toolkit_id)
    if not toolkit:
        raise HTTPException(status_code=404, detail=f"Toolkit '{toolkit_id}' not found")

    template = template_service.get_template(toolkit.template_id)
    return ToolkitWithTemplate(toolkit=toolkit, template=template)


@router.post("/toolkits", response_model=Toolkit, status_code=201)
async def create_toolkit(request: CreateToolkitRequest):
    """Create a new toolkit instance."""
    try:
        toolkit = toolkit_instance_service.create_toolkit(request)
        return toolkit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/toolkits/{toolkit_id}", response_model=Toolkit)
async def update_toolkit(toolkit_id: str, toolkit: Toolkit):
    """Update a toolkit instance."""
    if toolkit_id != toolkit.toolkit_id:
        raise HTTPException(status_code=400, detail="toolkit_id in URL must match toolkit_id in body")
    try:
        updated = toolkit_instance_service.update_toolkit(toolkit)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/toolkits/{toolkit_id}")
async def delete_toolkit(toolkit_id: str):
    """Delete a toolkit instance."""
    deleted = toolkit_instance_service.delete_toolkit(toolkit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Toolkit '{toolkit_id}' not found")
    return {"message": f"Toolkit '{toolkit_id}' deleted"}


# ==================== CHECK-IN / CHECK-OUT ====================

@router.post("/toolkits/{toolkit_id}/checkin", response_model=CheckInResponse)
async def checkin_toolkit(
    toolkit_id: str,
    file: UploadFile = File(..., description="Image file of the toolkit"),
    notes: Optional[str] = Form(None),
    checked_in_by: Optional[str] = Form(None),
):
    """Check in a toolkit by analyzing an uploaded image."""
    # Validate toolkit exists
    toolkit = toolkit_instance_service.get_toolkit(toolkit_id)
    if not toolkit:
        raise HTTPException(status_code=404, detail=f"Toolkit '{toolkit_id}' not found")

    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        contents = await file.read()
        image = load_image(contents)

        result = toolkit_instance_service.check_in(
            toolkit_id=toolkit_id,
            image=image,
            notes=notes,
            checked_in_by=checked_in_by,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Check-in failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Check-in failed: {e}")


@router.post("/toolkits/{toolkit_id}/checkout", response_model=Toolkit)
async def checkout_toolkit(
    toolkit_id: str,
    location: Optional[str] = Form(None),
):
    """Mark a toolkit as checked out."""
    try:
        toolkit = toolkit_instance_service.checkout(toolkit_id, location)
        return toolkit
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/toolkits/{toolkit_id}/history", response_model=list[CheckInRecord])
async def get_checkin_history(toolkit_id: str, limit: int = 10):
    """Get check-in history for a toolkit."""
    toolkit = toolkit_instance_service.get_toolkit(toolkit_id)
    if not toolkit:
        raise HTTPException(status_code=404, detail=f"Toolkit '{toolkit_id}' not found")

    history = toolkit_instance_service.get_checkin_history(toolkit_id, limit)
    return history


# ==================== DASHBOARD STATS ====================

class DashboardStats(BaseModel):
    total_toolkits: int
    checked_in: int
    checked_out: int
    incomplete: int
    never_checked: int
    total_templates: int


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get dashboard statistics."""
    toolkits = toolkit_instance_service.list_toolkits()
    templates = template_service.list_templates()

    stats = DashboardStats(
        total_toolkits=len(toolkits),
        checked_in=sum(1 for t in toolkits if t.status == ToolkitStatus.CHECKED_IN),
        checked_out=sum(1 for t in toolkits if t.status == ToolkitStatus.CHECKED_OUT),
        incomplete=sum(1 for t in toolkits if t.status == ToolkitStatus.INCOMPLETE),
        never_checked=sum(1 for t in toolkits if t.status == ToolkitStatus.NEVER_CHECKED),
        total_templates=len(templates),
    )

    return stats


# ==================== LEGACY COMPATIBILITY ====================
# These endpoints maintain backwards compatibility with the old API

from ..core.models import ToolkitConfig, AnalysisResult, AnalysisSummary, ToolAnalysisResult
from ..services.toolkit_service import toolkit_service


@router.get("/legacy/toolkits")
async def legacy_list_toolkits():
    """Legacy endpoint - list toolkit configs (now templates)."""
    templates = template_service.list_templates()
    # Convert to legacy format
    configs = [
        {
            "toolkit_id": t.template_id,
            "name": t.name,
            "description": t.description,
            "foam_color": t.foam_color,
            "tools": [tool.model_dump() for tool in t.tools],
        }
        for t in templates
    ]
    return {"toolkits": configs, "count": len(configs)}


@router.post("/legacy/analyze")
async def legacy_analyze(
    file: UploadFile = File(...),
    toolkit_id: str = Form(...),
    include_debug: bool = Form(False),
):
    """Legacy endpoint - analyze image against a template."""
    # This endpoint treats toolkit_id as template_id for backwards compatibility
    template = template_service.get_template(toolkit_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{toolkit_id}' not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        from ..cv.processor import ToolkitProcessor

        contents = await file.read()
        image = load_image(contents)

        toolkit_config = ToolkitConfig(
            toolkit_id=template.template_id,
            name=template.name,
            description=template.description,
            foam_color=template.foam_color,
            tools=template.tools,
            brightness_threshold=template.brightness_threshold,
            occupied_ratio_threshold=template.occupied_ratio_threshold,
        )

        processor = ToolkitProcessor()
        result = processor.analyze(
            image=image,
            toolkit_config=toolkit_config,
            include_annotated_image=True,
            include_debug_info=include_debug,
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
