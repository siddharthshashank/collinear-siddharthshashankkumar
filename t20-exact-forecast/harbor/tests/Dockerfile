# Verifier image. Makes no network calls at run time and never sees the agent's container.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PIP_NO_CACHE_DIR=1
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
# the submitted code runs as this user, which cannot read /tests
RUN useradd --create-home --shell /bin/bash runner && mkdir -p /app /work /logs/verifier
COPY . /tests/
RUN chmod -R go-rwx /tests && chmod +x /tests/test.sh
WORKDIR /app