import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base

from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic_settings import BaseSettings
from fastapi.middleware.cors import CORSMiddleware


# Настройки
class Settings(BaseSettings):
    database_url: str = "sqlite:///./quiz.db"
    secret_key: str = "secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


settings = Settings()

# Безопасность
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# База данных
Base = declarative_base()

# Удаляем существующую базу данных, если она есть (для разработки)
db_file = Path("quiz.db")
if db_file.exists():
    db_file.unlink()

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Модели
class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    is_active = Column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    question_text = Column(String, index=True)
    correct_answer = Column(String)
    quiz = relationship("Quiz")


class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    option_text = Column(String)
    question_id = Column(Integer, ForeignKey("questions.id"))


class QuizResult(Base):
    __tablename__ = "quiz_results"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    score = Column(Integer)
    quiz = relationship("Quiz")


# Создание таблиц
Base.metadata.create_all(bind=engine)


# Вспомогательные функции
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        token = token.replace("Bearer ", "")
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.username == username).first()


# Пример тестов
SAMPLE_QUIZZES = [
    {
        "title": "История лицея 1535",
        "description": "Проверьте свои знания об истории лицея",
        "questions": [
            {
                "question_text": "В каком году было построено здание лицея 1535?",
                "correct_answer": "1929",
                "options": ["1927", "1929", "1930", "1948"]
            },
            {
                "question_text": "Кто был архитектором здания лицея?",
                "correct_answer": "Мотылёв",
                "options": ["Мотылёв", "Ворошилов", "Мазинг", "Широков"]
            },
            {
                "question_text": "Что находилось на месте лицея в военное время?",
                "correct_answer": "Госпиталь",
                "options": ["Жилой дом", "Бомбоубежище", "Военная школа", "Госпиталь"]
            },
{
                "question_text": "Какой восточный язык в первую очередь стали изучать в лицее после войны?",
                "correct_answer": "Китайский",
                "options": ["Корейский", "Японский", "Китайский", "Арабский"]
    }
        ]
    },
    {
        "title": "Математика",
        "description": "Базовые математические вопросы",
        "questions": [
            {
                "question_text": "Чему равно π (пи) с точностью до пяти знаков?",
                "correct_answer": "3.14159",
                "options": ["3.14238", "3.14159", "3.14179", "3.14192"]
            },
            {
                "question_text": "Сколько градусов соответствует радианам 18П/5?",
                "correct_answer": "648",
                "options": ["578", "638", "648", "768"]
            },
{
                "question_text": "Сколько футов в сажени?",
                "correct_answer": "6",
                "options": ["500", "100", "6", "12"]
            }
        ]
    },
    {
        "title": "Какой ты лицеист?",
        "description": "Тест на определение вашего эмоционального состояния",
        "questions": [
            {
                "question_text": "Как ты себя чувствуешь утром перед уроками?",
                "correct_answer": "Полон энергии",
                "options": ["Полон энергии", "Нормально", "Устал", "Не хочу идти"]
            },
            {
                "question_text": "Что чувствуешь, когда видишь расписание на день?",
                "correct_answer": "Радость",
                "options": ["Радость", "Безразличие", "Легкую тревогу", "Ужас"]
            },
            {
                "question_text": "Твои эмоции перед контрольной?",
                "correct_answer": "Уверен в себе",
                "options": ["Уверен в себе", "Немного волнуюсь", "Сильно переживаю", "Паника"]
            },
            {
                "question_text": "Как реагируешь на неожиданную самостоятельную?",
                "correct_answer": "Отлично, люблю сюрпризы!",
                "options": ["Отлично, люблю сюрпризы!", "Спокойно", "Раздражение", "Шок"]
            },
            {
                "question_text": "Что чувствуешь после уроков?",
                "correct_answer": "Еще больше энергии",
                "options": ["Еще больше энергии", "Немного устал", "Устал", "Полное истощение"]
            },
            {
                "question_text": "Твое отношение к домашним заданиям?",
                "correct_answer": "Делаю с удовольствием",
                "options": ["Делаю с удовольствием", "Делаю без эмоций", "Делаю с неохотой", "Ненавижу"]
            },
            {
                "question_text": "Как ты себя чувствуешь в каникулы?",
                "correct_answer": "Отдыхаю и заряжаюсь",
                "options": ["Отдыхаю и заряжаюсь", "Нормально", "Скучаю по школе", "Не могу расслабиться"]
            },
            {
                "question_text": "Твои эмоции при виде учебника?",
                "correct_answer": "Интерес",
                "options": ["Интерес", "Безразличие", "Грусть", "Отвращение"]
            },
            {
                "question_text": "Как ты относишься к школьным мероприятиям?",
                "correct_answer": "Обожаю участвовать",
                "options": ["Обожаю участвовать", "Хожу иногда", "Не люблю", "Избегаю"]
            },
            {
                "question_text": "Твое общее впечатление от учебы?",
                "correct_answer": "Воодушевление",
                "options": ["Воодушевление", "Нейтральное", "Усталость", "Разочарование"]
            }
        ]
    }
]


