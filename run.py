from __future__ import annotations
from fastapi import FastAPI, Request, Depends, Form, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import SQLModel, Field, select, Relationship
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import Mapped
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from typing import Optional, Annotated, List
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import os
import hashlib
import jwt
import asyncio
from dotenv import load_dotenv, dotenv_values

# Определяем окружение
IS_PRODUCTION = os.getenv("RENDER", False) or os.getenv("RAILWAY", False)

# Загружаем конфиг из переменных окружения
config = {
    "DATABASE_URL": os.getenv("DATABASE_URL"),
    "SECRET_KEY": os.getenv("SECRET_KEY"),
    "JWT_CODER": os.getenv("JWT_CODER", "HS256"),
    "REGISTER_KEY": os.getenv("REGISTER_KEY")
}

# Проверяем, что все необходимые переменные есть
missing_vars = [k for k, v in config.items() if v is None and k != "JWT_CODER"]
if missing_vars:
    raise Exception(f"Missing environment variables: {missing_vars}")

print(f"🚀 Запуск в {'production' if IS_PRODUCTION else 'development'} режиме")
print(f"📦 База данных: {config['DATABASE_URL']}")

# Импортируем модели ПОСЛЕ определения конфига
from models import Users, Things, Promises

# Параметры для SQLite
connect_args = {"check_same_thread": False}
print("✅ Используется SQLite с aiosqlite")

engine = create_async_engine(
    database_url, 
    echo=not IS_PRODUCTION,  # Отключаем echo в production
    connect_args=connect_args
)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Утилиты
def hashing(text):
    return hashlib.sha256(text.encode()).hexdigest()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Приложение запускается...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("✅ База данных готова")
    yield
    print("🛑 Приложение останавливается...")
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

