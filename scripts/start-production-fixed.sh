#!/bin/bash

# FLRTS-BMAD Production Startup Script (Fixed)
# Loads environment variables and starts the application

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting FLRTS-BMAD Production Server (Fixed)${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo "Please copy .env.example.clean to .env and configure your settings"
    exit 1
fi

# Export all variables from .env file
export $(grep -v '^#' .env | xargs)

# Disable verbose httpx logging to prevent recursion
export HTTPX_LOG_LEVEL=WARNING

# Validate configuration
echo -e "${YELLOW}📋 Validating configuration...${NC}"
python scripts/validate_config.py --no-env

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Configuration validation failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Configuration validated${NC}"

# Clear the log file for fresh start
> app.log

# Start the application
echo -e "${YELLOW}🔧 Starting Flask application on port ${PORT:-8000}...${NC}"
echo -e "${YELLOW}📝 Logs will be written to app.log${NC}"
echo -e "${YELLOW}🔕 HTTPx logging set to WARNING level to prevent recursion${NC}"

# Run with reduced logging verbosity
PYTHONWARNINGS="ignore::DeprecationWarning" python -u main.py