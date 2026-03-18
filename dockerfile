# Use a slim Python image for faster builds
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies for MySQL (needed for pymysql/mysqlclient)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements first (to cache layers and build faster)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port FastAPI runs on
EXPOSE 8000

# Start the application. 
# We use 0.0.0.0 so it's accessible outside the container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
