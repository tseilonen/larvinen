import argparse
import sys
from larvinen import start


parser = argparse.ArgumentParser(description='Start discord bot Lärvinen')
parser.add_argument('-d', '--development', default=False, action='store_true',
                    help='Start lärvinen in development mode')

args = parser.parse_args()


def run_larvinen():
    start(args.development)


if __name__ == '__main__':
    run_larvinen()
