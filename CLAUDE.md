# Toolkit Processor

## Project Overview

A computer vision system for detecting tool presence/absence in industrial toolkits. Used for tracking tool usage and check-in/checkout workflows.

### Core Concept
- **Templates** define toolkit layouts with foam cutouts and ROIs for each tool slot
- **Toolkits** are physical instances tied to a template, each with a unique ID (e.g., "MKA-001")
- **Location is Identity**: A tool's identity is determined by its position in the toolkit, not by visual recognition
- **Detection Strategy**: Detect foam visibility (dark pixels = empty slot) vs tool presence (bright/metallic/colored pixels = occupied)

### Target Platforms (Phased Rollout)
1. **Phase 1**: Web application with still image upload (current focus)
2. **Phase 2**: Python script with webcam/video stream
3. **Phase 3**: iPhone app with video stream and AR overlay

## Architecture

```
toolkit-processor/
├── config/
│   └── toolkits/
│       ├── templates/     # Template JSON configurations
│       │   └── images/    # Template reference images (PNG)
│       ├── toolkits/      # Toolkit instance data
│       └── checkins/      # Check-in history records
├── img/                   # Sample and reference images
│   └── reference/         # Golden reference images per template
├── src/
│   ├── api/               # FastAPI routes
│   │   └── routes.py      # All API endpoints
│   ├── core/              # Config and Pydantic models
│   │   ├── config.py      # Settings and thresholds
│   │   └── models.py      # Data models (Template, Toolkit, CheckIn, etc.)
│   ├── cv/                # Computer vision pipeline
│   │   ├── processor.py   # Main orchestrator
│   │   ├── registration.py # Image alignment (ArUco/homography)
│   │   ├── detection.py   # Tool presence detection
│   │   └── visualization.py # Result rendering
│   ├── services/          # Business logic
│   │   ├── template_service.py        # Template CRUD
│   │   ├── toolkit_instance_service.py # Toolkit and check-in logic
│   │   └── toolkit_service.py         # Legacy CV service
│   └── utils/             # Helpers
├── static/                # Web UI assets
│   ├── index.html         # Multi-page SPA
│   ├── css/style.css      # Styles
│   └── js/app.js          # Frontend logic
└── tests/
```

## Data Model Hierarchy

### 1. Template (Blueprint)
Defines a type of toolkit layout:
- `template_id`: Unique identifier (e.g., "maintenance_kit")
- `name`: Human-readable name
- `foam_color`: Background foam color for detection
- `tools`: List of tool definitions with ROIs
- Detection thresholds (optional overrides)

### 2. Toolkit (Instance)
A physical toolkit tied to a template:
- `toolkit_id`: Unique identifier (e.g., "MKA-001")
- `template_id`: Which template it uses
- `status`: CHECKED_IN, CHECKED_OUT, INCOMPLETE, NEVER_CHECKED
- `tool_states`: Current status of each tool slot
- `location`: Current location/assignee
- Check-in/checkout timestamps

### 3. Check-In Record
Historical record of a check-in event:
- `checkin_id`: Unique ID with timestamp
- Snapshot of tool statuses and confidences
- Summary statistics (present/missing/uncertain)
- Optional notes and user attribution

## Web UI Pages

### Dashboard (`/`)
- Overview statistics: total toolkits, checked-in, checked-out, incomplete
- Table of all toolkits with status-aware actions:
  - "Check Out" for checked-in toolkits
  - "Check In" for checked-out or never-checked toolkits
  - "Re-verify" for incomplete toolkits
- Click-to-view details

### Templates (`templates`)
- List existing templates as cards
- Create/Edit templates in **full-screen editor**:
  - Upload reference image (persisted for later editing)
  - Add tools with ID and name
  - **Interactive ROI Drawing**: Select a tool, draw its bounding box on the canvas
  - Zoom controls for precision on high-res images
  - Visual feedback: tools with ROIs show in list
  - Edit existing templates with saved image loaded automatically

### Toolkits (`toolkits`)
- Table of all registered toolkits
- Register new toolkit:
  - Assign unique ID
  - Select template
  - Set name and location

### Toolkit Details (`details`)
- Current status with last check-in time
- Tool status list (present/missing/unknown with confidence)
- Check-in history
- Quick actions: Check-In, Check-Out, Delete

### Check-In (`checkin`)
- Select toolkit from dropdown
- Upload image
- View analysis results:
  - Status banner (Complete/Incomplete)
  - Tool breakdown by status
  - Annotated image with ROI overlays
  - "Done" button to return to dashboard

## API Endpoints

### Health
- `GET /api/health` - Health check

