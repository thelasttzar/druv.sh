#!/usr/bin/env python
import scanner
import time
import sys


def main():

    if len(sys.argv) == 2:
        account = sys.argv[1]
    elif len(sys.argv) == 1:
        account = 'Login1'
    else:
        print("[X] Invalid commands sent.")
        print("[X] Please use either ./main.py or ./main.py profile")

    for t in range(20):
        try:
            scanner.scan(account)
        except:
            pass

        print("Restarting scanner in 60 seconds.")
        time.sleep(60)

if __name__ == '__main__':
    main()
