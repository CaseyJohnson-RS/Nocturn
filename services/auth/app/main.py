from fastapi import FastAPI  
from app.core.settings import settings

app = FastAPI()  

@app.get("/")  
async def index():  
    return {"status": "It's ALIVE!"}