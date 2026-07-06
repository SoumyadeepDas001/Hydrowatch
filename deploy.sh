#!/bin/bash
# Exit on any error
set -e

echo "=================================================="
# Get current GCP project configuration
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")

if [ -z "$PROJECT_ID" ]; then
  echo "Error: No GCP Project configured. Run 'gcloud config set project [PROJECT_ID]' first."
  exit 1
fi

echo "Deploying HydroWatch pipeline to Cloud Run..."
echo "GCP Project ID: $PROJECT_ID"
echo "=================================================="

# Build image using Cloud Build
echo "\n>>> Submitting container build to Google Cloud Build..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/hydrowatch

# Deploy image to Cloud Run
echo "\n>>> Deploying service to Google Cloud Run..."
gcloud run deploy hydrowatch \
  --image gcr.io/$PROJECT_ID/hydrowatch \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080

echo "\n=================================================="
echo "HydroWatch Multi-Agent System Deployed Successfully!"
echo "=================================================="
