from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import users
from database import models, crud
from database.db import SessionLocal, engine
from database.schemas import UserCreate, TaskCreate, User

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

TOKEN_EXPIRE = 30

origins = [
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.put("/task/create")
def create_task(task: TaskCreate, user: User = Depends(users.get_current_user), db: Session = Depends(get_db)):
    """Создаёт новую задачу, либо возвращает ошибку:
        400, если данные задачи некорректны
        500, если возникла проблема при сохранении
    """
    task = users.create_task(db, task, user.id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error while saving task",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return task


@app.put("/task/update")
def update_task(task_id: int,
                task: TaskCreate,
                user: User = Depends(users.get_current_user),
                db: Session = Depends(get_db)):
    """Обновляет поля задачи, либо возвращает ошибку:
        404, если задача не найдена
        400, если данные задачи некорректны
    """
    result = crud.update_task(db, task_id, task)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
            headers={"WWW-Authenticate": "Bearer"}
        )


@app.post("/task/history")
def get_task_history(task_id: int, user: User = Depends(users.get_current_user), db: Session = Depends(get_db)):
    """Возвращает историю изменений задачи"""
    return crud.get_history(db, task_id)


@app.delete("/task/delete")
def delete_task(task_id: int, user: User = Depends(users.get_current_user), db: Session = Depends(get_db)):
    """Удаляет задачу по её id, либо возвращает 404, если задача не найдена"""
    result = crud.delete_task(db, task_id=task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
            headers={"WWW-Authenticate": "Bearer"}
        )


@app.post("/user/tasks")
def read_tasks(db: Session = Depends(get_db), user: User = Depends(users.get_current_user)):
    """Возвращает все задачи для текущего пользователя"""
    return crud.get_tasks(db, user.id)


@app.post("/user/create")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Создаёт нового пользователя"""
    return users.perform_registration(db, user)


@app.post("/login")
def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """Авторизирует пользователя и возвращает токен, либо возвращает ошибку 401"""
    user = users.authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token_expires = timedelta(minutes=TOKEN_EXPIRE)
    access_token = users.create_access_token(
        data={"sub": user.login}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