# CORS - динамический список origins
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
if IS_PRODUCTION:
    # Добавь свой Render URL
    origins.append("https://gaz-storage.onrender.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Зависимости
async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

SessionDep = Annotated[AsyncSession, Depends(get_session)]

def create_tokens(response: Response, data: dict, save = True) -> Response:
    try:
        # Refresh Token (30 дней)
        refresh_data = data.copy()
        refresh_data["exp"] = int((datetime.now() + timedelta(days=30)).timestamp())
        refresh_token = jwt.encode(refresh_data, config["SECRET_KEY"], algorithm=config["JWT_CODER"])

        # Access Token (15 минут)
        access_data = data.copy()
        access_data["exp"] = int((datetime.now() + timedelta(minutes=15)).timestamp())
        access_token = jwt.encode(access_data, config["SECRET_KEY"], algorithm=config["JWT_CODER"])

        # Устанавливаем куки
        cookie_params = {
            "max_age": 30*24*60*60 if save else 15*60,
            "httponly": True,
            "secure": IS_PRODUCTION,  # True в production
            "samesite": "lax",
            "path": "/"
        }
        
        if save:
            response.set_cookie(key="refresh", value=str(refresh_token), **cookie_params)
        
        response.set_cookie(key="access", value=str(access_token), **cookie_params)
        
        print("✅ Auth куки успешно установлены!")
        return response
        
    except Exception as e:
        print(f"❌ Ошибка установки auth кук: {e}")
        raise

# Аутентификация
decoded_access = 0
async def authenticate_user(request: Request, html: str = "-1", **variables_html):
    access_token = request.cookies.get("access")
    
    if access_token:
        try:
            decoded_access = await asyncio.to_thread(
                jwt.decode, access_token, config["SECRET_KEY"], algorithms=[config["JWT_CODER"]]
            )
            print("Access токен:", decoded_access)
            
            # Создаем response
            variables_html["request"] = request
            variables_html["user"] = decoded_access
            
            if html != "-1":
                response = templates.TemplateResponse(html, variables_html)
            else:
                response = templates.TemplateResponse("profile.html", variables_html)
            
            # Обновляем токены
            response_with_cookies = create_tokens(response, decoded_access)
            
            return (decoded_access, response_with_cookies)
            
        except jwt.ExpiredSignatureError:
            print("Access токен просрочен, пробуем обновить...")
            
    
    # Пробуем refresh токен
    refresh_token = request.cookies.get("refresh")
    if refresh_token:
        try:
            decoded_refresh = await asyncio.to_thread(
                jwt.decode, refresh_token, config["SECRET_KEY"], algorithms=[config["JWT_CODER"]]
            )
            print("Refresh токен:", decoded_refresh)
            
            # Создаем response
            variables_html["request"] = request
            variables_html["user"] = decoded_refresh
            
            if html != "-1":
                response = templates.TemplateResponse(html, variables_html)
            else:
                response = templates.TemplateResponse("profile.html", variables_html)
            
            # Обновляем токены
            response_with_cookies = create_tokens(response, decoded_refresh)
            
            return (decoded_refresh, response_with_cookies)
            
        except jwt.ExpiredSignatureError:
            print("Refresh токен также просрочен")
    
    print("Токены отсутствуют или просрочены")
    return None

# Роуты

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    auth_data = await authenticate_user(request, "register.html")
    
    if auth_data:
        return RedirectResponse(url="/profile", status_code=303)
    
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/things", response_class=HTMLResponse)
async def things_page(request: Request, session: SessionDep):
    statement = select(Things)
    result = await session.execute(statement)
    things = result.scalars().all()
    total_value = sum(thing.buy_cost * thing.amount for thing in things)
    if total_value >= 10_000_000:
        total_value = str(round(total_value/1_000_000,2))+" млн"
    else:
        total_value = str(round(total_value/1_000,2))+" тыс."
    print(things)
    auth_data = await authenticate_user(request, "things.html", things = things, total_value=total_value)
    
    if auth_data:
        return auth_data[1]

    return RedirectResponse(url="/login", status_code=303)

@app.get("/admin/add", response_class=HTMLResponse)
async def admin_add_page(request: Request, session: SessionDep):
    auth_data = await authenticate_user(request, "admin_add.html")
    
    if auth_data and auth_data[0]["admin"]:
        return auth_data[1]

    return RedirectResponse(url="/login", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, session: SessionDep):
    auth_data = await authenticate_user(request, "admin.html")
    
    if auth_data and auth_data[0]["admin"]:
        return auth_data[1]

    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    auth_data = await authenticate_user(request, "login.html")
    
    if auth_data:
        return RedirectResponse(url="/profile", status_code=303)
    
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_user(
    request: Request,
    response: Response,
    session: SessionDep,
    email: str = Form(...),
    password: str = Form(...),
    remember: Optional[str] = Form(None)
):
    stmt = select(Users).where(Users.email == email).where(Users.hashed_password == hashing(password))
    result = await session.execute(stmt)
    user = result.first()
    
    if user:
        data = {
            "email": email,
            "password": hashing(password),
            "fio": user[0].fio,
            "admin": user[0].admin,
            "id": user[0].id
        }
        redirect_response = RedirectResponse(url="/profile", status_code=303)
        redirect_response = create_tokens(redirect_response, data, save=bool(remember))
        return redirect_response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Неверный email или пароль"
        })

# ДОБАВЛЯЕМ ИМЕНА ЭНДПОИНТАМ ДЛЯ url_for()
@app.post("/register", name="register_user")
async def register(
    request: Request, 
    session: SessionDep, 
    fio: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...), 
    password_rep: str = Form(...),
    admin_key: str = Form(None)
):
    print("🎯 Начало регистрации...")
    
    # Валидация
    if len(fio) < 8:
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "ФИО должно быть не менее 8 символов"
        })
    
    if password != password_rep:
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "Пароли не совпадают"
        })
    
    # Проверка существующего пользователя
    stmt = select(Users).where(Users.email == email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "error": "Пользователь с таким email уже существует"
        })
    
    # Создание пользователя
    hashed_pass = hashing(password)
    new_user = Users(fio=fio, email=email, hashed_password=hashed_pass, admin=False)
    if admin_key == config["REGISTER_KEY"]:
        new_user.admin = True
    session.add(new_user)
    await session.commit()
    print("✅ Пользователь создан")
    
    # Данные для токенов
    data = {"email": email, "password": hashed_pass, "fio": fio,"admin": new_user.admin, "id": new_user.id}
    
    redirect_response = RedirectResponse(url="/profile", status_code=303)
    redirect_response = create_tokens(redirect_response, data)
    return redirect_response

