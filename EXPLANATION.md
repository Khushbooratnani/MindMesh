# MindMesh: Location-Aware & Radius Search Engine — Complete Technical Explanation

This document provides a comprehensive technical overview of all architecture, backend, frontend, networking, and version control implementations executed for the MindMesh project to enable intelligent, location-aware memory retrieval and radius search.

---

## Table of Contents
1. [Executive Summary & Core Objectives](#1-executive-summary--core-objectives)
2. [Backend Search Engine Architecture](#2-backend-search-engine-architecture)
   - [Haversine Distance Formulation](#haversine-distance-formulation)
   - [Database Query Execution & SQL Payload Extraction Fix](#database-query-execution--sql-payload-extraction-fix)
   - [Search Modes: Nearby, Hybrid, Graph, and Vector](#search-modes-nearby-hybrid-graph-and-vector)
   - [API Request & Response Contract](#api-request--response-contract)
3. [Mobile & Web Frontend Experience](#3-mobile--web-frontend-experience)
   - [Default Nearby Mode & Home Anchor](#default-nearby-mode--home-anchor)
   - [City Selection Bar](#city-selection-bar)
   - [Interactive Radius Selector & Live Querying](#interactive-radius-selector--live-querying)
   - [Custom Landmark Search](#custom-landmark-search)
   - ["Locate Me" Behavior & Geolocation Fault Tolerance](#locate-me-behavior--geolocation-fault-tolerance)
   - [Distance Badges & Visual Proximity Indicators](#distance-badges--visual-proximity-indicators)
4. [Production Web Server & Reverse Proxy](#4-production-web-server--reverse-proxy)
   - [Threaded Proxy Server Architecture (`web_proxy_server.py`)](#threaded-proxy-server-architecture-web_proxy_serverpy)
   - [CORS & Tunneling Configuration](#cors--tunneling-configuration)
5. [Git Repository & Version Control (`phase_2_3`)](#5-git-repository--version-control-phase_2_3)
6. [End-to-End System Workflow Diagram](#6-end-to-end-system-workflow-diagram)

---

## 1. Executive Summary & Core Objectives

MindMesh stores contextual, personal, and project memories with temporal, conceptual, and geographic metadata. The goal of this phase was to transform MindSeek from a pure semantic text search into a **location-aware discovery engine** that:
- Automatically anchors searches to user coordinates by default (**Dehradun**: `30.3165° N, 78.0322° E`).
- Provides rapid **Preset City switching** (Dehradun, Goa, Pune, Delhi, Mumbai, Bengaluru, Indiranagar).
- Allows dynamic **radius-based filtering** (`2 km`, `5 km`, `10 km`, `25 km`, `50 km`) with instant re-querying.
- Fixes GPS / browser location fallbacks so tapping **"Locate Me"** deterministically resets location and query state.
- Accurately renders distance badges (e.g., `📍 0.9 km`) on result cards.

---

## 2. Backend Search Engine Architecture

File location: `mindmesh/backend/phase1_text_to_json_ingestion/src/memory_search_service.py`

### Haversine Distance Formulation
To calculate real-world spherical surface distances between the search coordinates and stored memory locations, the backend applies the Haversine formula:

$$\Delta \text{lat} = \text{lat}_2 - \text{lat}_1$$
$$\Delta \text{lon} = \text{lon}_2 - \text{lon}_1$$
$$a = \sin^2\left(\frac{\Delta \text{lat}}{2}\right) + \cos(\text{lat}_1)\cos(\text{lat}_2)\sin^2\left(\frac{\Delta \text{lon}}{2}\right)$$
$$c = 2 \cdot \arctan2\left(\sqrt{a}, \sqrt{1 - a}\right)$$
$$d = R \cdot c \quad (R \approx 6371 \text{ km})$$

### Database Query Execution & SQL Payload Extraction Fix
Memories are stored in SQLite (`memories.db`). In `_nearby_search()`, an issue previously occurred where raw SQL selected `payload` without an alias, causing the model deserializer to fail parsing memory JSON payloads. 

This was resolved with explicit column aliasing:
```sql
SELECT 
    p.id, 
    p.user_id, 
    p.payload AS memory_json, 
    p.created_at, 
    p.updated_at
FROM memories p
```

Each memory payload is decoded; its `location.coordinates.latitude` and `location.coordinates.longitude` are parsed, Haversine distance is calculated, candidates with distance $> \text{radius\_km}$ are discarded, and the surviving candidates are sorted by proximity and relevance.

### Search Modes: Nearby, Hybrid, Graph, and Vector
1. **`nearby`**: Pure geographic spatial search. Scans memories within `radius_km` of the active coordinates, ranked by distance and query semantic alignment.
2. **`hybrid`**: Merges vector similarity (ChromaDB dense embeddings) + BM25 keyword matching + geographic radius pruning.
3. **`graph`**: Traverses knowledge graph entities, relationships, and nodes constrained to locations within the defined radius.
4. **`vector`**: Direct high-dimensional cosine similarity search across memory embeddings.

### API Request & Response Contract
Endpoint: `POST /api/memory/search`

#### Request Payload:
```json
{
  "query": "What did I do in Goa?",
  "top_k": 5,
  "content_weight": 0.5,
  "context_weight": 0.5,
  "generate_answer": true,
  "group_id": null,
  "latitude": 15.2993,
  "longitude": 74.1240,
  "radius_km": 10.0,
  "location_query": "Goa",
  "mode": "nearby"
}
```

#### Response Payload:
```json
{
  "query": "What did I do in Goa?",
  "answer": "You visited Curlies Beach Shack and attended a sunset session in Anjuna.",
  "grounded": true,
  "total_results": 2,
  "results": [
    {
      "id": "mem_01",
      "text": "Had dinner at Curlies Beach Shack in Anjuna.",
      "score": 0.94,
      "distance_km": 1.2,
      "location": {
        "place_name": "Curlies Beach Shack, Anjuna",
        "coordinates": { "latitude": 15.5732, "longitude": 73.7410 }
      }
    }
  ]
}
```

---

## 3. Mobile & Web Frontend Experience

File location: `mindmesh/mindmesh-mobile/src/screens/VaultScreen.tsx`

### Default Nearby Mode & Home Anchor
- On application boot, `searchScope` is set to `'nearby'`.
- Default city is set to `PRESET_CITIES[0]` (**Dehradun**, `30.3165, 78.0322`).
- Default search radius is set to **10 km**.
- Top right coordinates badge immediately reflects: `Dehradun (30.32°, 78.03°)`.

### City Selection Bar
Directly under the `[ 📍 Nearby ]` toggle, users can tap preset city chips:
- **Dehradun** (Default)
- **Goa**
- **Pune**
- **Delhi**
- **Mumbai**
- **Bengaluru**
- **Indiranagar**

Tapping any chip:
1. Updates `selectedCity`.
2. Updates the coordinates display.
3. If an existing query conversation exists, triggers `handleRerunQueryWithRadius()` to re-execute search against the new city.

### Interactive Radius Selector & Live Querying
- Quick radius chips: `2 km`, `5 km`, `10 km`, `25 km`, `50 km`.
- Increment / Decrement buttons (`+` / `-`) for fine-tuning.
- Adjusting the radius immediately re-queries the backend without requiring the user to re-enter text.

### Custom Landmark Search
An inline search bar inside the location panel allows searching custom landmarks within the active city context (e.g., *"Rajpur Road, Dehradun"* or *"Koregaon Park, Pune"*).

### "Locate Me" Behavior & Geolocation Fault Tolerance
#### The Problem:
Previously, clicking "Locate Me" invoked `navigator.geolocation.getCurrentPosition()`. In desktop browsers or localtunnel URLs where location permissions were blocked or timed out, the error callback fired but did nothing to reset the state. As a result, if the user had selected **Pune**, clicking "Locate Me" left the app stuck on Pune.

#### The Solution (`handleLocateMe`):
1. **Immediate State Shift**: Instantly sets `selectedCity` back to Dehradun (`PRESET_CITIES[0]`), resets scope to `'nearby'`, and re-triggers the active search query.
2. **Background Refinement**: Queries browser GPS with a 5-second timeout.
   - If GPS resolves: Checks if the user is within 80 km of a known city preset; if not, creates a custom `current_gps` option and updates search.
   - If GPS fails/denied: Gracefully keeps Dehradun active with no UI lockup.

### Distance Badges & Visual Proximity Indicators
In search results, cards feature distance badges rendered from `result.distance_km`:
- Proximity color coding (e.g. `#2D5A3D` theme green).
- Displayed as `📍 0.9 km`, giving immediate visual confirmation of physical proximity.

---

## 4. Production Web Server & Reverse Proxy

File location: `mindmesh/mindmesh-mobile/web_proxy_server.py`

### Threaded Proxy Server Architecture
To eliminate CORS issues, cookie problems, and routing friction between the static Expo web app (built via `npx expo export --platform web`) and the FastAPI backend, a unified multi-threaded server was created:
- Listens on port `3000`.
- **Static File Serving**: Serves the Expo web bundle (`dist/`) with SPA fallback to `index.html` for client-side navigation.
- **Reverse Proxy**: Intercepts `/api/*` and `/health` requests and streams them to FastAPI at `http://127.0.0.1:8002`.

### CORS & Tunneling Configuration
- Automatically injects permissive CORS headers:
  - `Access-Control-Allow-Origin: *`
  - `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS`
  - Handles `OPTIONS` preflight requests cleanly.
- Exposed via Localtunnel (`https://mean-eyes-drop.loca.lt`) for direct testing on mobile devices and remote browsers.

---

## 5. Git Repository & Version Control (`phase_2_3`)

Repository: `https://github.com/Khushbooratnani/MindMesh`  
Target Branch: `phase_2_3`  
Local Working Clone: `/home/coeai/mindmesh_copy/Major`

### Commit History Breakdown:
1. `c1f8734` - **feat(vault): add default location coordinates, nearby mode by default, city selection chips, and radius selector**
   - Configured Dehradun default coordinates and 10 km radius.
   - Built city selector chip bar and radius adjustment UI.
2. `db8a3ea` - **feat(search): add location-aware nearby search with Haversine distance ranking and distance badges**
   - Fixed SQL payload deserialization in `memory_search_service.py`.
   - Connected distance metrics to memory cards.
3. `1046a87` - **fix(locate-me): immediately shift selectedCity from Pune back to Dehradun on Locate Me click**
   - Implemented fail-safe `handleLocateMe` flow.
   - Ensured instant UI feedback and query re-execution.

---

## 6. End-to-End System Workflow Diagram

```
+-------------------------------------------------------------------------+
|                              USER INTERACTION                           |
|                                                                         |
|  [ Launch App ]           [ Select City Chip ]      [ Adjust Radius ]   |
|         │                          │                       │            |
|         ▼                          ▼                       ▼            |
|  Default: Dehradun           Change to Pune           Change to 25 km   |
|  (30.32°, 78.03°)          (18.52°, 73.86°)                 │           |
|  Scope: 'nearby'                   │                        │           |
|  Radius: 10 km                     │                        │           |
+─────────┬──────────────────────────┴────────────────────────┴───────────+
          │
          ▼
+-------------------------------------------------------------------------+
|                       FRONTEND: VaultScreen.tsx                         |
|                                                                         |
|  - Updates `selectedCity`, `radiusKm`, and top coordinates badge        |
|  - Calls `handleRerunQueryWithRadius()`                                 |
|  - Dispatches POST request to `/api/memory/search`                      |
+────────────────────────────────────┬────────────────────────────────────+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                  NETWORKING: web_proxy_server.py (Port 3000)            |
|                                                                         |
|  - Serves static Expo bundle from `dist/`                               |
|  - Reverse-proxies `/api/memory/search` to Backend (Port 8002)          |
|  - Adds CORS and preflight handling                                     |
+────────────────────────────────────┬────────────────────────────────────+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|             BACKEND: FastAPI + memory_search_service.py (Port 8002)     |
|                                                                         |
|  1. Parses coordinates (lat, lon) and `radius_km`                       |
|  2. Fetches memories from SQLite (`memories.db`)                        |
|  3. Runs Haversine calculation for each memory location                 |
|  4. Prunes candidates where distance > radius_km                        |
|  5. Sorts results by distance (ascending) + semantic score              |
|  6. Returns items with `distance_km` attached                           |
+────────────────────────────────────┬────────────────────────────────────+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
|                           RESULT PRESENTATION                           |
|                                                                         |
|  - Vault conversation displays memory answer                            |
|  - Memory result cards display visual distance badges: [ 📍 0.9 km ]    |
+-------------------------------------------------------------------------+
```
