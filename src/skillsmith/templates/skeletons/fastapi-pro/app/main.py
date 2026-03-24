from fastapi import FastAPI
app = FastAPI(title="Skillsmith FastAPI Pro")
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Ready to scale."}
