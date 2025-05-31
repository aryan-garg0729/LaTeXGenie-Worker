FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    ruby-full \
    build-essential \
    curl \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Install AnyStyle CLI
RUN gem install anystyle-cli && gem install anystyle

# (Optional) Verify AnyStyle installation
RUN anystyle --version

# Set working directory
WORKDIR /app

# Copy only latexgenie_core first to leverage caching
COPY latexgenie_core/ latexgenie_core/

# Install dependencies from latexgenie_core
RUN pip install --no-cache-dir ./latexgenie_core[full]

# Run model downloader early (cached if models don’t change)
RUN python latexgenie_core/scripts/download_models_hf.py

# Copy latexgenie_parser requirements and install separately
COPY latexgenie_parser/requirements.txt latexgenie_parser/
RUN pip install --no-cache-dir -r latexgenie_parser/requirements.txt

# Copy app requirements
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application (after all dependencies are cached)
COPY . .

# Set default command
CMD ["python", "run.py"]
