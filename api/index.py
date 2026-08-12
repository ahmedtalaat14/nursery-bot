from fastapi import FastAPI, Response
from api.privacy import router as privacy_router
from api.routers.webhook import router as webhook_router

app = FastAPI(title="Adam's & Elbaraa Nursery Bot", version="1.0.0")

# Register Routers
app.include_router(privacy_router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    return Response(
        content="Adam's & Elbaraa Nursery Facebook Bot is running smoothly!",
        media_type="text/plain",
        status_code=200
    )