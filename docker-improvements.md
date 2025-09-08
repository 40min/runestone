# Docker Configuration Improvements

This document outlines recommended improvements for the Runestone project's Docker configuration based on security, performance, and best practices analysis.

## Security Improvements

### 1. Run Containers as Non-Root User

**Issue**: Both [`Dockerfile.backend`](Dockerfile.backend) and [`Dockerfile.frontend`](Dockerfile.frontend) run containers as root, which is a security risk.

**Recommendation**: Add user creation and switching in both Dockerfiles:

```dockerfile
# In Dockerfile.backend (after WORKDIR /app)
RUN groupadd -r runestone && useradd -r -g runestone runestone
RUN chown -R runestone:runestone /app
USER runestone

# In Dockerfile.frontend (after copying nginx config)
RUN addgroup -g 101 -S nginx
RUN adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx
USER nginx
```

### 2. Tighten Content Security Policy

**Issue**: Current CSP in [`frontend/nginx.conf`](frontend/nginx.conf#L32) is overly permissive with `'unsafe-inline'`.

**Recommendation**: Restrict CSP to specific domains:

```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' http://backend:8000" always;
```

### 3. Add Resource Limits

**Issue**: No memory/CPU limits defined in [`docker-compose.yml`](docker-compose.yml).

**Recommendation**: Add resource constraints:

```yaml
services:
  backend:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  frontend:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 128M
        reservations:
          cpus: '0.1'
          memory: 64M
```

## Configuration Issues

### 4. Missing Environment Variables

**Issue**: [`docker-compose.yml`](docker-compose.yml#L11-L15) only includes OpenAI variables but missing `GEMINI_API_KEY`, despite backend supporting Gemini provider.

**Recommendation**: Add missing environment variable:

```yaml
environment:
  - LLM_PROVIDER=${LLM_PROVIDER}
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - OPENAI_MODEL=${OPENAI_MODEL}
  - GEMINI_API_KEY=${GEMINI_API_KEY}
  - VERBOSE=${VERBOSE}
```

### 5. Remove Unused Volume

**Issue**: Volume `runestone-data` is defined in [`docker-compose.yml`](docker-compose.yml#L40) but never used.

**Recommendation**: Remove the unused volume definition or implement it if needed for data persistence.

### 6. Make CORS Origins Configurable

**Issue**: CORS origins are hard-coded in [`src/runestone/api/main.py`](src/runestone/api/main.py#L40).

**Recommendation**: Make CORS origins configurable through environment variables:

```python
# In config.py
allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

# In main.py
allow_origins=settings.allowed_origins.split(",")
```

## Performance & Best Practices

### 7. Add Health Checks

**Issue**: No health checks defined for services, despite backend having [`/api/health`](src/runestone/api/endpoints.py#L111) endpoint.

**Recommendation**: Add health checks to docker-compose.yml:

```yaml
services:
  backend:
    # ... existing config ...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  frontend:
    # ... existing config ...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 8. Implement Multi-Stage Build for Backend

**Issue**: [`Dockerfile.backend`](Dockerfile.backend) could benefit from separating build dependencies.

**Recommendation**: Use multi-stage build to reduce final image size:

```dockerfile
# Build stage
FROM python:3.13-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --user -e .

# Production stage
FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY src/ ./src/
COPY res/ ./res/
ENV PATH=/root/.local/bin:$PATH
```

### 9. Add Nginx Optimizations

**Issue**: Missing gzip compression and request size limits in [`frontend/nginx.conf`](frontend/nginx.conf).

**Recommendation**: Add performance optimizations:

```nginx
# Add to nginx.conf
gzip on;
gzip_vary on;
gzip_min_length 1024;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

client_max_body_size 10M;
```

### 10. Add Container Labels

**Issue**: No metadata labels for better container organization.

**Recommendation**: Add labels to both Dockerfiles:

```dockerfile
LABEL maintainer="runestone-team"
LABEL version="1.0.0"
LABEL description="Runestone Swedish textbook analysis service"
LABEL org.opencontainers.image.source="https://github.com/your-org/runestone"
```

## Minor Issues

### 11. Environment File Handling

**Issue**: Manual environment variable setting required.

**Recommendation**: Use `.env` file in docker-compose.yml:

```yaml
# Add to docker-compose.yml
env_file:
  - .env
```

### 12. Logging Configuration

**Issue**: No specific logging setup for containers.

**Recommendation**: Add logging configuration:

```yaml
services:
  backend:
    # ... existing config ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  frontend:
    # ... existing config ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Priority Implementation Order

1. **High Priority (Security)**: Items #1, #2, #3, #4
2. **Medium Priority (Functionality)**: Items #5, #6, #7
3. **Low Priority (Optimization)**: Items #8, #9, #10, #11, #12

## Implementation Notes

- Test all changes in a development environment first
- Consider implementing changes incrementally
- Update documentation and deployment scripts accordingly
- Verify that security changes don't break existing functionality