### Templates
- `GET /api/templates` - List all templates
- `GET /api/templates/{template_id}` - Get specific template
- `POST /api/templates` - Create new template
- `PUT /api/templates/{template_id}` - Update template
- `DELETE /api/templates/{template_id}` - Delete template
- `POST /api/templates/{template_id}/image` - Upload reference image
- `GET /api/templates/{template_id}/image` - Get reference image
- `GET /api/templates/{template_id}/has-image` - Check if image exists

### Toolkits
- `GET /api/toolkits` - List all toolkit instances
- `GET /api/toolkits/{toolkit_id}` - Get toolkit with its template
- `POST /api/toolkits` - Register new toolkit
- `PUT /api/toolkits/{toolkit_id}` - Update toolkit
- `DELETE /api/toolkits/{toolkit_id}` - Delete toolkit

### Check-In/Checkout
- `POST /api/toolkits/{toolkit_id}/checkin` - Check in with image (multipart form)
- `POST /api/toolkits/{toolkit_id}/checkout` - Mark as checked out
- `GET /api/toolkits/{toolkit_id}/history` - Get check-in history

### Dashboard
- `GET /api/dashboard/stats` - Dashboard statistics

### Legacy (Backwards Compatibility)
- `GET /api/legacy/toolkits` - Old-style toolkit list
- `POST /api/legacy/analyze` - Old-style analyze endpoint

## Technical Approach

### Detection Logic (Dark Foam)
Since foam is dark grey/black:
- **Empty slot**: ROI has low average brightness, uniform dark color
- **Occupied slot**: ROI has higher brightness, metallic reflections, or colored elements

### Key Thresholds (Tunable)
- `BRIGHTNESS_THRESHOLD`: Default 60 (0-255 scale) - pixels above this are "bright"
- `OCCUPIED_RATIO`: Default 0.3 - if >30% of ROI pixels are bright, slot is occupied
- `SATURATION_THRESHOLD`: Default 50 - detect colored tools (red handles)

### Confidence Calculation
Combines multiple factors:
- Brightness ratio (how much of ROI is bright vs dark)
- Edge density (tools have more edges than foam)
- Saturation presence (colored tool handles)

## Development

### Setup
```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### Running
```bash
# Development server (port 7001 to avoid conflicts)
uvicorn src.main:app --reload --port 7001

# Access web UI at http://localhost:7001
# API docs at http://localhost:7001/docs
```

### Testing
```bash
pytest tests/

# Helper scripts
python scripts/visualize_rois.py <template_id> [--scale 0.5]
python scripts/test_analysis.py <template_id> <image_path> [--debug]
```

## Configuration

### Environment Variables
- `TOOLKIT_CONFIG_DIR`: Path to config storage (default: `config/toolkits`)
- `REFERENCE_IMAGE_DIR`: Path to reference images (default: `img/reference`)
- `DEBUG`: Enable debug mode with visualization output

### Detection Parameters
Adjust in `src/core/config.py` or per-template in JSON config:
- `brightness_threshold`: Pixel brightness cutoff
- `occupied_ratio_threshold`: Ratio of bright pixels to consider slot occupied
- `saturation_threshold`: For detecting colored tools

## Conventions

### Code Style
- Python 3.10+
- Type hints on all functions
- Pydantic models for data validation
- OpenCV for image processing (cv2)
- FastAPI for web backend

### Naming
- Template IDs: `snake_case` (e.g., `maintenance_kit`)
- Toolkit IDs: Any format, typically `<prefix>-<number>` (e.g., `MKA-001`)
- Tool IDs: `snake_case` with descriptive names (e.g., `wrench_10mm`)
- ROI coordinates: Pixel-based, origin at top-left of image

### Git Commits
- Do not include AI attribution in commits
- Use conventional commit format when applicable

### UI Patterns
- **Toast Notifications**: Transient messages for success/error/warning feedback (bottom-right corner)
- **Loading Overlay**: Full-screen spinner for async operations
- **Modals**: Used for forms (tool editor, toolkit creation) with `.active` class toggle
- **Full-screen Pages**: Template editor uses full viewport for canvas drawing

## Future Considerations

### Phase 2 (Webcam)
- Real-time video stream processing
- Frame differencing for stability
- Continuous monitoring mode

### Phase 3 (iPhone)
- ArUco marker detection for perspective correction
- Homography transformation to flatten perspective
- AR overlay showing tool status in real-time
- Swift/SwiftUI with OpenCV or Vision framework

### Potential Enhancements
- ML-based patch classifier for difficult lighting conditions
- Tool condition assessment (damaged/worn detection)
- Usage analytics and reporting
- Integration with inventory management systems
