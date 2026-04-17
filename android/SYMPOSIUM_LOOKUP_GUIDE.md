# CrisisCloud Symposium Lookup Guide

Use your editor's search feature with the `LOOKUP:` tag below to jump straight to the code you want to present. The headers are grouped by demo topic so you can move through the project in a clean order during a symposium or live walkthrough.

## Backend Lookups

- `LOOKUP: BACKEND-SETUP`
  - Flask startup, environment loading, shared constants

- `LOOKUP: BACKEND-SUPABASE-CONNECTION`
  - How the backend connects to the shared Supabase database and serves local icons

- `LOOKUP: BACKEND-RESOURCE-DATA`
  - High-level explanation of the shared database as the single source of truth

- `LOOKUP: BACKEND-RESOURCE-SERIALIZE`
  - Database connection helper, row normalization, resource fetch logic

- `LOOKUP: BACKEND-RESOURCE-METADATA`
  - How different building types track different capacity fields

- `LOOKUP: BACKEND-DATABASE-SETUP`
  - Postgres table creation and startup database validation

- `LOOKUP: BACKEND-RESOURCE-UPDATES`
  - How the backend applies status, phone, and availability changes

- `LOOKUP: BACKEND-WEATHER-FORECAST`
  - Weekly forecast extraction from the National Weather Service

- `LOOKUP: BACKEND-NWS-REQUEST`
  - Shared helper for all NWS API calls

- `LOOKUP: BACKEND-PAGE-ROUTES`
  - Main page route and favicon route

- `LOOKUP: BACKEND-RESOURCE-API`
  - `GET /api/resources` and `POST /api/resources/<resource_id>`

- `LOOKUP: BACKEND-WEATHER-API`
  - Live weather, alerts, and forecast endpoint

- `LOOKUP: BACKEND-REPORTS-API`
  - `GET /api/reports` and `POST /api/reports` for the live field dashboard

- `LOOKUP: BACKEND-AUTH`
  - Login, logout, session validation, and user registration endpoints

- `LOOKUP: BACKEND-APP-START`
  - App startup entry point and local development server

## Frontend Lookups

- `LOOKUP: FRONTEND-STYLES-THEME`
  - Dark mode/light mode color system

- `LOOKUP: FRONTEND-STYLES-TOGGLE`
  - Theme toggle and accessibility toggle styling

- `LOOKUP: FRONTEND-STYLES-LAYOUT`
  - Main page layout, cards, spacing, header, and responsive structure

- `LOOKUP: FRONTEND-STYLES-MAP-MARKERS`
  - Marker icon styles and status-ring visuals

- `LOOKUP: FRONTEND-STYLES-DATA-PANELS`
  - Forecast cards, insurance cards, recovery cards, and directory cards

- `LOOKUP: FRONTEND-HEADER`
  - Branded top header and top-level controls

- `LOOKUP: FRONTEND-PUBLIC-DASHBOARD`
  - Public-facing dashboard, map, weather, and resource summary area

- `LOOKUP: FRONTEND-REPORT-FEED`
  - Left-side live dashboard feed for the newest field reports

- `LOOKUP: FRONTEND-HELP-RESOURCES`
  - Insurance, FEMA, Red Cross, outage, and recovery resource links

- `LOOKUP: FRONTEND-ORG-SIDEBAR`
  - Right-hand sidebar with login, filters, and directories

- `LOOKUP: FRONTEND-FILTER-PANEL`
  - Resource filter panel for combining visible categories

- `LOOKUP: FRONTEND-REPORT-FORM`
  - Sidebar form for submitting live field reports

- `LOOKUP: FRONTEND-LOGIN-MODAL`
  - Organization login modal UI

- `LOOKUP: FRONTEND-STATE`
  - Shared frontend state, DOM references, and app-level variables

- `LOOKUP: FRONTEND-THEME-LOGIC`
  - Theme switching and map tile behavior

- `LOOKUP: FRONTEND-MAP-LAYERS`
  - Leaflet layer groups for resources and incidents

- `LOOKUP: FRONTEND-RESOURCE-HELPERS`
  - Icon selection, filter logic, and summary helpers

- `LOOKUP: FRONTEND-MAP-RENDER`
  - Marker rendering and popup creation

