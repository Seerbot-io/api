from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
import secrets

from app.api.endpoints import (
    analysis,
    auth,
    health,
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
# app.mount("/static", StaticFiles(directory=settings.STATIC_FOLDER), name="static")
# templates = Jinja2Templates(directory="templates")

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
    return get_openapi(title=app.title, version=app.version, routes=app.routes)

# Include your API routers
# version control rule: V{main}.{minor}.{patch}
#  - Main file will only control main version
app.include_router(health.router)

g_prefix = "/api"
app.include_router(analysis.router, prefix="/analysis")
app.include_router(auth.router, prefix="/auth")



# todo: login
# login page
# app.include_router(auth.router, prefix="/api/sessions")
# app.include_router(login_page.router, prefix="/api/sessions")  # exapmle client page for login
# app.include_router(google.router, prefix="/api/sessions")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        ssl_keyfile=settings.SSL_KEY,
        ssl_certfile=settings.SSL_CERT,
        reload=settings.DEBUG
    )
