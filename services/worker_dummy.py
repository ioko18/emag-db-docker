# app/services/worker_dummy.py
import sys, time

def main():
    print("worker dummy: container OK, waiting for jobs…", flush=True)
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
