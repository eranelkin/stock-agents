#!/bin/bash
# QA Test Runner for IB Data Configuration
# This script runs all configuration tests and validates the setup

set -e  # Exit on error

echo "=========================================="
echo "IB Data Configuration QA Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    print_error "pytest not found. Install with: pip install pytest"
    exit 1
fi

print_info "Running unit tests..."
echo ""

# Run unit tests
if pytest tests/test_config_qa.py -v; then
    print_success "Unit tests passed"
else
    print_error "Unit tests failed"
    exit 1
fi

echo ""
print_info "Validating test configuration files..."
echo ""

# Validate minimal config
if python -c "from src.config.loader import load_settings; from pathlib import Path; load_settings(Path('tests/test_configs/minimal_ib_data.yaml'))" 2>/dev/null; then
    print_success "minimal_ib_data.yaml is valid"
else
    print_error "minimal_ib_data.yaml is invalid"
    exit 1
fi

# Validate full config
if python -c "from src.config.loader import load_settings; from pathlib import Path; load_settings(Path('tests/test_configs/full_ib_data.yaml'))" 2>/dev/null; then
    print_success "full_ib_data.yaml is valid"
else
    print_error "full_ib_data.yaml is invalid"
    exit 1
fi

# Validate custom indicators config
if python -c "from src.config.loader import load_settings; from pathlib import Path; load_settings(Path('tests/test_configs/custom_indicators.yaml'))" 2>/dev/null; then
    print_success "custom_indicators.yaml is valid"
else
    print_error "custom_indicators.yaml is invalid"
    exit 1
fi

echo ""
print_info "Checking configuration field coverage..."
echo ""

# Check that all IBDataConfig fields are documented in settings.yaml
python << 'EOF'
from src.config.loader import IBDataConfig
from pathlib import Path
import dataclasses

config = IBDataConfig()
fields = [f.name for f in dataclasses.fields(config)]

settings_path = Path("config/settings.yaml")
if settings_path.exists():
    with open(settings_path, 'r') as f:
        content = f.read()
    
    missing = []
    for field in fields:
        if field not in content:
            missing.append(field)
    
    if missing:
        print(f"⚠ Warning: {len(missing)} fields not found in settings.yaml:")
        for field in missing:
            print(f"  - {field}")
        exit(1)
    else:
        print(f"✓ All {len(fields)} IBDataConfig fields are present in settings.yaml")
else:
    print("⚠ config/settings.yaml not found")
    exit 1
EOF

if [ $? -eq 0 ]; then
    print_success "Configuration field coverage is complete"
else
    print_error "Some configuration fields are missing"
    exit 1
fi

echo ""
print_info "Running integration tests (dry-run mode)..."
echo ""

# Test with default config (if main.py exists)
if [ -f "main.py" ]; then
    print_info "Testing default configuration..."
    if python main.py --mode screener --dry-run --no-hours-check --log-level WARNING 2>&1 | grep -q "dry-run"; then
        print_success "Default config dry-run completed"
    else
        print_error "Default config dry-run failed"
        exit 1
    fi
else
    print_info "Skipping integration tests (main.py not found)"
fi

echo ""
echo "=========================================="
print_success "All QA tests passed!"
echo "=========================================="
echo ""
echo "Configuration is ready for use."
echo ""
echo "Next steps:"
echo "  1. Review config/settings.yaml and adjust parameters"
echo "  2. Test with your IB Gateway connection"
echo "  3. Run: python main.py --mode screener --dry-run"
echo ""
