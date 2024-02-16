FROM python:3.11-slim

RUN mkdir django-simple-worksite
WORKDIR django-simple-worksite

ADD requirements/prod.txt /django-simple-worksite/requirements.txt
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y curl && apt-get clean

ADD . /django-simple-worksite/
ADD .env.docker /django-simple-worksite/.env

RUN mkdir log/

CMD sleep 7; python manage.py makemigrations; python manage.py migrate; python manage.py collectstatic --no-input; \
gunicorn worksite.wsgi:application -c /django-simple-worksite/gunicorn.conf.py
