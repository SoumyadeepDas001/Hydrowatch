# Use standard python slim image
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements or setup files first
# Since we are deploying the local code directory, we copy requirements.txt or write dependencies
# Let's write requirements inline or copy the workspace
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set python path
ENV PYTHONPATH=/app

# Expose default Cloud Run port
EXPOSE 8080

# Run the Streamlit dashboard on the port exposed by Cloud Run
CMD ["streamlit", "run", "dashboard.py", "--server.port", "8080", "--server.address", "0.0.0.0"]
