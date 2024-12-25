from fastapi import FastAPI, File, UploadFile, HTTPException, staticfiles, Request, Query, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Annotated

app = FastAPI(debug=True)
my_host = "127.0.0.1"
# функции
def create_db_and_tables():# обнуление/создание таблиц
    global acounts_engine,cataloge_engine
    SQLModel.metadata.create_all(cataloge_engine)
    SQLModel.metadata.create_all(acounts_engine)
    
def get_session(): #создание сессии
    with Session(engine) as session:
        yield session

# pydantic
class Cataloge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str | None
    amount: int
class Acounts(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
    password: int
    basket: str|None

# Указываем директорию для шаблонов
templates = Jinja2Templates(directory="templates")

app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")

# работа с SQL
sqlite_file_name = "db/cataloge.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
cataloge_engine = create_engine(sqlite_url, connect_args=connect_args)
####
sqlite_file_name = "db/acounts.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
acounts_engine = create_engine(sqlite_url, connect_args=connect_args)

SessionDep = Annotated[Session, Depends(get_session)]

# использование функций

# обработка запросов
@app.on_event("startup")
def on_start():
    create_db_and_tables()
    
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    req = {"request": request}
    return templates.TemplateResponse("index.html", req)

@app.get("/basket/", response_class=HTMLResponse)
async def basket(request: Request,user_id: int = -1):
    global my_host
    req = {
        "request": request,
        "my_host": my_host,
        "user_id": user_id
        }
    return templates.TemplateResponse("basket.html", req)

@app.post("/")
async def buying(request: Request):
    form_data = await request.form()
    form_type = form_data.get("buy_form")
    print(form_type)
    return form_data
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=my_host, port=8000)