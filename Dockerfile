FROM docker.io/library/debian:bookworm-slim

ARG SSP_EXPORTER_GIT_REPO SSP_EXPORTER_BIND_PORT
ENV SSP_EXPORTER_GIT_REPO ${SSP_EXPORTER_GIT_REPO:-https://github.com/freefd/ssp-exporter}
ENV SSP_EXPORTER_BIND_PORT ${SSP_EXPORTER_BIND_PORT:-10032}

RUN apt update \
    && apt -y dist-upgrade \
    && apt -y install git locales python3 python3-pip python3-jsonschema python3-yaml python3-requests python3-lxml python3-schedule python3-prometheus-client \
    && echo 'C.UTF-8 UTF-8\nen_US.UTF-8 UTF-8\nru_RU.UTF-8 UTF-8\n' > /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && apt clean all \
    && git clone ${SSP_EXPORTER_GIT_REPO} /app \
    && bash -O extglob -c "rm -rfv /app/!(main.py|logger.py|requirements.txt|providers) /app/.*" \
    && pip3 install --break-system-packages -r /app/requirements.txt \
    && rm /app/requirements.txt

EXPOSE $SSP_EXPORTER_BIND_PORT
ENTRYPOINT ["python3", "/app/main.py"]