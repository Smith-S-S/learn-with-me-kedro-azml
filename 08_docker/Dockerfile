# =============================================================================
# Dockerfile for the House Price API (Kedro pipeline + FastAPI)
# =============================================================================
# A Dockerfile is a RECIPE. Each line is one instruction, and Docker follows
# them top to bottom to build an "image" -- a frozen, complete computer that
# contains your code, Python, and every library, all at fixed versions.
#
# Copy this file to the house-price/ folder to build it:
#     copy 08_docker\Dockerfile house-price\
#     cd house-price
#     docker build -t house-price-api:1.0 .
#
# WHY TWO STAGES?
# This is a "multi-stage build". We use a big, fully-equipped image to INSTALL
# the libraries, then copy only the finished result into a small, clean image.
# The compilers and build junk stay behind.
# Result: a smaller image that ships less software an attacker could abuse.
# =============================================================================


# -----------------------------------------------------------------------------
# STAGE 1: "builder" -- where we install the Python libraries
# -----------------------------------------------------------------------------
# FROM chooses the starting point. We are NOT starting from an empty computer;
# we start from one Microsoft already prepared with Python 3.12 on Azure Linux.
#
# WHY mcr.microsoft.com and not Docker Hub?
#   MCR = Microsoft Container Registry. Companies prefer it because:
#     * Microsoft patches these images for security
#     * Docker Hub rate-limits anonymous pulls, which breaks CI builds
#     * Many corporate firewalls allow MCR but block Docker Hub outright
#
# WHY pin a version instead of using :latest?
#   ":latest" means "whatever is newest today". Your build would quietly change
#   under you, and a build that worked last week could fail today for no visible
#   reason. Pinning makes builds REPRODUCIBLE.
FROM mcr.microsoft.com/azurelinux/base/python:3.12 AS builder

# Create and use a virtual environment. Copying one self-contained folder to
# stage 2 is far simpler than hunting down installed files across the system.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

# COPY ONLY requirements.txt FIRST -- this looks odd but it is the single most
# important speed trick in Docker.
#
# WHY: Docker caches each step. If a file a step depends on has not changed,
# Docker reuses the cached result instead of redoing the work. Installing
# libraries is slow (minutes); your code changes constantly.
#
# By copying requirements.txt alone and installing BEFORE copying the code,
# editing main.py does NOT trigger a reinstall of pandas and scikit-learn.
# If we copied everything first, every single code edit would reinstall
# everything. Minutes wasted, every build.
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
# --no-cache-dir tells pip not to keep its download cache. We will never install
# anything again inside this image, so the cache is pure dead weight.


# -----------------------------------------------------------------------------
# STAGE 2: "runtime" -- the actual image we ship
# -----------------------------------------------------------------------------
# We start clean from the same small base. Nothing from stage 1 comes along
# except what we explicitly copy.
FROM mcr.microsoft.com/azurelinux/base/python:3.12 AS runtime

# Bring over ONLY the finished virtual environment. The compilers, pip cache,
# and build tools from stage 1 are all left behind.
ENV VIRTUAL_ENV=/opt/venv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# --- Python behaviour settings ---
# PYTHONDONTWRITEBYTECODE: skip .pyc files. They just bloat the image.
# PYTHONUNBUFFERED: print logs immediately instead of holding them in a buffer.
#   WITHOUT THIS, your logs appear late or vanish when a container crashes --
#   a genuinely painful thing to debug. Always set it.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# --- Run as a NON-ROOT user ---
# By default a container runs as root. If someone breaks into your app, they are
# root inside the container, which is a much better starting point for escaping
# to the host machine. Creating a plain user removes that advantage cheaply.
# Many companies (and Kubernetes policies) REQUIRE this.
#
# NOTE: Azure Linux is a MINIMAL image, so `useradd` is not installed by default
# -- it lives in the shadow-utils package. `tdnf` is Azure Linux's package
# manager (the equivalent of apt-get on Ubuntu or yum on RedHat).
# We clean the package cache in the same RUN so it does not become a layer.
RUN tdnf install -y shadow-utils && \
    tdnf clean all && \
    useradd --create-home --shell /bin/bash appuser

# Copy the project in. .dockerignore controls what is excluded (see that file --
# it is what keeps .venv and data out of the image).
COPY --chown=appuser:appuser . .

USER appuser

# Tell readers which port the app uses. This is DOCUMENTATION only -- it does
# not actually open the port. You still need -p 8000:8000 when running.
EXPOSE 8000

# --- Health check ---
# Docker will run this command periodically and mark the container "unhealthy"
# if it fails. This is the same /health endpoint APIM and Kubernetes use.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# --- The command that runs when the container starts ---
# --host 0.0.0.0 is ESSENTIAL and catches everyone out once.
#   127.0.0.1 means "only accept calls from inside this container" -- so your
#   API would be invisible from outside and appear completely broken.
#   0.0.0.0 means "accept calls from outside too". You need this in Docker.
#
# No --reload here: that is a development convenience that watches for file
# changes. In production it wastes memory and can restart at bad moments.
CMD ["uvicorn", "house_price.main:app", "--host", "0.0.0.0", "--port", "8000"]
