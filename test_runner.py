#!/usr/bin/env python3
"""
Test runner for EDINET Tools.

Organized testing approach using pytest markers:
1. Unit tests (fast, mocked, ~260 tests)
2. Integration tests (real API, ~25 tests)
3. Slow tests (CSV loading, ~2 tests)

Usage:
    python test_runner.py --help
    python test_runner.py --unit        # Fast unit tests only
    python test_runner.py --integration # Integration tests with real API
    python test_runner.py --all         # All tests (~287 total)
    python test_runner.py --smoke       # Quick validation
"""

import argparse
import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n🔄 {description}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            
            # Check if tests were skipped
            if "skipped" in result.stdout.lower() and "passed" not in result.stdout.lower():
                print(f"⏭️  SKIPPED - No API key configured")
                return True
            
            # Show the full pytest output for successful runs
            print(result.stdout)
            
            # Find the summary line with passed results
            summary_line = None
            for line in lines:
                if 'passed' in line and 'in' in line and '=' in line:
                    summary_line = line
                    break
            
            if summary_line:
                # Extract text between the equal sign borders
                import re
                match = re.search(r'=+\s*(.+?)\s*=+', summary_line)
                if match:
                    result_part = match.group(1).strip()
                    print(f"\n✅ SUCCESS: {result_part}")
                else:
                    print(f"\n✅ SUCCESS: Tests completed")
            else:
                print(f"\n✅ SUCCESS: Tests completed")
            
            return True
        else:
            print(f"❌ FAILED (exit code: {result.returncode})")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def run_unit_tests():
    """Run unit tests (fast, no external dependencies)."""
    # Use pytest markers to run fast unit tests only
    cmd = ["python", "-m", "pytest", "-m", "not slow and not integration", "-v", "--tb=short"]
    return run_command(cmd, "Unit Tests (fast, mocked, ~260 tests)")


def run_integration_tests():
    """Run integration tests (API contracts, file system)."""
    import os
    
    # Load config to get API key from .env file
    try:
        from edinet_tools.config import EDINET_API_KEY
        api_key = EDINET_API_KEY or os.environ.get('EDINET_API_KEY')
    except ImportError:
        api_key = os.environ.get('EDINET_API_KEY')
    
    if not api_key:
        print("\n" + "="*60)
        print("⏭️  INTEGRATION TESTS SKIPPED - NO API KEY")
        print("="*60)
        print("   EDINET_API_KEY not found in .env file or environment")
        print("   To run integration tests:")
        print("   1. Add EDINET_API_KEY='your_key_here' to .env file, OR")
        print("   2. Set environment variable: export EDINET_API_KEY='your_key_here'")
        print("="*60)
        return True  # Return True since skipping is expected behavior
    
    if len(api_key.strip()) < 10:
        print("\n" + "="*60)
        print(f"⏭️  INTEGRATION TESTS SKIPPED - INVALID API KEY")
        print("="*60)
        print(f"   EDINET_API_KEY too short: {len(api_key)} chars (expected >10)")
        print("   Please check your API key in .env file or environment variable")
        print("="*60)
        return True
    
    # Use pytest marker to run integration tests
    cmd = ["python", "-m", "pytest", "-m", "integration", "-v", "--tb=short"]
    return run_command(cmd, "Integration Tests (real API calls, ~25 tests)")


def run_all_tests():
    """Run complete test suite including slow tests."""
    print("\n🧪 EDINET Tools - Complete Test Suite")
    print("📊 Running all 287 tests (unit + integration + slow)")
    print("⏱️  Expected runtime: ~2-3 minutes")
    
    # Run all tests without exclusions
    cmd = ["python", "-m", "pytest", "-v", "--tb=short"]
    return run_command(cmd, "Complete Test Suite (287 tests)")


def run_slow_tests():
    """Run slow tests (CSV loading, etc.)."""
    cmd = ["python", "-m", "pytest", "-m", "slow", "-v", "--tb=short"]
    return run_command(cmd, "Slow Tests (CSV loading, ~2 tests)")


def run_quick_smoke_test():
    """Run a quick smoke test to verify core functionality."""
    # Test a few key components quickly
    tests = [
        "test/test_analysis.py::TestPydanticSchemas::test_one_line_summary_valid_data",
        "test/test_api.py::TestAPIWorkflow::test_find_and_download_document_workflow",
        "test/test_client.py::TestEdinetClientInitialization::test_init_with_env_var"
    ]
    cmd = ["python", "-m", "pytest"] + tests + ["-v", "--tb=short"]
    return run_command(cmd, "Quick Smoke Test (3 key functionality tests)")


def main():
    parser = argparse.ArgumentParser(
        description="EDINET Tools Test Runner",
        epilog="""Examples:
  python test_runner.py --unit        # Fast development testing (~30s)
  python test_runner.py --integration # API contract validation
  python test_runner.py --all         # Complete test suite (~2-3min)
  python test_runner.py --smoke       # Quick functionality check""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--unit", action="store_true", help="Run unit tests only (~260 tests, <2min)")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only (~25 tests, requires API key)")
    parser.add_argument("--slow", action="store_true", help="Run slow tests only (~2 tests, CSV loading)")
    parser.add_argument("--smoke", action="store_true", help="Run quick smoke test (3 tests, <5s)")
    parser.add_argument("--all", action="store_true", help="Run all tests (287 tests, 2-3min)")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage report")
    
    args = parser.parse_args()
    
    if not any([args.unit, args.integration, args.slow, args.smoke, args.all]):
        print("No test type specified. Use --help for options.")
        print("\n💡 Recommended for development: python test_runner.py --unit")
        print("💡 Recommended before release: python test_runner.py --all")
        return 1
    
    success = True
    
    if args.smoke:
        success &= run_quick_smoke_test()
    elif args.unit:
        success &= run_unit_tests()
    elif args.integration:
        success &= run_integration_tests()
    elif args.slow:
        success &= run_slow_tests()
    elif args.all:
        success &= run_all_tests()
    
    if args.coverage:
        print("\n📈 Generating Coverage Report...")
        run_command(
            ["python", "-m", "pytest", "-m", "not integration", "--cov=edinet_tools", "--cov-report=html", "--cov-report=term"],
            "Coverage Analysis (excluding integration tests)"
        )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())