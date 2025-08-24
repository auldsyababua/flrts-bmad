#!/bin/bash

# FLRTS-BMAD Production Startup Script
# Loads environment variables and starts the application

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting FLRTS-BMAD Production Server${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please copy .env.example.clean to .env and configure your settings"
    exit 1
fi

# Export all variables from .env file
export $(grep -v '^#' .env | xargs)

# Validate configuration
echo -e "${YELLOW}📋 Validating configuration...${NC}"
python scripts/validate_config.py --no-env

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Configuration validation failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration validated${NC}"

# Start the application
echo -e "${YELLOW}🔧 Starting Flask application on port ${PORT:-8000}...${NC}"
python main.py