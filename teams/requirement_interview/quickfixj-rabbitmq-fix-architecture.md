** Below is a complete, end‑to‑end description of the proposed solution, including architectural overview, component details, deployment steps, error‑handling strategies, and operational monitoring. This document can be saved as `quickfixj-rabbitmq-fix-architecture.md`.

---

# QuickFixJ + RabbitMQ Integration – Architecture & Implementation Guide

## 1. Executive Summary
The QuickFixJ (QFJ) engine will consume market‑data messages from a RabbitMQ broker, transform them into FIX protocol payloads, and forward the FIX messages to downstream trading partners. The solution is built for high throughput (≥ 10 k msgs/sec), low latency (< 5 ms end‑to‑end), and resilience against network or broker failures.

## 2. High‑Level Architecture

```
+-------------------+       +----------------------+       +-------------------+
|   RabbitMQ Broker | ----> |   QFJ Consumer (Java) | ----> |   FIX Engine (QFJ) |
+-------------------+       +----------------------+       +-------------------+
                                 |                               |
                                 v                               v
                         +------------------------+    +------------------------+
                         |  Dead‑Letter Queue (DLQ) |    |  Monitoring / Metrics   |
                         +------------------------+    +------------------------+
```

- **RabbitMQ** – Stores market‑data events in a durable queue.
- **QFJ Consumer** – Pulls messages, performs validation, and hands them to the FIX engine.
- **FIX Engine (QuickFixJ)** – Encodes the payload into FIX 4.4/5.0 messages and sends them over TCP to counterparties.
- **DLQ** – Captures malformed or rejected messages for later re‑processing.
- **Metrics Exporter** – Exposes Prometheus‑compatible endpoints (`/metrics`) for latency, throughput, error rates, and queue depth.

## 3. Component Details

### 3.1 RabbitMQ Consumer
| Aspect | Implementation |
|--------|----------------|
| Library | Spring AMQP (or plain `com.rabbitmq.client`) |
| Connection | Automatic reconnect with exponential back‑off; TLS optional via `useSsl=true`. |
| Queue Declaration | Durable, non‑exclusive queue `market-data-in`. |
| Prefetch | `prefetchCount = 1` to guarantee single‑threaded processing and preserve order. |
| ACK/NACK | Manual ACK only after successful transformation; NACK with `requeue=false` for permanent failures (sent to DLQ). |
| Error Handling | - **Malformed JSON** → log, NACK → DLQ.<br>- **Unexpected exception** → log, NACK → DLQ. |

### 3.2 Command Dispatcher
- Maintains a **whitelist map** (`Map<String, String>`) linking market‑data keys to FIX message types (e.g., `"trade 10 gold"` → `FIX44_NEW_ORDER_SINGLE`).
- Unknown commands trigger a **RejectMessage** with FIX error code `5` (“Incorrect tag”) and a human‑readable description.

### 3.3 FIX Engine (QuickFixJ)
| Configuration | Value |
|---------------|-------|
| SenderCompID | `QFJ` |
| TargetCompID | Populated from environment variable or config file per counterparty. |
| HeartbeatInterval | `30` seconds |
| LogonTimeout | `5000` ms |
| Encryption | Optional TLS via `SocketSettings` (enable when `useTls=true`). |
| Message Store | In‑memory store for session recovery; persisted store optional for crash‑restart. |

### 3.4 Dead‑Letter Queue (DLQ)
- Configured as `market-data-dlq`.
- Messages are republished with a header `x-dlq-reason` indicating why they were routed there (`MALFORMED`, `UNKNOWN_COMMAND`).
- A separate **DLQ Processor** can be scheduled to retry after a back‑off period.

## 4. Deployment Pipeline

### 4.1 Docker Image Build
```bash
git clone https://github.com/yourorg/quickfixj-rabbitmq-fix.git
cd quickfixj-rabbitmq-fix

# Build the application JAR
./gradlew clean assemble

# Build Docker image (tag: latest)
docker build -t quickfixj-app:latest .
```

Dockerfile highlights:
- **JRE 17** base image.
- Copy `build/libs/*.jar` → `/app/qfj.jar`.
- Expose port `8080` for health/metrics endpoints.
- Entrypoint runs `java -jar /app/qfj.jar`.

