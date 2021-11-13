# coding=utf-8
from src.Config import init, clearVar, hasInstance
from src.EventBus import EventBus
import os
import sys


def main():
    if hasInstance():
        return
    init()
    a = EventBus()
    a.loop()
    clearVar()


if __name__ == '__main__':
    main()
