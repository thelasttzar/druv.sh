#!/usr/bin/env python
import scanner
import time

def main():
    while True:
        try:
            scanner.scan()
        except Exception as e:
            print("Restarting scanner in 60 seconds.")
            time.sleep(60)

if __name__ == '__main__':
    main()
