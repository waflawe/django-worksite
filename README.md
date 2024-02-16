# Worksite
Проект простого сайта для поиска работы Worksite. 
Написан на языке Python при помощи фреймворка Django, библиотек celery, redis. 
Используемая СУБД - PostgreSQL.

## Установка
```commandline
git clone https://github.com/waflawe/django-worksite.git
cd django-worksite
```

### Запуск через Docker
```commandline
docker-compose up
```
Переходим на http://127.0.0.1:80 и наслаждаемся.

### Запуск локально
При локальном запуске вам нужно предварительно создать файл с переменными окружения .env 
по примеру файла .env.docker в репозитории.
```commandline
python -m venv venv
source venv/bin/activate
pip install -r requirements/dev.txt
redis-server
```
```commandline
source venv/bin/activate
celery -A worksite.celery_setup:app worker --loglevel=info
```
```commandline
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
python manage.py runserver 0.0.0.0:80
```
Переходим на http://127.0.0.1:80 и наслаждаемся.
