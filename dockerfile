# Dockerfile

FROM public.ecr.aws/lambda/python:3.11

# Set working directory
WORKDIR /var/task

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Set the Lambda handler (Python module path to handler object)
CMD ["app.app.handler"]
