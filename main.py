from fastapi import FastAPI, File, UploadFile, HTTPException, staticfiles, Request, Query, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Annotated
import hashlib

#--------------------------#
# venv\Scripts\activate    #
#                          #  
# venv\Scripts\deactivate  #
#--------------------------#

app = FastAPI(debug=True)
global HOST, PORT
HOST = "192.168.0.101"
PORT = 8000
# функции
def create_db_and_tables():# обнуление/создание таблиц
    global engine
    SQLModel.metadata.create_all(engine)
    
def get_session(): #создание сессии
    with Session(engine) as session:
        yield session

# pydantic
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
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

# функции не связанные с fastapi
def clear_db(db):
    with Session(engine) as session:
      results = session.exec(select(db)).all()
      for result in results:
          session.delete(result)
      session.commit()
def hashing(text):
    return hashlib.sha256(text.encode()).hexdigest()# текст кодируется по сиситеме sha256 и префращфется в 16-ричную систему
# обработка запросов
@app.on_event("startup")
def on_start():
    create_db_and_tables()

@app.get("/",response_class=HTMLResponse)
def read_root(request: Request):
    req = {"request": request, "HOST": HOST, "PORT": PORT}
    return templates.TemplateResponse("login.html", req)

@app.post("/")
def read_root(session:SessionDep, request: Request, password: str|None = Form(...), email: str|None = Form(...)):
    hash_e =hashing(email)
    hash_pas = hashing(password)
    statement = select(User).where(User.email == hash_e).where(User.password == hash_pas)
    result = session.exec(statement)
    first = result.first()
    print(first)
    if not (first is None):
        return HTMLResponse(content=f"""<meta http-equiv="refresh" content="0.1; URL='/cataloge?email={hash_e}'" />""")
    return HTMLResponse(content=f'<h1 style = "color: red;">Пользователь не найден</h1>')

@app.get("/register",response_class=HTMLResponse)
def read_root(request: Request):
    req = {"request": request, "HOST": HOST, "PORT": PORT}
    return templates.TemplateResponse("register.html", req)

@app.post("/register",response_class=HTMLResponse)
def read_root(session: SessionDep, request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), rep_password: str = Form(...)):
    if password == rep_password:
        try:
            hash_e = hashing(email)
            hash_pas = hashing(password)
            user = User(username = username, email = hash_e, password = hash_pas, basket = None)
        except ValidationError as e:
            return e
        except Exception as e:
            return e
        email_query = select(User).where(User.email == hash_e)
        result = session.exec(email_query)
        first = result.first()
        if not (first is None):
            return HTMLResponse(content=f'<h1 style = "color: red;">Пользователь с такой почтой уже есть</h1>')
        session.add(user)
        session.commit()
        session.refresh(user)
        return f'<h1 style = "color: green;">Успешно</h1>'
    return f'<h1 style = "color: red;">Пароли не совпадают</h1>'

@app.get("/admin/add", response_class=HTMLResponse)
def read_root(request: Request):
    req = {"request": request, "PORT": PORT}
    return templates.TemplateResponse("creater.html", req)

@app.post("/admin/add", response_class=HTMLResponse)
def read_root(session: SessionDep, description: str = Form(...), name: str = Form(...), amount: str = Form(...), cost: str = Form(...)):
    try:
        amount = float(amount.replace(",","."))
        cost = float(cost.replace(",","."))
        if cost > 0 and amount > 0 and amount % 1 == 0:
            tovar = Cataloge(description=description, name=name, amount=amount, cost=cost)
            session.add(tovar)
            session.commit()
            session.refresh(tovar)
            return HTMLResponse(content='<h1 style = "color: green;">успешно!</h1>')
        return HTMLResponse(content='<h1 style = "color: red;">Ошибочные данные</h1>')
    except ValueError:
        return HTMLResponse(content='<h1 style = "color: red;">Цена и количество не могут быть символами</h1>')    

@app.get("/cataloge", response_class=HTMLResponse)
def read_root(request: Request, session: SessionDep, email:str|None):
    alls = session.query(Cataloge).all()
    names = list()
    descriptions = list()
    costs = list()
    amounts = list()
    for t in alls:
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
        "all": len(alls),
        "PORT": PORT,
        "HOST": HOST,
        "email": email
        }
    return templates.TemplateResponse("cataloge.html", req)

@app.get("/basket/", response_class=HTMLResponse)
def basket(request: Request, email:str|None):
    
    req = {
        "request": request,
        "HOST": HOST,
        "PORT": PORT,
        "email": email
        }
    return templates.TemplateResponse("basket.html", req)

@app.post("/cataloge")
def buying(session: SessionDep,request: Request, buy_form: int = Form(...)):
    return buy_form
    id = buy_form
    tovar = session.get(Cataloge,id)
    return tovar.id,tovar.name, tovar.amount
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)