app = FastAPI(title="School Quiz App", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# HTML-шаблоны
template_files = {
    "base.html": """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Школьные Квизы{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: url('/static/school-bg.jpg') no-repeat center center fixed;
            background-size: cover;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .navbar {
            background-color: #0a4275 !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .card {
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            box-shadow: 0 6px 12px rgba(0,0,0,0.1);
            transition: transform 0.3s ease-in-out;
        }
        .card:hover {
            transform: translateY(-5px);
        }
        .btn-school {
            background-color: #2ecc71;
            color: white;
            border: none;
            padding: 10px 20px;
            font-weight: bold;
        }
        .btn-school:hover {
            background-color: #27ae60;
        }
        .logo {
            max-height: 40px;
            margin-right: 10px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark mb-4">
        <div class="container">
            <img src="/static/lyceum1535-logo.png" alt="Логотип" class="logo">
            <a class="navbar-brand" href="/">Школьные Квизы</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item"><a class="nav-link" href="/">Главная</a></li>
                    <li class="nav-item"><a class="nav-link" href="/quizzes">Квизы</a></li>
                </ul>
                <ul class="navbar-nav">
                    {% if user %}
                        <li class="nav-item"><a class="nav-link" href="/profile">Профиль</a></li>
                        <li class="nav-item"><a class="nav-link" href="/logout">Выход</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="/login">Войти</a></li>
                        <li class="nav-item"><a class="nav-link" href="/register">Регистрация</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>
    <div class="container my-5">
        {% block content %}{% endblock %}
    </div>
    <footer class="text-center text-muted mt-5 pb-3">
        &copy; 2023 | Лицей №1535 | Школьные квизы
    </footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>""",

    "index.html": """{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card p-4 text-center">
            <h2 class="mb-4">Добро пожаловать в онлайн-квиз!</h2>
            <img src="/static/lyceum1535.jpg"
                 alt="Фото здания лицея"
                 class="img-fluid rounded shadow-sm mb-4"
                 style="max-width: 60%; height: auto;">
            <p class="lead">Проверьте свои знания о лицеях и истории образования.</p>
            {% if user %}
                <a href="/quizzes" class="btn btn-school btn-lg">Выбрать тест</a>
            {% else %}
                <div class="alert alert-info mt-3">
                    Пожалуйста, <a href="/login" class="alert-link">войдите</a> или
                    <a href="/register" class="alert-link">зарегистрируйтесь</a>, чтобы начать.
                </div>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}""",

    "login.html": """{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center mt-5">
    <div class="col-md-6">
        <div class="card p-4">
            <h3 class="text-center mb-4">Вход в систему</h3>
            {% if error %}
            <div class="alert alert-danger">{{ error }}</div>
            {% endif %}
            <form method="post">
                <div class="mb-3">
                    <label for="username" class="form-label">Имя пользователя</label>
                    <input type="text" class="form-control" id="username" name="username" required>
                </div>
                <div class="mb-3">
                    <label for="password" class="form-label">Пароль</label>
                    <input type="password" class="form-control" id="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-school w-100">Войти</button>
            </form>
            <div class="mt-3 text-center">
                Нет аккаунта? <a href="/register">Зарегистрируйтесь</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}""",

    "register.html": """{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center mt-5">
    <div class="col-md-6">
        <div class="card p-4">
            <h3 class="text-center mb-4">Регистрация</h3>
            {% if error %}
            <div class="alert alert-danger">{{ error }}</div>
            {% endif %}
            <form method="post">
                <div class="mb-3">
                    <label for="username" class="form-label">Имя пользователя</label>
                    <input type="text" class="form-control" id="username" name="username" required>
                </div>
                <div class="mb-3">
                    <label for="email" class="form-label">Email</label>
                    <input type="email" class="form-control" id="email" name="email" required>
                </div>
                <div class="mb-3">
                    <label for="password" class="form-label">Пароль (минимум 6 символов)</label>
                    <input type="password" class="form-control" id="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-school w-100">Зарегистрироваться</button>
            </form>
            <div class="mt-3 text-center">
                Уже есть аккаунт? <a href="/login">Войдите</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}""",

    "quizzes.html": """{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-10">
        <h2 class="text-center mb-4">Доступные тесты</h2>
        <div class="row">
            {% for quiz in quizzes %}
            <div class="col-md-6 mb-4">
                <div class="card h-100">
                    <div class="card-body">
                        <h4 class="card-title">{{ quiz.title }}</h4>
                        <p class="card-text">{{ quiz.description }}</p>
                    </div>
                    <div class="card-footer bg-transparent">
                        <a href="/quiz/{{ quiz.id }}" class="btn btn-school w-100">Начать тест</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}""",

    "quiz.html": """{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <h2 class="text-center mb-4">{{ quiz.title }}</h2>
        <form method="post" action="/submit-quiz">
            <input type="hidden" name="quiz_id" value="{{ quiz.id }}">
            {% for question in questions %}
            <div class="card mb-3">
                <div class="card-header bg-primary text-white">
                    <strong>Вопрос {{ loop.index }}:</strong> {{ question.question_text }}
                </div>
                <div class="card-body">
                    {% for option in question.options %}
                    <div class="form-check mb-2">
                        <input class="form-check-input" type="radio"
                               name="question_{{ question.id }}"
                               id="q{{ question.id }}_o{{ loop.index }}"
                               value="{{ option.option_text }}" required>
                        <label class="form-check-label" for="q{{ question.id }}_o{{ loop.index }}">
                            {{ option.option_text }}
                        </label>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
            <div class="text-center">
                <button type="submit" class="btn btn-school btn-lg">Отправить ответы</button>
            </div>
        </form>
    </div>
</div>
{% endblock %}""",

    "result.html": """{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card p-4 text-center">
            <h3 class="mb-4">Результаты теста "{{ quiz_title }}"</h3>
            <h4>Вы набрали {{ score }} из {{ total }} баллов</h4>
            <div class="progress mb-4" style="height: 30px;">
                <div class="progress-bar bg-success" role="progressbar" style="width: {{ percentage }}%">
                    {{ percentage }}%
                </div>
            </div>
            {% if personality %}
            <div class="alert alert-info">
                <h4>{{ personality }}</h4>
            </div>
            {% endif %}
            {% if percentage >= 80 %}
            <div class="alert alert-success">Отлично! Вы отлично разбираетесь в теме!</div>
            {% elif percentage >= 50 %}
            <div class="alert alert-warning">Хорошо! Можно попробовать ещё лучше!</div>
            {% else %}
            <div class="alert alert-danger">Попробуйте ещё! Вы сможете лучше!</div>
            {% endif %}
            <div class="mt-4">
                <a href="/quizzes" class="btn btn-outline-primary me-2">Выбрать другой тест</a>
                <a href="/profile" class="btn btn-outline-secondary">Профиль</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}""",

    "profile.html": """{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card p-4">
            <h3 class="text-center mb-4">Профиль</h3>
            <h4>{{ user.username }}</h4>
            <p class="text-muted">{{ user.email }}</p>
            <hr>
            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header">Статистика</div>
                        <div class="card-body">
                            <p>Количество тестов: {{ total_quizzes }}</p>
                            <p>Лучший результат: {{ best_score }}</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header">Последние результаты</div>
                        <div class="card-body">
                            {% if results %}
                                <ul class="list-group">
                                    {% for result in results[-5:] %}
                                    <li class="list-group-item">
                                        {{ result.quiz.title }}: {{ result.score }} баллов
                                    </li>
                                    {% endfor %}
                                </ul>
                            {% else %}
                                <p>Нет результатов</p>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
            <div class="text-center mt-3">
                <a href="/quizzes" class="btn btn-school">Выбрать тест</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}"""
}

# Сохранение шаблонов
for fname, content in template_files.items():
    with open(templates_dir / fname, "w", encoding="utf-8") as f:
        f.write(content)


# Маршруты
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html",
                                          {"request": request, "error": "Неверное имя пользователя или пароль"},
                                          status_code=400)
    token = create_access_token(data={"sub": user.username},
                                expires_delta=timedelta(minutes=settings.access_token_expire_minutes))
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True,
                        max_age=settings.access_token_expire_minutes * 60)
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    if len(password) < 6:
        return templates.TemplateResponse("register.html",
                                          {"request": request, "error": "Пароль должен быть не менее 6 символов"},
                                          status_code=400)
    existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing:
        field = "Имя пользователя" if existing.username == username else "Email"
        return templates.TemplateResponse("register.html", {"request": request, "error": f"{field} уже занят"},
                                          status_code=400)
    try:
        new_user = User(username=username, email=email, hashed_password=get_password_hash(password))
        db.add(new_user)
        db.commit()
        token = create_access_token(data={"sub": new_user.username})
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True)
        return response
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("register.html",
                                          {"request": request, "error": f"Ошибка регистрации: {str(e)}"},
                                          status_code=500)


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response


