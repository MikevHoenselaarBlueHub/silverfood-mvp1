from fastapi import FastAPI, HTTPException
from analyse import analyse

app = FastAPI(title="Silverfood-API")

@app.get("/analyse")
def analyse_endpoint(url: str):
    try:
        return {"swaps": analyse(url)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
