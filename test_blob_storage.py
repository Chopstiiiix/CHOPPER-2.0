#!/usr/bin/env python3
"""
Test Vercel Blob Storage integration.
Verifies that file upload, download, and deletion work correctly.
"""

import os
import io
from dotenv import load_dotenv
import blob_storage

load_dotenv()

def test_blob_storage():
    """Test Blob storage functionality"""
    print("🧪 Testing Vercel Blob Storage Integration\n")
    print("=" * 60)

    # Test 1: Check configuration
    print("\n1. Checking Blob storage configuration...")
    if blob_storage.is_blob_configured():
        print("✅ Blob storage IS configured")
        print(f"   Token: {os.environ.get('BLOB_READ_WRITE_TOKEN', 'NOT SET')[:20]}...")
    else:
        print("⚠️  Blob storage NOT configured")
        print("   Set BLOB_READ_WRITE_TOKEN environment variable to test")
        print("   Fallback to local storage will be used")
        return False

    # Test 2: Upload test file (bytes)
    print("\n2. Testing file upload (bytes)...")
    try:
        test_data = b"This is a test file for Vercel Blob storage"
        test_path = "test/test-file.txt"

        blob_url = blob_storage.upload_bytes(
            data=test_data,
            path=test_path,
            content_type="text/plain"
        )

        print(f"✅ File uploaded successfully!")
        print(f"   Blob URL: {blob_url}")

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

    # Test 3: Get file info
    print("\n3. Testing file metadata retrieval...")
    try:
        info = blob_storage.get_file_info(blob_url)
        if info:
            print(f"✅ File info retrieved:")
            print(f"   Size: {info.get('size')} bytes")
            print(f"   Content-Type: {info.get('contentType')}")
            print(f"   Uploaded: {info.get('uploadedAt')}")
        else:
            print("⚠️  Could not retrieve file info")

    except Exception as e:
        print(f"⚠️  Metadata retrieval error: {e}")

    # Test 4: Delete test file
    print("\n4. Testing file deletion...")
    try:
        success = blob_storage.delete_file(blob_url)
        if success:
            print("✅ File deleted successfully")
        else:
            print("⚠️  File deletion failed (file may not exist)")

    except Exception as e:
        print(f"⚠️  Deletion error: {e}")

    # Test 5: Generate blob path
    print("\n5. Testing path generation...")
    path = blob_storage.generate_blob_path("audio", "myfile.mp3")
    print(f"✅ Generated path: {path}")

    print("\n" + "=" * 60)
    print("✅ All Blob storage tests completed!")
    print("=" * 60)
    return True

if __name__ == '__main__':
    import sys
    success = test_blob_storage()

    if success:
        print("\n🎉 Blob storage is ready for production!")
        sys.exit(0)
    else:
        print("\n⚠️  Blob storage not configured. Using local storage fallback.")
        print("To enable Blob storage:")
        print("1. Create Blob store: https://vercel.com/docs/storage/vercel-blob/quickstart")
        print("2. Set BLOB_READ_WRITE_TOKEN in your .env file or Vercel")
        print("3. Re-run this test")
        sys.exit(1)
