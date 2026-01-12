from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db


app = FastAPI()  

@app.get("/")  
async def index():  
    return {"status": "It's ALIVE!"}


@app.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    return {"users": []}  # Placeholder for actual user retrieval logic
