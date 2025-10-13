FROM python:3.13.5

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /src

COPY chroma ./chroma
COPY meal_advisor.py ./meal_advisor.py
COPY chatbot.py ./chatbot.py
COPY .chainlit ./.chainlit

COPY requirements.txt .
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 8000

CMD ["chainlit", "run", "chatbot.py", "--host", "0.0.0.0", "--port", "8000"]