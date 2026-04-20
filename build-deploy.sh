#!/bin/bash

# Build & Deploy to Kubernetes Script - Version 2.0 (New Structure)
# Sử dụng: ./build-deploy.sh [backend|frontend|all] [minikube|docker]

set -e

# --- CẤU HÌNH ĐƯỜNG DẪN ---
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"
K8S_DIR="$PROJECT_ROOT/k8s"
TARGET="${1:-all}"
RUNTIME="${2:-minikube}"

echo "🚀 Building and deploying crypto system to Kubernetes"
echo "   Target: $TARGET"
echo "   Runtime: $RUNTIME"

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

load_to_minikube() {
    print_step "Loading images to minikube..."
    minikube image load crypto-backend:latest
    minikube image load crypto-frontend:latest
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
    
    # 3. Ứng dụng chính
    kubectl apply -f "$K8S_DIR/03-backend-deployment.yaml"
    kubectl apply -f "$K8S_DIR/04-frontend-deployment.yaml"
    # Thêm FastAPI nếu có file riêng
    if [ -f "$K8S_DIR/fastapi.yaml" ]; then kubectl apply -f "$K8S_DIR/fastapi.yaml"; fi
    
    print_success "Deployment completed"
}

wait_for_deployment() {
    print_step "Waiting for deployments to be ready..."
    # Lưu ý: Thay đổi tên deployment nếu trong file yaml bạn đặt tên khác
    kubectl rollout status deployment/backend -n crypto-system --timeout=3m || echo "Backend wait timeout"
    kubectl rollout status deployment/frontend -n crypto-system --timeout=3m || echo "Frontend wait timeout"
    print_success "Check rollout status complete"
}

# --- LOGIC CHÍNH ---

case $TARGET in
    backend)  build_backend ;;
    frontend) build_frontend ;;
    all)      build_backend; build_frontend ;;
    *)        print_error "Unknown target: $TARGET. Use: backend|frontend|all" ;;
esac

if [ "$RUNTIME" = "minikube" ]; then
    load_to_minikube
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