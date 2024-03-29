# using ubuntu LTS version
FROM ubuntu:20.04 AS builder-image

# avoid stuck build due to user prompt
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install --no-install-recommends -y python3.9 python3.9-dev python3.9-venv python3-pip python3-wheel build-essential && \
	apt-get clean && rm -rf /var/lib/apt/lists/*

# create and activate virtual environment
# using final folder name to avoid path issues with packages
RUN python3.9 -m venv /home/app/venv
ENV PATH="/home/app/venv/bin:$PATH"
ENV ENVIRONMENT dev
ENV TESTING 0

# install requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir wheel
RUN pip3 install --no-cache-dir -r requirements.txt

FROM ubuntu:20.04 AS runner-image
RUN apt-get update && apt-get install --no-install-recommends -y python3.9 python3-venv && \
	apt-get clean && rm -rf /var/lib/apt/lists/*

# Run as root
# USER root

# create a user named "app" with a group also named "app":
RUN useradd --create-home -U app

# copy across virtual environment:
COPY --from=builder-image /home/app/venv /home/app/venv

RUN mkdir /home/app/web
WORKDIR /home/app/web

# Create directory structure needed for uploads directory to exist:
RUN mkdir -p /home/app/web/src/app/uploads

# supposed to recursively change owner and group for directory structure beneath web
# RUN chown -R app:app /home/app/web

# copy from host to container, done as user 'app' but files are still owner and group root:root
COPY --chown=app:app . /home/app/web

# change to the app user
USER app

EXPOSE 8000

# make sure all messages always reach console
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE 1
ENV ENVIRONMENT dev
ENV TESTING 0

# activate virtual environment
ENV VIRTUAL_ENV=/home/app/venv
ENV PATH="/home/app/venv/bin:$PATH"

# /dev/shm is mapped to shared memory and should be used for gunicorn heartbeat
# this will improve performance and avoid random freezes
CMD ["gunicorn", "--reload", "-b", "0.0.0.0:8000",  "-w", "4", "-k", "gevent", "--worker-tmp-dir", "/dev/shm", "app:app"]

