#!/usr/bin/env python3
"""
Server startup script for PKU Treehole Starred Saver API

This script provides an easy way to start the API server with different configurations.
"""

import argparse
import os
import sys
import uvicorn


def ensure_directories():
    """
    Ensure all necessary directories exist.
    """
    directories = ["TaskData", "static"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

    print("📁 Directory structure verified")


def check_dependencies():
    """
    Check if all required dependencies are installed.
    """
    required_modules = ["fastapi", "uvicorn", "requests", "matplotlib", "tqdm"]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        print(f"❌ Missing required modules: {', '.join(missing_modules)}")
        print("Please install them using: pip install -r requirements.txt")
        return False

    print("✅ All dependencies are installed")
    return True


def check_config_files():
    """
    Check if configuration files exist.
    """
    config_files = ["client.py", "crawler.py", "save_markdown.py", "config.py"]
    missing_files = []

    for file in config_files:
        if not os.path.exists(file):
            missing_files.append(file)

    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        return False

    print("✅ All required files are present")
    return True


def main():
    """
    Main entry point for the server startup script.
    """
    parser = argparse.ArgumentParser(
        description="Start PKU Treehole Starred Saver API Server"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent crawling tasks (default: 3)",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode (enables reload and debug logging)",
    )

    args = parser.parse_args()

    print("🚀 Starting PKU Treehole Starred Saver API Server")
    print("=" * 50)

    # Check dependencies and configuration
    if not check_dependencies():
        sys.exit(1)

    if not check_config_files():
        sys.exit(1)

    # Ensure directories exist
    ensure_directories()

    # Set environment variables for configuration
    os.environ["MAX_CONCURRENT_TASKS"] = str(args.max_concurrent)

    # Configure logging level
    log_level = "debug" if args.dev else "info"

    # Determine reload setting
    reload = args.reload or args.dev

    print(f"🌐 Server will start at http://{args.host}:{args.port}")
    print(f"⚙️  Max concurrent tasks: {args.max_concurrent}")
    print(f"🔄 Auto-reload: {'enabled' if reload else 'disabled'}")
    print(f"📝 Log level: {log_level}")
    print("=" * 50)

    try:
        # Start the server
        uvicorn.run(
            "api_server:app",
            host=args.host,
            port=args.port,
            reload=reload,
            log_level=log_level,
            access_log=True,
        )
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
