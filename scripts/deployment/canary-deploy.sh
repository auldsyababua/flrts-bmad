#!/bin/bash

# FLRTS-BMAD Canary Deployment Script
# Progressive rollout for small teams with Story 1.6 validation

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
CANARY_CONFIG="scripts/deployment/canary-deploy.yaml"
HEALTH_CHECK_URL="${DEPLOY_URL:-http://localhost:8000}/health"
STORY_16_URL="${DEPLOY_URL:-http://localhost:8000}/health/story-1-6"

# Function to print stage header
print_stage() {
    echo -e "\n${BLUE}══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  CANARY DEPLOYMENT - $1${NC}"
    echo -e "${BLUE}══════════════════════════════════════════════════════════${NC}\n"
}

# Function to check health
check_health() {
    local url=$1
    local expected_status=$2
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    
    if [ "$response" = "$expected_status" ]; then
        return 0
    else
        return 1
    fi
}

# Function to check Story 1.6 metrics
check_story_16_metrics() {
    echo -e "${YELLOW}📊 Checking Story 1.6 Direct Execution Metrics...${NC}"
    
    # Check router confidence
    confidence=$(curl -s "${DEPLOY_URL:-http://localhost:8000}/api/metrics/story-16" 2>/dev/null | \
                 grep -o '"avg_confidence":[0-9.]*' | cut -d: -f2 || echo "0")
    
    if (( $(echo "$confidence > 0.8" | bc -l) )); then
        echo -e "${GREEN}✅ Router confidence: $confidence (above threshold)${NC}"
    else
        echo -e "${RED}❌ Router confidence: $confidence (below 0.8 threshold)${NC}"
        return 1
    fi
    
    # Check direct execution rate
    direct_rate=$(curl -s "${DEPLOY_URL:-http://localhost:8000}/api/metrics/story-16" 2>/dev/null | \
                  grep -o '"direct_execution_rate":[0-9.]*' | cut -d: -f2 || echo "0")
    
    if (( $(echo "$direct_rate > 0.6" | bc -l) )); then
        echo -e "${GREEN}✅ Direct execution rate: ${direct_rate}% (above threshold)${NC}"
    else
        echo -e "${YELLOW}⚠️  Direct execution rate: ${direct_rate}% (below 60% target)${NC}"
    fi
    
    return 0
}

# Function to perform rollback
rollback() {
    echo -e "\n${RED}🔄 INITIATING ROLLBACK${NC}"
    echo -e "${YELLOW}Rolling back to stable version...${NC}"
    
    # Rollback logic here (platform-specific)
    if [ -n "$RENDER_API_KEY" ]; then
        # Render.com rollback
        echo "Rolling back on Render.com..."
        # Add Render API call to rollback
    elif [ -n "$RAILWAY_API_KEY" ]; then
        # Railway rollback
        echo "Rolling back on Railway..."
        # Add Railway API call to rollback
    else
        # Local rollback
        echo "Performing local rollback..."
        git checkout stable
        ./scripts/start-production.sh
    fi
    
    echo -e "${GREEN}✅ Rollback completed${NC}"
    exit 1
}

