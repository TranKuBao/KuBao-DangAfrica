FROM python:3.10

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP run.py
ENV DEBUG True

COPY requirements.txt .

# install python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Cài Ruby và WPScan
RUN apt-get update && \
    apt-get install -y ruby-full build-essential libcurl4-openssl-dev libxml2 libxml2-dev libxslt1-dev zlib1g-dev git && \
    gem install wpscan

COPY env.sample .env

WORKDIR /app
COPY . .

RUN mkdir -p /app/migrations/versions
RUN flask db migrate
RUN flask db upgrade
#RUN flask gen_api

# gunicorn
CMD ["gunicorn", "--config", "gunicorn-cfg.py", "run:app"]
