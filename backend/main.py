from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.analyze import router as analyze_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Interview Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)

@app.get("/")
def root():
    return {"message": "Interview Analyzer API is running ✅"}