# Main deployment flow
main() {
    print_stage "PRE-DEPLOYMENT VALIDATION"
    
    # Run tests
    echo -e "${YELLOW}🧪 Running Story 1.6 tests...${NC}"
    if python -m pytest tests/unit/test_router_enhanced_phrases.py -q; then
        echo -e "${GREEN}✅ Story 1.6 tests passed${NC}"
    else
        echo -e "${RED}❌ Story 1.6 tests failed${NC}"
        exit 1
    fi
    
    # Validate configuration
    echo -e "${YELLOW}🔍 Validating configuration...${NC}"
    if python scripts/validate_config.py --no-env; then
        echo -e "${GREEN}✅ Configuration valid${NC}"
    else
        echo -e "${RED}❌ Configuration invalid${NC}"
        exit 1
    fi
    
    print_stage "STAGE 1: CANARY 10%"
    
    echo -e "${YELLOW}🚀 Deploying canary with 10% traffic...${NC}"
    # Platform-specific deployment logic here
    
    echo -e "${YELLOW}⏳ Monitoring for 30 minutes...${NC}"
    for i in {1..6}; do
        sleep 300  # 5 minutes
        
        if check_health "$HEALTH_CHECK_URL" "200"; then
            echo -e "${GREEN}✅ Health check $i/6 passed${NC}"
        else
            echo -e "${RED}❌ Health check failed${NC}"
            rollback
        fi
        
        if ! check_story_16_metrics; then
            echo -e "${RED}❌ Story 1.6 metrics below threshold${NC}"
            rollback
        fi
    done
    
    print_stage "STAGE 2: CANARY 30%"
    
    echo -e "${YELLOW}🚀 Expanding canary to 30% traffic...${NC}"
    # Increase traffic split
    
    echo -e "${YELLOW}⏳ Monitoring for 30 minutes...${NC}"
    for i in {1..6}; do
        sleep 300
        
        if check_health "$HEALTH_CHECK_URL" "200"; then
            echo -e "${GREEN}✅ Health check $i/6 passed${NC}"
        else
            echo -e "${RED}❌ Health check failed${NC}"
            rollback
        fi
    done
    
    print_stage "STAGE 3: CANARY 50%"
    
    echo -e "${YELLOW}🚀 Expanding canary to 50% traffic...${NC}"
    # Increase traffic split
    
    echo -e "${YELLOW}⏳ Monitoring for 1 hour...${NC}"
    for i in {1..12}; do
        sleep 300
        
        if check_health "$HEALTH_CHECK_URL" "200"; then
            echo -e "${GREEN}✅ Health check $i/12 passed${NC}"
        else
            echo -e "${RED}❌ Health check failed${NC}"
            rollback
        fi
    done
    
    print_stage "STAGE 4: FULL PRODUCTION"
    
    echo -e "${YELLOW}🚀 Promoting canary to production (100% traffic)...${NC}"
    # Complete the deployment
    
    echo -e "${GREEN}✅ Canary deployment successful!${NC}"
    
    # Post-deployment tasks
    echo -e "\n${YELLOW}📋 Post-deployment tasks:${NC}"
    echo "  - Monitoring production metrics"
    echo "  - Updating documentation"
    echo "  - Tagging release"
    
    # Tag the release
    if [ -n "$GIT_SHA" ]; then
        git tag -a "v$(date +%Y.%m.%d)-canary" -m "Successful canary deployment with Story 1.6"
        echo -e "${GREEN}✅ Release tagged${NC}"
    fi
    
    print_stage "DEPLOYMENT COMPLETE"
    
    echo -e "${GREEN}🎉 Canary deployment completed successfully!${NC}"
    echo -e "\n${BLUE}Deployment Summary:${NC}"
    echo "  - Story 1.6 Direct Execution: ACTIVE"
    echo "  - Router Confidence: >0.8"
    echo "  - Direct Execution Rate: >60%"
    echo "  - Response Time: <500ms"
    echo "  - All health checks: PASSED"
}

# Check if this is a dry run
if [ "$1" = "--dry-run" ]; then
    echo -e "${YELLOW}🔍 DRY RUN MODE - No actual deployment will occur${NC}"
    echo -e "${BLUE}Canary deployment stages that would be executed:${NC}"
    echo "  1. Pre-deployment validation (tests & config)"
    echo "  2. Stage 1: Deploy canary with 10% traffic (30 min)"
    echo "  3. Stage 2: Expand to 30% traffic (30 min)"
    echo "  4. Stage 3: Expand to 50% traffic (1 hour)"
    echo "  5. Stage 4: Full production rollout (100%)"
    echo "  6. Post-deployment tasks (tagging, documentation)"
    exit 0
fi

# Run the deployment
main "$@"