#!/bin/bash

# Build & Deploy to Kubernetes Script - Version 2.0 (New Structure)
# Sử dụng:
#   ./build-deploy.sh [backend|frontend|crawler|spark|ml|all] [minikube-docker|docker|load]
#
# Khuyến nghị cho WSL/Minikube: minikube-docker
# Cách này build image trực tiếp vào Docker daemon của Minikube, tránh `minikube image load`
# vì image Spark lớn có thể làm WSL đơ/crash khi copy tar image.

set -e

# --- CẤU HÌNH ĐƯỜNG DẪN ---
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"
K8S_DIR="$PROJECT_ROOT/k8s"
TARGET="${1:-all}"
RUNTIME="${2:-minikube-docker}"

echo "🚀 Building and deploying crypto system to Kubernetes"
echo "   Target: $TARGET"
echo "   Runtime: $RUNTIME"

if [ "$RUNTIME" = "minikube-docker" ]; then
    echo "▶ Using Minikube Docker daemon, no image load needed..."
    eval "$(minikube docker-env)"
fi

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_step() { echo -e "${BLUE}▶ $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; exit 1; }

# --- CÁC HÀM XỬ LÝ ---

build_backend() {
    print_step "Building backend image..."
    # Sử dụng Dockerfile trong folder docker/ và context là PROJECT_ROOT
    docker build -f "$DOCKER_DIR/Dockerfile.backend-k8s" \
        -t crypto-backend:latest "$PROJECT_ROOT" || print_error "Backend build failed"
    print_success "Backend image built"
}

build_frontend() {
    print_step "Building frontend image..."
    # Sử dụng Dockerfile trong folder docker/ và context là PROJECT_ROOT
    docker build -f "$DOCKER_DIR/Dockerfile.frontend-k8s" \
        -t crypto-frontend:latest "$PROJECT_ROOT" || print_error "Frontend build failed"
    print_success "Frontend image built"
}

build_crawler() {
    print_step "Building crawler image..."
    docker build -f "$DOCKER_DIR/Dockerfile.crawler" \
        -t crypto-crawler:latest "$PROJECT_ROOT" || print_error "Crawler build failed"
    print_success "Crawler image built"
}

build_spark() {
    print_step "Building spark image..."
    docker build -f "$DOCKER_DIR/Dockerfile.spark" \
        -t crypto-spark:latest "$PROJECT_ROOT" || print_error "Spark build failed"
    print_success "Spark image built"
}

build_ml() {
    print_step "Building ML trainer image..."
    docker build -f "$DOCKER_DIR/Dockerfile.ml-trainer" \
        -t crypto-ml-trainer:latest "$PROJECT_ROOT" || print_error "ML trainer build failed"
    print_success "ML trainer image built"
}

load_to_minikube() {
    print_step "Loading images to minikube..."
    minikube image load crypto-backend:latest
    minikube image load crypto-frontend:latest
    minikube image load crypto-crawler:latest
    minikube image load crypto-spark:latest
    minikube image load crypto-ml-trainer:latest
    print_success "Images loaded to minikube"
}

deploy() {
    print_step "Deploying to Kubernetes từ folder $K8S_DIR..."
    
    # 1. Hạ tầng cơ bản
    kubectl apply -f "$K8S_DIR/00-namespace.yaml"
    kubectl apply -f "$K8S_DIR/01-configmap.yaml"
    kubectl apply -f "$K8S_DIR/02-secret.yaml"
    
    # 2. Database & Broker (Nếu bạn chưa chạy)
    kubectl apply -f "$K8S_DIR/postgres.yaml"
    kubectl apply -f "$K8S_DIR/kafka.yaml"
    kubectl apply -f "$K8S_DIR/minio.yaml"
    kubectl apply -f "$K8S_DIR/influxdb.yaml"
    kubectl apply -f "$K8S_DIR/05-init-jobs.yaml"
    
    # 3. Ứng dụng chính và pipeline
    kubectl apply -f "$K8S_DIR/03-backend-deployment.yaml"
    kubectl apply -f "$K8S_DIR/04-frontend-deployment.yaml"
    kubectl apply -f "$K8S_DIR/06-crawler-deployment.yaml"
    kubectl apply -f "$K8S_DIR/07-spark-speed-deployment.yaml"
    kubectl apply -f "$K8S_DIR/08-spark-batch-cronjob.yaml"
    kubectl apply -f "$K8S_DIR/09-ml-train-cronjob.yaml"
    
    print_success "Deployment completed"
}

wait_for_deployment() {
    print_step "Waiting for deployments to be ready..."
    # Lưu ý: Thay đổi tên deployment nếu trong file yaml bạn đặt tên khác
    kubectl rollout status deployment/backend -n crypto-system --timeout=3m || echo "Backend wait timeout"
    kubectl rollout status deployment/frontend -n crypto-system --timeout=3m || echo "Frontend wait timeout"
    kubectl rollout status deployment/crawler -n crypto-system --timeout=3m || echo "Crawler wait timeout"
    kubectl rollout status deployment/spark-speed-layer -n crypto-system --timeout=3m || echo "Spark speed wait timeout"
    print_success "Check rollout status complete"
}

# --- LOGIC CHÍNH ---

case $TARGET in
    backend)  build_backend ;;
    frontend) build_frontend ;;
    crawler)  build_crawler ;;
    spark)    build_spark ;;
    ml)       build_ml ;;
    all)      build_backend; build_frontend; build_crawler; build_spark; build_ml ;;
    *)        print_error "Unknown target: $TARGET. Use: backend|frontend|crawler|spark|ml|all" ;;
esac

if [ "$RUNTIME" = "load" ]; then
    load_to_minikube
elif [ "$RUNTIME" = "minikube-docker" ]; then
    print_step "Images were built inside Minikube Docker daemon; skipping image load."
fi

read -p "Deploy to Kubernetes now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    deploy
    wait_for_deployment
    print_success "✅ Deployment complete!"
    echo -e "\nServices status:"
    kubectl get svc -n crypto-system
else
    print_step "Deployment cancelled."
fi