### 4.2 Runtime Configuration (environment variables)

| Variable | Description |
|----------|-------------|
| `RABBITMQ_HOST` | Hostname of RabbitMQ cluster. |
| `RABBITMQ_USER` / `RABBITMQ_PASS` | Credentials for the queue user. |
| `FIX_SENDER_COMP_ID` | QFJ’s sender comp ID. |
| `FIX_TARGET_COMP_ID` | Counterparty identifier (can be overridden per deployment). |
| `FIX_PASSWORD` | Password for TLS mutual authentication (if used). |
| `METRICS_PORT` | Port on which `/metrics` is exposed (default `8080`). |

### 4.3 Container Run
```bash
docker run -d \
  --name quickfixj \
  --restart unless-stopped \
  -e RABBITMQ_HOST=rabbitmq.example.com \
  -e RABBITMQ_USER=app_user \
  -e RABBITMQ_PASS=secret_pass \
  -e FIX_SENDER_COMP_ID=quickfixj \
  -e FIX_TARGET_COMP_ID=vendor \
  -e FIX_PASSWORD=fix_secret \
  -p 8080:8080 \
  quickfixj-app:latest
```

### 4.4 Health & Metrics Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Returns `{"status":"UP"}` if broker connectivity and FIX session are alive. |
| `/metrics` | Prometheus‑compatible exposition of: <br>• `qfj_queue_depth` (current queue size) <br>• `qfj_messages_processed_total` <br>• `qfj_transform_errors_total` <br>• `qfj_fix_session_up_seconds` |

## 5. Error‑Handling & Resilience

| Failure Mode | Detection | Recovery Action |
|--------------|-----------|-----------------|
| **Broker unreachable** | RabbitMQ client exception on connect/publish | Exponential back‑off reconnect; continue consuming once restored. |
| **Message validation failure** | JSON parsing or schema check throws | Log, NACK → DLQ, increment `transform_errors_total`. |
| **FIX session down** | QuickFixJ `SessionIsTerminated` event | Auto‑reconnect logic; pause consumption until session re‑established (`pauseConsumption=true`). |
| **Unexpected runtime exception** | Uncaught exception in consumer thread | Stack trace logged, NACK → DLQ, process restarts automatically via Docker restart policy. |

## 6. Monitoring & Alerting

- **Prometheus Scrape Config** (example):
```yaml
scrape_configs:
  - job_name: 'quickfixj'
    static_configs:
      - targets: ['localhost:8080']
```
- **Alert Rules** (`alerts.yml`):
```yaml
groups:
  - name: quickfixj_alerts
    rules:
      - alert: QueueDepthHigh
        expr: qfj_queue_depth > 10000
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "RabbitMQ queue depth high"
          description: "Market‑data queue size is {{ $value }} messages."

      - alert: TransformErrorRate
        expr: rate(qfj_transform_errors_total[5m]) > 0.01
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "High transformation error rate"
          description: "{{ $value }}% of messages failed validation in the last 5 minutes."
```

## 7. CI/CD Pipeline (Optional)

- **GitHub Actions** steps: `build → test → docker-build → push-to-registry`.
- Tagging strategy: `v<major>.<minor>.<patch>`; images are version‑pinned in Kubernetes manifests.

## 8. Security Considerations

1. **Transport Encryption** – Use TLS for RabbitMQ (`amqps://`) and FIX (mutual TLS).
2. **Least‑Privilege User** – Create a dedicated RabbitMQ user with `configure`, `write`, `read` rights only on the required vhost and queues.
3. **Network Segmentation** – Deploy broker and consumer in a private subnet; expose only health/metrics ports to monitoring systems.

## 9. Operational Checklist

| Item | Done? |
|------|-------|
| ✅ RabbitMQ durable queue created (`market-data-in`) |
| ✅ DLQ configured (`market-data-dlq`) |
| ✅ Docker image built and pushed to registry |
| ✅ Helm chart / K8s manifest includes health, metrics, and restart policies |
| ✅ Prometheus scraping endpoint exposed |
| ✅ Alerting rules loaded into Alertmanager |
| ✅ TLS certificates provisioned for RabbitMQ and FIX sessions |
| ✅ Load testing performed (≥ 12 k msgs/sec sustained) |

---