@app.get("/quizzes", response_class=HTMLResponse)
async def quizzes_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Initialize quizzes if none exist
    if db.query(Quiz).count() == 0:
        for quiz_data in SAMPLE_QUIZZES:
            if not all(key in quiz_data for key in ["title", "description", "questions"]):
                continue

            quiz = Quiz(title=quiz_data["title"], description=quiz_data["description"])
            db.add(quiz)
            db.commit()

            for question_data in quiz_data["questions"]:
                if not all(key in question_data for key in ["question_text", "correct_answer", "options"]):
                    continue

                question = Question(
                    quiz_id=quiz.id,
                    question_text=question_data["question_text"],
                    correct_answer=question_data["correct_answer"]
                )
                db.add(question)
                db.commit()

                for option_text in question_data["options"]:
                    db.add(Option(option_text=option_text, question_id=question.id))
                db.commit()

    quizzes = db.query(Quiz).filter(Quiz.is_active == True).all()
    return templates.TemplateResponse("quizzes.html", {
        "request": request,
        "user": user,
        "quizzes": quizzes
    })


@app.get("/quiz/{quiz_id}", response_class=HTMLResponse)
async def quiz_page(request: Request, quiz_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    questions = db.query(Question).filter(Question.quiz_id == quiz_id).all()
    for q in questions:
        q.options = db.query(Option).filter(Option.question_id == q.id).all()

    return templates.TemplateResponse("quiz.html", {
        "request": request,
        "user": user,
        "quiz": quiz,
        "questions": questions
    })


@app.post("/submit-quiz")
async def submit_quiz(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    form_data = await request.form()
    quiz_id = form_data.get("quiz_id")

    if not quiz_id:
        raise HTTPException(status_code=400, detail="Quiz ID missing")

    score = 0
    questions = db.query(Question).filter(Question.quiz_id == quiz_id).all()
    total = len(questions)

    for q in questions:
        answer = form_data.get(f"question_{q.id}")
        if answer == q.correct_answer:
            score += 1

    result = QuizResult(user_id=user.id, quiz_id=quiz_id, score=score)
    db.add(result)
    db.commit()

    # Определяем тип лицеиста для теста "Какой ты лицеист?"
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    personality = None
    if quiz and quiz.title == "Какой ты лицеист?":
        if score >= 8:
            personality = "Веселый и жизнерадостный 7-классник, который ещё ни от чего не устал! 😊"
        elif 5 <= score <= 7:
            personality = "Серьезный лицеист, готовящийся к ОГЭ! 📚"
        elif 3 <= score <= 4:
            personality = "'Устал, но скоро лето' - вы задумчивый 10-классник, готовящийся к ИКР! 🤔"
        else:
            personality = "Ваш девиз: 'Поскорей бы сдать ЕГЭ и выпуститься! Вы держитесь на 3-х часовом сне последние несколько лет' 😅"

        save_result_to_file(
            username=user.username,
            quiz_title=quiz.title if quiz else "Неизвестный тест",
            score=score,
            total=total,
            personality=personality
        )

    return templates.TemplateResponse("result.html", {
        "request": request,
        "user": user,
        "score": score,
        "total": total,
        "percentage": int((score / total) * 100) if total > 0 else 0,
        "personality": personality,
        "quiz_title": quiz.title if quiz else ""
    })




def save_result_to_file(username: str, quiz_title: str, score: int, total: int, personality: str = None):
    """Сохраняет результаты теста в файл results.txt"""
    # Проверяем, существует ли файл
    file_exists = os.path.exists("results.txt")

    with open("results.txt", "a", encoding="utf-8") as f:
        # Если файл только создается, добавляем заголовок
        if not file_exists:
            f.write("=== РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ===\n")
            f.write(f"Дата начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Пользователь: {username}\n\n")

        f.write(f"Тест: {quiz_title}\n")
        f.write(f"Дата прохождения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Результат: {score} из {total} ({int((score / total) * 100)}%)\n")
        if personality:
            f.write(f"Характеристика: {personality}\n")
        f.write("-" * 40 + "\n")



@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    results = db.query(QuizResult).filter(QuizResult.user_id == user.id).order_by(QuizResult.id.desc()).all()
    best_score = max([r.score for r in results], default=0) if results else 0

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "results": results,
        "best_score": best_score,
        "total_quizzes": len(results)
    })


# В самом начале приложения добавляем очистку файла
if __name__ == "__main__":
    if os.path.exists("results.txt"):
        os.remove("results.txt")
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
