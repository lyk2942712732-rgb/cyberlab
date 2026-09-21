FROM python:3.12-alpine
WORKDIR /lab
COPY app.py .
RUN adduser -D -u 10001 lab
USER lab
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=10s --start-period=10s --retries=5 \
    CMD /bin/busybox wget -q -T 5 -O /dev/null http://127.0.0.1:8000/health
CMD ["python", "app.py"]
