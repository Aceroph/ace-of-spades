FROM python:3

WORKDIR /usr/src/ace-of-spades

RUN git clone https://github.com/Aceroph/ace-of-spades.git .
COPY config.jso[n] database.d[b] ./
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "main.py" ]