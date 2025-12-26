# Toolkit Processor

A computer vision system for detecting tool presence/absence in industrial toolkits. Used for tracking tool usage, check-in/checkout workflows, and ensuring toolkit completeness.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-red.svg)

## Features

- **Template-based toolkit management**: Define toolkit layouts with foam cutouts and tool positions
- **Visual tool detection**: CV-based detection using brightness, saturation, and edge analysis
- **Check-in/checkout workflow**: Track toolkit status and tool presence over time
- **Interactive ROI editor**: Full-screen canvas editor for defining tool regions
- **Image scaling**: Automatic ROI scaling for different image resolutions
- **Web-based UI**: Modern single-page application for all operations
- **REST API**: Full API with OpenAPI documentation

## How It Works

### Core Concept

1. **Templates** define toolkit layouts - the foam cutouts and expected tool positions (ROIs)
2. **Toolkits** are physical instances of a template, each with a unique ID
3. **Location is Identity**: A tool's identity is determined by its position in the toolkit, not visual recognition
4. **Detection Strategy**: Detect foam visibility (dark = empty slot) vs tool presence (bright/metallic = occupied)

### Detection Algorithm

The system analyzes each Region of Interest (ROI) using three signals:

| Signal | Weight | Description |
|--------|--------|-------------|
| Brightness | 50% | Ratio of bright pixels (metallic tools reflect light) |
| Saturation | 30% | Colored pixels (tool handles - red, orange, etc.) |
| Edges | 20% | Edge density (tools have distinct shapes) |

**Decision thresholds:**
- Combined score ≥ 0.7 → Tool **PRESENT**
- Combined score ≤ 0.3 → Tool **MISSING**
- Between → **UNCERTAIN**

## Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/limousyf/toolkit-processor.git
cd toolkit-processor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Running the Server

```bash
# Start the development server
uvicorn src.main:app --reload --port 7001

# Access the web UI at http://localhost:7001
# API documentation at http://localhost:7001/docs
```

### Workflow

1. **Create a Template**
   - Navigate to Templates page
   - Upload a reference image of your toolkit
   - Add tools and draw ROI boxes for each tool slot
   - Save the template

2. **Register a Toolkit**
   - Navigate to Toolkits page
   - Click "Register Toolkit"
   - Select a template, give it a unique ID and name

3. **Check In a Toolkit**
   - Take a photo of the physical toolkit
   - Navigate to Check-In page
   - Select the toolkit and upload the image
   - View the analysis results

4. **Monitor Status**
   - Dashboard shows overview of all toolkits
   - View detailed status and history for each toolkit

## Project Structure

```
toolkit-processor/
├── config/
│   └── toolkits/
│       ├── templates/        # Template JSON configs
│       │   └── images/       # Template reference images
│       ├── toolkits/         # Toolkit instance data
│       └── checkins/         # Check-in history records
├── src/
│   ├── api/
│   │   └── routes.py         # FastAPI endpoints
│   ├── core/
│   │   ├── config.py         # Settings and thresholds
│   │   └── models.py         # Pydantic data models
│   ├── cv/
│   │   ├── processor.py      # Main CV orchestrator
│   │   ├── detection.py      # Tool presence detection
│   │   └── visualization.py  # Result annotation
│   ├── services/
│   │   ├── template_service.py
│   │   └── toolkit_instance_service.py
│   └── utils/
│       └── image_utils.py
├── static/
│   ├── index.html            # Web UI
│   ├── css/style.css
│   └── js/app.js
├── tests/
├── requirements.txt
└── README.md
```

## API Reference

### Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/templates` | List all templates |
| GET | `/api/templates/{id}` | Get specific template |
| POST | `/api/templates` | Create new template |
| PUT | `/api/templates/{id}` | Update template |
| DELETE | `/api/templates/{id}` | Delete template |
| POST | `/api/templates/{id}/image` | Upload reference image |
| GET | `/api/templates/{id}/image` | Get reference image |

### Toolkits

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/toolkits` | List all toolkits |
| GET | `/api/toolkits/{id}` | Get specific toolkit |
| POST | `/api/toolkits` | Register new toolkit |
| PUT | `/api/toolkits/{id}` | Update toolkit |
| DELETE | `/api/toolkits/{id}` | Delete toolkit |

### Check-in/Checkout

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/toolkits/{id}/checkin` | Check in with image |
| POST | `/api/toolkits/{id}/checkout` | Mark as checked out |
| GET | `/api/toolkits/{id}/history` | Get check-in history |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/stats` | Get dashboard statistics |
| GET | `/api/health` | Health check |

## Configuration

### Detection Parameters

Adjust in `src/core/config.py` or per-template:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `brightness_threshold` | 60 | Pixels above this are "bright" (0-255) |
| `occupied_ratio_threshold` | 0.25 | Ratio of bright pixels = occupied |
| `saturation_threshold` | 40 | Minimum saturation for colored tools |
| `color_ratio_threshold` | 0.15 | Ratio of colored pixels |
| `edge_density_threshold` | 0.05 | Edge pixel ratio |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TOOLKIT_CONFIG_DIR` | Path to config storage |
| `TOOLKIT_DEBUG` | Enable debug mode |

## Tips for Best Results

1. **Consistent lighting**: Take check-in photos under similar lighting conditions as the reference image
2. **Same angle**: Position the camera at the same angle as when creating the template
3. **Dark foam**: The system works best with dark grey or black foam backgrounds
4. **Clear contrast**: Ensure tools contrast well against the foam (metallic or colored handles)
5. **Stable positioning**: Keep the toolkit in the same orientation for each check-in

## Development

### Running Tests

```bash
pytest tests/
```

### Helper Scripts

```bash
# Visualize ROIs on a template
python scripts/visualize_rois.py <template_id> [--scale 0.5]

# Test analysis on an image
python scripts/test_analysis.py <template_id> <image_path> [--debug]
```

## Roadmap

- [ ] Webcam/video stream support for real-time monitoring
- [ ] ArUco marker detection for automatic perspective correction
- [ ] Mobile app with AR overlay
- [ ] ML-based detection for challenging lighting conditions
- [ ] Tool condition assessment (wear/damage detection)
- [ ] Integration with inventory management systems

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
