from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analysis_router, upload_router

app = FastAPI(
    title="AgroPulse Backend API",
    description="API REST de alto rendimiento para procesamiento satelital agrícola",
    version="2.0.0"
)

# Configurar CORS (Permite que React desde otro puerto haga peticiones)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se especifica la URL exacta ['http://localhost:5173']
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(upload_router.router, prefix="/api")
app.include_router(analysis_router.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "AgroPulse Backend Operation Normal"}