@app.get("/edit/{id}", response_class=HTMLResponse)
async def menu(request: Request, session: SessionDep, id: int):
    # 1. Только проверяем авторизацию, НЕ рендерим шаблон
    auth_data = await authenticate_user(request, "-1")
    
    if not auth_data:
        return RedirectResponse(url="/login", status_code=303)
    
    decoded_user, _ = auth_data  # response = None, игнорируем
    
    # 3. Получаем товар из БД
    try:
        thing = await session.get(Things, id)
    except Exception as e:
        print(f"Ошибка БД: {e}")
        await session.rollback()  # ЯВНЫЙ ROLLBACK
        thing = None
    
    # 4. САМИ рендерим шаблон
    context = {
        "request": request,
        "user": decoded_user,
        "thing": thing
    }
    
    response = templates.TemplateResponse("edit.html", context)
    
    # 5. Обновляем токены, если нужно
    response = create_tokens(response, decoded_user, save=False)
    
    return response

@app.post("/admin/add")
async def admin_add(request: Request, session: SessionDep, name: str = Form(...), description: str = Form(...), amount: int = Form(...), buy_cost: float = Form(...), kind: str = Form(...)):
    
    auth_data = await authenticate_user(request, "admin_add.html")
    
    if auth_data and auth_data[0]["admin"]:
        thing = Things(name=name, description=description, amount=amount, buy_cost=buy_cost, kind=kind)
        session.add(thing)
        await session.commit()
        return auth_data[1]

    return RedirectResponse(url="/login", status_code=303)

@app.post("/admin/edit/{id}")
async def admin_edit(request: Request, session: SessionDep,
                id: int,
                name: str = Form(...),
                description: str = Form(...),
                amount: int = Form(...),
                buy_cost: float = Form(...),
                kind: str = Form(...)):
    
    auth_data = await authenticate_user(request, "-1")
    
    if auth_data and auth_data[0]["admin"]:
        
        thing = await session.get(Things, id)
           
        thing.name = name
        thing.description = description
        thing.amount = amount
        thing.buy_cost = buy_cost
        thing.kind = kind

        await session.commit()
        return RedirectResponse(url='/things', status_code=303)

    return RedirectResponse(url="/login", status_code=303)

@app.post("/operator/edit/{id}")
async def operator_edit(request: Request, session: SessionDep,
                id: int,
                new_name: str = Form(...),
                new_description: str = Form(...),
                new_amount: int = Form(...),
                new_buy_cost: float = Form(...),
                new_kind: str = Form(...),
                priority: str = Form(...),
                comment: str = Form(...)
                ):
    
    auth_data = await authenticate_user(request, "-1")
    
    if auth_data and not auth_data[0]["admin"]:
        
        thing = await session.get(Things, id)
        user = await session.get(Users, int(auth_data[0]["id"]))
        
        promise = Promises(promise_owner=user, promise_thing=thing,
                           new_amount=new_amount,
                           new_buy_cost=new_buy_cost,
                           new_kind=new_kind,
                           new_description=new_description,
                           new_name=new_name,
                           created_at=datetime.now(),
                           die_at=(datetime.now()+timedelta(days=14)),
                           priority=priority,
                           message=comment,
                           old_amount=thing.amount,
                           old_buy_cost=thing.buy_cost,
                           old_kind=thing.kind,
                           old_description=thing.description,
                           old_name=thing.name)
        
        if thing.name == promise.new_name:
            promise.new_name = None
        if thing.description == promise.new_description:
            promise.new_description = None
        if thing.amount == promise.new_amount:
            promise.new_amount = None
        if thing.buy_cost == promise.new_buy_cost:
            promise.new_buy_cost = None
        if thing.kind == promise.new_kind:
            promise.new_kind = None

        session.add(promise)
        await session.commit()
        return RedirectResponse(url='/things', status_code=303)

    return RedirectResponse(url="/login", status_code=303)

@app.get("/admin/requests/")
async def admin_requests(request: Request, session: SessionDep):
    
    auth_data = await authenticate_user(request, "-1")
    
    if auth_data and auth_data[0]["admin"]:
        
        statement = select(Promises, Things, Users).where(Promises.user_id == Users.id).where(Promises.thing_id == Things.id)
        result = await session.execute(statement)
        data = result.all()
        auth_data = await authenticate_user(request, "admin_requests.html", data=data)
        await session.commit()
        return auth_data[1]

    return RedirectResponse(url="/login", status_code=303)

