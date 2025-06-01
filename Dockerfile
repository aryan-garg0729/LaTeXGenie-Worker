# FROM python:3.12-slim

# # Install system dependencies
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#     poppler-utils \
#     ruby-full \
#     build-essential \
#     curl \
#     pandoc \
#     && rm -rf /var/lib/apt/lists/*

# # Install AnyStyle CLI
# RUN gem install anystyle-cli && gem install anystyle

# # Set working directory
# WORKDIR /app

# # Copy only latexgenie_core first to leverage caching
# COPY latexgenie_core/ latexgenie_core/

# # Install dependencies from latexgenie_core
# RUN pip install --no-cache-dir ./latexgenie_core[full]

# # Run model downloader early (cached if models don’t change)
# RUN python latexgenie_core/scripts/download_models_hf.py

# # Copy latexgenie_parser requirements and install separately
# COPY latexgenie_parser/requirements.txt latexgenie_parser/
# RUN pip install --no-cache-dir -r latexgenie_parser/requirements.txt

# # Copy app requirements
# # COPY requirements.txt .
# # RUN pip install --no-cache-dir -r requirements.txt

# # Now copy the rest of the application (after all dependencies are cached)
# COPY . .

# # Set default command
# CMD ["python", "run.py"]




FROM python:3.12-slim

# Prevents Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures stdout/stderr is unbuffered
ENV PYTHONUNBUFFERED=1

# Install only needed system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ruby-full \
    curl \
    pandoc \
    poppler-utils \
    fontconfig \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    # ttf-mscorefonts-installer \
    libreoffice \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install AnyStyle CLI
RUN gem install --no-document anystyle-cli anystyle

# Set working directory
WORKDIR /app

# Copy only latexgenie_core first to leverage Docker layer caching
COPY latexgenie_core/ latexgenie_core/

# Install dependencies from latexgenie_core
RUN pip install --no-cache-dir ./latexgenie_core[full]

# Run model downloader early (cached if models don’t change)
RUN python latexgenie_core/scripts/download_models_hf.py

# Copy and install parser requirements
COPY latexgenie_parser/requirements.txt latexgenie_parser/
RUN pip install --no-cache-dir -r latexgenie_parser/requirements.txt

# Now copy the full app
COPY . .

# Final cleanup to reduce image size
RUN apt-get purge -y build-essential ruby-full && \
    apt-get autoremove -y && \
    rm -rf ~/.cache/pip ~/.gem /root/.cache

# Default command
CMD ["python", "run.py"]
