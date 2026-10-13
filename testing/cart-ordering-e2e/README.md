# Cart Ordering End-to-End Verification Harness

This directory contains the automated test harness, execution scripts, browser recordings/logs, screenshots, and verification reports for the cart-ordering fix on branch `feature/cart-ordering-fix-clean`.

## Directory Structure

```
testing/cart-ordering-e2e/
├── README.md                                  # Setup and execution instructions
├── test-scenarios.md                          # Detailed test scenario definitions
├── TEST_REPORT.md                             # Comprehensive test report backed by actual observations
├── test_cart_ordering.py                      # Playwright CDP automation verifying the 7 essential cart behaviors
├── test_runner.py                             # Full E2E voice interaction and navigation test runner
├── screenshots/                               # Actual captured browser screenshots for each milestone
│   ├── behavior_01_three_products_added.png
│   ├── behavior_02_item_moved_to_bottom.png
│   ├── behavior_03_item_removed_order_preserved.png
│   ├── behavior_04_sidebar_matches_cart_page.png
│   ├── behavior_05_rapid_mutation_guarded.png
│   ├── behavior_06_recommendation_badges.png
│   ├── behavior_06_after_single_dismiss.png
│   └── behavior_07_cart_cleared_ordering_reset.png
└── logs/                                      # Execution logs and JSON results
    ├── cart_ordering_verification_results.json
    └── cart_ordering_browser_console.log
```

## Prerequisites

1. **Backend Server**: FastAPI running on port 8000:
   ```bash
   cd backend && uvicorn api:app --reload --host 127.0.0.1 --port 8000
   ```
2. **Frontend Dev Server**: Vite running on port 5173:
   ```bash
   cd frontend && npm run dev
   ```
3. **Chrome Debugging Instance**: Google Chrome running with remote debugging port 9222:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_test_profile
   ```

## Running the Automated Verification

To execute the cart-ordering verification suite:
```bash
backend/venv311/bin/python testing/cart-ordering-e2e/test_cart_ordering.py
```

The script will:
- Connect directly to the browser via Chrome DevTools Protocol (CDP).
- Execute all 7 essential cart-ordering behaviors sequentially.
- Capture timestamped screenshots in `screenshots/`.
- Verify DOM assertions against actual browser state.
- Write test output to `logs/cart_ordering_verification_results.json`.
