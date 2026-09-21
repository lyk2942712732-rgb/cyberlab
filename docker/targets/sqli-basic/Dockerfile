FROM python:3.12-alpine
WORKDIR /lab
COPY app.py .
RUN adduser -D -u 10001 lab
USER lab
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=10s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"
CMD ["python", "app.py"]