@app.get("/operator/requests/")
async def operator_requests(request: Request, session: SessionDep):
    
    auth_data = await authenticate_user(request, "-1")
    
    if auth_data and not auth_data[0]["admin"]:
        
        stmt = select(Promises)\
        .where(Promises.user_id == auth_data[0]["id"])\
        .options(selectinload(Promises.thing))\
        .order_by(Promises.created_at.desc())
    
        result = await session.execute(stmt)
        promises = result.scalars().all()
        
        auth_data = await authenticate_user(request, "operator_requests.html", promises=promises)

        await session.commit()
        return auth_data[1]

    return RedirectResponse(url="/login", status_code=303)

@app.post("/admin/requests/{id}/reject")  #отказ
async def decline(request: Request, session: SessionDep, id: int):
    
    auth_data = await authenticate_user(request, "-1")
    
    if auth_data and auth_data[0]["admin"]:
        
        promise = await session.get(Promises, id)
        promise.status = "Отклонено"
        await session.commit()
        return RedirectResponse(url='/admin/requests', status_code=303)

    return RedirectResponse(url="/login", status_code=303)

@app.post("/admin/requests/{id}/approve")   #принятие
async def claim(request: Request, session: SessionDep,
                id: int,
                new_name: str|None = Form(...),
                new_description: str|None = Form(...),
                new_amount: int|None = Form(...),
                new_buy_cost: float|None = Form(...),
                new_kind: str|None = Form(...)):
    
    auth_data = await authenticate_user(request, "-1")
    
    if auth_data and auth_data[0]["admin"]:

        stmt = select(Promises).where(Promises.id == id).options(
            selectinload(Promises.thing)  # жадная загрузка thing
        )
        result = await session.execute(stmt)
        promise = result.scalar_one_or_none()
        
        if not promise:
            return RedirectResponse(url="/admin/requests?error=not_found", status_code=303)

        promise.status = "Одобрено"
        thing = promise.thing
        if thing.name == promise.new_name:
            promise.new_name = None
        if thing.description == promise.new_description:
            promise.new_description = None
        if thing.amount == promise.new_amount:
            promise.new_amount = None
        if thing.buy_cost == promise.new_buy_cost:
            promise.new_buy_cost = None
        if thing.kind == promise.new_kind:
            promise.new_kind = None

        thing.name = new_name
        thing.description = new_description
        thing.amount = new_amount
        thing.buy_cost = new_buy_cost
        thing.kind = new_kind
        
        await session.commit()

        return RedirectResponse(url="/admin/requests", status_code=303)

    return RedirectResponse(url="/login", status_code=303)

@app.get("/admin/delete/{id}")
async def delete_item(request: Request, session: SessionDep, id: int):
    
    auth_data = await authenticate_user(request, "-1")
    
    if auth_data and auth_data[0]["admin"]:
        # 1. Добавляем await!
        thing = await session.get(Things, id)
        
        # 2. Проверяем, существует ли запись
        if not thing:
            # Если товар не найден
            return RedirectResponse(url="/things?error=not_found", status_code=303)
        
        # 3. Удаляем
        await session.delete(thing)
        await session.commit()
        
        return RedirectResponse(url="/things?success=deleted", status_code=303)

    return RedirectResponse(url="/login", status_code=303)

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, session: SessionDep):
    auth_data = await authenticate_user(request, "profile.html")
    
    if auth_data:
        return auth_data[1]
    else:
        print("В куки нет данных")
        return RedirectResponse(url="/login", status_code=303)

@app.get("/my-cookies")
async def my_cookies(request: Request):
    cookies = dict(request.cookies)
    return {
        "message": "Текущие куки:",
        "cookies": cookies,
        "total_cookies": len(cookies)
    }

@app.get("/logout")
async def logout(response: Response):
    print("❌Пользователь вышел")
    new_r = RedirectResponse(url="/")
    new_r.delete_cookie(key="access")
    new_r.delete_cookie(key="refresh")
    
    return new_r

if __name__ == "__main__":
    import uvicorn
    
    # Настройки для Render
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0" if IS_PRODUCTION else "127.0.0.1"
    
    print(f"🌐 Сервер запускается на {host}:{port}")

    uvicorn.run(app, host=host, port=port)
