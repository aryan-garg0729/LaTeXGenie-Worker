FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        ruby-full \
        build-essential \
        curl \
        pandoc \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install AnyStyle CLI
RUN gem install anystyle-cli && gem install anystyle

# (Optional) Verify AnyStyle installation
RUN anystyle --version

# Set working directory
WORKDIR /app

# Copy only LaTeXGenie-Core first to leverage caching
COPY LaTeXGenie-Core/ LaTeXGenie-Core/

# Install dependencies from LaTeXGenie-Core
RUN pip install --no-cache-dir ./LaTeXGenie-Core[full]

# Run model downloader early (cached if models don’t change)
RUN python LaTeXGenie-Core/scripts/download_models_hf.py

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
