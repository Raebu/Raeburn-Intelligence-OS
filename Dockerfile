FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV RIOS_DATABASE_URL=sqlite:////data/raeburn_intelligence.db
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "intelligence_os.main:app", "--host", "0.0.0.0", "--port", "8000"]
