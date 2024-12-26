from fastapi import FastAPI, File, UploadFile, HTTPException, staticfiles, Request, Query, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Annotated

app = FastAPI(debug=True)
my_host = "127.0.0.1"
# функции
def create_db_and_tables():# обнуление/создание таблиц
    global engine
    SQLModel.metadata.create_all(engine)
    
def get_session(): #создание сессии
    with Session(engine) as session:
        yield session

# pydantic
class Acounts(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
    password: str
    basket: str|None

class Cataloge(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str
    amount: int
    cost: float


# Указываем директорию для шаблонов
templates = Jinja2Templates(directory="templates")

app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")

# работа с SQL
sqlite_file_name = "db/database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)
SessionDep = Annotated[Session, Depends(get_session)]

# использование функций

# обработка запросов
@app.on_event("startup")
def on_start():
    create_db_and_tables()

@app.get("/admin/add", response_class=HTMLResponse)
async def read_root(request: Request):
    req = {"request": request}
    return templates.TemplateResponse("creater.html", req)

@app.post("/admin/add", response_class=HTMLResponse)
async def read_root(session: SessionDep,tovar: Cataloge = Form(None)) -> Cataloge:
    session.add(tovar)
    session.commit()
    session.refresh(tovar)
    return HTMLResponse(content='<h1 style = "color: green;">успешно!</h1>')
    

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, session: SessionDep):
    all = session.query(Cataloge).all()
    names = list()
    descriptions = list()
    costs = list()
    amounts = list()

    for t in all:
        amounts.append(t.amount)
        names.append(t.name)
        descriptions.append(t.description)
        costs.append(t.cost)
    req = {
        "request": request,
        "names": names,
        "descriptions": descriptions,
        "costs": costs,
        "amounts": amounts,
        "all": len(all)
        }
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
async def buying(session: SessionDep,request: Request, buy_form: int = Form(...)):
    id = buy_form
    tovar = session.get(Cataloge,id)
    return tovar
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=my_host, port=8000)