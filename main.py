from fastapi import FastAPI, File, UploadFile, HTTPException, staticfiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

app = FastAPI(debug=True)

#
#
# Указываем директорию для шаблонов
templates = Jinja2Templates(directory="templates")

app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    req = {"request": request}
    return templates.TemplateResponse("index.html", req)
@app.post("/")
def rr(request: Request):
    print(request)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)