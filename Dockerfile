FROM python:3.12-slim

# Install system dependencies: poppler-utils, Ruby, and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        ruby-full \
        build-essential \
        curl \
        pandoc \
    && rm -rf /var/lib/apt/lists/*

# Install AnyStyle CLI and core gem
RUN gem install anystyle-cli && gem install anystyle

# (Optional) Verify installation
RUN anystyle --version

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . .

# Set the default command (adjust as needed)
CMD ["python", "run.py"]
