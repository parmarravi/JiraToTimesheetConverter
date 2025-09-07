# Use official Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Expose port
EXPOSE 8080

# Run app
CMD ["python3",  "app.py"]
