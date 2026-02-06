import os
import secrets
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.endpoints import (
    ai_assistant,
    analysis,
    # auth,
    health,
    market,
    user,
    vault,
    web_content,
    websocket,
)
from app.core.config import settings
from app.services import price_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    if settings.TOKEN_CACHE_ENABLE_BACKGROUND_REFRESH:
        price_cache.start_background_refresh()
    yield
    # Shutdown
    price_cache.stop_background_refresh()


# Define the FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# Cache configuration is now done via @cache decorator on individual endpoints
# See app/api/endpoints/analysis.py for examples
# session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=1800,  # 1800,  # 30 minutes lifetime, extend with each request
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
    correct_password = secrets.compare_digest(
        credentials.password, settings.DOC_PASSWORD
    )
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
    openapi_schema = get_openapi(
        title=app.title, version=app.version, routes=app.routes
    )

    # Add WebSocket route to the schema
    openapi_schema["paths"].update(websocket.websocket_schema)
    return openapi_schema

@app.get("/websocket-test2", include_in_schema=False)
async def unified_websocket_test_page():
    """Serve the unified WebSocket test HTML page"""
    html_path = os.path.join(
        os.path.dirname(__file__), "static", "websocket_test2.html"
    )
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Unified WebSocket test page not found")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve the favicon"""
    favicon_path = os.path.join(
        os.path.dirname(__file__), "static", "images", "favicon.ico"
    )
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")


# Include your API routers
# version control rule: V{main}.{minor}.{patch}
#  - Main file will only control main version
app.include_router(health.router)

app.include_router(ai_assistant.router, prefix="/ai-assistant")
app.include_router(analysis.router, prefix="/analysis")
app.include_router(web_content.router, prefix="/content")
app.include_router(websocket.router)
app.include_router(market.router, prefix="/market")
app.include_router(user.router, prefix="/user")
app.include_router(vault.router, prefix="/vaults")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=settings.PORT,
        ssl_keyfile=settings.SSL_KEY,
        ssl_certfile=settings.SSL_CERT,
        reload=settings.DEBUG,
    )
