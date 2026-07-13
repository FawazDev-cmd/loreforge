from fastapi import FastAPI

from loreforge.api.documents import router as documents_router

app = FastAPI(title="LoreForge", version="0.1.0")
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "loreforge"}
