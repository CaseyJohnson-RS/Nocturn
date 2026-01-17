from fastapi import FastAPI
from app.registration.router import router as registration_router

app = FastAPI()

app.include_router(registration_router)

@app.get("/health")  
async def health_check():  
    return {"status": "healthy"}