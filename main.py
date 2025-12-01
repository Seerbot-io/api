from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
import secrets
import os

from app.api.endpoints import (
    analysis,
    # auth,
    charting,
    health,
    web_content,
    websocket,
)
from app.core.config import settings

# Define the FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url = None,
)

# Cache configuration is now done via @cache decorator on individual endpoints
# See app/api/endpoints/analysis.py for examples
# session middleware
app.add_middleware(SessionMiddleware, 
                   secret_key=settings.SESSION_SECRET_KEY,
                   max_age=1800  # 1800,  # 30 minutes lifetime, extend with each request
                   )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount public static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

security = HTTPBasic()
def doc_auth(credentials: HTTPBasicCredentials = Depends(security)):
    correct_password = secrets.compare_digest(credentials.password, settings.DOC_PASSWORD)
    if not (correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(username: str = Depends(doc_auth)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")

@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(doc_auth)):
    return get_redoc_html(openapi_url="/openapi.json", title="docs")

@app.get("/openapi.json", include_in_schema=False)
async def openapi(username: str = Depends(doc_auth)):
    openapi_schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

    # Add WebSocket route to the schema
    openapi_schema["paths"].update({
        "/ws": {
            "get": {
                "summary": "[WebSocket] Unified WebSocket endpoint",
                "tags": ["WebSocket"],
                "description": """Unified WebSocket endpoint for subscribing to multiple data channels. Send messages with action (subscribe/unsubscribe) and channel.\n
Supported channels:\n
- ohlc:{symbol}|{resolution} - e.g., ohlc:USDM_ADA|5m\n
- token_info:{symbol} - e.g., token_info:USDM
                """,
                "responses": {200: {"description": "WebSocket connection"}},
            }
        },
        # "/analysis/tokens/{symbol}/ws":  analysis.token_market_info_ws_schema,
        # "/analysis/charting/ws":  analysis.subscribe_bars_schema,
    })
    return openapi_schema

@app.get("/websocket-test", include_in_schema=False)
async def websocket_test_page():
    """Serve the WebSocket test HTML page"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "websocket_test.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="WebSocket test page not found")

@app.get("/websocket-test2", include_in_schema=False)
async def unified_websocket_test_page():
    """Serve the unified WebSocket test HTML page"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "websocket_test2.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Unified WebSocket test page not found")

# Include your API routers
# version control rule: V{main}.{minor}.{patch}
#  - Main file will only control main version
app.include_router(health.router)

g_prefix = "/api"
app.include_router(analysis.router, prefix="/analysis")
app.include_router(charting.router, prefix="/charting")
app.include_router(web_content.router, prefix="/content")
app.include_router(websocket.router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=settings.PORT,
        ssl_keyfile=settings.SSL_KEY,
        ssl_certfile=settings.SSL_CERT,
        reload=settings.DEBUG
    )
