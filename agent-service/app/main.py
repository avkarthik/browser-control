from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers import agent, status, whatsapp


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Agent service starting...")
    yield
    print("🛑 Agent service shutting down...")


app = FastAPI(
    title="Browser Agent Service",
    description="WhatsApp-driven browser automation agent with multi-LLM support",
    version="1.0.0",
    lifespan=lifespan,
)

# Router registration
app.include_router(agent.router)
app.include_router(status.router)
app.include_router(whatsapp.router)