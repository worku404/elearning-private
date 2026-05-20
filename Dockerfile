from python:3.12.3
#set environment varialbles

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

#SET WORK DIRECTORY
WORKDIR /code
#install dependencies

RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

#Copy the django project
COPY . .
RUN sed -i 's/\r$//' /code/wait-for-it.sh && chmod +x /code/wait-for-it.sh

