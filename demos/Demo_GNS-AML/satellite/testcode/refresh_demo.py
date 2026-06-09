import os
import glob

# The same path used in your other scripts
DATA_PATH = "/mount/vast"

def reset():
    print("🧹 FLUSHING DATA LAKE...")
    files = glob.glob(f"{DATA_PATH}/*.parquet")
    
    count = 0
    for f in files:
        try:
            os.remove(f)
            count += 1
        except Exception as e:
            print(f"Error deleting {f}: {e}")
            
    print(f"✨ DONE. Deleted {count} files.")
    print("✅ System is ready for the next take.")

if __name__ == "__main__":
    reset()
