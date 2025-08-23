#!/usr/bin/env python3
"""
Simple test runner for EDINET Tools.

Focused testing approach with minimal dependencies:
1. Unit tests (API layer, client functionality)  
2. Integration tests (real API, file system)

Usage:
    python test_runner.py --help
    python test_runner.py --unit
    python test_runner.py --integration  
    python test_runner.py --all
"""

import argparse
import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED (exit code: {result.returncode})")
            return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False


def run_unit_tests():
    """Run unit tests (fast, no external dependencies)."""
    tests = [
        (["python", "-m", "pytest", "test/test_api.py", "-v", "--tb=short"], 
         "API Layer Unit Tests"),
        (["python", "-m", "pytest", "test/test_client.py", "-v", "--tb=short"], 
         "Client Interface Unit Tests"),
        (["python", "-m", "pytest", "test/test_data.py", "-v", "--tb=short"], 
         "Data Management Unit Tests"),
    ]
    
    results = []
    for cmd, desc in tests:
        results.append(run_command(cmd, desc))
    
    return all(results)


def run_integration_tests():
    """Run integration tests (API contracts, file system)."""
    tests = [
        (["python", "-m", "pytest", "test/test_integration_real.py", "-v", "-m", "integration"], 
         "Real API Contract Integration Tests"),
        (["python", "-m", "pytest", "test/test_integration.py", "-v"], 
         "End-to-End Integration Tests"),
    ]
    
    results = []
    for cmd, desc in tests:
        results.append(run_command(cmd, desc))
    
    return all(results)


def run_all_tests():
    """Run core test suite."""
    print("🧪 Running EDINET Tools Test Suite")
    print("=" * 60)
    
    all_results = []
    
    # Unit tests (fast)
    print("\n📋 PHASE 1: Unit Tests (Core Functionality)")
    all_results.append(run_unit_tests())
    
    # Integration tests  
    print("\n🔗 PHASE 2: Integration Tests (API & File System)")
    all_results.append(run_integration_tests())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 60)
    
    phase_names = ["Unit Tests", "Integration Tests"]
    for i, (name, passed) in enumerate(zip(phase_names, all_results)):
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"Phase {i+1} - {name}: {status}")
    
    overall_success = all(all_results)
    overall_status = "🎉 ALL TESTS PASSED" if overall_success else "⚠️  SOME TESTS FAILED"
    print(f"\nOverall Result: {overall_status}")
    
    return overall_success


def run_quick_smoke_test():
    """Run a quick smoke test to verify core functionality."""
    cmd = ["python", "-m", "pytest", "test/test_api.py::TestFetchDocument::test_url_construction_realistic_doc_id", "-v"]
    return run_command(cmd, "Quick Smoke Test (URL Construction)")


def main():
    parser = argparse.ArgumentParser(description="EDINET Tools Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only") 
    parser.add_argument("--smoke", action="store_true", help="Run quick smoke test")
    parser.add_argument("--all", action="store_true", help="Run all test phases")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage report")
    
    args = parser.parse_args()
    
    if not any([args.unit, args.integration, args.smoke, args.all]):
        print("No test type specified. Use --help for options.")
        print("Suggested: python test_runner.py --all")
        return 1
    
    success = True
    
    if args.smoke:
        success &= run_quick_smoke_test()
    elif args.unit:
        success &= run_unit_tests()
    elif args.integration:
        success &= run_integration_tests()  
    elif args.all:
        success &= run_all_tests()
    
    if args.coverage:
        print("\n📈 Generating Coverage Report...")
        run_command(
            ["python", "-m", "pytest", "--cov=edinet_tools", "--cov-report=html", "--cov-report=term"],
            "Coverage Analysis"
        )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())