FROM python:3-slim

ARG REQ_TXT_PATH
ARG SCPT_TXT_PATH

# Not Truly Needed (Useful when switching between windows & Linux)
RUN apt-get update && apt-get install -y dos2unix

# Install dependencies
RUN mkdir -p "${DockerHOME}/scripts"
WORKDIR "${DockerHOME:-/home/app/}"
COPY "${SCPT_TXT_PATH}" ./scripts/
COPY "${REQ_TXT_PATH}" ./requirements.txt

# Not Truly Needed (Useful when switching between windows & Linux)
RUN dos2unix scripts/*.sh && \
    chmod +x scripts/*.sh

RUN bash -c "chmod +x scripts/install_req.sh"
RUN bash -c "scripts/install_req.sh"

# Expose the port where the Django app runs
EXPOSE 8000

# Start server
ENTRYPOINT ["/bin/bash", "-c"]
CMD ["chmod +x scripts/django_up.sh && scripts/django_up.sh"]