- `LOOKUP: FRONTEND-SIDEBAR-DIRECTORIES`
  - Directory rendering, city-filtered login list, and browse/update mode switching

- `LOOKUP: FRONTEND-MAP-FOCUS`
  - Click-to-map behavior and scroll-to-center logic

- `LOOKUP: FRONTEND-ORG-CONTROLS`
  - Organization edit controls for status, phone, and counts

- `LOOKUP: FRONTEND-RESOURCE-FETCH`
  - Background polling and frontend refresh from the backend

- `LOOKUP: FRONTEND-LOGIN-ACTIONS`
  - Login, logout, and city-filtered organization access flow

- `LOOKUP: FRONTEND-ORG-SAVE`
  - How the frontend submits updates to the backend

- `LOOKUP: FRONTEND-INCIDENT-DEMOS`
  - Flood, hurricane, and storm demo markers

- `LOOKUP: FRONTEND-WEATHER-REFRESH`
  - Live weather and weekly forecast refresh behavior

- `LOOKUP: FRONTEND-UI-EVENTS`
  - City changes, filters, and card click events

- `LOOKUP: FRONTEND-APP-START`
  - Initial page startup and polling loop

- `LOOKUP: FRONTEND-POLL-GUARD`
  - Logic that pauses auto refresh while a user is editing an org update or report draft

## Demo Flow: Start Here

- App branding and page structure:
  - `LOOKUP: FRONTEND-HEADER`
  - `LOOKUP: FRONTEND-PUBLIC-DASHBOARD`

- Shared hosted database:
  - `LOOKUP: BACKEND-SUPABASE-CONNECTION`
  - `LOOKUP: BACKEND-RESOURCE-API`

- Real-time updates without a full page reload:
  - `LOOKUP: FRONTEND-RESOURCE-FETCH`
  - `LOOKUP: FRONTEND-ORG-SAVE`
  - `LOOKUP: FRONTEND-POLL-GUARD`

- Weather and alerts:
  - `LOOKUP: BACKEND-WEATHER-API`
  - `LOOKUP: FRONTEND-WEATHER-REFRESH`

- Live field reporting:
  - `LOOKUP: BACKEND-REPORTS-API`
  - `LOOKUP: FRONTEND-REPORT-FEED`
  - `LOOKUP: FRONTEND-REPORT-FORM`
  - `LOOKUP: FRONTEND-REPORT-SYSTEM`

- City-specific resource browsing:
  - `LOOKUP: FRONTEND-FILTER-PANEL`
  - `LOOKUP: FRONTEND-SIDEBAR-DIRECTORIES`

- Org update workflow:
  - `LOOKUP: BACKEND-AUTH`
  - `LOOKUP: FRONTEND-LOGIN-ACTIONS`
  - `LOOKUP: FRONTEND-ORG-CONTROLS`
  - `LOOKUP: FRONTEND-ORG-SAVE`

- Map behavior:
  - `LOOKUP: FRONTEND-MAP-RENDER`
  - `LOOKUP: FRONTEND-MAP-FOCUS`
  - `LOOKUP: FRONTEND-THEME-LOGIC`

- Recovery and support resources:
  - `LOOKUP: FRONTEND-HELP-RESOURCES`

## Fast Search Cheat Sheet

- Search `LOOKUP: FRONTEND-REPORT-FEED` to show the left live dashboard.
- Search `LOOKUP: FRONTEND-REPORT-FORM` to show how live reports are submitted.
- Search `LOOKUP: FRONTEND-ORG-CONTROLS` to show how organizations update status.
- Search `LOOKUP: FRONTEND-ORG-SAVE` to show where updates are sent to the backend.
- Search `LOOKUP: FRONTEND-POLL-GUARD` to explain why edits are not reset during auto refresh.
- Search `LOOKUP: FRONTEND-MAP-FOCUS` to show the click-to-map behavior.
- Search `LOOKUP: FRONTEND-HELP-RESOURCES` to show insurance, FEMA, and recovery links.
- Search `LOOKUP: BACKEND-RESOURCE-API` to show the shared data endpoints.
- Search `LOOKUP: BACKEND-REPORTS-API` to show how live reports are stored and returned.
- Search `LOOKUP: BACKEND-AUTH` to show the login/session system.
- Search `LOOKUP: BACKEND-WEATHER-API` to show live weather and alert integration.
