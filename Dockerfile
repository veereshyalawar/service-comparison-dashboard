FROM public.ecr.aws/docker/library/python:3.11-slim

# Install AWS Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY db_connection.py .
COPY service_comparison_dashboard.py .
COPY .streamlit .streamlit

# Lambda Web Adapter config
ENV AWS_LWA_PORT=8501
ENV AWS_LWA_READINESS_CHECK_PATH=/_stcore/health
ENV AWS_LWA_INVOKE_MODE=response_stream

# Streamlit config
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false

EXPOSE 8501

CMD ["streamlit", "run", "service_comparison_dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
