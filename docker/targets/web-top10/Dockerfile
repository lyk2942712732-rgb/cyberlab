ARG BASE_IMAGE=python:3.12-alpine
FROM ${BASE_IMAGE}
WORKDIR /lab
COPY app.py .
RUN id -u lab >/dev/null 2>&1 || adduser -D -u 10001 lab
USER lab
ARG LAB_SCENARIO
ENV LAB_SCENARIO=${LAB_SCENARIO}
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=10s --start-period=10s --retries=5 \
    CMD /bin/busybox wget -q -T 5 -O /dev/null http://127.0.0.1:8000/health
CMD ["python", "app.py"]
