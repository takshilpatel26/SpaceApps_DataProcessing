"""SAR processing with progress monitoring and timeout."""

import subprocess
import time
import signal
import os


def run_with_timeout(cmd, timeout_minutes=45):
    """Run command with timeout and monitoring."""
    print(f"🚀 Starting: {' '.join(cmd)}")
    print(f"⏱️ Timeout: {timeout_minutes} minutes")

    start_time = time.time()

    try:
        # Run with timeout
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd="D:/Data Pre-Processing"
        )

        # Monitor progress
        while True:
            output = process.stdout.readline()
            if output:
                print(output.strip())

            # Check if process finished
            if process.poll() is not None:
                break

            # Check timeout
            elapsed = (time.time() - start_time) / 60
            if elapsed > timeout_minutes:
                print(f"⚠️ Timeout after {elapsed:.1f} minutes")
                process.terminate()
                time.sleep(5)
                if process.poll() is None:
                    process.kill()
                return False

        return process.returncode == 0

    except KeyboardInterrupt:
        print("🛑 Interrupted by user")
        process.terminate()
        return False


if __name__ == '__main__':
    # Set environment variables
    os.environ['JAVA_OPTS'] = '-Xmx12G -Xms4G'

    # Try CLI first
    cmd = ['python', '-m', 'src.sar_processor.cli.main', 'process-all']
    success = run_with_timeout(cmd, timeout_minutes=45)

    if not success:
        print("❌ CLI processing failed or timed out")
        print("🔄 Trying original script...")

        # Fallback to original script
        cmd = ['python', 'test-2.py']
        success = run_with_timeout(cmd, timeout_minutes=60)

        if success:
            print("✅ Original script completed successfully!")
        else:
            print("❌ Both methods failed")
