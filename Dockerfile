FROM python:3

WORKDIR /usr/src/ace-of-spades

COPY requirements.txt config.jso[n] database.d[b] .git ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY cogs ./cogs
COPY utils ./utils

CMD [ "python", "main.py" ]