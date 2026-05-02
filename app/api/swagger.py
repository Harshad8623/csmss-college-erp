"""
CSMSS ERP — Mobile REST API
All endpoints live under /api/v1/
JWT Bearer token authentication — separate from session-based web auth.
"""
from flasgger import Swagger

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/api/v1/apispec.json",
            "rule_filter": lambda rule: rule.rule.startswith("/api/"),
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
    "title": "CSMSS College ERP API",
    "uiversion": 3,
}

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "CSMSS College ERP — Mobile API",
        "description": "REST API for the CSMSS ERP mobile app (React Native). "
                       "All endpoints require Bearer JWT token except /api/v1/auth/login.",
        "version": "1.0.0",
        "contact": {"name": "CSMSS College"},
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header. Example: 'Bearer {token}'",
        }
    },
    "security": [{"Bearer": []}],
    "consumes": ["application/json"],
    "produces": ["application/json"],
}


def init_swagger(app):
    swagger = Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)
    return swagger
